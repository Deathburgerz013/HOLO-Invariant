"""Canonical byte encoding for INV verification receipt representations."""

import json
from collections.abc import Mapping
from typing import Any

from holosim.inv_verification_receipt import BoundVerificationReceipt
from holosim.inv_verification_receipt_serialization import (
    INVVerificationReceiptRepresentationError,
    bound_verification_receipt_from_data,
    bound_verification_receipt_to_data,
)


class INVVerificationReceiptEncodingError(ValueError):
    """Raised when verification receipt encoding is invalid or noncanonical."""


def encode_bound_verification_receipt_data(
    data: Mapping[str, Any],
) -> bytes:
    """Encode supported verification receipt data as canonical UTF-8 JSON."""

    try:
        receipt = bound_verification_receipt_from_data(data)
        normalized = bound_verification_receipt_to_data(receipt)
    except INVVerificationReceiptRepresentationError as exc:
        raise INVVerificationReceiptEncodingError(
            "unsupported verification receipt representation"
        ) from exc

    try:
        text = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise INVVerificationReceiptEncodingError(
            "verification receipt representation cannot be encoded"
        ) from exc

    return text.encode("utf-8")


def encode_bound_verification_receipt(
    receipt: BoundVerificationReceipt,
) -> bytes:
    """Encode an INV verification receipt as canonical UTF-8 JSON bytes."""

    try:
        data = bound_verification_receipt_to_data(receipt)
    except INVVerificationReceiptRepresentationError as exc:
        raise INVVerificationReceiptEncodingError(
            "unsupported INV verification receipt"
        ) from exc

    return encode_bound_verification_receipt_data(data)


def decode_bound_verification_receipt_data(
    encoded: bytes,
) -> dict[str, Any]:
    """Decode only exact canonical verification receipt bytes."""

    if type(encoded) is not bytes:
        raise INVVerificationReceiptEncodingError(
            "verification receipt encoding must be bytes"
        )

    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise INVVerificationReceiptEncodingError(
            "verification receipt encoding must be valid UTF-8"
        ) from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise INVVerificationReceiptEncodingError(
            "verification receipt encoding must be valid JSON"
        ) from exc

    if type(data) is not dict:
        raise INVVerificationReceiptEncodingError(
            "verification receipt encoding must contain a mapping"
        )

    try:
        canonical = encode_bound_verification_receipt_data(data)
    except INVVerificationReceiptEncodingError:
        raise

    if canonical != encoded:
        raise INVVerificationReceiptEncodingError(
            "verification receipt encoding is not canonical"
        )

    return data


def decode_bound_verification_receipt(
    encoded: bytes,
) -> BoundVerificationReceipt:
    """Decode canonical bytes into represented evidence without verifying it."""

    data = decode_bound_verification_receipt_data(encoded)

    try:
        return bound_verification_receipt_from_data(data)
    except INVVerificationReceiptRepresentationError as exc:
        raise INVVerificationReceiptEncodingError(
            "verification receipt representation is invalid"
        ) from exc
