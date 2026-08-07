from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.bounded_transformation_engine import (
    replace_exact_once_validated,
    verify_transformation_receipt,
)
from holosim.canonical import stable_hash


def _validated_receipt() -> dict[str, object]:
    def validator(result_text: str) -> dict[str, object]:
        return {
            "status": "VALID",
            "validated_result_hash": stable_hash(result_text),
        }

    return replace_exact_once_validated(
        "alpha\ntarget\nomega\n",
        expected="target",
        replacement="replacement",
        validator=validator,
    )


def _rehash(receipt: dict[str, object]) -> None:
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    receipt["receipt_hash"] = stable_hash(body)


def test_verify_validated_transformation_receipt_accepts_proof():
    receipt = _validated_receipt()

    verification = verify_transformation_receipt(receipt)

    assert verification["status"] == (
        "TRANSFORMATION_RECEIPT_VERIFIED"
    )
    assert verification["verified_receipt_hash"] == (
        receipt["receipt_hash"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "remove_validation_status",
        "invalidate_validation_status",
        "remove_validator_receipt",
        "invalidate_validator_status",
        "remove_validated_result_hash",
        "mismatch_validated_result_hash",
    ],
)
def test_verify_validated_transformation_receipt_rejects_false_claim(
    mutation,
):
    receipt = deepcopy(_validated_receipt())

    if mutation == "remove_validation_status":
        receipt.pop("validation_status")
    elif mutation == "invalidate_validation_status":
        receipt["validation_status"] = "INVALID"
    elif mutation == "remove_validator_receipt":
        receipt.pop("validator_receipt")
    elif mutation == "invalidate_validator_status":
        receipt["validator_receipt"]["status"] = "INVALID"
    elif mutation == "remove_validated_result_hash":
        receipt["validator_receipt"].pop(
            "validated_result_hash"
        )
    elif mutation == "mismatch_validated_result_hash":
        receipt["validator_receipt"][
            "validated_result_hash"
        ] = "wrong-hash"

    _rehash(receipt)

    with pytest.raises(
        ValueError,
        match="invalid validated transformation receipt",
    ):
        verify_transformation_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
    ],
)
def test_verify_validated_transformation_rejects_nested_authority(
    field,
    forged_value,
):
    receipt = deepcopy(_validated_receipt())
    receipt["validator_receipt"][field] = forged_value
    _rehash(receipt)

    with pytest.raises(
        ValueError,
        match="invalid validator receipt authority boundaries",
    ):
        verify_transformation_receipt(receipt)
def test_verify_validated_transformation_rejects_status_downgrade():
    receipt = deepcopy(_validated_receipt())
    receipt["status"] = "TRANSFORMED"
    _rehash(receipt)

    with pytest.raises(
        ValueError,
        match="invalid transformation receipt schema",
    ):
        verify_transformation_receipt(receipt)