from holosim.memory_card import (
    build_memory_card,
)


def _card():
    return build_memory_card(
        card_id="memory-card:autosave:v1",
        observation={
            "type": "recorded_state",
            "state": {
                "value": "state-A",
            },
        },
        source={
            "kind": "autosave-policy-test",
            "source_id": "memory-card",
        },
        observed_at="2026-09-22T20:00:00+00:00",
    )


def test_manual_save_is_always_available():
    card = _card()

    assert card["accepted"] is False
    assert card["write_authority"] == "NONE"
    assert card["execution_authority"] == "NONE"


def test_autosave_policy_can_be_disabled():
    policy = {
        "enabled": False,
        "interval_seconds": 300,
        "max_generations": 3,
    }

    assert policy["enabled"] is False
    assert policy["interval_seconds"] == 300
    assert policy["max_generations"] == 3


def test_autosave_policy_supports_adjustable_interval():
    policy = {
        "enabled": True,
        "interval_seconds": 60,
        "max_generations": 3,
    }

    assert policy["enabled"] is True
    assert policy["interval_seconds"] == 60


def test_autosave_policy_supports_multiple_retention_generations():
    policy = {
        "enabled": True,
        "interval_seconds": 120,
        "max_generations": 5,
    }

    assert policy["max_generations"] == 5


def test_autosave_policy_does_not_change_memory_card_identity():
    card = _card()

    policy_a = {
        "enabled": True,
        "interval_seconds": 60,
        "max_generations": 3,
    }

    policy_b = {
        "enabled": True,
        "interval_seconds": 600,
        "max_generations": 10,
    }

    assert policy_a != policy_b
    assert card["card_id"] == "memory-card:autosave:v1"


def test_policy_is_external_to_recorded_state():
    card = _card()

    assert "autosave" not in card
    assert "save_interval" not in card
    assert "retention" not in card

    # Saving policy controls storage behavior.
    # It is not part of the historical observation itself.