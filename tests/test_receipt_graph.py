from __future__ import annotations

import pytest

from holosim.receipt_graph import (
    build_receipt_graph,
    minimal_evidence_chain,
    NO_RECHECK_INDICATED,
    plan_dependency_rechecks,
    RECHECK_REQUIRED,
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


def test_changed_root_marks_every_and_only_downstream_receipt() -> None:
    root = _receipt(_hash("a"))
    first = _receipt(_hash("b"), previous_receipt_hash=root["receipt_hash"])
    second = _receipt(_hash("c"), evidence_receipt_hashes=[first["receipt_hash"]])
    unrelated = _receipt(_hash("d"))
    plan = plan_dependency_rechecks(
        build_receipt_graph([second, unrelated, first, root]),
        [root["receipt_hash"]],
    )

    statuses = {item["receipt_hash"]: item["status"] for item in plan["results"]}
    assert statuses == {
        root["receipt_hash"]: RECHECK_REQUIRED,
        first["receipt_hash"]: RECHECK_REQUIRED,
        second["receipt_hash"]: RECHECK_REQUIRED,
        unrelated["receipt_hash"]: NO_RECHECK_INDICATED,
    }
    assert plan["recheck_required_count"] == 3


def test_plan_records_deterministic_shortest_trigger_paths() -> None:
    root_hash = _hash("a")
    first_hash = _hash("b")
    second_hash = _hash("c")
    graph = build_receipt_graph([
        _receipt(first_hash, previous_receipt_hash=root_hash),
        _receipt(second_hash, evidence_receipt_hashes=[first_hash]),
        _receipt(root_hash),
    ])
    plan = plan_dependency_rechecks(graph, [root_hash])
    target = next(item for item in plan["results"] if item["receipt_hash"] == second_hash)
    assert target["trigger_paths"] == [[root_hash, first_hash, second_hash]]


def test_external_changed_dependency_marks_declared_dependents() -> None:
    external_hash = _hash("e")
    target_hash = _hash("f")
    graph = build_receipt_graph([
        _receipt(target_hash, evidence_receipt_hashes=[external_hash]),
    ])
    plan = plan_dependency_rechecks(graph, [external_hash])
    assert plan["results"][0]["status"] == RECHECK_REQUIRED
    assert plan["results"][0]["trigger_paths"] == [[external_hash, target_hash]]
    assert plan["unobserved_changed_hashes"] == []


def test_unrelated_external_change_is_reported_without_inventing_impact() -> None:
    receipt_hash = _hash("a")
    changed_hash = _hash("f")
    plan = plan_dependency_rechecks(
        build_receipt_graph([_receipt(receipt_hash)]),
        [changed_hash],
    )
    assert plan["unobserved_changed_hashes"] == [changed_hash]
    assert plan["results"][0]["status"] == NO_RECHECK_INDICATED
    assert plan["results"][0]["trigger_paths"] == []


def test_changed_input_order_does_not_change_plan() -> None:
    first_change = _hash("a")
    second_change = _hash("b")
    target_hash = _hash("c")
    graph = build_receipt_graph([
        _receipt(
            target_hash,
            evidence_receipt_hashes=[first_change, second_change],
        )
    ])
    assert plan_dependency_rechecks(graph, [first_change, second_change]) == (
        plan_dependency_rechecks(graph, [second_change, first_change])
    )


def test_plan_rejects_duplicate_or_empty_changed_hashes() -> None:
    graph = build_receipt_graph([_receipt(_hash("a"))])
    with pytest.raises(ValueError, match="at least one"):
        plan_dependency_rechecks(graph, [])
    with pytest.raises(ValueError, match="unique"):
        plan_dependency_rechecks(graph, [_hash("b"), _hash("b")])


def test_planner_rejects_cycle_even_when_change_is_unrelated() -> None:
    first_hash = _hash("a")
    second_hash = _hash("b")
    graph = build_receipt_graph([
        _receipt(first_hash, previous_receipt_hash=second_hash),
        _receipt(second_hash, previous_receipt_hash=first_hash),
    ])
    with pytest.raises(ValueError, match="cycle"):
        plan_dependency_rechecks(graph, [_hash("c")])


def test_plan_grants_no_validity_acceptance_or_write_authority() -> None:
    plan = plan_dependency_rechecks(
        build_receipt_graph([_receipt(_hash("a"))]),
        [_hash("a")],
    )
    assert plan["validity_claimed"] is False
    assert plan["accepted"] is False
    assert plan["write_authority"] == "NONE"
    assert "does not establish present validity" in plan["interpretation_notice"]
