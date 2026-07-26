"""Deterministic dependency graphs for version-bound receipts.

The graph preserves declared receipt dependencies and can derive the smallest
closed, ordered set of available receipts required to support a target. It
observes receipts without granting truth, acceptance, or write authority.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Iterable, Mapping

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
