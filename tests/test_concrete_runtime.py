import pytest

from holosim.concrete_runtime import evaluate_runtime_cycle
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    InvariantViolation,
    ReplaceTransition,
    SubtractTransition,
)


def test_valid_invariant_does_not_grant_execution():
    result = evaluate_runtime_cycle(
        state=5,
        transition=SubtractTransition(amount=2),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )

    assert result.receipt_verified is True
    assert result.invariant_accepted is True
    assert result.candidate_state == 3
    assert result.resulting_state == 5
    assert result.status == "BLOCKED"
    assert result.reason == "NO_EXECUTION_AUTHORITY"
    assert result.validation == 0
    assert result.accepted is False
    assert result.write_authority == "NONE"
    assert result.execution_authority == "NONE"


def test_invalid_candidate_is_blocked():
    result = evaluate_runtime_cycle(
        state=5,
        transition=SubtractTransition(amount=8),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )

    assert result.receipt_verified is True
    assert result.invariant_accepted is False
    assert result.candidate_state == -3
    assert result.resulting_state == 5
    assert result.reason == "INVARIANT_REJECTED"
    assert result.validation == 0


def test_invalid_current_state_fails_closed():
    result = evaluate_runtime_cycle(
        state=-1,
        transition=ReplaceTransition(value=2),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )

    assert result.status == "BLOCKED"
    assert result.reason == "TRANSITION_EVALUATION_FAILED"
    assert result.previous_state == -1
    assert result.candidate_state is None
    assert result.resulting_state == -1
    assert result.invariant_accepted is False
    assert result.receipt_verified is False
    assert result.accepted is False
    assert result.write_authority == "NONE"
    assert result.execution_authority == "NONE"


def test_repeated_evaluation_does_not_change_state():
    arguments = {
        "state": 5,
        "transition": ReplaceTransition(value=4),
        "invariant": GreaterThanOrEqualInvariant(minimum=0),
    }

    first = evaluate_runtime_cycle(**arguments)
    second = evaluate_runtime_cycle(**arguments)

    assert first == second
    assert first.resulting_state == 5
    assert second.resulting_state == 5

@pytest.mark.parametrize("failure", ["false", "exception"])
def test_receipt_verification_failure_blocks(monkeypatch, failure):
    import holosim.concrete_runtime as runtime

    def failed_verification(receipt):
        if failure == "exception":
            raise ValueError("invalid receipt")
        return False

    monkeypatch.setattr(
        runtime,
        "verify_transition_receipt",
        failed_verification,
    )

    result = runtime.evaluate_runtime_cycle(
        state=5,
        transition=ReplaceTransition(value=4),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )

    assert result.status == "BLOCKED"
    assert result.reason == "RECEIPT_VERIFICATION_FAILED"
    assert result.previous_state == 5
    assert result.candidate_state is None
    assert result.resulting_state == 5
    assert result.receipt_verified is False
    assert result.invariant_accepted is False
    assert result.accepted is False
    assert result.write_authority == "NONE"
    assert result.execution_authority == "NONE"
