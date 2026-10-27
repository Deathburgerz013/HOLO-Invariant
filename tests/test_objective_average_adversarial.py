"""Adversarial checks for Objective Average receipt verification."""

from copy import deepcopy
from fractions import Fraction

import pytest

from holosim.canonical import stable_hash
from holosim.metric_evidence import MetricEvidenceError, build_metric_evidence
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


def rehash(receipt):
    receipt["receipt_hash"] = stable_hash({
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    })


@pytest.mark.parametrize(
    "field,value",
    [
        ("sample_count", 999),
        ("metric_hashes", ["forged"]),
        ("method", "arbitrary_mean"),
        ("counted", "distance"),
        ("population", "different population"),
        ("measurement_method", "different method"),
        ("mean_numerator", 999),
        ("mean_denominator", 0),
        ("mean_denominator", -1),
    ],
)
def test_rehashed_forgery_rejected(field, value):
    receipt = average([1, 3])
    receipt[field] = value
    rehash(receipt)

    with pytest.raises(ObjectiveAverageError):
        verify_objective_average(receipt)


def test_oversized_integer_rejected():
    with pytest.raises(MetricEvidenceError, match="bound"):
        average([1 << 4097])


def test_oversized_unit_rejected():
    with pytest.raises(ObjectiveAverageError, match="bound"):
        build_objective_average(
            metrics=[metric(1, "evidence:1")],
            unit="x" * 1025,
        )


def test_input_mutation_does_not_change_receipt():
    evidence = [metric(1, "a"), metric(3, "b")]
    receipt = build_objective_average(metrics=evidence, unit="seconds")
    original = deepcopy(receipt)

    evidence[0]["value"] = 999

    assert receipt == original
    assert verify_objective_average(receipt)


def test_reordering_is_explicitly_hash_significant():
    first = average([1, 3])
    second = average([3, 1])

    assert Fraction(
        first["mean_numerator"], first["mean_denominator"]
    ) == Fraction(
        second["mean_numerator"], second["mean_denominator"]
    )

    assert first["receipt_hash"] != second["receipt_hash"]
    assert verify_objective_average(first)
    assert verify_objective_average(second)


def test_rehashed_unit_change_is_currently_accepted():
    """Document the existing caller-declared unit trust boundary."""
    receipt = average([1, 3])
    receipt["unit"] = "meters"
    rehash(receipt)

    assert verify_objective_average(receipt)
