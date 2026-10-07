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
    BoundVerificationReceipt,
    build_bound_verification_receipt,
    verify_bound_verification_receipt,
)
from holosim.inv_verification_receipt_encoding import (
    INVVerificationReceiptEncodingError,
    decode_bound_verification_receipt,
    decode_bound_verification_receipt_data,
    encode_bound_verification_receipt,
    encode_bound_verification_receipt_data,
)
from holosim.inv_verification_receipt_serialization import (
    bound_verification_receipt_to_data,
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


def test_equivalent_receipts_produce_identical_canonical_bytes():
    receipt = make_verification_receipt()

    first = encode_bound_verification_receipt(receipt)
    second = encode_bound_verification_receipt(replace(receipt))

    assert first == second


def test_mapping_insertion_order_does_not_change_canonical_bytes():
    data = bound_verification_receipt_to_data(make_verification_receipt())
    reversed_data = dict(reversed(list(data.items())))

    assert encode_bound_verification_receipt_data(data) == (
        encode_bound_verification_receipt_data(reversed_data)
    )


def test_canonical_bytes_are_compact_sorted_utf8_json():
    receipt = make_verification_receipt()
    data = bound_verification_receipt_to_data(receipt)

    encoded = encode_bound_verification_receipt(receipt)

    expected = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    assert encoded == expected


def test_canonical_bytes_decode_to_supported_plain_data():
    receipt = make_verification_receipt()
    encoded = encode_bound_verification_receipt(receipt)

    data = decode_bound_verification_receipt_data(encoded)

    assert data == bound_verification_receipt_to_data(receipt)


def test_canonical_bytes_reconstruct_verification_receipt():
    original = make_verification_receipt()
    encoded = encode_bound_verification_receipt(original)

    reconstructed = decode_bound_verification_receipt(encoded)

    assert reconstructed == original
    assert reconstructed is not original
    assert verify_bound_verification_receipt(reconstructed) is True


def test_decode_then_encode_reproduces_exact_canonical_bytes():
    encoded = encode_bound_verification_receipt(make_verification_receipt())

    reconstructed = decode_bound_verification_receipt(encoded)

    assert encode_bound_verification_receipt(reconstructed) == encoded


def test_noncanonical_whitespace_is_rejected():
    data = bound_verification_receipt_to_data(make_verification_receipt())
    noncanonical = json.dumps(
        data,
        sort_keys=True,
    ).encode("utf-8")

    with pytest.raises(INVVerificationReceiptEncodingError):
        decode_bound_verification_receipt(noncanonical)


def test_noncanonical_key_order_is_rejected():
    data = bound_verification_receipt_to_data(make_verification_receipt())
    reversed_data = dict(reversed(list(data.items())))
    noncanonical = json.dumps(
        reversed_data,
        sort_keys=False,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    canonical = encode_bound_verification_receipt_data(data)

    assert noncanonical != canonical

    with pytest.raises(INVVerificationReceiptEncodingError):
        decode_bound_verification_receipt(noncanonical)


def test_extra_field_is_rejected():
    data = bound_verification_receipt_to_data(make_verification_receipt())
    data["extra"] = "unsupported"
    encoded = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    with pytest.raises(INVVerificationReceiptEncodingError):
        decode_bound_verification_receipt(encoded)


def test_missing_field_is_rejected():
    data = bound_verification_receipt_to_data(make_verification_receipt())
    del data["semantic_verification_passed"]
    encoded = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    with pytest.raises(INVVerificationReceiptEncodingError):
        decode_bound_verification_receipt(encoded)


@pytest.mark.parametrize(
    "encoded",
    [
        b"",
        b"not-json",
        b"[]",
        b"null",
        b'"string"',
        b"\xff",
    ],
)
def test_invalid_encoded_input_fails_closed(encoded):
    with pytest.raises(INVVerificationReceiptEncodingError):
        decode_bound_verification_receipt(encoded)


def test_non_bytes_encoded_input_fails_closed():
    with pytest.raises(INVVerificationReceiptEncodingError):
        decode_bound_verification_receipt("not-bytes")


def test_contradictory_identity_survives_canonicalization():
    receipt = make_verification_receipt()
    changed_id = (
        ("0" if receipt.verified_receipt_content_id[0] != "0" else "1")
        + receipt.verified_receipt_content_id[1:]
    )
    contradictory = replace(
        receipt,
        verified_receipt_content_id=changed_id,
    )

    encoded = encode_bound_verification_receipt(contradictory)
    reconstructed = decode_bound_verification_receipt(encoded)

    assert reconstructed.verified_receipt_content_id == changed_id
    assert reconstructed.verified_receipt_bytes == receipt.verified_receipt_bytes
    assert verify_bound_verification_receipt(reconstructed) is False


def test_false_verification_outcome_survives_canonicalization():
    receipt = make_verification_receipt()
    contradictory = replace(
        receipt,
        semantic_verification_passed=False,
    )

    encoded = encode_bound_verification_receipt(contradictory)
    reconstructed = decode_bound_verification_receipt(encoded)

    assert reconstructed.semantic_verification_passed is False
    assert verify_bound_verification_receipt(reconstructed) is False


def test_authority_claim_survives_canonicalization_for_later_rejection():
    receipt = make_verification_receipt()
    contradictory = replace(
        receipt,
        execution_authority="GRANTED",
    )

    encoded = encode_bound_verification_receipt(contradictory)
    reconstructed = decode_bound_verification_receipt(encoded)

    assert reconstructed.execution_authority == "GRANTED"

    with pytest.raises(Exception):
        verify_bound_verification_receipt(reconstructed)


def test_encoding_does_not_repair_false_outer_identity():
    receipt = make_verification_receipt()
    changed = (
        ("0" if receipt.observed_outer_content_id[0] != "0" else "1")
        + receipt.observed_outer_content_id[1:]
    )
    contradictory = replace(
        receipt,
        observed_outer_content_id=changed,
    )

    encoded = encode_bound_verification_receipt(contradictory)
    reconstructed = decode_bound_verification_receipt(encoded)

    assert reconstructed.observed_outer_content_id == changed
    assert verify_bound_verification_receipt(reconstructed) is False


def test_unsupported_live_object_fails_closed():
    with pytest.raises(INVVerificationReceiptEncodingError):
        encode_bound_verification_receipt(object())
