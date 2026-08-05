from __future__ import annotations

import json

import pytest

from holosim.local_ollama_adapter import LocalOllamaAdapterError
from holosim.local_ollama_capability_decomposer import (
    build_local_ollama_capability_decomposer,
)
from holosim.software_capability_planner import (
    run_software_capability_planner,
)


CAPABILITIES = [
    {
        "id": "calculator.module",
        "requirement": "create calculator.add",
        "depends_on": [],
    },
    {
        "id": "calculator.tests",
        "requirement": "verify calculator.add returns the sum",
        "depends_on": ["calculator.module"],
    },
]


def test_decomposer_maps_request_to_bounded_model_prompt():
    observed = {}

    def requester(prompt, **kwargs):
        observed["prompt"] = json.loads(prompt)
        observed["kwargs"] = kwargs
        return {
            "output": {"capabilities": CAPABILITIES},
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }

    decomposer = build_local_ollama_capability_decomposer(
        requester=requester,
        timeout_seconds=9,
    )
    result = decomposer(
        {"id": "calculator", "requirement": "build a calculator"},
        {"language": "python"},
    )

    assert result == CAPABILITIES
    assert observed["prompt"]["task"] == "decompose_software_request"
    assert observed["prompt"]["software_request"] == {
        "id": "calculator",
        "requirement": "build a calculator",
    }
    assert observed["prompt"]["environmental_constraints"] == {
        "language": "python"
    }
    assert observed["prompt"]["output_schema"] == {
        "capabilities": [
            {
                "id": "unique.nonempty.string",
                "requirement": "one bounded observable requirement",
                "depends_on": ["earlier.capability.id"],
            }
        ]
    }
    assert observed["kwargs"]["timeout_seconds"] == 9
    assert decomposer.last_receipt["accepted"] is False
    assert decomposer.last_receipt["write_authority"] == "NONE"


def test_decomposer_returns_copies_not_requester_owned_values():
    payload = {"output": {"capabilities": CAPABILITIES}}
    decomposer = build_local_ollama_capability_decomposer(
        requester=lambda prompt, **kwargs: payload,
    )

    result = decomposer("calculator", {})
    result[0]["id"] = "mutated"

    assert payload["output"]["capabilities"][0]["id"] == (
        "calculator.module"
    )


@pytest.mark.parametrize(
    "receipt",
    [
        None,
        {},
        {"output": []},
        {"output": {"capabilities": []}},
        {"output": {"capabilities": ["not-a-mapping"]}},
    ],
)
def test_decomposer_rejects_malformed_model_receipts(receipt):
    decomposer = build_local_ollama_capability_decomposer(
        requester=lambda prompt, **kwargs: receipt,
    )

    with pytest.raises(LocalOllamaAdapterError):
        decomposer("calculator", {})


def test_existing_planner_rejects_model_dependency_disorder():
    disorder = [
        {
            "id": "calculator.tests",
            "requirement": "test calculator.add",
            "depends_on": ["calculator.module"],
        }
    ]
    decomposer = build_local_ollama_capability_decomposer(
        requester=lambda prompt, **kwargs: {
            "output": {"capabilities": disorder}
        },
    )

    receipt = run_software_capability_planner(
        "build a calculator",
        decomposer,
    )

    assert receipt["planned"] is False
    assert receipt["capabilities"] == []
    assert receipt["terminal_reason"] == (
        "INVALID_CAPABILITY_DEPENDENCY_ORDER"
    )
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_existing_planner_accepts_ordered_model_proposal_for_planning_only():
    decomposer = build_local_ollama_capability_decomposer(
        requester=lambda prompt, **kwargs: {
            "output": {"capabilities": CAPABILITIES}
        },
    )

    receipt = run_software_capability_planner(
        "build a calculator",
        decomposer,
        environmental_constraints={"language": "python"},
    )

    assert receipt["planned"] is True
    assert receipt["capabilities"] == CAPABILITIES
    assert receipt["generated"] is False
    assert receipt["verified"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
