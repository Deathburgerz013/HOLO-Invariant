"""Bounded plain-data serialization for INV verification receipt records."""

from typing import Any

from holosim.inv_verification_receipt_record import (
    BoundVerificationReceiptRecord,
)


class INVVerificationReceiptRecordRepresentationError(ValueError):
    """Raised when an INV verification receipt record representation is invalid."""


def bound_verification_receipt_record_to_data(
    record: BoundVerificationReceiptRecord,
) -> dict[str, Any]:
    """Convert a bounded verification receipt record into plain supported data."""

    if type(record) is not BoundVerificationReceiptRecord:
        raise INVVerificationReceiptRecordRepresentationError(
            "unsupported INV verification receipt record"
        )

    if type(record.encoded_verification_receipt) is not bytes:
        raise INVVerificationReceiptRecordRepresentationError(
            "verification receipt evidence must be bytes"
        )

    if type(record.content_id) is not str:
        raise INVVerificationReceiptRecordRepresentationError(
            "verification receipt record content identifier must be a string"
        )

    return {
        "encoded_verification_receipt_hex": (
            record.encoded_verification_receipt.hex()
        ),
        "content_id": record.content_id,
    }


def bound_verification_receipt_record_from_data(
    data: Any,
) -> BoundVerificationReceiptRecord:
    """Reconstruct a verification receipt record from supported plain data."""

    if type(data) is not dict:
        raise INVVerificationReceiptRecordRepresentationError(
            "verification receipt record representation must be a mapping"
        )

    expected_keys = {
        "encoded_verification_receipt_hex",
        "content_id",
    }

    if set(data.keys()) != expected_keys:
        raise INVVerificationReceiptRecordRepresentationError(
            "verification receipt record representation contains unsupported fields"
        )

    encoded_receipt_hex = data["encoded_verification_receipt_hex"]
    content_id = data["content_id"]

    if type(encoded_receipt_hex) is not str:
        raise INVVerificationReceiptRecordRepresentationError(
            "encoded verification receipt representation must be a string"
        )

    if type(content_id) is not str:
        raise INVVerificationReceiptRecordRepresentationError(
            "verification receipt record content identifier must be a string"
        )

    if len(encoded_receipt_hex) % 2 != 0:
        raise INVVerificationReceiptRecordRepresentationError(
            "encoded verification receipt representation must contain complete bytes"
        )

    try:
        encoded_verification_receipt = bytes.fromhex(encoded_receipt_hex)
    except ValueError as exc:
        raise INVVerificationReceiptRecordRepresentationError(
            "encoded verification receipt representation must be hexadecimal"
        ) from exc

    try:
        from holosim.inv_verification_receipt_encoding import (
            decode_bound_verification_receipt,
        )

        decode_bound_verification_receipt(encoded_verification_receipt)
    except Exception as exc:
        raise INVVerificationReceiptRecordRepresentationError(
            "encoded verification receipt representation must be canonical"
        ) from exc

    if len(content_id) != 64:
        raise INVVerificationReceiptRecordRepresentationError(
            "verification receipt record content identifier must be 64 hexadecimal characters"
        )

    try:
        bytes.fromhex(content_id)
    except ValueError as exc:
        raise INVVerificationReceiptRecordRepresentationError(
            "verification receipt record content identifier must be hexadecimal"
        ) from exc

    return BoundVerificationReceiptRecord(
        encoded_verification_receipt=encoded_verification_receipt,
        content_id=content_id,
    )
