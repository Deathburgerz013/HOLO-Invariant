from __future__ import annotations

from copy import deepcopy

from holosim.aligned_action_selector import run_aligned_observation
from holosim.hook_contract import build_hook_request, validate_hook_result


def _request(*, action: str, reference: str, payload: dict) -> dict:
    return build_hook_request(
        hook_id="local-computer",
        action=action,
        reference=reference,
        payload=payload,
    )


def _candidate(
    *,
    candidate_id: str,
    request: dict,
    value: float = 5,
    cost: float = 1,
    urgency: float = 0,
    dependency_impact: float = 0,
    comparison_status: str = "SUPPORTED",
    uncertainty: str = "LOW",
    conflicts: list[dict] | None = None,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "request": request,
        "evidence_references": ["evidence:current-environment"],
        "rule_references": ["invariant:bounded-observation"],
        "comparison_status": comparison_status,
        "uncertainty": uncertainty,
        "unresolved_conflicts": conflicts or [],
        "value": value,
        "cost": cost,
        "urgency": urgency,
        "dependency_impact": dependency_impact,
    }


def test_alignment_selects_and_executes_one_justified_observation(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"state")
    discover = _candidate(
        candidate_id="discover-root",
        request=_request(
            action="list_directory",
            reference=".",
            payload={"max_entries": 20},
        ),
        value=7,
        cost=2,
        dependency_impact=3,
    )
    deferred = _candidate(
        candidate_id="read-known-state",
        request=_request(
            action="read_text",
            reference="state.txt",
            payload={"encoding": "utf-8"},
        ),
        value=1,
        cost=5,
    )

    result = run_aligned_observation(
        goal_reference="goal:understand-current-root",
        reference_state="state:before-observation",
        candidates=[deferred, discover],
        allowed_root=tmp_path,
    )

    assert result["selection"]["decision"] == "SELECTED"
    assert result["selection"]["selected_candidate_id"] == "discover-root"
    assert result["execution_performed"] is True
    assert result["observation_result"]["status"] == "OBSERVED"
    assert result["observation_result"]["evidence"]["operation"] == (
        "list_directory"
    )
    assert result["observation_result"]["evidence"]["entries"] == [
        {"name": "state.txt", "kind": "file"}
    ]
    assert validate_hook_result(
        result["observation_result"],
        request=result["selection"]["selected_request"],
    ) is True
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_conflicted_candidate_cannot_win_on_attention_score(tmp_path):
    (tmp_path / "safe.txt").write_bytes(b"safe")
    conflicted = _candidate(
        candidate_id="conflicted-high-score",
        request=_request(
            action="list_directory",
            reference=".",
            payload={"max_entries": 20},
        ),
        value=100,
        conflicts=[{"id": "conflict:goal-mismatch"}],
    )
    justified = _candidate(
        candidate_id="justified-lower-score",
        request=_request(
            action="read_text",
            reference="safe.txt",
            payload={"encoding": "utf-8"},
        ),
        value=4,
        cost=1,
    )

    result = run_aligned_observation(
        goal_reference="goal:observe-safe-state",
        reference_state="state:current",
        candidates=[conflicted, justified],
        allowed_root=tmp_path,
    )

    assert result["selection"]["selected_candidate_id"] == (
        "justified-lower-score"
    )
    evaluations = {
        item["candidate_id"]: item
        for item in result["selection"]["evaluations"]
    }
    assert evaluations["conflicted-high-score"]["eligible"] is False
    assert evaluations["conflicted-high-score"]["judgment"]["status"] == (
        "CONFLICTED"
    )


def test_alignment_halts_when_no_candidate_is_justified_and_attended(tmp_path):
    uncertain = _candidate(
        candidate_id="uncertain",
        request=_request(
            action="list_directory",
            reference=".",
            payload={"max_entries": 20},
        ),
        uncertainty="HIGH",
    )
    deferred = _candidate(
        candidate_id="deferred",
        request=_request(
            action="list_directory",
            reference=".",
            payload={"max_entries": 20},
        ),
        value=1,
        cost=3,
    )

    result = run_aligned_observation(
        goal_reference="goal:remain-aligned",
        reference_state="state:current",
        candidates=[uncertain, deferred],
        allowed_root=tmp_path,
    )

    assert result["selection"]["decision"] == "HALT"
    assert result["selection"]["selected_candidate_id"] is None
    assert result["selection"]["selected_request"] is None
    assert result["execution_performed"] is False
    assert result["observation_result"] is None


def test_selection_is_deterministic_under_candidate_reordering(tmp_path):
    candidates = [
        _candidate(
            candidate_id="candidate-b",
            request=_request(
                action="list_directory",
                reference=".",
                payload={"max_entries": 10},
            ),
        ),
        _candidate(
            candidate_id="candidate-a",
            request=_request(
                action="list_directory",
                reference=".",
                payload={"max_entries": 20},
            ),
        ),
    ]

    first = run_aligned_observation(
        goal_reference="goal:deterministic-choice",
        reference_state="state:same",
        candidates=candidates,
        allowed_root=tmp_path,
    )
    second = run_aligned_observation(
        goal_reference="goal:deterministic-choice",
        reference_state="state:same",
        candidates=list(reversed(deepcopy(candidates))),
        allowed_root=tmp_path,
    )

    assert first == second
    assert first["selection"]["selected_candidate_id"] == "candidate-a"
