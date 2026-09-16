from copy import deepcopy

import pytest

from holosim.authorized_baseline_transition import (
    authorize_baseline_transition,
    build_baseline_transition_candidate,
)
from holosim.authorized_verified_claim_correction_transition import (
    authorize_verified_claim_correction_transition,
)
from holosim.baseline_observation_compare import (
    FINDING_CORRECTION,
    FINDING_SUPPORT,
    build_baseline_observation,
    compare_baseline_observations,
)
from holosim.baseline_promotion_gate import evaluate_baseline_promotion
from holosim.bounded_claim_correction import propose_bounded_claim_correction
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
from holosim.persistent_baseline_transition import (
    PersistentBaselineTransitionError,
    PersistentBaselineTransitionStore,
    validate_persisted_verified_claim_correction_read,
)
from holosim.post_persistence_verified_claim_reobservation import (
    STATUS_CHANGE,
    STATUS_CONFIRMED,
    STATUS_UNRESOLVED,
    PostPersistenceVerifiedClaimReobservationError,
    reobserve_persisted_verified_claim_correction,
    validate_post_persistence_verified_claim_reobservation,
)
from holosim.typed_operational_authorization import (
    ACTION_BASELINE_PROMOTION,
    build_operational_authorization,
)
from holosim.verified_claim_correction_transition import (
    build_verified_claim_correction_transition_candidate,
)


def _proposal():
    claims = {
        "color": {"value": "blue"},
        "shape": {"value": "flat"},
    }
    replacement = {"shape": {"value": "round"}}
    baseline_hash = stable_hash(claims)
    findings = {
        "color": FINDING_SUPPORT,
        "shape": FINDING_CORRECTION,
    }
    observations = []
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
        observations.append(
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
        observations[0], observations[1]
    )
    promotion = evaluate_evidence_bound_baseline_promotion(
        comparison=comparison
    )
    return propose_bounded_claim_correction(
        comparison=comparison,
        promotion=promotion,
        current_claims=claims,
        proposed_replacements=replacement,
    )


def _condition_bundle(
    *,
    condition_id,
    claim_set_hash,
    satisfied,
    hook_prefix,
    status="OBSERVED",
):
    request = build_hook_request(
        hook_id=f"{hook_prefix}-{condition_id}",
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
    return {"request": request, "result": result}


def _evidence(
    proposal,
    *,
    phase,
    hook_prefix,
    shape=True,
    color=True,
    shape_status="OBSERVED",
    color_status="OBSERVED",
):
    claim_set_hash = (
        proposal["baseline_state_hash"]
        if phase == "before"
        else proposal["candidate_baseline_hash"]
    )
    return {
        "shape-corrected": _condition_bundle(
            condition_id="shape-corrected",
            claim_set_hash=claim_set_hash,
            satisfied=shape,
            hook_prefix=hook_prefix,
            status=shape_status,
        ),
        "color-preserved": _condition_bundle(
            condition_id="color-preserved",
            claim_set_hash=claim_set_hash,
            satisfied=color,
            hook_prefix=hook_prefix,
            status=color_status,
        ),
    }


def _authorized_correction():
    proposal = _proposal()
    verification = verify_evidence_bound_claim_correction(
        proposal=proposal,
        claim_conditions={"shape": ["shape-corrected"]},
        before_evidence=_evidence(
            proposal,
            phase="before",
            hook_prefix="original-before",
            shape=False,
            color=True,
        ),
        after_evidence=_evidence(
            proposal,
            phase="after",
            hook_prefix="original-after",
            shape=True,
            color=True,
        ),
    )
    binding = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-2",
    )
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
    return proposal, authorized


def _persisted(tmp_path):
    proposal, authorized = _authorized_correction()
    store = PersistentBaselineTransitionStore(
        tmp_path / "baseline-transitions.jsonl",
        initial_baseline_id="baseline-1",
        initial_baseline_state_hash=proposal["baseline_state_hash"],
    )
    commit = store.commit_verified_claim_correction(
        authorized_correction=authorized
    )
    return proposal, authorized, store, commit


def _fresh(proposal, **kwargs):
    return _evidence(
        proposal,
        phase="after",
        hook_prefix=kwargs.pop("hook_prefix", "fresh-after"),
        **kwargs,
    )


