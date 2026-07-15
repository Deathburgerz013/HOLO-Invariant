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

COMPRESSION_STOP_TYPE = "compression_stop_finding"
COMPRESSION_STOP_VERSION = 1

COLLECTION_COMPLETE = "COLLECTION_COMPLETE"
COMPRESSION_FIXED_POINT = "COMPRESSION_FIXED_POINT"
COMPRESSION_BUDGET_EXHAUSTED = "COMPRESSION_BUDGET_EXHAUSTED"
COMPRESSION_BLOCKED_BY_REQUIRED_DISTINCTION = (
    "COMPRESSION_BLOCKED_BY_REQUIRED_DISTINCTION"
)
RECONSTRUCTION_FAILED = "RECONSTRUCTION_FAILED"
TEMPORARY_PAUSE = "TEMPORARY_PAUSE"
FALSE_CONVERGENCE = "FALSE_CONVERGENCE"
REOPENED = "REOPENED"
NO_STOP_FINDING = "NO_STOP_FINDING"

COMPRESSION_PHASE_FINDINGS = (
    COMPRESSION_FIXED_POINT,
    COMPRESSION_BUDGET_EXHAUSTED,
    COMPRESSION_BLOCKED_BY_REQUIRED_DISTINCTION,
    RECONSTRUCTION_FAILED,
    TEMPORARY_PAUSE,
    FALSE_CONVERGENCE,
    REOPENED,
    NO_STOP_FINDING,
)

TERMINAL_COMPRESSION_FINDINGS = (
    COMPRESSION_FIXED_POINT,
    COMPRESSION_BUDGET_EXHAUSTED,
    COMPRESSION_BLOCKED_BY_REQUIRED_DISTINCTION,
    RECONSTRUCTION_FAILED,
)

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


