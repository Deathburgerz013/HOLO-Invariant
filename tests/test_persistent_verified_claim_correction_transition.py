from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json

import pytest

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
from holosim.evidence_bound_claim_correction_verification import (
    VERIFY_ACTION,
    verify_evidence_bound_claim_correction,
)
from holosim.hook_contract import build_hook_request, build_hook_result
from holosim.persistent_baseline_transition import (
    VERIFIED_CORRECTION_RECORD_TYPE,
    PersistentBaselineTransitionError,
    PersistentBaselineTransitionStore,
)
from holosim.typed_operational_authorization import (
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
        bindings[0], bindings[1]
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


def _condition_bundle(*, condition_id, claim_set_hash, satisfied):
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


def _authorized_correction(*, authorization_id="authorization-1"):
    proposal = _proposal()
    before = {
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
    after = {
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
        before_evidence=before,
        after_evidence=after,
    )
    binding = build_verified_claim_correction_transition_candidate(
        verification=verification,
        next_baseline_id="baseline-2",
    )
    authorization = build_operational_authorization(
        authorization_id=authorization_id,
        actor_id="external-operator",
        action=binding["authorization_action"],
        target_sha256=binding["authorization_target_sha256"],
        approval_reference=f"operator-review-{authorization_id}",
    )
    receipt = authorize_verified_claim_correction_transition(
        transition_binding=binding,
        authorization=authorization,
    )
    return proposal, receipt


def _store(tmp_path, proposal):
    return PersistentBaselineTransitionStore(
        tmp_path / "baseline-transitions.jsonl",
        initial_baseline_id="baseline-1",
        initial_baseline_state_hash=proposal["baseline_state_hash"],
    )


def test_complete_verified_correction_commits_and_advances_head(tmp_path):
    proposal, authorized = _authorized_correction()
    store = _store(tmp_path, proposal)

    result = store.commit_verified_claim_correction(
        authorized_correction=authorized
    )

    assert result["status"] == "COMMITTED_VERIFIED_CLAIM_CORRECTION"
    assert result["commit_performed"] is True
    assert result["current_baseline_id"] == "baseline-2"
    assert result["current_baseline_state_hash"] == (
        proposal["candidate_baseline_hash"]
    )
    assert store.current_head() == {
        "baseline_id": "baseline-2",
        "baseline_state_hash": proposal["candidate_baseline_hash"],
        "transition_count": 1,
    }


def test_generic_commit_cannot_strip_verified_correction_provenance(tmp_path):
    proposal, authorized = _authorized_correction()
    store = _store(tmp_path, proposal)

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="authorization action does not match",
    ):
        store.commit(
            transition=authorized["authorized_baseline_transition"],
            authorization=authorized["operational_authorization"],
        )

    assert store.current_head() == {
        "baseline_id": "baseline-1",
        "baseline_state_hash": proposal["baseline_state_hash"],
        "transition_count": 0,
    }
    committed = store.commit_verified_claim_correction(
        authorized_correction=authorized
    )
    assert committed["correction_provenance_persisted"] is True


def test_one_chain_entry_preserves_complete_authorized_correction(tmp_path):
    proposal, authorized = _authorized_correction()
    store = _store(tmp_path, proposal)
    result = store.commit_verified_claim_correction(
        authorized_correction=authorized
    )

    entries = store.chain.load_and_verify()
    assert len(entries) == 1
    payload = json.loads(entries[0]["content"])
    assert payload["type"] == VERIFIED_CORRECTION_RECORD_TYPE
    assert payload["authorized_correction"] == authorized
    assert payload["record_id"] == result["record_id"]
    assert payload["authorized_correction"]["verification_hash"] == (
        authorized["verification_hash"]
    )
    assert payload["authorized_correction"]["authorization_binding_hash"] == (
        authorized["authorization_binding_hash"]
    )


def test_commit_receipt_preserves_every_handoff_identity(tmp_path):
    proposal, authorized = _authorized_correction()
    result = _store(tmp_path, proposal).commit_verified_claim_correction(
        authorized_correction=authorized
    )

    for field in (
        "verification_hash",
        "proposal_hash",
        "binding_hash",
        "authorization_binding_hash",
        "candidate_hash",
        "transition_id",
        "authorization_hash",
    ):
        assert result[field] == authorized[field]


def test_commit_receipt_reports_the_actual_mutation_boundary(tmp_path):
    proposal, authorized = _authorized_correction()
    result = _store(tmp_path, proposal).commit_verified_claim_correction(
        authorized_correction=authorized
    )

    assert result["authorization_consumed"] is True
    assert result["transition_persisted"] is True
    assert result["correction_provenance_persisted"] is True
    assert result["current_baseline_advanced"] is True
    assert result["supersession_performed"] is True
    assert result["canonical_mutation"] is True
    assert result["correction_applied"] is False
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert result["promotion_authority"] == "EXACT_TARGET_ONLY"


def test_restart_reconstructs_verified_correction_head(tmp_path):
    proposal, authorized = _authorized_correction()
    first = _store(tmp_path, proposal)
    first.commit_verified_claim_correction(authorized_correction=authorized)

    restarted = _store(tmp_path, proposal)
    assert restarted.current_head() == {
        "baseline_id": "baseline-2",
        "baseline_state_hash": proposal["candidate_baseline_hash"],
        "transition_count": 1,
    }


def test_same_authorization_is_consumed_exactly_once(tmp_path):
    proposal, authorized = _authorized_correction()
    store = _store(tmp_path, proposal)
    store.commit_verified_claim_correction(authorized_correction=authorized)

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="authorization has already been consumed",
    ):
        store.commit_verified_claim_correction(authorized_correction=authorized)
    assert store.current_head()["transition_count"] == 1


