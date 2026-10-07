"""Deterministic content identity for canonical INV verification receipt bytes."""

import hashlib
import hmac


class INVVerificationReceiptIdentityError(ValueError):
    """Raised when verification receipt content identity input is unsupported."""


def bound_verification_receipt_content_id(encoded: bytes) -> str:
    """Derive SHA-256 content identity from exact supplied bytes."""

    if type(encoded) is not bytes:
        raise INVVerificationReceiptIdentityError(
            "verification receipt content must be bytes"
        )

    return hashlib.sha256(encoded).hexdigest()


def verify_bound_verification_receipt_content_id(
    encoded: bytes,
    expected_content_id: str,
) -> bool:
    """Compare exact supplied bytes against an expected SHA-256 identifier."""

    if type(encoded) is not bytes:
        raise INVVerificationReceiptIdentityError(
            "verification receipt content must be bytes"
        )

    if type(expected_content_id) is not str:
        raise INVVerificationReceiptIdentityError(
            "expected verification receipt content identifier must be a string"
        )

    if len(expected_content_id) != 64:
        raise INVVerificationReceiptIdentityError(
            "expected verification receipt content identifier must be 64 hex characters"
        )

    try:
        identifier_bytes = bytes.fromhex(expected_content_id)
    except ValueError as exc:
        raise INVVerificationReceiptIdentityError(
            "expected verification receipt content identifier must be hexadecimal"
        ) from exc

    if len(identifier_bytes) != 32:
        raise INVVerificationReceiptIdentityError(
            "expected verification receipt content identifier must decode to 32 bytes"
        )

    actual = bound_verification_receipt_content_id(encoded)

    return hmac.compare_digest(
        actual,
        expected_content_id.lower(),
    )
