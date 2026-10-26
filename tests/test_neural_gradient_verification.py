import math

import pytest

from experiments.neural_gradient_verification import (
    analytical_gradient,
    numerical_gradient,
    propose_gradient_step,
    squared_error,
)


def test_analytical_gradient_matches_independent_numerical_reference():
    args = ((0.2, -0.3), (1.0, 0.5), 0.1, 1.0)
    analytical = analytical_gradient(*args)
    numerical = numerical_gradient(*args)

    assert analytical == pytest.approx((-0.85, -0.425, -0.85))
    assert analytical == pytest.approx(numerical, abs=1e-6)


def test_bounded_step_reduces_measured_loss():
    result = propose_gradient_step(
        (0.2, -0.3), (1.0, 0.5), 0.1, 1.0, 0.1
    )
    assert result["improved"] is True
    assert result["loss_after"] < result["loss_before"]
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_excessive_step_is_not_misrepresented_as_improvement():
    result = propose_gradient_step(
        (0.2, -0.3), (1.0, 0.5), 0.1, 1.0, 10.0
    )
    assert result["improved"] is False
    assert result["loss_after"] > result["loss_before"]


@pytest.mark.parametrize(
    "bad",
    [float("nan"), float("inf"), -float("inf"), True, "1"],
)
def test_invalid_numeric_values_fail_closed(bad):
    with pytest.raises(ValueError):
        squared_error((bad,), (1,), 0, 1)
    with pytest.raises(ValueError):
        propose_gradient_step((0,), (1,), 0, 1, bad)


def test_dimension_mismatch_fails_closed():
    with pytest.raises(ValueError):
        analytical_gradient((1, 2), (1,), 0, 1)


def test_nonpositive_learning_rate_fails_closed():
    for rate in (0, -0.1):
        with pytest.raises(ValueError):
            propose_gradient_step((0,), (1,), 0, 1, rate)


def test_nonfinite_result_fails_closed():
    with pytest.raises(ValueError):
        squared_error((1e308,), (1e308,), 0, 0)


def test_original_inputs_are_not_mutated():
    weights = [0.2, -0.3]
    inputs = [1.0, 0.5]
    propose_gradient_step(weights, inputs, 0.1, 1.0, 0.1)
    assert weights == [0.2, -0.3]
    assert inputs == [1.0, 0.5]

def test_training_improvement_can_worsen_reference_evidence():
    weights = (0.2, -0.3)
    inputs = (1.0, 0.5)
    bias = 0.1

    proposal = propose_gradient_step(
        weights, inputs, bias, 1.0, 0.1
    )

    reference_before = squared_error(
        weights, inputs, bias, 0.0
    )
    reference_after = squared_error(
        proposal["weights"],
        inputs,
        proposal["bias"],
        0.0,
    )

    assert proposal["improved"] is True
    assert reference_after > reference_before
    assert proposal["accepted"] is False
    assert proposal["write_authority"] == "NONE"
