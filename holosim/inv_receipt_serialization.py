"""Bounded representation and reconstruction for INV transition receipts."""

from typing import Any

from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    ReplaceTransition,
    SubtractTransition,
    TransitionDecisionReceipt,
)


class INVReceiptRepresentationError(ValueError):
    """Raised when bounded receipt data cannot be reconstructed safely."""


_RECEIPT_FIELDS = {
    "previous_state",
    "transition",
    "candidate_state",
    "invariant",
    "accepted",
    "resulting_state",
}

_TRANSITION_FIELDS = {
    "kind",
    "value",
}

_INVARIANT_FIELDS = {
    "kind",
    "minimum",
}


def receipt_to_data(receipt: TransitionDecisionReceipt) -> dict[str, Any]:
    """Convert a supported receipt into bounded plain data."""

    if not isinstance(receipt, TransitionDecisionReceipt):
        raise TypeError("unsupported INV transition receipt")

    if isinstance(receipt.transition, ReplaceTransition):
        transition_data = {
            "kind": "replace",
            "value": receipt.transition.value,
        }
    elif isinstance(receipt.transition, SubtractTransition):
        transition_data = {
            "kind": "subtract",
            "value": receipt.transition.amount,
        }
    else:
        raise TypeError("unsupported INV transition semantic")

    if not isinstance(receipt.invariant, GreaterThanOrEqualInvariant):
        raise TypeError("unsupported INV invariant semantic")

    return {
        "previous_state": receipt.previous_state,
        "transition": transition_data,
        "candidate_state": receipt.candidate_state,
        "invariant": {
            "kind": "greater_than_or_equal",
            "minimum": receipt.invariant.minimum,
        },
        "accepted": receipt.accepted,
        "resulting_state": receipt.resulting_state,
    }


def receipt_from_data(data: dict[str, Any]) -> TransitionDecisionReceipt:
    """Reconstruct a supported receipt from bounded plain data."""

    if not isinstance(data, dict):
        raise INVReceiptRepresentationError("receipt data must be a mapping")

    if set(data) != _RECEIPT_FIELDS:
        raise INVReceiptRepresentationError("invalid receipt fields")

    transition_data = data["transition"]
    invariant_data = data["invariant"]

    if not isinstance(transition_data, dict):
        raise INVReceiptRepresentationError("transition data must be a mapping")

    if set(transition_data) != _TRANSITION_FIELDS:
        raise INVReceiptRepresentationError("invalid transition fields")

    if not isinstance(invariant_data, dict):
        raise INVReceiptRepresentationError("invariant data must be a mapping")

    if set(invariant_data) != _INVARIANT_FIELDS:
        raise INVReceiptRepresentationError("invalid invariant fields")

    transition_kind = transition_data["kind"]
    transition_value = transition_data["value"]

    if type(transition_value) is not int:
        raise INVReceiptRepresentationError("transition value must be an integer")

    if transition_kind == "replace":
        transition = ReplaceTransition(value=transition_value)
    elif transition_kind == "subtract":
        transition = SubtractTransition(amount=transition_value)
    else:
        raise INVReceiptRepresentationError("unsupported transition kind")

    if invariant_data["kind"] != "greater_than_or_equal":
        raise INVReceiptRepresentationError("unsupported invariant kind")

    minimum = invariant_data["minimum"]

    if type(minimum) is not int:
        raise INVReceiptRepresentationError("invariant minimum must be an integer")

    for field in ("previous_state", "candidate_state", "resulting_state"):
        if type(data[field]) is not int:
            raise INVReceiptRepresentationError(
                f"{field} must be an integer"
            )

    if type(data["accepted"]) is not bool:
        raise INVReceiptRepresentationError("accepted must be a boolean")

    return TransitionDecisionReceipt(
        previous_state=data["previous_state"],
        transition=transition,
        candidate_state=data["candidate_state"],
        invariant=GreaterThanOrEqualInvariant(minimum=minimum),
        accepted=data["accepted"],
        resulting_state=data["resulting_state"],
    )
