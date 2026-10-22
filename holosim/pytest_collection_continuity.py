"""Bounded, read-only comparison of witnessed pytest collection identities."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

MAX_NODE_IDS = 10000
MAX_NODE_ID_LENGTH = 4096
VERSION = 1


class PytestCollectionContinuityError(ValueError):
    """Invalid or unsupported collection observation."""


def _normalize_node_ids(value: Any) -> tuple[str, ...]:
    if type(value) not in (list, tuple):
        raise PytestCollectionContinuityError("node_ids must be a list or tuple")
    if len(value) > MAX_NODE_IDS:
        raise PytestCollectionContinuityError("too many node_ids")

    result = []

    for node_id in value:
        if (
            type(node_id) is not str
            or not node_id
            or not node_id.strip()
            or len(node_id) > MAX_NODE_ID_LENGTH
            or "\x00" in node_id
        ):
            raise PytestCollectionContinuityError("invalid node_id")
        result.append(node_id)

    if len(set(result)) != len(result):
        raise PytestCollectionContinuityError("duplicate node_id")

    return tuple(sorted(result))


def _hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def observe_pytest_collection(*, node_ids: list[str] | tuple[str, ...]) -> dict[str, Any]:
    """Record supplied identities, not independently verify pytest execution."""
    normalized = _normalize_node_ids(node_ids)

    body = {
        "type": "pytest_collection_observation",
        "version": VERSION,
        "node_ids": list(normalized),
        "count": len(normalized),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "observation_id": _hash(body)}


def _verify_observation(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        raise PytestCollectionContinuityError("observation must be an object")

    if set(value) != {
        "type", "version", "node_ids", "count",
        "truth_claimed", "accepted", "write_authority",
        "observation_id",
    }:
        raise PytestCollectionContinuityError("observation fields do not match schema")

    expected_types = {
        "type": str,
        "version": int,
        "node_ids": list,
        "count": int,
        "truth_claimed": bool,
        "accepted": bool,
        "write_authority": str,
        "observation_id": str,
    }
    for field, expected_type in expected_types.items():
        if type(value[field]) is not expected_type:
            raise PytestCollectionContinuityError(
                f"invalid observation field type: {field}"
            )
    expected = observe_pytest_collection(node_ids=value["node_ids"])

    if value != expected:
        raise PytestCollectionContinuityError("observation does not match replay")

    return expected


def compare_pytest_collections(
    *,
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare witnessed identities without accepting or authorizing changes."""
    before = _verify_observation(previous)
    after = _verify_observation(current)

    previous_ids = set(before["node_ids"])
    current_ids = set(after["node_ids"])

    missing = sorted(previous_ids - current_ids)
    added = sorted(current_ids - previous_ids)
    retained = sorted(previous_ids & current_ids)

    body = {
        "type": "pytest_collection_continuity_comparison",
        "version": VERSION,
        "previous_observation_id": before["observation_id"],
        "current_observation_id": after["observation_id"],
        "previous_count": before["count"],
        "current_count": after["count"],
        "retained": retained,
        "missing": missing,
        "added": added,
        "status": "LOSS_DETECTED" if missing else "PRESERVED",
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "comparison_id": _hash(body)}
