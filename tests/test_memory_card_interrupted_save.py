import os

import pytest

from holosim.memory_card import (
    MemoryCardError,
    build_memory_card,
    load_memory_card,
    save_memory_card,
)


def _card(value):
    return build_memory_card(
        card_id=f"memory-card:interruption:{value}",
        observation={
            "type": "recorded_state",
            "state": {
                "value": value,
            },
        },
        source={
            "kind": "interruption-test",
            "source_id": "memory-card",
        },
        observed_at="2026-09-22T20:00:00+00:00",
    )


def test_interrupted_fsync_does_not_promote_failed_save(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "slot.json"

    first = _card("state-A")
    second = _card("state-B")

    save_memory_card(path, first)

    real_fsync = os.fsync

    def fail_fsync(_fd):
        raise RuntimeError("simulated interruption during fsync")

    monkeypatch.setattr(os, "fsync", fail_fsync)

    with pytest.raises(MemoryCardError):
        save_memory_card(path, second)

    monkeypatch.setattr(os, "fsync", real_fsync)

    loaded = load_memory_card(path)

    assert loaded == first
    assert loaded["card_hash"] == first["card_hash"]
    assert loaded["observation"]["state"]["value"] == "state-A"


def test_interrupted_replace_does_not_leave_successful_new_card(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "slot.json"

    first = _card("state-A")
    second = _card("state-B")

    save_memory_card(path, first)

    real_replace = os.replace

    def fail_replace(_src, _dst):
        raise RuntimeError("simulated interruption during replace")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(MemoryCardError):
        save_memory_card(path, second)

    monkeypatch.setattr(os, "replace", real_replace)

    loaded = load_memory_card(path)

    assert loaded == first
    assert loaded["card_hash"] == first["card_hash"]


def test_interrupted_save_does_not_mutate_supplied_card(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "slot.json"

    first = _card("state-A")
    second = _card("state-B")

    save_memory_card(path, first)

    original_second = second.copy()

    def fail_replace(_src, _dst):
        raise RuntimeError("simulated interruption during replace")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(MemoryCardError):
        save_memory_card(path, second)

    assert second == original_second


def test_successful_save_after_interruption_replaces_slot(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "slot.json"

    first = _card("state-A")
    second = _card("state-B")

    save_memory_card(path, first)

    real_replace = os.replace
    interrupted = True

    def fail_once(src, dst):
        nonlocal interrupted

        if interrupted:
            interrupted = False
            raise RuntimeError("simulated interruption")

        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_once)

    with pytest.raises(MemoryCardError):
        save_memory_card(path, second)

    loaded_after_failure = load_memory_card(path)
    assert loaded_after_failure == first

    save_memory_card(path, second)

    loaded_after_retry = load_memory_card(path)

    assert loaded_after_retry == second
    assert loaded_after_retry["card_hash"] != first["card_hash"]