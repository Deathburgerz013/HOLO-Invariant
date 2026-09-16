from copy import deepcopy

import pytest

from holosim.authorized_baseline_transition import (
    authorize_baseline_transition,
    build_baseline_transition_candidate,
)
from holosim.baseline_observation_compare import (
    FINDING_CORRECTION,
    FINDING_SUPPORT,
)
from holosim.bounded_claim_correction import (
    propose_bounded_claim_correction,
)
from holosim.canonical import stable_hash
from holosim.evidence_bound_baseline_observation import (
    build_evidence_bound_baseline_observation,
    compare_evidence_bound_baseline_observations,
    evaluate_evidence_bound_baseline_promotion,
)
from holosim.evidence_bound_claim_correction_verification import (
    VERIFY_ACTION,
    verify_evidence_bound_claim_correction,
)
from holosim.hook_contract import build_hook_request, build_hook_result
from holosim.typed_operational_authorization import (
    ACTION_VERIFIED_CLAIM_CORRECTION_PROMOTION,
    build_operational_authorization,
)
from holosim.verified_claim_correction_transition import (
    STATUS_READY,
    VerifiedClaimCorrectionTransitionError,
    build_verified_claim_correction_transition_candidate,
    validate_verified_claim_correction_transition_candidate,
)


def _build_proposal():
    current_claims = {
        "color": {"value": "blue"},
        "shape": {"value": "flat"},
    }
    replacement = {"shape": {"value": "round"}}
    baseline_hash = stable_hash(current_claims)
    findings = {
        "color": FINDING_SUPPORT,
        "shape": FINDING_CORRECTION,
    }

    bindings = []
    for observer_id in ("observer-left", "observer-right"):
        request = build_hook_request(
            hook_id=observer_id,
            action="observe-baseline",
            reference="baseline-1",
            payload={"baseline_state_hash": baseline_hash},
        )
        result = build_hook_result(
            request=request,
            status="OBSERVED",
            evidence={
                "observer": observer_id,
                "proposed_claim_replacements": deepcopy(replacement),
            },
        )
        bindings.append(
            build_evidence_bound_baseline_observation(
                observer_id=observer_id,
                baseline_id="baseline-1",
                baseline_state_hash=baseline_hash,
                findings=findings,
                request=request,
                observation_result=result,
            )
        )

    comparison = compare_evidence_bound_baseline_observations(
        bindings[0],
        bindings[1],
    )
    promotion = evaluate_evidence_bound_baseline_promotion(
        comparison=comparison
    )
    return propose_bounded_claim_correction(
        comparison=comparison,
        promotion=promotion,
        current_claims=current_claims,
        proposed_replacements=replacement,
    )


def _condition_bundle(
    *,
    condition_id,
    claim_set_hash,
    satisfied=False,
    status="OBSERVED",
):
    request = build_hook_request(
        hook_id=f"condition-verifier-{condition_id}",
        action=VERIFY_ACTION,
        reference=condition_id,
        payload={
            "condition_id": condition_id,
            "claim_set_hash": claim_set_hash,
        },
    )
    evidence = (
        {"condition_satisfied": satisfied}
        if status == "OBSERVED"
        else {"diagnostic": status.lower()}
    )
    result = build_hook_result(
        request=request,
        status=status,
        evidence=evidence,
    )
    return {
        "request": request,
        "result": result,
    }


def _build_verification(
    *,
    after_target=True,
    after_guard=True,
    after_target_status="OBSERVED",
):
    proposal = _build_proposal()

    before_evidence = {
        "shape-corrected": _condition_bundle(
            condition_id="shape-corrected",
            claim_set_hash=proposal["baseline_state_hash"],
            satisfied=False,
        ),
        "color-preserved": _condition_bundle(
            condition_id="color-preserved",
            claim_set_hash=proposal["baseline_state_hash"],
            satisfied=True,
        ),
    }
    after_evidence = {
        "shape-corrected": _condition_bundle(
            condition_id="shape-corrected",
            claim_set_hash=proposal["candidate_baseline_hash"],
            satisfied=after_target,
            status=after_target_status,
        ),
        "color-preserved": _condition_bundle(
            condition_id="color-preserved",
            claim_set_hash=proposal["candidate_baseline_hash"],
            satisfied=after_guard,
        ),
    }

    return verify_evidence_bound_claim_correction(
        proposal=proposal,
        claim_conditions={"shape": ["shape-corrected"]},
        before_evidence=before_evidence,
        after_evidence=after_evidence,
    )


