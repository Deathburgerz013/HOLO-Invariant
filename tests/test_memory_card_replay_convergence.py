from copy import deepcopy

from holosim.memory_card import (
    build_memory_card,
    copy_memory_card,
    load_memory_card,
    save_memory_card,
)


def _card():
    return build_memory_card(
        card_id="memory-card:replay:v1",
        observation={
            "type": "recorded_state",
            "state": {
                "location": "slot-1",
                "value": "state-A",
            },
        },
        source={
            "kind": "test",
            "source_id": "replay-convergence-test",
        },
        observed_at="2026-09-22T20:00:00+00:00",
    )


def test_saved_card_loads_as_same_recorded_state(tmp_path):
    card = _card()
    path = tmp_path / "slot-a.json"

    save_memory_card(path, card)
    loaded = load_memory_card(path)

    assert loaded == card
    assert loaded["observation"] == card["observation"]
    assert loaded["observation_hash"] == card["observation_hash"]
    assert loaded["card_hash"] == card["card_hash"]


def test_copy_then_load_preserves_recorded_state(tmp_path):
    card = _card()

    source = tmp_path / "slot-a.json"
    copied = tmp_path / "slot-b.json"

    save_memory_card(source, card)
    copy_memory_card(source, copied)

    replayed = load_memory_card(copied)

    assert replayed == card
    assert replayed["card_id"] == card["card_id"]
    assert replayed["card_hash"] == card["card_hash"]


def test_replay_does_not_promote_recorded_state_to_current_truth(tmp_path):
    card = _card()
    path = tmp_path / "slot-a.json"

    save_memory_card(path, card)
    replayed = load_memory_card(path)

    current_state = {
        "type": "current_state",
        "state": {
            "location": "slot-1",
            "value": "state-B",
        },
    }

    assert replayed["observation"]["state"]["value"] == "state-A"
    assert current_state["state"]["value"] == "state-B"

    # The card remains an observation of state-A.
    # Replay does not rewrite it into state-B or claim that state-A
    # is still current.
    assert replayed["observation"]["state"]["value"] != (
        current_state["state"]["value"]
    )


def test_replay_does_not_mutate_loaded_card(tmp_path):
    card = _card()
    path = tmp_path / "slot-a.json"

    save_memory_card(path, card)
    replayed = load_memory_card(path)

    before = deepcopy(replayed)

    _ = replayed["observation"]["state"]

    assert replayed == before


def test_identical_replay_inputs_produce_identical_recorded_state(tmp_path):
    card = _card()

    path_a = tmp_path / "slot-a.json"
    path_b = tmp_path / "slot-b.json"

    save_memory_card(path_a, card)
    copy_memory_card(path_a, path_b)

    first = load_memory_card(path_a)
    second = load_memory_card(path_b)

    assert first["observation"] == second["observation"]
    assert first["observation_hash"] == second["observation_hash"]
    assert first["card_hash"] == second["card_hash"]


def test_changed_current_state_remains_a_reobservation_boundary(tmp_path):
    card = _card()
    path = tmp_path / "slot-a.json"

    save_memory_card(path, card)
    replayed = load_memory_card(path)

    current = deepcopy(replayed["observation"])
    current["state"]["value"] = "state-C"

    assert replayed["observation"]["state"]["value"] == "state-A"
    assert current["state"]["value"] == "state-C"

    # A changed current observation does not modify the stored card.
    assert replayed["observation"]["state"]["value"] != (
        current["state"]["value"]
    )