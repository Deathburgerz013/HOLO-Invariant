"""Canonical byte encoding for bounded INV transition receipt data."""

import json
from typing import Any

from holosim.inv_receipt_serialization import (
    INVReceiptRepresentationError,
    receipt_from_data,
    receipt_to_data,
)
from holosim.inv_runtime import TransitionDecisionReceipt


class INVReceiptEncodingError(ValueError):
    """Raised when canonical INV receipt bytes cannot be decoded safely."""


def encode_receipt_data(data: dict[str, Any]) -> bytes:
    """Encode bounded receipt data into deterministic canonical UTF-8 JSON."""

    try:
        receipt = receipt_from_data(data)
    except (INVReceiptRepresentationError, TypeError) as exc:
        raise INVReceiptEncodingError("invalid INV receipt data") from exc

    bounded_data = receipt_to_data(receipt)

    try:
        text = json.dumps(
            bounded_data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise INVReceiptEncodingError("receipt data cannot be encoded") from exc

    return text.encode("utf-8")


def encode_receipt(receipt: TransitionDecisionReceipt) -> bytes:
    """Encode a supported INV receipt into canonical bytes."""

    return encode_receipt_data(receipt_to_data(receipt))


def decode_receipt_data(encoded: bytes) -> dict[str, Any]:
    """Decode canonical receipt bytes into validated bounded plain data."""

    if type(encoded) is not bytes:
        raise INVReceiptEncodingError("encoded receipt must be bytes")

    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise INVReceiptEncodingError("encoded receipt must be valid UTF-8") from exc

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise INVReceiptEncodingError("encoded receipt must contain valid JSON") from exc

    if not isinstance(data, dict):
        raise INVReceiptEncodingError("encoded receipt must contain a mapping")

    try:
        receipt = receipt_from_data(data)
    except (INVReceiptRepresentationError, TypeError) as exc:
        raise INVReceiptEncodingError("encoded receipt contains invalid data") from exc

    canonical = encode_receipt_data(data)

    if encoded != canonical:
        raise INVReceiptEncodingError("encoded receipt is not canonical")

    return receipt_to_data(receipt)


def decode_receipt(encoded: bytes) -> TransitionDecisionReceipt:
    """Decode canonical bytes and reconstruct an INV transition receipt."""

    return receipt_from_data(decode_receipt_data(encoded))
