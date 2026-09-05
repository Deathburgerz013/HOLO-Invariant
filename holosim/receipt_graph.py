"""Deterministic dependency graphs for version-bound receipts.

The graph preserves declared receipt dependencies and can derive the smallest
closed, ordered set of available receipts required to support a target. It
observes receipts without granting truth, acceptance, or write authority.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Iterable, Mapping

from holosim.canonical import stable_hash


RECHECK_PLAN_TYPE = "dependency_recheck_plan"
RECHECK_PLAN_VERSION = 1
RECHECK_REQUIRED = "RECHECK_REQUIRED"
NO_RECHECK_INDICATED = "NO_RECHECK_INDICATED"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SINGLE_DEPENDENCY_FIELDS = (
    "previous_receipt_hash",
    "proposed_receipt_hash",
    "resulting_receipt_hash",
    "convergence_receipt_hash",
)
_LIST_DEPENDENCY_FIELDS = ("evidence_receipt_hashes",)


def _require_receipt_hash(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hash")
    return value


def _declared_dependencies(receipt: Mapping[str, Any]) -> tuple[str, ...]:
    dependencies: list[str] = []

    for field_name in _SINGLE_DEPENDENCY_FIELDS:
        value = receipt.get(field_name)
        if value is not None:
            dependencies.append(_require_receipt_hash(value, field_name))

    for field_name in _LIST_DEPENDENCY_FIELDS:
        values = receipt.get(field_name, ())
        if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
            raise ValueError(f"{field_name} must be an iterable of hashes")
        dependencies.extend(
            _require_receipt_hash(value, f"{field_name} item")
            for value in values
        )

    return tuple(dict.fromkeys(dependencies))


def build_receipt_graph(
    receipts: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index receipts and their declared dependencies by receipt hash."""

    if isinstance(receipts, (str, bytes, Mapping)):
        raise ValueError("receipts must be an iterable of receipt mappings")

    graph: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            raise ValueError("each receipt must be a mapping")

        receipt_hash = _require_receipt_hash(
            receipt.get("receipt_hash"),
            "receipt_hash",
        )
        if receipt_hash in graph:
            raise ValueError("receipt hashes must be unique")

        graph[receipt_hash] = {
            "receipt": deepcopy(dict(receipt)),
            "dependencies": _declared_dependencies(receipt),
        }

    return graph


def minimal_evidence_chain(
    graph: Mapping[str, Mapping[str, Any]],
    target_receipt_hash: Any,
) -> list[str]:
    """Return the smallest dependency-closed chain available for a target.

    Dependencies absent from the supplied graph are external references and
    remain recorded in their source receipt, but cannot be expanded here.
    Cycles are rejected because no deterministic justification order exists.
    """

    target_hash = _require_receipt_hash(
        target_receipt_hash,
        "target_receipt_hash",
    )
    if target_hash not in graph:
        raise KeyError(target_hash)

    ordered: list[str] = []
    visited: set[str] = set()
    active: set[str] = set()

    def visit(receipt_hash: str) -> None:
        if receipt_hash in visited:
            return
        if receipt_hash in active:
            raise ValueError("receipt dependency cycle detected")

        node = graph.get(receipt_hash)
        if node is None:
            return

        dependencies = node.get("dependencies")
        if not isinstance(dependencies, (list, tuple)):
            raise ValueError("graph dependencies must be a list or tuple")

        active.add(receipt_hash)
        for dependency_hash in dependencies:
            dependency = _require_receipt_hash(
                dependency_hash,
                "graph dependency",
            )
            visit(dependency)
        active.remove(receipt_hash)

        visited.add(receipt_hash)
        ordered.append(receipt_hash)

    visit(target_hash)
    return ordered