def _binding(*, next_baseline_id="baseline-2"):
    verification = _build_verification()
    binding = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id=next_baseline_id,
    )
    return verification, binding


def test_binds_verified_improvement_to_exact_transition_candidate() -> None:
    verification, binding = _binding()
    proposal = verification["proposal"]
    gate = proposal["promotion"]["gate"]

    assert binding["status"] == STATUS_READY
    assert binding["verification"] == verification
    assert binding["verification_hash"] == verification["verification_hash"]
    assert binding["proposal_hash"] == proposal["proposal_hash"]
    assert binding["promotion_gate_id"] == gate["gate_id"]
    assert binding["previous_baseline_id"] == "baseline-1"
    assert (
        binding["previous_baseline_state_hash"]
        == proposal["baseline_state_hash"]
    )
    assert binding["next_baseline_id"] == "baseline-2"
    assert (
        binding["next_baseline_state_hash"]
        == proposal["candidate_baseline_hash"]
    )
    assert binding["corrected_claim_ids"] == ["shape"]
    assert binding["condition_ids"] == [
        "color-preserved",
        "shape-corrected",
    ]
    assert binding["newly_solved"] == ["shape-corrected"]
    assert binding["preserved"] == ["color-preserved"]
    assert binding["transition_candidate_created"] is True


def test_reuses_existing_baseline_transition_candidate_builder() -> None:
    verification, binding = _binding()
    gate = verification["proposal"]["promotion"]["gate"]

    expected = build_baseline_transition_candidate(
        promotion_gate=gate,
        next_baseline_id="baseline-2",
        next_baseline_state_hash=verification["candidate_baseline_hash"],
    )

    assert binding["baseline_transition_candidate"] == expected
    assert (
        binding["authorization_target_sha256"]
        == expected["candidate_hash"]
    )
    assert binding["authorization_action"] == (
        ACTION_VERIFIED_CLAIM_CORRECTION_PROMOTION
    )


def test_exact_target_is_compatible_with_existing_authorizer() -> None:
    verification, binding = _binding()
    gate = verification["proposal"]["promotion"]["gate"]

    authorization = build_operational_authorization(
        authorization_id="authorization-1",
        actor_id="external-operator",
        action=binding["authorization_action"],
        target_sha256=binding["authorization_target_sha256"],
        approval_reference="operator-review-transition-1",
    )
    transition = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=binding["baseline_transition_candidate"],
        authorization=authorization,
        authorization_action=binding["authorization_action"],
    )

    assert transition["status"] == "AUTHORIZED"
    assert transition["candidate_hash"] == (
        binding["authorization_target_sha256"]
    )
    assert transition["next_baseline_id"] == "baseline-2"
    assert transition["next_baseline_state_hash"] == (
        verification["candidate_baseline_hash"]
    )
    assert transition["accepted"] is False
    assert transition["truth_claimed"] is False
    assert transition["write_authority"] == "NONE"
    assert transition["execution_authority"] == "NONE"
    assert transition["promotion_authority"] == "EXACT_TARGET_ONLY"


def test_valid_binding_regenerates_exactly() -> None:
    _, binding = _binding()

    assert (
        validate_verified_claim_correction_transition_candidate(binding)
        is True
    )