def test_stale_verified_correction_is_rejected_after_head_moves(tmp_path):
    proposal, first = _authorized_correction(authorization_id="authorization-1")
    _, stale = _authorized_correction(authorization_id="authorization-2")
    store = _store(tmp_path, proposal)
    store.commit_verified_claim_correction(authorized_correction=first)

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="previous baseline does not match current head",
    ):
        store.commit_verified_claim_correction(authorized_correction=stale)
    assert store.current_head()["transition_count"] == 1


def test_concurrent_replay_commits_exactly_once(tmp_path):
    proposal, authorized = _authorized_correction()

    def attempt(_):
        store = _store(tmp_path, proposal)
        try:
            return store.commit_verified_claim_correction(
                authorized_correction=authorized
            )["status"]
        except PersistentBaselineTransitionError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))

    assert results.count("COMMITTED_VERIFIED_CLAIM_CORRECTION") == 1
    assert results.count("authorization has already been consumed") == 1
    assert _store(tmp_path, proposal).current_head()["transition_count"] == 1


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("verification_hash",), "0" * 64),
        (("binding_hash",), "0" * 64),
        (("authorization_binding_hash",), "0" * 64),
        (("operational_authorization", "actor_id"), "forged-actor"),
        (("authorized_baseline_transition", "transition_id"), "0" * 64),
        (("transition_binding", "verification_hash"), "0" * 64),
    ],
)
def test_tampered_complete_receipt_is_rejected_without_append(
    tmp_path, path, value
):
    proposal, authorized = _authorized_correction()
    store = _store(tmp_path, proposal)
    target = authorized
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="authorized correction is invalid",
    ):
        store.commit_verified_claim_correction(
            authorized_correction=authorized
        )
    assert store.current_head()["transition_count"] == 0


@pytest.mark.parametrize("invalid", [None, [], (), "receipt"])
def test_authorized_correction_must_be_plain_dictionary(tmp_path, invalid):
    proposal, _ = _authorized_correction()
    store = _store(tmp_path, proposal)

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="authorized_correction must be a plain dictionary",
    ):
        store.commit_verified_claim_correction(authorized_correction=invalid)
    assert store.current_head()["transition_count"] == 0


def test_input_is_not_mutated(tmp_path):
    proposal, authorized = _authorized_correction()
    original = deepcopy(authorized)

    _store(tmp_path, proposal).commit_verified_claim_correction(
        authorized_correction=authorized
    )

    assert authorized == original


def test_wrong_store_initial_identity_fails_on_reconstruction(tmp_path):
    proposal, authorized = _authorized_correction()
    store = _store(tmp_path, proposal)
    store.commit_verified_claim_correction(authorized_correction=authorized)
    wrong = PersistentBaselineTransitionStore(
        store.path,
        initial_baseline_id="baseline-wrong",
        initial_baseline_state_hash=proposal["baseline_state_hash"],
    )

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="store initial baseline does not match",
    ):
        wrong.current_head()
