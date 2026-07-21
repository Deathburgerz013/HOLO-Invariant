"""Shared check-identity binding for environment observation snapshots."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.check_identity import build_check_identity
from holosim.environment_snapshot import SnapshotValidationError, verify_snapshot


def build_environment_snapshot_check_identity(
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a shared check identity for one verified environment snapshot.

    The snapshot keeps its own ``snapshot_id``. This function identifies the
    check that produced the observation, so check identity and observation
    identity remain distinct and independently verifiable.
    """
    if not isinstance(snapshot, Mapping):
        raise SnapshotValidationError("snapshot must be an object")

    verification = verify_snapshot(snapshot)
    if verification["valid"] is not True:
        raise SnapshotValidationError(
            "cannot bind check identity to an invalid snapshot: "
            + "; ".join(verification["violations"])
        )

    snapshot_id = snapshot.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise SnapshotValidationError("snapshot requires snapshot_id")

    provenance = snapshot.get("provenance")
    if not isinstance(provenance, Mapping) or not provenance:
        raise SnapshotValidationError("snapshot provenance cannot be empty")

    evidence = snapshot.get("evidence_sha256")
    if not isinstance(evidence, list):
        raise SnapshotValidationError("snapshot evidence_sha256 must be a list")

    return build_check_identity(
        check_id=snapshot["check_id"],
        check_type="environment_observation",
        subject={
            "environment_id": snapshot["environment_id"],
            "episode_id": snapshot["episode_id"],
            "snapshot_id": snapshot_id,
        },
        reference_ids=[
            snapshot["goal_reference"],
            snapshot["feature_schema_id"],
        ],
        scope={
            "check_purpose": snapshot["check_purpose"],
            "observer_ids": deepcopy(snapshot["observer_ids"]),
            "clock_id": snapshot["clock_id"],
            "observed_at": snapshot["observed_at"],
        },
        evidence_references=list(evidence),
        rule_references=[snapshot["feature_schema_id"]],
        input_state_hash=snapshot_id,
    )
