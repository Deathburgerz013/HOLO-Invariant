from __future__ import annotations

import pytest

from holosim.bounded_transformation_engine import (
    replace_exact_once_validated,
)
from holosim.canonical import stable_hash


def test_validated_replacement_requires_matching_result_hash():
    expected_result = "alpha\nreplacement\nomega\n"

    def validator(result_text: str) -> dict[str, object]:
        return {
            "status": "VALID",
            "validated_result_hash": stable_hash(result_text),
        }

    receipt = replace_exact_once_validated(
        "alpha\ntarget\nomega\n",
        expected="target",
        replacement="replacement",
        validator=validator,
    )

    assert receipt["result_text"] == expected_result
    assert receipt["validator_receipt"][
        "validated_result_hash"
    ] == receipt["result_hash"]


@pytest.mark.parametrize(
    "validator_receipt",
    [
        {
            "status": "VALID",
        },
        {
            "status": "VALID",
            "validated_result_hash": "wrong-hash",
        },
    ],
)
def test_validated_replacement_rejects_unbound_validation(
    validator_receipt,
):
    def validator(_result_text: str) -> dict[str, object]:
        return validator_receipt

    with pytest.raises(
        ValueError,
        match="validator receipt is not bound to transformed result",
    ):
        replace_exact_once_validated(
            "alpha\ntarget\nomega\n",
            expected="target",
            replacement="replacement",
            validator=validator,
        )