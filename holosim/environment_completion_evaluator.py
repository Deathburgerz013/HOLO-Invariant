"""Read-only environmental completion-eligibility evaluation."""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.environment_snapshot import verify_snapshot
from holosim.environment_snapshot_comparator import compare_snapshots


CERTIFICATE_TYPE = "environment_completion_certificate"
CERTIFICATE_VERSION = 1
STATUSES = ("COMPLETE_ELIGIBLE", "INCOMPLETE", "UNCERTAIN")

CONTRACT_FIELDS = (
    "feature_schema_id",
    "distance_metric_id",
    "epsilon",
    "coverage_measure_id",
    "coverage_min",
    "stable_count_min",
    "observation_count_min",
    "sampling_policy_id",
    "required_signal_schema_id",
)

MEASUREMENT_FIELDS = (
    "comparison_distances",
    "observed_coverage",
    "unresolved_required_signals",
    "sampling_window_valid",
    "provenance_check_passed",
    "uncertainty_within_bounds",
)

COMPLETION_CERTIFICATE_FIELDS = (
    "type",
    "version",
    "status",
    "episode_id",
    "environment_id",
    "observer_ids",
    "clock_id",
    "window_start",
    "window_end",
    "observation_count",
    "observation_hashes",
    "comparison_hashes",
    "evidence_snapshot_sha256",
    "contract",
    "measurements",
    "observed_max_distance",
    "observed_stable_count",
    "checks",
    "failed_checks",
    "uncertain_checks",
    "unresolved_required_signals",
    "provenance",
    "evaluation_eligible",
    "correction_evaluated",
    "accepted",
    "write_authority",
    "interpretation_notice",
    "certificate_id",
)


