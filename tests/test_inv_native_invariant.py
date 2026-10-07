import pytest

from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    InvariantViolation,
    evaluate_invariant,
    transition_with_inv_invariant,
)
from holosim.inv_source import parse


def test_parser_preserves_explicit_inv_invariant_semantic():
    program = parse("""state 5
invariant state >= 0
transition -1
""")

    assert program.invariant == GreaterThanOrEqualInvariant(minimum=0)
    assert not callable(program.invariant)


def test_runtime_evaluates_native_invariant_semantic():
    invariant = GreaterThanOrEqualInvariant(minimum=0)

    assert evaluate_invariant(invariant, 5) is True
    assert evaluate_invariant(invariant, -1) is False


def test_native_invariant_rejects_transition_and_preserves_state():
    result = transition_with_inv_invariant(
        state=5,
        proposed_state=-1,
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )

    assert result.accepted is False
    assert result.state == 5


def test_invalid_current_state_fails_closed_with_native_invariant():
    with pytest.raises(InvariantViolation):
        transition_with_inv_invariant(
            state=-1,
            proposed_state=2,
            invariant=GreaterThanOrEqualInvariant(minimum=0),
        )


def test_unsupported_semantic_fails_closed():
    with pytest.raises(TypeError):
        evaluate_invariant(object(), 5)
