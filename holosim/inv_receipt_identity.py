"""Deterministic content identity for canonical INV receipt bytes."""

import hashlib
import hmac


class INVReceiptIdentityError(ValueError):
    """Raised when INV receipt content identity input is invalid."""


def receipt_content_id(encoded: bytes) -> str:
    """Derive a deterministic SHA-256 identifier from exact canonical bytes."""

    if type(encoded) is not bytes:
        raise INVReceiptIdentityError("encoded receipt must be bytes")

    return hashlib.sha256(encoded).hexdigest()


def verify_receipt_content_id(
    encoded: bytes,
    expected_content_id: str,
) -> bool:
    """Check exact receipt bytes against an expected SHA-256 identifier."""

    if type(encoded) is not bytes:
        raise INVReceiptIdentityError("encoded receipt must be bytes")

    if type(expected_content_id) is not str:
        raise INVReceiptIdentityError("expected content identifier must be a string")

    if len(expected_content_id) != 64:
        raise INVReceiptIdentityError(
            "expected content identifier must contain 64 hexadecimal characters"
        )

    try:
        bytes.fromhex(expected_content_id)
    except ValueError as exc:
        raise INVReceiptIdentityError(
            "expected content identifier must contain 64 hexadecimal characters"
        ) from exc

    actual_content_id = receipt_content_id(encoded)

    return hmac.compare_digest(
        actual_content_id,
        expected_content_id.lower(),
    )
