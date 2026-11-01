from copy import deepcopy

from tests.test_reconstruction_correction_binding import inputs
from holosim.continuity_under_absence import build_continuity_receipt
from holosim.environment_invariant_receipts import evaluate_environment_invariant
from holosim.reconstruction_correction_binding import (
    build_reconstruction_correction_binding,
    validate_reconstruction_correction_binding,
)

def test_regenerated_consistent_evidence_does_not_establish_provenance():
    original_receipt, original_evidence, proposal = inputs()

    # Construct a fresh, internally consistent receipt and observation
    # for the same candidate. This is not an authenticated observation.
    endpoint = deepcopy(proposal["candidate_claims"])

    regenerated_receipt = build_continuity_receipt(
        prior_state=deepcopy(proposal["current_claims"]),
        current_state=endpoint,
        observer_present_before=True,
        observer_present_after=False,
    )

    regenerated_evidence = evaluate_environment_invariant(
        invariant_id="adversarial-self-report",
        statement="self-reported endpoint matches declared endpoint",
        scope={"phase": "adversarial"},
        environment=endpoint,
        environment_probe=lambda: endpoint,
        check=lambda: True,
        check_id="self-report-check",
        observed_at="2026-11-01T12:00:00-07:00",
    )

    result = build_reconstruction_correction_binding(
        continuity_receipt=regenerated_receipt,
        external_evidence=regenerated_evidence,
        proposal=proposal,
    )

    assert validate_reconstruction_correction_binding(result) is True
    assert result["status"] == "IDENTITY_BOUND"
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"

    # The binding changed because the evidence identity changed.
    original_binding = build_reconstruction_correction_binding(
        continuity_receipt=original_receipt,
        external_evidence=original_evidence,
        proposal=proposal,
    )
    assert result["binding_hash"] != original_binding["binding_hash"]

    # Structural validation succeeded, but no independent provenance
    # was established by this test.
