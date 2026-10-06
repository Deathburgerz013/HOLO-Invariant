import pytest

from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    ReplaceTransition,
    SubtractTransition,
    evaluate_transition,
    execute_inv_transition,
)
from holosim.inv_source import execute, parse


REPLACE_SOURCE = """state 5
invariant state >= 0
transition -1
"""

SUBTRACT_SOURCE = """state 5
invariant state >= 0
transition subtract 6
"""


def test_replacement_source_parses_to_explicit_transition_semantic():
    program = parse(REPLACE_SOURCE)

    assert program.transition == ReplaceTransition(value=-1)
    assert not callable(program.transition)
    assert not hasattr(program, "proposed_state")


def test_subtraction_source_remains_explicit_transition_semantic():
    program = parse(SUBTRACT_SOURCE)

    assert program.transition == SubtractTransition(amount=6)
    assert not callable(program.transition)


@pytest.mark.parametrize(
    ("transition", "expected"),
    [
        (ReplaceTransition(value=-1), -1),
        (SubtractTransition(amount=6), -1),
    ],
)
def test_both_transition_semantics_share_evaluation_path(transition, expected):
    assert evaluate_transition(transition, 5) == expected


@pytest.mark.parametrize("source", [REPLACE_SOURCE, SUBTRACT_SOURCE])
def test_both_source_forms_share_rejection_behavior(source):
    result = execute(source)

    assert result.accepted is False
    assert result.previous_state == 5
    assert result.proposed_state == -1
    assert result.state == 5


def test_replacement_transition_can_be_accepted_through_native_path():
    result = execute("""state 5
invariant state >= 0
transition 3
""")

    assert result.accepted is True
    assert result.previous_state == 5
    assert result.proposed_state == 3
    assert result.state == 3


def test_unsupported_transition_semantic_still_fails_closed():
    with pytest.raises(TypeError):
        execute_inv_transition(
            state=5,
            transition=object(),
            invariant=GreaterThanOrEqualInvariant(minimum=0),
        )