def plan_dependency_rechecks(
    graph: Mapping[str, Mapping[str, Any]],
    changed_dependency_hashes: Iterable[str],
) -> dict[str, Any]:
    """Trace declared changes forward to every affected receipt.

    A changed hash is caller-supplied evidence, not a change detected by this
    function. The plan follows only explicit graph edges. Receipts outside the
    affected closure are classified ``NO_RECHECK_INDICATED`` rather than valid.
    One deterministic shortest path is retained from each relevant changed hash
    to each affected receipt.
    """
    if not isinstance(graph, Mapping):
        raise ValueError("graph must be a mapping")
    if isinstance(changed_dependency_hashes, (str, bytes, Mapping)):
        raise ValueError("changed_dependency_hashes must be an iterable of hashes")

    changed: list[str] = []
    seen_changes: set[str] = set()
    for value in changed_dependency_hashes:
        item = _require_receipt_hash(value, "changed_dependency_hash")
        if item in seen_changes:
            raise ValueError("changed dependency hashes must be unique")
        seen_changes.add(item)
        changed.append(item)
    if not changed:
        raise ValueError("at least one changed dependency hash is required")
    changed.sort()

    dependencies_by_receipt: dict[str, tuple[str, ...]] = {}
    reverse: dict[str, set[str]] = {}
    for raw_hash, node in graph.items():
        receipt_hash = _require_receipt_hash(raw_hash, "graph receipt hash")
        if not isinstance(node, Mapping):
            raise ValueError("graph nodes must be mappings")
        dependencies = node.get("dependencies")
        if not isinstance(dependencies, (list, tuple)):
            raise ValueError("graph dependencies must be a list or tuple")
        checked_dependencies = tuple(
            _require_receipt_hash(value, "graph dependency")
            for value in dependencies
        )
        if len(checked_dependencies) != len(set(checked_dependencies)):
            raise ValueError("graph dependencies must be unique")
        dependencies_by_receipt[receipt_hash] = checked_dependencies
        for dependency in checked_dependencies:
            reverse.setdefault(dependency, set()).add(receipt_hash)

    # Reject cycles across the whole supplied graph, including disconnected parts.
    visited: set[str] = set()
    active: set[str] = set()

    def check_cycle(receipt_hash: str) -> None:
        if receipt_hash in visited:
            return
        if receipt_hash in active:
            raise ValueError("receipt dependency cycle detected")
        active.add(receipt_hash)
        for dependency in dependencies_by_receipt[receipt_hash]:
            if dependency in dependencies_by_receipt:
                check_cycle(dependency)
        active.remove(receipt_hash)
        visited.add(receipt_hash)

    for receipt_hash in sorted(dependencies_by_receipt):
        check_cycle(receipt_hash)

    paths_by_receipt: dict[str, dict[str, list[str]]] = {}
    for origin in changed:
        frontier: list[tuple[str, list[str]]] = [(origin, [origin])]
        reached = {origin}
        while frontier:
            current, path = frontier.pop(0)
            if current in dependencies_by_receipt:
                paths_by_receipt.setdefault(current, {})[origin] = path
            for dependent in sorted(reverse.get(current, ())):
                if dependent in reached:
                    continue
                reached.add(dependent)
                frontier.append((dependent, [*path, dependent]))

    results = []
    for receipt_hash in sorted(dependencies_by_receipt):
        origin_paths = paths_by_receipt.get(receipt_hash, {})
        results.append({
            "receipt_hash": receipt_hash,
            "status": (
                RECHECK_REQUIRED if origin_paths else NO_RECHECK_INDICATED
            ),
            "trigger_paths": [
                origin_paths[origin] for origin in sorted(origin_paths)
            ],
        })

    referenced_hashes = set(dependencies_by_receipt)
    referenced_hashes.update(reverse)
    body = {
        "type": RECHECK_PLAN_TYPE,
        "version": RECHECK_PLAN_VERSION,
        "changed_dependency_hashes": changed,
        "unobserved_changed_hashes": [
            value for value in changed if value not in referenced_hashes
        ],
        "results": results,
        "recheck_required_count": sum(
            item["status"] == RECHECK_REQUIRED for item in results
        ),
        "validity_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "The plan reports reachability through declared dependencies only. "
            "NO_RECHECK_INDICATED does not establish present validity."
        ),
    }
    return {**body, "plan_hash": stable_hash(body)}
