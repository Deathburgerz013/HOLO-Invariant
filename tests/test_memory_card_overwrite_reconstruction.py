from holosim.memory_card import (
    build_memory_card,
    load_memory_card,
    overwrite_memory_card,
    save_memory_card,
)
from holosim.reconstructor import build_reconstructed_state


def _card(card_id, value):
    return build_memory_card(
        card_id=card_id,
        observation={
            "type": "recorded_state",
            "state": {
                "value": value,
            },
        },
        source={
            "kind": "overwrite-reconstruction-test",
            "source_id": "memory-card",
        },
        observed_at="2026-09-22T20:00:00+00:00",
    )


def _item(card):
    return {
        "id": card["card_id"],
        "memory_card": card,
    }


def test_overwritten_slot_reconstructs_new_state(tmp_path):
    old = _card("memory-card:old", "state-A")
    new = _card("memory-card:new", "state-B")

    path = tmp_path / "slot.json"

    save_memory_card(path, old)
    overwrite_memory_card(path, new)

    loaded = load_memory_card(path)

    state = build_reconstructed_state(
        "overwrite-reconstruction",
        [loaded["card_id"]],
        [_item(loaded)],
    )

    assert loaded["card_id"] == "memory-card:new"
    assert state["status"] == "COMPLETE"
    assert state["reachable_ids"] == ["memory-card:new"]
    assert (
        state["carried_items"][0]["memory_card"]["observation"]["state"][
            "value"
        ]
        == "state-B"
    )


def test_preserved_old_card_reconstructs_old_state_after_slot_overwrite(
    tmp_path,
):
    old = _card("memory-card:old", "state-A")
    new = _card("memory-card:new", "state-B")

    path = tmp_path / "slot.json"

    save_memory_card(path, old)

    # Preserve the old recorded block independently of the mutable slot.
    preserved_old = old

    overwrite_memory_card(path, new)

    old_state = build_reconstructed_state(
        "historical-state",
        [preserved_old["card_id"]],
        [_item(preserved_old)],
    )

    current_slot = load_memory_card(path)

    new_state = build_reconstructed_state(
        "current-slot-state",
        [current_slot["card_id"]],
        [_item(current_slot)],
    )

    assert old_state["carried_items"][0]["memory_card"]["card_id"] == (
        "memory-card:old"
    )
    assert (
        old_state["carried_items"][0]["memory_card"]["observation"]["state"][
            "value"
        ]
        == "state-A"
    )

    assert new_state["carried_items"][0]["memory_card"]["card_id"] == (
        "memory-card:new"
    )
    assert (
        new_state["carried_items"][0]["memory_card"]["observation"]["state"][
            "value"
        ]
        == "state-B"
    )


def test_overwrite_does_not_make_old_state_appear_current(tmp_path):
    old = _card("memory-card:old", "state-A")
    new = _card("memory-card:new", "state-B")

    path = tmp_path / "slot.json"

    save_memory_card(path, old)
    preserved_old = old

    overwrite_memory_card(path, new)

    loaded = load_memory_card(path)

    old_state = build_reconstructed_state(
        "old-reconstruction",
        [preserved_old["card_id"]],
        [_item(preserved_old)],
    )

    current_state = build_reconstructed_state(
        "new-reconstruction",
        [loaded["card_id"]],
        [_item(loaded)],
    )

    assert (
        old_state["carried_items"][0]["memory_card"]["observation"]["state"][
            "value"
        ]
        == "state-A"
    )
    assert (
        current_state["carried_items"][0]["memory_card"]["observation"]["state"][
            "value"
        ]
        == "state-B"
    )

    assert old_state["state_hash"] != current_state["state_hash"]


def test_two_slots_can_preserve_different_recorded_states(tmp_path):
    old = _card("memory-card:old", "state-A")
    new = _card("memory-card:new", "state-B")

    slot_a = tmp_path / "slot-a.json"
    slot_b = tmp_path / "slot-b.json"

    save_memory_card(slot_a, old)
    save_memory_card(slot_b, old)

    overwrite_memory_card(slot_a, new)

    preserved = load_memory_card(slot_b)
    replaced = load_memory_card(slot_a)

    preserved_state = build_reconstructed_state(
        "preserved-slot",
        [preserved["card_id"]],
        [_item(preserved)],
    )

    replaced_state = build_reconstructed_state(
        "replaced-slot",
        [replaced["card_id"]],
        [_item(replaced)],
    )

    assert preserved["card_id"] == "memory-card:old"
    assert replaced["card_id"] == "memory-card:new"

    assert (
        preserved_state["carried_items"][0]["memory_card"]["observation"][
            "state"
        ]["value"]
        == "state-A"
    )

    assert (
        replaced_state["carried_items"][0]["memory_card"]["observation"][
            "state"
        ]["value"]
        == "state-B"
    )