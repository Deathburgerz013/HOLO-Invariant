"""Read-only IDX coherence gate for cycle-state projection research.

This gate checks declared snapshot relationships only. It does not
authenticate receipts or establish completion, truth, or authority.
"""

from collections.abc import Mapping, Sequence


def check_idx_coherence(
    snapshot: Mapping,
    receipts: Sequence[Mapping],
) -> dict:
    """Return a bounded coherence observation, never an authorization."""
    reasons = []

    if not isinstance(snapshot, Mapping):
        snapshot = {}
        reasons.append("INVALID_SNAPSHOT")

    if not isinstance(receipts, (list, tuple)):
        receipts = []
        reasons.append("INVALID_RECEIPTS")

    idx = snapshot.get("idx_identity")
    hashes = snapshot.get("receipt_hashes")

    if not isinstance(idx, str) or not idx:
        reasons.append("IDX_IDENTITY_REQUIRED")

    if (
        not isinstance(hashes, list)
        or not hashes
        or any(not isinstance(h, str) or not h for h in hashes)
        or len(hashes) != len(set(hashes))
    ):
        reasons.append("INVALID_RECEIPT_MANIFEST")
        hashes = []

    observed = []
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            reasons.append("INVALID_RECEIPT")
            continue

        receipt_hash = receipt.get("receipt_hash")
        if not isinstance(receipt_hash, str) or not receipt_hash:
            reasons.append("RECEIPT_HASH_REQUIRED")
        else:
            observed.append(receipt_hash)

        receipt_idx = receipt.get("idx_identity")
        if not isinstance(receipt_idx, str) or not receipt_idx:
            reasons.append("IDX_IDENTITY_REQUIRED")
        elif isinstance(idx, str) and receipt_idx != idx:
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
