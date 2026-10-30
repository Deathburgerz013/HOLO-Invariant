
"""Research: application-level composition across absence and persisted correction.

The continuity receipt is NOT consumed by the correction API. The identity
assertions here are integration-level requirements, not production enforcement.
"""

from copy import deepcopy

import pytest

from holosim.authorized_verified_claim_correction_transition import (
    authorize_verified_claim_correction_transition,
)
from holosim.baseline_observation_compare import FINDING_CORRECTION, FINDING_SUPPORT
from holosim.bounded_claim_correction import propose_bounded_claim_correction
from holosim.canonical import stable_hash
from holosim.continuity_under_absence import (
    build_continuity_receipt,
    reconstruct_continuity,
)
from holosim.environment_invariant_receipts import evaluate_environment_invariant
from holosim.evidence_bound_baseline_observation import (
    build_evidence_bound_baseline_observation,
    compare_evidence_bound_baseline_observations,
    evaluate_evidence_bound_baseline_promotion,
)
from holosim.evidence_bound_claim_correction_verification import (
    STATUS_UNRESOLVED,
    VERIFY_ACTION,
    verify_evidence_bound_claim_correction,
)
from holosim.hook_contract import build_hook_request, build_hook_result
from holosim.persistent_baseline_transition import PersistentBaselineTransitionStore
from holosim.post_persistence_verified_claim_reobservation import (
    STATUS_CHANGE,
    STATUS_CONFIRMED,
    STATUS_UNRESOLVED as REOBSERVATION_UNRESOLVED,
    reobserve_persisted_verified_claim_correction,
)
from holosim.typed_operational_authorization import build_operational_authorization
from holosim.verified_claim_correction_transition import (
    VerifiedClaimCorrectionTransitionError,
    build_verified_claim_correction_transition_candidate,
)


def _proposal():
    current = {"color": {"value": "blue"}, "shape": {"value": "flat"}}
    replacement = {"shape": {"value": "round"}}
    baseline_hash = stable_hash(current)
    observations = []
    for observer in ("observer-left", "observer-right"):
        request = build_hook_request(
            hook_id=observer,
            action="observe-baseline",
            reference="baseline-1",
            payload={"baseline_state_hash": baseline_hash},
        )
        result = build_hook_result(
            request=request,
            status="OBSERVED",
            evidence={
                "observer": observer,
                "proposed_claim_replacements": deepcopy(replacement),
            },
        )
        observations.append(
            build_evidence_bound_baseline_observation(
                observer_id=observer,
                baseline_id="baseline-1",
                baseline_state_hash=baseline_hash,
                findings={"color": FINDING_SUPPORT, "shape": FINDING_CORRECTION},
                request=request,
                observation_result=result,
            )
        )
    comparison = compare_evidence_bound_baseline_observations(*observations)
    promotion = evaluate_evidence_bound_baseline_promotion(comparison=comparison)
    return propose_bounded_claim_correction(
        comparison=comparison,
        promotion=promotion,
        current_claims=current,
        proposed_replacements=replacement,
    )


def _evidence(
    proposal,
    *,
    phase,
    prefix,
    shape=True,
    color=True,
    shape_status="OBSERVED",
):
    claim_set_hash = (
        proposal["baseline_state_hash"]
        if phase == "before"
        else proposal["candidate_baseline_hash"]
    )
    result = {}
    for condition_id, satisfied, status in (
        ("shape-corrected", shape, shape_status),
        ("color-preserved", color, "OBSERVED"),
    ):
        request = build_hook_request(
            hook_id=f"{prefix}-{condition_id}",
            action=VERIFY_ACTION,
            reference=condition_id,
            payload={
                "condition_id": condition_id,
                "claim_set_hash": claim_set_hash,
            },
        )
        observation = build_hook_result(
            request=request,
            status=status,
            evidence=(
                {"condition_satisfied": satisfied}
                if status == "OBSERVED"
                else {"diagnostic": status.lower()}
            ),
        )
        result[condition_id] = {
            "request": request,
            "result": observation,
        }
    return result


def _reconstruct(proposal, *, endpoint=None):
    # Endpoint evidence is separate from the correction verification receipt.
    endpoint = deepcopy(
        proposal["candidate_claims"] if endpoint is None else endpoint
    )
    receipt = build_continuity_receipt(
        prior_state=proposal["current_claims"],
        current_state=endpoint,
        observer_present_before=True,
        observer_present_after=False,
    )
    evidence = evaluate_environment_invariant(
        invariant_id="post-absence-endpoint",
        statement="observed endpoint equals declared endpoint",
        scope={"phase": "post_absence"},
        environment=endpoint,
        environment_probe=lambda: endpoint,
        check=lambda: True,
        check_id="post-absence-endpoint-check",
        observed_at="2026-10-29T21:00:00-07:00",
    )
    return reconstruct_continuity(
        receipt,
        external_evidence=evidence,
        collection_closed=True,
    )


