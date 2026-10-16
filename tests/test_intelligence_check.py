from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.intelligence_check import evaluate_intelligence_check


def _criteria():
    return [
        {"id": "addition", "expected": 7},
        {"id": "comparison", "expected": True},
    ]


@pytest.mark.parametrize(
    ("before", "after", "expected_result"),
    [
        ({"addition": 8, "comparison": False},
         {"addition": 7, "comparison": True}, "IMPROVED"),
        ({"addition": 7, "comparison": True},
         {"addition": 8, "comparison": False}, "REGRESSED"),
        ({"addition": 8, "comparison": True},
         {"addition": 9, "comparison": True}, "UNCHANGED"),
    ],
)
def test_measured_performance_change(before, after, expected_result):
    receipt = evaluate_intelligence_check(
        task_id="fixture:arithmetic-v1",
        criteria=_criteria(),
        before=before,
        after=after,
    )

    assert receipt["result"] == expected_result
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert len(receipt["receipt_hash"]) == 64


def test_missing_observation_is_not_counted_as_failure_or_success():
    receipt = evaluate_intelligence_check(
        task_id="fixture:arithmetic-v1",
        criteria=_criteria(),
        before={"addition": 8, "comparison": False},
        after={"addition": 7},
    )

    assert receipt["result"] == "UNAVAILABLE"


def test_duplicate_criterion_ids_are_rejected():
    with pytest.raises(ValueError):
        evaluate_intelligence_check(
            task_id="fixture:arithmetic-v1",
            criteria=[
                {"id": "same", "expected": 1},
                {"id": "same", "expected": 2},
            ],
            before={"same": 1},
            after={"same": 2},
        )


def test_unexpected_observations_are_rejected():
    with pytest.raises(ValueError):
        evaluate_intelligence_check(
            task_id="fixture:arithmetic-v1",
            criteria=_criteria(),
            before={"addition": 7, "comparison": True, "extra": 99},
            after={"addition": 7, "comparison": True},
        )


def test_nested_boolean_cannot_satisfy_integer_expectation():
    receipt = evaluate_intelligence_check(
        task_id="adversarial:nested-type",
        criteria=[{"id": "answer", "expected": {"value": 1}}],
        before={"answer": {"value": True}},
        after={"answer": {"value": 1}},
    )

    assert receipt["before_score"] == 0
    assert receipt["after_score"] == 1
    assert receipt["result"] == "IMPROVED"


@pytest.mark.parametrize("invalid", [float("nan"), {1}, (1, 2)])
def test_noncanonical_expected_values_are_rejected(invalid):
    with pytest.raises(ValueError):
        evaluate_intelligence_check(
            task_id="adversarial:invalid",
            criteria=[{"id": "answer", "expected": invalid}],
            before={"answer": 0},
            after={"answer": 1},
        )


def test_rejects_excessive_criteria():
    criteria = [
        {"id": f"criterion-{i}", "expected": i}
        for i in range(1001)
    ]
    with pytest.raises(ValueError):
        evaluate_intelligence_check(
            task_id="adversarial:too-many-criteria",
            criteria=criteria,
            before={},
            after={},
        )


def test_rejects_oversized_evidence():
    with pytest.raises(ValueError):
        evaluate_intelligence_check(
            task_id="adversarial:oversized",
            criteria=[{"id": "answer", "expected": "x" * 70000}],
            before={"answer": "wrong"},
            after={"answer": "x" * 70000},
        )


def test_receipt_verifier_rejects_rehashed_false_outcome():
    from holosim.intelligence_check import verify_intelligence_check_receipt

    receipt = evaluate_intelligence_check(
        task_id="replay:forged-outcome",
        criteria=[{"id": "answer", "expected": 42}],
        before={"answer": 0},
        after={"answer": 42},
    )

    assert verify_intelligence_check_receipt(receipt) is True

    forged = deepcopy(receipt)
    forged["result"] = "REGRESSED"
    body = {key: value for key, value in forged.items() if key != "receipt_hash"}
    forged["receipt_hash"] = stable_hash(body)

    assert verify_intelligence_check_receipt(forged) is False


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("before_score", 999),
        ("after_score", -1),
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
    ],
)
def test_receipt_verifier_rejects_rehashed_tampering(field, replacement):
    from holosim.intelligence_check import verify_intelligence_check_receipt

    receipt = evaluate_intelligence_check(
        task_id="replay:tampering",
        criteria=[{"id": "answer", "expected": 42}],
        before={"answer": 0},
        after={"answer": 42},
    )

    forged = deepcopy(receipt)
    forged[field] = replacement
    body = {key: value for key, value in forged.items() if key != "receipt_hash"}
    forged["receipt_hash"] = stable_hash(body)

    assert verify_intelligence_check_receipt(forged) is False


def test_receipt_verifier_rejects_missing_field():
    from holosim.intelligence_check import verify_intelligence_check_receipt

    receipt = evaluate_intelligence_check(
        task_id="replay:missing-field",
        criteria=[{"id": "answer", "expected": 42}],
        before={"answer": 0},
        after={"answer": 42},
    )

    del receipt["after_score"]

    assert verify_intelligence_check_receipt(receipt) is False


def test_evaluation_is_deterministic_and_does_not_mutate_inputs():
    criteria = [{"id": "nested", "expected": {"value": 42}}]
    before = {"nested": {"value": 0}}
    after = {"nested": {"value": 42}}

    original = deepcopy((criteria, before, after))

    first = evaluate_intelligence_check(
        task_id="deterministic:nested",
        criteria=criteria,
        before=before,
        after=after,
    )
    second = evaluate_intelligence_check(
        task_id="deterministic:nested",
        criteria=criteria,
        before=before,
        after=after,
    )

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]
    assert (criteria, before, after) == original

    first["criteria"][0]["expected"]["value"] = 999
    first["after"]["nested"]["value"] = 999

    assert (criteria, before, after) == original
    assert second["result"] == "IMPROVED"
