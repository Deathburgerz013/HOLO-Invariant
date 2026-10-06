from dataclasses import replace

import pytest

from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    SubtractTransition,
    TransitionDecisionReceipt,
    execute_inv_transition,
    execute_inv_transition_with_receipt,
    verify_transition_receipt,
)


def make_receipt() -> TransitionDecisionReceipt:
    return execute_inv_transition_with_receipt(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )


def test_receipt_preserves_execution_semantics_and_decision():
    receipt = make_receipt()

    assert receipt.previous_state == 5
    assert receipt.transition == SubtractTransition(amount=6)
    assert receipt.candidate_state == -1
    assert receipt.invariant == GreaterThanOrEqualInvariant(minimum=0)
    assert receipt.accepted is False
    assert receipt.resulting_state == 5


def test_receipt_matches_existing_execution_behavior():
    transition = SubtractTransition(amount=6)
    invariant = GreaterThanOrEqualInvariant(minimum=0)

    result = execute_inv_transition(
        state=5,
        transition=transition,
        invariant=invariant,
    )
    receipt = execute_inv_transition_with_receipt(
        state=5,
        transition=transition,
        invariant=invariant,
    )

    assert receipt.previous_state == result.previous_state
    assert receipt.candidate_state == result.proposed_state
    assert receipt.accepted == result.accepted
    assert receipt.resulting_state == result.state


def test_valid_receipt_verifies():
    assert verify_transition_receipt(make_receipt()) is True


@pytest.mark.parametrize(
    "changed_receipt",
    [
        lambda receipt: replace(receipt, candidate_state=-2),
        lambda receipt: replace(receipt, accepted=True),
        lambda receipt: replace(receipt, resulting_state=-1),
    ],
)
def test_contradictory_derived_receipt_fields_fail_verification(changed_receipt):
    receipt = make_receipt()

    assert verify_transition_receipt(changed_receipt(receipt)) is False


def test_changed_transition_without_matching_candidate_fails_verification():
    receipt = make_receipt()
    altered = replace(
        receipt,
        transition=SubtractTransition(amount=5),
    )

    assert verify_transition_receipt(altered) is False


def test_changed_invariant_without_matching_decision_fails_verification():
    receipt = make_receipt()
    altered = replace(
        receipt,
        invariant=GreaterThanOrEqualInvariant(minimum=-1),
    )

    assert verify_transition_receipt(altered) is False


def test_unsupported_receipt_fails_closed():
    with pytest.raises(TypeError):
        verify_transition_receipt(object())
