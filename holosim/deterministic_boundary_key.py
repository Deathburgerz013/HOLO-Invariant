"""Deterministic, non-authoritative keys for explicit boundary descriptors."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any


RECEIPT_TYPE = "deterministic_boundary_key_receipt"
RECEIPT_VERSION = 1
KEY_ALGORITHM = "sha256"
KEY_DOMAIN = "holo.boundary-key.v1"

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_DESCRIPTOR_FIELDS = {
    "namespace",
    "subject_type",
    "subject_id",
    "scope",
    "contract_type",
    "contract_version",
}
_RECEIPT_FIELDS = {
    "type",
    "version",
    "descriptor",
    "descriptor_hash",
    "key_algorithm",
    "key_domain",
    "boundary_key",
    "accepted",
    "write_authority",
    "interpretation_notice",
    "receipt_hash",
}


class BoundaryKeyError(ValueError):
    """Raised when a stable boundary key cannot be derived honestly."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise BoundaryKeyError("value could not be canonicalized") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _identifier(value: Any, field: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise BoundaryKeyError(f"{field} is invalid or ambiguous")
    return value


def _normalize_descriptor(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _DESCRIPTOR_FIELDS:
        raise BoundaryKeyError("descriptor fields mismatch")
    version = value["contract_version"]
    if type(version) is not int or version < 1:
        raise BoundaryKeyError("contract_version must be a positive integer")
    return {
        "namespace": _identifier(value["namespace"], "namespace"),
        "subject_type": _identifier(value["subject_type"], "subject_type"),
        "subject_id": _identifier(value["subject_id"], "subject_id"),
        "scope": _identifier(value["scope"], "scope"),
        "contract_type": _identifier(value["contract_type"], "contract_type"),
        "contract_version": version,
    }


def _derive_key(descriptor: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        KEY_DOMAIN.encode("ascii") + b"\x00" + _canonical_bytes(descriptor)
    ).hexdigest()
    return f"{KEY_DOMAIN}:{digest}"


def make_boundary_key_receipt(descriptor: Mapping[str, Any]) -> dict[str, Any]:
    """Derive one stable key from one closed, explicit descriptor."""
    normalized = _normalize_descriptor(descriptor)
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "descriptor": normalized,
        "descriptor_hash": _hash(normalized),
        "key_algorithm": KEY_ALGORITHM,
        "key_domain": KEY_DOMAIN,
        "boundary_key": _derive_key(normalized),
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "The key identifies this exact declared descriptor. It does not prove "
            "truth, authorship, uniqueness beyond the hash assumption, acceptance, "
            "or authority."
        ),
    }
    return {**body, "receipt_hash": _hash(body)}


def verify_boundary_key_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Verify structure and deterministic derivation without granting authority."""
    failures: list[str] = []
    if not isinstance(receipt, Mapping) or set(receipt) != _RECEIPT_FIELDS:
        raise BoundaryKeyError("receipt fields mismatch")

    try:
        descriptor = _normalize_descriptor(receipt["descriptor"])
    except BoundaryKeyError:
        descriptor = None
        failures.append("descriptor_invalid")

    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        failures.append("receipt_contract_mismatch")
    if receipt["key_algorithm"] != KEY_ALGORITHM:
        failures.append("key_algorithm_mismatch")
    if receipt["key_domain"] != KEY_DOMAIN:
        failures.append("key_domain_mismatch")
    if receipt["accepted"] is not False or receipt["write_authority"] != "NONE":
        failures.append("forbidden_authority")

    if descriptor is not None:
        if receipt["descriptor_hash"] != _hash(descriptor):
            failures.append("descriptor_hash_mismatch")
        if receipt["boundary_key"] != _derive_key(descriptor):
            failures.append("boundary_key_mismatch")

    body = {key: receipt[key] for key in receipt if key != "receipt_hash"}
    if receipt["receipt_hash"] != _hash(body):
        failures.append("receipt_hash_mismatch")

    result_body = {
        "type": "deterministic_boundary_key_check",
        "version": 1,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "boundary_key": receipt["boundary_key"],
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**result_body, "check_hash": _hash(result_body)}
