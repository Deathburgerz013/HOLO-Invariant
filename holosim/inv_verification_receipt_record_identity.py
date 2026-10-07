"""Content identity for canonical INV verification receipt record bytes."""

import hashlib
import hmac

from holosim.inv_verification_receipt_record_encoding import (
    INVVerificationReceiptRecordEncodingError,
    decode_bound_verification_receipt_record_data,
)


class INVVerificationReceiptRecordIdentityError(ValueError):
    """Raised when verification receipt record identity input is invalid."""


def bound_verification_receipt_record_content_id(encoded: bytes) -> str:
    """Hash exact supplied canonical record bytes without semantic verification."""

    if type(encoded) is not bytes:
        raise INVVerificationReceiptRecordIdentityError(
            "encoded verification receipt record must be bytes"
        )

    try:
        decode_bound_verification_receipt_record_data(encoded)
    except INVVerificationReceiptRecordEncodingError as exc:
        raise INVVerificationReceiptRecordIdentityError(
            "verification receipt record bytes must be canonical"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def verify_bound_verification_receipt_record_content_id(
    encoded: bytes,
    expected_content_id: str,
) -> bool:
    """Compare canonical record bytes with an independently supplied identity."""

    if type(expected_content_id) is not str:
        raise INVVerificationReceiptRecordIdentityError(
            "expected content identifier must be a string"
        )

    if len(expected_content_id) != 64:
        raise INVVerificationReceiptRecordIdentityError(
            "expected content identifier must contain 64 hexadecimal characters"
        )

    try:
        identifier_bytes = bytes.fromhex(expected_content_id)
    except ValueError as exc:
        raise INVVerificationReceiptRecordIdentityError(
            "expected content identifier must be hexadecimal"
        ) from exc

    if len(identifier_bytes) != 32:
        raise INVVerificationReceiptRecordIdentityError(
            "expected content identifier must decode to 32 bytes"
        )

    actual = bound_verification_receipt_record_content_id(encoded)

    return hmac.compare_digest(actual, expected_content_id.lower())