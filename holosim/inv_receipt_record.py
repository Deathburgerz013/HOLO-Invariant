"""Bound record for canonical INV receipt bytes and content identity."""

from dataclasses import dataclass

from holosim.inv_receipt_encoding import decode_receipt
from holosim.inv_receipt_identity import (
    receipt_content_id,
    verify_receipt_content_id,
)
from holosim.inv_runtime import TransitionDecisionReceipt


class INVReceiptRecordError(ValueError):
    """Raised when a bound INV receipt record cannot be used safely."""


@dataclass(frozen=True)
class BoundReceiptRecord:
    encoded_receipt: bytes
    content_id: str


def bind_receipt_bytes(encoded_receipt: bytes) -> BoundReceiptRecord:
    """Bind exact canonical receipt bytes to their deterministic content ID."""

    if type(encoded_receipt) is not bytes:
        raise INVReceiptRecordError("encoded receipt must be bytes")

    return BoundReceiptRecord(
        encoded_receipt=encoded_receipt,
        content_id=receipt_content_id(encoded_receipt),
    )


def verify_bound_receipt_record(record: BoundReceiptRecord) -> bool:
    """Verify that the record's content ID still matches its stored bytes."""

    if not isinstance(record, BoundReceiptRecord):
        raise INVReceiptRecordError("unsupported INV receipt record")

    try:
        return verify_receipt_content_id(
            record.encoded_receipt,
            record.content_id,
        )
    except (TypeError, ValueError) as exc:
        raise INVReceiptRecordError("invalid INV receipt record") from exc


def reconstruct_bound_receipt(
    record: BoundReceiptRecord,
) -> TransitionDecisionReceipt:
    """Verify content binding, then reconstruct through canonical decoding."""

    if not verify_bound_receipt_record(record):
        raise INVReceiptRecordError("INV receipt record content binding mismatch")

    return decode_receipt(record.encoded_receipt)
