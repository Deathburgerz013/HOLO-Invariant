from dataclasses import replace

import pytest

from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_record import (
    BoundReceiptRecord,
    bind_receipt_bytes,
)
from holosim.inv_receipt_record_encoding import (
    encode_bound_receipt_record,
)
from holosim.inv_receipt_record_identity import (
    bound_receipt_record_content_id,
)
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    SubtractTransition,
    execute_inv_transition_with_receipt,
)
from holosim.inv_verification_receipt import (
    BoundVerificationReceipt,
    INVVerificationReceiptError,
    build_bound_verification_receipt,
    verify_bound_verification_receipt,
)


def make_encoded_record():
    receipt = execute_inv_transition_with_receipt(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )
    record = bind_receipt_bytes(encode_receipt(receipt))
    return encode_bound_receipt_record(record)


def make_verification_receipt():
    encoded = make_encoded_record()
    outer_id = bound_receipt_record_content_id(encoded)
    return build_bound_verification_receipt(encoded, outer_id)


def test_successful_verification_produces_bounded_receipt():
    receipt = make_verification_receipt()

    assert receipt.outer_identity_verified is True
    assert receipt.canonical_record_verified is True
    assert receipt.inner_binding_verified is True
    assert receipt.receipt_reconstructed is True
    assert receipt.semantic_verification_passed is True
    assert receipt.accepted is False
    assert receipt.truth_claimed is False
    assert receipt.write_authority == "NONE"
    assert receipt.execution_authority == "NONE"
    assert verify_bound_verification_receipt(receipt) is True


def test_equivalent_inputs_produce_equivalent_receipts():
    encoded = make_encoded_record()
    outer_id = bound_receipt_record_content_id(encoded)

    first = build_bound_verification_receipt(encoded, outer_id)
    second = build_bound_verification_receipt(encoded, outer_id.upper())

    assert first == second


def test_failed_experiment_014_verification_produces_no_receipt():
    encoded = make_encoded_record()
    outer_id = bound_receipt_record_content_id(encoded)

    changed = (
        ("0" if outer_id[0] != "0" else "1")
        + outer_id[1:]
    )

    with pytest.raises(
        INVVerificationReceiptError,
        match="bound record verification failed",
    ):
        build_bound_verification_receipt(encoded, changed)


def test_invalid_inner_binding_produces_no_receipt():
    encoded = make_encoded_record()

    from holosim.inv_receipt_record_encoding import (
        decode_bound_receipt_record,
    )

    record = decode_bound_receipt_record(encoded)
    invalid = BoundReceiptRecord(
        encoded_receipt=record.encoded_receipt,
        content_id="0" * 64,
    )
    invalid_encoded = encode_bound_receipt_record(invalid)
    outer_id = bound_receipt_record_content_id(invalid_encoded)

    with pytest.raises(INVVerificationReceiptError):
        build_bound_verification_receipt(
            invalid_encoded,
            outer_id,
        )


@pytest.mark.parametrize(
    "field",
    [
        "outer_identity_verified",
        "canonical_record_verified",
        "inner_binding_verified",
        "receipt_reconstructed",
        "semantic_verification_passed",
    ],
)
def test_tampered_check_outcome_is_rejected(field):
    receipt = make_verification_receipt()
    tampered = replace(receipt, **{field: False})

    assert verify_bound_verification_receipt(tampered) is False


def test_tampered_observed_outer_id_is_rejected():
    receipt = make_verification_receipt()
    changed = (
        ("0" if receipt.observed_outer_content_id[0] != "0" else "1")
        + receipt.observed_outer_content_id[1:]
    )

    tampered = replace(
        receipt,
        observed_outer_content_id=changed,
    )

    assert verify_bound_verification_receipt(tampered) is False


def test_tampered_verified_receipt_identity_is_not_silently_malformed():
    receipt = make_verification_receipt()

    tampered = replace(
        receipt,
        verified_receipt_content_id="not-an-id",
    )

    with pytest.raises(INVVerificationReceiptError):
        verify_bound_verification_receipt(tampered)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "WRITE"),
        ("execution_authority", "EXECUTE"),
    ],
)
def test_authority_bearing_receipt_is_rejected(field, value):
    receipt = make_verification_receipt()
    tampered = replace(receipt, **{field: value})

    with pytest.raises(INVVerificationReceiptError):
        verify_bound_verification_receipt(tampered)


def test_receipt_verifier_does_not_require_underlying_record():
    receipt = make_verification_receipt()

    assert verify_bound_verification_receipt(receipt) is True


def test_receipt_validity_does_not_reverify_changed_underlying_record():
    receipt = make_verification_receipt()
    encoded = make_encoded_record()

    changed_record = (
        (b"0" if encoded[:1] != b"0" else b"1")
        + encoded[1:]
    )

    assert changed_record != encoded
    assert verify_bound_verification_receipt(receipt) is True


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        "receipt",
    ],
)
def test_unsupported_receipt_type_fails_closed(value):
    with pytest.raises(INVVerificationReceiptError):
        verify_bound_verification_receipt(value)


def test_receipt_is_frozen():
    receipt = make_verification_receipt()

    with pytest.raises(Exception):
        receipt.accepted = True
