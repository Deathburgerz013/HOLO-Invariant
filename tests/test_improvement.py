"""Tests for version-bound performance improvement comparison."""

from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.improvement import (
    ImprovementComparisonError,
    compare_performance_receipts,
)
from holosim.performance import (
    _digest,
    _scaling_steps,
    observe_chain_performance,
)


def _receipt(
    *,
    entry_counts: list[int] | None = None,
    repeats: int = 1,
    payload: str = "improvement-test",
) -> dict:
    return observe_chain_performance(
        entry_counts or [1, 2],
        repeats=repeats,
        payload=payload,
    )


def _rebuild_receipt(receipt: dict) -> dict:
    """Rebuild fields derived from measurements after controlled test edits."""
    receipt["scaling_steps"] = _scaling_steps(receipt["measurements"])

    body = dict(receipt)
    body.pop("receipt_hash")
    receipt["receipt_hash"] = _digest(body)

    return receipt


def test_reports_improvement_regression_and_unchanged() -> None:
    baseline = _receipt()
    candidate = deepcopy(baseline)

    candidate_measurement = candidate["measurements"][0]

    candidate_measurement["samples"][0]["append_ns"] -= 1
    candidate_measurement["median_append_ns"] -= 1

    candidate_measurement["samples"][0]["health_ns"] += 1
    candidate_measurement["median_health_ns"] += 1

    candidate["environment"]["holosim_version"] = "candidate-version"
    _rebuild_receipt(candidate)

    result = compare_performance_receipts(baseline, candidate)

    assert result["comparable"] is True
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"

    assert any(
        item["metric"] == "median_append_ns"
        and item["classification"] == "improvement"
        and item["delta_ns"] == -1
        for item in result["comparisons"]
    )
    assert any(
        item["metric"] == "median_health_ns"
        and item["classification"] == "regression"
        and item["delta_ns"] == 1
        for item in result["comparisons"]
    )
    assert any(
        item["classification"] == "unchanged"
        for item in result["comparisons"]
    )

    assert result["improvements"]
    assert result["regressions"]
    assert result["unchanged"]
    assert len(result["comparison_hash"]) == 64


def test_rejects_environment_mismatch() -> None:
    baseline = _receipt()
    candidate = deepcopy(baseline)

    candidate["environment"]["machine"] = "different-machine"
    _rebuild_receipt(candidate)

    with pytest.raises(
        ImprovementComparisonError,
        match="environment mismatch: machine",
    ):
        compare_performance_receipts(baseline, candidate)


@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param(
            _receipt(entry_counts=[1]),
            id="entry-counts",
        ),
        pytest.param(
            _receipt(repeats=2),
            id="repeats",
        ),
        pytest.param(
            _receipt(payload="different-payload"),
            id="payload",
        ),
    ],
)
def test_rejects_workload_mismatch(candidate: dict) -> None:
    baseline = _receipt()

    with pytest.raises(
        ImprovementComparisonError,
        match="workload mismatch",
    ):
        compare_performance_receipts(baseline, candidate)


def test_rejects_invalid_baseline_receipt() -> None:
    baseline = _receipt()
    candidate = deepcopy(baseline)

    baseline["receipt_hash"] = "0" * 64

    with pytest.raises(
        ImprovementComparisonError,
        match="baseline performance receipt is invalid",
    ):
        compare_performance_receipts(baseline, candidate)


def test_rejects_invalid_candidate_receipt() -> None:
    baseline = _receipt()
    candidate = deepcopy(baseline)

    candidate["receipt_hash"] = "0" * 64

    with pytest.raises(
        ImprovementComparisonError,
        match="candidate performance receipt is invalid",
    ):
        compare_performance_receipts(baseline, candidate)


def test_comparison_is_deterministic_for_identical_receipts() -> None:
    baseline = _receipt()
    candidate = deepcopy(baseline)

    first = compare_performance_receipts(baseline, candidate)
    second = compare_performance_receipts(baseline, candidate)

    assert first == second
    assert not first["improvements"]
    assert not first["regressions"]
    assert first["unchanged"]