"""Bounded, read-only classification of declared evidence dependencies.

Shared ancestry establishes declared dependence, not factual truth.
No observed overlap never establishes source independence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from holosim.receipt_graph import build_receipt_graph

_HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_RECEIPTS = 1000
MAX_EDGES = 10000


class EvidenceOriginError(ValueError):
    """Invalid or unbounded evidence-origin graph."""


def classify_evidence_origins(
    receipts: Sequence[Mapping[str, Any]],
    left_hash: str,
    right_hash: str,
) -> dict[str, Any]:
    """Compare declared ancestry without inferring truth or independence."""
    if type(receipts) not in (list, tuple):
        raise EvidenceOriginError("receipts must be a list or tuple")
    if not 1 <= len(receipts) <= MAX_RECEIPTS:
        raise EvidenceOriginError("receipt budget exceeded")

    for label, value in (("left_hash", left_hash), ("right_hash", right_hash)):
        if type(value) is not str or _HASH.fullmatch(value) is None:
            raise EvidenceOriginError(f"invalid {label}")

    if left_hash == right_hash:
        raise EvidenceOriginError("reports must have distinct hashes")

    # Validate raw input before the shared graph builder normalizes it.
    # Never let deduplication hide oversized or malformed input.
    allowed_fields = {
        "receipt_hash",
        "evidence_receipt_hashes",
    }
    raw_edges = 0

    for raw in receipts:
        if type(raw) is not dict:
            raise EvidenceOriginError("receipt must be a plain object")

        if not set(raw).issubset(allowed_fields):
            raise EvidenceOriginError("unknown receipt fields")

        if "receipt_hash" not in raw:
            raise EvidenceOriginError("receipt hash missing")

        identity = raw["receipt_hash"]
        if type(identity) is not str or _HASH.fullmatch(identity) is None:
            raise EvidenceOriginError("invalid receipt hash")

        dependencies = raw.get("evidence_receipt_hashes", [])

        if type(dependencies) not in (list, tuple):
            raise EvidenceOriginError(
                "dependencies must be a list or tuple"
            )

        raw_edges += len(dependencies)
        if raw_edges > MAX_EDGES:
            raise EvidenceOriginError("dependency budget exceeded")

        seen_dependencies = set()

        for dependency in dependencies:
            if (
                type(dependency) is not str
                or _HASH.fullmatch(dependency) is None
            ):
                raise EvidenceOriginError("invalid dependency hash")

            if dependency in seen_dependencies:
                raise EvidenceOriginError(
                    "duplicate dependency hash"
                )

            seen_dependencies.add(dependency)

    try:
        graph = build_receipt_graph(receipts)
    except (ValueError, TypeError, KeyError) as exc:
        raise EvidenceOriginError("invalid receipt graph") from exc

    if left_hash not in graph or right_hash not in graph:
        raise EvidenceOriginError("report receipt missing")

    edges = sum(len(node["dependencies"]) for node in graph.values())
    if edges > MAX_EDGES:
        raise EvidenceOriginError("dependency budget exceeded")

    # Validate the complete declared graph once using iterative DFS.
    # State: absent = unseen, 1 = active, 2 = complete.
    state: dict[str, int] = {}

    for root in graph:
        if state.get(root) == 2:
            continue

        state[root] = 1
        stack = [(root, iter(graph[root]["dependencies"]))]

        while stack:
            current, dependencies = stack[-1]

            try:
                dependency = next(dependencies)
            except StopIteration:
                state[current] = 2
                stack.pop()
                continue

            if dependency not in graph:
                continue

            dependency_state = state.get(dependency, 0)

            if dependency_state == 1:
                raise EvidenceOriginError("dependency cycle detected")

            if dependency_state == 2:
                continue

            state[dependency] = 1
            stack.append(
                (dependency, iter(graph[dependency]["dependencies"]))
            )

    def ancestry(start: str) -> tuple[set[str], set[str]]:
        visited: set[str] = set()
        missing: set[str] = set()
        active: set[str] = set()
        stack = [(start, False)]

        while stack:
            current, leaving = stack.pop()

            if leaving:
                active.remove(current)
                visited.add(current)
                continue

            if current in active:
                raise EvidenceOriginError("dependency cycle detected")
            if current in visited:
                continue

            node = graph.get(current)
            if node is None:
                missing.add(current)
                visited.add(current)
                continue

            active.add(current)
            stack.append((current, True))
            for dependency in reversed(node["dependencies"]):
                stack.append((dependency, False))

        return visited - {start}, missing

    left_ancestors, left_missing = ancestry(left_hash)
    right_ancestors, right_missing = ancestry(right_hash)

    shared = sorted(left_ancestors & right_ancestors)
    missing = sorted(left_missing | right_missing)

    return {
        "type": "bounded_evidence_origin_classification",
        "left_receipt_hash": left_hash,
        "right_receipt_hash": right_hash,
        "status": "SHARED_DEPENDENCY" if shared else "UNKNOWN",
        "shared_dependency_hashes": shared,
        "missing_dependency_hashes": missing,
        "independence_established": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
