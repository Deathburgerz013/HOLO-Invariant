from copy import deepcopy

import pytest

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
    EvidenceBoundClaimCorrectionVerificationError,
    STATUS_INSUFFICIENT,
    STATUS_REGRESSION,
    STATUS_UNRESOLVED,
    STATUS_VERIFIED,
    VERIFY_ACTION,
    validate_evidence_bound_claim_correction_verification,
    verify_evidence_bound_claim_correction,
)
from holosim.hook_contract import build_hook_request, build_hook_result


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
    action=VERIFY_ACTION,
    reference=None,
    payload=None,
    evidence=None,
):
    if reference is None:
        reference = condition_id
    if payload is None:
        payload = {
            "condition_id": condition_id,
            "claim_set_hash": claim_set_hash,
        }

    request = build_hook_request(
        hook_id=f"condition-verifier-{condition_id}",
        action=action,
        reference=reference,
        payload=payload,
    )

    if evidence is None:
        if status == "OBSERVED":
            evidence = {"condition_satisfied": satisfied}
        else:
            evidence = {"diagnostic": status.lower()}

    result = build_hook_result(
        request=request,
        status=status,
        evidence=evidence,
    )
    return {
        "request": request,
        "result": result,
    }


def _verification_inputs(
    *,
    before_target=False,
    after_target=True,
    before_guard=True,
    after_guard=True,
    before_target_status="OBSERVED",
    after_target_status="OBSERVED",
    before_guard_status="OBSERVED",
    after_guard_status="OBSERVED",
):
    proposal = _build_proposal()
    before_evidence = {
        "shape-corrected": _condition_bundle(
            condition_id="shape-corrected",
            claim_set_hash=proposal["baseline_state_hash"],
            satisfied=before_target,
            status=before_target_status,
        ),
        "color-preserved": _condition_bundle(
            condition_id="color-preserved",
            claim_set_hash=proposal["baseline_state_hash"],
            satisfied=before_guard,
            status=before_guard_status,
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
            status=after_guard_status,
        ),
    }
    return proposal, before_evidence, after_evidence


def _verify(**overrides):
    proposal, before_evidence, after_evidence = _verification_inputs(
        **overrides
    )
    verification = verify_evidence_bound_claim_correction(
        proposal=proposal,
        claim_conditions={"shape": ["shape-corrected"]},
        before_evidence=before_evidence,
        after_evidence=after_evidence,
    )
    return proposal, before_evidence, after_evidence, verification


def test_verified_improvement_is_ready_only_to_request_authorization() -> None:
    proposal, _, _, verification = _verify()

    assert verification["status"] == STATUS_VERIFIED
    assert verification["proposal_hash"] == proposal["proposal_hash"]
    assert (
        verification["baseline_state_hash"]
        == proposal["baseline_state_hash"]
    )
    assert (
        verification["candidate_baseline_hash"]
        == proposal["candidate_baseline_hash"]
    )
    assert verification["corrected_claim_ids"] == ["shape"]
    assert verification["claim_conditions"] == {
        "shape": ["shape-corrected"]
    }
    assert verification["condition_ids"] == [
        "color-preserved",
        "shape-corrected",
    ]
    assert verification["guard_condition_ids"] == ["color-preserved"]
    assert verification["newly_solved"] == ["shape-corrected"]
    assert verification["preserved"] == ["color-preserved"]
    assert verification["regressed"] == []
    assert verification["unresolved"] == []
    assert verification["blocking_unavailable"] == []
    assert verification["unverified_claim_ids"] == []
    assert verification["verification_complete"] is True
    assert verification["verified_to_request_authorization"] is True
    assert verification["authorization_requested"] is False
    assert verification["transition_created"] is False


def test_uses_existing_solution_coverage_evaluator() -> None:
    _, _, _, verification = _verify()

    assert verification["coverage"] == {
        "newly_solved": ["shape-corrected"],
        "preserved": ["color-preserved"],
        "regressed": [],
        "unresolved": [],
        "before_solved_count": 1,
        "after_solved_count": 2,
        "net_solved_gain": 1,
        "closure_ready": True,
        "accepted": False,
        "write_authority": "NONE",
    }


def test_valid_verification_regenerates_exactly() -> None:
    _, _, _, verification = _verify()

    assert (
        validate_evidence_bound_claim_correction_verification(
            verification
        )
        is True
    )


