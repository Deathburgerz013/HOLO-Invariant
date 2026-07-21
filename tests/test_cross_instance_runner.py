from copy import deepcopy

from holosim.baseline_promotion_gate import (
    STATUS_CONFLICTED,
    STATUS_JUSTIFIED_TO_PROPOSE,
)
from holosim.cross_instance_runner import run_cross_instance_baseline_check


def test_runner_composes_full_vertical_slice_without_authority():
    result = run_cross_instance_baseline_check(
        baseline_id="baseline-1",
        baseline_state_hash="state-abc",
        left_observer_id="observer-a",
        left_findings={
            "claim-stable": "SUPPORT",
            "claim-new": "EXTENSION",
        },
        right_observer_id="observer-b",
        right_findings={
            "claim-stable": "SUPPORT",
            "claim-new": "EXTENSION",
        },
        justification_references={"claim-new": "evidence:new"},
    )

    assert result["summary"] == {
        "agreement": ["claim-stable"],
        "extension": ["claim-new"],
        "correction": [],
        "conflict": [],
        "unknown": [],
        "proposal_status": STATUS_JUSTIFIED_TO_PROPOSE,
    }
    assert result["promotion_gate"]["status"] == STATUS_JUSTIFIED_TO_PROPOSE
    assert result["next_baseline_created"] is False
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_runner_exposes_conflict_and_blocks_proposal():
    result = run_cross_instance_baseline_check(
        baseline_id="baseline-1",
        baseline_state_hash="state-abc",
        left_observer_id="observer-a",
        left_findings={"claim-x": "CORRECTION"},
        right_observer_id="observer-b",
        right_findings={"claim-x": "SUPPORT"},
        justification_references={"claim-x": "evidence:x"},
    )

    assert result["summary"]["conflict"] == ["claim-x"]
    assert result["summary"]["proposal_status"] == STATUS_CONFLICTED
    assert result["promotion_gate"]["candidate_next_baseline_created"] is False


def test_runner_is_deterministic_for_same_inputs():
    kwargs = dict(
        baseline_id="baseline-2",
        baseline_state_hash="state-def",
        left_observer_id="observer-a",
        left_findings={"claim-a": "SUPPORT", "claim-b": "CORRECTION"},
        right_observer_id="observer-b",
        right_findings={"claim-a": "SUPPORT", "claim-b": "CORRECTION"},
        justification_references={"claim-b": "evidence:b"},
    )

    first = run_cross_instance_baseline_check(**kwargs)
    second = run_cross_instance_baseline_check(**deepcopy(kwargs))

    assert first == second
    assert first["run_id"] == second["run_id"]


def test_runner_preserves_exact_observer_provenance():
    result = run_cross_instance_baseline_check(
        baseline_id="baseline-3",
        baseline_state_hash="state-ghi",
        left_observer_id="instance-left",
        left_findings={"claim-a": "SUPPORT"},
        right_observer_id="instance-right",
        right_findings={"claim-a": "SUPPORT"},
        justification_references={},
    )

    assert [item["observer_id"] for item in result["observations"]] == [
        "instance-left",
        "instance-right",
    ]
    assert result["comparison"]["left_observation_id"] == result["observations"][0]["observation_id"]
    assert result["comparison"]["right_observation_id"] == result["observations"][1]["observation_id"]
    assert result["promotion_gate"]["comparison_id"] == result["comparison"]["comparison_id"]
