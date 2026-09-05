from __future__ import annotations

from holosim.agent import run_verified_convergence_agent
from holosim.bounded_evidence_analyst import build_evidence_analysis_receipt
from holosim.canonical import stable_hash


def _analysis(
    analysis_id: str,
    finding_id: str,
    statement: str,
) -> dict[str, object]:
    return build_evidence_analysis_receipt(
        analysis_id=analysis_id,
        scope="shared-scope",
        method={
            "method_id": "independent-model-observation",
            "method_version": "v1",
            "description": "Independent observation for symmetric residual characterization.",
        },
        evidence=[
            {
                "evidence_id": "shared-evidence",
                "content_sha256": stable_hash({"observed": "same external evidence"}),
                "source_reference": "fixture:shared-external-evidence",
                "availability": "VERIFIED",
            }
        ],
        findings=[
            {
                "finding_id": finding_id,
                "statement": statement,
                "evidence_assessments": [
                    {
                        "evidence_id": "shared-evidence",
                        "disposition": "INCLUDED",
                        "relation": "SUPPORTS",
                        "rationale": "Observation checked against the same declared evidence.",
                    }
                ],
            }
        ],
    )


def _run(receipts: list[dict[str, object]]) -> dict[str, object]:
    return run_verified_convergence_agent(
        run_id="agent.no-last-speaker-residual-characterization",
        objective="Characterize symmetric preservation of cross-model disagreement.",
        analysis_receipts=receipts,
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


def test_cross_model_disagreement_is_preserved_as_symmetric_residual() -> None:
    model_a = _analysis(
        "model-a",
        "model-a.local-17",
        "The observed boundary is closed.",
    )
    model_b = _analysis(
        "model-b",
        "model-b.local-3",
        "The observed boundary remains open.",
    )

    forward = _run([model_a, model_b])
    reverse = _run([model_b, model_a])

    assert forward == reverse
    assert forward["run_status"] == "PARTIAL"
    assert forward["converged_findings"] == []
    assert forward["rejected_findings"] == []
    assert len(forward["unresolved_findings"]) == 1

    residual = forward["unresolved_findings"][0]
    assert residual["fact_id"] == "fact:shared-observation"
    assert residual["status"] == "UNRESOLVED"

    assert residual["finding_ids"] == [
        "model-a.local-17",
        "model-b.local-3",
    ]

    scope_result = residual["scope_results"][0]
    assert scope_result["scope"] == "shared-scope"
    assert scope_result["status"] == "UNRESOLVED"
    assert scope_result["reason"] == "STATEMENT_IDENTITY_CONFLICT_WITHIN_SCOPE"

    assert scope_result["statements"] == [
        "The observed boundary is closed.",
        "The observed boundary remains open.",
    ]

    assert forward["truth_claimed"] is False
    assert forward["accepted"] is False
    assert forward["selection_authority"] == "NONE"
    assert forward["write_authority"] == "NONE"
    assert forward["execution_authority"] == "NONE"
