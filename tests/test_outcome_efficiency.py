from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.metric_evidence import build_metric_evidence
from holosim.outcome_efficiency import (
    OutcomeEfficiencyError,
    evaluate_outcome_efficiency,
)


def _gap(value: float, *, method: str = "count unresolved checks") -> dict[str, object]:
    return build_metric_evidence(
        value=value,
        counted="unresolved checks",
        population="bounded validation run",
        source="test fixture",
        measurement_method=method,
        evidence_reference=f"gap-{value}",
    )


def _cost(value: float) -> dict[str, object]:
    return build_metric_evidence(
        value=value,
        counted="processor seconds",
        population="bounded validation run",
        source="test fixture",
        measurement_method="monotonic elapsed-time observation",
        evidence_reference=f"cost-{value}",
    )


def test_efficiency_binds_gap_reduction_to_measured_cost() -> None:
    result = evaluate_outcome_efficiency(
        before_gap=_gap(10),
        after_gap=_gap(4),
        measured_cost=_cost(3),
    )

    assert result["gap_reduction"] == 6
    assert result["closure_fraction"] == 0.6
    assert result["efficiency"] == 2
    assert result["efficiency_unit"] == (
        "unresolved checks reduced per processor seconds"
    )
    assert result["outcome"] == "IMPROVED"
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert len(result["receipt_hash"]) == 64


def test_unchanged_gap_reports_zero_efficiency() -> None:
    result = evaluate_outcome_efficiency(
        before_gap=_gap(5),
        after_gap=_gap(5),
        measured_cost=_cost(2),
    )

    assert result["gap_reduction"] == 0
    assert result["closure_fraction"] == 0
    assert result["efficiency"] == 0
    assert result["outcome"] == "UNCHANGED"


def test_regression_preserves_negative_efficiency() -> None:
    result = evaluate_outcome_efficiency(
        before_gap=_gap(4),
        after_gap=_gap(7),
        measured_cost=_cost(3),
    )

    assert result["gap_reduction"] == -3
    assert result["closure_fraction"] == -0.75
    assert result["efficiency"] == -1
    assert result["outcome"] == "REGRESSED"


def test_zero_initial_gap_has_explicitly_undefined_closure_fraction() -> None:
    result = evaluate_outcome_efficiency(
        before_gap=_gap(0),
        after_gap=_gap(1),
        measured_cost=_cost(1),
    )

    assert result["closure_fraction"] is None
    assert result["efficiency"] == -1
    assert result["outcome"] == "REGRESSED"


@pytest.mark.parametrize("value", [0, -1])
def test_nonpositive_cost_is_rejected(value: float) -> None:
    with pytest.raises(
        OutcomeEfficiencyError,
        match="measured_cost.value must be greater than zero",
    ):
        evaluate_outcome_efficiency(
            before_gap=_gap(5),
            after_gap=_gap(2),
            measured_cost=_cost(value),
        )


def test_negative_gap_is_rejected() -> None:
    with pytest.raises(
        OutcomeEfficiencyError,
        match="after_gap.value must be non-negative",
    ):
        evaluate_outcome_efficiency(
            before_gap=_gap(5),
            after_gap=_gap(-1),
            measured_cost=_cost(1),
        )


def test_incompatible_gap_measurements_are_rejected() -> None:
    with pytest.raises(
        OutcomeEfficiencyError,
        match="before_gap and after_gap measurement_method must match",
    ):
        evaluate_outcome_efficiency(
            before_gap=_gap(5),
            after_gap=_gap(2, method="estimate unresolved checks"),
            measured_cost=_cost(1),
        )


def test_tampered_metric_receipt_is_rejected() -> None:
    after = _gap(2)
    after["value"] = 1

    with pytest.raises(
        OutcomeEfficiencyError,
        match="after_gap is invalid: metric hash mismatch",
    ):
        evaluate_outcome_efficiency(
            before_gap=_gap(5),
            after_gap=after,
            measured_cost=_cost(1),
        )


def test_inputs_are_not_mutated_and_receipt_is_deterministic() -> None:
    before = _gap(10)
    after = _gap(4)
    cost = _cost(3)
    originals = deepcopy((before, after, cost))

    first = evaluate_outcome_efficiency(
        before_gap=before,
        after_gap=after,
        measured_cost=cost,
    )
    second = evaluate_outcome_efficiency(
        before_gap=before,
        after_gap=after,
        measured_cost=cost,
    )

    assert (before, after, cost) == originals
    assert first == second
