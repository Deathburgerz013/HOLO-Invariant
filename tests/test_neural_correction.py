"""Falsifiable tests for deterministic neural correction."""

import pytest

from experiments.neural_correction import Perceptron


AND_DATA = (
    ((0, 0), 0),
    ((0, 1), 0),
    ((1, 0), 0),
    ((1, 1), 1),
)


def train(model, epochs=20):
    corrections = 0
    for _ in range(epochs):
        for inputs, expected in AND_DATA:
            corrections += int(model.correct(inputs, expected))
    return corrections


def test_initial_model_has_no_learned_weights():
    model = Perceptron(2)
    prediction = model.predict((1, 1))
    assert prediction.output == 0
    assert prediction.weights == (0, 0)
    assert prediction.bias == 0


def test_model_learns_and_function():
    model = Perceptron(2)
    assert train(model) > 0

    for inputs, expected in AND_DATA:
        assert model.predict(inputs).output == expected


def test_training_is_deterministic():
    first = Perceptron(2)
    second = Perceptron(2)

    assert train(first) == train(second)
    assert first.weights == second.weights
    assert first.bias == second.bias


def test_correct_prediction_does_not_modify_model():
    model = Perceptron(2)
    before = model.predict((0, 0))

    assert model.correct((0, 0), 0) is False
    assert model.predict((0, 0)) == before


def test_invalid_inputs_fail_closed():
    model = Perceptron(2)

    for inputs in ((1,), (1, 2), [1, 0], (True, 0)):
        with pytest.raises(ValueError):
            model.predict(inputs)

    with pytest.raises(ValueError):
        model.correct((1, 1), 2)


def test_invalid_dimensions_rejected():
    for dimensions in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            Perceptron(dimensions)


def test_correction_changes_wrong_prediction():
    model = Perceptron(2)

    assert model.predict((1, 1)).output == 0
    assert model.correct((1, 1), 1) is True
    assert model.predict((1, 1)).output == 1
