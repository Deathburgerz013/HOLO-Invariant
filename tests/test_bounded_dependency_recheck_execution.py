import pytest
from holosim.bounded_dependency_recheck_execution import DependencyINVRecheckError

from holosim.agent import (
    run_dependency_checked_convergence_agent,
    run_verified_convergence_agent,
    verify_dependency_checked_agent_receipt,
)
from holosim.bounded_evidence_analyst import build_evidence_analysis_receipt
from holosim.canonical import stable_hash
from holosim.bounded_dependency_recheck_execution import (
    execute_dependency_inv_recheck,
    verify_dependency_inv_recheck_receipt,
)


def _valid_recheck():
    source = build_evidence_analysis_receipt(
        analysis_id="exp024-analysis",
        scope="fixture",
        method={
            "method_id": "fixture",
            "method_version": "v1",
            "description": "bounded test fixture",
        },
        evidence=[{
            "evidence_id": "e1",
            "content_sha256": stable_hash({"evidence": 1}),
            "source_reference": "fixture:e1",
            "availability": "VERIFIED",
        }],
        findings=[{
            "finding_id": "f1",
            "statement": "Fixture claim",
            "evidence_assessments": [{
                "evidence_id": "e1",
                "disposition": "INCLUDED",
                "relation": "SUPPORTS",
                "rationale": "fixture support",
            }],
        }],
    )

    base = run_verified_convergence_agent(
        run_id="exp024-base",
        objective="Verify bounded dependency recheck",
        analysis_receipts=[source],
    )

    changed = stable_hash({"dependency": "changed"})

    prior = run_dependency_checked_convergence_agent(
        run_id="exp024-dependency",
        base_agent_receipt=base,
        dependency_bindings=[{
            "analysis_receipt_hash": source["receipt_hash"],
            "dependency_receipt_hashes": [changed],
        }],
        dependency_receipts=[],
        changed_dependency_hashes=[changed],
    )

    result = execute_dependency_inv_recheck(
        dependency_checked_receipt=prior,
        analysis_receipt_hash=source["receipt_hash"],
        changed_dependency_hash=changed,
        state=10,
        transition_kind="subtract",
        transition_value=3,
        minimum=0,
    )

    return result


def test_changed_dependency_executes_bounded_inv_recheck():
    result = _valid_recheck()

    assert verify_dependency_inv_recheck_receipt(result) is True
    assert result["inv_decision"]["accepted"] is True
    assert result["inv_decision"]["resulting_state"] == 7

    prior = result["dependency_checked_receipt"]
    assert result["dependency_checked_receipt_hash"] == prior["receipt_hash"]
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert verify_dependency_checked_agent_receipt(prior) is True

def test_rehashed_forged_inv_decision_is_rejected():
    result = _valid_recheck()
    result["inv_decision"]["resulting_state"] = 999
    result["receipt_hash"] = stable_hash({
        k: v for k, v in result.items() if k != "receipt_hash"
    })
    assert verify_dependency_inv_recheck_receipt(result) is False


def test_rehashed_authority_escalation_is_rejected():
    result = _valid_recheck()
    result["accepted"] = True
    result["write_authority"] = "AGENT"
    result["receipt_hash"] = stable_hash({
        k: v for k, v in result.items() if k != "receipt_hash"
    })
    assert verify_dependency_inv_recheck_receipt(result) is False


def test_altered_original_receipt_is_rejected():
    result = _valid_recheck()
    result["dependency_checked_receipt"]["accepted"] = True
    result["receipt_hash"] = stable_hash({
        k: v for k, v in result.items() if k != "receipt_hash"
    })
    assert verify_dependency_inv_recheck_receipt(result) is False

def test_unaffected_analysis_is_rejected():
    result = _valid_recheck()
    prior = result["dependency_checked_receipt"]

    with pytest.raises(DependencyINVRecheckError, match="no affected analysis path"):
        execute_dependency_inv_recheck(
            dependency_checked_receipt=prior,
            analysis_receipt_hash=stable_hash({"analysis": "unaffected"}),
            changed_dependency_hash=result["changed_dependency_hash"],
            state=10,
            transition_kind="subtract",
            transition_value=3,
            minimum=0,
        )


def test_undeclared_dependency_is_rejected():
    result = _valid_recheck()

    with pytest.raises(DependencyINVRecheckError, match="not declared"):
        execute_dependency_inv_recheck(
            dependency_checked_receipt=result["dependency_checked_receipt"],
            analysis_receipt_hash=result["analysis_receipt_hash"],
            changed_dependency_hash=stable_hash({"dependency": "undeclared"}),
            state=10,
            transition_kind="subtract",
            transition_value=3,
            minimum=0,
        )

def test_rejected_inv_transition_preserves_state():
    result = _valid_recheck()

    rejected = execute_dependency_inv_recheck(
        dependency_checked_receipt=result["dependency_checked_receipt"],
        analysis_receipt_hash=result["analysis_receipt_hash"],
        changed_dependency_hash=result["changed_dependency_hash"],
        state=10,
        transition_kind="subtract",
        transition_value=15,
        minimum=0,
    )

    assert rejected["inv_decision"]["accepted"] is False
    assert rejected["inv_decision"]["candidate_state"] == -5
    assert rejected["inv_decision"]["resulting_state"] == 10
    assert rejected["accepted"] is False
    assert verify_dependency_inv_recheck_receipt(rejected) is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("state", True),
        ("minimum", False),
        ("transition_value", "3"),
        ("transition_kind", "unknown"),
    ],
)
def test_invalid_inv_inputs_fail_closed(field, value):
    result = _valid_recheck()

    arguments = {
        "dependency_checked_receipt": result["dependency_checked_receipt"],
        "analysis_receipt_hash": result["analysis_receipt_hash"],
        "changed_dependency_hash": result["changed_dependency_hash"],
        "state": 10,
        "transition_kind": "subtract",
        "transition_value": 3,
        "minimum": 0,
    }
    arguments[field] = value

    with pytest.raises(DependencyINVRecheckError):
        execute_dependency_inv_recheck(**arguments)
