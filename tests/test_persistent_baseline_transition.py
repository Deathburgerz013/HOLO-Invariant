import copy
import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from holosim.authorized_baseline_transition import (
    authorize_baseline_transition,
    build_baseline_transition_candidate,
)
from holosim.baseline_observation_compare import (
    build_baseline_observation,
    compare_baseline_observations,
)
from holosim.baseline_promotion_gate import evaluate_baseline_promotion
from holosim.persistent_baseline_transition import (
    PersistentBaselineTransitionError,
    PersistentBaselineTransitionStore,
)
from holosim.typed_operational_authorization import (
    ACTION_BASELINE_PROMOTION,
    ACTION_SERVICE_APPEND,
    build_operational_authorization,
)


def _state(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


A_STATE = _state("state-a")
B_STATE = _state("state-b")
C_STATE = _state("state-c")


def _authorized_transition(
    *,
    previous_id="baseline-a",
    previous_state=A_STATE,
    next_id="baseline-b",
    next_state=B_STATE,
    authorization_id="approval:a-to-b",
    action=ACTION_BASELINE_PROMOTION,
):
    left = build_baseline_observation(
        observer_id="observer-a",
        baseline_id=previous_id,
        baseline_state_hash=previous_state,
        findings={"claim-a": "EXTENSION"},
    )
    right = build_baseline_observation(
        observer_id="observer-b",
        baseline_id=previous_id,
        baseline_state_hash=previous_state,
        findings={"claim-a": "EXTENSION"},
    )
    comparison = compare_baseline_observations(left, right)
    gate = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references={"claim-a": "justification:claim-a:v1"},
    )
    candidate = build_baseline_transition_candidate(
        promotion_gate=gate,
        next_baseline_id=next_id,
        next_baseline_state_hash=next_state,
    )
    authorization = build_operational_authorization(
        authorization_id=authorization_id,
        actor_id="external-reviewer",
        action=action,
        target_sha256=candidate["candidate_hash"],
        approval_reference=authorization_id,
    )
    if action != ACTION_BASELINE_PROMOTION:
        return gate, candidate, authorization, None
    transition = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=candidate,
        authorization=authorization,
    )
    return gate, candidate, authorization, transition


def _store(tmp_path, *, initial_id="baseline-a", initial_state=A_STATE):
    return PersistentBaselineTransitionStore(
        tmp_path / "baseline-transitions.jsonl",
        initial_baseline_id=initial_id,
        initial_baseline_state_hash=initial_state,
    )


def test_initial_head_is_declared_baseline(tmp_path):
    store = _store(tmp_path)
    assert store.current_head() == {
        "baseline_id": "baseline-a",
        "baseline_state_hash": A_STATE,
        "transition_count": 0,
    }


def test_exact_authorized_transition_becomes_current(tmp_path):
    store = _store(tmp_path)
    _, _, authorization, transition = _authorized_transition()

    result = store.commit(
        transition=transition,
        authorization=authorization,
    )

    assert result["status"] == "COMMITTED"
    assert result["commit_performed"] is True
    assert result["current_baseline_id"] == "baseline-b"
    assert result["current_baseline_state_hash"] == B_STATE
    assert store.current_head()["baseline_id"] == "baseline-b"
    assert store.current_head()["transition_count"] == 1


def test_same_authorization_is_consumed_exactly_once(tmp_path):
    store = _store(tmp_path)
    _, _, authorization, transition = _authorized_transition()

    store.commit(transition=transition, authorization=authorization)

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="authorization has already been consumed",
    ):
        store.commit(transition=transition, authorization=authorization)

    assert store.current_head()["transition_count"] == 1


def test_stale_previous_baseline_is_rejected_after_head_moves(tmp_path):
    store = _store(tmp_path)
    _, _, first_authorization, first_transition = _authorized_transition()
    store.commit(
        transition=first_transition,
        authorization=first_authorization,
    )

    _, _, stale_authorization, stale_transition = _authorized_transition(
        next_id="baseline-c",
        next_state=C_STATE,
        authorization_id="approval:stale-a-to-c",
    )

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="previous baseline does not match current head",
    ):
        store.commit(
            transition=stale_transition,
            authorization=stale_authorization,
        )

    assert store.current_head()["baseline_id"] == "baseline-b"
    assert store.current_head()["transition_count"] == 1


