from __future__ import annotations

from copy import deepcopy
from holosim.canonical import stable_hash
import pytest

from holosim.bounded_transformation_engine import (
    replace_exact_once,
    verify_transformation_receipt,
)


def test_verify_transformation_receipt_accepts_valid_receipt():
    receipt = replace_exact_once(
        "alpha\ntarget\nomega\n",
        expected="target",
        replacement="replacement",
    )

    verification = verify_transformation_receipt(receipt)

    assert verification["status"] == "TRANSFORMATION_RECEIPT_VERIFIED"
    assert verification["verified_receipt_hash"] == receipt["receipt_hash"]
    assert verification["write_authority"] == "NONE"
    assert verification["execution_authority"] == "NONE"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "result_text",
            "alpha\ntampered\nomega\n",
            "result hash mismatch",
        ),
        (
            "source_text",
            "different source",
            "source hash mismatch",
        ),
        (
            "receipt_hash",
            "wrong-hash",
            "receipt hash mismatch",
        ),
        (
            "replacement_fragment",
            "different replacement",
            "declared transformation does not reproduce result",
        ),
    ],
)
def test_verify_transformation_receipt_rejects_tampering(
    field,
    value,
    message,
):
    receipt = replace_exact_once(
        "alpha\ntarget\nomega\n",
        expected="target",
        replacement="replacement",
    )

    tampered = deepcopy(receipt)
    tampered[field] = value

    with pytest.raises(ValueError, match=message):
        verify_transformation_receipt(tampered)


@pytest.mark.parametrize(
    "receipt",
    [
        None,
        True,
        "receipt",
        [],
        {},
    ],
)
def test_verify_transformation_receipt_rejects_malformed_receipt(
    receipt,
):
    with pytest.raises(
        ValueError,
        match="invalid transformation receipt",
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
def test_verify_transformation_receipt_rejects_forged_authority(
    field,
    forged_value,
):
    receipt = replace_exact_once(
        "alpha\ntarget\nomega\n",
        expected="target",
        replacement="replacement",
    )

    receipt[field] = forged_value
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    receipt["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        ValueError,
        match="invalid transformation authority boundaries",
    ):
        verify_transformation_receipt(receipt)
def test_verify_transformation_receipt_rejects_undeclared_field():
    receipt = replace_exact_once(
        "alpha\ntarget\nomega\n",
        expected="target",
        replacement="replacement",
    )

    receipt["undeclared_claim"] = "GRANTED"
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    receipt["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        ValueError,
        match="invalid transformation receipt schema",
    ):
        verify_transformation_receipt(receipt)