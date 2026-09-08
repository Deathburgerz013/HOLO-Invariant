from __future__ import annotations

from holosim.agent import run_verified_convergence_agent
from holosim.bounded_evidence_analyst import build_evidence_analysis_receipt
from holosim.canonical import stable_hash


def _analysis(analysis_id: str, relations: tuple[str, str]) -> dict[str, object]:
    evidence = [
        {"evidence_id": "e1", "content_sha256": stable_hash({"evidence": "one"}), "source_reference": "fixture:e1", "availability": "VERIFIED"},
        {"evidence_id": "e2", "content_sha256": stable_hash({"evidence": "two"}), "source_reference": "fixture:e2", "availability": "VERIFIED"},
    ]
    return build_evidence_analysis_receipt(
        analysis_id=analysis_id,
        scope="shared-scope",
        method={"method_id": "declared-relation-aggregation", "method_version": "v1", "description": "Characterize validity classification across placements."},
        evidence=evidence,
        findings=[{
            "finding_id": "shared-finding",
            "statement": "The bounded claim holds.",
            "evidence_assessments": [
                {"evidence_id": "e1", "disposition": "INCLUDED", "relation": relations[0], "rationale": "declared relation one"},
                {"evidence_id": "e2", "disposition": "INCLUDED", "relation": relations[1], "rationale": "declared relation two"},
            ],
        }],
    )


def _run(receipts: list[dict[str, object]]) -> dict[str, object]:
    return run_verified_convergence_agent(
        run_id="agent.verified-validity-preference-invariance",
        objective="Characterize validity classification independent of placement order.",
        analysis_receipts=receipts,
    )


def test_verified_classification_is_invariant_to_placement_order() -> None:
    placement_a = _analysis("placement-a", ("SUPPORTS", "NEUTRAL"))
    placement_b = _analysis("placement-b", ("SUPPORTS", "NEUTRAL"))
    forward = _run([placement_a, placement_b])
    reverse = _run([placement_b, placement_a])
    assert forward == reverse
    assert forward["run_status"] == "CONVERGED_CANDIDATE"
    assert len(forward["converged_findings"]) == 1
    assert forward["converged_findings"][0]["status"] == "SUPPORTED"
    assert forward["truth_claimed"] is False
    assert forward["accepted"] is False
    assert forward["selection_authority"] == "NONE"


def test_verified_contradiction_is_not_ranked_below_support() -> None:
    placement_a = _analysis("placement-a", ("CONTRADICTS", "NEUTRAL"))
    placement_b = _analysis("placement-b", ("CONTRADICTS", "NEUTRAL"))
    result = _run([placement_a, placement_b])
    assert result["run_status"] == "NO_SUPPORTED_FINDINGS"
    assert len(result["rejected_findings"]) == 1
    assert result["rejected_findings"][0]["status"] == "CONTRADICTED"
    assert result["truth_claimed"] is False
    assert result["selection_authority"] == "NONE"


def test_conflicting_evidence_preserves_residual_instead_of_forcing_preference() -> None:
    placement_a = _analysis("placement-a", ("SUPPORTS", "CONTRADICTS"))
    placement_b = _analysis("placement-b", ("SUPPORTS", "CONTRADICTS"))
    forward = _run([placement_a, placement_b])
    reverse = _run([placement_b, placement_a])
    assert forward == reverse
    assert forward["run_status"] == "PARTIAL"
    assert forward["converged_findings"] == []
    assert forward["rejected_findings"] == []
    assert len(forward["unresolved_findings"]) == 1
    assert forward["unresolved_findings"][0]["status"] == "UNRESOLVED"
    assert forward["truth_claimed"] is False
    assert forward["accepted"] is False
    assert forward["selection_authority"] == "NONE"
