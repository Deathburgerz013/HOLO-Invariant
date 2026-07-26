"""Version-bound correction receipts for HOLO/Sim.

A correction receipt preserves the state before a proposal, the proposal
itself, the resulting state, and the evidence-backed reason for the
transition. It records a correction without granting truth, acceptance, or
write authority.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Iterable, Mapping

from holosim.canonical import stable_hash


RECEIPT_TYPE = "correction_receipt"
RECEIPT_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_receipt_hash(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hash")
    return value


def _normalize_evidence(
    evidence_receipt_hashes: Iterable[Any],
) -> list[str]:
    if isinstance(evidence_receipt_hashes, (str, bytes)):
        raise ValueError("evidence_receipt_hashes must be an iterable of hashes")

    evidence = [
        _require_receipt_hash(value, "evidence receipt hash")
        for value in evidence_receipt_hashes
    ]

    if not evidence:
        raise ValueError("at least one evidence receipt hash is required")

    if len(set(evidence)) != len(evidence):
        raise ValueError("evidence receipt hashes must be unique")

    return evidence


def record_correction(
    previous_receipt_hash: Any,
    proposed_receipt_hash: Any,
    resulting_receipt_hash: Any,
    reason: Any,
    evidence_receipt_hashes: Iterable[Any],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record one evidence-backed state correction.

    The resulting state may match the proposal, the previous state, or a
    third state. This permits forward correction, rejection, and rollback
    without erasing any of the compared states.
    """

    previous_hash = _require_receipt_hash(
        previous_receipt_hash,
        "previous_receipt_hash",
    )
    proposed_hash = _require_receipt_hash(
        proposed_receipt_hash,
        "proposed_receipt_hash",
    )
    resulting_hash = _require_receipt_hash(
        resulting_receipt_hash,
        "resulting_receipt_hash",
    )

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string")

    evidence = _normalize_evidence(evidence_receipt_hashes)
    copied_metadata = deepcopy(dict(metadata or {}))

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "previous_receipt_hash": previous_hash,
        "proposed_receipt_hash": proposed_hash,
        "resulting_receipt_hash": resulting_hash,
        "reason": reason.strip(),
        "evidence_receipt_hashes": evidence,
        "metadata": copied_metadata,
        "changed": resulting_hash != previous_hash,
        "proposal_adopted": resulting_hash == proposed_hash,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }
