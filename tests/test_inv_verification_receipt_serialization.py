from dataclasses import replace

import pytest

from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_identity import receipt_content_id
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
from holosim.inv_verification_receipt_serialization import (
    INVVerificationReceiptRepresentationError,
    bound_verification_receipt_from_data,
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


def test_round_trip_preserves_verification_receipt():
    original = make_verification_receipt()

    data = bound_verification_receipt_to_data(original)
    reconstructed = bound_verification_receipt_from_data(data)

    assert reconstructed == original
    assert reconstructed is not original
    assert verify_bound_verification_receipt(reconstructed) is True


def test_plain_data_preserves_verified_receipt_bytes_as_lowercase_hex():
    receipt = make_verification_receipt()

    data = bound_verification_receipt_to_data(receipt)

    assert data["verified_receipt_hex"] == receipt.verified_receipt_bytes.hex()
    assert data["verified_receipt_hex"] == data["verified_receipt_hex"].lower()


def test_reconstruction_preserves_false_verified_receipt_identity():
    receipt = make_verification_receipt()
    changed_id = (
        ("0" if receipt.verified_receipt_content_id[0] != "0" else "1")
        + receipt.verified_receipt_content_id[1:]
    )
    contradictory = replace(
        receipt,
        verified_receipt_content_id=changed_id,
    )

    data = bound_verification_receipt_to_data(contradictory)
    reconstructed = bound_verification_receipt_from_data(data)

    assert reconstructed.verified_receipt_content_id == changed_id
    assert reconstructed.verified_receipt_bytes == receipt.verified_receipt_bytes
    assert verify_bound_verification_receipt(reconstructed) is False


def test_reconstruction_preserves_false_verification_outcome():
    receipt = make_verification_receipt()
    contradictory = replace(
        receipt,
        semantic_verification_passed=False,
    )

    data = bound_verification_receipt_to_data(contradictory)
    reconstructed = bound_verification_receipt_from_data(data)

    assert reconstructed.semantic_verification_passed is False
    assert verify_bound_verification_receipt(reconstructed) is False


def test_reconstruction_preserves_authority_claim_for_later_rejection():
    receipt = make_verification_receipt()
    contradictory = replace(
        receipt,
        write_authority="GRANTED",
    )

    data = bound_verification_receipt_to_data(contradictory)
    reconstructed = bound_verification_receipt_from_data(data)

    assert reconstructed.write_authority == "GRANTED"

    with pytest.raises(Exception):
        verify_bound_verification_receipt(reconstructed)


@pytest.mark.parametrize(
    "field",
    [
        "expected_outer_content_id",
        "observed_outer_content_id",
        "verified_receipt_hex",
        "verified_receipt_content_id",
        "outer_identity_verified",
        "canonical_record_verified",
        "inner_binding_verified",
        "receipt_reconstructed",
        "semantic_verification_passed",
        "accepted",
        "truth_claimed",
        "write_authority",
        "execution_authority",
    ],
)
def test_missing_field_fails_closed(field):
    data = bound_verification_receipt_to_data(make_verification_receipt())
    del data[field]

    with pytest.raises(INVVerificationReceiptRepresentationError):
        bound_verification_receipt_from_data(data)


def test_extra_field_fails_closed():
    data = bound_verification_receipt_to_data(make_verification_receipt())
    data["extra"] = "unsupported"

    with pytest.raises(INVVerificationReceiptRepresentationError):
        bound_verification_receipt_from_data(data)


@pytest.mark.parametrize(
    "field",
    [
        "expected_outer_content_id",
        "observed_outer_content_id",
        "verified_receipt_hex",
        "verified_receipt_content_id",
        "write_authority",
        "execution_authority",
    ],
)
def test_non_string_string_field_fails_closed(field):
    data = bound_verification_receipt_to_data(make_verification_receipt())
    data[field] = 1

    with pytest.raises(INVVerificationReceiptRepresentationError):
        bound_verification_receipt_from_data(data)


@pytest.mark.parametrize(
    "field",
    [
        "outer_identity_verified",
        "canonical_record_verified",
        "inner_binding_verified",
        "receipt_reconstructed",
        "semantic_verification_passed",
        "accepted",
        "truth_claimed",
    ],
)
def test_non_bool_boolean_field_fails_closed(field):
    data = bound_verification_receipt_to_data(make_verification_receipt())
    data[field] = 1

    with pytest.raises(INVVerificationReceiptRepresentationError):
        bound_verification_receipt_from_data(data)


def test_non_hex_verified_receipt_bytes_fail_closed():
    data = bound_verification_receipt_to_data(make_verification_receipt())
    data["verified_receipt_hex"] = "not-hex"

    with pytest.raises(INVVerificationReceiptRepresentationError):
        bound_verification_receipt_from_data(data)


def test_uppercase_verified_receipt_hex_fails_closed():
    data = bound_verification_receipt_to_data(make_verification_receipt())
    data["verified_receipt_hex"] = data["verified_receipt_hex"].upper()

    with pytest.raises(INVVerificationReceiptRepresentationError):
        bound_verification_receipt_from_data(data)


def test_noncanonical_spaced_hex_fails_closed():
    data = bound_verification_receipt_to_data(make_verification_receipt())
    encoded = data["verified_receipt_hex"]
    data["verified_receipt_hex"] = encoded[:2] + " " + encoded[2:]

    with pytest.raises(INVVerificationReceiptRepresentationError):
        bound_verification_receipt_from_data(data)


def test_unsupported_representation_type_fails_closed():
    with pytest.raises(INVVerificationReceiptRepresentationError):
        bound_verification_receipt_from_data([])


def test_unsupported_live_object_fails_closed():
    with pytest.raises(INVVerificationReceiptRepresentationError):
        bound_verification_receipt_to_data(object())


def test_reconstruction_does_not_recompute_verified_receipt_identity():
    receipt = make_verification_receipt()
    data = bound_verification_receipt_to_data(receipt)

    changed = (
        ("0" if data["verified_receipt_content_id"][0] != "0" else "1")
        + data["verified_receipt_content_id"][1:]
    )
    data["verified_receipt_content_id"] = changed

    reconstructed = bound_verification_receipt_from_data(data)

    assert reconstructed.verified_receipt_content_id == changed
    assert receipt_content_id(reconstructed.verified_receipt_bytes) != changed
    assert verify_bound_verification_receipt(reconstructed) is False
