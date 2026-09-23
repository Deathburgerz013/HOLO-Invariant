from copy import deepcopy

from holosim.memory_card import (
    build_memory_card,
    copy_memory_card,
    load_memory_card,
    save_memory_card,
)
from holosim.reconstructor import (
    build_reconstructed_state,
    validate_reconstructed_state,
)


def _card():
    return build_memory_card(
        card_id="memory-card:integration:v1",
        observation={
            "type": "recorded_state",
            "state": {
                "location": "slot-1",
                "value": "state-A",
            },
        },
        source={
            "kind": "integration-test",
            "source_id": "memory-card-reconstruction",
        },
        observed_at="2026-09-22T20:00:00+00:00",
    )


def _item(card):
    return {
        "id": card["card_id"],
        "memory_card": deepcopy(card),
    }


def test_loaded_memory_card_can_be_reconstructed_as_explicit_state(tmp_path):
    card = _card()
    path = tmp_path / "slot-a.json"

    save_memory_card(path, card)
    loaded = load_memory_card(path)

    item = _item(loaded)

    state = build_reconstructed_state(
        "memory-card-replay",
        [loaded["card_id"]],
        [item],
    )

    assert state["status"] == "COMPLETE"
    assert state["reachable_ids"] == [loaded["card_id"]]
    assert state["carried_items"] == [item]
    assert state["accepted"] is False
    assert state["write_authority"] == "NONE"


def test_copied_memory_card_reconstructs_same_state(tmp_path):
    card = _card()

    source = tmp_path / "slot-a.json"
    copied = tmp_path / "slot-b.json"

    save_memory_card(source, card)
    copy_memory_card(source, copied)

    original = load_memory_card(source)
    transported = load_memory_card(copied)

    original_state = build_reconstructed_state(
        "memory-card-boundary",
        [original["card_id"]],
        [_item(original)],
    )

    transported_state = build_reconstructed_state(
        "memory-card-boundary",
        [transported["card_id"]],
        [_item(transported)],
    )

    assert original_state["state_hash"] == transported_state["state_hash"]
    assert original_state["carried_items"] == transported_state["carried_items"]


def test_reconstruction_preserves_recorded_state_without_claiming_current_truth(
    tmp_path,
):
    card = _card()
    path = tmp_path / "slot-a.json"

    save_memory_card(path, card)
    loaded = load_memory_card(path)

    reconstructed = build_reconstructed_state(
        "memory-card-currentness-boundary",
        [loaded["card_id"]],
        [_item(loaded)],
    )

    recorded = reconstructed["carried_items"][0]["memory_card"]

    current = {
        "type": "current_observation",
        "state": {
            "location": "slot-1",
            "value": "state-B",
        },
    }

    assert recorded["observation"]["state"]["value"] == "state-A"
    assert current["state"]["value"] == "state-B"

    # Reconstruction carries the recorded card exactly.
    # It does not replace the recorded observation with current evidence.
    assert recorded["observation"]["state"]["value"] != current["state"]["value"]

    assert "truth" not in reconstructed
    assert "current" not in reconstructed


def test_reconstructed_memory_card_state_is_independently_validatable(
    tmp_path,
):
    card = _card()
    path = tmp_path / "slot-a.json"

    save_memory_card(path, card)
    loaded = load_memory_card(path)

    item = _item(loaded)

    reconstructed = build_reconstructed_state(
        "memory-card-validation",
        [loaded["card_id"]],
        [item],
    )

    assert validate_reconstructed_state(
        reconstructed,
        [item],
    ) is True


def test_changed_current_observation_does_not_mutate_reconstructed_state(
    tmp_path,
):
    card = _card()
    path = tmp_path / "slot-a.json"

    save_memory_card(path, card)
    loaded = load_memory_card(path)

    item = _item(loaded)

    reconstructed = build_reconstructed_state(
        "memory-card-no-mutation",
        [loaded["card_id"]],
        [item],
    )

    before = deepcopy(reconstructed)

    current = deepcopy(loaded["observation"])
    current["state"]["value"] = "state-C"

    assert current["state"]["value"] == "state-C"
    assert reconstructed == before
    assert (
        reconstructed["carried_items"][0]["memory_card"]["observation"]["state"][
            "value"
        ]
        == "state-A"
    )