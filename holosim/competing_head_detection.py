"""Bounded detection of competing sibling heads.

A structural fork exists when distinct declared head identities share the same declared parent identity. Detection preserves the competing identities and does not select, merge, accept, reject, or authorize any head.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from holosim.canonical import stable_hash

RECEIPT_TYPE = "competing_head_detection_receipt"
RECEIPT_VERSION = 1
NO_FORK = "NO_FORK"
CONFLICT = "CONFLICT"
_HEAD_FIELDS = {"head_hash", "parent_hash"}


class CompetingHeadDetectionError(ValueError):
    """Raised when declared candidate-head structure is invalid."""


def _required_identity(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise CompetingHeadDetectionError(f"{field} must be a nonempty string")
    if value != value.strip():
        raise CompetingHeadDetectionError(f"{field} cannot contain outer whitespace")
    return value


def _validate_heads(heads: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    if type(heads) not in {list, tuple}:
        raise CompetingHeadDetectionError("heads must be a list or tuple")
    checked = []
    seen = set()
    for index, head in enumerate(heads):
        if not isinstance(head, Mapping):
            raise CompetingHeadDetectionError(f"heads[{index}] must be a mapping")
        if set(head) != _HEAD_FIELDS:
            raise CompetingHeadDetectionError(f"heads[{index}] fields must be exactly head_hash and parent_hash")
        head_hash = _required_identity(head["head_hash"], f"heads[{index}].head_hash")
        parent_hash = _required_identity(head["parent_hash"], f"heads[{index}].parent_hash")
        if head_hash in seen:
            raise CompetingHeadDetectionError("head hashes must be unique")
        seen.add(head_hash)
        checked.append({"head_hash": head_hash, "parent_hash": parent_hash})
    return checked


def detect_competing_heads(*, heads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Detect shared-parent divergence without choosing a successor."""
    checked_heads = _validate_heads(heads)
    by_parent = defaultdict(list)
    for head in checked_heads:
        by_parent[head["parent_hash"]].append(head["head_hash"])
    fork_parent_hashes = sorted(parent for parent, children in by_parent.items() if len(children) > 1)
    competing_heads = [sorted(by_parent[parent]) for parent in fork_parent_hashes]
    status = CONFLICT if competing_heads else NO_FORK
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "heads": checked_heads,
        "status": status,
        "fork_parent_hashes": fork_parent_hashes,
        "competing_heads": competing_heads,
        "selected_head": None,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": "This receipt detects only explicit shared-parent divergence among supplied head identities. It does not infer ancestry beyond the supplied parent, choose a winner, merge heads, determine truth, accept or reject a head, mutate canonical state, or grant authority.",
    }
    return {**body, "receipt_hash": stable_hash(body)}
