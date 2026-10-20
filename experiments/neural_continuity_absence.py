"""Bounded neural reconstruction from externally committed training events."""

import hashlib
import json
import re

from experiments.neural_correction import Perceptron

MAX_EVENTS = 10000
MAX_DIMENSIONS = 256


class NeuralContinuityError(ValueError):
    """Training evidence is invalid, incomplete, or unverifiable."""


def history_commitment(events):
    """Hash the exact ordered training-event sequence."""
    return hashlib.sha256(
        json.dumps(
            events, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _validate(events, dimensions):
    if type(dimensions) is not int or not 1 <= dimensions <= MAX_DIMENSIONS:
        raise NeuralContinuityError("invalid dimensions")
    if type(events) is not list or not 1 <= len(events) <= MAX_EVENTS:
        raise NeuralContinuityError("invalid event collection")

    for event in events:
        if type(event) is not list or len(event) != 2:
            raise NeuralContinuityError("invalid event")
        inputs, expected = event
        if (
            type(inputs) is not list
            or len(inputs) != dimensions
            or any(type(x) is not int or x not in (0, 1) for x in inputs)
            or type(expected) is not int
            or expected not in (0, 1)
        ):
            raise NeuralContinuityError("invalid training event")


def reconstruct_neural_state(
    events, *,
    dimensions,
    supplied_commitment,
    external_reference,
    collection_closed,
):
    """Replay verified records; never infer independent reference custody."""
    _validate(events, dimensions)

    if collection_closed is not True:
        raise NeuralContinuityError("event collection is not closed")

    if (
        type(supplied_commitment) is not str
        or re.fullmatch(r"[0-9a-f]{64}", supplied_commitment) is None
        or type(external_reference) is not str
        or re.fullmatch(r"[0-9a-f]{64}", external_reference) is None
    ):
        raise NeuralContinuityError("missing or invalid commitment")

    actual = history_commitment(events)

    if actual != supplied_commitment:
        raise NeuralContinuityError("history integrity mismatch")

    if supplied_commitment != external_reference:
        raise NeuralContinuityError("external reference mismatch")

    model = Perceptron(dimensions)
    for inputs, expected in events:
        model.correct(tuple(inputs), expected)

    return {
        "type": "bounded_neural_reconstruction",
        "version": 1,
        "dimensions": dimensions,
        "event_count": len(events),
        "history_commitment": actual,
        "weights": list(model.weights),
        "bias": model.bias,
        "collection_closed": True,
        "reconstruction_verified": True,
        "historical_occurrence_verified": False,
        "reference_custody_verified": False,
        "continuity_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
