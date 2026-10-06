import pytest

from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_record import (
    BoundReceiptRecord,
    bind_receipt_bytes,
    verify_bound_receipt_record,
)
from holosim.inv_receipt_record_encoding import encode_bound_receipt_record
from holosim.inv_receipt_record_identity import (
    INVReceiptRecordIdentityError,
    bound_receipt_record_content_id,
    verify_bound_receipt_record_content_id,
)
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    SubtractTransition,
    execute_inv_transition_with_receipt,
)


def make_record():
    receipt = execute_inv_transition_with_receipt(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )
    return bind_receipt_bytes(encode_receipt(receipt))


def test_identical_canonical_record_bytes_have_same_content_id():
    first = encode_bound_receipt_record(make_record())
    second = encode_bound_receipt_record(make_record())

    assert first == second
    assert bound_receipt_record_content_id(first) == (
        bound_receipt_record_content_id(second)
    )


def test_matching_content_id_verifies():
    encoded = encode_bound_receipt_record(make_record())
    content_id = bound_receipt_record_content_id(encoded)

    assert verify_bound_receipt_record_content_id(encoded, content_id) is True


def test_changed_record_bytes_have_different_content_id():
    encoded = encode_bound_receipt_record(make_record())
    changed = (
        (b"0" if encoded[:1] != b"0" else b"1")
        + encoded[1:]
    )

    assert changed != encoded
    assert bound_receipt_record_content_id(changed) != (
        bound_receipt_record_content_id(encoded)
    )


def test_changed_record_bytes_fail_prior_content_id():
    encoded = encode_bound_receipt_record(make_record())
    content_id = bound_receipt_record_content_id(encoded)

    changed = (
        (b"0" if encoded[:1] != b"0" else b"1")
        + encoded[1:]
    )

    assert verify_bound_receipt_record_content_id(
        changed,
        content_id,
    ) is False


def test_changed_expected_content_id_fails_unchanged_bytes():
    encoded = encode_bound_receipt_record(make_record())
    content_id = bound_receipt_record_content_id(encoded)

    changed_content_id = (
        ("0" if content_id[0] != "0" else "1")
        + content_id[1:]
    )

    assert verify_bound_receipt_record_content_id(
        encoded,
        changed_content_id,
    ) is False


def test_uppercase_equivalent_content_id_verifies():
    encoded = encode_bound_receipt_record(make_record())
    content_id = bound_receipt_record_content_id(encoded)

    assert verify_bound_receipt_record_content_id(
        encoded,
        content_id.upper(),
    ) is True


@pytest.mark.parametrize(
    "expected_content_id",
    [
        "",
        "0" * 63,
        "0" * 65,
        "g" * 64,
    ],
)
def test_malformed_expected_content_id_fails_closed(expected_content_id):
    encoded = encode_bound_receipt_record(make_record())

    with pytest.raises(INVReceiptRecordIdentityError):
        verify_bound_receipt_record_content_id(
            encoded,
            expected_content_id,
        )


@pytest.mark.parametrize(
    "encoded",
    [
        None,
        "not-bytes",
        bytearray(b"record"),
        memoryview(b"record"),
    ],
)
def test_unsupported_encoded_type_fails_closed(encoded):
    with pytest.raises(INVReceiptRecordIdentityError):
        bound_receipt_record_content_id(encoded)


@pytest.mark.parametrize(
    "expected_content_id",
    [
        None,
        b"0" * 64,
        0,
    ],
)
def test_unsupported_expected_content_id_type_fails_closed(
    expected_content_id,
):
    encoded = encode_bound_receipt_record(make_record())

    with pytest.raises(INVReceiptRecordIdentityError):
        verify_bound_receipt_record_content_id(
            encoded,
            expected_content_id,
        )


def test_outer_identity_covers_represented_inner_content_id():
    record = make_record()
    original_encoded = encode_bound_receipt_record(record)

    changed_inner_id = (
        ("0" if record.content_id[0] != "0" else "1")
        + record.content_id[1:]
    )
    changed_record = BoundReceiptRecord(
        encoded_receipt=record.encoded_receipt,
        content_id=changed_inner_id,
    )
    changed_encoded = encode_bound_receipt_record(changed_record)

    assert changed_encoded != original_encoded
    assert bound_receipt_record_content_id(changed_encoded) != (
        bound_receipt_record_content_id(original_encoded)
    )


def test_invalid_inner_binding_can_have_valid_outer_identity():
    record = make_record()
    invalid_inner = BoundReceiptRecord(
        encoded_receipt=record.encoded_receipt,
        content_id="0" * 64,
    )

    assert verify_bound_receipt_record(invalid_inner) is False

    encoded = encode_bound_receipt_record(invalid_inner)
    outer_content_id = bound_receipt_record_content_id(encoded)

    assert verify_bound_receipt_record_content_id(
        encoded,
        outer_content_id,
    ) is True
    assert verify_bound_receipt_record(invalid_inner) is False
