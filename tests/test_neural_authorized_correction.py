import copy

import pytest

from experiments.neural_checkpoint import capture_checkpoint, verify_checkpoint
from experiments.neural_correction import Perceptron
from holosim.typed_operational_authorization import (
    ACTION_NEURAL_WEIGHT_CORRECTION,
    ACTION_SERVICE_APPEND,
    OperationalAuthorizationError,
    build_operational_authorization,
)
from experiments.neural_authorized_correction import (
    propose_neural_correction,
    verify_neural_correction_proposal,
    verify_authorized_neural_correction,
)


def test_proposal_does_not_mutate_source_checkpoint():
    model = Perceptron(2)
    before = capture_checkpoint(model, "binary-example")
    original = copy.deepcopy(before)

    proposal = propose_neural_correction(
        before, inputs=(1, 0), expected=1,
    )

    assert before == original
    assert model.weights == [0, 0]
    assert model.bias == 0
    assert proposal["changed"] is True
    assert proposal["accepted"] is False
    assert proposal["write_authority"] == "NONE"
    assert proposal["truth_claimed"] is False
    assert verify_checkpoint(proposal["after_checkpoint"])
    assert proposal["after_checkpoint"]["weights"] == [1, 0]
    assert proposal["after_checkpoint"]["bias"] == 1


def test_proposal_is_deterministic():
    before = capture_checkpoint(Perceptron(2), "binary-example")
    first = propose_neural_correction(
        before, inputs=(1, 0), expected=1,
    )
    second = propose_neural_correction(
        before, inputs=(1, 0), expected=1,
    )

    assert first == second


def test_invalid_checkpoint_fails_closed():
    before = capture_checkpoint(Perceptron(2), "binary-example")
    before["weights"][0] = 999

    with pytest.raises(ValueError, match="checkpoint hash mismatch"):
        propose_neural_correction(
            before, inputs=(1, 0), expected=1,
        )


def test_invalid_training_input_fails_closed():
    before = capture_checkpoint(Perceptron(2), "binary-example")

    with pytest.raises(ValueError):
        propose_neural_correction(
            before, inputs=(2, 0), expected=1,
        )



def _proposal_pair():
    before = capture_checkpoint(Perceptron(2), "binary-example")
    proposal = propose_neural_correction(
        before, inputs=(1, 0), expected=1,
    )
    return before, proposal


def test_verified_neural_proposal_accepts_exact_reconstruction():
    before, proposal = _proposal_pair()
    assert verify_neural_correction_proposal(before, proposal)


def test_modified_after_weights_are_rejected():
    before, proposal = _proposal_pair()
    proposal["after_checkpoint"]["weights"][0] = 999

    with pytest.raises(ValueError, match="does not match"):
        verify_neural_correction_proposal(before, proposal)


def test_forged_proposal_hash_is_rejected():
    before, proposal = _proposal_pair()
    proposal["proposal_hash"] = "a" * 64

    with pytest.raises(ValueError, match="does not match"):
        verify_neural_correction_proposal(before, proposal)


def test_changed_correction_inputs_are_rejected():
    before, proposal = _proposal_pair()
    proposal["inputs"] = [0, 1]

    with pytest.raises(ValueError, match="does not match"):
        verify_neural_correction_proposal(before, proposal)


def test_missing_proposal_fields_are_rejected():
    before, proposal = _proposal_pair()
    del proposal["before_checkpoint_hash"]

    with pytest.raises(ValueError, match="fields mismatch"):
        verify_neural_correction_proposal(before, proposal)


def test_wrong_original_checkpoint_is_rejected():
    before, proposal = _proposal_pair()
    other = capture_checkpoint(Perceptron(2), "different-objective")

    with pytest.raises(ValueError, match="does not match"):
        verify_neural_correction_proposal(other, proposal)


def test_invalid_proposal_authority_claim_is_rejected():
    before, proposal = _proposal_pair()
    proposal["accepted"] = True

    with pytest.raises(ValueError, match="invalid proposal contract"):
        verify_neural_correction_proposal(before, proposal)



def _neural_authorization(proposal, *, action=ACTION_NEURAL_WEIGHT_CORRECTION):
    return build_operational_authorization(
        authorization_id="neural-review-1",
        actor_id="external-reviewer",
        action=action,
        target_sha256=proposal["proposal_hash"],
        approval_reference="review:neural-1",
    )


def test_exact_neural_authorization_verifies_without_mutation():
    before, proposal = _proposal_pair()
    original = copy.deepcopy(before)
    authorization = _neural_authorization(proposal)

    assert verify_authorized_neural_correction(
        before, proposal, authorization,
    )
    assert before == original
    assert authorization["execution_authority"] == "NONE"
    assert authorization["truth_claimed"] is False


def test_wrong_authorization_action_is_rejected():
    before, proposal = _proposal_pair()
    authorization = _neural_authorization(
        proposal, action=ACTION_SERVICE_APPEND,
    )

    with pytest.raises(
        OperationalAuthorizationError,
        match="action does not match",
    ):
        verify_authorized_neural_correction(
            before, proposal, authorization,
        )


def test_wrong_authorization_target_is_rejected():
    before, proposal = _proposal_pair()
    authorization = _neural_authorization(proposal)
    authorization["target_sha256"] = "a" * 64

    with pytest.raises(OperationalAuthorizationError):
        verify_authorized_neural_correction(
            before, proposal, authorization,
        )


def test_different_valid_target_authorization_is_rejected():
    before, proposal = _proposal_pair()

    authorization = build_operational_authorization(
        authorization_id="neural-review-2",
        actor_id="external-reviewer",
        action=ACTION_NEURAL_WEIGHT_CORRECTION,
        target_sha256="b" * 64,
        approval_reference="review:neural-2",
    )

    with pytest.raises(
        OperationalAuthorizationError,
        match="target does not match",
    ):
        verify_authorized_neural_correction(
            before, proposal, authorization,
        )


def test_tampered_proposal_rejected_even_with_matching_authorization():
    before, proposal = _proposal_pair()
    authorization = _neural_authorization(proposal)
    proposal["after_checkpoint"]["bias"] = 999

    with pytest.raises(ValueError, match="does not match"):
        verify_authorized_neural_correction(
            before, proposal, authorization,
        )
