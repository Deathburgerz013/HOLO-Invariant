import json

import pytest

from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_record import (
    BoundReceiptRecord,
    bind_receipt_bytes,
    verify_bound_receipt_record,
)
from holosim.inv_receipt_record_encoding import (
    INVReceiptRecordEncodingError,
    decode_bound_receipt_record,
    decode_bound_receipt_record_data,
    encode_bound_receipt_record,
    encode_bound_receipt_record_data,
)
from holosim.inv_receipt_record_serialization import (
    bound_receipt_record_to_data,
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


def test_equivalent_records_produce_identical_canonical_bytes():
    first = make_record()
    second = make_record()

    assert first == second
    assert first is not second
    assert encode_bound_receipt_record(first) == encode_bound_receipt_record(second)


def test_mapping_insertion_order_does_not_change_canonical_bytes():
    record = make_record()
    data = bound_receipt_record_to_data(record)

    reversed_data = {
        "content_id": data["content_id"],
        "encoded_receipt_hex": data["encoded_receipt_hex"],
    }

    assert encode_bound_receipt_record_data(data) == (
        encode_bound_receipt_record_data(reversed_data)
    )


def test_canonical_bytes_decode_to_supported_plain_data():
    record = make_record()
    encoded = encode_bound_receipt_record(record)

    data = decode_bound_receipt_record_data(encoded)

    assert data == bound_receipt_record_to_data(record)
    assert type(data) is dict
    assert type(data["encoded_receipt_hex"]) is str
    assert type(data["content_id"]) is str


def test_canonical_bytes_reconstruct_new_bound_record():
    record = make_record()

    reconstructed = decode_bound_receipt_record(
        encode_bound_receipt_record(record)
    )

    assert reconstructed == record
    assert reconstructed is not record
    assert verify_bound_receipt_record(reconstructed) is True


def test_decode_then_reencode_preserves_exact_canonical_bytes():
    encoded = encode_bound_receipt_record(make_record())

    data = decode_bound_receipt_record_data(encoded)

    assert encode_bound_receipt_record_data(data) == encoded


def test_noncanonical_equivalent_json_fails_closed():
    data = bound_receipt_record_to_data(make_record())

    noncanonical = json.dumps(
        data,
        sort_keys=False,
        indent=2,
    ).encode("utf-8")

    assert json.loads(noncanonical.decode("utf-8")) == data

    with pytest.raises(INVReceiptRecordEncodingError):
        decode_bound_receipt_record_data(noncanonical)


def test_canonical_encoding_preserves_content_binding_mismatch():
    record = make_record()
    mismatched = BoundReceiptRecord(
        encoded_receipt=record.encoded_receipt,
        content_id="0" * 64,
    )

    encoded = encode_bound_receipt_record(mismatched)
    reconstructed = decode_bound_receipt_record(encoded)

    assert reconstructed == mismatched
    assert verify_bound_receipt_record(reconstructed) is False


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"encoded_receipt_hex": "00"},
        {"content_id": "0" * 64},
        {
            "encoded_receipt_hex": "00",
            "content_id": "0" * 64,
            "extra": True,
        },
        {
            "encoded_receipt_hex": "AA",
            "content_id": "0" * 64,
        },
    ],
)
def test_unsupported_representation_data_fails_closed(data):
    with pytest.raises(INVReceiptRecordEncodingError):
        encode_bound_receipt_record_data(data)


@pytest.mark.parametrize(
    "encoded",
    [
        "not-bytes",
        b"",
        b"not-json",
        b"\xff",
        b"[]",
        b"{}",
    ],
)
def test_invalid_encoded_input_fails_closed(encoded):
    with pytest.raises(INVReceiptRecordEncodingError):
        decode_bound_receipt_record_data(encoded)


def test_extra_json_field_fails_closed():
    data = bound_receipt_record_to_data(make_record())
    data["extra"] = True

    encoded = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    with pytest.raises(INVReceiptRecordEncodingError):
        decode_bound_receipt_record_data(encoded)


def test_encoding_does_not_confer_content_binding_validity():
    record = make_record()
    invalid = BoundReceiptRecord(
        encoded_receipt=record.encoded_receipt,
        content_id="0" * 64,
    )

    encoded = encode_bound_receipt_record(invalid)
    reconstructed = decode_bound_receipt_record(encoded)

    assert reconstructed == invalid
    assert verify_bound_receipt_record(reconstructed) is False
