"""Read-only environmental observation snapshots for HOLO/Sim."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash


SNAPSHOT_TYPE = "environment_observation_snapshot"
SNAPSHOT_VERSION = 1
VERIFICATION_TYPE = "environment_observation_snapshot_verification"
VERIFICATION_VERSION = 1

SNAPSHOT_PAYLOAD_FIELDS = (
    "type",
    "version",
    "episode_id",
    "environment_id",
    "check_id",
    "check_purpose",
    "goal_reference",
    "observer_ids",
    "clock_id",
    "observed_at",
    "feature_schema_id",
    "observed",
    "missing",
    "unknown",
    "assumptions",
    "falsifiers",
    "evidence_sha256",
    "provenance",
    "uncertainty",
    "accepted",
    "write_authority",
)


class SnapshotValidationError(ValueError):
    """Raised when a proposed snapshot violates the snapshot contract."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotValidationError(f"{field} must be a nonempty string")
    return value.strip()


def _unique_text_list(values: Sequence[str], field: str) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise SnapshotValidationError(f"{field} must be a list of strings")

    normalized = [_required_text(value, field) for value in values]
    if not normalized:
        raise SnapshotValidationError(f"{field} cannot be empty")
    if len(set(normalized)) != len(normalized):
        raise SnapshotValidationError(f"{field} cannot contain duplicates")
    return normalized


def _validate_observed_at(value: Any) -> str:
    observed_at = _required_text(value, "observed_at")
    parse_value = (
        observed_at[:-1] + "+00:00"
        if observed_at.endswith("Z")
        else observed_at
    )
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError as exc:
        raise SnapshotValidationError(
            "observed_at must be a valid ISO-8601 timestamp"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SnapshotValidationError(
            "observed_at must include an explicit timezone"
        )
    return observed_at


def _validate_evidence_hashes(values: Sequence[str]) -> list[str]:
    hashes = _unique_text_list(values, "evidence_sha256")
    for value in hashes:
        if len(value) != 64 or any(
            character not in "0123456789abcdef"
            for character in value
        ):
            raise SnapshotValidationError(
                "evidence_sha256 values must be lowercase SHA-256 hex"
            )
    return hashes


def _json_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise SnapshotValidationError(f"{field} must be a list")
    return deepcopy(value)


def _json_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SnapshotValidationError(f"{field} must be an object")
    return deepcopy(dict(value))


def _snapshot_payload(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    missing_fields = [
        field for field in SNAPSHOT_PAYLOAD_FIELDS if field not in snapshot
    ]
    if missing_fields:
        raise SnapshotValidationError(
            "snapshot is missing fields: " + ", ".join(missing_fields)
        )
    return {
        field: deepcopy(snapshot[field])
        for field in SNAPSHOT_PAYLOAD_FIELDS
    }


def build_snapshot(
    *,
    episode_id: str,
    environment_id: str,
    check_id: str,
    check_purpose: str,
    goal_reference: str,
    observer_ids: Sequence[str],
    clock_id: str,
    observed_at: str,
    feature_schema_id: str,
    observed: Mapping[str, Any],
    missing: list[Any],
    unknown: list[Any],
    assumptions: list[Any],
    falsifiers: list[Any],
    evidence_sha256: Sequence[str],
    provenance: Mapping[str, Any],
    uncertainty: list[Any],
) -> dict[str, Any]:
    """Build a deterministic, non-authoritative observation snapshot."""
    payload: dict[str, Any] = {
        "type": SNAPSHOT_TYPE,
        "version": SNAPSHOT_VERSION,
        "episode_id": _required_text(episode_id, "episode_id"),
        "environment_id": _required_text(
            environment_id,
            "environment_id",
        ),
        "check_id": _required_text(check_id, "check_id"),
        "check_purpose": _required_text(
            check_purpose,
            "check_purpose",
        ),
        "goal_reference": _required_text(
            goal_reference,
            "goal_reference",
        ),
        "observer_ids": _unique_text_list(observer_ids, "observer_ids"),
        "clock_id": _required_text(clock_id, "clock_id"),
        "observed_at": _validate_observed_at(observed_at),
        "feature_schema_id": _required_text(
            feature_schema_id,
            "feature_schema_id",
        ),
        "observed": _json_object(observed, "observed"),
        "missing": _json_list(missing, "missing"),
        "unknown": _json_list(unknown, "unknown"),
        "assumptions": _json_list(assumptions, "assumptions"),
        "falsifiers": _json_list(falsifiers, "falsifiers"),
        "evidence_sha256": _validate_evidence_hashes(evidence_sha256),
        "provenance": _json_object(provenance, "provenance"),
        "uncertainty": _json_list(uncertainty, "uncertainty"),
        "accepted": False,
        "write_authority": "NONE",
    }

    if not payload["provenance"]:
        raise SnapshotValidationError("provenance cannot be empty")

    try:
        snapshot_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise SnapshotValidationError(str(exc)) from exc

    return {**payload, "snapshot_id": snapshot_id}


def verify_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Verify snapshot structure and identity without mutation."""
    violations: list[str] = []
    expected_snapshot_id: str | None = None
    actual_snapshot_id = snapshot.get("snapshot_id")

    try:
        payload = _snapshot_payload(snapshot)
        rebuilt = build_snapshot(
            episode_id=payload["episode_id"],
            environment_id=payload["environment_id"],
            check_id=payload["check_id"],
            check_purpose=payload["check_purpose"],
            goal_reference=payload["goal_reference"],
            observer_ids=payload["observer_ids"],
            clock_id=payload["clock_id"],
            observed_at=payload["observed_at"],
            feature_schema_id=payload["feature_schema_id"],
            observed=payload["observed"],
            missing=payload["missing"],
            unknown=payload["unknown"],
            assumptions=payload["assumptions"],
            falsifiers=payload["falsifiers"],
            evidence_sha256=payload["evidence_sha256"],
            provenance=payload["provenance"],
            uncertainty=payload["uncertainty"],
        )
        expected_snapshot_id = rebuilt["snapshot_id"]
    except (SnapshotValidationError, CanonicalValueError) as exc:
        violations.append(str(exc))

    if snapshot.get("type") != SNAPSHOT_TYPE:
        violations.append("snapshot type is invalid")
    if snapshot.get("version") != SNAPSHOT_VERSION:
        violations.append("snapshot version is invalid")
    if snapshot.get("accepted") is not False:
        violations.append("snapshot must remain non-accepting")
    if snapshot.get("write_authority") != "NONE":
        violations.append("snapshot must have no write authority")
    if expected_snapshot_id is not None and actual_snapshot_id != expected_snapshot_id:
        violations.append("snapshot identity mismatch")

    return {
        "type": VERIFICATION_TYPE,
        "version": VERIFICATION_VERSION,
        "valid": not violations,
        "snapshot_id": actual_snapshot_id,
        "expected_snapshot_id": expected_snapshot_id,
        "violations": violations,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Verification establishes structure and identity only; it does "
            "not establish observation truth or evidence sufficiency."
        ),
    }