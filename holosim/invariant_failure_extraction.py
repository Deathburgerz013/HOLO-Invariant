from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.environment_invariant_receipts import (
    EnvironmentInvariantReceiptError,
    verify_environment_invariant_receipt,
)


RECEIPT_TYPE = "holo_invariant_failure_extraction_receipt"
RECEIPT_VERSION = 1


class InvariantFailureExtractionError(ValueError):
    """Raised when a demonstrated invariant failure cannot be extracted honestly."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise InvariantFailureExtractionError(str(exc)) from exc


def extract_invariant_failure(
    invariant_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract only an environment invariant that was actually FAILED."""
    try:
        verify_environment_invariant_receipt(invariant_receipt)
    except EnvironmentInvariantReceiptError as exc:
        raise InvariantFailureExtractionError(
            "invariant receipt is invalid"
        ) from exc

    if invariant_receipt.get("status") != "FAILED":
        raise InvariantFailureExtractionError(
            f"invariant receipt is not FAILED: "
            f"{invariant_receipt.get('status')!r}"
        )

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "invariant_id": invariant_receipt["invariant_id"],
        "statement": invariant_receipt["statement"],
        "check_id": invariant_receipt["check_id"],
        "observed_at": invariant_receipt["observed_at"],
        "declared_environment_fingerprint": invariant_receipt[
            "declared_environment_fingerprint"
        ],
        "observed_environment": invariant_receipt["observed_environment"],
        "environment_fingerprint": invariant_receipt[
            "environment_fingerprint"
        ],
        "source_receipt_hash": invariant_receipt["receipt_hash"],
        "status": "DEMONSTRATED_FAILURE",
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {**body, "receipt_hash": _hash(body)}


def verify_invariant_failure_extraction(
    receipt: Mapping[str, Any],
    *,
    invariant_receipt: Mapping[str, Any],
) -> bool:
    """Rebuild the failure extraction and require exact identity."""
    if type(receipt) is not dict:
        raise InvariantFailureExtractionError(
            "receipt must be a plain object"
        )

    expected = extract_invariant_failure(invariant_receipt)

    if dict(receipt) != expected:
        raise InvariantFailureExtractionError(
            "failure extraction does not match source invariant receipt"
        )

    return True