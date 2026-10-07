from copy import deepcopy

import pytest

from holosim.inv_receipt_encoding import (
    INVReceiptEncodingError,
    decode_receipt,
    decode_receipt_data,
    encode_receipt,
    encode_receipt_data,
)
from holosim.inv_receipt_serialization import receipt_to_data
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    ReplaceTransition,
    SubtractTransition,
    execute_inv_transition_with_receipt,
    verify_transition_receipt,
)


def make_receipt(transition):
    return execute_inv_transition_with_receipt(
        state=5,
        transition=transition,
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )


@pytest.mark.parametrize(
    "transition",
    [
        ReplaceTransition(value=-1),
        SubtractTransition(amount=6),
    ],
)
def test_canonical_round_trip_preserves_semantics(transition):
    receipt = make_receipt(transition)

    encoded = encode_receipt(receipt)
    reconstructed = decode_receipt(encoded)

    assert type(encoded) is bytes
    assert reconstructed == receipt
    assert reconstructed is not receipt
    assert verify_transition_receipt(reconstructed) is True


def test_equivalent_receipts_produce_identical_bytes():
    first = make_receipt(SubtractTransition(amount=6))
    second = make_receipt(SubtractTransition(amount=6))

    assert first is not second
    assert encode_receipt(first) == encode_receipt(second)


def test_mapping_insertion_order_does_not_change_canonical_bytes():
    receipt = make_receipt(SubtractTransition(amount=6))
    data = receipt_to_data(receipt)

    reordered = {
        "resulting_state": data["resulting_state"],
        "accepted": data["accepted"],
        "invariant": {
            "minimum": data["invariant"]["minimum"],
            "kind": data["invariant"]["kind"],
        },
        "candidate_state": data["candidate_state"],
        "transition": {
            "value": data["transition"]["value"],
            "kind": data["transition"]["kind"],
        },
        "previous_state": data["previous_state"],
    }

    assert encode_receipt_data(data) == encode_receipt_data(reordered)


def test_decode_returns_bounded_plain_data():
    receipt = make_receipt(SubtractTransition(amount=6))
    encoded = encode_receipt(receipt)

    assert decode_receipt_data(encoded) == receipt_to_data(receipt)


@pytest.mark.parametrize(
    "encoded",
    [
        b"",
        b"not-json",
        b"[]",
        b'{"previous_state":5}',
        b'{"accepted":false,"candidate_state":-1,"invariant":{"kind":"greater_than_or_equal","minimum":0},"previous_state":5,"resulting_state":5,"transition":{"kind":"multiply","value":6}}',
        b"\xff",
    ],
)
def test_malformed_or_unsupported_encoded_input_fails_closed(encoded):
    with pytest.raises(INVReceiptEncodingError):
        decode_receipt(encoded)


def test_noncanonical_json_bytes_fail_closed():
    receipt = make_receipt(SubtractTransition(amount=6))
    data = receipt_to_data(receipt)
    canonical = encode_receipt_data(data)

    noncanonical = (
        b'{ "previous_state": 5, "transition": {"kind": "subtract", "value": 6}, '
        b'"candidate_state": -1, "invariant": {"kind": "greater_than_or_equal", '
        b'"minimum": 0}, "accepted": false, "resulting_state": 5 }'
    )

    assert noncanonical != canonical

    with pytest.raises(INVReceiptEncodingError):
        decode_receipt(noncanonical)


def test_changed_semantic_data_changes_canonical_bytes():
    receipt = make_receipt(SubtractTransition(amount=6))
    original = receipt_to_data(receipt)
    changed = deepcopy(original)
    changed["candidate_state"] = -2

    assert encode_receipt_data(original) != encode_receipt_data(changed)

    reconstructed = decode_receipt(encode_receipt_data(changed))
    assert verify_transition_receipt(reconstructed) is False
