import pytest

from holosim.memory_card import (
    MemoryCardError,
    build_memory_card,
    load_memory_card,
    save_memory_card,
)


def _card(value):
    return build_memory_card(
        card_id=f"generation:{value}",
        observation={
            "type": "recorded_state",
            "state": {"value": value},
        },
        source={
            "kind": "generation-test",
            "source_id": "memory-card",
        },
        observed_at="2026-09-22T20:00:00+00:00",
    )


def test_generations_retain_verified_recorded_states(tmp_path):
    path = tmp_path / "slot.json"

    first = _card("state-A")
    second = _card("state-B")
    third = _card("state-C")

    from holosim.memory_card_generations import (
        save_memory_card_generation,
        list_memory_card_generations,
    )

    save_memory_card_generation(path, first, max_generations=3)
    save_memory_card_generation(path, second, max_generations=3)
    save_memory_card_generation(path, third, max_generations=3)

    generations = list_memory_card_generations(path)

    assert len(generations) == 3
    assert [item["card_hash"] for item in generations] == [
        first["card_hash"],
        second["card_hash"],
        third["card_hash"],
    ]


def test_generation_retention_removes_only_oldest_verified_generation(
    tmp_path,
):
    path = tmp_path / "slot.json"

    cards = [_card("state-A"), _card("state-B"), _card("state-C")]

    from holosim.memory_card_generations import (
        save_memory_card_generation,
        list_memory_card_generations,
    )

    for card in cards:
        save_memory_card_generation(
            path,
            card,
            max_generations=2,
        )

    generations = list_memory_card_generations(path)

    assert len(generations) == 2
    assert [item["card_hash"] for item in generations] == [
        cards[1]["card_hash"],
        cards[2]["card_hash"],
    ]


def test_retained_generation_reconstructs_recorded_state(tmp_path):
    path = tmp_path / "slot.json"
    card = _card("state-A")

    from holosim.memory_card_generations import (
        save_memory_card_generation,
        load_memory_card_generation,
    )

    save_memory_card_generation(path, card, max_generations=3)

    loaded = load_memory_card_generation(
        path,
        generation=1,
    )

    assert loaded["observation"]["state"]["value"] == "state-A"
    assert "current" not in loaded
    assert "truth" not in loaded
    assert "correct" not in loaded


def test_interrupted_generation_save_preserves_previous_generation(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "slot.json"

    first = _card("state-A")
    second = _card("state-B")

    from holosim.memory_card_generations import (
        save_memory_card_generation,
        load_memory_card_generation,
    )

    save_memory_card_generation(
        path,
        first,
        max_generations=3,
    )

    def fail_replace(_src, _dst):
        raise RuntimeError("simulated generation interruption")

    monkeypatch.setattr("os.replace", fail_replace)

    with pytest.raises(MemoryCardError):
        save_memory_card_generation(
            path,
            second,
            max_generations=3,
        )

    monkeypatch.undo()

    recovered = load_memory_card_generation(
        path,
        generation=1,
    )

    assert recovered["card_hash"] == first["card_hash"]


def test_failed_generation_is_not_retained(tmp_path, monkeypatch):
    path = tmp_path / "slot.json"

    first = _card("state-A")
    second = _card("state-B")

    from holosim.memory_card_generations import (
        save_memory_card_generation,
        list_memory_card_generations,
    )

    save_memory_card_generation(
        path,
        first,
        max_generations=3,
    )

    def fail_replace(_src, _dst):
        raise RuntimeError("simulated generation interruption")

    monkeypatch.setattr("os.replace", fail_replace)

    with pytest.raises(MemoryCardError):
        save_memory_card_generation(
            path,
            second,
            max_generations=3,
        )

    monkeypatch.undo()

    generations = list_memory_card_generations(path)

    assert len(generations) == 1
    assert generations[0]["card_hash"] == first["card_hash"]


def test_generation_numbers_are_stable_after_retention(tmp_path):
    path = tmp_path / "slot.json"

    cards = [_card("state-A"), _card("state-B"), _card("state-C")]

    from holosim.memory_card_generations import (
        save_memory_card_generation,
        list_memory_card_generations,
    )

    for card in cards:
        save_memory_card_generation(
            path,
            card,
            max_generations=2,
        )

    generations = list_memory_card_generations(path)

    assert [item["generation"] for item in generations] == [2, 3]
    assert [item["card_hash"] for item in generations] == [
        cards[1]["card_hash"],
        cards[2]["card_hash"],
    ]