def test_logically_identical_inputs_are_deterministic() -> None:
    verification = _build_verification()

    first = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-2",
    )
    second = build_verified_claim_correction_transition_candidate(
        verification=deepcopy(verification),
        next_baseline_id="baseline-2",
    )

    assert first == second
    assert first["binding_hash"] == second["binding_hash"]


def test_different_next_baseline_changes_exact_target() -> None:
    verification = _build_verification()

    first = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-2",
    )
    second = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-3",
    )

    assert (
        first["authorization_target_sha256"]
        != second["authorization_target_sha256"]
    )
    assert first["binding_hash"] != second["binding_hash"]


@pytest.mark.parametrize(
    "invalid_id",
    [
        "",
        "   ",
        None,
        1,
    ],
)
def test_next_baseline_identity_must_be_nonempty_text(invalid_id) -> None:
    verification = _build_verification()

    with pytest.raises(VerifiedClaimCorrectionTransitionError):
        build_verified_claim_correction_transition_candidate(
            verification=verification,
            next_baseline_id=invalid_id,
        )


def test_insufficient_improvement_cannot_create_transition_candidate() -> None:
    verification = _build_verification(after_target=False)

    with pytest.raises(
        VerifiedClaimCorrectionTransitionError,
        match="not ready to request authorization",
    ):
        build_verified_claim_correction_transition_candidate(
            verification=verification,
            next_baseline_id="baseline-2",
        )


def test_regression_cannot_create_transition_candidate() -> None:
    verification = _build_verification(after_guard=False)

    with pytest.raises(
        VerifiedClaimCorrectionTransitionError,
        match="not ready to request authorization",
    ):
        build_verified_claim_correction_transition_candidate(
            verification=verification,
            next_baseline_id="baseline-2",
        )


def test_unavailable_evidence_cannot_create_transition_candidate() -> None:
    verification = _build_verification(
        after_target_status="UNAVAILABLE"
    )

    with pytest.raises(
        VerifiedClaimCorrectionTransitionError,
        match="not ready to request authorization",
    ):
        build_verified_claim_correction_transition_candidate(
            verification=verification,
            next_baseline_id="baseline-2",
        )


def test_forged_verification_fails_closed() -> None:
    verification = _build_verification()
    verification["candidate_baseline_hash"] = "0" * 64

    with pytest.raises(
        VerifiedClaimCorrectionTransitionError,
        match="verification is invalid",
    ):
        build_verified_claim_correction_transition_candidate(
            verification=verification,
            next_baseline_id="baseline-2",
        )


def test_input_verification_is_not_mutated() -> None:
    verification = _build_verification()
    original = deepcopy(verification)

    build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-2",
    )

    assert verification == original


def test_authorization_and_transition_remain_absent() -> None:
    _, binding = _binding()

    assert binding["transition_candidate_created"] is True
    assert binding["authorization_requested"] is False
    assert binding["authorization_consumed"] is False
    assert binding["transition_created"] is False
    assert binding["correction_applied"] is False
    assert binding["supersession_performed"] is False
    assert binding["accepted"] is False
    assert binding["truth_claimed"] is False
    assert binding["write_authority"] == "NONE"
    assert binding["execution_authority"] == "NONE"
    assert binding["canonical_mutation"] is False


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("verification_hash", "0" * 64),
        ("proposal_hash", "0" * 64),
        ("promotion_gate_id", "0" * 64),
        ("next_baseline_state_hash", "0" * 64),
        ("authorization_target_sha256", "0" * 64),
        ("transition_candidate_created", False),
        ("authorization_requested", True),
        ("authorization_consumed", True),
        ("transition_created", True),
        ("correction_applied", True),
        ("supersession_performed", True),
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
        ("canonical_mutation", True),
        ("binding_hash", "0" * 64),
    ],
)
def test_validator_rejects_tampering(field, forged_value) -> None:
    _, binding = _binding()
    binding[field] = forged_value

    with pytest.raises(
        VerifiedClaimCorrectionTransitionError,
        match="binding does not match its verified correction",
    ):
        validate_verified_claim_correction_transition_candidate(binding)