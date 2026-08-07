from __future__ import annotations

import pytest

from holosim.bounded_transformation_engine import (
    replace_exact_once_validated,
)
from holosim.canonical import stable_hash


def test_validated_replacement_returns_validator_receipt():
    def validator(result_text: str) -> dict[str, object]:
        return {
            "status": "VALID",
            "checked_text": result_text,
            "validated_result_hash": stable_hash(result_text),
        }

    receipt = replace_exact_once_validated(
        "alpha\ntarget\nomega\n",
        expected="target",
        replacement="replacement",
        validator=validator,
    )

    assert receipt["status"] == "TRANSFORMED_AND_VALIDATED"
    assert receipt["validation_status"] == "VALID"
    assert receipt["validator_receipt"] == {
        "status": "VALID",
        "checked_text": "alpha\nreplacement\nomega\n",
        "validated_result_hash": receipt["result_hash"],
    }
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_validated_replacement_rejects_failed_validation():
    def validator(_result_text: str) -> dict[str, object]:
        return {
            "status": "INVALID",
            "reason": "domain check failed",
        }

    with pytest.raises(
        ValueError,
        match="transformed result failed validation",
    ):
        replace_exact_once_validated(
            "alpha\ntarget\nomega\n",
            expected="target",
            replacement="replacement",
            validator=validator,
        )


@pytest.mark.parametrize(
    "validator_result",
    [
        None,
        True,
        "VALID",
        [],
        {},
        {"reason": "missing status"},
    ],
)
def test_validated_replacement_rejects_invalid_validator_receipt(
    validator_result,
):
    def validator(_result_text: str):
        return validator_result

    with pytest.raises(
        ValueError,
        match="validator must return a receipt with status VALID",
    ):
        replace_exact_once_validated(
            "alpha\ntarget\nomega\n",
            expected="target",
            replacement="replacement",
            validator=validator,
        )


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
    ],
)
def test_validated_replacement_rejects_validator_authority(
    field,
    forged_value,
):
    def validator(result_text: str) -> dict[str, object]:
        return {
            "status": "VALID",
            "validated_result_hash": stable_hash(result_text),
            field: forged_value,
        }

    with pytest.raises(
        ValueError,
        match="invalid validator receipt authority boundaries",
    ):
        replace_exact_once_validated(
            "alpha\ntarget\nomega\n",
            expected="target",
            replacement="replacement",
            validator=validator,
        )