import pytest

from holosim.frame_information_evaluator import (
    FrameInformationEvaluationError,
    evaluate_information_in_frame,
)


INFO = {
    "information_id": "x",
    "statement": "An observation.",
    "tags": ["alpha", "beta"],
    "source_refs": ["source://one"],
}


def _frame(scope):
    return {
        "frame_id": "frame-1",
        "measurement": "declared_measurement",
        "scope": scope,
        "priorities": ["safety"],
        "constraints": {"rule": "declared"},
        "conditions": {"mode": "test"},
    }


def test_scope_relation_is_derived_without_semantic_guessing():
    receipt = evaluate_information_in_frame(INFO, _frame(["alpha", "beta"]))
    assert receipt["scope_relation"]["status"] == "IN_SCOPE"
    assert receipt["constraint_status"] == "DECLARED_NOT_EVALUATED"
    assert receipt["condition_status"] == "DECLARED_NOT_EVALUATED"


def test_partial_and_out_of_scope_are_distinct():
    partial = evaluate_information_in_frame(INFO, _frame(["alpha"]))
    outside = evaluate_information_in_frame(INFO, _frame(["gamma"]))
    assert partial["scope_relation"]["status"] == "PARTIAL_SCOPE"
    assert outside["scope_relation"]["status"] == "OUT_OF_SCOPE"


def test_input_objects_are_not_mutated():
    info = dict(INFO)
    info["tags"] = list(INFO["tags"])
    info["source_refs"] = list(INFO["source_refs"])
    frame = _frame(["alpha"])
    before_info = repr(info)
    before_frame = repr(frame)
    evaluate_information_in_frame(info, frame)
    assert repr(info) == before_info
    assert repr(frame) == before_frame


def test_malformed_frame_fails_closed():
    frame = _frame(["alpha"])
    del frame["measurement"]
    with pytest.raises(FrameInformationEvaluationError):
        evaluate_information_in_frame(INFO, frame)
