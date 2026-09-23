import json

import pytest

from holosim.memory_card import build_memory_card
from holosim.memory_card_generations import (
    MemoryCardGenerationError,
    list_memory_card_generations,
    load_memory_card_generation,
    save_memory_card_generation,
)


def _card(value):
    return build_memory_card(
        card_id=f"generation:{value}",
        observation={
            "type": "recorded_state",
            "state": {"value": value},
        },
        source={
            "kind": "generation-corruption-test",
            "source_id": "memory-card",
        },
        observed_at="2026-09-22T20:00:00+00:00",
    )


def test_corrupted_retained_generation_fails_closed_without_promoting_later_state(
    tmp_path,
):
    path = tmp_path / "slot.json"
    first = _card("state-A")
    second = _card("state-B")
    third = _card("state-C")

    save_memory_card_generation(path, first, max_generations=3)
    save_memory_card_generation(path, second, max_generations=3)
    save_memory_card_generation(path, third, max_generations=3)

    generation_two = path.parent / ".slot.json.generations" / "generation-000002.json"
    raw = generation_two.read_text(encoding="utf-8")
    generation_two.write_text(raw.replace("state-B","state-TAMPERED"),encoding="utf-8")

    with pytest.raises(MemoryCardGenerationError):
        load_memory_card_generation(path,generation=2)

    with pytest.raises(MemoryCardGenerationError):
        list_memory_card_generations(path)

    assert load_memory_card_generation(path,generation=1)["card_hash"]==first["card_hash"]
    assert load_memory_card_generation(path,generation=3)["card_hash"]==third["card_hash"]

    assert not (path.parent / ".slot.json.generations" / "generation-000004.json").exists()


def test_corrupted_generation_is_not_relabeled(tmp_path):
    path = tmp_path / "slot.json"
    for value in ("state-A","state-B","state-C"):
        save_memory_card_generation(path,_card(value),max_generations=3)

    generation_two = path.parent / ".slot.json.generations" / "generation-000002.json"
    object = json.loads(generation_two.read_text(encoding="utf-8"))
    object["card_id"] = "generation:corrupted"
    generation_two.write_text(json.dumps(object,sort_keys=True,indent=2) + "\n",encoding="utf-8")

    with pytest.raises(MemoryCardGenerationError):
        load_memory_card_generation(path,generation=2)

    recovered = load_memory_card_generation(path,generation=1)
    assert recovered["observation"]["state"]["value"] == "state-A"

