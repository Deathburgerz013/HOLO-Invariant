from __future__ import annotations

import copy

import pytest

from holosim.baseline_observation_compare import (
    BaselineObservationError,
    build_baseline_observation,
    compare_baseline_observations,
)


def _obs(observer_id: str, findings: dict[str, str], *, state: str = "state-a"):
    return build_baseline_observation(
        observer_id=observer_id,
        baseline_id="baseline-1",
        baseline_state_hash=state,
        findings=findings,
    )


def test_same_baseline_support_becomes_agreement() -> None:
    left = _obs("observer-a", {"claim-1": "SUPPORT"})
    right = _obs("observer-b", {"claim-1": "SUPPORT"})

    result = compare_baseline_observations(left, right)

    assert result["agreement"] == ["claim-1"]
    assert result["extension"] == []
    assert result["conflict"] == []
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_yes_and_is_preserved_as_extension_not_vote() -> None:
    left = _obs("observer-a", {"claim-1": "SUPPORT", "claim-2": "EXTENSION"})
    right = _obs("observer-b", {"claim-1": "SUPPORT", "claim-2": "SUPPORT"})

    result = compare_baseline_observations(left, right)

    assert result["agreement"] == ["claim-1"]
    assert result["extension"] == ["claim-2"]
    assert result["next_baseline_selected"] is False


def test_no_but_is_preserved_as_correction_when_both_observers_agree() -> None:
    left = _obs("observer-a", {"claim-1": "CORRECTION"})
    right = _obs("observer-b", {"claim-1": "CORRECTION"})

    result = compare_baseline_observations(left, right)

    assert result["correction"] == ["claim-1"]
    assert result["conflict"] == []


def test_support_vs_correction_is_conflict_not_resolution() -> None:
    left = _obs("observer-a", {"claim-1": "SUPPORT"})
    right = _obs("observer-b", {"claim-1": "CORRECTION"})

    result = compare_baseline_observations(left, right)

    assert result["conflict"] == ["claim-1"]
    assert result["agreement"] == []
    assert result["truth_claimed"] is False


def test_missing_or_unknown_observation_remains_unknown() -> None:
    left = _obs("observer-a", {"claim-1": "UNKNOWN", "claim-2": "SUPPORT"})
    right = _obs("observer-b", {"claim-2": "SUPPORT"})

    result = compare_baseline_observations(left, right)

    assert result["unknown"] == ["claim-1"]
    assert result["agreement"] == ["claim-2"]


def test_different_baseline_state_cannot_be_compared_as_same_baseline() -> None:
    left = _obs("observer-a", {"claim-1": "SUPPORT"}, state="state-a")
    right = _obs("observer-b", {"claim-1": "SUPPORT"}, state="state-b")

    with pytest.raises(BaselineObservationError, match="same baseline_state_hash"):
        compare_baseline_observations(left, right)


def test_tampered_observation_is_rejected_and_inputs_are_not_mutated() -> None:
    left = _obs("observer-a", {"claim-1": "SUPPORT"})
    right = _obs("observer-b", {"claim-1": "SUPPORT"})
    original_left = copy.deepcopy(left)
    original_right = copy.deepcopy(right)

    compare_baseline_observations(left, right)

    assert left == original_left
    assert right == original_right

    tampered = copy.deepcopy(left)
    tampered["findings"]["claim-1"] = "CORRECTION"
    with pytest.raises(BaselineObservationError, match="hash does not match content"):
        compare_baseline_observations(tampered, right)
