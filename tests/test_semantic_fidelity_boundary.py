from holosim.hook_contract import build_hook_request, build_hook_result
from holosim.source_grounded_information_extraction import (
    build_source_grounded_extraction,
    verify_source_grounded_extraction,
)
from holosim.extraction_claim_binding import (
    build_extraction_claim_binding,
    verify_extraction_claim_binding,
    verify_extraction_claim_correspondence,
)


from holosim.bounded_invariant_breaker import (
    build_invariant_artifact,
    compare_invariant_artifacts,
    verify_breaker_receipt,
)

def test_valid_identity_binding_does_not_establish_semantic_fidelity():
    source = "Corrections require verified evidence."

    request = build_hook_request(
        hook_id="source-reader",
        action="observe",
        reference="document:fidelity-counterexample",
        payload={},
    )
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"document": {"text": source}},
    )

    extraction = build_source_grounded_extraction(
        request=request,
        result=result,
        source_path=["document", "text"],
        start_offset=0,
        end_offset=len(source),
        extracted_text=source,
    )

    assert verify_source_grounded_extraction(
        extraction,
        request=request,
        result=result,
    ) is True

    claim_id = "claim.verified-evidence-required"
    claim_value = {"verified_evidence_required": False}

    binding = build_extraction_claim_binding(
        extraction_hash=extraction["extraction_hash"],
        claim_id=claim_id,
    )

    assert verify_extraction_claim_binding(binding) is True
    assert verify_extraction_claim_correspondence(
        binding,
        extraction_hash=extraction["extraction_hash"],
        claim_id=claim_id,
    ) is True

    # The claim value contradicts the source requirement.
    # Neither verifier receives or evaluates claim_value.
    assert claim_value["verified_evidence_required"] is False
    assert "require verified evidence" in source

    # Valid correspondence is not semantic justification.
    assert binding["truth_claimed"] is False
    assert binding["accepted"] is False
    assert binding["write_authority"] == "NONE"
    assert binding["execution_authority"] == "NONE"

def test_structured_preservation_does_not_prove_source_fidelity():
    incorrect_claim = {
        "claim.verified-evidence-required": {
            "verified_evidence_required": False,
        }
    }

    def artifact(label, expression):
        return build_invariant_artifact(
            artifact_label=label,
            contract_id="semantic-fidelity-boundary",
            contract_version=1,
            claims=incorrect_claim,
            expression=expression,
            provenance={"source": "fidelity-counterexample"},
        )

    anchor = artifact(
        "anchor",
        "Corrections require verified evidence.",
    )
    parent = artifact(
        "parent",
        "Corrections require verified evidence.",
    )
    candidate = artifact(
        "candidate",
        "Corrections may proceed without verified evidence.",
    )

    receipt = compare_invariant_artifacts(
        anchor=anchor,
        parent=parent,
        candidate=candidate,
    )

    assert verify_breaker_receipt(receipt)["valid"] is True
    assert receipt["classification"] == "EQUIVALENT_EXPRESSION"
    assert receipt["expression_changed"] is True
    assert receipt["contradictory_claim_ids"] == []
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
