from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.bounded_priority_derivation import (
    BoundedPriorityDerivationError,
    derive_bounded_priority,
)
from holosim.evidence_bound_rule_applicability_gate import (
    build_evidence_bound_rule,
    evaluate_rule_applicability,
)
from holosim.frame_relative_criterion_evaluation import (
    build_frame_criterion_evaluation_receipt,
)


def _information():
    return {
        "information_id": "artifact:priority-demo",
        "statement": "candidate-a has verified mismatch evidence",
        "tags": ["priority"],
        "source_refs": ["measurement://priority-run-1"],
    }


def _frame():
    return {
        "frame_id": "frame:priority-derivation",
        "measurement": "priority eligibility",
        "scope": ["priority"],
        "priorities": ["prefer verified mismatch"],
        "constraints": {},
        "conditions": {},
        "required_criteria": ["criterion:verified-mismatch"],
        "success_rule": "ALL_REQUIRED_PASS",
    }


def _criterion_evaluation(*, result="PASS"):
    return build_frame_criterion_evaluation_receipt(
        information=_information(),
        frame=_frame(),
        criterion_results=[
            {
                "criterion_id": "criterion:verified-mismatch",
                "result": result,
                "evidence_hash": "a" * 64,
                "verifier_id": "verifier:mismatch-v1",
            }
        ],
    )


def _rule_applicability():
    source_evidence = {
        "evidence_id": "evidence:verified-mismatch",
        "candidate_id": "candidate-a",
    }

    rule = build_evidence_bound_rule(
        rule_id="rule:prefer-verified-mismatch",
        scope_type="project",
        scope_id="HOLO-Invariant",
        source_evidence=source_evidence,
        parent_rule_id=None,
        justification="Prefer a candidate with verified mismatch evidence.",
        applicability_conditions=["verified-mismatch-present"],
        conflict_ids=[],
    )

    return evaluate_rule_applicability(
        rule=rule,
        subject_type="project",
        subject_id="HOLO-Invariant",
        current_rule_id="rule:prefer-verified-mismatch",
        satisfied_conditions=["verified-mismatch-present"],
        unresolved_conflict_ids=[],
    )


def test_applicable_rule_and_passing_evaluation_derive_relative_priority():
    result = derive_bounded_priority(
        candidate_a_id="candidate-a",
        candidate_b_id="candidate-b",
        preferred_candidate_id="candidate-a",
        criterion_evaluation=_criterion_evaluation(),
        rule_applicability=_rule_applicability(),
    )

    assert result["relation"] == "A_OVER_B"
    assert result["preferred_candidate_id"] == "candidate-a"
    assert result["rule_id"] == "rule:prefer-verified-mismatch"

    assert result["selected_candidate_id"] is None
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert result["canonical_mutation"] is False


def test_nonpassing_evaluation_cannot_justify_priority():
    with pytest.raises(
        BoundedPriorityDerivationError,
        match="criterion evaluation must PASS",
    ):
        derive_bounded_priority(
            candidate_a_id="candidate-a",
            candidate_b_id="candidate-b",
            preferred_candidate_id="candidate-a",
            criterion_evaluation=_criterion_evaluation(
                result="INDETERMINATE"
            ),
            rule_applicability=_rule_applicability(),
        )


def test_preferred_candidate_must_be_one_of_compared_candidates():
    with pytest.raises(
        BoundedPriorityDerivationError,
        match="preferred candidate must be one of the compared candidates",
    ):
        derive_bounded_priority(
            candidate_a_id="candidate-a",
            candidate_b_id="candidate-b",
            preferred_candidate_id="candidate-c",
            criterion_evaluation=_criterion_evaluation(),
            rule_applicability=_rule_applicability(),
        )


def test_tampered_criterion_evaluation_is_rejected():
    evaluation = deepcopy(_criterion_evaluation())
    evaluation["result"] = "FAIL"

    with pytest.raises(
        BoundedPriorityDerivationError,
        match="criterion evaluation",
    ):
        derive_bounded_priority(
            candidate_a_id="candidate-a",
            candidate_b_id="candidate-b",
            preferred_candidate_id="candidate-a",
            criterion_evaluation=evaluation,
            rule_applicability=_rule_applicability(),
        )


def test_tampered_rule_applicability_is_rejected():
    applicability = deepcopy(_rule_applicability())
    applicability["result"] = "CONFLICT"

    with pytest.raises(
        BoundedPriorityDerivationError,
        match="rule applicability",
    ):
        derive_bounded_priority(
            candidate_a_id="candidate-a",
            candidate_b_id="candidate-b",
            preferred_candidate_id="candidate-a",
            criterion_evaluation=_criterion_evaluation(),
            rule_applicability=applicability,
        )