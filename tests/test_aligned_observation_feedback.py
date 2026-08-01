from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.aligned_observation_feedback import (
    AlignedObservationFeedbackError,
    advance_observation_episode,
    build_observation_episode,
    validate_observation_episode,
)
from holosim.hook_contract import build_hook_request


def _candidate(
    *,
    candidate_id: str = "discover-root",
    uncertainty: str = "LOW",
    value: float = 5,
    cost: float = 1,
) -> dict:
    request = build_hook_request(
        hook_id="local-computer",
        action="list_directory",
        reference=".",
        payload={"max_entries": 20},
    )
    return {
        "candidate_id": candidate_id,
        "request": request,
        "evidence_references": ["evidence:current-environment"],
        "rule_references": ["invariant:bounded-observation"],
        "comparison_status": "SUPPORTED",
        "uncertainty": uncertainty,
        "unresolved_conflicts": [],
        "value": value,
        "cost": cost,
        "urgency": 0,
        "dependency_impact": 0,
    }


def _episode(max_steps: int = 3) -> dict:
    return build_observation_episode(
        goal_reference="goal:observe-meaningful-change",
        initial_state_reference="state:initial",
        max_steps=max_steps,
    )


def test_repeated_observation_without_state_change_halts(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"unchanged")
    first = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate()],
        allowed_root=tmp_path,
    )

    assert first["status"] == "READY"
    assert first["step_count"] == 1
    assert first["steps"][0]["state_changed"] is True
    assert first["current_state_reference"].startswith("observation:")

    second = advance_observation_episode(
        episode=first,
        candidates=[_candidate()],
        allowed_root=tmp_path,
    )

    assert second["status"] == "HALT_NO_CHANGE"
    assert second["step_count"] == 2
    assert second["steps"][1]["state_changed"] is False
    assert second["current_state_reference"] == (
        first["current_state_reference"]
    )
    assert validate_observation_episode(second) is True


def test_changed_environment_advances_feedback_state(tmp_path):
    (tmp_path / "first.txt").write_bytes(b"first")
    first = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate()],
        allowed_root=tmp_path,
    )
    (tmp_path / "second.txt").write_bytes(b"second")

    second = advance_observation_episode(
        episode=first,
        candidates=[_candidate()],
        allowed_root=tmp_path,
    )

    assert second["status"] == "READY"
    assert second["step_count"] == 2
    assert second["steps"][1]["state_changed"] is True
    assert second["current_state_reference"] != (
        first["current_state_reference"]
    )
    assert len(second["observed_evidence_hashes"]) == 2


def test_step_budget_halts_after_last_allowed_observation(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"state")

    result = advance_observation_episode(
        episode=_episode(max_steps=1),
        candidates=[_candidate()],
        allowed_root=tmp_path,
    )

    assert result["status"] == "HALT_BUDGET"
    assert result["step_count"] == 1
    assert result["steps"][0]["run"]["execution_performed"] is True


def test_unaligned_candidates_halt_without_computer_execution(tmp_path):
    result = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate(uncertainty="HIGH")],
        allowed_root=tmp_path,
    )

    assert result["status"] == "HALT_UNALIGNED"
    assert result["step_count"] == 1
    assert result["steps"][0]["run"]["execution_performed"] is False
    assert result["steps"][0]["evidence_hash"] is None
    assert result["current_state_reference"] == "state:initial"


def test_tampered_episode_cannot_continue(tmp_path):
    episode = _episode()
    tampered = deepcopy(episode)
    tampered["max_steps"] = 99

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="hash mismatch",
    ):
        advance_observation_episode(
            episode=tampered,
            candidates=[_candidate()],
            allowed_root=tmp_path,
        )
