from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.interpretation import (
    compare_interpretations,
    record_interpretation,
    validate_interpretation_receipt,
)


def _receipt(*, rule: str, result: str) -> dict[str, object]:
    return record_interpretation(
        inputs={"claim": "the current state is supported"},
        rules=[rule],
        assumptions=["receipt hashes identify the compared evidence"],
        scope="current repository state",
        transformations=["compare the claim with the declared evidence"],
        result=result,
    )


def test_identical_interpretation_chain_cannot_explain_different_result() -> None:
    left = _receipt(
        rule="a claim is supported when current evidence matches it",
        result="supported",
    )
    right = _receipt(
        rule="a claim is supported when current evidence matches it",
        result="unsupported",
    )

    comparison = compare_interpretations(left, right)

    assert comparison["changed_dimensions"] == []
    assert comparison["result_changed"] is True
    assert comparison["difference_justified"] is False
    assert comparison["unexplained_result_difference"] is True
    assert comparison["valid"] is False


def test_declared_rule_change_explains_result_difference() -> None:
    left = _receipt(
        rule="any matching receipt supports the claim",
        result="supported",
    )
    right = _receipt(
        rule="only a current matching receipt supports the claim",
        result="unsupported",
    )

    comparison = compare_interpretations(left, right)

    assert comparison["changed_dimensions"] == ["rules"]
    assert comparison["result_changed"] is True
    assert comparison["difference_justified"] is True
    assert comparison["unexplained_result_difference"] is False
    assert comparison["valid"] is True


def test_receipt_hash_is_deterministic_and_tampering_is_rejected() -> None:
    first = _receipt(
        rule="a claim is supported when current evidence matches it",
        result="supported",
    )
    second = _receipt(
        rule="a claim is supported when current evidence matches it",
        result="supported",
    )

    assert first == second
    assert validate_interpretation_receipt(first) == first

    tampered = deepcopy(first)
    tampered["result"] = "unsupported"

    with pytest.raises(
        ValueError,
        match="receipt_hash does not match receipt body",
    ):
        validate_interpretation_receipt(tampered)
