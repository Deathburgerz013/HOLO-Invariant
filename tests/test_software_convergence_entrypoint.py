from __future__ import annotations

from pathlib import Path

from holosim.canonical import stable_hash
from holosim.software_convergence_entrypoint import (
    run_software_convergence_request,
)


REQUEST = {
    "id": "calculator",
    "requirement": "build a runnable tested calculator",
}


def _decomposer(request, constraints):
    return [
        {
            "id": "calculator.module",
            "requirement": "create calculator.add",
            "depends_on": [],
        },
        {
            "id": "calculator.tests",
            "requirement": "add must return the sum",
            "depends_on": ["calculator.module"],
        },
    ]


def _invalid_decomposer(request, constraints):
    return [
        {
            "id": "calculator.tests",
            "requirement": "test calculator.add",
            "depends_on": ["calculator.module"],
        }
    ]


def _comparator(capability, workspace: Path):
    source_path = workspace / "calculator.py"
    source = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
    capability_id = capability["id"]

    if capability_id == "calculator.module":
        satisfied = "def add" in source
    else:
        satisfied = "return a + b" in source

    return {
        "relevant_difference": not satisfied,
        "description": capability,
        "reason": "NO_RELEVANT_DIFFERENCE",
    }


def _proposer(task, observed_state, constraints, prior_feedback):
    if task["id"] == "calculator.module":
        source = "def add(a, b):\n    return a - b\n"
    else:
        source = "def add(a, b):\n    return a + b\n"
    return {"files": {"calculator.py": source}}


def _capability_verifier(workspace: Path):
    source = (workspace / "calculator.py").read_text(encoding="utf-8")
    return {"passed": "def add" in source}


def _project_verifier(workspace: Path):
    namespace: dict = {}
    source = (workspace / "calculator.py").read_text(encoding="utf-8")
    exec(source, namespace)
    passed = namespace["add"](2, 3) == 5
    return {
        "passed": passed,
        "runnable": passed,
        "command": "python calculator.py",
        "reason": "calculator.add must return 5",
    }


def test_request_converges_ordered_capabilities_into_runnable_project(tmp_path):
    receipt = run_software_convergence_request(
        REQUEST,
        tmp_path,
        _decomposer,
        _comparator,
        _proposer,
        _capability_verifier,
        _project_verifier,
        environmental_constraints={"language": "python"},
    )

    assert receipt["status"] == "CONVERGED"
    assert receipt["terminal_reason"] == "PROJECT_VERIFIED_RUNNABLE"
    assert receipt["converged"] is True
    assert receipt["runnable"] is True
    assert receipt["completed_capability_ids"] == [
        "calculator.module",
        "calculator.tests",
    ]
    assert receipt["blocked_capability_id"] is None
    assert len(receipt["generation_receipts"]) == 2
    assert receipt["final_verification"]["passed"] is True
    assert receipt["final_verification"]["runnable"] is True
    assert (tmp_path / "calculator.py").is_file()
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    assert receipt["receipt_hash"] == stable_hash(body)


def test_invalid_plan_stops_before_generation(tmp_path):
    calls = {"comparator": 0, "project_verifier": 0}

    def comparator(*args):
        calls["comparator"] += 1
        return {"relevant_difference": False}

    def project_verifier(*args):
        calls["project_verifier"] += 1
        return {"passed": True, "runnable": True}

    receipt = run_software_convergence_request(
        REQUEST,
        tmp_path,
        _invalid_decomposer,
        comparator,
        _proposer,
        _capability_verifier,
        project_verifier,
    )

    assert receipt["status"] == "PLANNING_FAILED"
    assert receipt["terminal_reason"] == "INVALID_CAPABILITY_DEPENDENCY_ORDER"
    assert receipt["generation_receipts"] == []
    assert receipt["final_verification"] is None
    assert calls == {"comparator": 0, "project_verifier": 0}


def test_failed_capability_stops_later_dependencies_and_reports_blocker(tmp_path):
    comparator_calls: list[str] = []

    def comparator(capability, workspace):
        comparator_calls.append(capability["id"])
        return {"relevant_difference": True, "description": capability}

    def bad_proposer(task, observed_state, constraints, feedback):
        return {"files": {"calculator.py": "broken = True\n"}}

    def verifier(workspace):
        return {"passed": False, "feedback": "calculator module missing"}

    receipt = run_software_convergence_request(
        REQUEST,
        tmp_path,
        _decomposer,
        comparator,
        bad_proposer,
        verifier,
        _project_verifier,
        max_builder_attempts=1,
    )

    assert receipt["status"] == "CAPABILITY_FAILED"
    assert receipt["terminal_reason"] == "BUILDER_VERIFICATION_FAILED"
    assert receipt["blocked_capability_id"] == "calculator.module"
    assert receipt["completed_capability_ids"] == []
    assert len(receipt["generation_receipts"]) == 1
    assert comparator_calls == ["calculator.module"]
    assert receipt["final_verification"] is None
    assert receipt["converged"] is False
    assert receipt["runnable"] is False


def test_final_project_failure_cannot_claim_runnable_convergence(tmp_path):
    def project_verifier(workspace):
        return {
            "passed": True,
            "runnable": False,
            "reason": "ENTRYPOINT_COMMAND_MISSING",
        }

    receipt = run_software_convergence_request(
        REQUEST,
        tmp_path,
        _decomposer,
        _comparator,
        _proposer,
        _capability_verifier,
        project_verifier,
    )

    assert receipt["status"] == "PROJECT_VERIFICATION_FAILED"
    assert receipt["terminal_reason"] == "ENTRYPOINT_COMMAND_MISSING"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False
    assert receipt["final_verification"]["passed"] is True


def test_runnable_claim_without_command_is_rejected(tmp_path):
    def project_verifier(workspace):
        return {"passed": True, "runnable": True}

    receipt = run_software_convergence_request(
        REQUEST,
        tmp_path,
        _decomposer,
        _comparator,
        _proposer,
        _capability_verifier,
        project_verifier,
    )

    assert receipt["status"] == "PROJECT_VERIFICATION_FAILED"
    assert receipt["terminal_reason"] == "PROJECT_RUN_COMMAND_MISSING"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False


def test_already_satisfied_capability_counts_as_converged(tmp_path):
    (tmp_path / "calculator.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    proposer_calls = {"count": 0}

    def proposer(*args):
        proposer_calls["count"] += 1
        return {"files": {}}

    receipt = run_software_convergence_request(
        REQUEST,
        tmp_path,
        _decomposer,
        _comparator,
        proposer,
        _capability_verifier,
        _project_verifier,
    )

    assert receipt["status"] == "CONVERGED"
    assert receipt["runnable"] is True
    assert proposer_calls["count"] == 0
    assert all(
        generation["converged"] is True
        for generation in receipt["generation_receipts"]
    )
