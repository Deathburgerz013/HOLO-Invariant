import copy

import pytest
from holosim.functional_consciousness_experiment import (
    FunctionalConsciousnessExperimentError,
    build_experiment_input_receipt,
    build_internal_monitor_receipt,
    verify_experiment_input_receipt,
    verify_internal_monitor_receipt,
)


def _receipt():
    return build_experiment_input_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="baseline",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_state={"signal": "stable", "value": 1},
        self_state={"operating_state": "nominal", "value": 1},
    )


def test_builds_verified_source_separated_receipt():
    receipt = _receipt()

    assert receipt["world_source_id"] == "world-channel"
    assert receipt["self_source_id"] == "self-channel"
    assert receipt["world_state_hash"] != receipt["self_state_hash"]
    assert receipt["sources_separated"] is True
    assert receipt["subjective_consciousness_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert verify_experiment_input_receipt(receipt) is True


def test_identical_inputs_are_byte_stable_at_receipt_value_level():
    first = _receipt()
    second = _receipt()

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_world_and_self_sources_must_differ():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="must differ",
    ):
        build_experiment_input_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="baseline",
            world_source_id="same-channel",
            self_source_id="same-channel",
            world_state={"value": 1},
            self_state={"value": 1},
        )


def test_same_value_from_distinct_sources_remains_source_separated():
    receipt = build_experiment_input_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="same-value-control",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_state={"value": 1},
        self_state={"value": 1},
    )

    assert receipt["world_state_hash"] == receipt["self_state_hash"]
    assert receipt["world_source_id"] != receipt["self_source_id"]
    assert receipt["sources_separated"] is True
    assert verify_experiment_input_receipt(receipt) is True


def test_non_json_state_fails_closed():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="plain JSON values",
    ):
        build_experiment_input_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="invalid-state",
            world_source_id="world-channel",
            self_source_id="self-channel",
            world_state={"invalid": {1, 2, 3}},
            self_state={"value": 1},
        )


def test_nonfinite_state_fails_closed():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="finite",
    ):
        build_experiment_input_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="nonfinite-state",
            world_source_id="world-channel",
            self_source_id="self-channel",
            world_state={"value": float("nan")},
            self_state={"value": 1},
        )


def test_tampered_receipt_hash_fails_closed():
    receipt = _receipt()
    receipt["condition_id"] = "tampered"

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="receipt hash mismatch",
    ):
        verify_experiment_input_receipt(receipt)


def test_rehashed_source_collision_still_fails_closed():
    receipt = _receipt()
    forged = copy.deepcopy(receipt)
    forged["self_source_id"] = forged["world_source_id"]

    body = {
        key: value
        for key, value in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="not separated",
    ):
        verify_experiment_input_receipt(forged)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sources_separated", False, "sources_separated"),
        (
            "subjective_consciousness_claimed",
            True,
            "subjective consciousness",
        ),
        ("accepted", True, "must not accept"),
        ("write_authority", "FULL", "write authority"),
        ("execution_authority", "FULL", "execution authority"),
    ],
)
def test_rehashed_boundary_tampering_fails_closed(field, value, message):
    receipt = _receipt()
    forged = copy.deepcopy(receipt)
    forged[field] = value

    body = {
        key: item
        for key, item in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match=message,
    ):
        verify_experiment_input_receipt(forged)


def test_unknown_receipt_field_fails_closed():
    receipt = _receipt()
    receipt["surprise_authority_from_the_void"] = True

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="receipt fields mismatch",
    ):
        verify_experiment_input_receipt(receipt)
def _monitor_receipt():
    return build_internal_monitor_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="hidden-self-perturbation",
        self_source_id="self-channel",
        expected_self_state={
            "operating_state": "nominal",
            "load": 1,
        },
        observed_self_state={
            "operating_state": "degraded",
            "load": 1,
        },
    )


def test_monitor_detects_hidden_self_perturbation_pre_report():
    receipt = _monitor_receipt()

    assert receipt["mismatch_paths"] == ["operating_state"]
    assert receipt["perturbation_detected"] is True
    assert receipt["observation_stage"] == "PRE_REPORT"
    assert receipt["reporter_executed"] is False
    assert verify_internal_monitor_receipt(receipt) is True


def test_monitor_nominal_state_has_no_perturbation():
    receipt = build_internal_monitor_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="nominal",
        self_source_id="self-channel",
        expected_self_state={"operating_state": "nominal"},
        observed_self_state={"operating_state": "nominal"},
    )

    assert receipt["mismatch_paths"] == []
    assert receipt["perturbation_detected"] is False
    assert (
        receipt["expected_self_state_hash"]
        == receipt["observed_self_state_hash"]
    )
    assert verify_internal_monitor_receipt(receipt) is True


def test_monitor_mismatch_paths_are_deterministic():
    receipt = build_internal_monitor_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="multi-perturbation",
        self_source_id="self-channel",
        expected_self_state={
            "z": 1,
            "nested": {"b": 2, "a": 1},
        },
        observed_self_state={
            "z": 2,
            "nested": {"b": 3, "a": 0},
        },
    )

    assert receipt["mismatch_paths"] == [
        "nested.a",
        "nested.b",
        "z",
    ]


def test_monitor_rejects_non_json_self_state():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="plain JSON values",
    ):
        build_internal_monitor_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="invalid",
            self_source_id="self-channel",
            expected_self_state={"value": 1},
            observed_self_state={"value": {1, 2}},
        )


def test_monitor_tampering_fails_before_semantic_credit():
    receipt = _monitor_receipt()
    receipt["perturbation_detected"] = False

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="monitor receipt hash mismatch",
    ):
        verify_internal_monitor_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "perturbation_detected",
            False,
            "monitor detection is inconsistent",
        ),
        (
            "observation_stage",
            "POST_REPORT",
            "must execute pre-report",
        ),
        (
            "reporter_executed",
            True,
            "reporter must not execute",
        ),
        (
            "subjective_consciousness_claimed",
            True,
            "subjective consciousness",
        ),
        (
            "accepted",
            True,
            "must not accept",
        ),
        (
            "write_authority",
            "FULL",
            "write authority",
        ),
        (
            "execution_authority",
            "FULL",
            "execution authority",
        ),
    ],
)
def test_rehashed_monitor_boundary_tampering_fails_closed(
    field,
    value,
    message,
):
    receipt = _monitor_receipt()
    forged = copy.deepcopy(receipt)
    forged[field] = value

    body = {
        key: item
        for key, item in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match=message,
    ):
        verify_internal_monitor_receipt(forged)


def test_rehashed_monitor_hash_relation_tampering_fails_closed():
    receipt = _monitor_receipt()
    forged = copy.deepcopy(receipt)
    forged["observed_self_state_hash"] = forged["expected_self_state_hash"]

    body = {
        key: item
        for key, item in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="hashes and mismatch state are inconsistent",
    ):
        verify_internal_monitor_receipt(forged)