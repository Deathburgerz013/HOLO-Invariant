"""Bind outcome-efficiency calculations to authenticated metric observations.

Each signed occurrence carries one validated metric receipt, an evaluation
identity, and one required role. Authentication establishes origin and
integrity only; the resulting efficiency remains a bounded observation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.metric_evidence import (
    MetricEvidenceError,
    validate_metric_evidence,
)
from holosim.outcome_efficiency import (
    OutcomeEfficiencyError,
    evaluate_outcome_efficiency,
)
from holosim.signed_occurrence import (
    SignedOccurrenceError,
    verify_signed_occurrence,
)


SIGNED_EFFICIENCY_TYPE = "bounded_signed_efficiency_evidence"
SIGNED_EFFICIENCY_VERSION = 1
REQUIRED_ROLES = ("BEFORE_GAP", "AFTER_GAP", "MEASURED_COST")
PAYLOAD_FIELDS = {"evaluation_id", "role", "metric"}


class SignedEfficiencyEvidenceError(ValueError):
    """Raised when signed efficiency evidence cannot be bound honestly."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise SignedEfficiencyEvidenceError(str(exc)) from exc


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SignedEfficiencyEvidenceError(
            f"{field} must be a non-empty string"
        )
    return value


def _occurrence_sequence(value: Any) -> list[Mapping[str, Any]]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or not value
    ):
        raise SignedEfficiencyEvidenceError(
            "occurrences must be a non-empty sequence"
        )
    result: list[Mapping[str, Any]] = []
    for index, occurrence in enumerate(value):
        if not isinstance(occurrence, Mapping):
            raise SignedEfficiencyEvidenceError(
                f"occurrences[{index}] must be an object"
            )
        result.append(occurrence)
    return result


def _validated_payload(
    occurrence: Mapping[str, Any],
    *,
    expected_evaluation_id: str,
    index: int,
) -> tuple[str, dict[str, Any]]:
    payload = occurrence.get("payload")
    if not isinstance(payload, Mapping) or set(payload) != PAYLOAD_FIELDS:
        raise SignedEfficiencyEvidenceError(
            f"occurrences[{index}].payload fields are invalid"
        )

    evaluation_id = _required_text(
        payload["evaluation_id"],
        f"occurrences[{index}].payload.evaluation_id",
    )
    if evaluation_id != expected_evaluation_id:
        raise SignedEfficiencyEvidenceError(
            f"occurrences[{index}] is bound to a different evaluation"
        )

    role = _required_text(
        payload["role"],
        f"occurrences[{index}].payload.role",
    )
    if role not in REQUIRED_ROLES:
        raise SignedEfficiencyEvidenceError(
            f"occurrences[{index}].payload.role is invalid"
        )

    metric = payload["metric"]
    if not isinstance(metric, Mapping):
        raise SignedEfficiencyEvidenceError(
            f"occurrences[{index}].payload.metric must be an object"
        )
    copied = deepcopy(dict(metric))
    try:
        validate_metric_evidence(copied)
    except MetricEvidenceError as exc:
        raise SignedEfficiencyEvidenceError(
            f"occurrences[{index}].payload.metric is invalid: {exc}"
        ) from exc
    return role, copied


def evaluate_signed_outcome_efficiency(
    *,
    evaluation_id: str,
    occurrences: Sequence[Mapping[str, Any]],
    source_secrets: Mapping[str, bytes],
) -> dict[str, Any]:
    """Verify three metric observations and derive outcome efficiency."""
    identity = _required_text(evaluation_id, "evaluation_id")
    occurrence_items = _occurrence_sequence(occurrences)
    if not isinstance(source_secrets, Mapping):
        raise SignedEfficiencyEvidenceError(
            "source_secrets must be a mapping"
        )

    seen_occurrence_ids: set[str] = set()
    by_role: dict[str, dict[str, Any]] = {}

    for index, occurrence in enumerate(occurrence_items):
        try:
            verification = verify_signed_occurrence(
                occurrence=occurrence,
                source_secrets=source_secrets,
                seen_occurrence_ids=seen_occurrence_ids,
            )
        except SignedOccurrenceError as exc:
            raise SignedEfficiencyEvidenceError(
                f"occurrences[{index}] is invalid: {exc}"
            ) from exc

        if not verification["verified"]:
            raise SignedEfficiencyEvidenceError(
                f"occurrences[{index}] was not verified: "
                f"{verification['status']}"
            )

        role, metric = _validated_payload(
            occurrence,
            expected_evaluation_id=identity,
            index=index,
        )
        if role in by_role:
            raise SignedEfficiencyEvidenceError(
                f"duplicate signed efficiency role: {role}"
            )

        by_role[role] = {
            "metric": metric,
            "source_id": verification["source_id"],
            "occurrence_hash": verification["occurrence_sha256"],
            "verification_hash": verification["verification_hash"],
        }
        seen_occurrence_ids.add(occurrence["occurrence_id"])

    missing_roles = [
        role for role in REQUIRED_ROLES if role not in by_role
    ]
    if missing_roles:
        raise SignedEfficiencyEvidenceError(
            "missing signed efficiency roles: " + ", ".join(missing_roles)
        )

    try:
        efficiency = evaluate_outcome_efficiency(
            before_gap=by_role["BEFORE_GAP"]["metric"],
            after_gap=by_role["AFTER_GAP"]["metric"],
            measured_cost=by_role["MEASURED_COST"]["metric"],
        )
    except OutcomeEfficiencyError as exc:
        raise SignedEfficiencyEvidenceError(
            f"signed efficiency metrics are incompatible: {exc}"
        ) from exc

    observations = {
        role: {
            "source_id": by_role[role]["source_id"],
            "occurrence_hash": by_role[role]["occurrence_hash"],
            "verification_hash": by_role[role]["verification_hash"],
            "metric_hash": by_role[role]["metric"]["metric_hash"],
        }
        for role in REQUIRED_ROLES
    }
    body = {
        "type": SIGNED_EFFICIENCY_TYPE,
        "version": SIGNED_EFFICIENCY_VERSION,
        "evaluation_id": identity,
        "observations": observations,
        "efficiency": efficiency,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Signatures establish observation origin and integrity only. "
            "The efficiency result does not establish causation, truth, "
            "acceptance, or authority."
        ),
    }
    return {**body, "binding_hash": _hash(body)}
