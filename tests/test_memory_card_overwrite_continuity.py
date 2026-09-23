from holosim.memory_card import (
    build_memory_card,
    load_memory_card,
    overwrite_memory_card,
    save_memory_card,
)


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
            "kind": "overwrite-continuity-test",
            "source_id": "memory-card",
        },
        observed_at="2026-09-22T20:00:00+00:00",
    )


def test_overwrite_changes_slot_but_does_not_change_old_card():
    old = _card("memory-card:state-A", "state-A")
    new = _card("memory-card:state-B", "state-B")

    slot = tmp_path = None
    del slot

    # This test deliberately keeps the old card in memory while replacing
    # the storage slot with a new card.
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "slot.json"

        save_memory_card(path, old)
        overwrite_memory_card(path, new)

        loaded = load_memory_card(path)

        assert loaded == new
        assert loaded["card_id"] == "memory-card:state-B"
        assert loaded["observation"]["state"]["value"] == "state-B"

        # The previously constructed card remains unchanged.
        assert old["card_id"] == "memory-card:state-A"
        assert old["observation"]["state"]["value"] == "state-A"


def test_overwrite_does_not_rewrite_the_old_card_identity(tmp_path):
    old = _card("memory-card:state-A", "state-A")
    new = _card("memory-card:state-B", "state-B")

    path = tmp_path / "slot.json"

    save_memory_card(path, old)
    old_hash = old["card_hash"]

    overwrite_memory_card(path, new)

    assert old["card_hash"] == old_hash
    assert old["card_hash"] != new["card_hash"]


def test_old_card_can_still_be_reconstructed_after_slot_overwrite(tmp_path):
    old = _card("memory-card:state-A", "state-A")
    new = _card("memory-card:state-B", "state-B")

    path = tmp_path / "slot.json"

    save_memory_card(path, old)

    # Preserve the old card outside the mutable storage slot.
    preserved = old.copy()

    overwrite_memory_card(path, new)

    loaded = load_memory_card(path)

    assert loaded["card_id"] == "memory-card:state-B"
    assert preserved["card_id"] == "memory-card:state-A"
    assert preserved["card_hash"] == old["card_hash"]


def test_overwrite_is_not_a_historical_correction(tmp_path):
    old = _card("memory-card:state-A", "state-A")
    new = _card("memory-card:state-B", "state-B")

    path = tmp_path / "slot.json"

    save_memory_card(path, old)
    overwrite_memory_card(path, new)

    loaded = load_memory_card(path)

    assert loaded["corrections"] == []
    assert loaded["reobservations"] == []

    # Replacement of a storage slot is distinct from recording a correction
    # against the older card.
    assert loaded["card_id"] != old["card_id"]
    assert loaded["card_hash"] != old["card_hash"]


def test_same_card_can_be_saved_to_multiple_slots_before_overwrite(tmp_path):
    card = _card("memory-card:shared", "state-A")

    slot_a = tmp_path / "slot-a.json"
    slot_b = tmp_path / "slot-b.json"

    save_memory_card(slot_a, card)
    save_memory_card(slot_b, card)

    overwrite_memory_card(
        slot_a,
        _card("memory-card:replacement", "state-B"),
    )

    still_preserved = load_memory_card(slot_b)
    replaced = load_memory_card(slot_a)

    assert still_preserved == card
    assert replaced["card_id"] == "memory-card:replacement"
    assert still_preserved["card_hash"] != replaced["card_hash"]