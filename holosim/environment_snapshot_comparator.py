"""Read-only comparison of canonical environmental observation snapshots."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.environment_snapshot import verify_snapshot


COMPARISON_TYPE = "environment_snapshot_comparison"
COMPARISON_VERSION = 1


class SnapshotComparisonError(ValueError):
    """Raised when two snapshots cannot form a valid comparison."""


def _timestamp(value: str) -> datetime:
    parse_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(parse_value)


def _require_valid_snapshot(snapshot: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise SnapshotComparisonError(f"{label} must be a snapshot object")
    verification = verify_snapshot(snapshot)
    if not verification["valid"]:
        details = "; ".join(verification["violations"])
        raise SnapshotComparisonError(f"{label} is invalid: {details}")
    return snapshot


def _object_delta(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    before_keys = set(before)
    after_keys = set(after)
    shared_keys = before_keys & after_keys
    changed_keys = sorted(
        key for key in shared_keys if before[key] != after[key]
    )
    return {
        "added": {
            key: deepcopy(after[key]) for key in sorted(after_keys - before_keys)
        },
        "removed": {
            key: deepcopy(before[key]) for key in sorted(before_keys - after_keys)
        },
        "changed": {
            key: {
                "before": deepcopy(before[key]),
                "after": deepcopy(after[key]),
            }
            for key in changed_keys
        },
        "unchanged_keys": sorted(
            key for key in shared_keys if before[key] == after[key]
        ),
    }


def _list_delta(before: list[Any], after: list[Any]) -> dict[str, Any]:
    """Return a canonical multiset delta while preserving source order."""
    try:
        before_ids = [stable_hash(item) for item in before]
        after_ids = [stable_hash(item) for item in after]
    except CanonicalValueError as exc:
        raise SnapshotComparisonError(str(exc)) from exc

    remaining_after = list(after_ids)
    retained_ids: list[str] = []
    removed: list[Any] = []
    for item, item_id in zip(before, before_ids):
        if item_id in remaining_after:
            retained_ids.append(item_id)
            remaining_after.remove(item_id)
        else:
            removed.append(deepcopy(item))

    remaining_retained = list(retained_ids)
    added: list[Any] = []
    retained: list[Any] = []
    for item, item_id in zip(after, after_ids):
        if item_id in remaining_retained:
            retained.append(deepcopy(item))
            remaining_retained.remove(item_id)
        else:
            added.append(deepcopy(item))

    return {"added": added, "removed": removed, "retained": retained}


def _context_delta(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    scalar_fields = (
        "check_id",
        "check_purpose",
        "goal_reference",
        "clock_id",
        "feature_schema_id",
    )
    changed = {
        field: {
            "before": deepcopy(before[field]),
            "after": deepcopy(after[field]),
        }
        for field in scalar_fields
        if before[field] != after[field]
    }
    observer_delta = _list_delta(
        list(before["observer_ids"]),
        list(after["observer_ids"]),
    )
    return {
        "changed": changed,
        "observer_ids": observer_delta,
        "comparable_feature_schema": (
            before["feature_schema_id"] == after["feature_schema_id"]
        ),
    }


def compare_snapshots(
    before_snapshot: Mapping[str, Any],
    after_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two valid snapshots without judging truth or completion."""
    before = _require_valid_snapshot(before_snapshot, "before_snapshot")
    after = _require_valid_snapshot(after_snapshot, "after_snapshot")

    if before["environment_id"] != after["environment_id"]:
        raise SnapshotComparisonError(
            "snapshots must describe the same environment_id"
        )
    if before["episode_id"] != after["episode_id"]:
        raise SnapshotComparisonError(
            "snapshots must describe the same episode_id"
        )
    if _timestamp(after["observed_at"]) <= _timestamp(before["observed_at"]):
        raise SnapshotComparisonError(
            "after_snapshot observed_at must be later than before_snapshot"
        )

    payload: dict[str, Any] = {
        "type": COMPARISON_TYPE,
        "version": COMPARISON_VERSION,
        "episode_id": before["episode_id"],
        "environment_id": before["environment_id"],
        "before_snapshot_id": before["snapshot_id"],
        "after_snapshot_id": after["snapshot_id"],
        "before_observed_at": before["observed_at"],
        "after_observed_at": after["observed_at"],
        "context": _context_delta(before, after),
        "observed": _object_delta(before["observed"], after["observed"]),
        "missing": _list_delta(before["missing"], after["missing"]),
        "unknown": _list_delta(before["unknown"], after["unknown"]),
        "assumptions": _list_delta(
            before["assumptions"], after["assumptions"]
        ),
        "falsifiers": _list_delta(before["falsifiers"], after["falsifiers"]),
        "uncertainty": _list_delta(
            before["uncertainty"], after["uncertainty"]
        ),
        "evidence_sha256": _list_delta(
            before["evidence_sha256"], after["evidence_sha256"]
        ),
        "provenance": _object_delta(
            before["provenance"], after["provenance"]
        ),
        "completion_evaluated": False,
        "correction_evaluated": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This comparison reports structural differences between two "
            "observations. It does not establish truth, improvement, "
            "completion, correction eligibility, or permission to write."
        ),
    }

    try:
        comparison_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise SnapshotComparisonError(str(exc)) from exc
    return {**payload, "comparison_id": comparison_id}