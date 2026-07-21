from __future__ import annotations

import json
from pathlib import Path

import pytest

from holosim.function_registry import (
    FunctionRegistryError,
    build_composition,
    evaluate_functional_merge,
    register_function,
    relate_implementation,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "function_registry"


def test_register_store_function_without_claiming_authority() -> None:
    record = register_function(
        function_id="STORE",
        description="Preserve recoverable state",
        contract={
            "input": "state",
            "required_outcome": "retrievable_equivalent_state",
        },
        evidence_reference="computer-functions@store",
    )

    assert record["function_id"] == "STORE"
    assert record["accepted"] is False
    assert record["write_authority"] == "NONE"
    assert len(record["function_hash"]) == 64


def test_implementation_relation_is_only_proposed() -> None:
    function = register_function(
        function_id="STORE",
        description="Preserve recoverable state",
        contract={"required_outcome": "retrievable_equivalent_state"},
        evidence_reference="computer-functions@store",
    )

    relation = relate_implementation(
        function_record=function,
        implementation={
            "id": "dram",
            "kind": "semiconductor-memory",
        },
        reproduction_reference="reproduction@dram-store",
    )

    assert relation["function_id"] == "STORE"
    assert relation["implementation_id"] == "dram"
    assert relation["status"] == "PROPOSED"
    assert relation["accepted"] is False


def test_reproduced_implementations_may_share_function_node() -> None:
    result = evaluate_functional_merge(
        function_id="STORE",
        implementation_ids=["williams-tube", "dram"],
        reproduction_status="REPRODUCED",
        reproduction_reference="reproduction@store-equivalence",
    )

    assert result["merge_status"] == "SHARED_FUNCTION"
    assert result["implementations_declared_identical"] is False
    assert result["obsolete_implementations"] == []


def test_failed_reproduction_preserves_distinction() -> None:
    result = evaluate_functional_merge(
        function_id="STORE",
        implementation_ids=["implementation-a", "implementation-b"],
        reproduction_status="NOT_REPRODUCED",
        reproduction_reference="reproduction@failed-equivalence",
    )

    assert result["merge_status"] == "PRESERVE_DISTINCTION"


def test_unvalidated_merge_remains_unvalidated() -> None:
    result = evaluate_functional_merge(
        function_id="STORE",
        implementation_ids=["implementation-a", "implementation-b"],
        reproduction_status="UNVALIDATED",
        reproduction_reference="proposal@store-equivalence",
    )

    assert result["merge_status"] == "UNVALIDATED"


@pytest.mark.parametrize(
    "mode",
    ["STACK", "ADJACENT", "NESTED", "CONNECTED"],
)
def test_supported_composition_geometries(mode: str) -> None:
    composition = build_composition(
        composition_id=f"example-{mode.lower()}",
        mode=mode,
        members=[
            {"id": "STORE", "kind": "function"},
            {"id": "RETRIEVE", "kind": "function"},
        ],
        evidence_reference="composition@example",
    )

    assert composition["mode"] == mode
    assert composition["status"] == "OBSERVED_STRUCTURE"
    assert composition["accepted"] is False


def test_duplicate_composition_member_fails_closed() -> None:
    with pytest.raises(
        FunctionRegistryError,
        match="duplicate composition member id",
    ):
        build_composition(
            composition_id="bad-composition",
            mode="STACK",
            members=[
                {"id": "STORE"},
                {"id": "STORE"},
            ],
            evidence_reference="composition@bad",
        )


def test_invalid_geometry_fails_closed() -> None:
    with pytest.raises(FunctionRegistryError, match="mode must be one of"):
        build_composition(
            composition_id="bad-mode",
            mode="MAGICAL_SPAGHETTI",
            members=[{"id": "STORE"}],
            evidence_reference="composition@bad",
        )


def test_hashes_are_deterministic() -> None:
    kwargs = {
        "function_id": "STORE",
        "description": "Preserve recoverable state",
        "contract": {
            "input": "state",
            "required_outcome": "retrievable_equivalent_state",
        },
        "evidence_reference": "computer-functions@store",
    }

    first = register_function(**kwargs)
    second = register_function(**kwargs)

    assert first == second


def test_real_store_implementations_share_validated_function() -> None:
    fixture = json.loads(
        (FIXTURE_DIR / "store_reproduction.json").read_text(encoding="utf-8")
    )

    function_data = fixture["function"]

    function = register_function(
        function_id=function_data["function_id"],
        description=function_data["description"],
        contract=function_data["contract"],
        evidence_reference=function_data["evidence_reference"],
    )

    result = evaluate_functional_merge(
        function_id=function["function_id"],
        implementation_ids=[item["id"] for item in fixture["implementations"]],
        reproduction_status=fixture["reproduction"]["status"],
        reproduction_reference=fixture["reproduction"]["reference"],
    )

    assert result["merge_status"] == "SHARED_FUNCTION"
    assert result["implementations_declared_identical"] is False
    assert result["obsolete_implementations"] == []
