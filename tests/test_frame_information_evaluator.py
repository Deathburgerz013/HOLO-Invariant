import importlib
import pytest

MODULE = "holosim.frame_information_evaluator"

def _load_evaluator():
    try:
        module = importlib.import_module(MODULE)
    except ModuleNotFoundError:
        pytest.fail("Missing production frame-information evaluator: expected holosim.frame_information_evaluator")
    evaluator = getattr(module, "evaluate_information_in_frame", None)
    assert callable(evaluator)
    return evaluator

def _information():
    return {
        "information_id": "battery-temperature",
        "statement": "Battery temperature is 62 C.",
        "tags": ["battery", "temperature", "telemetry"],
        "source_refs": ["sensor://battery/temperature"],
    }

def _frame(frame_id, measurement, priorities, constraints):
    return {
        "frame_id": frame_id,
        "measurement": measurement,
        "scope": ["battery", "temperature", "telemetry"],
        "priorities": priorities,
        "constraints": constraints,
        "conditions": {"vehicle_state": "charging"},
    }

def test_same_information_can_count_differently_under_two_declared_frames():
    evaluate = _load_evaluator()
    information = _information()
    safety = evaluate(information, _frame(
        "battery-safety", "operational_safety",
        ["safety", "continuity"], {"max_temperature_c": 60}))
    archival = evaluate(information, _frame(
        "telemetry-archive", "historical_retention",
        ["retention", "ordering"], {"required_source_refs": True}))
    assert safety["information_hash"] == archival["information_hash"]
    assert safety["frame_hash"] != archival["frame_hash"]
    assert safety["evaluation_hash"] != archival["evaluation_hash"]
    assert safety != archival

def test_evaluation_is_deterministic_for_same_information_and_same_frame():
    evaluate = _load_evaluator()
    information = _information()
    frame = _frame("battery-safety", "operational_safety",
                   ["safety", "continuity"], {"max_temperature_c": 60})
    assert evaluate(information, frame) == evaluate(information, frame)

def test_evaluator_preserves_declared_frame_and_grants_no_authority():
    evaluate = _load_evaluator()
    frame = _frame("battery-safety", "operational_safety",
                   ["safety", "continuity"], {"max_temperature_c": 60})
    receipt = evaluate(_information(), frame)
    assert receipt["frame"] == frame
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["state_change_authorized"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

def test_evaluator_does_not_invent_universal_numeric_weight():
    evaluate = _load_evaluator()
    frame = _frame("battery-safety", "operational_safety",
                   ["safety", "continuity"], {"max_temperature_c": 60})
    receipt = evaluate(_information(), frame)
    assert "weight" not in receipt
    assert "score" not in receipt
    assert "importance" not in receipt
