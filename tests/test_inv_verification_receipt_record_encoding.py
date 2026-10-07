import json
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
    build_bound_verification_receipt,
    verify_bound_verification_receipt,
)
from holosim.inv_verification_receipt_record import (
    BoundVerificationReceiptRecord,
    bind_verification_receipt_bytes,
    verify_bound_verification_receipt_record,
)
from holosim.inv_verification_receipt_record_encoding import (
    INVVerificationReceiptRecordEncodingError,
    decode_bound_verification_receipt_record,
    decode_bound_verification_receipt_record_data,
    encode_bound_verification_receipt_record,
    encode_bound_verification_receipt_record_data,
)
from holosim.inv_verification_receipt_record_serialization import (
    bound_verification_receipt_record_to_data,
)


def make_verification_receipt():
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


def make_record():
    receipt = make_verification_receipt()

    encoded_verification_receipt = (
        __import__(
            "holosim.inv_verification_receipt_encoding",
            fromlist=["encode_bound_verification_receipt"],
        ).encode_bound_verification_receipt(receipt)
    )

    return bind_verification_receipt_bytes(encoded_verification_receipt)


def test_equivalent_records_produce_identical_canonical_bytes():
    first = make_record()
    second = make_record()

    assert first == second
    assert first is not second
    assert (
        encode_bound_verification_receipt_record(first)
        == encode_bound_verification_receipt_record(second)
    )


def test_mapping_insertion_order_does_not_change_canonical_bytes():
    record = make_record()
    data = bound_verification_receipt_record_to_data(record)

    reversed_data = dict(reversed(list(data.items())))

    assert encode_bound_verification_receipt_record_data(data) == (
        encode_bound_verification_receipt_record_data(reversed_data)
    )


def test_canonical_bytes_decode_to_supported_plain_data():
    record = make_record()
    encoded = encode_bound_verification_receipt_record(record)

    data = decode_bound_verification_receipt_record_data(encoded)

    assert data == bound_verification_receipt_record_to_data(record)
    assert type(data) is dict
    assert type(data["encoded_verification_receipt_hex"]) is str
    assert type(data["content_id"]) is str


def test_canonical_bytes_reconstruct_new_bound_record():
    record = make_record()

    reconstructed = decode_bound_verification_receipt_record(
        encode_bound_verification_receipt_record(record)
    )

    assert reconstructed == record
    assert reconstructed is not record
    assert verify_bound_verification_receipt_record(reconstructed) is True


def test_decode_then_reencode_preserves_exact_canonical_bytes():
    encoded = encode_bound_verification_receipt_record(make_record())

    data = decode_bound_verification_receipt_record_data(encoded)

    assert encode_bound_verification_receipt_record_data(data) == encoded


def test_noncanonical_equivalent_json_fails_closed():
    data = bound_verification_receipt_record_to_data(make_record())

    noncanonical = json.dumps(
        data,
        sort_keys=False,
        indent=2,
    ).encode("utf-8")

    assert json.loads(noncanonical.decode("utf-8")) == data

    with pytest.raises(INVVerificationReceiptRecordEncodingError):
        decode_bound_verification_receipt_record_data(noncanonical)


def test_canonical_encoding_preserves_content_binding_mismatch():
    record = make_record()
    mismatched = BoundVerificationReceiptRecord(
        encoded_verification_receipt=record.encoded_verification_receipt,
        content_id="0" * 64,
    )

    encoded = encode_bound_verification_receipt_record(mismatched)
    reconstructed = decode_bound_verification_receipt_record(encoded)

    assert reconstructed == mismatched
    assert verify_bound_verification_receipt_record(reconstructed) is False


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"encoded_verification_receipt_hex": "00"},
        {"content_id": "0" * 64},
        {
            "encoded_verification_receipt_hex": "00",
            "content_id": "0" * 64,
            "extra": True,
        },
        {
            "encoded_verification_receipt_hex": "AA",
            "content_id": "0" * 64,
        },
    ],
)
def test_unsupported_representation_data_fails_closed(data):
    with pytest.raises(INVVerificationReceiptRecordEncodingError):
        encode_bound_verification_receipt_record_data(data)


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
    with pytest.raises(INVVerificationReceiptRecordEncodingError):
        decode_bound_verification_receipt_record_data(encoded)


def test_extra_json_field_fails_closed():
    data = bound_verification_receipt_record_to_data(make_record())
    data["extra"] = True

    encoded = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    with pytest.raises(INVVerificationReceiptRecordEncodingError):
        decode_bound_verification_receipt_record_data(encoded)


def test_encoding_does_not_confer_content_binding_validity():
    record = make_record()
    invalid = BoundVerificationReceiptRecord(
        encoded_verification_receipt=record.encoded_verification_receipt,
        content_id="0" * 64,
    )

    encoded = encode_bound_verification_receipt_record(invalid)
    reconstructed = decode_bound_verification_receipt_record(encoded)

    assert reconstructed == invalid
    assert verify_bound_verification_receipt_record(reconstructed) is False


def test_encoding_does_not_verify_embedded_verification_receipt():
    receipt = make_verification_receipt()
    encoded_receipt = (
        __import__(
            "holosim.inv_verification_receipt_encoding",
            fromlist=["encode_bound_verification_receipt"],
        ).encode_bound_verification_receipt(receipt)
    )

    contradictory_receipt = replace(
        receipt,
        semantic_verification_passed=False,
    )

    contradictory_encoded = (
        __import__(
            "holosim.inv_verification_receipt_encoding",
            fromlist=["encode_bound_verification_receipt"],
        ).encode_bound_verification_receipt(contradictory_receipt)
    )

    assert encoded_receipt != contradictory_encoded

    record = bind_verification_receipt_bytes(contradictory_encoded)
    encoded_record = encode_bound_verification_receipt_record(record)
    reconstructed = decode_bound_verification_receipt_record(encoded_record)

    assert reconstructed == record
    assert verify_bound_verification_receipt_record(reconstructed) is True

    embedded = __import__(
        "holosim.inv_verification_receipt_encoding",
        fromlist=["decode_bound_verification_receipt"],
    ).decode_bound_verification_receipt(
        reconstructed.encoded_verification_receipt
    )

    assert embedded.semantic_verification_passed is False
    assert verify_bound_verification_receipt(embedded) is False