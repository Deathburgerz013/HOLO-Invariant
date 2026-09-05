from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.agent import (
    CONDITIONALLY_DIVERGENT,
    VerifiedConvergenceAgentError,
    run_verified_convergence_agent,
    verify_agent_convergence_receipt,
)
from holosim.bounded_evidence_analyst import build_evidence_analysis_receipt
from holosim.canonical import stable_hash


def analysis(analysis_id, scope, finding_id="f1", statement="X holds", relation="SUPPORTS"):
    return build_evidence_analysis_receipt(
        analysis_id=analysis_id,
        scope=scope,
        method={
            "method_id": "fixture-method",
            "method_version": "v1",
            "description": "fixture declared-relation method",
        },
        evidence=[{
            "evidence_id": "e1",
            "content_sha256": stable_hash({"analysis": analysis_id}),
            "source_reference": f"fixture:{analysis_id}",
            "availability": "VERIFIED",
        }],
        findings=[{
            "finding_id": finding_id,
            "statement": statement,
            "evidence_assessments": [{
                "evidence_id": "e1",
                "disposition": "INCLUDED",
                "relation": relation,
                "rationale": f"fixture relation {relation}",
            }],
        }],
    )


def run(receipts):
    return run_verified_convergence_agent(
        run_id="agent.run-1",
        objective="Converge verified fixture findings without erasure.",
        analysis_receipts=receipts,
    )


def test_repeated_support_converges_same_finding() -> None:
    receipt = run([analysis("a2", "scope-1"), analysis("a1", "scope-1")])
    assert receipt["run_status"] == "CONVERGED_CANDIDATE"
    assert [item["finding_id"] for item in receipt["converged_findings"]] == ["f1"]
    assert receipt["rejected_findings"] == []
    assert receipt["unresolved_findings"] == []
    assert verify_agent_convergence_receipt(receipt) is True


def test_contradicted_finding_is_preserved_as_rejected() -> None:
    receipt = run([analysis("a1", "scope-1", relation="CONTRADICTS")])
    assert receipt["run_status"] == "NO_SUPPORTED_FINDINGS"
    assert receipt["converged_findings"] == []
    assert receipt["rejected_findings"][0]["status"] == "CONTRADICTED"


def test_scope_dependent_difference_is_not_averaged() -> None:
    receipt = run([
        analysis("a1", "condition-1", relation="SUPPORTS"),
        analysis("a2", "condition-2", relation="CONTRADICTS"),
    ])
    finding = receipt["unresolved_findings"][0]
    assert receipt["run_status"] == "PARTIAL"
    assert finding["status"] == CONDITIONALLY_DIVERGENT
    assert [item["status"] for item in finding["scope_results"]] == [
        "SUPPORTED", "CONTRADICTED",
    ]


def test_different_statement_for_same_id_remains_unresolved() -> None:
    receipt = run([
        analysis("a1", "scope-1", statement="X holds"),
        analysis("a2", "scope-1", statement="X never holds"),
    ])
    finding = receipt["unresolved_findings"][0]
    assert finding["status"] == "UNRESOLVED"
    assert finding["scope_results"][0]["reason"] == (
        "STATEMENT_IDENTITY_CONFLICT_WITHIN_SCOPE"
    )


def test_unknown_evidence_prevents_convergence() -> None:
    receipt = run([analysis("a1", "scope-1", relation="UNKNOWN")])
    assert receipt["run_status"] == "PARTIAL"
    assert receipt["unresolved_findings"][0]["status"] == "UNRESOLVED"


def test_distinct_supported_findings_are_retained() -> None:
    receipt = run([
        analysis("a1", "scope-1", finding_id="f2", statement="Y holds"),
        analysis("a2", "scope-1", finding_id="f1", statement="X holds"),
    ])
    assert [item["finding_id"] for item in receipt["converged_findings"]] == [
        "f1", "f2",
    ]


def test_input_order_does_not_change_receipt() -> None:
    first = analysis("a1", "scope-1")
    second = analysis("a2", "scope-2")
    assert run([first, second]) == run([second, first])


def test_input_receipts_are_isolated_from_later_mutation() -> None:
    source = analysis("a1", "scope-1")
    receipt = run([source])
    source["scope"] = "changed"
    assert receipt == run([analysis("a1", "scope-1")])


def test_duplicate_analysis_identity_fails_closed() -> None:
    with pytest.raises(VerifiedConvergenceAgentError, match="analysis_id"):
        run([analysis("a1", "scope-1"), analysis("a1", "scope-2")])


def test_empty_input_fails_closed() -> None:
    with pytest.raises(VerifiedConvergenceAgentError, match="at least one"):
        run([])


def test_tampered_analysis_receipt_fails_before_convergence() -> None:
    source = analysis("a1", "scope-1")
    source["finding_results"][0]["status"] = "CONTRADICTED"
    with pytest.raises(VerifiedConvergenceAgentError, match="verification failed"):
        run([source])


def test_agent_stops_before_uncomposed_effect_stages() -> None:
    receipt = run([analysis("a1", "scope-1")])
    assert receipt["pending_stages"] == [
        "DEPENDENCY_RECHECK", "ADMISSION", "PERSISTENCE",
    ]
    assert receipt["stopped"] is True


def test_agent_never_infers_usefulness_truth_or_authority() -> None:
    receipt = run([analysis("a1", "scope-1")])
    assert receipt["method_executed"] is False
    assert receipt["usefulness_inferred"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["recommended_action"] is None
    assert receipt["accepted"] is False
    assert receipt["selection_authority"] == "NONE"
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_receipt_hash_tampering_is_rejected() -> None:
    receipt = run([analysis("a1", "scope-1")])
    receipt["run_status"] = "CONVERGED"
    with pytest.raises(VerifiedConvergenceAgentError, match="hash mismatch"):
        verify_agent_convergence_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("usefulness_inferred", True),
        ("truth_claimed", True),
        ("accepted", True),
        ("selection_authority", "AGENT"),
        ("write_authority", "AGENT"),
        ("execution_authority", "AGENT"),
        ("recommended_action", "persist"),
        ("pending_stages", []),
    ],
)
def test_rehashed_semantic_forgery_is_rejected(field, value) -> None:
    receipt = run([analysis("a1", "scope-1")])
    receipt[field] = value
    body = {key: item for key, item in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(VerifiedConvergenceAgentError, match="internally inconsistent"):
        verify_agent_convergence_receipt(receipt)


def test_extra_field_is_rejected() -> None:
    receipt = run([analysis("a1", "scope-1")])
    receipt["autonomous"] = True
    with pytest.raises(VerifiedConvergenceAgentError, match="fields mismatch"):
        verify_agent_convergence_receipt(receipt)
