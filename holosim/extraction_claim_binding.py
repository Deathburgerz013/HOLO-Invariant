"""Read-only binding between a grounded extraction and a declared claim.

This boundary records correspondence only. It does not establish truth,
acceptance, write authority, or execution authority.
"""

from __future__ import annotations

import re
from typing import Any

from holosim.canonical import stable_hash


BINDING_TYPE = "extraction_claim_binding"
BINDING_VERSION = 1


class ExtractionClaimBindingError(ValueError):
    """Raised when extraction-to-claim correspondence is malformed."""


def build_extraction_claim_binding(
    *,
    extraction_hash: str,
    claim_id: str,
) -> dict[str, Any]:
    """Bind one exact extraction identity to one declared claim identity."""
    if (
        type(extraction_hash) is not str
        or re.fullmatch(r"[0-9a-f]{64}", extraction_hash) is None
    ):
        raise ExtractionClaimBindingError(
            "extraction_hash must be a SHA-256 hex digest"
        )
    if type(claim_id) is not str or not claim_id.strip():
        raise ExtractionClaimBindingError(
            "claim_id must be a nonempty string"
        )

    body = {
        "type": BINDING_TYPE,
        "version": BINDING_VERSION,
        "extraction_hash": extraction_hash,
        "claim_id": claim_id,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "binding_hash": stable_hash(body)}


def verify_extraction_claim_binding(binding: Any) -> bool:
    """Rebuild the closed binding and reject semantic tampering."""
    expected_fields = {
        "type", "version", "extraction_hash", "claim_id",
        "truth_claimed", "accepted", "write_authority",
        "execution_authority", "binding_hash",
    }
    if type(binding) is not dict or set(binding) != expected_fields:
        raise ExtractionClaimBindingError("binding fields mismatch")
    if binding["type"] != BINDING_TYPE or binding["version"] != BINDING_VERSION:
        raise ExtractionClaimBindingError("binding schema mismatch")

    expected = build_extraction_claim_binding(
        extraction_hash=binding["extraction_hash"],
        claim_id=binding["claim_id"],
    )
    if dict(binding) != expected:
        raise ExtractionClaimBindingError("binding is internally inconsistent")
    return True


def verify_extraction_claim_correspondence(
    binding: Any,
    *,
    extraction_hash: str,
    claim_id: str,
) -> bool:
    """Verify one binding corresponds to the exact presented identities."""
    verify_extraction_claim_binding(binding)
    if binding["extraction_hash"] != extraction_hash:
        raise ExtractionClaimBindingError(
            "binding does not correspond to extraction"
        )
    if binding["claim_id"] != claim_id:
        raise ExtractionClaimBindingError(
            "binding does not correspond to claim"
        )
    return True
