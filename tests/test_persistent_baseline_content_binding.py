import hashlib

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
from holosim.bounded_baseline_content_identity import (
    bind_baseline_content_identity,
)
from holosim.canonical import stable_hash
from holosim.persistent_baseline_content_binding import (
    BASELINE_ID_MISMATCH,
    BASELINE_STATE_IDENTITY_MISMATCH,
    CONTENT_BINDING_INCOMPLETE,
    CURRENT_BASELINE_BOUND,
    PersistentBaselineContentBindingError,
    bind_persistent_baseline_content,
)
from holosim.persistent_baseline_transition import (
    PersistentBaselineTransitionStore,
)
from holosim.typed_operational_authorization import (
    ACTION_BASELINE_PROMOTION,
    build_operational_authorization,
)


def stable_identity(value):
    return stable_hash(value)


def different_identity(value):
    return "different:" + stable_hash(value)


def _state_for(value):
    return stable_hash(value)


A_CONTENT = {
    "claims": [
        {"id": "claim-a", "value": 1},
    ],
    "authority": "NONE",
}

B_CONTENT = {
    "claims": [
        {"id": "claim-a", "value": 1},
        {"id": "claim-b", "value": 2},
    ],
    "authority": "NONE",
}

A_STATE = _state_for(A_CONTENT)
B_STATE = _state_for(B_CONTENT)


def _store(
    tmp_path,
    *,
    initial_id="baseline-a",
    initial_state=A_STATE,
):
    return PersistentBaselineTransitionStore(
        tmp_path / "baseline-transitions.jsonl",
        initial_baseline_id=initial_id,
        initial_baseline_state_hash=initial_state,
    )


def _content_receipt(
    *,
    baseline=A_CONTENT,
    baseline_id="baseline-a",
    declared_state_identity=A_STATE,
):
    return bind_baseline_content_identity(
        baseline=baseline,
        baseline_id=baseline_id,
        declared_state_identity=declared_state_identity,
        identity_function=stable_identity,
    )


def _authorized_transition(
    *,
    previous_id="baseline-a",
    previous_state=A_STATE,
    next_id="baseline-b",
    next_state=B_STATE,
    authorization_id="approval:a-to-b",
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
        justification_references={
            "claim-a": "justification:claim-a:v1",
        },
    )

    candidate = build_baseline_transition_candidate(
        promotion_gate=gate,
        next_baseline_id=next_id,
        next_baseline_state_hash=next_state,
    )

    authorization = build_operational_authorization(
        authorization_id=authorization_id,
        actor_id="external-reviewer",
        action=ACTION_BASELINE_PROMOTION,
        target_sha256=candidate["candidate_hash"],
        approval_reference=authorization_id,
    )

    transition = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=candidate,
        authorization=authorization,
    )

    return authorization, transition


def _advance_to_b(store):
    authorization, transition = _authorized_transition()

    return store.commit(
        transition=transition,
        authorization=authorization,
    )


def test_current_initial_baseline_content_is_bound(tmp_path):
    store = _store(tmp_path)

    receipt = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=_content_receipt(),
        identity_function=stable_identity,
    )

    assert receipt["status"] == CURRENT_BASELINE_BOUND
    assert receipt["binding_complete"] is True
    assert receipt["content_binding_complete"] is True
    assert receipt["baseline_id_matches"] is True
    assert receipt["state_identity_matches"] is True
    assert receipt["current_baseline_id"] == "baseline-a"
    assert receipt["current_baseline_state_hash"] == A_STATE
    assert receipt["transition_count"] == 0


def test_current_advanced_baseline_content_is_bound(tmp_path):
    store = _store(tmp_path)
    _advance_to_b(store)

    content_receipt = _content_receipt(
        baseline=B_CONTENT,
        baseline_id="baseline-b",
        declared_state_identity=B_STATE,
    )

    receipt = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=content_receipt,
        identity_function=stable_identity,
    )

    assert receipt["status"] == CURRENT_BASELINE_BOUND
    assert receipt["binding_complete"] is True
    assert receipt["current_baseline_id"] == "baseline-b"
    assert receipt["current_baseline_state_hash"] == B_STATE
    assert receipt["transition_count"] == 1


def test_previous_valid_baseline_becomes_stale_after_head_advances(
    tmp_path,
):
    store = _store(tmp_path)

    old_content_receipt = _content_receipt()

    before = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=old_content_receipt,
        identity_function=stable_identity,
    )

    assert before["status"] == CURRENT_BASELINE_BOUND
    assert before["binding_complete"] is True

    _advance_to_b(store)

    after = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=old_content_receipt,
        identity_function=stable_identity,
    )

    assert after["status"] == BASELINE_ID_MISMATCH
    assert after["binding_complete"] is False
    assert after["content_binding_complete"] is True
    assert after["baseline_id_matches"] is False
    assert after["state_identity_matches"] is False
    assert after["current_baseline_id"] == "baseline-b"
    assert after["current_baseline_state_hash"] == B_STATE
    assert after["transition_count"] == 1
    assert before["receipt_id"] != after["receipt_id"]


