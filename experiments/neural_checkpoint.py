"""Deterministic neural checkpoints with independent reference comparison."""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from experiments.neural_correction import Perceptron


def _hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def capture_checkpoint(model: Perceptron, objective: str) -> dict:
    if type(objective) is not str or not objective:
        raise ValueError("objective must be a nonempty string")

    if (
        not model.weights
        or any(type(w) is not int for w in model.weights)
        or type(model.bias) is not int
    ):
        raise ValueError("invalid model state")

    body = {
        "version": 1,
        "architecture": "binary_perceptron",
        "dimensions": len(model.weights),
        "objective": objective,
        "weights": list(model.weights),
        "bias": model.bias,
    }

    return {**body, "checkpoint_hash": _hash(body)}


def verify_checkpoint(checkpoint: Mapping[str, Any]) -> bool:
    if not isinstance(checkpoint, dict):
        raise ValueError("checkpoint must be a dictionary")

    required = {
        "version", "architecture", "dimensions",
        "objective", "weights", "bias", "checkpoint_hash",
    }

    if set(checkpoint) != required:
        raise ValueError("checkpoint fields mismatch")

    if type(checkpoint["version"]) is not int or checkpoint["version"] != 1:
        raise ValueError("unsupported checkpoint version")

    if checkpoint["architecture"] != "binary_perceptron":
        raise ValueError("unsupported architecture")

    dimensions = checkpoint["dimensions"]
    weights = checkpoint["weights"]

    if (
        type(dimensions) is not int
        or dimensions <= 0
        or type(weights) is not list
        or len(weights) != dimensions
        or any(type(w) is not int for w in weights)
        or type(checkpoint["bias"]) is not int
        or type(checkpoint["objective"]) is not str
        or not checkpoint["objective"]
    ):
        raise ValueError("invalid checkpoint state")

    body = {key: checkpoint[key] for key in required - {"checkpoint_hash"}}

    if checkpoint["checkpoint_hash"] != _hash(body):
        raise ValueError("checkpoint hash mismatch")

    return True


def verify_against_reference(
    checkpoint: Mapping[str, Any],
    reference: Mapping[str, Any],
) -> bool:
    verify_checkpoint(checkpoint)
    verify_checkpoint(reference)

    if checkpoint != reference:
        raise ValueError("checkpoint differs from independent reference")

    return True


def restore_checkpoint(
    checkpoint: Mapping[str, Any],
    reference: Mapping[str, Any],
) -> Perceptron:
    verify_against_reference(checkpoint, reference)

    model = Perceptron(checkpoint["dimensions"])
    model.weights = list(checkpoint["weights"])
    model.bias = checkpoint["bias"]
    return model
