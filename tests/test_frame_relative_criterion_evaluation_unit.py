from __future__ import annotations

import pytest

from holosim.frame_relative_criterion_evaluation import (
    FrameRelativeCriterionEvaluationError,
    build_frame_criterion_evaluation_receipt,
)


def _information():
    return {
        "information_id": "artifact:demo",
        "statement": "latency_ms=95",
        "tags": ["latency"],
        "source_refs": ["measurement://run-1"],
    }


def _frame():
    return {
        "frame_id": "frame:latency",
        "measurement": "latency eligibility",
        "scope": ["latency"],
        "priorities": ["preserve measured latency"],
        "constraints": {},
        "conditions": {},
        "required_criteria": ["criterion:a", "criterion:b"],
        "success_rule": "ALL_REQUIRED_PASS",
    }


def _criterion(criterion_id: str, result: str):
    return {
        "criterion_id": criterion_id,
        "result": result,
        "evidence_hash": "b" * 64,
        "verifier_id": "verifier:test-v1",
    }


def test_all_required_pass_yields_pass():
    receipt = build_frame_criterion_evaluation_receipt(
        information=_information(),
        frame=_frame(),
        criterion_results=[
            _criterion("criterion:a", "PASS"),
            _criterion("criterion:b", "PASS"),
        ],
    )
    assert receipt["result"] == "PASS"
    assert receipt["missing_required_criteria"] == []


def test_required_fail_yields_fail():
    receipt = build_frame_criterion_evaluation_receipt(
        information=_information(),
        frame=_frame(),
        criterion_results=[
            _criterion("criterion:a", "PASS"),
            _criterion("criterion:b", "FAIL"),
        ],
    )
    assert receipt["result"] == "FAIL"


def test_required_indeterminate_yields_indeterminate():
    receipt = build_frame_criterion_evaluation_receipt(
        information=_information(),
        frame=_frame(),
        criterion_results=[
            _criterion("criterion:a", "PASS"),
            _criterion("criterion:b", "INDETERMINATE"),
        ],
    )
    assert receipt["result"] == "INDETERMINATE"


def test_duplicate_criterion_ids_fail_closed():
    with pytest.raises(FrameRelativeCriterionEvaluationError):
        build_frame_criterion_evaluation_receipt(
            information=_information(),
            frame=_frame(),
            criterion_results=[
                _criterion("criterion:a", "PASS"),
                _criterion("criterion:a", "FAIL"),
            ],
        )


def test_unsupported_success_rule_fails_closed():
    frame = _frame()
    frame["success_rule"] = "MAJORITY"

    with pytest.raises(FrameRelativeCriterionEvaluationError):
        build_frame_criterion_evaluation_receipt(
            information=_information(),
            frame=frame,
            criterion_results=[],
        )
