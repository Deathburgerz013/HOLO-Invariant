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


def test_zero_step_episode_rejects_invented_current_state():
    from holosim.canonical import stable_hash

    episode = _episode()
    tampered = deepcopy(episode)
    tampered["current_state_reference"] = "state:invented"
    tampered.pop("episode_hash")
    tampered["episode_hash"] = stable_hash(tampered)

    assert tampered["step_count"] == 0
    assert tampered["steps"] == []
    with pytest.raises(
        AlignedObservationFeedbackError,
        match="current state mismatch",
    ):
        validate_observation_episode(tampered)


def test_recorded_episode_rejects_invented_final_state(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate()],
        allowed_root=tmp_path,
    )
    assert observed["step_count"] == 1
    assert validate_observation_episode(observed) is True

    tampered = deepcopy(observed)
    tampered["current_state_reference"] = "state:invented"
    tampered.pop("episode_hash")
    tampered["episode_hash"] = stable_hash(tampered)

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="current state mismatch",
    ):
        validate_observation_episode(tampered)


def test_rejects_forged_nested_observation_hash(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate()],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    observation = step["run"]["observation_result"]

    observation["result_hash"] = "a" * 64
    forged["current_state_reference"] = "observation:" + "a" * 64

    run = step["run"]
    run["run_hash"] = stable_hash({
        key: value for key, value in run.items()
        if key != "run_hash"
    })
    step["step_hash"] = stable_hash({
        key: value for key, value in step.items()
        if key != "step_hash"
    })
    forged["episode_hash"] = stable_hash({
        key: value for key, value in forged.items()
        if key != "episode_hash"
    })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="observation result hash mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_forged_selection_reference_state(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate()],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]

    selection["reference_state"] = "state:invented"

    for record, hash_field in (
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection reference state mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_ineligible_recorded_selection(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[
            _candidate(candidate_id="eligible"),
            _candidate(
                candidate_id="ineligible",
                uncertainty="HIGH",
            ),
        ],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]

    assert selection["selected_candidate_id"] == "eligible"

    selection["selected_candidate_id"] = "ineligible"

    for record, hash_field in (
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection candidate mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_forged_evaluation_eligibility(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[
            _candidate(candidate_id="eligible"),
            _candidate(candidate_id="ineligible", uncertainty="HIGH"),
        ],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]

    evaluation = next(
        item for item in selection["evaluations"]
        if item["candidate_id"] == "ineligible"
    )
    assert evaluation["judgment"]["status"] == "UNCERTAIN"
    assert evaluation["eligible"] is False

    evaluation["eligible"] = True

    for record, hash_field in (
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection eligibility mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_forged_judgment_status(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[
            _candidate(candidate_id="eligible"),
            _candidate(candidate_id="ineligible", uncertainty="HIGH"),
        ],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]

    evaluation = next(
        item for item in selection["evaluations"]
        if item["candidate_id"] == "ineligible"
    )
    judgment = evaluation["judgment"]

    assert judgment["uncertainty"] == "HIGH"
    assert judgment["status"] == "UNCERTAIN"

    judgment["status"] = "JUSTIFIED"
    evaluation["eligible"] = True

    for record, hash_field in (
        (judgment, "justification_hash"),
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection judgment mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_forged_attention_decision(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[
            _candidate(candidate_id="eligible"),
            _candidate(candidate_id="deferred", value=0, cost=1),
        ],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]

    evaluation = next(
        item for item in selection["evaluations"]
        if item["candidate_id"] == "deferred"
    )
    attention = evaluation["attention"]

    assert attention["score"] == -1
    assert attention["decision"] == "DEFER"

    attention["decision"] = "EARN_CYCLES"
    evaluation["eligible"] = True

    for record, hash_field in (
        (attention, "decision_hash"),
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection attention mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_mismatched_judgment_identity(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate(candidate_id="original")],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]
    evaluation = selection["evaluations"][0]
    judgment = evaluation["judgment"]

    assert evaluation["candidate_id"] == "original"
    assert judgment["judgment_id"] == "alignment:original"

    judgment["judgment_id"] = "alignment:someone-else"

    for record, hash_field in (
        (judgment, "justification_hash"),
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection judgment identity mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_mismatched_judgment_conclusion(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate(candidate_id="original")],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]
    evaluation = selection["evaluations"][0]
    judgment = evaluation["judgment"]

    assert judgment["conclusion"]["goal_reference"] == selection["goal_reference"]

    judgment["conclusion"]["goal_reference"] = "goal:unrelated"

    for record, hash_field in (
        (judgment, "justification_hash"),
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection judgment conclusion mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_mismatched_judgment_reference_state(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate(candidate_id="original")],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]
    evaluation = selection["evaluations"][0]
    judgment = evaluation["judgment"]

    assert judgment["reference_state"] == selection["reference_state"]

    judgment["reference_state"] = "state:unrelated"

    for record, hash_field in (
        (judgment, "justification_hash"),
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection judgment reference state mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_forged_candidate_capability(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate(candidate_id="original")],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]
    evaluation = selection["evaluations"][0]

    assert evaluation["capable"] is True

    evaluation["capable"] = False

    for record, hash_field in (
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection capability mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_mismatched_attention_candidate_identity(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[_candidate(candidate_id="original")],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]
    evaluation = selection["evaluations"][0]
    attention = evaluation["attention"]

    assert evaluation["candidate_id"] == "original"
    assert attention["candidate_id"] == "original"

    attention["candidate_id"] = "someone-else"

    for record, hash_field in (
        (attention, "decision_hash"),
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection attention candidate mismatch",
    ):
        validate_observation_episode(forged)


def test_rejects_invalid_unselected_candidate_request(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[
            _candidate(candidate_id="selected"),
            _candidate(candidate_id="unselected", value=1, cost=5),
        ],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]

    assert selection["selected_candidate_id"] == "selected"

    evaluation = next(
        item for item in selection["evaluations"]
        if item["candidate_id"] == "unselected"
    )
    request = evaluation["request"]
    judgment = evaluation["judgment"]

    request["request_hash"] = "0" * 64
    judgment["conclusion"]["request_hash"] = request["request_hash"]

    judgment_body = {
        key: value for key, value in judgment.items()
        if key != "justification_hash"
    }
    judgment["justification_hash"] = stable_hash(judgment_body)

    for record, hash_field in (
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="selection candidate request invalid",
    ):
        validate_observation_episode(forged)


def test_rejects_duplicate_recorded_candidate_identity(tmp_path):
    from holosim.canonical import stable_hash

    (tmp_path / "state.txt").write_bytes(b"observed")

    observed = advance_observation_episode(
        episode=_episode(),
        candidates=[
            _candidate(candidate_id="first"),
            _candidate(candidate_id="second", value=1, cost=5),
        ],
        allowed_root=tmp_path,
    )
    assert validate_observation_episode(observed) is True

    forged = deepcopy(observed)
    step = forged["steps"][0]
    run = step["run"]
    selection = run["selection"]
    evaluations = selection["evaluations"]

    assert len({item["candidate_id"] for item in evaluations}) == 2

    second = evaluations[1]
    second["candidate_id"] = evaluations[0]["candidate_id"]

    judgment = second["judgment"]
    judgment["judgment_id"] = f"alignment:{second['candidate_id']}"
    judgment["justification_hash"] = stable_hash({
        key: value for key, value in judgment.items()
        if key != "justification_hash"
    })

    attention = second["attention"]
    attention["candidate_id"] = second["candidate_id"]
    attention["decision_hash"] = stable_hash({
        key: value for key, value in attention.items()
        if key != "decision_hash"
    })

    for record, hash_field in (
        (selection, "selection_hash"),
        (run, "run_hash"),
        (step, "step_hash"),
        (forged, "episode_hash"),
    ):
        record[hash_field] = stable_hash({
            key: value for key, value in record.items()
            if key != hash_field
        })

    with pytest.raises(
        AlignedObservationFeedbackError,
        match="duplicate selection candidate identity",
    ):
        validate_observation_episode(forged)
