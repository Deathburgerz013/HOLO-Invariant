import pytest

from holosim.bounded_evidence_analyst import (
    build_evidence_analysis_receipt,
    verify_evidence_analysis_receipt,
)
from holosim.canonical import stable_hash
from holosim.check_identity import build_check_identity, bind_check_result
from holosim.declared_verifier_execution_receipt import (
    execute_declared_verifier,
)
from holosim.directional_evidence_binding import (
    DirectionalEvidenceBindingError,
    bind_directional_outcome_to_evidence,
)
from holosim.verified_directional_check_outcome import (
    build_verified_directional_check_outcome,
)


def _directional_outcome(
    result=None,
    *,
    mismatch_outcome="CONTRADICTS",
):
    if result is None:
        result = {"status": "COMPLETE"}

    check_identity = build_check_identity(
        check_id="check:a",
        check_type="environment_snapshot_comparison",
        subject={"target": "environment:a"},
        reference_ids=["reference:a"],
        scope={"field": "status"},
        evidence_references=["evidence:a"],
        rule_references=["rule:a"],
        input_state_hash="state:before",
    )

    verifier_check_binding = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "declared_verifier_binding_hash": stable_hash(
            {"declared": "binding"}
        ),
        "verifier_id": "environment_snapshot_comparison",
        "check_id": check_identity["check_id"],
        "check_identity_hash": check_identity["check_identity_hash"],
        "execution_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    verifier_check_binding["binding_hash"] = stable_hash(
        verifier_check_binding
    )

    execution_receipt = execute_declared_verifier(
        verifier_check_binding=verifier_check_binding,
        check_identity=check_identity,
        available_verifiers={
            "environment_snapshot_comparison": lambda _: result
        },
    )

    result_binding = bind_check_result(
        check_identity=check_identity,
        result=execution_receipt["result"],
        output_state_hash="state:after",
    )

    return build_verified_directional_check_outcome(
        execution_receipt=execution_receipt,
        result_binding=result_binding,
        evaluation_rule={
            "type": "exact_result_match",
            "expected_result": {"status": "COMPLETE"},
            "match_outcome": "SUPPORTS",
            "mismatch_outcome": mismatch_outcome,
        },
    )


def test_support_direction_becomes_supporting_evidence():
    directional = _directional_outcome()

    bound = bind_directional_outcome_to_evidence(directional)

    assert bound["evidence"] == {
        "evidence_id": "check:a",
        "content_sha256": directional["outcome_hash"],
        "source_reference": (
            f"directional:{directional['outcome_hash']}"
        ),
        "availability": "VERIFIED",
    }
    assert bound["assessment"]["evidence_id"] == "check:a"
    assert bound["assessment"]["disposition"] == "INCLUDED"
    assert bound["assessment"]["relation"] == "SUPPORTS"


def test_contradiction_direction_is_preserved():
    directional = _directional_outcome(
        {"status": "INCOMPLETE"},
    )

    bound = bind_directional_outcome_to_evidence(directional)

    assert directional["outcome"] == "CONTRADICTS"
    assert bound["assessment"]["relation"] == "CONTRADICTS"


def test_unknown_direction_is_preserved():
    directional = _directional_outcome(
        {"status": "INCOMPLETE"},
        mismatch_outcome="UNKNOWN",
    )

    bound = bind_directional_outcome_to_evidence(directional)

    assert directional["outcome"] == "UNKNOWN"
    assert bound["assessment"]["relation"] == "UNKNOWN"


def test_binding_preserves_verified_source_identity():
    directional = _directional_outcome()

    bound = bind_directional_outcome_to_evidence(directional)

    assert bound["source_outcome_hash"] == directional["outcome_hash"]
    assert (
        bound["source_execution_receipt_hash"]
        == directional["execution_receipt_hash"]
    )
    assert (
        bound["source_result_binding_hash"]
        == directional["result_binding_hash"]
    )
    assert (
        bound["source_evaluation_rule_hash"]
        == directional["evaluation_rule_hash"]
    )


def test_binding_grants_no_truth_acceptance_or_authority():
    bound = bind_directional_outcome_to_evidence(
        _directional_outcome()
    )

    assert bound["truth_claimed"] is False
    assert bound["accepted"] is False
    assert bound["selection_authority"] == "NONE"
    assert bound["write_authority"] == "NONE"
    assert bound["execution_authority"] == "NONE"


def test_tampered_directional_outcome_fails_closed():
    directional = _directional_outcome()
    directional["outcome"] = "CONTRADICTS"

    with pytest.raises(DirectionalEvidenceBindingError):
        bind_directional_outcome_to_evidence(directional)


def test_binding_feeds_bounded_evidence_analysis_without_reinterpretation():
    directional = _directional_outcome()
    bound = bind_directional_outcome_to_evidence(directional)

    analysis = build_evidence_analysis_receipt(
        analysis_id="directional-analysis",
        scope="verified directional check",
        method={
            "method_id": "directional-binding",
            "method_version": "1",
            "description": (
                "analyze preserved verified directional outcome"
            ),
        },
        evidence=[bound["evidence"]],
        findings=[
            {
                "finding_id": "finding:a",
                "statement": "verified check supports candidate condition",
                "evidence_assessments": [bound["assessment"]],
            }
        ],
    )

    assert verify_evidence_analysis_receipt(analysis) is True
    assert analysis["finding_results"][0]["status"] == "SUPPORTED"
    assert (
        analysis["finding_results"][0]["supporting_evidence_ids"]
        == ["check:a"]
    )
    assert analysis["truth_claimed"] is False
    assert analysis["accepted"] is False
