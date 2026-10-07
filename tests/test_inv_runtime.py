from holosim.inv_runtime import InvariantViolation, transition


def nonnegative(value: int) -> bool:
    return value >= 0


def test_transition_accepts_state_that_preserves_invariant():
    result = transition(
        state=5,
        proposed_state=3,
        invariant=nonnegative,
    )

    assert result.accepted is True
    assert result.previous_state == 5
    assert result.proposed_state == 3
    assert result.state == 3


def test_transition_rejects_state_that_violates_invariant():
    result = transition(
        state=5,
        proposed_state=-1,
        invariant=nonnegative,
    )

    assert result.accepted is False
    assert result.previous_state == 5
    assert result.proposed_state == -1
    assert result.state == 5


def test_invalid_current_state_fails_closed():
    try:
        transition(
            state=-1,
            proposed_state=2,
            invariant=nonnegative,
        )
    except InvariantViolation:
        return

    raise AssertionError("invalid current state was accepted")
