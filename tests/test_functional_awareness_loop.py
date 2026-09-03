from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.functional_awareness_loop import (
    FunctionalAwarenessLoopError,
    build_functional_awareness_receipt,
    verify_functional_awareness_receipt,
)


SOLUTION = {
    "solution_id": "solution.adjust",
    "description": "Apply the bounded adjustment.",
    "execution_status": "VERIFIED_EXECUTED",
    "execution_receipt_hash": "a" * 64,
}
ADAPTATION = {
    "adaptation_id": "adaptation.keep",
    "statement": "Propose this adjustment for a later authorized decision.",
}


def build(before, after, *, before_status="VERIFIED", after_status="VERIFIED", adaptation=None):
    return build_functional_awareness_receipt(
        loop_id="loop-1",
        goal_state={"safe": True, "score": 2},
        before_state=before,
        after_state=after,
        before_evidence_status=before_status,
        after_evidence_status=after_status,
        solution=SOLUTION,
        adaptation=adaptation,
    )


def rehash(receipt):
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)


def test_resolved_mismatch_proposes_bounded_adaptation():
    receipt = build({"safe": False, "score": 2}, {"safe": True, "score": 2}, adaptation=ADAPTATION)
    assert receipt["effect"] == "RESOLVED"
    assert receipt["before_mismatch_paths"] == ["safe"]
    assert receipt["after_mismatch_paths"] == []
    assert receipt["problem_visible"] is True
    assert receipt["awareness_carried_forward"] is True
    assert receipt["adaptation_status"] == "PROPOSED"
    assert verify_functional_awareness_receipt(receipt)


def test_strict_mismatch_reduction_is_improved():
    receipt = build({"safe": False, "score": 0}, {"safe": True, "score": 0}, adaptation=ADAPTATION)
    assert receipt["effect"] == "IMPROVED"
    assert receipt["before_mismatch_paths"] == ["safe", "score"]
    assert receipt["after_mismatch_paths"] == ["score"]


@pytest.mark.parametrize(
    ("after", "effect", "reason"),
    [
        ({"safe": False, "score": 0}, "UNCHANGED", "MISMATCH_SET_UNCHANGED"),
        ({"safe": False, "score": 0, "extra": 1}, "WORSENED", "MISMATCH_SET_EXPANDED"),
        ({"safe": True, "score": 0}, "CHANGED", "MISMATCH_SET_CHANGED_WITHOUT_SUBSET_GAIN"),
    ],
)
def test_non_improving_effects_withhold_adaptation(after, effect, reason):
    before = {"safe": False, "score": 2} if effect == "CHANGED" else {"safe": False, "score": 0}
    receipt = build(before, after)
    assert receipt["effect"] == effect
    assert receipt["effect_reason"] == reason
    assert receipt["adaptation_status"] == "WITHHELD"


def test_goal_already_matched_is_no_problem():
    receipt = build({"safe": True, "score": 2}, {"safe": True, "score": 2})
    assert receipt["effect"] == "NO_PROBLEM"
    assert receipt["problem_visible"] is False
    assert receipt["awareness_carried_forward"] is False


def test_unverified_before_cannot_establish_problem():
    receipt = build({"safe": False}, None, before_status="UNVERIFIED", after_status="UNAVAILABLE")
    assert receipt["effect"] == "UNKNOWN"
    assert receipt["effect_reason"] == "BEFORE_EVIDENCE_NOT_VERIFIED"
    assert receipt["before_state_hash"] is None
    assert receipt["awareness_carried_forward"] is False


def test_unavailable_after_preserves_visible_problem_but_not_improvement():
    receipt = build({"safe": False, "score": 2}, None, after_status="UNAVAILABLE")
    assert receipt["effect"] == "UNKNOWN"
    assert receipt["after_state_hash"] is None
    assert receipt["after_mismatch_paths"] is None
    assert receipt["awareness_carried_forward"] is True


def test_unverified_after_must_not_supply_state():
    with pytest.raises(FunctionalAwarenessLoopError, match="after_state must be null"):
        build({"safe": False, "score": 2}, {"safe": True}, after_status="UNVERIFIED")


