"""Fail-closed integrity tests for persisted neural corrections."""

import json
from copy import deepcopy

import pytest

from experiments.neural_authorized_correction import propose_neural_correction
from experiments.neural_checkpoint import capture_checkpoint
from experiments.neural_correction import Perceptron
from experiments.neural_persistent_correction import PersistentNeuralCorrectionStore
from holosim.typed_operational_authorization import (
    ACTION_NEURAL_WEIGHT_CORRECTION,
    build_operational_authorization,
)


def make_case(tmp_path):
    model = Perceptron(2)
    initial = capture_checkpoint(model, "binary classification")
    path = tmp_path / "neural-integrity.jsonl"

    store = PersistentNeuralCorrectionStore(
        path, initial_checkpoint=initial,
    )

    proposal = propose_neural_correction(
        initial,
        inputs=(1, 1),
        expected=1 - model.predict((1, 1)).output,
    )

    authorization = build_operational_authorization(
        authorization_id="integrity-test-001",
        actor_id="test-operator",
        action=ACTION_NEURAL_WEIGHT_CORRECTION,
        target_sha256=proposal["proposal_hash"],
        approval_reference="test-only",
    )

    return path, initial, store, proposal, authorization


def test_tampered_chain_refuses_reconstruction(tmp_path):
    path, initial, store, proposal, authorization = make_case(tmp_path)

    store.commit(proposal=proposal, authorization=authorization)

    data = path.read_text(encoding="utf-8")
    entry = json.loads(data.splitlines()[0])
    entry["content"] = entry["content"] + "tampered"

    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    reopened = PersistentNeuralCorrectionStore(
        path, initial_checkpoint=initial,
    )

    with pytest.raises(ValueError):
        reopened.current_checkpoint()


def test_tampered_chain_refuses_further_commit(tmp_path):
    path, _, store, proposal, authorization = make_case(tmp_path)

    store.commit(proposal=proposal, authorization=authorization)

    data = path.read_text(encoding="utf-8")
    entry = json.loads(data.splitlines()[0])
    entry["hash"] = "0" * 64

    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(ValueError):
        store.commit(proposal=proposal, authorization=authorization)

    assert path.read_bytes() == before


def test_invalid_authorization_does_not_write(tmp_path):
    path, initial, store, proposal, authorization = make_case(tmp_path)

    forged = deepcopy(authorization)
    forged["target_sha256"] = "0" * 64

    with pytest.raises(ValueError):
        store.commit(proposal=proposal, authorization=forged)

    assert not path.exists()
    assert store.current_checkpoint() == initial


def test_tampered_proposal_does_not_write(tmp_path):
    path, initial, store, proposal, authorization = make_case(tmp_path)

    forged = deepcopy(proposal)
    forged["after_checkpoint"]["bias"] += 1

    with pytest.raises(ValueError):
        store.commit(proposal=forged, authorization=authorization)

    assert not path.exists()
    assert store.current_checkpoint() == initial


def test_replay_after_restart_does_not_write(tmp_path):
    path, initial, store, proposal, authorization = make_case(tmp_path)

    store.commit(proposal=proposal, authorization=authorization)
    before = path.read_bytes()

    reopened = PersistentNeuralCorrectionStore(
        path, initial_checkpoint=initial,
    )

    with pytest.raises(ValueError):
        reopened.commit(proposal=proposal, authorization=authorization)

    assert path.read_bytes() == before
