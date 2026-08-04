"""Deterministic receipts for measured outcome efficiency.

Efficiency binds a verified before-gap metric, after-gap metric, and cost metric.
It reports observed gap reduction per measured cost without claiming that the
measurement is true, accepted, or authorized.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.metric_evidence import (
    MetricEvidenceError,
    validate_metric_evidence,
)


OUTCOME_EFFICIENCY_TYPE = "bounded_outcome_efficiency"
OUTCOME_EFFICIENCY_VERSION = 1


class OutcomeEfficiencyError(ValueError):
    """Raised when outcome efficiency cannot be calculated honestly."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise OutcomeEfficiencyError(str(exc)) from exc


def _validated_metric(
    value: Mapping[str, Any],
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OutcomeEfficiencyError(f"{field} must be a metric evidence object")
    copied = deepcopy(dict(value))
    try:
        validate_metric_evidence(copied)
    except MetricEvidenceError as exc:
        raise OutcomeEfficiencyError(f"{field} is invalid: {exc}") from exc
    return copied


def _finite_number(value: Any, field: str) -> float | int:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise OutcomeEfficiencyError(f"{field} must be a finite number")
    return value


def _require_compatible_gap_metrics(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> None:
    for field in ("counted", "population", "measurement_method"):
        if before[field] != after[field]:
            raise OutcomeEfficiencyError(
                f"before_gap and after_gap {field} must match"
            )


def evaluate_outcome_efficiency(
    *,
    before_gap: Mapping[str, Any],
    after_gap: Mapping[str, Any],
    measured_cost: Mapping[str, Any],
) -> dict[str, Any]:
    """Calculate bounded gap reduction and efficiency from metric receipts."""
    before = _validated_metric(before_gap, "before_gap")
    after = _validated_metric(after_gap, "after_gap")
    cost = _validated_metric(measured_cost, "measured_cost")
    _require_compatible_gap_metrics(before, after)

    before_value = _finite_number(before["value"], "before_gap.value")
    after_value = _finite_number(after["value"], "after_gap.value")
    cost_value = _finite_number(cost["value"], "measured_cost.value")

    if before_value < 0:
        raise OutcomeEfficiencyError("before_gap.value must be non-negative")
    if after_value < 0:
        raise OutcomeEfficiencyError("after_gap.value must be non-negative")
    if cost_value <= 0:
        raise OutcomeEfficiencyError("measured_cost.value must be greater than zero")

    gap_reduction = before_value - after_value
    closure_fraction = (
        None
        if before_value == 0
        else gap_reduction / before_value
    )
    efficiency = gap_reduction / cost_value

    if gap_reduction > 0:
        outcome = "IMPROVED"
    elif gap_reduction < 0:
        outcome = "REGRESSED"
    else:
        outcome = "UNCHANGED"

    body = {
        "type": OUTCOME_EFFICIENCY_TYPE,
        "version": OUTCOME_EFFICIENCY_VERSION,
        "before_metric_hash": before["metric_hash"],
        "after_metric_hash": after["metric_hash"],
        "cost_metric_hash": cost["metric_hash"],
        "gap_definition": {
            "counted": before["counted"],
            "population": before["population"],
            "measurement_method": before["measurement_method"],
        },
        "cost_definition": {
            "counted": cost["counted"],
            "population": cost["population"],
            "measurement_method": cost["measurement_method"],
        },
        "before_gap": before_value,
        "after_gap": after_value,
        "measured_cost": cost_value,
        "gap_reduction": gap_reduction,
        "closure_fraction": closure_fraction,
        "efficiency": efficiency,
        "efficiency_unit": (
            f"{before['counted']} reduced per {cost['counted']}"
        ),
        "outcome": outcome,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "This receipt describes only the supplied bounded measurements. "
            "It does not establish causation, truth, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": _hash(body)}
