"""Persistence and replay checks for experimental neural corrections."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from experiments.neural_authorized_correction import propose_neural_correction
from experiments.neural_checkpoint import capture_checkpoint
from experiments.neural_correction import Perceptron
from experiments.neural_persistent_correction import (
    PersistentNeuralCorrectionStore,
)
from holosim.typed_operational_authorization import (
    ACTION_NEURAL_WEIGHT_CORRECTION,
    build_operational_authorization,
)


def setup_case(tmp_path):
    model = Perceptron(2)
    checkpoint = capture_checkpoint(model, "binary classification")

    store = PersistentNeuralCorrectionStore(
        tmp_path / "neural.jsonl",
        initial_checkpoint=checkpoint,
    )

    proposal = propose_neural_correction(
        checkpoint,
        inputs=(1, 1),
        expected=1 - model.predict((1, 1)).output,
    )

    authorization = build_operational_authorization(
        authorization_id="neural-test-001",
        actor_id="test-operator",
        action=ACTION_NEURAL_WEIGHT_CORRECTION,
        target_sha256=proposal["proposal_hash"],
        approval_reference="test-only",
    )

    return checkpoint, store, proposal, authorization


def test_initial_checkpoint_is_unchanged(tmp_path):
    checkpoint, store, _, _ = setup_case(tmp_path)

    assert store.current_checkpoint() == checkpoint


def test_commit_advances_persisted_checkpoint(tmp_path):
    _, store, proposal, authorization = setup_case(tmp_path)

    result = store.commit(
        proposal=proposal,
        authorization=authorization,
    )

    assert result["commit_performed"] is True
    assert store.current_checkpoint() == proposal["after_checkpoint"]


def test_restart_reconstructs_same_checkpoint(tmp_path):
    checkpoint, store, proposal, authorization = setup_case(tmp_path)

    store.commit(proposal=proposal, authorization=authorization)

    reopened = PersistentNeuralCorrectionStore(
        tmp_path / "neural.jsonl",
        initial_checkpoint=checkpoint,
    )

    assert reopened.current_checkpoint() == proposal["after_checkpoint"]


def test_replayed_authorization_cannot_commit_twice(tmp_path):
    _, store, proposal, authorization = setup_case(tmp_path)

    store.commit(proposal=proposal, authorization=authorization)

    with pytest.raises(ValueError):
        store.commit(
            proposal=proposal,
            authorization=authorization,
        )

    assert len(store.chain.load_and_verify()) == 1


def test_wrong_checkpoint_cannot_reconstruct_history(tmp_path):
    _, store, proposal, authorization = setup_case(tmp_path)

    store.commit(proposal=proposal, authorization=authorization)

    wrong_model = Perceptron(2)
    wrong_model.weights = [7, 7]

    wrong_checkpoint = capture_checkpoint(
        wrong_model, "binary classification",
    )

    reopened = PersistentNeuralCorrectionStore(
        tmp_path / "neural.jsonl",
        initial_checkpoint=wrong_checkpoint,
    )

    with pytest.raises(ValueError):
        reopened.current_checkpoint()


def test_concurrent_replay_commits_exactly_once(tmp_path):
    _, store, proposal, authorization = setup_case(tmp_path)

    def attempt(_):
        try:
            store.commit(
                proposal=deepcopy(proposal),
                authorization=deepcopy(authorization),
            )
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))

    assert sorted(outcomes) == [False, True]
    assert len(store.chain.load_and_verify()) == 1
    assert store.current_checkpoint() == proposal["after_checkpoint"]
