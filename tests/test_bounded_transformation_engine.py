from __future__ import annotations

import pytest

from holosim.bounded_transformation_engine import (
    replace_exact_once,
)


def test_replace_exact_once_returns_auditable_receipt():
    source = (
        "alpha\n"
        "target block\n"
        "omega\n"
    )

    receipt = replace_exact_once(
        source,
        expected="target block",
        replacement="replacement block",
    )

    assert receipt["status"] == "TRANSFORMED"
    assert receipt["changed"] is True
    assert receipt["match_count"] == 1
    assert receipt["source_text"] == source
    assert receipt["result_text"] == (
        "alpha\n"
        "replacement block\n"
        "omega\n"
    )
    assert receipt["source_hash"] != receipt["result_hash"]
    assert "-target block" in receipt["diff"]
    assert "+replacement block" in receipt["diff"]
    assert receipt["write_authority"] == "NONE"


@pytest.mark.parametrize(
    ("source", "expected", "message"),
    [
        (
            "alpha\nomega\n",
            "target block",
            "expected fragment was not found",
        ),
        (
            "target block\ntarget block\n",
            "target block",
            "expected fragment must occur exactly once",
        ),
    ],
)
def test_replace_exact_once_rejects_ambiguous_source(
    source,
    expected,
    message,
):
    with pytest.raises(ValueError, match=message):
        replace_exact_once(
            source,
            expected=expected,
            replacement="replacement block",
        )