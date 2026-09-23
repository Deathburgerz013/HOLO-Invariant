import copy

import pytest

from holosim.memory_card import (
    MEMORY_CARD_TYPE,
    MEMORY_CARD_VERSION,
    MemoryCardError,
    build_memory_card,
    verify_memory_card,
)


def _card():
    return build_memory_card(
        card_id="memory-card-v1",
        observation={
            "claim": "the observed state is different",
            "value": 2,
        },
        source={
            "kind": "test_observer",
            "id": "observer-1",
        },
        observed_at="2026-09-22T00:00:00+00:00",
    )


def test_memory_card_builds_and_verifies():
    card = _card()

    assert verify_memory_card(card) is True
    assert card["type"] == MEMORY_CARD_TYPE
    assert card["version"] == MEMORY_CARD_VERSION


def test_memory_card_is_deterministic():
    first = _card()
    second = _card()

    assert first == second


def test_memory_card_contains_hash_bound_observation():
    card = _card()

    assert isinstance(card["observation_hash"], str)
    assert len(card["observation_hash"]) == 64
    assert isinstance(card["card_hash"], str)
    assert len(card["card_hash"]) == 64


def test_tampered_observation_fails_closed():
    card = _card()
    tampered = copy.deepcopy(card)
    tampered["observation"]["value"] = 999

    with pytest.raises(MemoryCardError):
        verify_memory_card(tampered)


def test_tampered_observation_hash_fails_closed():
    card = _card()
    tampered = copy.deepcopy(card)
    tampered["observation_hash"] = "a" * 64

    with pytest.raises(MemoryCardError):
        verify_memory_card(tampered)


def test_tampered_card_hash_fails_closed():
    card = _card()
    tampered = copy.deepcopy(card)
    tampered["status"] = "CORRECTED"

    with pytest.raises(MemoryCardError):
        verify_memory_card(tampered)


def test_memory_card_cannot_gain_authority():
    card = _card()

    tampered = copy.deepcopy(card)
    tampered["accepted"] = True

    with pytest.raises(MemoryCardError):
        verify_memory_card(tampered)

    tampered = copy.deepcopy(card)
    tampered["write_authority"] = "WRITE"

    with pytest.raises(MemoryCardError):
        verify_memory_card(tampered)

    tampered = copy.deepcopy(card)
    tampered["execution_authority"] = "EXECUTE"

    with pytest.raises(MemoryCardError):
        verify_memory_card(tampered)


def test_memory_card_preserves_corrections_and_reobservations():
    card = build_memory_card(
        card_id="memory-card-history-v1",
        observation={"value": 1},
        source={"kind": "test_observer", "id": "observer-1"},
        observed_at="2026-09-22T00:00:00+00:00",
        corrections=[
            {
                "correction_id": "correction-1",
                "reason": "later evidence contradicted the interpretation",
            }
        ],
        reobservations=[
            {
                "reobservation_id": "reobservation-1",
                "observation_hash": "b" * 64,
            }
        ],
    )

    assert verify_memory_card(card) is True
    assert card["observation"] == {"value": 1}
    assert card["corrections"][0]["correction_id"] == "correction-1"
    assert card["reobservations"][0]["reobservation_id"] == "reobservation-1"


def test_memory_card_rejects_unknown_fields():
    card = _card()
    tampered = copy.deepcopy(card)
    tampered["unexpected"] = "not part of the contract"

    with pytest.raises(MemoryCardError):
        verify_memory_card(tampered)