"""Deterministic content identity for canonical INV bound receipt record bytes."""

import hashlib
import hmac


class INVReceiptRecordIdentityError(ValueError):
    """Raised when INV bound receipt record content identity input is invalid."""


def bound_receipt_record_content_id(encoded: bytes) -> str:
    """Derive a deterministic content identifier from exact canonical record bytes."""

    if type(encoded) is not bytes:
        raise INVReceiptRecordIdentityError(
            "encoded bound receipt record must be bytes"
        )

    return hashlib.sha256(encoded).hexdigest()


def verify_bound_receipt_record_content_id(
    encoded: bytes,
    expected_content_id: str,
) -> bool:
    """Verify exact record bytes against an expected content identifier."""

    if type(encoded) is not bytes:
        raise INVReceiptRecordIdentityError(
            "encoded bound receipt record must be bytes"
        )

    if type(expected_content_id) is not str:
        raise INVReceiptRecordIdentityError(
            "expected content identifier must be a string"
        )

    if len(expected_content_id) != 64:
        raise INVReceiptRecordIdentityError(
            "expected content identifier must contain 64 hexadecimal characters"
        )

    try:
        bytes.fromhex(expected_content_id)
    except ValueError as exc:
        raise INVReceiptRecordIdentityError(
            "expected content identifier must contain 64 hexadecimal characters"
        ) from exc

    actual_content_id = bound_receipt_record_content_id(encoded)

    return hmac.compare_digest(
        actual_content_id,
        expected_content_id.lower(),
    )
