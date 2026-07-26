from __future__ import annotations

import pytest

from holosim.receipt_graph import (
    build_receipt_graph,
    minimal_evidence_chain,
)


def _hash(character: str) -> str:
    return character * 64


def _receipt(receipt_hash: str, **dependencies):
    return {
        "type": "test_receipt",
        "version": 1,
        "receipt_hash": receipt_hash,
        **dependencies,
    }


def test_minimal_evidence_chain_is_dependency_closed_and_ordered() -> None:
    root = _receipt(_hash("a"))
    unrelated = _receipt(_hash("b"))
    evidence = _receipt(
        _hash("c"),
        previous_receipt_hash=root["receipt_hash"],
    )
    target = _receipt(
        _hash("d"),
        evidence_receipt_hashes=[evidence["receipt_hash"]],
    )

    graph = build_receipt_graph([target, unrelated, evidence, root])

    assert minimal_evidence_chain(graph, target["receipt_hash"]) == [
        root["receipt_hash"],
        evidence["receipt_hash"],
        target["receipt_hash"],
    ]


def test_external_dependencies_are_preserved_but_not_invented() -> None:
    external_hash = _hash("e")
    target = _receipt(
        _hash("f"),
        evidence_receipt_hashes=[external_hash],
    )

    graph = build_receipt_graph([target])

    assert graph[target["receipt_hash"]]["dependencies"] == (
        external_hash,
    )
    assert minimal_evidence_chain(graph, target["receipt_hash"]) == [
        target["receipt_hash"]
    ]


def test_duplicate_receipt_hashes_are_rejected() -> None:
    receipt = _receipt(_hash("a"))

    with pytest.raises(ValueError, match="unique"):
        build_receipt_graph([receipt, dict(receipt)])


def test_dependency_cycle_is_rejected() -> None:
    first_hash = _hash("a")
    second_hash = _hash("b")
    graph = build_receipt_graph(
        [
            _receipt(first_hash, previous_receipt_hash=second_hash),
            _receipt(second_hash, previous_receipt_hash=first_hash),
        ]
    )

    with pytest.raises(ValueError, match="cycle"):
        minimal_evidence_chain(graph, first_hash)


def test_missing_target_is_rejected() -> None:
    graph = build_receipt_graph([_receipt(_hash("a"))])

    with pytest.raises(KeyError):
        minimal_evidence_chain(graph, _hash("b"))


def test_malformed_dependency_hash_is_rejected() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        build_receipt_graph(
            [
                _receipt(
                    _hash("a"),
                    evidence_receipt_hashes=["not-a-hash"],
                )
            ]
        )