class CompressionStopValidationError(ValueError):
    """Raised when compression-stop evidence violates its contract."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotValidationError(f"{field} must be a nonempty string")
    return value.strip()


def _compression_required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompressionStopValidationError(
            f"{field} must be a nonempty string"
        )
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


def _compression_text_list(
    values: Sequence[str],
    field: str,
    *,
    allow_empty: bool,
) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise CompressionStopValidationError(
            f"{field} must be a list of strings"
        )

    normalized = [
        _compression_required_text(value, field)
        for value in values
    ]
    if not allow_empty and not normalized:
        raise CompressionStopValidationError(f"{field} cannot be empty")
    if len(set(normalized)) != len(normalized):
        raise CompressionStopValidationError(
            f"{field} cannot contain duplicates"
        )
    return sorted(normalized)


def _required_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise CompressionStopValidationError(f"{field} must be a boolean")
    return value


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


def _compression_json_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise CompressionStopValidationError(f"{field} must be a list")
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


def _normalize_lower_cost_candidates(
    candidates: Sequence[Mapping[str, Any]],
    evaluated_operator_ids: Sequence[str],
) -> list[dict[str, Any]]:
    if isinstance(candidates, (str, bytes)) or not isinstance(
        candidates,
        Sequence,
    ):
        raise CompressionStopValidationError(
            "lower_cost_candidates must be a list"
        )

    evaluated = set(evaluated_operator_ids)
    normalized: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()

    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise CompressionStopValidationError(
                f"lower_cost_candidates[{index}] must be an object"
            )

        required_fields = {
            "candidate_id",
            "operator_id",
            "contract_satisfied",
            "lost_required_distinctions",
        }
        missing_fields = sorted(required_fields - set(candidate))
        unexpected_fields = sorted(set(candidate) - required_fields)

        if missing_fields:
            raise CompressionStopValidationError(
                "lower-cost candidate is missing fields: "
                + ", ".join(missing_fields)
            )
        if unexpected_fields:
            raise CompressionStopValidationError(
                "lower-cost candidate has unexpected fields: "
                + ", ".join(unexpected_fields)
            )

        candidate_id = _compression_required_text(
            candidate["candidate_id"],
            "candidate_id",
        )
        operator_id = _compression_required_text(
            candidate["operator_id"],
            "operator_id",
        )
        contract_satisfied = _required_bool(
            candidate["contract_satisfied"],
            "contract_satisfied",
        )
        lost_distinctions = _compression_text_list(
            candidate["lost_required_distinctions"],
            "lost_required_distinctions",
            allow_empty=True,
        )

        if candidate_id in candidate_ids:
            raise CompressionStopValidationError(
                "candidate_id cannot contain duplicates"
            )
        candidate_ids.add(candidate_id)

        if operator_id not in evaluated:
            raise CompressionStopValidationError(
                "lower-cost candidate operator_id must be evaluated"
            )

        if contract_satisfied and lost_distinctions:
            raise CompressionStopValidationError(
                "a contract-satisfied candidate cannot lose a required "
                "distinction"
            )

        normalized.append(
            {
                "candidate_id": candidate_id,
                "operator_id": operator_id,
                "contract_satisfied": contract_satisfied,
                "lost_required_distinctions": lost_distinctions,
            }
        )

    return sorted(normalized, key=lambda item: item["candidate_id"])


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
    if (
        expected_snapshot_id is not None
        and actual_snapshot_id != expected_snapshot_id
    ):
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


def evaluate_compression_stop(
    *,
    reconstruction_contract_satisfied: bool,
    required_operator_ids: Sequence[str],
    evaluated_operator_ids: Sequence[str],
    lower_cost_candidates: Sequence[Mapping[str, Any]],
    audit_budget_exhausted: bool,
    reported_finding: str | None = None,
    false_convergence_reasons: Sequence[str] = (),
    pause_reasons: Sequence[str] = (),
    reopen_reasons: Sequence[str] = (),
    uncertainty: list[Any],
) -> dict[str, Any]:
    """Derive one scoped, non-authoritative compression-stop finding."""
    contract_satisfied = _required_bool(
        reconstruction_contract_satisfied,
        "reconstruction_contract_satisfied",
    )
    budget_exhausted = _required_bool(
        audit_budget_exhausted,
        "audit_budget_exhausted",
    )
    required_operators = _compression_text_list(
        required_operator_ids,
        "required_operator_ids",
        allow_empty=False,
    )
    evaluated_operators = _compression_text_list(
        evaluated_operator_ids,
        "evaluated_operator_ids",
        allow_empty=True,
    )

    unexpected_operators = sorted(
        set(evaluated_operators) - set(required_operators)
    )
    if unexpected_operators:
        raise CompressionStopValidationError(
            "evaluated_operator_ids contains undeclared operators: "
            + ", ".join(unexpected_operators)
        )

    candidates = _normalize_lower_cost_candidates(
        lower_cost_candidates,
        evaluated_operators,
    )
    false_reasons = _compression_text_list(
        false_convergence_reasons,
        "false_convergence_reasons",
        allow_empty=True,
    )
    pauses = _compression_text_list(
        pause_reasons,
        "pause_reasons",
        allow_empty=True,
    )
    reopenings = _compression_text_list(
        reopen_reasons,
        "reopen_reasons",
        allow_empty=True,
    )
    preserved_uncertainty = _compression_json_list(
        uncertainty,
        "uncertainty",
    )

    if reported_finding is not None:
        reported_finding = _compression_required_text(
            reported_finding,
            "reported_finding",
        )
        if reported_finding not in COMPRESSION_PHASE_FINDINGS:
            raise CompressionStopValidationError(
                "reported_finding is not a compression-phase finding"
            )

    missing_operators = sorted(
        set(required_operators) - set(evaluated_operators)
    )
    safe_candidate_ids = [
        candidate["candidate_id"]
        for candidate in candidates
        if candidate["contract_satisfied"]
    ]
    blocked_candidate_ids = [
        candidate["candidate_id"]
        for candidate in candidates
        if candidate["lost_required_distinctions"]
    ]
    all_candidates_blocked = bool(candidates) and all(
        candidate["lost_required_distinctions"]
        for candidate in candidates
    )

    invalid_fixed_point_report = (
        reported_finding == COMPRESSION_FIXED_POINT
        and (
            not contract_satisfied
            or bool(missing_operators)
            or bool(safe_candidate_ids)
        )
    )

    decision_reasons: list[str]

    if reopenings:
        finding = REOPENED
        decision_reasons = [
            "New evidence, requirements, or explicit direction reopened "
            "the prior boundary."
        ]
    elif pauses:
        finding = TEMPORARY_PAUSE
        decision_reasons = [
            "An external reason paused evaluation without a terminal "
            "compression finding."
        ]
    elif not contract_satisfied:
        finding = RECONSTRUCTION_FAILED
        decision_reasons = [
            "The current frame does not satisfy the reconstruction "
            "contract."
        ]
    elif false_reasons or invalid_fixed_point_report:
        finding = FALSE_CONVERGENCE
        decision_reasons = [
            "A convergence claim is unsupported by the declared evidence."
        ]
        if invalid_fixed_point_report:
            false_reasons = sorted(
                set(
                    false_reasons
                    + [
                        "reported fixed point fails its decision "
                        "conditions"
                    ]
                )
            )
    elif missing_operators and budget_exhausted:
        finding = COMPRESSION_BUDGET_EXHAUSTED
        decision_reasons = [
            "The audit budget ended before every required operator was "
            "evaluated."
        ]
    elif missing_operators:
        finding = NO_STOP_FINDING
        decision_reasons = [
            "Required operators remain unevaluated and the audit budget "
            "has not ended."
        ]
    elif safe_candidate_ids:
        finding = NO_STOP_FINDING
        decision_reasons = [
            "At least one lower-cost candidate still satisfies the "
            "reconstruction contract."
        ]
    elif all_candidates_blocked:
        finding = COMPRESSION_BLOCKED_BY_REQUIRED_DISTINCTION
        decision_reasons = [
            "Every lower-cost candidate loses at least one distinction "
            "required by the reconstruction contract."
        ]
    else:
        finding = COMPRESSION_FIXED_POINT
        decision_reasons = [
            "Every required operator was evaluated and no lower-cost "
            "contract-satisfying candidate remains."
        ]

    terminal = finding in TERMINAL_COMPRESSION_FINDINGS
    reported_matches = (
        None
        if reported_finding is None
        else reported_finding == finding
    )

    payload: dict[str, Any] = {
        "type": COMPRESSION_STOP_TYPE,
        "version": COMPRESSION_STOP_VERSION,
        "finding": finding,
        "terminal": terminal,
        "reconstruction_contract_satisfied": contract_satisfied,
        "required_operator_ids": required_operators,
        "evaluated_operator_ids": evaluated_operators,
        "missing_operator_ids": missing_operators,
        "lower_cost_candidates": candidates,
        "contract_preserving_lower_cost_candidate_ids": safe_candidate_ids,
        "required_distinction_blocked_candidate_ids": blocked_candidate_ids,
        "audit_budget_exhausted": budget_exhausted,
        "reported_finding": reported_finding,
        "reported_finding_matches": reported_matches,
        "false_convergence_reasons": false_reasons,
        "pause_reasons": pauses,
        "reopen_reasons": reopenings,
        "decision_reasons": decision_reasons,
        "uncertainty": preserved_uncertainty,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This finding is scoped to caller-supplied structured evidence. "
            "It does not establish global optimality, losslessness, truth, "
            "acceptance, or authority to modify state."
        ),
    }

    try:
        finding_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise CompressionStopValidationError(str(exc)) from exc

    return {**payload, "finding_id": finding_id}