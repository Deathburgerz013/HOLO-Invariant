from copy import deepcopy

import pytest

from holosim.authorized_baseline_transition import (
    authorize_baseline_transition,
)
from holosim.authorized_verified_claim_correction_transition import (
    STATUS_AUTHORIZED,
    AuthorizedVerifiedClaimCorrectionTransitionError,
    authorize_verified_claim_correction_transition,
    validate_authorized_verified_claim_correction_transition,
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
    ACTION_SERVICE_APPEND,
    ACTION_VERIFIED_CLAIM_CORRECTION_PROMOTION,
    build_operational_authorization,
)
from holosim.verified_claim_correction_transition import (
    build_verified_claim_correction_transition_candidate,
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
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"condition_satisfied": satisfied},
    )
    return {"request": request, "result": result}


def _build_binding():
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
            satisfied=True,
        ),
        "color-preserved": _condition_bundle(
            condition_id="color-preserved",
            claim_set_hash=proposal["candidate_baseline_hash"],
            satisfied=True,
        ),
    }
    verification = verify_evidence_bound_claim_correction(
        proposal=proposal,
        claim_conditions={"shape": ["shape-corrected"]},
        before_evidence=before_evidence,
        after_evidence=after_evidence,
    )
    binding = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-2",
    )
    return verification, binding


def _authorization(
    binding,
    *,
    authorization_id="authorization-1",
    actor_id="external-operator",
    action=None,
    target=None,
):
    return build_operational_authorization(
        authorization_id=authorization_id,
        actor_id=actor_id,
        action=action or binding["authorization_action"],
        target_sha256=target or binding["authorization_target_sha256"],
        approval_reference="operator-review-transition-1",
    )


def _receipt():
    verification, binding = _build_binding()
    authorization = _authorization(binding)
    receipt = authorize_verified_claim_correction_transition(
        transition_binding=binding,
        authorization=authorization,
    )
    return verification, binding, authorization, receipt


def test_authorizes_only_the_complete_verified_transition_binding() -> None:
    verification, binding, authorization, receipt = _receipt()

    assert receipt["status"] == STATUS_AUTHORIZED
    assert receipt["transition_binding"] == binding
    assert receipt["binding_hash"] == binding["binding_hash"]
    assert receipt["verification_hash"] == verification["verification_hash"]
    assert receipt["proposal_hash"] == verification["proposal"]["proposal_hash"]
    assert receipt["operational_authorization"] == authorization
    assert receipt["authorization_hash"] == authorization["authorization_hash"]
    assert receipt["authorized_by_actor_id"] == "external-operator"


def test_reuses_existing_baseline_transition_authorizer() -> None:
    _, binding, authorization, receipt = _receipt()
    gate = binding["verification"]["proposal"]["promotion"]["gate"]

    expected = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=binding["baseline_transition_candidate"],
        authorization=authorization,
        authorization_action=binding["authorization_action"],
    )

    assert receipt["authorized_baseline_transition"] == expected
    assert receipt["transition_id"] == expected["transition_id"]
    assert receipt["candidate_hash"] == expected["candidate_hash"]


def test_preserves_exact_verified_successor_identity() -> None:
    verification, binding, _, receipt = _receipt()

    assert receipt["previous_baseline_id"] == "baseline-1"
    assert receipt["next_baseline_id"] == "baseline-2"
    assert receipt["next_baseline_state_hash"] == (
        verification["candidate_baseline_hash"]
    )
    assert receipt["candidate_hash"] == (
        binding["authorization_target_sha256"]
    )


def test_wrong_authorization_target_fails_closed() -> None:
    _, binding = _build_binding()
    authorization = _authorization(binding, target="0" * 64)

    with pytest.raises(
        AuthorizedVerifiedClaimCorrectionTransitionError,
        match="authorization target does not match",
    ):
        authorize_verified_claim_correction_transition(
            transition_binding=binding,
            authorization=authorization,
        )


def test_wrong_authorization_action_fails_closed() -> None:
    _, binding = _build_binding()
    authorization = _authorization(
        binding,
        action=ACTION_SERVICE_APPEND,
    )

    with pytest.raises(
        AuthorizedVerifiedClaimCorrectionTransitionError,
        match="authorization action does not match",
    ):
        authorize_verified_claim_correction_transition(
            transition_binding=binding,
            authorization=authorization,
        )


def test_tampered_transition_binding_fails_before_authorization() -> None:
    _, binding = _build_binding()
    authorization = _authorization(binding)
    binding["verification_hash"] = "0" * 64

    with pytest.raises(
        AuthorizedVerifiedClaimCorrectionTransitionError,
        match="transition binding is invalid",
    ):
        authorize_verified_claim_correction_transition(
            transition_binding=binding,
            authorization=authorization,
        )


def test_substituted_candidate_fails_before_authorization() -> None:
    _, binding = _build_binding()
    authorization = _authorization(binding)
    binding["baseline_transition_candidate"]["next_baseline_id"] = (
        "baseline-substituted"
    )

    with pytest.raises(
        AuthorizedVerifiedClaimCorrectionTransitionError,
        match="transition binding is invalid",
    ):
        authorize_verified_claim_correction_transition(
            transition_binding=binding,
            authorization=authorization,
        )


def test_forged_authorization_fails_closed() -> None:
    _, binding = _build_binding()
    authorization = _authorization(binding)
    authorization["actor_id"] = "forged-actor"

    with pytest.raises(
        AuthorizedVerifiedClaimCorrectionTransitionError,
        match="authorization is invalid",
    ):
        authorize_verified_claim_correction_transition(
            transition_binding=binding,
            authorization=authorization,
        )