def test_restart_reconstructs_persisted_current_head(tmp_path):
    path = tmp_path / "baseline-transitions.jsonl"
    first_store = PersistentBaselineTransitionStore(
        path,
        initial_baseline_id="baseline-a",
        initial_baseline_state_hash=A_STATE,
    )
    _, _, authorization, transition = _authorized_transition()
    first_store.commit(transition=transition, authorization=authorization)

    restarted = PersistentBaselineTransitionStore(
        path,
        initial_baseline_id="baseline-a",
        initial_baseline_state_hash=A_STATE,
    )

    assert restarted.current_head() == {
        "baseline_id": "baseline-b",
        "baseline_state_hash": B_STATE,
        "transition_count": 1,
    }


def test_new_transition_must_start_from_reconstructed_head(tmp_path):
    store = _store(tmp_path)
    _, _, first_authorization, first_transition = _authorized_transition()
    store.commit(
        transition=first_transition,
        authorization=first_authorization,
    )

    _, _, second_authorization, second_transition = _authorized_transition(
        previous_id="baseline-b",
        previous_state=B_STATE,
        next_id="baseline-c",
        next_state=C_STATE,
        authorization_id="approval:b-to-c",
    )
    result = store.commit(
        transition=second_transition,
        authorization=second_authorization,
    )

    assert result["current_baseline_id"] == "baseline-c"
    assert store.current_head() == {
        "baseline_id": "baseline-c",
        "baseline_state_hash": C_STATE,
        "transition_count": 2,
    }


def test_wrong_initial_baseline_is_rejected_after_persistence(tmp_path):
    path = tmp_path / "baseline-transitions.jsonl"
    store = PersistentBaselineTransitionStore(
        path,
        initial_baseline_id="baseline-a",
        initial_baseline_state_hash=A_STATE,
    )
    _, _, authorization, transition = _authorized_transition()
    store.commit(transition=transition, authorization=authorization)

    wrong = PersistentBaselineTransitionStore(
        path,
        initial_baseline_id="baseline-wrong",
        initial_baseline_state_hash=A_STATE,
    )

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="store initial baseline does not match",
    ):
        wrong.current_head()


def test_tampered_transition_is_rejected_without_mutation(tmp_path):
    store = _store(tmp_path)
    _, _, authorization, transition = _authorized_transition()
    tampered = copy.deepcopy(transition)
    tampered["next_baseline_id"] = "tampered"

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="transition identity is invalid",
    ):
        store.commit(
            transition=tampered,
            authorization=authorization,
        )

    assert store.current_head()["transition_count"] == 0


def test_service_append_authorization_cannot_persist_baseline_transition(tmp_path):
    store = _store(tmp_path)
    gate, candidate, _, _ = _authorized_transition()
    promotion_authorization = build_operational_authorization(
        authorization_id="approval:a-to-b",
        actor_id="external-reviewer",
        action=ACTION_BASELINE_PROMOTION,
        target_sha256=candidate["candidate_hash"],
        approval_reference="approval:a-to-b",
    )
    transition = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=candidate,
        authorization=promotion_authorization,
    )
    wrong_authorization = build_operational_authorization(
        authorization_id="approval:wrong-action",
        actor_id="external-reviewer",
        action=ACTION_SERVICE_APPEND,
        target_sha256=candidate["candidate_hash"],
        approval_reference="approval:wrong-action",
    )

    with pytest.raises(
        PersistentBaselineTransitionError,
        match="authorization action does not match",
    ):
        store.commit(
            transition=transition,
            authorization=wrong_authorization,
        )

    assert store.current_head()["transition_count"] == 0


def test_persisted_transition_remains_non_epistemic_and_non_executing(tmp_path):
    store = _store(tmp_path)
    _, _, authorization, transition = _authorized_transition()

    result = store.commit(
        transition=transition,
        authorization=authorization,
    )

    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_concurrent_replay_commits_exactly_once(tmp_path):
    path = tmp_path / "baseline-transitions.jsonl"
    _, _, authorization, transition = _authorized_transition()

    def attempt():
        store = PersistentBaselineTransitionStore(
            path,
            initial_baseline_id="baseline-a",
            initial_baseline_state_hash=A_STATE,
        )
        try:
            result = store.commit(
                transition=transition,
                authorization=authorization,
            )
            return result["status"]
        except PersistentBaselineTransitionError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))

    assert results.count("COMMITTED") == 1
    assert results.count("authorization has already been consumed") == 1

    restarted = PersistentBaselineTransitionStore(
        path,
        initial_baseline_id="baseline-a",
        initial_baseline_state_hash=A_STATE,
    )
    assert restarted.current_head()["transition_count"] == 1
    assert restarted.current_head()["baseline_id"] == "baseline-b"
