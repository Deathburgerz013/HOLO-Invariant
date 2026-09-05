from holosim.agent import (
    run_verified_convergence_agent,
    verify_agent_convergence_receipt,
)
from holosim.bounded_evidence_analyst import build_evidence_analysis_receipt
from holosim.canonical import stable_hash
from holosim.fact_identity import build_verified_fact_identity_receipt


def _analysis(analysis_id: str, finding_id: str) -> dict:
    return build_evidence_analysis_receipt(
        analysis_id=analysis_id,
        scope="scope-1",
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
            "statement": "X holds",
            "evidence_assessments": [{
                "evidence_id": "e1",
                "disposition": "INCLUDED",
                "relation": "SUPPORTS",
                "rationale": "fixture support",
            }],
        }],
    )


def test_fact_identity_receipt_origin_convergence_receipt_rebuilds() -> None:
    first = _analysis("model-a", "model-a.fact-17")
    second = _analysis("model-b", "model-b.output-3")
    identity_receipt = build_verified_fact_identity_receipt(
        fact_id="fact:x",
        members=[
            {"analysis_id": "model-a", "finding_id": "model-a.fact-17"},
            {"analysis_id": "model-b", "finding_id": "model-b.output-3"},
        ],
    )

    receipt = run_verified_convergence_agent(
        run_id="agent.run-identity-receipt",
        objective="Verify receipt-origin fact identity convergence.",
        analysis_receipts=[first, second],
        fact_identity_receipts=[identity_receipt],
    )

    assert verify_agent_convergence_receipt(receipt) is True

def test_direct_fact_identity_bindings_and_receipts_fail_closed() -> None:
    first = _analysis("model-a", "model-a.fact-17")
    second = _analysis("model-b", "model-b.output-3")
    members = [
        {"analysis_id": "model-a", "finding_id": "model-a.fact-17"},
        {"analysis_id": "model-b", "finding_id": "model-b.output-3"},
    ]
    identity_receipt = build_verified_fact_identity_receipt(
        fact_id="fact:x",
        members=members,
    )

    import pytest
    from holosim.agent import VerifiedConvergenceAgentError

    with pytest.raises(
        VerifiedConvergenceAgentError,
        match="bindings and receipts cannot be combined",
    ):
        run_verified_convergence_agent(
            run_id="agent.run-identity-conflict",
            objective="Reject duplicate fact-identity input channels.",
            analysis_receipts=[first, second],
            fact_identity_bindings=[
                {
                    "fact_id": "fact:x",
                    "members": members,
                },
            ],
            fact_identity_receipts=[identity_receipt],
        )

