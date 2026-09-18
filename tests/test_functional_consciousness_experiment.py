import copy

import pytest

from holosim.functional_consciousness_experiment import (
    FunctionalConsciousnessExperimentError,
    build_experiment_input_receipt,
    verify_experiment_input_receipt,
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