def test_target_must_be_newly_solved_not_merely_preserved() -> None:
    _, _, _, verification = _verify(
        before_target=True,
        after_target=True,
    )

    assert verification["coverage"]["closure_ready"] is True
    assert verification["newly_solved"] == []
    assert verification["preserved"] == [
        "color-preserved",
        "shape-corrected",
    ]
    assert verification["unverified_claim_ids"] == ["shape"]
    assert verification["status"] == STATUS_INSUFFICIENT
    assert verification["verification_complete"] is False
    assert verification["verified_to_request_authorization"] is False


def test_still_unsolved_target_is_insufficient() -> None:
    _, _, _, verification = _verify(
        before_target=False,
        after_target=False,
    )

    assert verification["unresolved"] == ["shape-corrected"]
    assert verification["unverified_claim_ids"] == ["shape"]
    assert verification["status"] == STATUS_INSUFFICIENT
    assert verification["verification_complete"] is False


def test_guard_regression_blocks_verification() -> None:
    _, _, _, verification = _verify(
        before_guard=True,
        after_guard=False,
    )

    assert verification["newly_solved"] == ["shape-corrected"]
    assert verification["regressed"] == ["color-preserved"]
    assert verification["status"] == STATUS_REGRESSION
    assert verification["verification_complete"] is False
    assert verification["verified_to_request_authorization"] is False


@pytest.mark.parametrize(
    ("phase", "status"),
    [
        ("before", "UNAVAILABLE"),
        ("before", "FAILED"),
        ("after", "UNAVAILABLE"),
        ("after", "FAILED"),
    ],
)
def test_unavailable_or_failed_target_evidence_is_unresolved(
    phase,
    status,
) -> None:
    overrides = {}
    overrides[f"{phase}_target_status"] = status

    _, _, _, verification = _verify(**overrides)

    assert verification["status"] == STATUS_UNRESOLVED
    assert verification["unresolved"] == ["shape-corrected"]
    assert verification["unverified_claim_ids"] == ["shape"]
    assert len(verification["blocking_unavailable"]) == 1
    blocker = verification["blocking_unavailable"][0]
    assert blocker["condition_id"] == "shape-corrected"
    assert blocker["phase"] == phase.upper()
    assert blocker["status"] == status
    assert verification["verification_complete"] is False


def test_unavailable_guard_also_blocks_verification() -> None:
    _, _, _, verification = _verify(
        after_guard_status="UNAVAILABLE",
    )

    assert verification["newly_solved"] == ["shape-corrected"]
    assert verification["unresolved"] == ["color-preserved"]
    assert verification["status"] == STATUS_UNRESOLVED
    assert verification["verified_to_request_authorization"] is False


def test_failed_or_unavailable_result_cannot_claim_satisfaction() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()
    after_evidence["shape-corrected"] = _condition_bundle(
        condition_id="shape-corrected",
        claim_set_hash=proposal["candidate_baseline_hash"],
        status="UNAVAILABLE",
        evidence={"condition_satisfied": True},
    )

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="cannot claim satisfaction",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": ["shape-corrected"]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_condition_satisfied_must_be_boolean() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()
    after_evidence["shape-corrected"] = _condition_bundle(
        condition_id="shape-corrected",
        claim_set_hash=proposal["candidate_baseline_hash"],
        evidence={"condition_satisfied": 1},
    )

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="condition_satisfied must be a boolean",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": ["shape-corrected"]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_before_evidence_must_bind_original_baseline_hash() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()
    before_evidence["shape-corrected"] = _condition_bundle(
        condition_id="shape-corrected",
        claim_set_hash=proposal["candidate_baseline_hash"],
        satisfied=False,
    )

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="bound to the wrong claim set",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": ["shape-corrected"]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_after_evidence_must_bind_candidate_hash() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()
    after_evidence["shape-corrected"] = _condition_bundle(
        condition_id="shape-corrected",
        claim_set_hash=proposal["baseline_state_hash"],
        satisfied=True,
    )

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="bound to the wrong claim set",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": ["shape-corrected"]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_condition_request_requires_exact_action() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()
    after_evidence["shape-corrected"] = _condition_bundle(
        condition_id="shape-corrected",
        claim_set_hash=proposal["candidate_baseline_hash"],
        satisfied=True,
        action="apply-correction",
    )

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="uses the wrong action",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": ["shape-corrected"]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_condition_request_reference_must_match_identity() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()
    after_evidence["shape-corrected"] = _condition_bundle(
        condition_id="shape-corrected",
        claim_set_hash=proposal["candidate_baseline_hash"],
        satisfied=True,
        reference="another-condition",
    )

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="reference does not match condition id",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": ["shape-corrected"]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_before_and_after_condition_sets_must_match() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()
    after_evidence.pop("color-preserved")

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="same condition ids",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": ["shape-corrected"]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_every_claim_condition_requires_evidence() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="every claim condition must have before and after evidence",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": ["missing-condition"]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_claim_condition_keys_must_match_corrected_claims() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="exactly match corrected claim ids",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={
                "color": ["color-preserved"],
                "shape": ["shape-corrected"],
            },
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_duplicate_condition_for_one_claim_fails_closed() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="duplicate condition id",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={
                "shape": [
                    "shape-corrected",
                    "shape-corrected",
                ]
            },
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