def _advance_with_generic_transition(store, *, previous_hash):
    left = build_baseline_observation(
        observer_id="later-left",
        baseline_id="baseline-2",
        baseline_state_hash=previous_hash,
        findings={"later-claim": "EXTENSION"},
    )
    right = build_baseline_observation(
        observer_id="later-right",
        baseline_id="baseline-2",
        baseline_state_hash=previous_hash,
        findings={"later-claim": "EXTENSION"},
    )
    comparison = compare_baseline_observations(left, right)
    gate = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references={"later-claim": "later-justification"},
    )
    candidate = build_baseline_transition_candidate(
        promotion_gate=gate,
        next_baseline_id="baseline-3",
        next_baseline_state_hash=stable_hash({"later": "state"}),
    )
    authorization = build_operational_authorization(
        authorization_id="authorization-2",
        actor_id="external-operator",
        action=ACTION_BASELINE_PROMOTION,
        target_sha256=candidate["candidate_hash"],
        approval_reference="operator-review-2",
    )
    transition = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=candidate,
        authorization=authorization,
    )
    store.commit(transition=transition, authorization=authorization)


def test_store_reads_one_verified_record_from_verified_chain(tmp_path):
    _, authorized, store, commit = _persisted(tmp_path)

    read = store.read_verified_claim_correction(record_id=commit["record_id"])

    assert validate_persisted_verified_claim_correction_read(read) is True
    assert read["record"]["authorized_correction"] == authorized
    assert read["record_id"] == commit["record_id"]
    assert read["record_is_current_head"] is True
    assert read["transition_index"] == 1
    assert read["transition_count"] == 1
    assert read["read_only"] is True
    assert read["canonical_mutation"] is False


def test_matching_fresh_evidence_confirms_reobservation(tmp_path):
    proposal, authorized, store, commit = _persisted(tmp_path)

    receipt = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=_fresh(proposal),
    )

    assert receipt["status"] == STATUS_CONFIRMED
    assert receipt["exact_outcome_match"] is True
    assert receipt["verified_correction_still_supported"] is True
    assert receipt["reobservation_complete"] is True
    assert receipt["changed_condition_ids"] == []
    assert receipt["unresolved_condition_ids"] == []
    assert receipt["authorization_binding_hash"] == (
        authorized["authorization_binding_hash"]
    )


def test_changed_owned_condition_is_observed_not_hidden(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)

    receipt = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=_fresh(proposal, shape=False),
    )

    assert receipt["status"] == STATUS_CHANGE
    assert receipt["exact_outcome_match"] is False
    assert receipt["verified_correction_still_supported"] is False
    assert receipt["changed_condition_ids"] == ["shape-corrected"]
    assert receipt["outcome_comparison"]["regressed"] == [
        "shape-corrected"
    ]


def test_unavailable_fresh_condition_remains_unresolved(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)

    receipt = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=_fresh(
            proposal,
            shape_status="UNAVAILABLE",
        ),
    )

    assert receipt["status"] == STATUS_UNRESOLVED
    assert receipt["reobservation_complete"] is False
    assert receipt["exact_outcome_match"] is False
    assert receipt["unresolved_condition_ids"] == ["shape-corrected"]


def test_persisted_after_evidence_cannot_be_reused(tmp_path):
    _, authorized, store, commit = _persisted(tmp_path)
    original_after = authorized["transition_binding"]["verification"][
        "after_evidence"
    ]

    with pytest.raises(
        PostPersistenceVerifiedClaimReobservationError,
        match="reuses persisted after evidence",
    ):
        reobserve_persisted_verified_claim_correction(
            store=store,
            record_id=commit["record_id"],
            fresh_after_evidence=original_after,
        )


def test_reobservation_is_rejected_after_later_transition(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)
    _advance_with_generic_transition(
        store,
        previous_hash=proposal["candidate_baseline_hash"],
    )

    with pytest.raises(
        PostPersistenceVerifiedClaimReobservationError,
        match="no longer the current baseline head",
    ):
        reobserve_persisted_verified_claim_correction(
            store=store,
            record_id=commit["record_id"],
            fresh_after_evidence=_fresh(proposal),
        )


def test_unknown_record_fails_closed(tmp_path):
    proposal, _, store, _ = _persisted(tmp_path)

    with pytest.raises(
        PostPersistenceVerifiedClaimReobservationError,
        match="record was not found",
    ):
        reobserve_persisted_verified_claim_correction(
            store=store,
            record_id="0" * 64,
            fresh_after_evidence=_fresh(proposal),
        )


def test_wrong_store_type_fails_closed(tmp_path):
    proposal = _proposal()
    with pytest.raises(
        PostPersistenceVerifiedClaimReobservationError,
        match="store must be",
    ):
        reobserve_persisted_verified_claim_correction(
            store=tmp_path,
            record_id="0" * 64,
            fresh_after_evidence=_fresh(proposal),
        )


