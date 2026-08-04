from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.guarantee_review_eligibility import (
    GuaranteeReviewEligibilityError,
    evaluate_guarantee_review_eligibility,
)


def _candidate() -> dict[str, object]:
    return {
        "guarantee_id": "attention-cycle-value",
        "confidence": 0.9,
        "reinforcement_count": 3,
        "evidence_refs": ["receipt-a", "receipt-b"],
        "session_ids": ["session-a", "session-b"],
        "contradiction_count": 0,
        "dedup_key": "attention:cycle-value:v1",
        "duplicate_of": None,
    }


def test_candidate_with_bounded_independent_evidence_is_review_eligible() -> None:
    result = evaluate_guarantee_review_eligibility(_candidate())

    assert result["decision"] == "REVIEW_ELIGIBLE"
    assert result["checks"] == {
        "confidence": True,
        "reinforcement": True,
        "evidence": True,
        "session_diversity": True,
        "uncontradicted": True,
        "unique": True,
    }
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert len(result["candidate_hash"]) == 64
    assert len(result["receipt_hash"]) == 64


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("confidence", 0.7, "INSUFFICIENT_CONFIDENCE"),
        ("reinforcement_count", 1, "INSUFFICIENT_REINFORCEMENT"),
        ("evidence_refs", ["receipt-a"], "INSUFFICIENT_EVIDENCE"),
        (
            "session_ids",
            ["session-a"],
            "INSUFFICIENT_SESSION_DIVERSITY",
        ),
    ],
)
def test_candidate_reports_the_first_unsatisfied_evidence_gate(
    field: str,
    value: object,
    expected: str,
) -> None:
    candidate = _candidate()
    candidate[field] = value

    result = evaluate_guarantee_review_eligibility(candidate)

    assert result["decision"] == expected
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_contradiction_requires_review_before_other_thresholds() -> None:
    candidate = _candidate()
    candidate["confidence"] = 0.1
    candidate["contradiction_count"] = 1

    result = evaluate_guarantee_review_eligibility(candidate)

    assert result["decision"] == "CONTRADICTED"
    assert result["accepted"] is False


def test_exact_structural_duplicate_is_not_review_eligible() -> None:
    candidate = _candidate()
    candidate["duplicate_of"] = "existing-attention-cycle-value"

    result = evaluate_guarantee_review_eligibility(candidate)

    assert result["decision"] == "DUPLICATE"
    assert result["checks"]["unique"] is False
    assert result["candidate"]["dedup_key"] == "attention:cycle-value:v1"


def test_input_is_not_mutated() -> None:
    candidate = _candidate()
    original = deepcopy(candidate)

    evaluate_guarantee_review_eligibility(candidate)

    assert candidate == original


def test_receipt_is_deterministic() -> None:
    first = evaluate_guarantee_review_eligibility(_candidate())
    second = evaluate_guarantee_review_eligibility(_candidate())

    assert first == second


def test_duplicate_session_ids_are_rejected_instead_of_inflating_diversity() -> None:
    candidate = _candidate()
    candidate["session_ids"] = ["session-a", "session-a"]

    with pytest.raises(
        GuaranteeReviewEligibilityError,
        match="session_ids must contain unique values",
    ):
        evaluate_guarantee_review_eligibility(candidate)


def test_nonfinite_confidence_is_rejected() -> None:
    candidate = _candidate()
    candidate["confidence"] = float("nan")

    with pytest.raises(
        GuaranteeReviewEligibilityError,
        match="confidence must be a finite number between 0 and 1",
    ):
        evaluate_guarantee_review_eligibility(candidate)


def test_unknown_fields_are_rejected() -> None:
    candidate = _candidate()
    candidate["accepted"] = True

    with pytest.raises(
        GuaranteeReviewEligibilityError,
        match="candidate fields are invalid",
    ):
        evaluate_guarantee_review_eligibility(candidate)
