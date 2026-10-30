"""Tests for read-only absence-to-correction identity binding."""

from copy import deepcopy

import pytest

from holosim.absence_claim_correction_binding import (
    AbsenceClaimCorrectionBindingError,
    build_absence_claim_correction_binding,
    validate_absence_claim_correction_binding,
)
from holosim.continuity_under_absence import build_continuity_receipt
from holosim.environment_invariant_receipts import evaluate_environment_invariant
from holosim.verified_claim_correction_transition import (
    build_verified_claim_correction_transition_candidate,
)

from test_absence_to_persisted_correction_integration import (
    _proposal,
    _verify,
)


def _inputs(*, endpoint=None, prior=None):
    proposal = _proposal()
    verification = _verify(proposal)
    transition = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-2",
    )

    prior_state = deepcopy(
        proposal["current_claims"] if prior is None else prior
    )
    endpoint_state = deepcopy(
        proposal["candidate_claims"] if endpoint is None else endpoint
    )

    receipt = build_continuity_receipt(
        prior_state=prior_state,
        current_state=endpoint_state,
        observer_present_before=True,
        observer_present_after=False,
    )

    evidence = evaluate_environment_invariant(
        invariant_id="absence-binding-endpoint",
        statement="observed endpoint equals declared endpoint",
        scope={"phase": "post_absence"},
        environment=endpoint_state,
        environment_probe=lambda: endpoint_state,
        check=lambda: True,
        check_id="absence-binding-endpoint-check",
        observed_at="2026-10-29T21:00:00-07:00",
    )

    return receipt, evidence, transition


def _build(receipt, evidence, transition):
    return build_absence_claim_correction_binding(
        continuity_receipt=receipt,
        external_evidence=evidence,
        transition_candidate=transition,
    )


def test_matching_verified_sources_produce_deterministic_binding():
    receipt, evidence, transition = _inputs()

    original = deepcopy((receipt, evidence, transition))
    first = _build(receipt, evidence, transition)
    second = _build(receipt, evidence, transition)

    assert first == second
    assert first["continuity_receipt_hash"] == receipt["receipt_hash"]
    assert first["external_evidence_hash"] == evidence["receipt_hash"]
    assert first["transition_binding_hash"] == transition["binding_hash"]
    assert first["absence_interval_observed"] is False
    assert first["absence_interval_reconstructed"] is False
    assert first["continuity_claimed"] is False
    assert first["truth_claimed"] is False
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"
    assert first["execution_authority"] == "NONE"
    assert first["canonical_mutation"] is False
    assert (receipt, evidence, transition) == original

    assert validate_absence_claim_correction_binding(
        first,
        continuity_receipt=receipt,
        external_evidence=evidence,
        transition_candidate=transition,
    )


@pytest.mark.parametrize(
    ("prior", "endpoint"),
    [
        ({"color": {"value": "red"}, "shape": {"value": "flat"}}, None),
        (None, {"color": {"value": "red"}, "shape": {"value": "round"}}),
    ],
)
def test_individually_valid_sources_with_different_states_fail(prior, endpoint):
    receipt, evidence, transition = _inputs(prior=prior, endpoint=endpoint)

    with pytest.raises(
        AbsenceClaimCorrectionBindingError,
        match="continuity endpoints do not match",
    ):
        _build(receipt, evidence, transition)


def test_tampered_continuity_receipt_fails():
    receipt, evidence, transition = _inputs()
    receipt["current_state_hash"] = "0" * 64

    with pytest.raises(AbsenceClaimCorrectionBindingError):
        _build(receipt, evidence, transition)


def test_tampered_transition_fails():
    receipt, evidence, transition = _inputs()
    transition["next_baseline_state_hash"] = "0" * 64

    with pytest.raises(AbsenceClaimCorrectionBindingError):
        _build(receipt, evidence, transition)


def test_missing_external_evidence_fails():
    receipt, _, transition = _inputs()

    with pytest.raises(AbsenceClaimCorrectionBindingError):
        _build(receipt, None, transition)


def test_binding_tampering_fails_validation():
    receipt, evidence, transition = _inputs()
    binding = _build(receipt, evidence, transition)
    binding["accepted"] = True

    with pytest.raises(
        AbsenceClaimCorrectionBindingError,
        match="binding schema or identity mismatch",
    ):
        validate_absence_claim_correction_binding(
            binding,
            continuity_receipt=receipt,
            external_evidence=evidence,
            transition_candidate=transition,
        )
