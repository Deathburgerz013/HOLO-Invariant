import pytest

from holosim.information_boundary_firewall import (
    InformationBoundaryFirewallError,
    evaluate_information_crossing,
    verify_information_crossing,
)


def test_extraction_alone_cannot_cross_into_verified_truth():
    extraction = {
        "type": "source_grounded_information_extraction",
        "version": 1,
        "extraction_hash": "a" * 64,
    }

    with pytest.raises(
        InformationBoundaryFirewallError,
        match="verified truth",
    ):
        evaluate_information_crossing(
            information=extraction,
            requested_boundary="VERIFIED_TRUTH",
            verification_receipt=None,
        )


def test_arbitrary_verification_dictionary_cannot_cross_into_verified_truth():
    extraction = {"type": "source_grounded_information_extraction", "version": 1, "extraction_hash": "a" * 64}
    with pytest.raises(InformationBoundaryFirewallError, match="not supported"):
        evaluate_information_crossing(information=extraction, requested_boundary="VERIFIED_TRUTH", verification_receipt={"verified": True})


def test_extraction_claim_binding_is_required_before_truth_crossing():
    extraction = {"type": "source_grounded_information_extraction", "version": 1, "extraction_hash": "a" * 64}
    truth = {"type": "time_scoped_truth_state_receipt", "version": 1}
    with pytest.raises(InformationBoundaryFirewallError, match="claim binding"):
        evaluate_information_crossing(information=extraction, requested_boundary="VERIFIED_TRUTH", verification_receipt=truth)


def test_wrong_extraction_claim_binding_cannot_cross_verified_truth():
    from holosim.extraction_claim_binding import build_extraction_claim_binding
    extraction = {"type": "source_grounded_information_extraction", "version": 1, "extraction_hash": "a" * 64}
    truth = {"type": "time_scoped_truth_state_receipt", "version": 1, "claim": {"claim_id": "claim.original"}}
    binding = build_extraction_claim_binding(extraction_hash="b" * 64, claim_id="claim.original")
    with pytest.raises(InformationBoundaryFirewallError, match="does not correspond to extraction"):
        evaluate_information_crossing(information=extraction, requested_boundary="VERIFIED_TRUTH", verification_receipt=truth, claim_binding=binding)


def test_verified_true_receipt_with_exact_binding_crosses_firewall():
    from holosim.extraction_claim_binding import build_extraction_claim_binding
    from tests.test_time_scoped_truth import _receipt
    extraction = {"type": "source_grounded_information_extraction", "version": 1, "extraction_hash": "a" * 64}
    truth = _receipt()
    binding = build_extraction_claim_binding(extraction_hash=extraction["extraction_hash"], claim_id=truth["claim"]["claim_id"])
    crossing = evaluate_information_crossing(information=extraction, requested_boundary="VERIFIED_TRUTH", verification_receipt=truth, claim_binding=binding)
    assert crossing["status"] == "PERMITTED"
    assert crossing["boundary"] == "VERIFIED_TRUTH"
    assert crossing["extraction_hash"] == extraction["extraction_hash"]
    assert crossing["claim_id"] == truth["claim"]["claim_id"]
    assert crossing["truth_receipt_hash"] == truth["receipt_hash"]
    assert crossing["write_authority"] == "NONE"
    assert crossing["execution_authority"] == "NONE"


def test_verified_false_receipt_cannot_cross_verified_truth():
    from holosim.extraction_claim_binding import build_extraction_claim_binding
    from tests.test_time_scoped_truth import _receipt
    extraction = {"type": "source_grounded_information_extraction", "version": 1, "extraction_hash": "a" * 64}
    truth = _receipt(outcome="CONTRADICTS")
    assert truth["truth_status"] == "FALSE"
    binding = build_extraction_claim_binding(extraction_hash=extraction["extraction_hash"], claim_id=truth["claim"]["claim_id"])
    with pytest.raises(InformationBoundaryFirewallError, match="requires bounded TRUE"):
        evaluate_information_crossing(information=extraction, requested_boundary="VERIFIED_TRUTH", verification_receipt=truth, claim_binding=binding)


