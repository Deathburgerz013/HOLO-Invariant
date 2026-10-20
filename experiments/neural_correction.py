"""Deterministic perceptron experiment. No external dependencies."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Prediction:
    inputs: tuple[int, ...]
    output: int
    weights: tuple[int, ...]
    bias: int


class Perceptron:
    def __init__(self, dimensions: int) -> None:
        if type(dimensions) is not int or dimensions <= 0:
            raise ValueError("dimensions must be a positive integer")
        self.weights = [0] * dimensions
        self.bias = 0

    def predict(self, inputs: tuple[int, ...]) -> Prediction:
        if (
            not isinstance(inputs, tuple)
            or len(inputs) != len(self.weights)
            or any(type(x) is not int or x not in (0, 1) for x in inputs)
        ):
            raise ValueError("inputs must be binary integers")
        score = sum(w * x for w, x in zip(self.weights, inputs)) + self.bias
        return Prediction(
            inputs=inputs,
            output=int(score > 0),
            weights=tuple(self.weights),
            bias=self.bias,
        )

    def correct(self, inputs: tuple[int, ...], expected: int) -> bool:
        if type(expected) is not int or expected not in (0, 1):
            raise ValueError("expected must be binary")
        prediction = self.predict(inputs)
        error = expected - prediction.output
        if error == 0:
            return False
        self.weights = [
            w + error * x for w, x in zip(self.weights, inputs)
        ]
        self.bias += error
        return True