class CompletionEvaluationError(ValueError):
    """Raised when completion eligibility cannot be evaluated structurally."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompletionEvaluationError(f"{field} must be a nonempty string")
    return value.strip()


def _number(value: Any, field: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CompletionEvaluationError(f"{field} must be a finite number")
    normalized = float(value)
    if not isfinite(normalized):
        raise CompletionEvaluationError(f"{field} must be a finite number")
    if normalized < minimum:
        raise CompletionEvaluationError(f"{field} must be >= {minimum}")
    return normalized


def _ratio(value: Any, field: str) -> float:
    normalized = _number(value, field)
    if normalized > 1.0:
        raise CompletionEvaluationError(f"{field} must be <= 1.0")
    return normalized


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CompletionEvaluationError(f"{field} must be an integer >= 1")
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise CompletionEvaluationError(f"{field} must be a boolean")
    return value


def _exact_object(
    value: Any,
    fields: Sequence[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CompletionEvaluationError(f"{label} must be an object")
    missing = sorted(set(fields) - set(value))
    extra = sorted(set(value) - set(fields))
    if missing:
        raise CompletionEvaluationError(
            f"{label} is missing fields: " + ", ".join(missing)
        )
    if extra:
        raise CompletionEvaluationError(
            f"{label} has unsupported fields: " + ", ".join(extra)
        )
    return value


def _text_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise CompletionEvaluationError(f"{field} must be a list")
    normalized = [_required_text(item, field) for item in value]
    if len(set(normalized)) != len(normalized):
        raise CompletionEvaluationError(f"{field} cannot contain duplicates")
    return normalized


def _validate_contract(value: Any) -> dict[str, Any]:
    contract = _exact_object(value, CONTRACT_FIELDS, "contract")
    return {
        "feature_schema_id": _required_text(
            contract["feature_schema_id"], "contract.feature_schema_id"
        ),
        "distance_metric_id": _required_text(
            contract["distance_metric_id"], "contract.distance_metric_id"
        ),
        "epsilon": _number(contract["epsilon"], "contract.epsilon"),
        "coverage_measure_id": _required_text(
            contract["coverage_measure_id"], "contract.coverage_measure_id"
        ),
        "coverage_min": _ratio(
            contract["coverage_min"], "contract.coverage_min"
        ),
        "stable_count_min": _positive_integer(
            contract["stable_count_min"], "contract.stable_count_min"
        ),
        "observation_count_min": _positive_integer(
            contract["observation_count_min"],
            "contract.observation_count_min",
        ),
        "sampling_policy_id": _required_text(
            contract["sampling_policy_id"], "contract.sampling_policy_id"
        ),
        "required_signal_schema_id": _required_text(
            contract["required_signal_schema_id"],
            "contract.required_signal_schema_id",
        ),
    }


def _validate_snapshots(value: Any, contract: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CompletionEvaluationError("snapshots must be an ordered list")
    snapshots = list(value)
    if not snapshots:
        raise CompletionEvaluationError("snapshots cannot be empty")

    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, Mapping):
            raise CompletionEvaluationError(f"snapshots[{index}] must be an object")
        verification = verify_snapshot(snapshot)
        if not verification["valid"]:
            details = "; ".join(verification["violations"])
            raise CompletionEvaluationError(
                f"snapshots[{index}] is invalid: {details}"
            )

    episode_ids = {snapshot["episode_id"] for snapshot in snapshots}
    environment_ids = {snapshot["environment_id"] for snapshot in snapshots}
    clock_ids = {snapshot["clock_id"] for snapshot in snapshots}
    schemas = {snapshot["feature_schema_id"] for snapshot in snapshots}
    snapshot_ids = [snapshot["snapshot_id"] for snapshot in snapshots]
    if len(episode_ids) != 1:
        raise CompletionEvaluationError("snapshots must share one episode_id")
    if len(environment_ids) != 1:
        raise CompletionEvaluationError("snapshots must share one environment_id")
    if len(clock_ids) != 1:
        raise CompletionEvaluationError("snapshots must share one clock_id")
    if schemas != {contract["feature_schema_id"]}:
        raise CompletionEvaluationError(
            "snapshot feature_schema_id must match the contract"
        )
    if len(set(snapshot_ids)) != len(snapshot_ids):
        raise CompletionEvaluationError("snapshot identities cannot repeat")

    for before, after in zip(snapshots, snapshots[1:]):
        try:
            compare_snapshots(before, after)
        except ValueError as exc:
            raise CompletionEvaluationError(
                f"snapshot order is invalid: {exc}"
            ) from exc
    return snapshots


def _validate_comparisons(
    value: Any,
    snapshots: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise CompletionEvaluationError("comparisons must be an ordered list")
    expected = [
        compare_snapshots(before, after)
        for before, after in zip(snapshots, snapshots[1:])
    ]
    if value != expected:
        raise CompletionEvaluationError(
            "comparisons must exactly match recomputed adjacent comparisons"
        )
    return deepcopy(value)


def _validate_measurements(
    value: Any,
    comparisons: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    measurements = _exact_object(value, MEASUREMENT_FIELDS, "measurements")
    distances = measurements["comparison_distances"]
    if not isinstance(distances, Mapping):
        raise CompletionEvaluationError(
            "measurements.comparison_distances must be an object"
        )
    expected_ids = [comparison["comparison_id"] for comparison in comparisons]
    if set(distances) != set(expected_ids):
        raise CompletionEvaluationError(
            "comparison_distances must exactly cover comparison identities"
        )
    normalized_distances = {
        comparison_id: _number(
            distances[comparison_id],
            f"comparison_distances.{comparison_id}",
        )
        for comparison_id in expected_ids
    }
    return {
        "comparison_distances": normalized_distances,
        "observed_coverage": _ratio(
            measurements["observed_coverage"],
            "measurements.observed_coverage",
        ),
        "unresolved_required_signals": _text_list(
            measurements["unresolved_required_signals"],
            "measurements.unresolved_required_signals",
        ),
        "sampling_window_valid": _boolean(
            measurements["sampling_window_valid"],
            "measurements.sampling_window_valid",
        ),
        "provenance_check_passed": _boolean(
            measurements["provenance_check_passed"],
            "measurements.provenance_check_passed",
        ),
        "uncertainty_within_bounds": _boolean(
            measurements["uncertainty_within_bounds"],
            "measurements.uncertainty_within_bounds",
        ),
    }


def _observer_ids(snapshots: Sequence[Mapping[str, Any]]) -> list[str]:
    ordered: list[str] = []
    for snapshot in snapshots:
        for observer_id in snapshot["observer_ids"]:
            if observer_id not in ordered:
                ordered.append(observer_id)
    return ordered


def evaluate_completion(
    *,
    snapshots: Sequence[Mapping[str, Any]],
    comparisons: list[Mapping[str, Any]],
    contract: Mapping[str, Any],
    measurements: Mapping[str, Any],
    evidence_snapshot: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate completion eligibility without acceptance or mutation."""
    normalized_contract = _validate_contract(contract)
    normalized_snapshots = _validate_snapshots(snapshots, normalized_contract)
    normalized_comparisons = _validate_comparisons(
        comparisons, normalized_snapshots
    )
    normalized_measurements = _validate_measurements(
        measurements, normalized_comparisons
    )
    if not isinstance(evidence_snapshot, Mapping) or not evidence_snapshot:
        raise CompletionEvaluationError(
            "evidence_snapshot must be a nonempty object"
        )
    if not isinstance(provenance, Mapping) or not provenance:
        raise CompletionEvaluationError("provenance must be a nonempty object")

    try:
        evidence_snapshot_sha256 = stable_hash(dict(evidence_snapshot))
        stable_hash(dict(provenance))
    except CanonicalValueError as exc:
        raise CompletionEvaluationError(str(exc)) from exc

    distances = list(normalized_measurements["comparison_distances"].values())
    observed_max_distance = max(distances) if distances else None
    observed_stable_count = 0
    for distance in reversed(distances):
        if distance <= normalized_contract["epsilon"]:
            observed_stable_count += 1
        else:
            break

    checks = {
        "window_valid": normalized_measurements["sampling_window_valid"],
        "observation_count": (
            len(normalized_snapshots)
            >= normalized_contract["observation_count_min"]
        ),
        "coverage": (
            normalized_measurements["observed_coverage"]
            >= normalized_contract["coverage_min"]
        ),
        "distance": (
            observed_max_distance is not None
            and observed_max_distance <= normalized_contract["epsilon"]
        ),
        "stable_count": (
            observed_stable_count
            >= normalized_contract["stable_count_min"]
        ),
        "required_signals": not normalized_measurements[
            "unresolved_required_signals"
        ],
        "provenance": normalized_measurements["provenance_check_passed"],
        "uncertainty": normalized_measurements["uncertainty_within_bounds"],
    }
    uncertain_checks = [
        name for name in ("provenance", "uncertainty") if not checks[name]
    ]
    failed_checks = [
        name
        for name in (
            "window_valid",
            "observation_count",
            "coverage",
            "distance",
            "stable_count",
            "required_signals",
        )
        if not checks[name]
    ]
    if uncertain_checks:
        status = "UNCERTAIN"
    elif failed_checks:
        status = "INCOMPLETE"
    else:
        status = "COMPLETE_ELIGIBLE"

    first = normalized_snapshots[0]
    last = normalized_snapshots[-1]
    payload: dict[str, Any] = {
        "type": CERTIFICATE_TYPE,
        "version": CERTIFICATE_VERSION,
        "status": status,
        "episode_id": first["episode_id"],
        "environment_id": first["environment_id"],
        "observer_ids": _observer_ids(normalized_snapshots),
        "clock_id": first["clock_id"],
        "window_start": first["observed_at"],
        "window_end": last["observed_at"],
        "observation_count": len(normalized_snapshots),
        "observation_hashes": [
            snapshot["snapshot_id"] for snapshot in normalized_snapshots
        ],
        "comparison_hashes": [
            comparison["comparison_id"]
            for comparison in normalized_comparisons
        ],
        "evidence_snapshot_sha256": evidence_snapshot_sha256,
        "contract": deepcopy(normalized_contract),
        "measurements": deepcopy(normalized_measurements),
        "observed_max_distance": observed_max_distance,
        "observed_stable_count": observed_stable_count,
        "checks": checks,
        "failed_checks": failed_checks,
        "uncertain_checks": uncertain_checks,
        "unresolved_required_signals": deepcopy(
            normalized_measurements["unresolved_required_signals"]
        ),
        "provenance": deepcopy(dict(provenance)),
        "evaluation_eligible": status == "COMPLETE_ELIGIBLE",
        "correction_evaluated": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Completion eligibility applies only to this declared window, "
            "contract, evidence snapshot, and measurements. It does not "
            "establish truth, correction gain, acceptance, or authority "
            "to mutate state."
        ),
    }
    try:
        certificate_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise CompletionEvaluationError(str(exc)) from exc
    return {**payload, "certificate_id": certificate_id}
