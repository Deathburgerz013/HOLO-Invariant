"""Shared check-identity binding for environment snapshot comparisons."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.check_identity import build_check_identity
from holosim.environment_snapshot_comparator import (
    COMPARISON_TYPE,
    COMPARISON_VERSION,
    SnapshotComparisonError,
)


def _require_valid_comparison(comparison: Any) -> Mapping[str, Any]:
    if not isinstance(comparison, Mapping):
        raise SnapshotComparisonError("comparison must be an object")

    if comparison.get("type") != COMPARISON_TYPE:
        raise SnapshotComparisonError("comparison type is invalid")
    if comparison.get("version") != COMPARISON_VERSION:
        raise SnapshotComparisonError("comparison version is invalid")
    if comparison.get("accepted") is not False:
        raise SnapshotComparisonError("comparison must remain non-accepting")
    if comparison.get("write_authority") != "NONE":
        raise SnapshotComparisonError("comparison must have no write authority")

    comparison_id = comparison.get("comparison_id")
    if not isinstance(comparison_id, str) or not comparison_id:
        raise SnapshotComparisonError("comparison requires comparison_id")

    body = {
        key: deepcopy(value)
        for key, value in comparison.items()
        if key != "comparison_id"
    }
    try:
        expected = stable_hash(body)
    except CanonicalValueError as exc:
        raise SnapshotComparisonError(str(exc)) from exc
    if expected != comparison_id:
        raise SnapshotComparisonError("comparison identity mismatch")

    return comparison


def _evidence_references(comparison: Mapping[str, Any]) -> list[str]:
    delta = comparison.get("evidence_sha256")
    if not isinstance(delta, Mapping):
        raise SnapshotComparisonError("comparison evidence_sha256 delta is invalid")

    references: list[str] = []
    for field in ("added", "removed", "retained"):
        values = delta.get(field)
        if not isinstance(values, list):
            raise SnapshotComparisonError(
                f"comparison evidence_sha256.{field} must be a list"
            )
        for value in values:
            if not isinstance(value, str) or not value:
                raise SnapshotComparisonError(
                    "comparison evidence references must be non-empty strings"
                )
            if value not in references:
                references.append(value)
    return references


def build_environment_snapshot_comparison_check_identity(
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a shared check identity for one verified snapshot comparison.

    ``comparison_id`` remains the identity of the comparison artifact. The shared
    identity names the comparison operation from its exact input snapshot pair.
    """
    verified = _require_valid_comparison(comparison)

    before_snapshot_id = verified.get("before_snapshot_id")
    after_snapshot_id = verified.get("after_snapshot_id")
    if not isinstance(before_snapshot_id, str) or not before_snapshot_id:
        raise SnapshotComparisonError("comparison requires before_snapshot_id")
    if not isinstance(after_snapshot_id, str) or not after_snapshot_id:
        raise SnapshotComparisonError("comparison requires after_snapshot_id")

    input_descriptor = {
        "type": "environment_snapshot_comparison_input",
        "before_snapshot_id": before_snapshot_id,
        "after_snapshot_id": after_snapshot_id,
    }
    input_state_hash = stable_hash(input_descriptor)
    check_id = stable_hash(
        {
            "type": "environment_snapshot_comparison_check",
            "input_state_hash": input_state_hash,
        }
    )

    return build_check_identity(
        check_id=check_id,
        check_type="environment_snapshot_comparison",
        subject={
            "environment_id": verified["environment_id"],
            "episode_id": verified["episode_id"],
            "comparison_id": verified["comparison_id"],
        },
        reference_ids=[before_snapshot_id, after_snapshot_id],
        scope={
            "before_observed_at": verified["before_observed_at"],
            "after_observed_at": verified["after_observed_at"],
            "context": deepcopy(verified["context"]),
        },
        evidence_references=_evidence_references(verified),
        rule_references=[],
        input_state_hash=input_state_hash,
    )
