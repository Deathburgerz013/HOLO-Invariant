import pytest

from holosim.inv_runtime import GreaterThanOrEqualInvariant
from holosim.inv_source import INVSourceError, execute, parse


SOURCE = """state 5
invariant state >= 0
transition -1
"""


def test_parse_native_inv_source():
    program = parse(SOURCE)

    assert program.state == 5
    assert program.invariant == GreaterThanOrEqualInvariant(minimum=0)
    assert program.proposed_state == -1


def test_execute_rejects_invariant_violation_and_preserves_state():
    result = execute(SOURCE)

    assert result.accepted is False
    assert result.previous_state == 5
    assert result.proposed_state == -1
    assert result.state == 5


def test_execute_accepts_valid_transition():
    result = execute("""state 5
invariant state >= 0
transition 3
""")

    assert result.accepted is True
    assert result.state == 3


def test_unsupported_source_fails_closed():
    with pytest.raises(INVSourceError):
        execute("""state 5
invariant state < 10
transition 3
""")
