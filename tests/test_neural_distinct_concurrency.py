"""Distinct concurrent proposals must not fork checkpoint history."""

from concurrent.futures import ProcessPoolExecutor

from experiments.neural_authorized_correction import propose_neural_correction
from experiments.neural_checkpoint import capture_checkpoint
from experiments.neural_correction import Perceptron
from experiments.neural_persistent_correction import PersistentNeuralCorrectionStore
from holosim.typed_operational_authorization import (
    ACTION_NEURAL_WEIGHT_CORRECTION,
    build_operational_authorization,
)
from tests.test_neural_persistent_multiprocess import attempt_commit


def test_distinct_concurrent_proposals_preserve_single_history(tmp_path):
    model = Perceptron(2)
    checkpoint = capture_checkpoint(model, "binary classification")

    proposal_a = propose_neural_correction(
        checkpoint,
        inputs=(1, 1),
        expected=1 - model.predict((1, 1)).output,
    )
    proposal_b = propose_neural_correction(
        checkpoint,
        inputs=(1, 0),
        expected=1 - model.predict((1, 0)).output,
    )

    assert proposal_a["proposal_hash"] != proposal_b["proposal_hash"]

    authorization_a = build_operational_authorization(
        authorization_id="distinct-concurrent-a",
        actor_id="test-operator",
        action=ACTION_NEURAL_WEIGHT_CORRECTION,
        target_sha256=proposal_a["proposal_hash"],
        approval_reference="test-only",
    )
    authorization_b = build_operational_authorization(
        authorization_id="distinct-concurrent-b",
        actor_id="test-operator",
        action=ACTION_NEURAL_WEIGHT_CORRECTION,
        target_sha256=proposal_b["proposal_hash"],
        approval_reference="test-only",
    )

    path = tmp_path / "distinct-concurrent.jsonl"

    arguments = [
        (str(path), checkpoint, proposal_a, authorization_a),
        (str(path), checkpoint, proposal_b, authorization_b),
    ]

    with ProcessPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt_commit, arguments))

    assert sorted(outcomes) == ["COMMITTED", "REJECTED"]

    reopened = PersistentNeuralCorrectionStore(
        path,
        initial_checkpoint=checkpoint,
    )

    assert len(reopened.chain.load_and_verify()) == 1
    assert reopened.current_checkpoint() in (
        proposal_a["after_checkpoint"],
        proposal_b["after_checkpoint"],
    )
