from holosim.functional_consciousness_experiment import (
    build_internal_monitor_receipt,
    verify_internal_monitor_receipt,
)


def test_internal_monitor_registers_detected_mismatch():
    receipt = build_internal_monitor_receipt(
        experiment_id="detection-registration-v1",
        condition_id="mismatch-detection",
        self_source_id="self-state",
        expected_self_state={"value": 1},
        observed_self_state={"value": 2},
    )

    assert verify_internal_monitor_receipt(receipt) is True
    assert receipt["perturbation_detected"] is True
    assert receipt["mismatch_paths"] == ["value"]
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_internal_monitor_registers_no_detection_when_states_match():
    receipt = build_internal_monitor_receipt(
        experiment_id="detection-registration-v1",
        condition_id="no-mismatch",
        self_source_id="self-state",
        expected_self_state={"value": 1},
        observed_self_state={"value": 1},
    )

    assert verify_internal_monitor_receipt(receipt) is True
    assert receipt["perturbation_detected"] is False
    assert receipt["mismatch_paths"] == []
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"