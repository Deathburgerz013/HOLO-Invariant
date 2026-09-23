from holosim.memory_card import build_memory_card
from holosim.memory_card_generations import save_memory_card_generation, load_memory_card_generation, list_memory_card_generations


def _card(domain, state):
    return build_memory_card(
        card_id=f'{domain}:{state}',
        observation={'domain': domain, 'state': state},
        source={'kind': domain},
        observed_at='2026-09-23T00:00:00+00:00',
    )


def test_ai_and_game_states_share_generation_history(tmp_path):
    path = tmp_path / 'slot.json'
    ai = _card('ai', 'checkpoint-A')
    game = _card('game', 'checkpoint-A')

    save_memory_card_generation(path, ai, max_generations=4)
    save_memory_card_generation(path, game, max_generations=4)

    generations = list_memory_card_generations(path)

    assert [item['generation'] for item in generations] == [1, 2]
    assert generations[0]['observation']['domain'] == 'ai'
    assert generations[1]['observation']['domain'] == 'game'


def test_generation_reconstruction_preserves_domain_meaning(tmp_path):
    path = tmp_path / 'slot.json'
    ai = _card('ai', 'checkpoint-A')
    game = _card('game', 'checkpoint-A')

    save_memory_card_generation(path, ai, max_generations=4)
    save_memory_card_generation(path, game, max_generations=4)

    assert load_memory_card_generation(path, generation=1)['observation'] == ai['observation']
    assert load_memory_card_generation(path, generation=2)['observation'] == game['observation']
