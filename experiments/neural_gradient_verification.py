"""Bounded, read-only gradient-learning experiment.

Created-By: Canyon Brock Haney
AI-Contributor: GPT

This module does not mutate models, checkpoints, or persistent state.
"""

import math


def _finite(value):
    if type(value) not in (int, float):
        raise ValueError("Expected a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError("Expected a finite number") from None
    if not math.isfinite(result):
        raise ValueError("Expected a finite number")
    return result


def _inputs(weights, inputs, bias, target):
    if not isinstance(weights, (tuple, list)):
        raise ValueError("Invalid weights")
    if not isinstance(inputs, (tuple, list)):
        raise ValueError("Invalid inputs")
    if not 1 <= len(weights) <= 256 or len(weights) != len(inputs):
        raise ValueError("Invalid dimensions")

    w = tuple(_finite(v) for v in weights)
    x = tuple(_finite(v) for v in inputs)
    return w, x, _finite(bias), _finite(target)


def squared_error(weights, inputs, bias, target):
    """Half squared error for one linear-neuron observation."""
    w, x, b, t = _inputs(weights, inputs, bias, target)
    prediction = math.fsum(a * v for a, v in zip(w, x)) + b
    result = 0.5 * (prediction - t) ** 2
    if not math.isfinite(result):
        raise ValueError("Non-finite loss")
    return result


def analytical_gradient(weights, inputs, bias, target):
    """Gradient for weights followed by bias."""
    w, x, b, t = _inputs(weights, inputs, bias, target)
    prediction = math.fsum(a * v for a, v in zip(w, x)) + b
    error = prediction - t
    result = tuple(error * v for v in x) + (error,)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("Non-finite gradient")
    return result


def numerical_gradient(weights, inputs, bias, target, epsilon=1e-6):
    """Independent central finite-difference reference."""
    w, x, b, t = _inputs(weights, inputs, bias, target)
    step = _finite(epsilon)
    if step <= 0:
        raise ValueError("Invalid epsilon")

    result = []
    for index in range(len(w)):
        plus = list(w)
        minus = list(w)
        plus[index] += step
        minus[index] -= step
        if plus[index] == minus[index]:
            raise ValueError("Unresolvable finite-difference step")
        difference = (
            squared_error(plus, x, b, t)
            - squared_error(minus, x, b, t)
        ) / (plus[index] - minus[index])
        result.append(difference)

    if b + step == b - step:
        raise ValueError("Unresolvable bias step")

    result.append(
        (
            squared_error(w, x, b + step, t)
            - squared_error(w, x, b - step, t)
        ) / ((b + step) - (b - step))
    )

    if not all(math.isfinite(v) for v in result):
        raise ValueError("Non-finite numerical gradient")
    return tuple(result)


def propose_gradient_step(weights, inputs, bias, target, learning_rate):
    """Return a proposed new state and measured loss, without mutation."""
    w, x, b, t = _inputs(weights, inputs, bias, target)
    rate = _finite(learning_rate)
    if rate <= 0:
        raise ValueError("Invalid learning rate")

    gradient = analytical_gradient(w, x, b, t)
    new_weights = tuple(
        value - rate * derivative
        for value, derivative in zip(w, gradient[:-1])
    )
    new_bias = b - rate * gradient[-1]

    before = squared_error(w, x, b, t)
    after = squared_error(new_weights, x, new_bias, t)

    return {
        "weights": new_weights,
        "bias": new_bias,
        "loss_before": before,
        "loss_after": after,
        "improved": after < before,
        "accepted": False,
        "write_authority": "NONE",
    }
