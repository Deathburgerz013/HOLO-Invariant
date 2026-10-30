"""Tests for read-only persisted absence-correction attestation."""

from copy import deepcopy

import pytest

from holosim.absence_claim_correction_binding import (
    build_absence_claim_correction_binding,
)
from holosim.continuity_under_absence import build_continuity_receipt
from holosim.environment_invariant_receipts import evaluate_environment_invariant
from holosim.persisted_absence_correction_attestation import (
    PersistedAbsenceCorrectionAttestationError,
    build_persisted_absence_correction_attestation,
    validate_persisted_absence_correction_attestation,
)
from holosim.verified_claim_correction_transition import (
    build_verified_claim_correction_transition_candidate,
)

from test_absence_to_persisted_correction_integration import (
    _persist,
    _proposal,
    _verify,
)


def _inputs(tmp_path):
    proposal = _proposal()
    verification = _verify(proposal)
    candidate = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-2",
    )

    prior = deepcopy(proposal["current_claims"])
    endpoint = deepcopy(proposal["candidate_claims"])

    receipt = build_continuity_receipt(
        prior_state=prior,
        current_state=endpoint,
        observer_present_before=True,
        observer_present_after=False,
    )
    evidence = evaluate_environment_invariant(
        invariant_id="persisted-absence-endpoint",
        statement="observed endpoint equals declared endpoint",
        scope={"phase": "post_absence"},
        environment=endpoint,
        environment_probe=lambda: endpoint,
        check=lambda: True,
        check_id="persisted-absence-endpoint-check",
        observed_at="2026-10-29T21:00:00-07:00",
    )
    binding = build_absence_claim_correction_binding(
        continuity_receipt=receipt,
        external_evidence=evidence,
        transition_candidate=candidate,
    )
    store, commit = _persist(tmp_path, proposal, verification)
    return store, commit, receipt, evidence, binding


def _build(store, commit, receipt, evidence, binding):
    return build_persisted_absence_correction_attestation(
        store=store,
        record_id=commit["record_id"],
        continuity_receipt=receipt,
        external_evidence=evidence,
        absence_binding=binding,
    )


def test_matching_persisted_correction_is_deterministic_and_read_only(tmp_path):
    store, commit, receipt, evidence, binding = _inputs(tmp_path)
    before = store.current_head()
    original = deepcopy((receipt, evidence, binding))

    first = _build(store, commit, receipt, evidence, binding)
    second = _build(store, commit, receipt, evidence, binding)

    assert first == second
    assert first["record_id"] == commit["record_id"]
    assert first["chain_entry_hash"] == commit["chain_entry"]["hash"]
    assert first["absence_binding_hash"] == binding["binding_hash"]
    assert first["post_persistence_association"] is True
    assert first["precommit_evidence_checked"] is False
    assert first["absence_interval_observed"] is False
    assert first["absence_interval_reconstructed"] is False
    assert first["truth_claimed"] is False
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"
    assert first["execution_authority"] == "NONE"
    assert first["canonical_mutation"] is False
    assert store.current_head() == before
    assert (receipt, evidence, binding) == original

    assert validate_persisted_absence_correction_attestation(
        first,
        store=store,
        continuity_receipt=receipt,
        external_evidence=evidence,
        absence_binding=binding,
    )


def test_missing_persisted_record_fails(tmp_path):
    store, commit, receipt, evidence, binding = _inputs(tmp_path)
    missing = dict(commit, record_id="missing-record")

    with pytest.raises(PersistedAbsenceCorrectionAttestationError):
        _build(store, missing, receipt, evidence, binding)


def test_tampered_continuity_evidence_fails(tmp_path):
    store, commit, receipt, evidence, binding = _inputs(tmp_path)
    receipt["current_state_hash"] = "0" * 64

    with pytest.raises(PersistedAbsenceCorrectionAttestationError):
        _build(store, commit, receipt, evidence, binding)


def test_tampered_external_evidence_fails(tmp_path):
    store, commit, receipt, evidence, binding = _inputs(tmp_path)
    evidence["receipt_hash"] = "0" * 64

    with pytest.raises(PersistedAbsenceCorrectionAttestationError):
        _build(store, commit, receipt, evidence, binding)


def test_tampered_absence_binding_fails(tmp_path):
    store, commit, receipt, evidence, binding = _inputs(tmp_path)
    binding["transition_binding_hash"] = "0" * 64

    with pytest.raises(PersistedAbsenceCorrectionAttestationError):
        _build(store, commit, receipt, evidence, binding)


def test_tampered_attestation_fails_validation(tmp_path):
    store, commit, receipt, evidence, binding = _inputs(tmp_path)
    attestation = _build(store, commit, receipt, evidence, binding)
    attestation["precommit_evidence_checked"] = True

    with pytest.raises(
        PersistedAbsenceCorrectionAttestationError,
        match="attestation schema or identity mismatch",
    ):
        validate_persisted_absence_correction_attestation(
            attestation,
            store=store,
            continuity_receipt=receipt,
            external_evidence=evidence,
            absence_binding=binding,
        )


def test_non_dictionary_attestation_fails(tmp_path):
    store, _, receipt, evidence, binding = _inputs(tmp_path)

    with pytest.raises(PersistedAbsenceCorrectionAttestationError):
        validate_persisted_absence_correction_attestation(
            None,
            store=store,
            continuity_receipt=receipt,
            external_evidence=evidence,
            absence_binding=binding,
        )

