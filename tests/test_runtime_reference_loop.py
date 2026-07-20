import copy

import pytest

from holosim.runtime import HoloRuntime


def _prior_items():
    return [
        {"id": "a", "requires": ["b"], "state": "supported", "value": 1},
        {"id": "b", "requires": ["c"], "state": "supported", "value": 2},
        {"id": "c", "requires": [], "state": "supported", "value": 3},
        {"id": "x", "requires": [], "state": "unrelated", "value": 99},
    ]


def _reachable_state():
    return [
        {"id": "a", "requires": ["b"], "state": "supported", "value": 1},
        {"id": "b", "requires": ["c"], "state": "supported", "value": 2},
        {"id": "c", "requires": [], "state": "supported", "value": 3},
    ]


def test_reference_loop_reconstructs_compares_and_stops_at_no_difference(tmp_path):
    runtime = HoloRuntime(tmp_path / "chain.jsonl")
    changed = _reachable_state()
    changed[1]["value"] = 200
    current = _reachable_state()
    later = _reachable_state()
    later[0]["value"] = 999

    result = runtime.reference_loop(
        reference="current task",
        target_ids=["a"],
        prior_items=_prior_items(),
        observations=[changed, current, later],
    )

    assert result["status"] == "NO_RELEVANT_DIFFERENCE"
    assert result["reconstructed_state"]["reachable_ids"] == ["a", "b", "c"]
    assert [item["id"] for item in result["reconstructed_state"]["carried_items"]] == ["a", "b", "c"]
    assert len(result["manifests"]) == 2
    assert result["correction_cycle"]["steps"][0]["correction_targets"] == ["b"]
    assert result["correction_cycle"]["steps"][1]["status"] == "NO_RELEVANT_DIFFERENCE"
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_reference_loop_added_environmental_growth_does_not_keep_cycle_open(tmp_path):
    runtime = HoloRuntime(tmp_path / "chain.jsonl")
    present = _reachable_state()
    present.append({"id": "new", "requires": [], "state": "supported", "value": 4})

    result = runtime.reference_loop(
        reference="growth",
        target_ids=["a"],
        prior_items=_prior_items(),
        observations=[present],
    )

    assert result["status"] == "NO_RELEVANT_DIFFERENCE"
    assert result["manifests"][0]["added_ids"] == ["new"]
    assert result["correction_cycle"]["next_correction_targets"] == []


def test_reference_loop_remains_open_when_last_observation_has_difference(tmp_path):
    runtime = HoloRuntime(tmp_path / "chain.jsonl")
    present = _reachable_state()
    present = [item for item in present if item["id"] != "c"]

    result = runtime.reference_loop(
        reference="missing dependency",
        target_ids=["a"],
        prior_items=_prior_items(),
        observations=[present],
    )

    assert result["status"] == "CORRECTION_REQUIRED"
    assert result["correction_cycle"]["next_correction_targets"] == ["c"]
    assert result["correction_cycle"]["terminal_index"] is None


def test_reference_loop_does_not_mutate_inputs(tmp_path):
    runtime = HoloRuntime(tmp_path / "chain.jsonl")
    prior = _prior_items()
    observations = [_reachable_state()]
    prior_before = copy.deepcopy(prior)
    observations_before = copy.deepcopy(observations)

    runtime.reference_loop(
        reference="immutability",
        target_ids=["a"],
        prior_items=prior,
        observations=observations,
    )

    assert prior == prior_before
    assert observations == observations_before


def test_reference_loop_requires_at_least_one_observation(tmp_path):
    runtime = HoloRuntime(tmp_path / "chain.jsonl")

    with pytest.raises(ValueError, match="observations must be a nonempty"):
        runtime.reference_loop(
            reference="empty",
            target_ids=["a"],
            prior_items=_prior_items(),
            observations=[],
        )
