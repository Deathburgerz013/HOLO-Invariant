"""Adversarial tests for bounded neural continuity under absence."""

from copy import deepcopy

import pytest

from experiments.neural_continuity_absence import (
    NeuralContinuityError,
    history_commitment,
    reconstruct_neural_state,
)


def history():
    return [
        [list(inputs), expected]
        for _ in range(20)
        for inputs, expected in (
            ((0, 0), 0),
            ((0, 1), 0),
            ((1, 0), 0),
            ((1, 1), 1),
        )
    ]


def recover(events, reference=None, **changes):
    arguments = {
        "dimensions": 2,
        "supplied_commitment": history_commitment(events),
        "external_reference": (
            history_commitment(events) if reference is None else reference
        ),
        "collection_closed": True,
    }
    arguments.update(changes)
    return reconstruct_neural_state(events, **arguments)


def test_exact_reconstruction():
    result = recover(history())
    assert result["weights"] == [2, 1]
    assert result["bias"] == -2
    assert result["event_count"] == 80


def test_reconstruction_grants_no_authority():
    result = recover(history())
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["continuity_claimed"] is False
    assert result["historical_occurrence_verified"] is False
    assert result["reference_custody_verified"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize("mutation", ["missing", "reordered", "altered"])
def test_modified_history_rejected_against_original_reference(mutation):
    original = history()
    reference = history_commitment(original)
    changed = deepcopy(original)

    if mutation == "missing":
        changed.pop(3)
    elif mutation == "reordered":
        changed[2], changed[3] = changed[3], changed[2]
    else:
        changed[-1][1] = 0

    with pytest.raises(NeuralContinuityError, match="external reference"):
        recover(changed, reference=reference)


def test_corruption_without_rehash_rejected():
    events = history()
    original_hash = history_commitment(events)
    events[-1][1] = 0

    with pytest.raises(NeuralContinuityError, match="integrity"):
        recover(events, supplied_commitment=original_hash)


def test_unavailable_reference_rejected():
    with pytest.raises(NeuralContinuityError):
        recover(history(), external_reference=None)


def test_open_collection_rejected():
    with pytest.raises(NeuralContinuityError, match="not closed"):
        recover(history(), collection_closed=False)


@pytest.mark.parametrize("invalid", [
    [[[True, 0], 0]],
    [[[0, 1], True]],
    [[[0, 1], 2]],
    [[[0], 1]],
    [[(0, 1), 1]],
    [],
])
def test_malformed_history_rejected(invalid):
    with pytest.raises(NeuralContinuityError):
        recover(invalid)


def test_invalid_dimensions_rejected():
    with pytest.raises(NeuralContinuityError):
        recover(history(), dimensions=True)


def test_self_consistent_forgery_not_independently_authenticated():
    forged = history()
    forged[-1][1] = 0

    result = recover(forged)
    assert result["reference_custody_verified"] is False
    assert result["historical_occurrence_verified"] is False


def test_original_reference_rejects_self_consistent_forgery():
    original = history()
    reference = history_commitment(original)
    forged = deepcopy(original)
    forged[-1][1] = 0

    with pytest.raises(NeuralContinuityError):
        recover(forged, reference=reference)
