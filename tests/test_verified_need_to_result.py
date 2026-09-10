from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from holosim.canonical import stable_hash
from holosim.justification_notice import build_justification_notice
from holosim.verified_need_to_result import (
    VerifiedNeedToResultError,
    run_verified_need_to_result,
    verify_need_to_result_receipt,
)


REQUEST = {
    "id": "greeting-tool",
    "requirement": "produce one runnable greeting module",
}


def _purpose(
    request=REQUEST,
    *,
    why: str = "A runnable greeting tool is the next declared need.",
    stop_condition: str = "PROJECT_VERIFIED_RUNNABLE",
):
    return build_justification_notice(
        notice_id="notice:greeting-tool:v1",
        parent_notice_hash=None,
        target={
            "target_id": "software-request:greeting-tool",
            "target_type": "software_request",
            "target_sha256": stable_hash(request),
        },
        observed_failure={
            "failure_id": "greeting-tool-missing",
            "observation": "The requested runnable tool is not present.",
        },
        evidence_bindings=[
            {
                "evidence_id": "workspace:before",
                "evidence_sha256": stable_hash({"greeting.py": None}),
            }
        ],
        selected_change={
            "operation": "run bounded software convergence",
            "changes_target": False,
        },
        why_selected=why,
        rejected_alternatives=[],
        declared_scope={
            "boundary": "greeting tool only",
            "stop_condition": stop_condition,
        },
        established_findings=[
            {"finding": "The declared software request is currently unmet."}
        ],
        unknowns=[],
        reopen_conditions=[
            "A later verified state no longer contains a runnable greeting tool."
        ],
        contributors=[
            {"contributor_id": "Canyon", "role": "declared bounded need"}
        ],
    )


def _decomposer(request, constraints):
    return [
        {
            "id": "greeting.module",
            "requirement": request["requirement"],
            "depends_on": [],
        }
    ]


def _comparator(capability, workspace: Path):
    path = workspace / "greeting.py"
    satisfied = path.is_file() and "def greet" in path.read_text(encoding="utf-8")
    return {
        "verified": True,
        "relevant_difference": not satisfied,
        "description": capability,
        "reason": "NO_RELEVANT_DIFFERENCE",
    }


def _proposer(task, observed_state, constraints, prior_feedback):
    return {"files": {"greeting.py": "def greet():\n    return 'hello'\n"}}


def _capability_verifier(workspace: Path):
    source = (workspace / "greeting.py").read_text(encoding="utf-8")
    return {"passed": "def greet" in source}


def _project_verifier(workspace: Path):
    namespace: dict = {}
    exec((workspace / "greeting.py").read_text(encoding="utf-8"), namespace)
    passed = namespace["greet"]() == "hello"
    return {
        "passed": passed,
        "runnable": passed,
        "command": "python greeting.py",
        "reason": "greet must return hello",
    }


def _run(tmp_path: Path, *, purpose=None, comparator=_comparator):
    return run_verified_need_to_result(
        path_id="need-to-result:greeting:v1",
        purpose_notice=purpose or _purpose(),
        software_request=REQUEST,
        workspace=tmp_path,
        decomposer=_decomposer,
        comparator=comparator,
        proposer=_proposer,
        capability_verifier=_capability_verifier,
        project_verifier=_project_verifier,
        environmental_constraints={"language": "python"},
    )


def test_exact_need_produces_one_bound_verified_runnable_result(tmp_path):
    receipt = _run(tmp_path)

    assert receipt["status"] == "COMPLETE"
    assert receipt["terminal_reason"] == "PROJECT_VERIFIED_RUNNABLE"
    assert receipt["stop_reached"] is True
    assert receipt["purpose_notice_hash"] == receipt["purpose_notice"]["notice_hash"]
    assert receipt["software_request_hash"] == stable_hash(REQUEST)
    assert receipt["production_receipt_hash"] == receipt["production_receipt"]["receipt_hash"]
    assert receipt["production_receipt"]["environmental_constraints"][
        "purpose_notice_hash"
    ] == receipt["purpose_notice_hash"]
    assert receipt["production_receipt"]["runnable"] is True
    assert (tmp_path / "greeting.py").read_text(encoding="utf-8") == (
        "def greet():\n    return 'hello'\n"
    )
    assert receipt["persistence_performed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert verify_need_to_result_receipt(receipt) is True


def test_wrong_request_binding_stops_before_production(tmp_path):
    calls = {"decomposer": 0}

    def decomposer(*args):
        calls["decomposer"] += 1
        return _decomposer(*args)

    with pytest.raises(VerifiedNeedToResultError, match="exact software request"):
        run_verified_need_to_result(
            path_id="need-to-result:greeting:v1",
            purpose_notice=_purpose({"id": "different"}),
            software_request=REQUEST,
            workspace=tmp_path,
            decomposer=decomposer,
            comparator=_comparator,
            proposer=_proposer,
            capability_verifier=_capability_verifier,
            project_verifier=_project_verifier,
        )

    assert calls["decomposer"] == 0
    assert list(tmp_path.iterdir()) == []


def test_free_text_stop_condition_cannot_control_production(tmp_path):
    with pytest.raises(VerifiedNeedToResultError, match="declared stop_condition"):
        _run(tmp_path, purpose=_purpose(stop_condition="looks useful"))

    assert list(tmp_path.iterdir()) == []


def test_conflicting_caller_purpose_binding_stops_before_production(tmp_path):
    with pytest.raises(VerifiedNeedToResultError, match="conflicting purpose"):
        run_verified_need_to_result(
            path_id="need-to-result:greeting:v1",
            purpose_notice=_purpose(),
            software_request=REQUEST,
            workspace=tmp_path,
            decomposer=_decomposer,
            comparator=_comparator,
            proposer=_proposer,
            capability_verifier=_capability_verifier,
            project_verifier=_project_verifier,
            environmental_constraints={"purpose_notice_hash": "0" * 64},
        )

    assert list(tmp_path.iterdir()) == []


def test_unverified_difference_blocks_without_a_result_claim(tmp_path):
    def unverified_comparator(capability, workspace):
        return {
            "model_generated": True,
            "verified": False,
            "relevant_difference": True,
            "description": capability,
        }

    receipt = _run(tmp_path, comparator=unverified_comparator)

    assert receipt["status"] == "BLOCKED"
    assert receipt["terminal_reason"] == "UNVERIFIED_MODEL_COMPARISON"
    assert receipt["stop_reached"] is False
    assert receipt["production_receipt"]["runnable"] is False
    assert list(tmp_path.iterdir()) == []
    assert verify_need_to_result_receipt(receipt) is True


def test_posthoc_purpose_substitution_is_rejected(tmp_path):
    receipt = _run(tmp_path)
    substituted = deepcopy(receipt)
    substituted["purpose_notice"] = _purpose(
        why="A different reason was inserted after production."
    )
    substituted["purpose_notice_hash"] = substituted["purpose_notice"]["notice_hash"]
    body = {key: value for key, value in substituted.items() if key != "receipt_hash"}
    substituted["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        VerifiedNeedToResultError,
        match="not bound to the purpose notice",
    ):
        verify_need_to_result_receipt(substituted)


def test_nested_production_tamper_is_rejected(tmp_path):
    receipt = _run(tmp_path)
    receipt["production_receipt"]["runnable"] = False

    with pytest.raises(VerifiedNeedToResultError, match="hash mismatch"):
        verify_need_to_result_receipt(receipt)
