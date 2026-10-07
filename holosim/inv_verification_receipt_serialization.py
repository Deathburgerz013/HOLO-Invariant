"""Bounded plain-data representation for INV verification receipts."""

from collections.abc import Mapping
from typing import Any

from holosim.inv_verification_receipt import BoundVerificationReceipt


class INVVerificationReceiptRepresentationError(ValueError):
    """Raised when verification receipt representation is unsupported."""


_FIELDS = {
    "expected_outer_content_id",
    "observed_outer_content_id",
    "verified_receipt_hex",
    "verified_receipt_content_id",
    "outer_identity_verified",
    "canonical_record_verified",
    "inner_binding_verified",
    "receipt_reconstructed",
    "semantic_verification_passed",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
}


def bound_verification_receipt_to_data(
    receipt: BoundVerificationReceipt,
) -> dict[str, Any]:
    """Convert a verification receipt to bounded plain data."""

    if type(receipt) is not BoundVerificationReceipt:
        raise INVVerificationReceiptRepresentationError(
            "unsupported INV verification receipt"
        )

    if type(receipt.verified_receipt_bytes) is not bytes:
        raise INVVerificationReceiptRepresentationError(
            "verified receipt evidence must be bytes"
        )

    return {
        "expected_outer_content_id": receipt.expected_outer_content_id,
        "observed_outer_content_id": receipt.observed_outer_content_id,
        "verified_receipt_hex": receipt.verified_receipt_bytes.hex(),
        "verified_receipt_content_id": receipt.verified_receipt_content_id,
        "outer_identity_verified": receipt.outer_identity_verified,
        "canonical_record_verified": receipt.canonical_record_verified,
        "inner_binding_verified": receipt.inner_binding_verified,
        "receipt_reconstructed": receipt.receipt_reconstructed,
        "semantic_verification_passed": receipt.semantic_verification_passed,
        "accepted": receipt.accepted,
        "truth_claimed": receipt.truth_claimed,
        "write_authority": receipt.write_authority,
        "execution_authority": receipt.execution_authority,
    }


def bound_verification_receipt_from_data(
    data: Mapping[str, Any],
) -> BoundVerificationReceipt:
    """Reconstruct represented verification evidence without verifying it."""

    if not isinstance(data, Mapping):
        raise INVVerificationReceiptRepresentationError(
            "verification receipt representation must be a mapping"
        )

    if set(data.keys()) != _FIELDS:
        raise INVVerificationReceiptRepresentationError(
            "verification receipt representation has unsupported fields"
        )

    string_fields = (
        "expected_outer_content_id",
        "observed_outer_content_id",
        "verified_receipt_hex",
        "verified_receipt_content_id",
        "write_authority",
        "execution_authority",
    )

    for field in string_fields:
        if type(data[field]) is not str:
            raise INVVerificationReceiptRepresentationError(
                f"{field} must be a string"
            )

    bool_fields = (
        "outer_identity_verified",
        "canonical_record_verified",
        "inner_binding_verified",
        "receipt_reconstructed",
        "semantic_verification_passed",
        "accepted",
        "truth_claimed",
    )

    for field in bool_fields:
        if type(data[field]) is not bool:
            raise INVVerificationReceiptRepresentationError(
                f"{field} must be a bool"
            )

    encoded_hex = data["verified_receipt_hex"]

    if encoded_hex != encoded_hex.lower():
        raise INVVerificationReceiptRepresentationError(
            "verified receipt hex must be lowercase"
        )

    try:
        verified_receipt_bytes = bytes.fromhex(encoded_hex)
    except ValueError as exc:
        raise INVVerificationReceiptRepresentationError(
            "verified receipt hex is invalid"
        ) from exc

    if verified_receipt_bytes.hex() != encoded_hex:
        raise INVVerificationReceiptRepresentationError(
            "verified receipt hex is not canonical"
        )

    return BoundVerificationReceipt(
        expected_outer_content_id=data["expected_outer_content_id"],
        observed_outer_content_id=data["observed_outer_content_id"],
        verified_receipt_bytes=verified_receipt_bytes,
        verified_receipt_content_id=data["verified_receipt_content_id"],
        outer_identity_verified=data["outer_identity_verified"],
        canonical_record_verified=data["canonical_record_verified"],
        inner_binding_verified=data["inner_binding_verified"],
        receipt_reconstructed=data["receipt_reconstructed"],
        semantic_verification_passed=data["semantic_verification_passed"],
        accepted=data["accepted"],
        truth_claimed=data["truth_claimed"],
        write_authority=data["write_authority"],
        execution_authority=data["execution_authority"],
    )