def test_different_valid_transition_identity_cannot_inherit_absence_binding(tmp_path):
    store, commit, receipt, evidence, original_binding = _inputs(tmp_path)

    proposal = _proposal()
    verification = _verify(proposal)
    different_candidate = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="different-baseline-2",
    )

    different_binding = build_absence_claim_correction_binding(
        continuity_receipt=receipt,
        external_evidence=evidence,
        transition_candidate=different_candidate,
    )

    assert different_binding != original_binding
    assert (
        different_candidate["previous_baseline_state_hash"]
        == original_binding["prior_state_hash"]
    )
    assert (
        different_candidate["next_baseline_state_hash"]
        == original_binding["current_state_hash"]
    )

    before = store.current_head()

    with pytest.raises(PersistedAbsenceCorrectionAttestationError):
        _build(store, commit, receipt, evidence, different_binding)

    assert store.current_head() == before

def test_historical_attestation_survives_valid_successor_commit(tmp_path):
    from holosim.authorized_verified_claim_correction_transition import (
        authorize_verified_claim_correction_transition,
    )
    from holosim.baseline_observation_compare import (
        FINDING_CORRECTION,
        FINDING_SUPPORT,
    )
    from holosim.bounded_claim_correction import propose_bounded_claim_correction
    from holosim.canonical import stable_hash
    from holosim.evidence_bound_baseline_observation import (
        build_evidence_bound_baseline_observation,
        compare_evidence_bound_baseline_observations,
        evaluate_evidence_bound_baseline_promotion,
    )
    from holosim.hook_contract import build_hook_request, build_hook_result
    from holosim.typed_operational_authorization import (
        build_operational_authorization,
    )

    store, first_commit, receipt, evidence, binding = _inputs(tmp_path)
    original = _build(store, first_commit, receipt, evidence, binding)

    claims = {
        "color": {"value": "blue"},
        "shape": {"value": "round"},
    }
    replacements = {"shape": {"value": "oval"}}
    baseline_hash = stable_hash(claims)

    observations = []
    for observer in ("successor-left", "successor-right"):
        request = build_hook_request(
            hook_id=observer,
            action="observe-baseline",
            reference="baseline-2",
            payload={"baseline_state_hash": baseline_hash},
        )
        result = build_hook_result(
            request=request,
            status="OBSERVED",
            evidence={
                "observer": observer,
                "proposed_claim_replacements": deepcopy(replacements),
            },
        )
        observations.append(
            build_evidence_bound_baseline_observation(
                observer_id=observer,
                baseline_id="baseline-2",
                baseline_state_hash=baseline_hash,
                findings={
                    "color": FINDING_SUPPORT,
                    "shape": FINDING_CORRECTION,
                },
                request=request,
                observation_result=result,
            )
        )

    comparison = compare_evidence_bound_baseline_observations(*observations)
    promotion = evaluate_evidence_bound_baseline_promotion(
        comparison=comparison
    )
    successor_proposal = propose_bounded_claim_correction(
        comparison=comparison,
        promotion=promotion,
        current_claims=claims,
        proposed_replacements=replacements,
    )
    successor_verification = _verify(successor_proposal)
    assert successor_verification["verified_to_request_authorization"] is True

    successor_candidate = build_verified_claim_correction_transition_candidate(
        verification=successor_verification,
        next_baseline_id="baseline-3",
    )
    assert successor_candidate["previous_baseline_id"] == "baseline-2"
    assert successor_candidate["previous_baseline_state_hash"] == baseline_hash

    authorization = build_operational_authorization(
        authorization_id="authorization-2",
        actor_id="external-operator",
        action=successor_candidate["authorization_action"],
        target_sha256=successor_candidate["authorization_target_sha256"],
        approval_reference="operator-review-2",
    )
    authorized = authorize_verified_claim_correction_transition(
        transition_binding=successor_candidate,
        authorization=authorization,
    )
    successor_commit = store.commit_verified_claim_correction(
        authorized_correction=authorized
    )

    assert successor_commit["record_id"] != first_commit["record_id"]
    assert store.current_head()["baseline_id"] == "baseline-3"
    assert store.current_head()["transition_count"] == 2

    historical_read = store.read_verified_claim_correction(
        record_id=first_commit["record_id"]
    )
    assert historical_read["record_is_current_head"] is False

    assert _build(store, first_commit, receipt, evidence, binding) == original
    assert validate_persisted_absence_correction_attestation(
        original,
        store=store,
        continuity_receipt=receipt,
        external_evidence=evidence,
        absence_binding=binding,
    )

@pytest.mark.parametrize("record_id", [None, "", 123, [], {}])
def test_malformed_attestation_record_id_fails_with_domain_error(tmp_path, record_id):
    from holosim.persisted_absence_correction_attestation import (
        PersistedAbsenceCorrectionAttestationError,
        validate_persisted_absence_correction_attestation,
    )

    with pytest.raises(PersistedAbsenceCorrectionAttestationError):
        validate_persisted_absence_correction_attestation(
            {"record_id": record_id},
            store=None,
            continuity_receipt={},
            external_evidence={},
            absence_binding={},
        )
