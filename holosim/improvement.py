"""Version-bound comparison of validated performance observations."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from holosim.performance import (
    PerformanceObservationError,
    validate_performance_receipt,
)


IMPROVEMENT_COMPARISON_TYPE = "holo_performance_improvement_comparison"
IMPROVEMENT_COMPARISON_VERSION = 1

_METRIC_FIELDS = (
    "median_setup_ns",
    "median_append_ns",
    "median_health_ns",
    "median_cleanup_ns",
)

_ENVIRONMENT_FIELDS = (
    "python_implementation",
    "python_version",
    "operating_system",
    "operating_system_release",
    "machine",
    "clock",
)


class ImprovementComparisonError(ValueError):
    """Raised when performance receipts cannot be compared honestly."""


def _canonical_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise ImprovementComparisonError(
            "comparison could not be canonicalized"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def _validate_receipt(
    receipt: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    try:
        validate_performance_receipt(receipt)
    except PerformanceObservationError as exc:
        raise ImprovementComparisonError(
            f"{label} performance receipt is invalid"
        ) from exc

    return dict(receipt)


def _require_comparable(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> None:
    for field in _ENVIRONMENT_FIELDS:
        if baseline["environment"][field] != candidate["environment"][field]:
            raise ImprovementComparisonError(
                f"environment mismatch: {field}"
            )

    for field in ("entry_counts", "repeats", "payload_sha256"):
        if baseline[field] != candidate[field]:
            raise ImprovementComparisonError(
                f"workload mismatch: {field}"
            )


def compare_performance_receipts(
    baseline_receipt: Mapping[str, Any],
    candidate_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Compare two validated performance observations.

    A comparison is allowed only when execution environment and workload
    identity match. The HoloSim versions may differ because version change is
    the subject of the comparison.

    Lower elapsed time is reported as an observed improvement. No acceptance,
    defect, causation, or write authority is inferred.
    """
    baseline = _validate_receipt(baseline_receipt, "baseline")
    candidate = _validate_receipt(candidate_receipt, "candidate")
    _require_comparable(baseline, candidate)

    comparisons: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []

    for baseline_measurement, candidate_measurement in zip(
        baseline["measurements"],
        candidate["measurements"],
    ):
        entry_count = baseline_measurement["entry_count"]

        for metric in _METRIC_FIELDS:
            baseline_ns = baseline_measurement[metric]
            candidate_ns = candidate_measurement[metric]
            delta_ns = candidate_ns - baseline_ns

            if delta_ns < 0:
                classification = "improvement"
            elif delta_ns > 0:
                classification = "regression"
            else:
                classification = "unchanged"

            observation = {
                "entry_count": entry_count,
                "metric": metric,
                "baseline_ns": baseline_ns,
                "candidate_ns": candidate_ns,
                "delta_ns": delta_ns,
                "classification": classification,
            }
            comparisons.append(observation)

            if classification == "improvement":
                improvements.append(observation)
            elif classification == "regression":
                regressions.append(observation)
            else:
                unchanged.append(observation)

    body = {
        "type": IMPROVEMENT_COMPARISON_TYPE,
        "version": IMPROVEMENT_COMPARISON_VERSION,
        "baseline": {
            "receipt_hash": baseline["receipt_hash"],
            "holosim_version": baseline["environment"]["holosim_version"],
        },
        "candidate": {
            "receipt_hash": candidate["receipt_hash"],
            "holosim_version": candidate["environment"]["holosim_version"],
        },
        "comparable": True,
        "comparisons": comparisons,
        "improvements": improvements,
        "regressions": regressions,
        "unchanged": unchanged,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Classifications describe elapsed-time differences between two "
            "comparable bounded observations only. They do not establish "
            "causation, acceptance, a defect, or authority."
        ),
    }

    return {
        **body,
        "comparison_hash": _canonical_hash(body),
    }