from dataclasses import replace

import pytest

from holosim.inv_verification_receipt import (
    build_bound_verification_receipt,
)
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    SubtractTransition,
    execute_inv_transition_with_receipt,
)
from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_record import bind_receipt_bytes
from holosim.inv_receipt_record_encoding import encode_bound_receipt_record
from holosim.inv_receipt_record_identity import bound_receipt_record_content_id
from holosim.inv_verification_receipt_encoding import (
    decode_bound_verification_receipt,
    encode_bound_verification_receipt,
)
from holosim.inv_verification_receipt_record import (
    BoundVerificationReceiptRecord,
    bind_verification_receipt_bytes,
    verify_bound_verification_receipt_record,
)
from holosim.inv_verification_receipt_record_serialization import (
    INVVerificationReceiptRecordRepresentationError,
    bound_verification_receipt_record_from_data,
    bound_verification_receipt_record_to_data,
)


def _canonical_verification_receipt_bytes() -> bytes:
    transition_receipt = execute_inv_transition_with_receipt(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )
    bound_record = bind_receipt_bytes(
        encode_receipt(transition_receipt)
    )
    encoded_record = encode_bound_receipt_record(bound_record)
    expected_outer_content_id = bound_receipt_record_content_id(encoded_record)

    verification_receipt = build_bound_verification_receipt(
        encoded_record,
        expected_outer_content_id,
    )
    return encode_bound_verification_receipt(verification_receipt)

def _record() -> BoundVerificationReceiptRecord:
    return bind_verification_receipt_bytes(
        _canonical_verification_receipt_bytes()
    )


def test_record_to_data_uses_only_supported_fields():
    record = _record()

    data = bound_verification_receipt_record_to_data(record)

    assert set(data) == {
        "encoded_verification_receipt_hex",
        "content_id",
    }


def test_record_to_data_preserves_exact_bytes_as_lowercase_hex():
    record = _record()

    data = bound_verification_receipt_record_to_data(record)

    assert data["encoded_verification_receipt_hex"] == (
        record.encoded_verification_receipt.hex()
    )


def test_record_to_data_preserves_content_id_exactly():
    record = _record()

    data = bound_verification_receipt_record_to_data(record)

    assert data["content_id"] == record.content_id


def test_round_trip_reconstructs_equal_but_distinct_record():
    original = _record()

    reconstructed = bound_verification_receipt_record_from_data(
        bound_verification_receipt_record_to_data(original)
    )

    assert reconstructed == original
    assert reconstructed is not original


def test_reconstruction_preserves_exact_verification_receipt_bytes():
    original = _record()
    data = bound_verification_receipt_record_to_data(original)

    reconstructed = bound_verification_receipt_record_from_data(data)

    assert (
        reconstructed.encoded_verification_receipt
        == original.encoded_verification_receipt
    )


def test_reconstruction_preserves_represented_content_id_without_rederiving():
    original = _record()
    data = bound_verification_receipt_record_to_data(original)
    represented_wrong_id = "f" * 64
    assert represented_wrong_id != original.content_id

    data["content_id"] = represented_wrong_id
    reconstructed = bound_verification_receipt_record_from_data(data)

    assert reconstructed.content_id == represented_wrong_id
    assert not verify_bound_verification_receipt_record(reconstructed)


def test_reconstruction_preserves_binding_contradiction():
    original = _record()
    original_receipt = decode_bound_verification_receipt(
        original.encoded_verification_receipt
    )

    changed_inner_id = (
        ("0" if original_receipt.verified_receipt_content_id[0] != "0" else "1")
        + original_receipt.verified_receipt_content_id[1:]
    )
    contradictory_receipt = replace(
        original_receipt,
        verified_receipt_content_id=changed_inner_id,
    )
    changed_bytes = encode_bound_verification_receipt(
        contradictory_receipt
    )

    assert changed_bytes != original.encoded_verification_receipt

    data = bound_verification_receipt_record_to_data(original)
    data["encoded_verification_receipt_hex"] = changed_bytes.hex()

    reconstructed = bound_verification_receipt_record_from_data(data)

    assert reconstructed.encoded_verification_receipt == changed_bytes
    assert reconstructed.content_id == original.content_id
    assert not verify_bound_verification_receipt_record(reconstructed)


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"encoded_verification_receipt_hex": "00"},
        {"content_id": "0" * 64},
        {
            "encoded_verification_receipt_hex": "00",
            "content_id": "0" * 64,
            "extra": "unsupported",
        },
    ],
)
def test_reconstruction_rejects_missing_or_extra_fields(data):
    with pytest.raises(INVVerificationReceiptRecordRepresentationError):
        bound_verification_receipt_record_from_data(data)


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        (),
        "",
        b"",
        1,
        True,
    ],
)
def test_reconstruction_rejects_unsupported_container_types(data):
    with pytest.raises(INVVerificationReceiptRecordRepresentationError):
        bound_verification_receipt_record_from_data(data)


@pytest.mark.parametrize(
    "encoded_hex",
    [
        None,
        b"00",
        1,
        True,
        [],
        {},
        "0",
        "zz",
    ],
)
def test_reconstruction_rejects_invalid_encoded_receipt_hex(encoded_hex):
    data = {
        "encoded_verification_receipt_hex": encoded_hex,
        "content_id": "0" * 64,
    }

    with pytest.raises(INVVerificationReceiptRecordRepresentationError):
        bound_verification_receipt_record_from_data(data)


@pytest.mark.parametrize(
    "content_id",
    [
        None,
        b"0" * 64,
        1,
        True,
        [],
        {},
        "",
        "0" * 63,
        "g" * 64,
    ],
)
def test_reconstruction_rejects_invalid_content_id_shape(content_id):
    data = {
        "encoded_verification_receipt_hex": "00",
        "content_id": content_id,
    }

    with pytest.raises(INVVerificationReceiptRecordRepresentationError):
        bound_verification_receipt_record_from_data(data)


def test_serialization_rejects_unsupported_record_type():
    with pytest.raises(INVVerificationReceiptRecordRepresentationError):
        bound_verification_receipt_record_to_data(object())


def test_reconstruction_does_not_require_original_record_object():
    original = _record()
    data = {
        "encoded_verification_receipt_hex": (
            original.encoded_verification_receipt.hex()
        ),
        "content_id": original.content_id,
    }
    del original

    reconstructed = bound_verification_receipt_record_from_data(data)

    assert isinstance(reconstructed, BoundVerificationReceiptRecord)


def test_reconstruction_does_not_repair_changed_identifier():
    original = _record()
    data = bound_verification_receipt_record_to_data(original)
    data["content_id"] = "a" * 64

    reconstructed = bound_verification_receipt_record_from_data(data)

    assert reconstructed.content_id == "a" * 64
    assert not verify_bound_verification_receipt_record(reconstructed)


def test_reconstruction_does_not_mutate_input_mapping():
    original = _record()
    data = bound_verification_receipt_record_to_data(original)
    before = dict(data)

    bound_verification_receipt_record_from_data(data)

    assert data == before