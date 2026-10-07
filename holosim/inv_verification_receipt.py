"""Bounded evidence receipt for successful INV bound record verification."""

from dataclasses import dataclass

from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_identity import (
    receipt_content_id,
    verify_receipt_content_id,
)
from holosim.inv_receipt_record_identity import (
    bound_receipt_record_content_id,
)
from holosim.inv_receipt_record_verification import (
    INVReceiptRecordVerificationError,
    verify_canonical_bound_receipt_record,
)


class INVVerificationReceiptError(ValueError):
    """Raised when an INV verification receipt is invalid."""


@dataclass(frozen=True)
class BoundVerificationReceipt:
    expected_outer_content_id: str
    observed_outer_content_id: str
    verified_receipt_bytes: bytes
    verified_receipt_content_id: str
    outer_identity_verified: bool
    canonical_record_verified: bool
    inner_binding_verified: bool
    receipt_reconstructed: bool
    semantic_verification_passed: bool
    accepted: bool
    truth_claimed: bool
    write_authority: str
    execution_authority: str


def build_bound_verification_receipt(
    encoded_record: bytes,
    expected_outer_content_id: str,
) -> BoundVerificationReceipt:
    """Verify through Experiment 014 and preserve bounded verification evidence."""

    try:
        receipt = verify_canonical_bound_receipt_record(
            encoded_record,
            expected_outer_content_id,
        )
    except INVReceiptRecordVerificationError as exc:
        raise INVVerificationReceiptError(
            "bound record verification failed"
        ) from exc

    observed_outer_content_id = bound_receipt_record_content_id(
        encoded_record
    )
    verified_receipt_bytes = encode_receipt(receipt)
    verified_receipt_content_id = receipt_content_id(
        verified_receipt_bytes
    )

    return BoundVerificationReceipt(
        expected_outer_content_id=expected_outer_content_id.lower(),
        observed_outer_content_id=observed_outer_content_id,
        verified_receipt_bytes=verified_receipt_bytes,
        verified_receipt_content_id=verified_receipt_content_id,
        outer_identity_verified=True,
        canonical_record_verified=True,
        inner_binding_verified=True,
        receipt_reconstructed=True,
        semantic_verification_passed=True,
        accepted=False,
        truth_claimed=False,
        write_authority="NONE",
        execution_authority="NONE",
    )


def verify_bound_verification_receipt(
    receipt: BoundVerificationReceipt,
) -> bool:
    """Verify represented historical evidence without re-verifying its record."""

    if type(receipt) is not BoundVerificationReceipt:
        raise INVVerificationReceiptError(
            "unsupported INV verification receipt"
        )

    identifiers = (
        receipt.expected_outer_content_id,
        receipt.observed_outer_content_id,
        receipt.verified_receipt_content_id,
    )

    for identifier in identifiers:
        if type(identifier) is not str or len(identifier) != 64:
            raise INVVerificationReceiptError(
                "verification receipt contains invalid content identifier"
            )
        try:
            decoded_identifier = bytes.fromhex(identifier)
        except ValueError as exc:
            raise INVVerificationReceiptError(
                "verification receipt contains invalid content identifier"
            ) from exc

        if len(decoded_identifier) != 32:
            raise INVVerificationReceiptError(
                "verification receipt contains invalid content identifier"
            )

    if type(receipt.verified_receipt_bytes) is not bytes:
        raise INVVerificationReceiptError(
            "verified receipt evidence must be bytes"
        )

    if (
        receipt.expected_outer_content_id.lower()
        != receipt.observed_outer_content_id.lower()
    ):
        return False

    try:
        verified_receipt_identity_valid = verify_receipt_content_id(
            receipt.verified_receipt_bytes,
            receipt.verified_receipt_content_id,
        )
    except (TypeError, ValueError) as exc:
        raise INVVerificationReceiptError(
            "invalid verified receipt content binding"
        ) from exc

    if not verified_receipt_identity_valid:
        return False

    check_fields = (
        receipt.outer_identity_verified,
        receipt.canonical_record_verified,
        receipt.inner_binding_verified,
        receipt.receipt_reconstructed,
        receipt.semantic_verification_passed,
    )

    if any(type(value) is not bool for value in check_fields):
        raise INVVerificationReceiptError(
            "verification receipt contains invalid check outcome"
        )

    if not all(check_fields):
        return False

    if type(receipt.accepted) is not bool or receipt.accepted is not False:
        raise INVVerificationReceiptError(
            "verification receipt cannot grant acceptance"
        )

    if (
        type(receipt.truth_claimed) is not bool
        or receipt.truth_claimed is not False
    ):
        raise INVVerificationReceiptError(
            "verification receipt cannot claim truth"
        )

    if receipt.write_authority != "NONE":
        raise INVVerificationReceiptError(
            "verification receipt cannot grant write authority"
        )

    if receipt.execution_authority != "NONE":
        raise INVVerificationReceiptError(
            "verification receipt cannot grant execution authority"
        )

    return True
