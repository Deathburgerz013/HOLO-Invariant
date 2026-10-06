"""Bounded verification path for canonical INV bound receipt records."""

from holosim.inv_receipt_record import (
    INVReceiptRecordError,
    reconstruct_bound_receipt,
    verify_bound_receipt_record,
)
from holosim.inv_receipt_record_encoding import (
    INVReceiptRecordEncodingError,
    decode_bound_receipt_record,
)
from holosim.inv_receipt_record_identity import (
    INVReceiptRecordIdentityError,
    verify_bound_receipt_record_content_id,
)
from holosim.inv_runtime import (
    TransitionDecisionReceipt,
    verify_transition_receipt,
)


class INVReceiptRecordVerificationError(ValueError):
    """Raised when bounded INV receipt record verification fails."""


def verify_canonical_bound_receipt_record(
    encoded_record: bytes,
    expected_content_id: str,
) -> TransitionDecisionReceipt:
    """Verify the complete established INV bound receipt record chain."""

    try:
        outer_identity_valid = verify_bound_receipt_record_content_id(
            encoded_record,
            expected_content_id,
        )
    except INVReceiptRecordIdentityError as exc:
        raise INVReceiptRecordVerificationError(
            "invalid outer content identity input"
        ) from exc

    if not outer_identity_valid:
        raise INVReceiptRecordVerificationError(
            "outer content identity mismatch"
        )

    try:
        record = decode_bound_receipt_record(encoded_record)
    except INVReceiptRecordEncodingError as exc:
        raise INVReceiptRecordVerificationError(
            "invalid canonical bound receipt record"
        ) from exc

    try:
        inner_binding_valid = verify_bound_receipt_record(record)
    except INVReceiptRecordError as exc:
        raise INVReceiptRecordVerificationError(
            "invalid inner content binding"
        ) from exc

    if not inner_binding_valid:
        raise INVReceiptRecordVerificationError(
            "inner content binding mismatch"
        )

    try:
        receipt = reconstruct_bound_receipt(record)
    except INVReceiptRecordError as exc:
        raise INVReceiptRecordVerificationError(
            "bound receipt reconstruction failed"
        ) from exc

    if not verify_transition_receipt(receipt):
        raise INVReceiptRecordVerificationError(
            "transition receipt semantic contradiction"
        )

    return receipt