def test_right_baseline_id_with_wrong_state_identity_is_rejected(
    tmp_path,
):
    store = _store(tmp_path)
    _advance_to_b(store)

    content_receipt = _content_receipt(
        baseline=A_CONTENT,
        baseline_id="baseline-b",
        declared_state_identity=A_STATE,
    )

    receipt = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=content_receipt,
        identity_function=stable_identity,
    )

    assert receipt["status"] == BASELINE_STATE_IDENTITY_MISMATCH
    assert receipt["binding_complete"] is False
    assert receipt["content_binding_complete"] is True
    assert receipt["baseline_id_matches"] is True
    assert receipt["state_identity_matches"] is False


def test_matching_head_strings_do_not_override_failed_content_binding(
    tmp_path,
):
    store = _store(tmp_path)

    wrong_content = {
        "claims": [{"id": "wrong", "value": 999}],
        "authority": "NONE",
    }

    content_receipt = _content_receipt(
        baseline=wrong_content,
        baseline_id="baseline-a",
        declared_state_identity=A_STATE,
    )

    assert content_receipt["binding_complete"] is False

    receipt = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=content_receipt,
        identity_function=stable_identity,
    )

    assert receipt["status"] == CONTENT_BINDING_INCOMPLETE
    assert receipt["binding_complete"] is False
    assert receipt["content_binding_complete"] is False
    assert receipt["baseline_id_matches"] is True
    assert receipt["state_identity_matches"] is True


def test_wrong_baseline_id_is_distinguished_from_wrong_content(
    tmp_path,
):
    store = _store(tmp_path)

    content_receipt = _content_receipt(
        baseline=A_CONTENT,
        baseline_id="baseline-wrong",
        declared_state_identity=A_STATE,
    )

    receipt = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=content_receipt,
        identity_function=stable_identity,
    )

    assert receipt["status"] == BASELINE_ID_MISMATCH
    assert receipt["binding_complete"] is False
    assert receipt["content_binding_complete"] is True
    assert receipt["baseline_id_matches"] is False
    assert receipt["state_identity_matches"] is True


def test_tampered_content_identity_receipt_fails_before_head_binding(
    tmp_path,
):
    store = _store(tmp_path)
    content_receipt = _content_receipt()
    content_receipt["baseline"]["claims"][0]["value"] = 999

    with pytest.raises(
        PersistentBaselineContentBindingError,
        match="must verify before persistent binding",
    ):
        bind_persistent_baseline_content(
            store=store,
            content_identity_receipt=content_receipt,
            identity_function=stable_identity,
        )


def test_different_identity_function_fails_before_head_binding(
    tmp_path,
):
    store = _store(tmp_path)

    with pytest.raises(
        PersistentBaselineContentBindingError,
        match="must verify before persistent binding",
    ):
        bind_persistent_baseline_content(
            store=store,
            content_identity_receipt=_content_receipt(),
            identity_function=different_identity,
        )


def test_non_mapping_content_receipt_fails_closed(tmp_path):
    store = _store(tmp_path)

    with pytest.raises(
        PersistentBaselineContentBindingError,
        match="content_identity_receipt must be a mapping",
    ):
        bind_persistent_baseline_content(
            store=store,
            content_identity_receipt=None,
            identity_function=stable_identity,
        )


def test_wrong_store_type_fails_closed():
    with pytest.raises(
        PersistentBaselineContentBindingError,
        match="store must be a PersistentBaselineTransitionStore",
    ):
        bind_persistent_baseline_content(
            store={},
            content_identity_receipt=_content_receipt(),
            identity_function=stable_identity,
        )


def test_restart_reconstructs_same_bound_current_head(tmp_path):
    path = tmp_path / "baseline-transitions.jsonl"

    first = PersistentBaselineTransitionStore(
        path,
        initial_baseline_id="baseline-a",
        initial_baseline_state_hash=A_STATE,
    )
    _advance_to_b(first)

    restarted = PersistentBaselineTransitionStore(
        path,
        initial_baseline_id="baseline-a",
        initial_baseline_state_hash=A_STATE,
    )

    content_receipt = _content_receipt(
        baseline=B_CONTENT,
        baseline_id="baseline-b",
        declared_state_identity=B_STATE,
    )

    receipt = bind_persistent_baseline_content(
        store=restarted,
        content_identity_receipt=content_receipt,
        identity_function=stable_identity,
    )

    assert receipt["status"] == CURRENT_BASELINE_BOUND
    assert receipt["binding_complete"] is True
    assert receipt["transition_count"] == 1


def test_binding_grants_no_truth_compression_or_write_authority(
    tmp_path,
):
    store = _store(tmp_path)

    receipt = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=_content_receipt(),
        identity_function=stable_identity,
    )

    assert receipt["baseline_truth_verified"] is False
    assert receipt["compression_preservation_verified"] is False
    assert receipt["compression_authorized"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_binding_is_deterministic_for_unchanged_head(tmp_path):
    store = _store(tmp_path)
    content_receipt = _content_receipt()

    first = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=content_receipt,
        identity_function=stable_identity,
    )
    second = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=content_receipt,
        identity_function=stable_identity,
    )

    assert first == second