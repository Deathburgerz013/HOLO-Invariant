"""Bounded plain-data representation for INV bound receipt records."""

from typing import Any

from holosim.inv_receipt_record import BoundReceiptRecord


class INVReceiptRecordRepresentationError(ValueError):
    """Raised when a bound receipt record representation is invalid."""


_RECORD_FIELDS = {"encoded_receipt_hex", "content_id"}


def bound_receipt_record_to_data(record: BoundReceiptRecord) -> dict[str, Any]:
    """Convert a bound receipt record to bounded plain data."""

    if not isinstance(record, BoundReceiptRecord):
        raise INVReceiptRecordRepresentationError(
            "unsupported INV bound receipt record"
        )

    if type(record.encoded_receipt) is not bytes:
        raise INVReceiptRecordRepresentationError(
            "encoded receipt must be bytes"
        )

    if type(record.content_id) is not str:
        raise INVReceiptRecordRepresentationError(
            "content identifier must be a string"
        )

    return {
        "encoded_receipt_hex": record.encoded_receipt.hex(),
        "content_id": record.content_id,
    }


def bound_receipt_record_from_data(data: Any) -> BoundReceiptRecord:
    """Reconstruct a bound receipt record without repairing its content binding."""

    if type(data) is not dict:
        raise INVReceiptRecordRepresentationError(
            "bound receipt record data must be a mapping"
        )

    if set(data) != _RECORD_FIELDS:
        raise INVReceiptRecordRepresentationError(
            "bound receipt record fields do not match the supported representation"
        )

    encoded_receipt_hex = data["encoded_receipt_hex"]
    content_id = data["content_id"]

    if type(encoded_receipt_hex) is not str:
        raise INVReceiptRecordRepresentationError(
            "encoded receipt representation must be a string"
        )

    if type(content_id) is not str:
        raise INVReceiptRecordRepresentationError(
            "content identifier must be a string"
        )

    if len(encoded_receipt_hex) % 2 != 0:
        raise INVReceiptRecordRepresentationError(
            "encoded receipt representation must contain complete hexadecimal bytes"
        )

    try:
        encoded_receipt = bytes.fromhex(encoded_receipt_hex)
    except ValueError as exc:
        raise INVReceiptRecordRepresentationError(
            "encoded receipt representation must be hexadecimal"
        ) from exc

    if encoded_receipt.hex() != encoded_receipt_hex:
        raise INVReceiptRecordRepresentationError(
            "encoded receipt representation must use canonical lowercase hexadecimal"
        )

    return BoundReceiptRecord(
        encoded_receipt=encoded_receipt,
        content_id=content_id,
    )