def _assert_same_state_identity(reconstruction, proposal):
    """Application-level composition guard, NOT an existing production API."""
    assert reconstruction["prior_state"] == proposal["current_claims"]
    assert reconstruction["prior_state_hash"] == proposal["baseline_state_hash"]
    assert reconstruction["current_state"] == proposal["candidate_claims"]
    assert reconstruction["current_state_hash"] == proposal["candidate_baseline_hash"]


def _verify(proposal, *, shape_status="OBSERVED"):
    return verify_evidence_bound_claim_correction(
        proposal=proposal,
        claim_conditions={"shape": ["shape-corrected"]},
        before_evidence=_evidence(
            proposal,
            phase="before",
            prefix="original-before",
            shape=False,
        ),
        after_evidence=_evidence(
            proposal,
            phase="after",
            prefix="original-after",
            shape_status=shape_status,
        ),
    )


def _persist(tmp_path, proposal, verification):
    binding = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-2",
    )
    assert binding["previous_baseline_state_hash"] == proposal["baseline_state_hash"]
    assert binding["next_baseline_state_hash"] == proposal["candidate_baseline_hash"]

    authorization = build_operational_authorization(
        authorization_id="authorization-1",
        actor_id="external-operator",
        action=binding["authorization_action"],
        target_sha256=binding["authorization_target_sha256"],
        approval_reference="operator-review-1",
    )
    authorized = authorize_verified_claim_correction_transition(
        transition_binding=binding,
        authorization=authorization,
    )
    store = PersistentBaselineTransitionStore(
        tmp_path / "baseline-transitions.jsonl",
        initial_baseline_id="baseline-1",
        initial_baseline_state_hash=proposal["baseline_state_hash"],
    )
    commit = store.commit_verified_claim_correction(
        authorized_correction=authorized
    )
    return store, commit


def test_absence_endpoint_correction_persistence_and_later_checks(tmp_path):
    proposal = _proposal()
    reconstruction = _reconstruct(proposal)
    _assert_same_state_identity(reconstruction, proposal)

    assert reconstruction["current_state_verified"] is True
    assert reconstruction["absence_interval_observed"] is False
    assert reconstruction["absence_interval_reconstructed"] is False
    assert reconstruction["continuity_claimed"] is False

    verification = _verify(proposal)
    assert verification["verified_to_request_authorization"] is True

    store, commit = _persist(tmp_path, proposal, verification)
    original_read = store.read_verified_claim_correction(
        record_id=commit["record_id"]
    )
    original_head = store.current_head()

    for prefix, shape, status, expected in (
        ("fresh-confirmed", True, "OBSERVED", STATUS_CONFIRMED),
        ("fresh-changed", False, "OBSERVED", STATUS_CHANGE),
        ("fresh-unavailable", True, "UNAVAILABLE", REOBSERVATION_UNRESOLVED),
    ):
        observation = reobserve_persisted_verified_claim_correction(
            store=store,
            record_id=commit["record_id"],
            fresh_after_evidence=_evidence(
                proposal,
                phase="after",
                prefix=prefix,
                shape=shape,
                shape_status=status,
            ),
        )

        assert observation["status"] == expected
        assert observation["canonical_mutation"] is False
        assert observation["truth_claimed"] is False
        assert store.current_head() == original_head
        assert (
            store.read_verified_claim_correction(record_id=commit["record_id"])
            == original_read
        )
        assert reconstruction["absence_interval_observed"] is False
        assert reconstruction["absence_interval_reconstructed"] is False


def test_different_verified_endpoint_does_not_bind_to_correction():
    proposal = _proposal()
    unrelated_endpoint = {
        "color": {"value": "red"},
        "shape": {"value": "round"},
    }
    reconstruction = _reconstruct(proposal, endpoint=unrelated_endpoint)

    assert reconstruction["current_state_verified"] is True

    with pytest.raises(AssertionError):
        _assert_same_state_identity(reconstruction, proposal)

    assert reconstruction["absence_interval_observed"] is False


def test_unavailable_condition_blocks_correction_authorization_even_with_endpoint():
    proposal = _proposal()
    reconstruction = _reconstruct(proposal)
    _assert_same_state_identity(reconstruction, proposal)

    verification = _verify(proposal, shape_status="UNAVAILABLE")

    assert verification["status"] == STATUS_UNRESOLVED
    assert verification["verified_to_request_authorization"] is False

    with pytest.raises(VerifiedClaimCorrectionTransitionError):
        build_verified_claim_correction_transition_candidate(
            verification=verification,
            next_baseline_id="baseline-2",
        )

    assert reconstruction["absence_interval_observed"] is False
