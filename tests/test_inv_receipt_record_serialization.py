from copy import deepcopy

import pytest

from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_record import (
    BoundReceiptRecord,
    bind_receipt_bytes,
    reconstruct_bound_receipt,
    verify_bound_receipt_record,
)
from holosim.inv_receipt_record_serialization import (
    INVReceiptRecordRepresentationError,
    bound_receipt_record_from_data,
    bound_receipt_record_to_data,
)
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    SubtractTransition,
    execute_inv_transition_with_receipt,
    verify_transition_receipt,
)


def make_receipt():
    return execute_inv_transition_with_receipt(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )


def make_record():
    return bind_receipt_bytes(encode_receipt(make_receipt()))


def test_bound_record_round_trip_uses_only_plain_data():
    record = make_record()

    data = bound_receipt_record_to_data(record)
    reconstructed = bound_receipt_record_from_data(data)

    assert set(data) == {"encoded_receipt_hex", "content_id"}
    assert type(data["encoded_receipt_hex"]) is str
    assert type(data["content_id"]) is str

    assert reconstructed == record
    assert reconstructed is not record
    assert verify_bound_receipt_record(reconstructed) is True


def test_round_trip_preserves_exact_receipt_bytes_and_content_id():
    record = make_record()

    reconstructed = bound_receipt_record_from_data(
        bound_receipt_record_to_data(record)
    )

    assert reconstructed.encoded_receipt == record.encoded_receipt
    assert reconstructed.content_id == record.content_id


def test_reconstructed_record_remains_usable_by_existing_path():
    receipt = make_receipt()
    record = bind_receipt_bytes(encode_receipt(receipt))

    reconstructed_record = bound_receipt_record_from_data(
        bound_receipt_record_to_data(record)
    )
    reconstructed_receipt = reconstruct_bound_receipt(reconstructed_record)

    assert reconstructed_receipt == receipt
    assert verify_transition_receipt(reconstructed_receipt) is True


def test_changed_serialized_content_preserves_claim_and_fails_binding():
    record = make_record()
    data = bound_receipt_record_to_data(record)

    changed = deepcopy(data)
    original = bytes.fromhex(changed["encoded_receipt_hex"])
    replacement = (
        (b"0" if original[:1] != b"0" else b"1")
        + original[1:]
    )
    changed["encoded_receipt_hex"] = replacement.hex()

    reconstructed = bound_receipt_record_from_data(changed)

    assert reconstructed.content_id == record.content_id
    assert reconstructed.encoded_receipt != record.encoded_receipt
    assert verify_bound_receipt_record(reconstructed) is False


def test_changed_serialized_content_id_is_not_repaired():
    record = make_record()
    data = bound_receipt_record_to_data(record)

    changed = deepcopy(data)
    changed["content_id"] = (
        ("0" if record.content_id[0] != "0" else "1")
        + record.content_id[1:]
    )

    reconstructed = bound_receipt_record_from_data(changed)

    assert reconstructed.encoded_receipt == record.encoded_receipt
    assert reconstructed.content_id == changed["content_id"]
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
            "encoded_receipt_hex": 123,
            "content_id": "0" * 64,
        },
        {
            "encoded_receipt_hex": "00",
            "content_id": b"0" * 64,
        },
        {
            "encoded_receipt_hex": "0",
            "content_id": "0" * 64,
        },
        {
            "encoded_receipt_hex": "zz",
            "content_id": "0" * 64,
        },
        {
            "encoded_receipt_hex": "AA",
            "content_id": "0" * 64,
        },
    ],
)
def test_malformed_or_unsupported_data_fails_closed(data):
    with pytest.raises(INVReceiptRecordRepresentationError):
        bound_receipt_record_from_data(data)


def test_unsupported_live_record_input_fails_closed():
    with pytest.raises(INVReceiptRecordRepresentationError):
        bound_receipt_record_to_data(object())


def test_reconstruction_does_not_confer_semantic_validity():
    invalid_record = BoundReceiptRecord(
        encoded_receipt=make_record().encoded_receipt,
        content_id="0" * 64,
    )

    data = bound_receipt_record_to_data(invalid_record)
    reconstructed = bound_receipt_record_from_data(data)

    assert reconstructed == invalid_record
    assert verify_bound_receipt_record(reconstructed) is False