def test_adaptation_is_required_only_for_verified_reduction():
    with pytest.raises(FunctionalAwarenessLoopError, match="required exactly"):
        build({"safe": False, "score": 2}, {"safe": True, "score": 2})
    with pytest.raises(FunctionalAwarenessLoopError, match="required exactly"):
        build({"safe": False, "score": 2}, {"safe": False, "score": 2}, adaptation=ADAPTATION)


def test_verified_solution_requires_execution_receipt():
    solution = {**SOLUTION, "execution_receipt_hash": None}
    with pytest.raises(FunctionalAwarenessLoopError, match="requires exactly"):
        build_functional_awareness_receipt(
            loop_id="loop-1", goal_state=1, before_state=0, after_state=1,
            before_evidence_status="VERIFIED", after_evidence_status="VERIFIED",
            solution=solution, adaptation=ADAPTATION,
        )


def test_receipt_never_executes_trains_accepts_or_claims_consciousness():
    receipt = build({"safe": False, "score": 2}, {"safe": True, "score": 2}, adaptation=ADAPTATION)
    assert receipt["solution_executed_by_loop"] is False
    assert receipt["training_applied"] is False
    assert receipt["subjective_consciousness_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == receipt["execution_authority"] == "NONE"


def test_raw_states_are_committed_by_hash_not_copied():
    receipt = build({"safe": False, "score": 2}, {"safe": True, "score": 2}, adaptation=ADAPTATION)
    assert "goal_state" not in receipt
    assert "before_state" not in receipt
    assert "after_state" not in receipt


def test_nested_paths_are_deterministic_and_inputs_are_isolated():
    goal = {"z": [{"value": 2}], "a": True}
    before = {"z": [{"value": 0}], "a": False}
    after = deepcopy(goal)
    receipt = build_functional_awareness_receipt(
        loop_id="loop-2", goal_state=goal, before_state=before, after_state=after,
        before_evidence_status="VERIFIED", after_evidence_status="VERIFIED",
        solution=SOLUTION, adaptation=ADAPTATION,
    )
    goal["z"][0]["value"] = 99
    assert receipt["before_mismatch_paths"] == ["a", "z[0].value"]
    assert verify_functional_awareness_receipt(receipt)


def test_nonfinite_state_is_rejected():
    with pytest.raises(FunctionalAwarenessLoopError, match="finite"):
        build({"safe": False, "score": float("nan")}, None, after_status="UNAVAILABLE")


def test_hash_tamper_is_rejected():
    receipt = build({"safe": False, "score": 2}, {"safe": True, "score": 2}, adaptation=ADAPTATION)
    receipt["effect"] = "UNKNOWN"
    with pytest.raises(FunctionalAwarenessLoopError, match="hash mismatch"):
        verify_functional_awareness_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("effect", "UNKNOWN", "derived awareness"),
        ("training_applied", True, "forbidden claim or authority"),
        ("subjective_consciousness_claimed", True, "forbidden claim or authority"),
        ("execution_authority", "SELF", "forbidden claim or authority"),
        ("interpretation_notice", "Consciousness proven.", "interpretation boundary"),
        ("goal_state_hash", None, "cannot be null"),
    ],
)
def test_rehashed_semantic_or_authority_forgery_is_rejected(field, value, message):
    receipt = build({"safe": False, "score": 2}, {"safe": True, "score": 2}, adaptation=ADAPTATION)
    receipt[field] = value
    rehash(receipt)
    with pytest.raises(FunctionalAwarenessLoopError, match=message):
        verify_functional_awareness_receipt(receipt)


def test_extra_receipt_field_is_rejected_even_if_rehashed():
    receipt = build({"safe": False, "score": 2}, {"safe": True, "score": 2}, adaptation=ADAPTATION)
    receipt["future_prediction"] = True
    rehash(receipt)
    with pytest.raises(FunctionalAwarenessLoopError, match="fields mismatch"):
        verify_functional_awareness_receipt(receipt)