def test_missing_fresh_condition_fails_closed(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)
    fresh = _fresh(proposal)
    fresh.pop("color-preserved")

    with pytest.raises(
        PostPersistenceVerifiedClaimReobservationError,
        match="fresh re-observation evidence is invalid",
    ):
        reobserve_persisted_verified_claim_correction(
            store=store,
            record_id=commit["record_id"],
            fresh_after_evidence=fresh,
        )


def test_wrong_claim_set_binding_fails_closed(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)
    fresh = _fresh(proposal)
    fresh["shape-corrected"]["request"]["payload"][
        "claim_set_hash"
    ] = proposal["baseline_state_hash"]

    with pytest.raises(
        PostPersistenceVerifiedClaimReobservationError,
        match="fresh re-observation evidence is invalid",
    ):
        reobserve_persisted_verified_claim_correction(
            store=store,
            record_id=commit["record_id"],
            fresh_after_evidence=fresh,
        )


def test_reobservation_does_not_mutate_inputs_or_store(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)
    fresh = _fresh(proposal)
    original = deepcopy(fresh)
    head = store.current_head()

    reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=fresh,
    )

    assert fresh == original
    assert store.current_head() == head


def test_reobservation_flags_remain_non_authoritative(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)
    receipt = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=_fresh(proposal),
    )

    assert receipt["persistence_still_current"] is True
    assert receipt["authorization_consumed"] is True
    assert receipt["transition_persisted"] is True
    assert receipt["persisted_supersession_observed"] is True
    assert receipt["persisted_canonical_mutation_observed"] is True
    assert receipt["correction_applied"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["canonical_mutation"] is False


def test_logically_identical_reobservations_are_deterministic(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)
    fresh = _fresh(proposal)

    first = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=fresh,
    )
    second = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=deepcopy(fresh),
    )

    assert first == second
    assert first["reobservation_hash"] == second["reobservation_hash"]


def test_valid_receipt_regenerates_exactly(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)
    receipt = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=_fresh(proposal),
    )

    assert (
        validate_post_persistence_verified_claim_reobservation(
            receipt,
            store=store,
        )
        is True
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("persistence_read_hash", "0" * 64),
        ("record_id", "0" * 64),
        ("chain_entry_hash", "0" * 64),
        ("authorization_binding_hash", "0" * 64),
        ("original_verification_hash", "0" * 64),
        ("fresh_verification_hash", "0" * 64),
        ("changed_condition_ids", ["forged"]),
        ("exact_outcome_match", False),
        ("verified_correction_still_supported", False),
        ("status", "FORGED"),
        ("persistence_still_current", False),
        ("authorization_consumed", False),
        ("transition_persisted", False),
        ("correction_applied", True),
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
        ("canonical_mutation", True),
        ("reobservation_hash", "0" * 64),
    ],
)
def test_validator_rejects_top_level_tampering(
    tmp_path, field, value
):
    proposal, _, store, commit = _persisted(tmp_path)
    receipt = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=_fresh(proposal),
    )
    receipt[field] = value

    with pytest.raises(PostPersistenceVerifiedClaimReobservationError):
        validate_post_persistence_verified_claim_reobservation(
            receipt,
            store=store,
        )


def test_validator_rejects_nested_fresh_evidence_tampering(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)
    receipt = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=_fresh(proposal),
    )
    receipt["fresh_verification"]["after_outcomes"][
        "shape-corrected"
    ] = False

    with pytest.raises(
        PostPersistenceVerifiedClaimReobservationError,
        match="does not match",
    ):
        validate_post_persistence_verified_claim_reobservation(
            receipt,
            store=store,
        )


def test_validator_becomes_stale_when_persisted_head_advances(tmp_path):
    proposal, _, store, commit = _persisted(tmp_path)
    receipt = reobserve_persisted_verified_claim_correction(
        store=store,
        record_id=commit["record_id"],
        fresh_after_evidence=_fresh(proposal),
    )
    _advance_with_generic_transition(
        store,
        previous_hash=proposal["candidate_baseline_hash"],
    )

    with pytest.raises(
        PostPersistenceVerifiedClaimReobservationError,
        match="no longer the current baseline head",
    ):
        validate_post_persistence_verified_claim_reobservation(
            receipt,
            store=store,
        )


def test_persisted_read_rejects_tampered_chain_entry(tmp_path):
    _, _, store, commit = _persisted(tmp_path)
    read = store.read_verified_claim_correction(record_id=commit["record_id"])
    read["chain_entry"]["hash"] = "0" * 64

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="chain entry identity is invalid",
    ):
        validate_persisted_verified_claim_correction_read(read)
