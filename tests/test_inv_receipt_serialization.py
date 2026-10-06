from copy import deepcopy
from dataclasses import asdict

import pytest

from holosim.inv_receipt_serialization import (
    INVReceiptRepresentationError,
    receipt_from_data,
    receipt_to_data,
)
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    ReplaceTransition,
    SubtractTransition,
    execute_inv_transition_with_receipt,
    verify_transition_receipt,
)


@pytest.mark.parametrize(
    "transition",
    [
        ReplaceTransition(value=-1),
        SubtractTransition(amount=6),
    ],
)
def test_receipt_round_trip_preserves_semantics_and_verifies(transition):
    receipt = execute_inv_transition_with_receipt(
        state=5,
        transition=transition,
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )

    data = receipt_to_data(receipt)
    reconstructed = receipt_from_data(deepcopy(data))

    assert reconstructed == receipt
    assert reconstructed is not receipt
    assert verify_transition_receipt(reconstructed) is True


def test_representation_contains_no_live_semantic_objects():
    receipt = execute_inv_transition_with_receipt(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )

    data = receipt_to_data(receipt)

    assert data == {
        "previous_state": 5,
        "transition": {
            "kind": "subtract",
            "value": 6,
        },
        "candidate_state": -1,
        "invariant": {
            "kind": "greater_than_or_equal",
            "minimum": 0,
        },
        "accepted": False,
        "resulting_state": 5,
    }

    assert data != asdict(receipt)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.pop("candidate_state"),
        lambda data: data.__setitem__("extra", 1),
        lambda data: data.__setitem__(
            "transition",
            {"kind": "multiply", "value": 6},
        ),
        lambda data: data.__setitem__(
            "transition",
            {"kind": "subtract"},
        ),
        lambda data: data.__setitem__(
            "invariant",
            {"kind": "less_than", "minimum": 0},
        ),
        lambda data: data.__setitem__(
            "invariant",
            {"kind": "greater_than_or_equal"},
        ),
        lambda data: data.__setitem__("accepted", 1),
    ],
)
def test_malformed_or_unsupported_data_fails_closed(mutation):
    receipt = execute_inv_transition_with_receipt(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )
    data = receipt_to_data(receipt)

    mutation(data)

    with pytest.raises(INVReceiptRepresentationError):
        receipt_from_data(data)


def test_reconstructed_contradiction_still_fails_existing_verifier():
    receipt = execute_inv_transition_with_receipt(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )
    data = receipt_to_data(receipt)
    data["candidate_state"] = -2

    reconstructed = receipt_from_data(data)

    assert verify_transition_receipt(reconstructed) is False
