from copy import deepcopy

import pytest

from holosim.inv_receipt_encoding import (
    decode_receipt,
    encode_receipt,
    encode_receipt_data,
)
from holosim.inv_receipt_identity import (
    INVReceiptIdentityError,
    receipt_content_id,
    verify_receipt_content_id,
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


def test_equivalent_canonical_bytes_have_same_content_id():
    first = encode_receipt(make_receipt())
    second = encode_receipt(make_receipt())

    assert first == second
    assert receipt_content_id(first) == receipt_content_id(second)


def test_matching_content_id_verifies():
    encoded = encode_receipt(make_receipt())
    content_id = receipt_content_id(encoded)

    assert verify_receipt_content_id(encoded, content_id) is True


def test_changed_canonical_bytes_have_different_content_id():
    receipt = make_receipt()
    original_data = receipt_to_data(receipt)
    changed_data = deepcopy(original_data)
    changed_data["candidate_state"] = -2

    original = encode_receipt_data(original_data)
    changed = encode_receipt_data(changed_data)

    assert original != changed
    assert receipt_content_id(original) != receipt_content_id(changed)


def test_changed_bytes_fail_against_prior_content_id():
    receipt = make_receipt()
    original_data = receipt_to_data(receipt)
    changed_data = deepcopy(original_data)
    changed_data["candidate_state"] = -2

    original = encode_receipt_data(original_data)
    changed = encode_receipt_data(changed_data)
    original_id = receipt_content_id(original)

    assert verify_receipt_content_id(changed, original_id) is False


def test_changed_content_id_fails_against_unchanged_bytes():
    encoded = encode_receipt(make_receipt())
    content_id = receipt_content_id(encoded)

    replacement = (
        ("0" if content_id[0] != "0" else "1")
        + content_id[1:]
    )

    assert verify_receipt_content_id(encoded, replacement) is False


def test_uppercase_equivalent_content_id_verifies():
    encoded = encode_receipt(make_receipt())
    content_id = receipt_content_id(encoded)

    assert verify_receipt_content_id(encoded, content_id.upper()) is True


@pytest.mark.parametrize(
    "expected_content_id",
    [
        "",
        "0" * 63,
        "0" * 65,
        "z" * 64,
    ],
)
def test_invalid_expected_content_id_fails_closed(expected_content_id):
    encoded = encode_receipt(make_receipt())

    with pytest.raises(INVReceiptIdentityError):
        verify_receipt_content_id(encoded, expected_content_id)


def test_non_bytes_content_input_fails_closed():
    with pytest.raises(INVReceiptIdentityError):
        receipt_content_id("not-bytes")


def test_non_string_expected_content_id_fails_closed():
    encoded = encode_receipt(make_receipt())

    with pytest.raises(INVReceiptIdentityError):
        verify_receipt_content_id(encoded, b"0" * 64)


def test_content_identity_does_not_confer_semantic_validity():
    receipt = make_receipt()
    changed_data = deepcopy(receipt_to_data(receipt))
    changed_data["candidate_state"] = -2

    encoded = encode_receipt_data(changed_data)
    content_id = receipt_content_id(encoded)

    assert verify_receipt_content_id(encoded, content_id) is True

    reconstructed = decode_receipt(encoded)
    assert verify_transition_receipt(reconstructed) is False
