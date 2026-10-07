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
    INVVerificationReceiptIdentityError,
    bound_verification_receipt_content_id,
    verify_bound_verification_receipt_content_id,
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


def test_identical_canonical_bytes_produce_same_content_id():
    encoded = encode_bound_verification_receipt(make_verification_receipt())

    first = bound_verification_receipt_content_id(encoded)
    second = bound_verification_receipt_content_id(encoded)

    assert first == second
    assert len(first) == 64
    assert first == first.lower()


def test_matching_content_id_verifies():
    encoded = encode_bound_verification_receipt(make_verification_receipt())
    content_id = bound_verification_receipt_content_id(encoded)

    assert verify_bound_verification_receipt_content_id(
        encoded,
        content_id,
    ) is True


def test_changed_canonical_bytes_produce_different_content_id():
    receipt = make_verification_receipt()
    first = encode_bound_verification_receipt(receipt)

    changed_receipt = replace(
        receipt,
        semantic_verification_passed=False,
    )
    second = encode_bound_verification_receipt(changed_receipt)

    assert first != second
    assert bound_verification_receipt_content_id(first) != (
        bound_verification_receipt_content_id(second)
    )


def test_changed_canonical_bytes_fail_prior_content_id():
    receipt = make_verification_receipt()
    original = encode_bound_verification_receipt(receipt)
    original_id = bound_verification_receipt_content_id(original)

    changed = encode_bound_verification_receipt(
        replace(receipt, semantic_verification_passed=False)
    )

    assert verify_bound_verification_receipt_content_id(
        changed,
        original_id,
    ) is False


def test_changed_expected_id_fails_unchanged_bytes():
    encoded = encode_bound_verification_receipt(make_verification_receipt())
    content_id = bound_verification_receipt_content_id(encoded)
    changed_id = (
        ("0" if content_id[0] != "0" else "1")
        + content_id[1:]
    )

    assert verify_bound_verification_receipt_content_id(
        encoded,
        changed_id,
    ) is False


def test_uppercase_equivalent_content_id_verifies():
    encoded = encode_bound_verification_receipt(make_verification_receipt())
    content_id = bound_verification_receipt_content_id(encoded)

    assert verify_bound_verification_receipt_content_id(
        encoded,
        content_id.upper(),
    ) is True


@pytest.mark.parametrize(
    "expected",
    [
        "",
        "0" * 63,
        "0" * 65,
        "g" * 64,
        "not-an-id",
    ],
)
def test_malformed_expected_content_id_fails_closed(expected):
    encoded = encode_bound_verification_receipt(make_verification_receipt())

    with pytest.raises(INVVerificationReceiptIdentityError):
        verify_bound_verification_receipt_content_id(
            encoded,
            expected,
        )


@pytest.mark.parametrize(
    "encoded",
    [
        None,
        "",
        bytearray(b"abc"),
        memoryview(b"abc"),
    ],
)
def test_unsupported_encoded_type_fails_closed(encoded):
    with pytest.raises(INVVerificationReceiptIdentityError):
        bound_verification_receipt_content_id(encoded)


@pytest.mark.parametrize(
    "expected",
    [
        None,
        b"0" * 64,
        0,
    ],
)
def test_unsupported_identifier_type_fails_closed(expected):
    encoded = encode_bound_verification_receipt(make_verification_receipt())

    with pytest.raises(INVVerificationReceiptIdentityError):
        verify_bound_verification_receipt_content_id(
            encoded,
            expected,
        )


def test_outer_content_identity_does_not_validate_inner_contradiction():
    receipt = make_verification_receipt()
    changed_inner_id = (
        ("0" if receipt.verified_receipt_content_id[0] != "0" else "1")
        + receipt.verified_receipt_content_id[1:]
    )
    contradictory = replace(
        receipt,
        verified_receipt_content_id=changed_inner_id,
    )

    encoded = encode_bound_verification_receipt(contradictory)
    outer_id = bound_verification_receipt_content_id(encoded)

    assert verify_bound_verification_receipt_content_id(
        encoded,
        outer_id,
    ) is True

    reconstructed = decode_bound_verification_receipt(encoded)

    assert reconstructed.verified_receipt_content_id == changed_inner_id
    assert verify_bound_verification_receipt(reconstructed) is False


def test_outer_content_identity_does_not_validate_false_outcome():
    contradictory = replace(
        make_verification_receipt(),
        semantic_verification_passed=False,
    )

    encoded = encode_bound_verification_receipt(contradictory)
    outer_id = bound_verification_receipt_content_id(encoded)

    assert verify_bound_verification_receipt_content_id(
        encoded,
        outer_id,
    ) is True

    reconstructed = decode_bound_verification_receipt(encoded)

    assert reconstructed.semantic_verification_passed is False
    assert verify_bound_verification_receipt(reconstructed) is False


def test_outer_content_identity_does_not_confer_authority():
    contradictory = replace(
        make_verification_receipt(),
        write_authority="GRANTED",
    )

    encoded = encode_bound_verification_receipt(contradictory)
    outer_id = bound_verification_receipt_content_id(encoded)

    assert verify_bound_verification_receipt_content_id(
        encoded,
        outer_id,
    ) is True

    reconstructed = decode_bound_verification_receipt(encoded)

    assert reconstructed.write_authority == "GRANTED"

    with pytest.raises(Exception):
        verify_bound_verification_receipt(reconstructed)


def test_content_identity_operates_on_exact_bytes_without_decoding():
    arbitrary = b"not a canonical verification receipt"

    content_id = bound_verification_receipt_content_id(arbitrary)

    assert verify_bound_verification_receipt_content_id(
        arbitrary,
        content_id,
    ) is True
