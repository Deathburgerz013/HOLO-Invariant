from __future__ import annotations

import copy

import pytest

from holosim.canonical import stable_hash
from holosim.choice_consequence_oracle import (
    ChoiceConsequenceOracleError,
    build_choice_consequence_receipt,
    verify_choice_consequence_receipt,
)


def _assumptions():
    return [
        {
            "assumption_id": "capacity_available",
            "statement": "Required compute remains available.",
            "status": "VERIFIED",
            "evidence_references": ["sha256:" + "a" * 64],
        },
        {
            "assumption_id": "demand_continues",
            "statement": "Demand may continue during the observed window.",
            "status": "DECLARED",
            "evidence_references": [],
        },
    ]


def _choices():
    return [
        {
            "choice_id": "build_now",
            "action": "Build the bounded capability now.",
            "consequences": [
                {
                    "consequence_id": "earlier_feedback",
                    "statement": "Usable feedback could arrive earlier.",
                    "condition_assumption_ids": ["capacity_available"],
                    "valence": "BENEFIT",
                },
                {
                    "consequence_id": "rework_exposure",
                    "statement": "Changed demand could create rework.",
                    "condition_assumption_ids": ["demand_continues"],
                    "valence": "RISK",
                },
            ],
        },
        {
            "choice_id": "wait",
            "action": "Wait for another observation.",
            "consequences": [
                {
                    "consequence_id": "later_evidence",
                    "statement": "Another observation could reduce uncertainty.",
                    "condition_assumption_ids": [],
                    "valence": "BENEFIT",
                }
            ],
        },
    ]


def _receipt():
    return build_choice_consequence_receipt(
        decision_id="oracle-slice-1",
        observed_state={"commit": "abc123", "tests_passed": 151},
        assumptions=_assumptions(),
        choices=_choices(),
    )


def test_builds_and_verifies_conditional_scenario_receipt():
    receipt = _receipt()
    assert verify_choice_consequence_receipt(receipt) is True
    assert [branch["consequence_id"] for branch in receipt["scenario_branches"]] == [
        "earlier_feedback", "rework_exposure", "later_evidence"
    ]
    assert all(
        branch["status"] == "POSSIBLE_IF_ASSUMPTIONS_HOLD"
        for branch in receipt["scenario_branches"]
    )


def test_logically_identical_input_order_has_same_identity():
    first = _receipt()
    second = build_choice_consequence_receipt(
        decision_id="oracle-slice-1",
        observed_state={"tests_passed": 151, "commit": "abc123"},
        assumptions=list(reversed(_assumptions())),
        choices=list(reversed(_choices())),
    )
    assert first == second


def test_receipt_grants_no_prediction_recommendation_or_authority():
    receipt = _receipt()
    assert receipt["prediction_status"] == "CONDITIONAL_ONLY"
    assert receipt["recommended_choice_id"] is None
    assert receipt["probability_claimed"] is False
    assert receipt["causation_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_unknown_assumption_reference_is_rejected():
    choices = _choices()
    choices[0]["consequences"][0]["condition_assumption_ids"] = ["missing"]
    with pytest.raises(ChoiceConsequenceOracleError, match="unknown assumption_id"):
        build_choice_consequence_receipt(
            decision_id="decision", observed_state={},
            assumptions=_assumptions(), choices=choices,
        )


def test_duplicate_choice_id_is_rejected():
    choices = _choices()
    choices[1]["choice_id"] = choices[0]["choice_id"]
    with pytest.raises(ChoiceConsequenceOracleError, match="choice_id values"):
        build_choice_consequence_receipt(
            decision_id="decision", observed_state={},
            assumptions=_assumptions(), choices=choices,
        )


def test_duplicate_consequence_id_across_choices_is_rejected():
    choices = _choices()
    choices[1]["consequences"][0]["consequence_id"] = "earlier_feedback"
    with pytest.raises(ChoiceConsequenceOracleError, match="globally unique"):
        build_choice_consequence_receipt(
            decision_id="decision", observed_state={},
            assumptions=_assumptions(), choices=choices,
        )


def test_comparison_requires_at_least_two_choices():
    with pytest.raises(ChoiceConsequenceOracleError, match="at least two choices"):
        build_choice_consequence_receipt(
            decision_id="decision", observed_state={},
            assumptions=_assumptions(), choices=_choices()[:1],
        )


def test_verified_assumption_requires_evidence_reference():
    assumptions = _assumptions()
    assumptions[0]["evidence_references"] = []
    with pytest.raises(ChoiceConsequenceOracleError, match="requires evidence"):
        build_choice_consequence_receipt(
            decision_id="decision", observed_state={},
            assumptions=assumptions, choices=_choices(),
        )


def test_input_mutation_does_not_change_receipt():
    state = {"nested": {"value": 1}}
    assumptions = _assumptions()
    choices = _choices()
    receipt = build_choice_consequence_receipt(
        decision_id="decision", observed_state=state,
        assumptions=assumptions, choices=choices,
    )
    state["nested"]["value"] = 2
    assumptions[0]["statement"] = "changed"
    choices[0]["action"] = "changed"
    assert receipt["observed_state"]["nested"]["value"] == 1
    assert verify_choice_consequence_receipt(receipt) is True


def test_hash_tampering_is_rejected():
    receipt = _receipt()
    receipt["scenario_branches"][0]["statement"] = "tampered"
    with pytest.raises(ChoiceConsequenceOracleError, match="receipt hash mismatch"):
        verify_choice_consequence_receipt(receipt)


def test_rehashed_recommendation_forgery_is_rejected_semantically():
    receipt = _receipt()
    receipt["recommended_choice_id"] = "build_now"
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(ChoiceConsequenceOracleError, match="internally inconsistent"):
        verify_choice_consequence_receipt(receipt)


def test_rehashed_probability_forgery_is_rejected_semantically():
    receipt = _receipt()
    receipt["probability_claimed"] = True
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(ChoiceConsequenceOracleError, match="internally inconsistent"):
        verify_choice_consequence_receipt(receipt)


def test_extra_authority_field_is_rejected_even_when_rehashed():
    receipt = _receipt()
    receipt["approval"] = "GRANTED"
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(ChoiceConsequenceOracleError, match="receipt fields mismatch"):
        verify_choice_consequence_receipt(receipt)


def test_nonfinite_observed_state_is_rejected():
    with pytest.raises(ChoiceConsequenceOracleError, match="finite"):
        build_choice_consequence_receipt(
            decision_id="decision", observed_state={"value": float("nan")},
            assumptions=_assumptions(), choices=_choices(),
        )
