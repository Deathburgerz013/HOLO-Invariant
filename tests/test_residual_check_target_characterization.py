from __future__ import annotations

from holosim.agent import run_verified_convergence_agent
from holosim.bounded_evidence_analyst import build_evidence_analysis_receipt
from holosim.canonical import stable_hash


def _analysis(
    analysis_id: str,
    finding_id: str,
    statement: str,
    evidence_payload: str,
) -> dict[str, object]:
    return build_evidence_analysis_receipt(
        analysis_id=analysis_id,
        scope="shared-scope",
        method={
            "method_id": "independent-model-observation",
            "method_version": "v1",
            "description": "Characterize whether unresolved residuals retain recheck inputs.",
        },
        evidence=[
            {
                "evidence_id": "e1",
                "content_sha256": stable_hash({"payload": evidence_payload}),
                "source_reference": f"fixture:{analysis_id}",
                "availability": "VERIFIED",
            }
        ],
        findings=[
            {
                "finding_id": finding_id,
                "statement": statement,
                "evidence_assessments": [
                    {
                        "evidence_id": "e1",
                        "disposition": "INCLUDED",
                        "relation": "SUPPORTS",
                        "rationale": "Independent observation.",
                    }
                ],
            }
        ],
    )


def test_unresolved_cross_model_residual_retains_complete_recheck_identity() -> None:
    model_a = _analysis(
        "model-a",
        "model-a.local-17",
        "The observed boundary is closed.",
        "evidence-a",
    )
    model_b = _analysis(
        "model-b",
        "model-b.local-3",
        "The observed boundary remains open.",
        "evidence-b",
    )

    receipt = run_verified_convergence_agent(
        run_id="agent.residual-check-target-characterization",
        objective="Preserve enough identity to know exactly what must be rechecked.",
        analysis_receipts=[model_b, model_a],
        fact_identity_bindings=[
            {
                "fact_id": "fact:shared-observation",
                "members": [
                    {
                        "analysis_id": "model-a",
                        "finding_id": "model-a.local-17",
                    },
                    {
                        "analysis_id": "model-b",
                        "finding_id": "model-b.local-3",
                    },
                ],
            }
        ],
    )

    assert len(receipt["unresolved_findings"]) == 1
    residual = receipt["unresolved_findings"][0]

    assert residual["fact_id"] == "fact:shared-observation"
    assert residual["status"] == "UNRESOLVED"
    assert residual["reason"] == "AT_LEAST_ONE_SCOPE_UNRESOLVED"

    scope_result = residual["scope_results"][0]
    assert scope_result["scope"] == "shared-scope"
    assert scope_result["reason"] == "STATEMENT_IDENTITY_CONFLICT_WITHIN_SCOPE"

    observations = scope_result["observations"]
    assert [item["analysis_id"] for item in observations] == ["model-a", "model-b"]
    assert [item["finding_id"] for item in observations] == [
        "model-a.local-17",
        "model-b.local-3",
    ]

    # A future verifier must be able to identify the exact source analyses
    # and exact evidence sets involved in the unresolved disagreement.
    assert [item["analysis_receipt_hash"] for item in observations] == sorted([
        model_a["receipt_hash"],
        model_b["receipt_hash"],
    ])
    assert {item["evidence_set_hash"] for item in observations} == {
        model_a["evidence_set_hash"],
        model_b["evidence_set_hash"],
    }

    # No observer is elevated merely because it was supplied last.
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["selection_authority"] == "NONE"
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
