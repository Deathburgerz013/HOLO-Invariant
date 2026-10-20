"""Adversarial tests for neural checkpoint integrity and recovery."""

from copy import deepcopy

import pytest

from experiments.neural_checkpoint import (
    _hash,
    capture_checkpoint,
    restore_checkpoint,
    verify_against_reference,
    verify_checkpoint,
)
from experiments.neural_correction import Perceptron


def trained_and_model():
    model = Perceptron(2)
    dataset = (
        ((0, 0), 0),
        ((0, 1), 0),
        ((1, 0), 0),
        ((1, 1), 1),
    )
    for _ in range(20):
        for inputs, expected in dataset:
            model.correct(inputs, expected)
    return model


def test_valid_checkpoint():
    checkpoint = capture_checkpoint(trained_and_model(), "AND")
    assert verify_checkpoint(checkpoint)


def test_corrupted_weights_rejected():
    checkpoint = capture_checkpoint(trained_and_model(), "AND")
    checkpoint["weights"][0] += 1

    with pytest.raises(ValueError):
        verify_checkpoint(checkpoint)


def test_corrupted_objective_rejected():
    checkpoint = capture_checkpoint(trained_and_model(), "AND")
    checkpoint["objective"] = "OR"

    with pytest.raises(ValueError):
        verify_checkpoint(checkpoint)


def test_forged_hash_passes_structural_but_fails_reference():
    reference = capture_checkpoint(trained_and_model(), "AND")
    forged = deepcopy(reference)

    forged["weights"][0] += 1
    body = {k: v for k, v in forged.items() if k != "checkpoint_hash"}
    forged["checkpoint_hash"] = _hash(body)

    assert verify_checkpoint(forged)

    with pytest.raises(ValueError):
        verify_against_reference(forged, reference)


def test_restore_recovers_original_behavior():
    model = trained_and_model()
    checkpoint = capture_checkpoint(model, "AND")
    reference = deepcopy(checkpoint)

    model.weights = [0, 0]
    model.bias = 0

    recovered = restore_checkpoint(checkpoint, reference)

    assert recovered.predict((1, 1)).output == 1
    assert recovered.predict((1, 0)).output == 0
    assert tuple(recovered.weights) == tuple(reference["weights"])
    assert recovered.bias == reference["bias"]


def test_invalid_checkpoint_fields_rejected():
    checkpoint = capture_checkpoint(trained_and_model(), "AND")
    checkpoint["unexpected"] = True

    with pytest.raises(ValueError):
        verify_checkpoint(checkpoint)


def test_invalid_state_types_rejected():
    checkpoint = capture_checkpoint(trained_and_model(), "AND")
    checkpoint["weights"][0] = True

    with pytest.raises(ValueError):
        verify_checkpoint(checkpoint)


def test_reference_mismatch_blocks_restoration():
    checkpoint = capture_checkpoint(trained_and_model(), "AND")
    reference = deepcopy(checkpoint)
    reference["objective"] = "OR"
    reference["checkpoint_hash"] = _hash({
        k: v for k, v in reference.items()
        if k != "checkpoint_hash"
    })

    with pytest.raises(ValueError):
        restore_checkpoint(checkpoint, reference)
