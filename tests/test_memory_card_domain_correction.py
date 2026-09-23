from copy import deepcopy

from holosim.memory_card import build_memory_card
from holosim.memory_card_generations import (
    load_memory_card_generation,
    save_memory_card_generation,
)


def _card(domain, state):
    return build_memory_card(
        card_id=f"{domain}:{state}",
        observation={"domain": domain, "state": state},
        source={"kind": domain},
        observed_at="2026-09-23T00:00:00+00:00",
    )


def test_correction_history_preserves_ai_and_game_meaning(tmp_path):
    path = tmp_path / "slot.json"

    ai = _card("ai", "checkpoint-A")
    game = _card("game", "checkpoint-A")

    save_memory_card_generation(path, ai, max_generations=4)
    save_memory_card_generation(path, game, max_generations=4)

    ai_original = load_memory_card_generation(path, generation=1)
    game_original = load_memory_card_generation(path, generation=2)

    ai_updated = deepcopy(ai_original)
    game_updated = deepcopy(game_original)

    ai_updated["corrections"] = [
        {
            "type": "correction",
            "correction_id": "ai-correction-1",
            "source_card_hash": ai_original["card_hash"],
            "statement": "AI state requires reobservation.",
        }
    ]

    game_updated["corrections"] = [
        {
            "type": "correction",
            "correction_id": "game-correction-1",
            "source_card_hash": game_original["card_hash"],
            "statement": "Game state requires reobservation.",
        }
    ]

    assert ai_updated["observation"] == ai_original["observation"]
    assert game_updated["observation"] == game_original["observation"]

    assert ai_updated["observation"]["domain"] == "ai"
    assert game_updated["observation"]["domain"] == "game"

    assert (
        ai_updated["corrections"][0]["source_card_hash"]
        == ai_original["card_hash"]
    )
    assert (
        game_updated["corrections"][0]["source_card_hash"]
        == game_original["card_hash"]
    )


def test_correction_history_does_not_grant_authority_across_domains(tmp_path):
    path = tmp_path / "slot.json"

    ai = _card("ai", "checkpoint-A")
    game = _card("game", "checkpoint-A")

    save_memory_card_generation(path, ai, max_generations=4)
    save_memory_card_generation(path, game, max_generations=4)

    ai_updated = load_memory_card_generation(path, generation=1)
    game_updated = load_memory_card_generation(path, generation=2)

    for card, domain in (
        (ai_updated, "ai"),
        (game_updated, "game"),
    ):
        card["corrections"] = [
            {
                "type": "correction",
                "correction_id": f"{domain}-correction-1",
                "source_card_hash": card["card_hash"],
                "statement": "Reobserve.",
            }
        ]

        assert card["accepted"] is False
        assert card["write_authority"] == "NONE"
        assert card["execution_authority"] == "NONE"
        assert card["observation"]["domain"] == domain