def test_verified_unknown_receipt_cannot_cross_verified_truth():
    from holosim.extraction_claim_binding import build_extraction_claim_binding
    from tests.test_time_scoped_truth import _inputs
    from holosim.time_scoped_truth import build_time_scoped_truth_receipt
    inputs = _inputs()
    from tests.test_time_scoped_truth import _check
    check = _check(status="UNAVAILABLE")
    inputs["checks"] = [check]
    inputs["observation"]["state_hash"] = check["result_binding"]["output_state_hash"]
    truth = build_time_scoped_truth_receipt(**inputs)
    assert truth["truth_status"] == "UNKNOWN"
    extraction = {"type": "source_grounded_information_extraction", "version": 1, "extraction_hash": "a" * 64}
    binding = build_extraction_claim_binding(extraction_hash=extraction["extraction_hash"], claim_id=truth["claim"]["claim_id"])
    with pytest.raises(InformationBoundaryFirewallError, match="requires bounded TRUE"):
        evaluate_information_crossing(information=extraction, requested_boundary="VERIFIED_TRUTH", verification_receipt=truth, claim_binding=binding)


def test_rehashed_forged_true_receipt_cannot_cross_verified_truth():
    from holosim.canonical import stable_hash
    from holosim.extraction_claim_binding import build_extraction_claim_binding
    from tests.test_time_scoped_truth import _receipt
    truth = _receipt(outcome="CONTRADICTS")
    assert truth["truth_status"] == "FALSE"
    truth["truth_status"] = "TRUE"
    truth["bounded_truth_established"] = True
    body = {key: value for key, value in truth.items() if key != "receipt_hash"}
    truth["receipt_hash"] = stable_hash(body)
    extraction = {"type": "source_grounded_information_extraction", "version": 1, "extraction_hash": "a" * 64}
    binding = build_extraction_claim_binding(extraction_hash=extraction["extraction_hash"], claim_id=truth["claim"]["claim_id"])
    with pytest.raises(InformationBoundaryFirewallError, match="verified truth receipt is invalid"):
        evaluate_information_crossing(information=extraction, requested_boundary="VERIFIED_TRUTH", verification_receipt=truth, claim_binding=binding)


def test_permitted_crossing_is_reconstructable_and_hash_bound():
    from holosim.extraction_claim_binding import build_extraction_claim_binding
    from tests.test_time_scoped_truth import _receipt
    extraction = {"type": "source_grounded_information_extraction", "version": 1, "extraction_hash": "a" * 64}
    truth = _receipt()
    binding = build_extraction_claim_binding(extraction_hash=extraction["extraction_hash"], claim_id=truth["claim"]["claim_id"])
    crossing = evaluate_information_crossing(information=extraction, requested_boundary="VERIFIED_TRUTH", verification_receipt=truth, claim_binding=binding)
    assert len(crossing["crossing_hash"]) == 64
    assert verify_information_crossing(crossing, information=extraction, verification_receipt=truth, claim_binding=binding) is True


def test_rehashed_forged_crossing_authority_fails_verification():
    from holosim.canonical import stable_hash
    from holosim.extraction_claim_binding import build_extraction_claim_binding
    from tests.test_time_scoped_truth import _receipt
    extraction = {"type": "source_grounded_information_extraction", "version": 1, "extraction_hash": "a" * 64}
    truth = _receipt()
    binding = build_extraction_claim_binding(extraction_hash=extraction["extraction_hash"], claim_id=truth["claim"]["claim_id"])
    crossing = evaluate_information_crossing(information=extraction, requested_boundary="VERIFIED_TRUTH", verification_receipt=truth, claim_binding=binding)
    crossing["write_authority"] = "GRANTED"
    body = {key: value for key, value in crossing.items() if key != "crossing_hash"}
    crossing["crossing_hash"] = stable_hash(body)
    with pytest.raises(InformationBoundaryFirewallError, match="internally inconsistent"):
        verify_information_crossing(crossing, information=extraction, verification_receipt=truth, claim_binding=binding)
