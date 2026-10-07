"""Content-bound records for canonical INV verification receipt bytes."""

from dataclasses import dataclass

from holosim.inv_verification_receipt_identity import (
    INVVerificationReceiptIdentityError,
    bound_verification_receipt_content_id,
    verify_bound_verification_receipt_content_id,
)


class INVVerificationReceiptRecordError(ValueError):
    """Raised when a bound verification receipt record is unsupported."""


@dataclass(frozen=True)
class BoundVerificationReceiptRecord:
    encoded_verification_receipt: bytes
    content_id: str


def bind_verification_receipt_bytes(
    encoded_verification_receipt: bytes,
) -> BoundVerificationReceiptRecord:
    """Bind exact verification receipt bytes to their derived content identifier."""

    if type(encoded_verification_receipt) is not bytes:
        raise INVVerificationReceiptRecordError(
            "verification receipt content must be bytes"
        )

    content_id = bound_verification_receipt_content_id(
        encoded_verification_receipt
    )

    return BoundVerificationReceiptRecord(
        encoded_verification_receipt=encoded_verification_receipt,
        content_id=content_id,
    )


def verify_bound_verification_receipt_record(
    record: BoundVerificationReceiptRecord,
) -> bool:
    """Verify only the bytes-to-content-identifier relationship."""

    if type(record) is not BoundVerificationReceiptRecord:
        raise INVVerificationReceiptRecordError(
            "record must be a BoundVerificationReceiptRecord"
        )

    if type(record.encoded_verification_receipt) is not bytes:
        raise INVVerificationReceiptRecordError(
            "bound verification receipt content must be bytes"
        )

    if type(record.content_id) is not str:
        raise INVVerificationReceiptRecordError(
            "bound verification receipt content identifier must be a string"
        )

    try:
        return verify_bound_verification_receipt_content_id(
            record.encoded_verification_receipt,
            record.content_id,
        )
    except INVVerificationReceiptIdentityError as exc:
        raise INVVerificationReceiptRecordError(
            "bound verification receipt content identifier is invalid"
        ) from exc
