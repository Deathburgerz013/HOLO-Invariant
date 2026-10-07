"""Canonical byte encoding for INV verification receipt records."""

import json
from typing import Any

from holosim.inv_verification_receipt_record import (
    BoundVerificationReceiptRecord,
)
from holosim.inv_verification_receipt_record_serialization import (
    INVVerificationReceiptRecordRepresentationError,
    bound_verification_receipt_record_from_data,
    bound_verification_receipt_record_to_data,
)


class INVVerificationReceiptRecordEncodingError(ValueError):
    """Raised when canonical verification receipt record encoding is invalid."""


def encode_bound_verification_receipt_record_data(data: Any) -> bytes:
    """Encode supported verification receipt record data as canonical UTF-8 JSON."""

    try:
        record = bound_verification_receipt_record_from_data(data)
        normalized = bound_verification_receipt_record_to_data(record)
    except INVVerificationReceiptRecordRepresentationError as exc:
        raise INVVerificationReceiptRecordEncodingError(
            "invalid verification receipt record representation"
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
        raise INVVerificationReceiptRecordEncodingError(
            "verification receipt record representation cannot be encoded"
        ) from exc

    return text.encode("utf-8")


def encode_bound_verification_receipt_record(
    record: BoundVerificationReceiptRecord,
) -> bytes:
    """Encode a verification receipt record as canonical bytes."""

    try:
        data = bound_verification_receipt_record_to_data(record)
    except INVVerificationReceiptRecordRepresentationError as exc:
        raise INVVerificationReceiptRecordEncodingError(
            "invalid verification receipt record"
        ) from exc

    return encode_bound_verification_receipt_record_data(data)


def decode_bound_verification_receipt_record_data(
    encoded: bytes,
) -> dict[str, Any]:
    """Decode only the canonical byte representation of supported record data."""

    if type(encoded) is not bytes:
        raise INVVerificationReceiptRecordEncodingError(
            "encoded verification receipt record must be bytes"
        )

    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise INVVerificationReceiptRecordEncodingError(
            "encoded verification receipt record must be valid UTF-8"
        ) from exc

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise INVVerificationReceiptRecordEncodingError(
            "encoded verification receipt record must contain valid JSON"
        ) from exc

    try:
        canonical = encode_bound_verification_receipt_record_data(data)
    except INVVerificationReceiptRecordEncodingError:
        raise

    if canonical != encoded:
        raise INVVerificationReceiptRecordEncodingError(
            "encoded verification receipt record is not canonical"
        )

    return data


def decode_bound_verification_receipt_record(
    encoded: bytes,
) -> BoundVerificationReceiptRecord:
    """Decode canonical bytes through the existing bounded reconstruction path."""

    data = decode_bound_verification_receipt_record_data(encoded)

    try:
        return bound_verification_receipt_record_from_data(data)
    except INVVerificationReceiptRecordRepresentationError as exc:
        raise INVVerificationReceiptRecordEncodingError(
            "invalid verification receipt record representation"
        ) from exc