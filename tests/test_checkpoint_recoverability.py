import pytest

from holosim.checkpoint_recoverability import (
    evaluate_checkpoint_recoverability,
)


def test_trapped_checkpoint_is_unreachable():
    transitions = {
        "trapped": ("failure",),
        "failure": (),
        "goal": (),
    }

    result = evaluate_checkpoint_recoverability(
        checkpoint="trapped",
        goal="goal",
        transitions=transitions,
        max_states=10,
    )

    assert result.status == "UNREACHABLE"
    assert result.path == ()


def test_earlier_checkpoint_has_escape():
    transitions = {
        "earlier": ("trapped", "escape"),
        "trapped": ("failure",),
        "escape": ("goal",),
        "failure": (),
        "goal": (),
    }

    result = evaluate_checkpoint_recoverability(
        checkpoint="earlier",
        goal="goal",
        transitions=transitions,
        max_states=10,
    )

    assert result.status == "REACHABLE"
    assert result.path == ("earlier", "escape", "goal")
def test_missing_branch_does_not_hide_reachable_goal():
    transitions = {
        "start": ("missing", "escape"),
        "escape": ("goal",),
        "goal": (),
    }

    result = evaluate_checkpoint_recoverability(
        checkpoint="start",
        goal="goal",
        transitions=transitions,
        max_states=10,
    )

    assert result.status == "REACHABLE"
    assert result.path == ("start", "escape", "goal")


def test_budget_boundary_still_checks_discovered_goal():
    transitions = {
        "start": ("goal",),
        "goal": (),
    }

    result = evaluate_checkpoint_recoverability(
        checkpoint="start",
        goal="goal",
        transitions=transitions,
        max_states=1,
    )

    assert result.status == "REACHABLE"
    assert result.path == ("start", "goal")

def test_cycle_without_goal_is_unreachable():
    transitions = {
        "start": ("middle",),
        "middle": ("start",),
        "goal": (),
    }

    result = evaluate_checkpoint_recoverability(
        checkpoint="start",
        goal="goal",
        transitions=transitions,
        max_states=10,
    )

    assert result.status == "UNREACHABLE"
    assert result.path == ()


def test_missing_transition_without_escape_is_unknown():
    transitions = {
        "start": ("missing",),
        "goal": (),
    }

    result = evaluate_checkpoint_recoverability(
        checkpoint="start",
        goal="goal",
        transitions=transitions,
        max_states=10,
    )

    assert result.status == "UNKNOWN"
    assert result.path == ()


def test_exhausted_search_budget_is_unknown():
    transitions = {
        "start": ("middle",),
        "middle": ("goal",),
        "goal": (),
    }

    result = evaluate_checkpoint_recoverability(
        checkpoint="start",
        goal="goal",
        transitions=transitions,
        max_states=1,
    )

    assert result.status == "UNKNOWN"
    assert result.path == ()


def test_undeclared_goal_is_unknown():
    transitions = {
        "start": ("goal",),
    }

    result = evaluate_checkpoint_recoverability(
        checkpoint="start",
        goal="goal",
        transitions=transitions,
        max_states=10,
    )

    assert result.status == "UNKNOWN"
    assert result.path == ()


@pytest.mark.parametrize(
    "max_states",
    [0, -1, True, 1.5],
)
def test_invalid_search_budget_is_rejected(max_states):
    with pytest.raises(ValueError):
        evaluate_checkpoint_recoverability(
            checkpoint="start",
            goal="goal",
            transitions={"start": (), "goal": ()},
            max_states=max_states,
        )


def test_invalid_successor_is_rejected():
    with pytest.raises(ValueError):
        evaluate_checkpoint_recoverability(
            checkpoint="start",
            goal="goal",
            transitions={"start": (None,), "goal": ()},
            max_states=10,
        )


def test_invalid_transition_collection_is_rejected():
    with pytest.raises(ValueError):
        evaluate_checkpoint_recoverability(
            checkpoint="start",
            goal="goal",
            transitions={"start": ["goal"], "goal": ()},
            max_states=10,
        )


def test_malformed_unvisited_branch_is_rejected():
    transitions = {
        "start": ("goal",),
        "goal": (),
        "malformed": ["unknown"],
    }

    with pytest.raises(ValueError):
        evaluate_checkpoint_recoverability(
            checkpoint="start",
            goal="goal",
            transitions=transitions,
            max_states=10,
        )


def test_oversized_successor_collection_is_rejected():
    transitions = {
        "start": tuple(f"state_{i}" for i in range(1001)),
        "goal": (),
    }

    with pytest.raises(ValueError):
        evaluate_checkpoint_recoverability(
            checkpoint="start",
            goal="goal",
            transitions=transitions,
            max_states=10,
        )


def test_oversized_declared_graph_is_rejected():
    transitions = {
        f"state_{i}": ()
        for i in range(10001)
    }
    transitions["start"] = ()
    transitions["goal"] = ()

    with pytest.raises(ValueError):
        evaluate_checkpoint_recoverability(
            checkpoint="start",
            goal="goal",
            transitions=transitions,
            max_states=10,
        )


def test_oversized_state_identifier_is_rejected():
    transitions = {
        "start": ("x" * 257,),
        "goal": (),
    }

    with pytest.raises(ValueError):
        evaluate_checkpoint_recoverability(
            checkpoint="start",
            goal="goal",
            transitions=transitions,
            max_states=10,
        )
