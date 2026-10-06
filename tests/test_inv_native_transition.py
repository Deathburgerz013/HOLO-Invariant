import pytest

from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    SubtractTransition,
    evaluate_transition,
    execute_inv_transition,
)
from holosim.inv_source import INVSourceError, execute, parse


SOURCE = """state 5
invariant state >= 0
transition subtract 6
"""


def test_parser_preserves_explicit_transition_semantic():
    program = parse(SOURCE)

    assert program.transition == SubtractTransition(amount=6)
    assert not callable(program.transition)


def test_transition_semantic_produces_candidate_without_mutating_input():
    state = 5
    candidate = evaluate_transition(SubtractTransition(amount=6), state)

    assert candidate == -1
    assert state == 5


def test_native_transition_is_gated_before_commit():
    result = execute_inv_transition(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )

    assert result.accepted is False
    assert result.proposed_state == -1
    assert result.state == 5


def test_source_execution_rejects_violating_native_transition():
    result = execute(SOURCE)

    assert result.accepted is False
    assert result.proposed_state == -1
    assert result.state == 5


def test_source_execution_accepts_valid_native_transition():
    result = execute("""state 5
invariant state >= 0
transition subtract 2
""")

    assert result.accepted is True
    assert result.state == 3


def test_unsupported_transition_source_fails_closed():
    with pytest.raises(INVSourceError):
        execute("""state 5
invariant state >= 0
transition multiply 2
""")


def test_unsupported_transition_semantic_fails_closed():
    with pytest.raises(TypeError):
        evaluate_transition(object(), 5)
