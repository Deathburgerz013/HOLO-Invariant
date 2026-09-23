from holosim.memory_card import build_memory_card, verify_memory_card, save_memory_card, load_memory_card


def _cards():
    return [
        build_memory_card(
            card_id='ai:state-001',
            observation={'domain':'ai','context_window':128,'state':'checkpoint-A'},
            source={'kind':'ai-runtime'},
            observed_at='2026-09-23T00:00:00+00:00',
        ),
        build_memory_card(
            card_id='game:state-001',
            observation={'domain':'game','game':'example','slot':1,'player_state':{'level':42},'world_state':{'area':'town'}},
            source={'kind':'emulator'},
            observed_at='2026-09-23T00:00:00+00:00',
        ),
    ]


def test_ai_and_game_states_share_the_same_memory_card_contract():
    for card in _cards():
        assert verify_memory_card(card) is True
        assert card['accepted'] is False
        assert card['write_authority'] == 'NONE'
        assert card['execution_authority'] == 'NONE'
        assert card['observation_hash']
        assert card['card_hash']


def test_domain_meaning_does_not_change_recorded_state_identity():
    ai, game = _cards()
    assert ai['observation']['domain'] == 'ai'
    assert game['observation']['domain'] == 'game'
    assert ai['observation_hash'] != game['observation_hash']
    assert ai['card_hash'] != game['card_hash']


def test_both_domains_round_trip_through_the_same_storage_api(tmp_path):
    for index, card in enumerate(_cards(), start=1):
        path = tmp_path / f'domain-{index}.json'
        save_memory_card(path, card)
        assert load_memory_card(path) == card


def test_domain_payload_is_not_reinterpreted_during_reconstruction(tmp_path):
    ai, game = _cards()
    ai_path = tmp_path / 'ai.json'
    game_path = tmp_path / 'game.json'
    save_memory_card(ai_path, ai)
    save_memory_card(game_path, game)
    assert load_memory_card(ai_path)['observation'] == ai['observation']
    assert load_memory_card(game_path)['observation'] == game['observation']
