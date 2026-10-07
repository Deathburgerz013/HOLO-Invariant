from dataclasses import replace

import pytest

from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_record import bind_receipt_bytes
from holosim.inv_receipt_record_encoding import encode_bound_receipt_record
from holosim.inv_receipt_record_identity import bound_receipt_record_content_id
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    ReplaceTransition,
    TransitionDecisionReceipt,
)
from holosim.inv_verification_receipt import (
    BoundVerificationReceipt,
    build_bound_verification_receipt,
    verify_bound_verification_receipt,
)
from holosim.inv_verification_receipt_encoding import (
    decode_bound_verification_receipt,
    encode_bound_verification_receipt,
)
from holosim.inv_verification_receipt_identity import (
    bound_verification_receipt_content_id,
)
from holosim.inv_verification_receipt_record import (
    BoundVerificationReceiptRecord,
    INVVerificationReceiptRecordError,
    bind_verification_receipt_bytes,
    verify_bound_verification_receipt_record,
)


def make_verification_receipt() -> BoundVerificationReceipt:
    transition_receipt = TransitionDecisionReceipt(
        previous_state=5,
        transition=ReplaceTransition(value=4),
        candidate_state=4,
        invariant=GreaterThanOrEqualInvariant(minimum=0),
        accepted=True,
        resulting_state=4,
    )
    encoded_receipt = encode_receipt(transition_receipt)
    bound_record = bind_receipt_bytes(encoded_receipt)
    encoded_record = encode_bound_receipt_record(bound_record)
    outer_content_id = bound_receipt_record_content_id(encoded_record)

    return build_bound_verification_receipt(
        encoded_record,
        outer_content_id,
    )


def test_binding_preserves_exact_bytes_and_derives_content_id():
    encoded = encode_bound_verification_receipt(make_verification_receipt())

    record = bind_verification_receipt_bytes(encoded)

    assert record.encoded_verification_receipt == encoded
    assert record.content_id == bound_verification_receipt_content_id(encoded)


def test_unchanged_bound_record_passes_binding_check():
    encoded = encode_bound_verification_receipt(make_verification_receipt())
    record = bind_verification_receipt_bytes(encoded)

    assert verify_bound_verification_receipt_record(record) is True


def test_changed_bytes_with_original_id_fail_binding_check():
    receipt = make_verification_receipt()
    original = encode_bound_verification_receipt(receipt)
    record = bind_verification_receipt_bytes(original)

    changed = encode_bound_verification_receipt(
        replace(receipt, semantic_verification_passed=False)
    )
    contradictory = replace(
        record,
        encoded_verification_receipt=changed,
    )

    assert verify_bound_verification_receipt_record(contradictory) is False


def test_changed_id_with_original_bytes_fails_binding_check():
    encoded = encode_bound_verification_receipt(make_verification_receipt())
    record = bind_verification_receipt_bytes(encoded)
    changed_id = (
        ("0" if record.content_id[0] != "0" else "1")
        + record.content_id[1:]
    )
    contradictory = replace(
        record,
        content_id=changed_id,
    )

    assert verify_bound_verification_receipt_record(contradictory) is False


@pytest.mark.parametrize(
    "encoded",
    [
        None,
        "",
        bytearray(b"abc"),
        memoryview(b"abc"),
    ],
)
def test_binding_rejects_unsupported_content_type(encoded):
    with pytest.raises(INVVerificationReceiptRecordError):
        bind_verification_receipt_bytes(encoded)


@pytest.mark.parametrize(
    "record",
    [
        None,
        object(),
        {},
    ],
)
def test_verifier_rejects_unsupported_record_type(record):
    with pytest.raises(INVVerificationReceiptRecordError):
        verify_bound_verification_receipt_record(record)


def test_verifier_rejects_unsupported_bound_bytes_type():
    record = BoundVerificationReceiptRecord(
        encoded_verification_receipt="not-bytes",
        content_id="0" * 64,
    )

    with pytest.raises(INVVerificationReceiptRecordError):
        verify_bound_verification_receipt_record(record)


def test_verifier_rejects_unsupported_bound_id_type():
    record = BoundVerificationReceiptRecord(
        encoded_verification_receipt=b"abc",
        content_id=None,
    )

    with pytest.raises(INVVerificationReceiptRecordError):
        verify_bound_verification_receipt_record(record)


@pytest.mark.parametrize(
    "content_id",
    [
        "",
        "0" * 63,
        "0" * 65,
        "g" * 64,
        "not-an-id",
    ],
)
def test_verifier_rejects_malformed_bound_content_id(content_id):
    record = BoundVerificationReceiptRecord(
        encoded_verification_receipt=b"abc",
        content_id=content_id,
    )

    with pytest.raises(INVVerificationReceiptRecordError):
        verify_bound_verification_receipt_record(record)


def test_valid_binding_does_not_validate_inner_contradiction():
    receipt = make_verification_receipt()
    changed_inner_id = (
        ("0" if receipt.verified_receipt_content_id[0] != "0" else "1")
        + receipt.verified_receipt_content_id[1:]
    )
    contradictory_receipt = replace(
        receipt,
        verified_receipt_content_id=changed_inner_id,
    )

    encoded = encode_bound_verification_receipt(contradictory_receipt)
    record = bind_verification_receipt_bytes(encoded)

    assert verify_bound_verification_receipt_record(record) is True

    reconstructed = decode_bound_verification_receipt(
        record.encoded_verification_receipt
    )

    assert reconstructed.verified_receipt_content_id == changed_inner_id
    assert verify_bound_verification_receipt(reconstructed) is False


def test_valid_binding_does_not_validate_false_outcome():
    contradictory_receipt = replace(
        make_verification_receipt(),
        semantic_verification_passed=False,
    )

    encoded = encode_bound_verification_receipt(contradictory_receipt)
    record = bind_verification_receipt_bytes(encoded)

    assert verify_bound_verification_receipt_record(record) is True

    reconstructed = decode_bound_verification_receipt(
        record.encoded_verification_receipt
    )

    assert reconstructed.semantic_verification_passed is False
    assert verify_bound_verification_receipt(reconstructed) is False


def test_valid_binding_does_not_confer_authority():
    contradictory_receipt = replace(
        make_verification_receipt(),
        execution_authority="GRANTED",
    )

    encoded = encode_bound_verification_receipt(contradictory_receipt)
    record = bind_verification_receipt_bytes(encoded)

    assert verify_bound_verification_receipt_record(record) is True

    reconstructed = decode_bound_verification_receipt(
        record.encoded_verification_receipt
    )

    assert reconstructed.execution_authority == "GRANTED"

    with pytest.raises(Exception):
        verify_bound_verification_receipt(reconstructed)


def test_binding_operates_on_exact_bytes_without_decoding():
    arbitrary = b"not a canonical verification receipt"

    record = bind_verification_receipt_bytes(arbitrary)

    assert record.encoded_verification_receipt == arbitrary
    assert verify_bound_verification_receipt_record(record) is True
