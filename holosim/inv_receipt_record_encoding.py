"""Canonical byte encoding for INV bound receipt records."""

import json
from typing import Any

from holosim.inv_receipt_record import BoundReceiptRecord
from holosim.inv_receipt_record_serialization import (
    INVReceiptRecordRepresentationError,
    bound_receipt_record_from_data,
    bound_receipt_record_to_data,
)


class INVReceiptRecordEncodingError(ValueError):
    """Raised when canonical bound receipt record encoding is invalid."""


def encode_bound_receipt_record_data(data: Any) -> bytes:
    """Encode supported bound receipt record data as canonical UTF-8 JSON."""

    try:
        record = bound_receipt_record_from_data(data)
        normalized = bound_receipt_record_to_data(record)
    except INVReceiptRecordRepresentationError as exc:
        raise INVReceiptRecordEncodingError(
            "invalid bound receipt record representation"
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
        raise INVReceiptRecordEncodingError(
            "bound receipt record representation cannot be encoded"
        ) from exc

    return text.encode("utf-8")


def encode_bound_receipt_record(record: BoundReceiptRecord) -> bytes:
    """Encode a bound receipt record as canonical bytes."""

    try:
        data = bound_receipt_record_to_data(record)
    except INVReceiptRecordRepresentationError as exc:
        raise INVReceiptRecordEncodingError(
            "invalid bound receipt record"
        ) from exc

    return encode_bound_receipt_record_data(data)


def decode_bound_receipt_record_data(encoded: bytes) -> dict[str, Any]:
    """Decode only the canonical byte representation of supported record data."""

    if type(encoded) is not bytes:
        raise INVReceiptRecordEncodingError(
            "encoded bound receipt record must be bytes"
        )

    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise INVReceiptRecordEncodingError(
            "encoded bound receipt record must be valid UTF-8"
        ) from exc

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise INVReceiptRecordEncodingError(
            "encoded bound receipt record must contain valid JSON"
        ) from exc

    try:
        canonical = encode_bound_receipt_record_data(data)
    except INVReceiptRecordEncodingError:
        raise

    if canonical != encoded:
        raise INVReceiptRecordEncodingError(
            "encoded bound receipt record is not canonical"
        )

    return data


def decode_bound_receipt_record(encoded: bytes) -> BoundReceiptRecord:
    """Decode canonical bytes through the existing bounded reconstruction path."""

    data = decode_bound_receipt_record_data(encoded)

    try:
        return bound_receipt_record_from_data(data)
    except INVReceiptRecordRepresentationError as exc:
        raise INVReceiptRecordEncodingError(
            "invalid bound receipt record representation"
        ) from exc
