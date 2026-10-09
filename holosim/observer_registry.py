"""Experimental ordered observer registrations using HoloChain's atomic append.

An observer number is a recorded position, not proof of AI identity.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from holosim.canonical import canonical_json, stable_hash
from holosim.core import HoloChain

GENESIS = "0" * 64
KIND = "holo_observer_registration"


class ObserverRegistryError(ValueError):
    """A registry entry, predecessor, or registration request is invalid."""


def _digest(value: Any, field: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ObserverRegistryError(f"{field} must be a lowercase 64-character hex digest")
    return value


MAX_DECLARATION_BYTES = 65536


def _declaration(value: Any) -> str:
    if type(value) is not str or not value.strip():
        raise ObserverRegistryError("invalid observer declaration")
    if len(value.encode("utf-8")) > MAX_DECLARATION_BYTES:
        raise ObserverRegistryError("declaration exceeds size limit")
    return value


def verify_records(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verify observer-specific succession inside an already verified chain."""
    records: list[dict[str, Any]] = []
    for entry in entries:
        try:
            record = json.loads(entry["content"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ObserverRegistryError("registry contains invalid JSON") from exc
        if type(record) is not dict or entry["content"] != canonical_json(record):
            raise ObserverRegistryError("registry contains noncanonical JSON")
        if set(record) != {
            "type", "version", "sequence", "observer_id", "previous_record_hash",
            "source_checkpoint_hash", "declaration", "record_hash",
        }:
            raise ObserverRegistryError("registry schema mismatch")
        seq = len(records) + 1
        previous = GENESIS if not records else records[-1]["record_hash"]
        if (record["type"] != KIND or type(record["version"]) is not int
                or record["version"] != 1 or type(record["sequence"]) is not int
                or record["sequence"] != seq or record["observer_id"] != f"AI-{seq:06d}"
                or record["previous_record_hash"] != previous):
            raise ObserverRegistryError("registry succession mismatch")
        _digest(record["source_checkpoint_hash"], "source_checkpoint_hash")
        _declaration(record["declaration"])
        body = {key: value for key, value in record.items() if key != "record_hash"}
        if record["record_hash"] != stable_hash(body):
            raise ObserverRegistryError("registry record hash mismatch")
        records.append(record)
    return records


class ObserverRegistry:
    """Locally ordered registrations in a dedicated HoloChain file."""

    def __init__(self, path: str | Path):
        self.chain = HoloChain(path)

    def read(self) -> list[dict[str, Any]]:
        return verify_records(self.chain.load_and_verify())

    def register(self, *, source_checkpoint_hash: str, declaration: str,
                 expected_previous_record_hash: str) -> dict[str, Any]:
        """Append only if the verified head still matches the caller's head.

        The caller must explicitly refresh on a stale-head failure. This
        prevents a hidden retry from silently changing its declared predecessor.
        """
        _digest(source_checkpoint_hash, "source_checkpoint_hash")
        _digest(expected_previous_record_hash, "expected_previous_record_hash")
        _declaration(declaration)
        records = self.read()
        current = GENESIS if not records else records[-1]["record_hash"]
        if current != expected_previous_record_hash:
            raise ObserverRegistryError("stale registry head")
        sequence = len(records) + 1
        body = {
            "type": KIND,
            "version": 1,
            "sequence": sequence,
            "observer_id": f"AI-{sequence:06d}",
            "previous_record_hash": current,
            "source_checkpoint_hash": source_checkpoint_hash,
            "declaration": declaration,
        }
        record = {**body, "record_hash": stable_hash(body)}

        def check(entries: list[dict[str, Any]]) -> None:
            verified = verify_records(entries)
            head = GENESIS if not verified else verified[-1]["record_hash"]
            if head != expected_previous_record_hash or len(verified) != sequence - 1:
                raise ObserverRegistryError("stale registry head")

        self.chain.append(canonical_json(record), precondition=check)
        return record
