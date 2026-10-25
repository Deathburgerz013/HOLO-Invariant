"""Cross-process neural correction replay tests."""

from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy

from experiments.neural_authorized_correction import propose_neural_correction
from experiments.neural_checkpoint import capture_checkpoint
from experiments.neural_correction import Perceptron
from experiments.neural_persistent_correction import PersistentNeuralCorrectionStore
from holosim.typed_operational_authorization import (
    ACTION_NEURAL_WEIGHT_CORRECTION,
    build_operational_authorization,
)


def attempt_commit(args):
    path, checkpoint, proposal, authorization = args

    store = PersistentNeuralCorrectionStore(
        path,
        initial_checkpoint=checkpoint,
    )

    try:
        store.commit(
            proposal=deepcopy(proposal),
            authorization=deepcopy(authorization),
        )
        return "COMMITTED"
    except ValueError:
        return "REJECTED"


def test_two_processes_cannot_commit_same_correction(tmp_path):
    model = Perceptron(2)
    checkpoint = capture_checkpoint(model, "binary classification")

    proposal = propose_neural_correction(
        checkpoint,
        inputs=(1, 1),
        expected=1 - model.predict((1, 1)).output,
    )

    authorization = build_operational_authorization(
        authorization_id="multiprocess-neural-001",
        actor_id="test-operator",
        action=ACTION_NEURAL_WEIGHT_CORRECTION,
        target_sha256=proposal["proposal_hash"],
        approval_reference="test-only",
    )

    path = tmp_path / "neural-process.jsonl"
    arguments = (
        str(path),
        checkpoint,
        proposal,
        authorization,
    )

    with ProcessPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt_commit, [arguments, arguments]))

    assert sorted(outcomes) == ["COMMITTED", "REJECTED"]

    reopened = PersistentNeuralCorrectionStore(
        path,
        initial_checkpoint=checkpoint,
    )

    assert len(reopened.chain.load_and_verify()) == 1
    assert reopened.current_checkpoint() == proposal["after_checkpoint"]
