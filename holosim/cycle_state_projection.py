"""Read-only declared-identity coherence gate for cycle-state research.

This checks only snapshot IDX identity and receipt-hash membership.

Non-goals: Frozen IDX active-hash/slot/order validation, frame and episode
coherence, cryptographic receipt verification, source-receipt attribution,
completion determination, and authorization.

A coherent result is not sufficient to advance a cycle-state projection.
"""

from collections.abc import Mapping


def _identity(value):
    """Accept only nonempty, whitespace-canonical strings."""
    return isinstance(value, str) and bool(value) and value == value.strip()


def check_idx_coherence(snapshot: Mapping, receipts) -> dict:
    """Observe declared relationships without establishing integrity or authority."""
    reasons = []

    if not isinstance(snapshot, Mapping):
        snapshot = {}
        reasons.append("INVALID_SNAPSHOT")

    if not isinstance(receipts, (list, tuple)):
        receipts = []
        reasons.append("INVALID_RECEIPTS")

    idx = snapshot.get("idx_identity")
    hashes = snapshot.get("receipt_hashes")

    if not _identity(idx):
        reasons.append("IDX_IDENTITY_REQUIRED")

    if (
        not isinstance(hashes, (list, tuple))
        or any(not _identity(h) for h in hashes)
        or (
            isinstance(hashes, (list, tuple))
            and len(hashes) != len(set(h for h in hashes if _identity(h)))
        )
    ):
        reasons.append("INVALID_RECEIPT_MANIFEST")
        hashes = []

    observed = []
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            reasons.append("INVALID_RECEIPT")
            continue

        receipt_hash = receipt.get("receipt_hash")
        if not _identity(receipt_hash):
            reasons.append("RECEIPT_HASH_REQUIRED")
        else:
            observed.append(receipt_hash)

        receipt_idx = receipt.get("idx_identity")
        if not _identity(receipt_idx):
            reasons.append("IDX_IDENTITY_REQUIRED")
        elif _identity(idx) and receipt_idx != idx:
            reasons.append("IDX_IDENTITY_MISMATCH")

    if len(observed) != len(set(observed)):
        reasons.append("DUPLICATE_RECEIPT")

    if sorted(observed) != sorted(hashes):
        reasons.append("SNAPSHOT_RECEIPT_MISMATCH")

    reasons = sorted(set(reasons))
    return {
        "state": "BLOCKED_INVARIANT" if reasons else None,
        "coherent": not reasons,
        "reason_codes": reasons,
        "integrity_verified": False,
        "truth_claimed": False,
        "accepted": False,
        "execution_authorized": False,
        "state_change_authorized": False,
        "write_authority": "NONE",
    }
