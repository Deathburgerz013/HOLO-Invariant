import pytest

from holosim.inv_source import parse


def test_source_accepts_multiple_transitions():
    source = """\
state 5
invariant state >= 0
transition subtract 2
transition subtract 10
transition 7
"""
    program = parse(source)
    assert len(program.transitions) == 3


from holosim.inv_source import execute_sequence


def test_sequential_transitions_preserve_rejected_state():
    source = """\
state 5
invariant state >= 0
transition subtract 2
transition subtract 10
transition 7
"""
    result = execute_sequence(source)

    assert result.final_state == 7
    assert [receipt.accepted for receipt in result.receipts] == [
        True, False, True
    ]
    assert [receipt.resulting_state for receipt in result.receipts] == [
        3, 3, 7
    ]

from dataclasses import replace

from holosim.inv_runtime import verify_transition_receipt


def test_sequence_receipts_are_independently_verifiable():
    result = execute_sequence("""\
state 5
invariant state >= 0
transition subtract 2
transition subtract 10
transition 7
""")

    assert all(verify_transition_receipt(r) for r in result.receipts)

    altered = replace(result.receipts[1], resulting_state=-7)
    assert verify_transition_receipt(altered) is False

    assert all(
        previous.resulting_state == current.previous_state
        for previous, current in zip(result.receipts, result.receipts[1:])
    )

@pytest.mark.parametrize("source", [
    "",
    "state 5",
    "state 5\ninvariant state >= 0",
    "state 5\ninvariant state >= 0\ntransition",
    "state 5\ninvariant state >= 0\ntransition subtract nope",
    "state 5\ninvariant state >= 0\ntransition 2\ntransition multiply 3",
    "state 5\ninvariant state < 10\ntransition 2",
])
def test_sequence_rejects_invalid_source(source):
    from holosim.inv_source import INVSourceError

    with pytest.raises(INVSourceError):
        execute_sequence(source)


def test_sequence_rejects_invalid_initial_state():
    from holosim.inv_runtime import InvariantViolation

    with pytest.raises(InvariantViolation):
        execute_sequence("""\
state -1
invariant state >= 0
transition 5
""")