@pytest.mark.parametrize(
    "invalid_conditions",
    [
        [],
        (),
        "",
        None,
    ],
)
def test_each_corrected_claim_requires_conditions(
    invalid_conditions,
) -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="one or more conditions",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": invalid_conditions},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


@pytest.mark.parametrize(
    "invalid_id",
    [
        "",
        "   ",
        " padded ",
        1,
    ],
)
def test_invalid_condition_identity_fails_closed(invalid_id) -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()

    with pytest.raises(EvidenceBoundClaimCorrectionVerificationError):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": [invalid_id]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_forged_proposal_fails_closed() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()
    proposal["candidate_baseline_hash"] = "0" * 64

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="proposal is invalid",
    ):
        verify_evidence_bound_claim_correction(
            proposal=proposal,
            claim_conditions={"shape": ["shape-corrected"]},
            before_evidence=before_evidence,
            after_evidence=after_evidence,
        )


def test_logically_identical_input_order_is_deterministic() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()

    first = verify_evidence_bound_claim_correction(
        proposal=proposal,
        claim_conditions={"shape": ["shape-corrected"]},
        before_evidence=before_evidence,
        after_evidence=after_evidence,
    )
    second = verify_evidence_bound_claim_correction(
        proposal=proposal,
        claim_conditions={"shape": ("shape-corrected",)},
        before_evidence=dict(reversed(list(before_evidence.items()))),
        after_evidence=dict(reversed(list(after_evidence.items()))),
    )

    assert first == second
    assert first["verification_hash"] == second["verification_hash"]


def test_inputs_are_not_mutated() -> None:
    proposal, before_evidence, after_evidence = _verification_inputs()
    claim_conditions = {"shape": ["shape-corrected"]}

    original_proposal = deepcopy(proposal)
    original_conditions = deepcopy(claim_conditions)
    original_before = deepcopy(before_evidence)
    original_after = deepcopy(after_evidence)

    verify_evidence_bound_claim_correction(
        proposal=proposal,
        claim_conditions=claim_conditions,
        before_evidence=before_evidence,
        after_evidence=after_evidence,
    )

    assert proposal == original_proposal
    assert claim_conditions == original_conditions
    assert before_evidence == original_before
    assert after_evidence == original_after


def test_authority_and_mutation_remain_absent() -> None:
    _, _, _, verification = _verify()

    assert verification["authorization_requested"] is False
    assert verification["transition_created"] is False
    assert verification["correction_applied"] is False
    assert verification["supersession_performed"] is False
    assert verification["accepted"] is False
    assert verification["truth_claimed"] is False
    assert verification["write_authority"] == "NONE"
    assert verification["execution_authority"] == "NONE"
    assert verification["canonical_mutation"] is False


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("verification_complete", False),
        ("verified_to_request_authorization", False),
        ("authorization_requested", True),
        ("transition_created", True),
        ("correction_applied", True),
        ("supersession_performed", True),
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
        ("canonical_mutation", True),
        ("verification_hash", "0" * 64),
    ],
)
def test_validator_rejects_tampering(field, forged_value) -> None:
    _, _, _, verification = _verify()
    verification[field] = forged_value

    with pytest.raises(
        EvidenceBoundClaimCorrectionVerificationError,
        match="verification does not match its source evidence",
    ):
        validate_evidence_bound_claim_correction_verification(
            verification
        )