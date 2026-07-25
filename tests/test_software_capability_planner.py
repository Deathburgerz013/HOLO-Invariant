from __future__ import annotations

from holosim.canonical import stable_hash
from holosim.software_capability_planner import (
    run_software_capability_planner,
)


def _valid_decomposer(request, environmental_constraints):
    return [
        {
            "id": "calculator.module",
            "requirement": "create the calculator module",
            "depends_on": [],
        },
        {
            "id": "calculator.add",
            "requirement": "add must return the sum",
            "depends_on": ["calculator.module"],
        },
        {
            "id": "calculator.tests",
            "requirement": "verify calculator addition",
            "depends_on": ["calculator.add"],
        },
    ]


def _invalid_decomposer(request, environmental_constraints):
    return [
        {
            "id": "calculator.tests",
            "requirement": "verify calculator addition",
            "depends_on": ["calculator.add"],
        },
        {
            "id": "calculator.add",
            "requirement": "add must return the sum",
            "depends_on": [],
        },
    ]


def test_valid_request_produces_ordered_capability_plan() -> None:
    request = {
        "id": "calculator",
        "requirement": "build a tested calculator",
    }

    receipt = run_software_capability_planner(
        request,
        _valid_decomposer,
        environmental_constraints={
            "language": "python",
        },
    )

    assert receipt["type"] == "software_capability_plan_receipt"
    assert receipt["version"] == 1
    assert receipt["software_request"] == request

    assert receipt["planned"] is True
    assert receipt["terminal_reason"] == "CAPABILITY_PLAN_COMPLETE"

    assert [
        capability["id"]
        for capability in receipt["capabilities"]
    ] == [
        "calculator.module",
        "calculator.add",
        "calculator.tests",
    ]

    assert receipt["capabilities"][0]["depends_on"] == []
    assert receipt["capabilities"][1]["depends_on"] == [
        "calculator.module"
    ]
    assert receipt["capabilities"][2]["depends_on"] == [
        "calculator.add"
    ]

    assert receipt["generated"] is False
    assert receipt["verified"] is False
    assert receipt["completed"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    assert receipt["receipt_hash"] == stable_hash(body)


def test_forward_dependency_fails_closed() -> None:
    receipt = run_software_capability_planner(
        {
            "id": "calculator",
            "requirement": "build a tested calculator",
        },
        _invalid_decomposer,
    )

    assert receipt["planned"] is False
    assert receipt["terminal_reason"] == (
        "INVALID_CAPABILITY_DEPENDENCY_ORDER"
    )
    assert receipt["capabilities"] == []

    assert receipt["generated"] is False
    assert receipt["verified"] is False
    assert receipt["completed"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"