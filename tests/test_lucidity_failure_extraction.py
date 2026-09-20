from copy import deepcopy

import pytest

from holosim.bounded_evidence_analyst import build_evidence_analysis_receipt
from holosim.lucidity_failure_extraction import (
    LucidityFailureExtractionError,
    extract_demonstrated_failures,
    verify_lucidity_failure_extraction,
)


def _analysis(relation="CONTRADICTS"):
    return build_evidence_analysis_receipt(
        analysis_id="dream-replay-1",
        scope="offline replay",
        method={
            "method_id": "replay-check",
            "method_version": "1",
            "description": "compare replay finding with retained evidence",
        },
        evidence=[
            {
                "evidence_id": "e1",
                "content_sha256": "a" * 64,
                "source_reference": "replay:episode:1",
                "availability": "VERIFIED",
            }
        ],
        findings=[
            {
                "finding_id": "f1",
                "statement": "candidate behavior succeeds",
                "evidence_assessments": [
                    {
                        "evidence_id": "e1",
                        "disposition": "INCLUDED",
                        "relation": relation,
                        "rationale": "observed replay outcome differs",
                    }
                ],
            }
        ],
    )


def test_extracts_only_derived_contradiction():
    source = _analysis()
    receipt = extract_demonstrated_failures(source)

    assert receipt["status"] == "DEMONSTRATED_FAILURES_EXTRACTED"
    assert receipt["failure_count"] == 1
    assert receipt["failures"][0]["finding_id"] == "f1"
    assert receipt["failures"][0]["status"] == "CONTRADICTED"
    assert receipt["failures"][0]["contradicting_evidence_ids"] == ["e1"]
    assert receipt["source_receipt_hash"] == source["receipt_hash"]


def test_supported_finding_is_not_mislabeled_as_failure():
    source = _analysis("SUPPORTS")
    receipt = extract_demonstrated_failures(source)

    assert receipt["status"] == "NO_DEMONSTRATED_FAILURE"
    assert receipt["failure_count"] == 0
    assert receipt["failures"] == []


def test_extraction_grants_no_authority_or_truth():
    receipt = extract_demonstrated_failures(_analysis())

    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["selection_authority"] == "NONE"
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_extraction_is_deterministic():
    source = _analysis()
    assert extract_demonstrated_failures(source) == extract_demonstrated_failures(source)


def test_tampered_source_fails_closed():
    source = _analysis()
    source["finding_results"][0]["status"] = "SUPPORTED"

    with pytest.raises(LucidityFailureExtractionError):
        extract_demonstrated_failures(source)


def test_verifier_rebuilds_against_exact_source():
    source = _analysis()
    receipt = extract_demonstrated_failures(source)

    assert verify_lucidity_failure_extraction(
        receipt,
        analysis_receipt=source,
    )


def test_tampered_extraction_fails_verification():
    source = _analysis()
    receipt = extract_demonstrated_failures(source)
    tampered = deepcopy(receipt)
    tampered["failures"][0]["statement"] = "invented mistake"

    with pytest.raises(LucidityFailureExtractionError):
        verify_lucidity_failure_extraction(
            tampered,
            analysis_receipt=source,
        )


def _two_evidence_analysis(relations):
    return build_evidence_analysis_receipt(
        analysis_id="dream-replay-unresolved",
        scope="offline replay",
        method={
            "method_id": "replay-check",
            "method_version": "1",
            "description": "compare replay finding with retained evidence",
        },
        evidence=[
            {
                "evidence_id": "e1",
                "content_sha256": "a" * 64,
                "source_reference": "replay:episode:1",
                "availability": "VERIFIED",
            },
            {
                "evidence_id": "e2",
                "content_sha256": "b" * 64,
                "source_reference": "replay:episode:2",
                "availability": "VERIFIED",
            },
        ],
        findings=[
            {
                "finding_id": "f1",
                "statement": "candidate behavior succeeds",
                "evidence_assessments": [
                    {
                        "evidence_id": "e1",
                        "disposition": "INCLUDED",
                        "relation": relations[0],
                        "rationale": "first retained replay relation",
                    },
                    {
                        "evidence_id": "e2",
                        "disposition": "INCLUDED",
                        "relation": relations[1],
                        "rationale": "second retained replay relation",
                    },
                ],
            }
        ],
    )


def test_conflicting_evidence_is_not_promoted_to_failure():
    source = _two_evidence_analysis(("SUPPORTS", "CONTRADICTS"))
    assert source["finding_results"][0]["status"] == "UNRESOLVED"
    assert source["finding_results"][0]["status_reason"] == "CONFLICTING_EVIDENCE"

    receipt = extract_demonstrated_failures(source)
    assert receipt["status"] == "NO_DEMONSTRATED_FAILURE"
    assert receipt["failure_count"] == 0
    assert receipt["failures"] == []


def test_unknown_evidence_is_not_promoted_to_failure():
    source = _two_evidence_analysis(("SUPPORTS", "UNKNOWN"))
    assert source["finding_results"][0]["status"] == "UNRESOLVED"
    assert source["finding_results"][0]["status_reason"] == "UNKNOWN_EVIDENCE_REMAINS"

    receipt = extract_demonstrated_failures(source)
    assert receipt["status"] == "NO_DEMONSTRATED_FAILURE"
    assert receipt["failure_count"] == 0
    assert receipt["failures"] == []
