"""
Research tests for interrupted persistent-state recovery.

Question:

If persistence is interrupted while a chain entry is being written, can the
system distinguish a verified historical prefix from an incomplete successor?

These tests distinguish an operation failure from persisted-state validity.
A failed fsync does not necessarily mean that bytes already written to the
file are invalid or absent.
"""

from pathlib import Path

import pytest

from holosim.core import HoloChain


def _chain(tmp_path: Path) -> HoloChain:
    return HoloChain(tmp_path / "state.jsonl")


def test_interrupted_fsync_can_leave_a_complete_verified_successor(
    tmp_path, monkeypatch
):
    chain = _chain(tmp_path)

    first = chain.append("state-A")

    def fail_fsync(_fd):
        raise RuntimeError("simulated interruption during fsync")

    monkeypatch.setattr("os.fsync", fail_fsync)

    with pytest.raises(RuntimeError, match="simulated interruption"):
        chain.append("state-B")

    path = tmp_path / "state.jsonl"
    raw_lines = path.read_text(encoding="utf-8").splitlines()

    # The write occurred before fsync failed, so a complete successor may
    # already exist on the filesystem.
    assert len(raw_lines) == 2

    recovered = _chain(tmp_path)

    # A failed fsync does not imply that the already-written record is
    # malformed. If the bytes form a complete valid chain, verification
    # should succeed.
    entries = recovered.load_and_verify()

    assert len(entries) == 2
    assert entries[0]["hash"] == first["hash"]
    assert entries[0]["content"] == "state-A"
    assert entries[1]["content"] == "state-B"
    assert entries[1]["prev_hash"] == first["hash"]


def test_truncated_final_record_is_not_accepted_as_verified_state(tmp_path):
    chain = _chain(tmp_path)

    first = chain.append("state-A")
    second = chain.append("state-B")

    path = tmp_path / "state.jsonl"
    data = path.read_text(encoding="utf-8")

    # Simulate power loss while the final JSON object is being written.
    lines = data.splitlines()
    assert len(lines) == 2

    truncated = lines[0] + "\n" + lines[1][:-8]
    path.write_text(truncated, encoding="utf-8")

    recovered = _chain(tmp_path)

    with pytest.raises(Exception):
        recovered.load_and_verify()

    # The original verified prefix remains independently reconstructable.
    prefix_path = tmp_path / "verified-prefix.jsonl"
    prefix_path.write_text(
        lines[0] + "\n",
        encoding="utf-8",
    )

    prefix = HoloChain(prefix_path)
    entries = prefix.load_and_verify()

    assert len(entries) == 1
    assert entries[0]["hash"] == first["hash"]
    assert entries[0]["content"] == "state-A"
    assert second["hash"] != first["hash"]


def test_interrupted_state_is_never_silently_repaired_as_history(
    tmp_path,
):
    chain = _chain(tmp_path)

    first = chain.append("state-A")
    chain.append("state-B")

    path = tmp_path / "state.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()

    # Simulate a torn final record.
    damaged_final = lines[1][:-8]
    path.write_text(
        lines[0] + "\n" + damaged_final,
        encoding="utf-8",
    )

    recovered = _chain(tmp_path)

    with pytest.raises(Exception):
        recovered.load_and_verify()

    # Recovery does not silently rewrite the damaged file.
    damaged = path.read_text(encoding="utf-8")
    assert damaged == lines[0] + "\n" + damaged_final

    # The verified prefix is still the exact original record.
    prefix_path = tmp_path / "prefix.jsonl"
    prefix_path.write_text(
        lines[0] + "\n",
        encoding="utf-8",
    )

    prefix = HoloChain(prefix_path)
    prefix_entries = prefix.load_and_verify()

    assert prefix_entries[0]["idx"] == 1
    assert prefix_entries[0]["hash"] == first["hash"]
    assert prefix_entries[0]["content"] == "state-A"


def test_successful_append_still_produces_verified_two_entry_chain(tmp_path):
    chain = _chain(tmp_path)

    first = chain.append("state-A")
    second = chain.append("state-B")

    entries = chain.load_and_verify()

    assert len(entries) == 2
    assert entries[0]["hash"] == first["hash"]
    assert entries[1]["hash"] == second["hash"]
    assert entries[1]["prev_hash"] == first["hash"]
    assert entries[0]["content"] == "state-A"
    assert entries[1]["content"] == "state-B"