@pytest.mark.parametrize("invalid", [None, [], (), "binding"])
def test_transition_binding_must_be_plain_dictionary(invalid) -> None:
    _, binding = _build_binding()
    authorization = _authorization(binding)

    with pytest.raises(
        AuthorizedVerifiedClaimCorrectionTransitionError,
        match="transition_binding must be a plain dictionary",
    ):
        authorize_verified_claim_correction_transition(
            transition_binding=invalid,
            authorization=authorization,
        )


@pytest.mark.parametrize("invalid", [None, [], (), "authorization"])
def test_authorization_must_be_plain_dictionary(invalid) -> None:
    _, binding = _build_binding()

    with pytest.raises(
        AuthorizedVerifiedClaimCorrectionTransitionError,
        match="authorization must be a plain dictionary",
    ):
        authorize_verified_claim_correction_transition(
            transition_binding=binding,
            authorization=invalid,
        )


def test_inputs_are_not_mutated() -> None:
    _, binding = _build_binding()
    authorization = _authorization(binding)
    original_binding = deepcopy(binding)
    original_authorization = deepcopy(authorization)

    authorize_verified_claim_correction_transition(
        transition_binding=binding,
        authorization=authorization,
    )

    assert binding == original_binding
    assert authorization == original_authorization


def test_logically_identical_inputs_are_deterministic() -> None:
    _, binding = _build_binding()
    authorization = _authorization(binding)

    first = authorize_verified_claim_correction_transition(
        transition_binding=binding,
        authorization=authorization,
    )
    second = authorize_verified_claim_correction_transition(
        transition_binding=deepcopy(binding),
        authorization=deepcopy(authorization),
    )

    assert first == second
    assert first["authorization_binding_hash"] == (
        second["authorization_binding_hash"]
    )


def test_different_authorization_changes_receipt_identity() -> None:
    _, binding = _build_binding()
    first_authorization = _authorization(binding)
    second_authorization = _authorization(
        binding,
        authorization_id="authorization-2",
    )

    first = authorize_verified_claim_correction_transition(
        transition_binding=binding,
        authorization=first_authorization,
    )
    second = authorize_verified_claim_correction_transition(
        transition_binding=binding,
        authorization=second_authorization,
    )

    assert first["authorization_hash"] != second["authorization_hash"]
    assert first["transition_id"] != second["transition_id"]
    assert first["authorization_binding_hash"] != (
        second["authorization_binding_hash"]
    )


def test_valid_receipt_regenerates_exactly() -> None:
    _, _, _, receipt = _receipt()

    assert (
        validate_authorized_verified_claim_correction_transition(receipt)
        is True
    )


def test_persistence_and_application_remain_absent() -> None:
    _, _, _, receipt = _receipt()

    assert receipt["authorization_requested"] is False
    assert receipt["authorization_validated"] is True
    assert receipt["authorization_consumed"] is False
    assert receipt["transition_created"] is True
    assert receipt["transition_persisted"] is False
    assert receipt["correction_applied"] is False
    assert receipt["supersession_performed"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["promotion_authority"] == "EXACT_TARGET_ONLY"
    assert receipt["canonical_mutation"] is False


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("binding_hash", "0" * 64),
        ("verification_hash", "0" * 64),
        ("proposal_hash", "0" * 64),
        ("authorization_hash", "0" * 64),
        ("authorized_by_actor_id", "forged-actor"),
        ("transition_id", "0" * 64),
        ("candidate_hash", "0" * 64),
        ("next_baseline_state_hash", "0" * 64),
        ("status", "FORGED"),
        ("authorization_requested", True),
        ("authorization_validated", False),
        ("authorization_consumed", True),
        ("transition_created", False),
        ("transition_persisted", True),
        ("correction_applied", True),
        ("supersession_performed", True),
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
        ("promotion_authority", "GENERAL"),
        ("canonical_mutation", True),
        ("authorization_binding_hash", "0" * 64),
    ],
)
def test_validator_rejects_top_level_tampering(
    field,
    forged_value,
) -> None:
    _, _, _, receipt = _receipt()
    receipt[field] = forged_value

    with pytest.raises(
        AuthorizedVerifiedClaimCorrectionTransitionError,
        match="receipt does not match",
    ):
        validate_authorized_verified_claim_correction_transition(receipt)


def test_validator_rejects_nested_binding_tampering() -> None:
    _, _, _, receipt = _receipt()
    receipt["transition_binding"]["verification_hash"] = "0" * 64

    with pytest.raises(AuthorizedVerifiedClaimCorrectionTransitionError):
        validate_authorized_verified_claim_correction_transition(receipt)


def test_validator_rejects_nested_authorization_tampering() -> None:
    _, _, _, receipt = _receipt()
    receipt["operational_authorization"]["actor_id"] = "forged-actor"

    with pytest.raises(AuthorizedVerifiedClaimCorrectionTransitionError):
        validate_authorized_verified_claim_correction_transition(receipt)


def test_validator_rejects_nested_transition_tampering() -> None:
    _, _, _, receipt = _receipt()
    receipt["authorized_baseline_transition"]["transition_id"] = "0" * 64

    with pytest.raises(
        AuthorizedVerifiedClaimCorrectionTransitionError,
        match="receipt does not match",
    ):
        validate_authorized_verified_claim_correction_transition(receipt)


def test_action_routes_exact_verified_correction_promotion() -> None:
    _, binding, authorization, receipt = _receipt()

    assert binding["authorization_action"] == (
        ACTION_VERIFIED_CLAIM_CORRECTION_PROMOTION
    )
    assert authorization["action"] == (
        ACTION_VERIFIED_CLAIM_CORRECTION_PROMOTION
    )
    assert authorization["target_sha256"] == receipt["candidate_hash"]
