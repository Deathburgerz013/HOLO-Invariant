from copy import deepcopy

import pytest

from holosim.memory_card import (
    MemoryCardError,
    build_memory_card,
    load_memory_card,
    save_memory_card,
    copy_memory_card,
    delete_memory_card,
    overwrite_memory_card,
)


def _card():
    return build_memory_card(
        card_id="memory-card:storage:v1",
        observation={
            "type": "recorded_state",
            "state": {
                "location": "slot-1",
                "value": "state-A",
            },
        },
        source={
            "kind": "test",
            "source_id": "storage-test",
        },
    )


def test_save_and_load_preserve_recorded_state(tmp_path):
    card = _card()
    path = tmp_path / "card.json"

    saved = save_memory_card(path, card)

    assert saved["card_hash"] == card["card_hash"]

    loaded = load_memory_card(path)

    assert loaded == card


def test_copy_preserves_card_identity_and_content(tmp_path):
    card = _card()

    source = tmp_path / "slot-1.json"
    target = tmp_path / "slot-2.json"

    save_memory_card(source, card)
    copied = copy_memory_card(source, target)

    assert copied == card
    assert load_memory_card(target) == card


def test_delete_removes_storage_without_mutating_card(tmp_path):
    card = _card()
    path = tmp_path / "slot-1.json"

    save_memory_card(path, card)

    original = deepcopy(card)
    delete_memory_card(path)

    assert not path.exists()
    assert card == original


def test_overwrite_replaces_active_slot_with_new_card(tmp_path):
    first = _card()

    second = build_memory_card(
        card_id="memory-card:storage:v2",
        observation={
            "type": "recorded_state",
            "state": {
                "location": "slot-1",
                "value": "state-B",
            },
        },
        source={
            "kind": "test",
            "source_id": "storage-test",
        },
    )

    path = tmp_path / "slot-1.json"

    save_memory_card(path, first)
    overwrite_memory_card(path, second)

    loaded = load_memory_card(path)

    assert loaded == second
    assert loaded["card_hash"] == second["card_hash"]
    assert loaded["card_hash"] != first["card_hash"]


def test_load_does_not_turn_recorded_state_into_current_truth(tmp_path):
    card = _card()
    path = tmp_path / "slot-1.json"

    save_memory_card(path, card)

    loaded = load_memory_card(path)

    assert loaded["observation"]["state"]["value"] == "state-A"

    # The card records a state. Loading it does not claim that the state
    # remains current or correct.
    assert "current" not in loaded
    assert "truth" not in loaded
    assert "correct" not in loaded


def test_copy_does_not_create_a_new_state_identity(tmp_path):
    card = _card()

    source = tmp_path / "slot-1.json"
    target = tmp_path / "slot-2.json"

    save_memory_card(source, card)
    copy_memory_card(source, target)

    copied = load_memory_card(target)

    assert copied["card_id"] == card["card_id"]
    assert copied["card_hash"] == card["card_hash"]


def test_overwrite_does_not_mutate_the_supplied_card(tmp_path):
    first = _card()

    second = build_memory_card(
        card_id="memory-card:storage:v2",
        observation={
            "type": "recorded_state",
            "state": {
                "location": "slot-1",
                "value": "state-B",
            },
        },
        source={
            "kind": "test",
            "source_id": "storage-test",
        },
    )

    original_second = deepcopy(second)
    path = tmp_path / "slot-1.json"

    save_memory_card(path, first)
    overwrite_memory_card(path, second)

    assert second == original_second


def test_save_rejects_invalid_memory_card(tmp_path):
    path = tmp_path / "slot-1.json"

    with pytest.raises(MemoryCardError):
        save_memory_card(path, {"not": "a memory card"})


def test_load_rejects_tampered_memory_card(tmp_path):
    card = _card()
    path = tmp_path / "slot-1.json"

    save_memory_card(path, card)

    raw = path.read_text(encoding="utf-8")
    raw = raw.replace("state-A", "state-TAMPERED")
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(MemoryCardError):
        load_memory_card(path)