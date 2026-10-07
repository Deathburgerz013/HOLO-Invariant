from copy import deepcopy
from dataclasses import replace

import pytest

from holosim.inv_receipt_encoding import (
    encode_receipt,
    encode_receipt_data,
)
from holosim.inv_receipt_record import (
    BoundReceiptRecord,
    INVReceiptRecordError,
    bind_receipt_bytes,
    reconstruct_bound_receipt,
    verify_bound_receipt_record,
)
from holosim.inv_receipt_serialization import receipt_to_data
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


def test_bind_record_preserves_exact_bytes_and_derived_content_id():
    encoded = encode_receipt(make_receipt())
    record = bind_receipt_bytes(encoded)

    assert record.encoded_receipt == encoded
    assert type(record.content_id) is str
    assert len(record.content_id) == 64
    assert verify_bound_receipt_record(record) is True


def test_equivalent_bytes_produce_equivalent_bound_records():
    first = bind_receipt_bytes(encode_receipt(make_receipt()))
    second = bind_receipt_bytes(encode_receipt(make_receipt()))

    assert first == second
    assert first is not second


def test_changed_bytes_with_prior_content_id_fail_binding():
    record = bind_receipt_bytes(encode_receipt(make_receipt()))

    changed_data = deepcopy(receipt_to_data(make_receipt()))
    changed_data["candidate_state"] = -2
    changed_bytes = encode_receipt_data(changed_data)

    changed_record = replace(
        record,
        encoded_receipt=changed_bytes,
    )

    assert verify_bound_receipt_record(changed_record) is False

    with pytest.raises(INVReceiptRecordError):
        reconstruct_bound_receipt(changed_record)


def test_changed_content_id_with_unchanged_bytes_fails_binding():
    record = bind_receipt_bytes(encode_receipt(make_receipt()))

    changed_content_id = (
        ("0" if record.content_id[0] != "0" else "1")
        + record.content_id[1:]
    )

    changed_record = replace(
        record,
        content_id=changed_content_id,
    )

    assert verify_bound_receipt_record(changed_record) is False

    with pytest.raises(INVReceiptRecordError):
        reconstruct_bound_receipt(changed_record)


def test_valid_record_reconstructs_through_existing_decoder():
    receipt = make_receipt()
    record = bind_receipt_bytes(encode_receipt(receipt))

    reconstructed = reconstruct_bound_receipt(record)

    assert reconstructed == receipt
    assert reconstructed is not receipt
    assert verify_transition_receipt(reconstructed) is True


def test_binding_does_not_confer_semantic_validity():
    receipt = make_receipt()
    changed_data = deepcopy(receipt_to_data(receipt))
    changed_data["candidate_state"] = -2

    encoded = encode_receipt_data(changed_data)
    record = bind_receipt_bytes(encoded)

    assert verify_bound_receipt_record(record) is True

    reconstructed = reconstruct_bound_receipt(record)
    assert verify_transition_receipt(reconstructed) is False


def test_non_bytes_binding_input_fails_closed():
    with pytest.raises(INVReceiptRecordError):
        bind_receipt_bytes("not-bytes")


def test_unsupported_record_fails_closed():
    with pytest.raises(INVReceiptRecordError):
        verify_bound_receipt_record(object())


@pytest.mark.parametrize(
    "record",
    [
        BoundReceiptRecord(
            encoded_receipt=b"not-json",
            content_id="0" * 64,
        ),
        BoundReceiptRecord(
            encoded_receipt=b"",
            content_id="not-a-content-id",
        ),
    ],
)
def test_invalid_record_cannot_reconstruct(record):
    with pytest.raises(INVReceiptRecordError):
        reconstruct_bound_receipt(record)
