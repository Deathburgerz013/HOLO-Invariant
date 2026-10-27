from copy import deepcopy
from fractions import Fraction

import pytest

from holosim.canonical import stable_hash
from holosim.metric_evidence import build_metric_evidence
from holosim.objective_average import (
    ObjectiveAverageError,
    build_objective_average,
    verify_objective_average,
)


def metric(value, reference):
    return build_metric_evidence(
        value=value,
        counted="duration",
        population="checkpoint recoveries in test fixture",
        source="fixture:checkpoint",
        measurement_method="elapsed seconds from monotonic clock",
        evidence_reference=reference,
    )


def average(values):
    return build_objective_average(
        metrics=[metric(value, f"evidence:{i}") for i, value in enumerate(values)],
        unit="seconds",
    )


def test_exact_mean_and_authority():
    receipt = average([1, 2, 4])
    assert Fraction(receipt["mean_numerator"], receipt["mean_denominator"]) == Fraction(7, 3)
    assert receipt["sample_count"] == 3
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert verify_objective_average(receipt)
    assert receipt == average([1, 2, 4])


def test_binary_float_exactness():
    receipt = average([0.1, 0.2])
    expected = (Fraction.from_float(0.1) + Fraction.from_float(0.2)) / 2
    assert Fraction(receipt["mean_numerator"], receipt["mean_denominator"]) == expected


@pytest.mark.parametrize("values", [[], [True], [float("nan")], [float("inf")]])
def test_invalid_values(values):
    with pytest.raises((ObjectiveAverageError, ValueError)):
        average(values)


def test_duplicate_evidence_rejected():
    item = metric(2, "same")
    with pytest.raises(ObjectiveAverageError, match="duplicate"):
        build_objective_average(metrics=[item, item], unit="seconds")


def test_incompatible_definitions_rejected():
    first = metric(1, "a")
    second = metric(2, "b")
    second = build_metric_evidence(
        value=2, counted="distance", population=second["population"],
        source=second["source"], measurement_method=second["measurement_method"],
        evidence_reference="b",
    )
    with pytest.raises(ObjectiveAverageError, match="incompatible"):
        build_objective_average(metrics=[first, second], unit="seconds")


def test_tampered_result_rejected_even_when_rehashed():
    receipt = average([1, 3])
    changed = deepcopy(receipt)
    changed["mean_numerator"] = 99
    changed["receipt_hash"] = stable_hash({k: v for k, v in changed.items() if k != "receipt_hash"})
    with pytest.raises(ObjectiveAverageError, match="recomputed"):
        verify_objective_average(changed)


def test_rehashed_authority_escalation_rejected():
    changed = average([1])
    changed["write_authority"] = "ALL"
    changed["receipt_hash"] = stable_hash({k: v for k, v in changed.items() if k != "receipt_hash"})
    with pytest.raises(ObjectiveAverageError, match="recomputed"):
        verify_objective_average(changed)


def test_changed_metric_hash_rejected():
    changed = average([1, 3])
    changed["metrics"][0]["value"] = 100
    with pytest.raises(ObjectiveAverageError, match="invalid metric"):
        verify_objective_average(changed)


def test_missing_and_extra_fields_rejected():
    changed = average([1])
    changed["approval"] = True
    with pytest.raises(ObjectiveAverageError, match="schema"):
        verify_objective_average(changed)


def test_bound_rejected():
    with pytest.raises(ObjectiveAverageError, match="bounded"):
        build_objective_average(metrics=[metric(1, str(i)) for i in range(1001)], unit="seconds")
