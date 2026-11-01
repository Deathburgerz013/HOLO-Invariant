from copy import deepcopy

import pytest

from tests.test_absence_to_persisted_correction_integration import _proposal
from holosim.continuity_under_absence import build_continuity_receipt
from holosim.environment_invariant_receipts import evaluate_environment_invariant
from holosim.reconstruction_correction_binding import (
    ReconstructionCorrectionBindingError,
    build_reconstruction_correction_binding,
    validate_reconstruction_correction_binding,
)


def inputs():
    proposal = _proposal()
    endpoint = deepcopy(proposal["candidate_claims"])
    receipt = build_continuity_receipt(
        prior_state=proposal["current_claims"],
        current_state=endpoint,
        observer_present_before=True,
        observer_present_after=False,
    )
    evidence = evaluate_environment_invariant(
        invariant_id="binding-test",
        statement="observed endpoint equals declared endpoint",
        scope={"phase": "post_absence"},
        environment=endpoint,
        environment_probe=lambda: endpoint,
        check=lambda: True,
        check_id="binding-test-check",
        observed_at="2026-10-31T20:00:00-07:00",
    )
    return receipt, evidence, proposal


def bind(receipt, evidence, proposal):
    return build_reconstruction_correction_binding(
        continuity_receipt=receipt,
        external_evidence=evidence,
        proposal=proposal,
    )


def test_matching_inputs_validate_and_remain_non_authorizing():
    receipt, evidence, proposal = inputs()
    original = deepcopy((receipt, evidence, proposal))
    result = bind(receipt, evidence, proposal)

    assert validate_reconstruction_correction_binding(result) is True
    assert result["status"] == "IDENTITY_BOUND"
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert result["canonical_mutation"] is False
    assert result["correction_applied"] is False
    assert result["supersession_performed"] is False
    assert (receipt, evidence, proposal) == original


def test_repeated_inputs_produce_identical_binding():
    receipt, evidence, proposal = inputs()
    assert bind(receipt, evidence, proposal) == bind(
        receipt, evidence, proposal
    )


def test_mismatched_reconstructed_endpoint_rejected():
    receipt, evidence, proposal = inputs()
    endpoint = {"color": {"value": "blue"}, "shape": {"value": "square"}}
    wrong_receipt = build_continuity_receipt(
        prior_state=proposal["current_claims"],
        current_state=endpoint,
        observer_present_before=True,
        observer_present_after=False,
    )
    wrong_evidence = evaluate_environment_invariant(
        invariant_id="wrong-endpoint",
        statement="observed endpoint equals declared endpoint",
        scope={"phase": "post_absence"},
        environment=endpoint,
        environment_probe=lambda: endpoint,
        check=lambda: True,
        check_id="wrong-endpoint-check",
        observed_at="2026-10-31T20:00:00-07:00",
    )
    with pytest.raises(ReconstructionCorrectionBindingError):
        bind(wrong_receipt, wrong_evidence, proposal)


def test_missing_evidence_rejected():
    receipt, _, proposal = inputs()
    with pytest.raises(ReconstructionCorrectionBindingError):
        bind(receipt, None, proposal)


def test_tampered_continuity_receipt_rejected():
    receipt, evidence, proposal = inputs()
    receipt["prior_state"]["shape"]["value"] = "tampered"
    with pytest.raises(ReconstructionCorrectionBindingError):
        bind(receipt, evidence, proposal)


def test_tampered_proposal_rejected():
    receipt, evidence, proposal = inputs()
    proposal["candidate_claims"]["shape"]["value"] = "tampered"
    with pytest.raises(ReconstructionCorrectionBindingError):
        bind(receipt, evidence, proposal)


def test_tampered_external_evidence_rejected():
    receipt, evidence, proposal = inputs()
    evidence["status"] = "HELD_BUT_ALTERED"
    with pytest.raises(ReconstructionCorrectionBindingError):
        bind(receipt, evidence, proposal)


def test_tampered_binding_rejected():
    receipt, evidence, proposal = inputs()
    result = bind(receipt, evidence, proposal)
    result["write_authority"] = "GRANTED"
    with pytest.raises(ReconstructionCorrectionBindingError):
        validate_reconstruction_correction_binding(result)


def test_extra_binding_field_rejected():
    receipt, evidence, proposal = inputs()
    result = bind(receipt, evidence, proposal)
    result["unexpected"] = True
    with pytest.raises(ReconstructionCorrectionBindingError):
        validate_reconstruction_correction_binding(result)
