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
            "description": "Independent observation for order-invariance characterization.",
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
                        "rationale": "Both observations are checked against the same evidence.",
                    }
                ],
            }
        ],
    )


def _run(receipts: list[dict[str, object]]) -> dict[str, object]:
    return run_verified_convergence_agent(
        run_id="agent.no-last-speaker-characterization",
        objective="Characterize whether observation order changes convergence.",
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


def test_cross_model_convergence_has_no_last_speaker_privilege() -> None:
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
