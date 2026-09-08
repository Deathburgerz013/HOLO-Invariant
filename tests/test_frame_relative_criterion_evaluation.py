from __future__ import annotations

import importlib


MODULE = "holosim.frame_relative_criterion_evaluation"


def _load_callable():
    module = importlib.import_module(MODULE)
    candidate = getattr(module, "build_frame_criterion_evaluation_receipt", None)
    assert callable(candidate), (
        f"{MODULE}.build_frame_criterion_evaluation_receipt must exist"
    )
    return candidate


def _information():
    return {
        "information_id": "artifact:demo",
        "statement": "latency_ms=95",
        "tags": ["latency"],
        "source_refs": ["measurement://run-1"],
    }


def _frame(frame_id: str, criterion_id: str):
    return {
        "frame_id": frame_id,
        "measurement": "latency eligibility",
        "scope": ["latency"],
        "priorities": ["preserve measured latency"],
        "constraints": {},
        "conditions": {},
        "required_criteria": [criterion_id],
        "success_rule": "ALL_REQUIRED_PASS",
    }


def _criterion(criterion_id: str, result: str):
    return {
        "criterion_id": criterion_id,
        "result": result,
        "evidence_hash": "a" * 64,
        "verifier_id": "verifier:latency-threshold-v1",
    }


def test_same_information_can_have_different_justified_results_under_different_frames():
    build = _load_callable()
    information = _information()

    permissive = build(
        information=information,
        frame=_frame("frame:p95-under-100", "criterion:p95-under-100"),
        criterion_results=[_criterion("criterion:p95-under-100", "PASS")],
    )
    strict = build(
        information=information,
        frame=_frame("frame:p99-under-80", "criterion:p99-under-80"),
        criterion_results=[_criterion("criterion:p99-under-80", "FAIL")],
    )

    assert permissive["information_hash"] == strict["information_hash"]
    assert permissive["frame_hash"] != strict["frame_hash"]
    assert permissive["result"] == "PASS"
    assert strict["result"] == "FAIL"
    assert permissive["evaluation_hash"] != strict["evaluation_hash"]


def test_original_success_criteria_are_preserved_and_missing_results_do_not_become_pass():
    build = _load_callable()
    receipt = build(
        information=_information(),
        frame=_frame("frame:missing", "criterion:required"),
        criterion_results=[],
    )

    assert receipt["frame"]["required_criteria"] == ["criterion:required"]
    assert receipt["result"] == "INDETERMINATE"
    assert receipt["missing_required_criteria"] == ["criterion:required"]


def test_criterion_for_another_frame_cannot_satisfy_this_frame():
    build = _load_callable()
    receipt = build(
        information=_information(),
        frame=_frame("frame:bound", "criterion:required"),
        criterion_results=[_criterion("criterion:other", "PASS")],
    )

    assert receipt["result"] == "INDETERMINATE"
    assert receipt["missing_required_criteria"] == ["criterion:required"]
    assert receipt["unbound_criterion_results"] == ["criterion:other"]


def test_receipt_grants_no_truth_acceptance_or_action_authority():
    build = _load_callable()
    receipt = build(
        information=_information(),
        frame=_frame("frame:bounded", "criterion:bounded"),
        criterion_results=[_criterion("criterion:bounded", "PASS")],
    )

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["state_change_authorized"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
