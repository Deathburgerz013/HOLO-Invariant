"""Verify agreement between HoloChain diagnostics and replay decoding."""

import json
import zlib

from holosim.core import HoloChain
from holosim.holochain_terminal_tail_diagnosis import (
    diagnose_holochain_terminal_tail,
)
from holosim.replay import MAX_SEARCH_DECODED_BYTES, ReplayEngine, SearchDecodeError


def test_diagnostic_rejects_trailing_compressed_data(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    payload = zlib.compress(b"historical content") + b"TRAILING"
    chain.append(payload.hex())

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["type"] = "compressed"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    assert len(chain.load_and_verify()) == 1

    try:
        ReplayEngine._searchable_content(entry)
    except SearchDecodeError as exc:
        assert "trailing compressed data" in str(exc)
    else:
        raise AssertionError("Replay unexpectedly accepted trailing data")

    receipt = diagnose_holochain_terminal_tail(path)

    assert receipt["status"] == "TERMINAL_INVALID_RECORD"
    assert receipt["failure_kind"] == "INVALID_COMPRESSION"
    assert receipt["complete_entry_count"] == 0
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_diagnostic_rejects_oversized_compressed_content(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    payload = zlib.compress(b"A" * (MAX_SEARCH_DECODED_BYTES + 1))
    chain.append(payload.hex())

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["type"] = "compressed"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    assert len(chain.load_and_verify()) == 1

    receipt = diagnose_holochain_terminal_tail(path)

    assert receipt["status"] == "TERMINAL_INVALID_RECORD"
    assert receipt["failure_kind"] == "INVALID_COMPRESSION"
    assert receipt["complete_entry_count"] == 0
    assert receipt["repair_performed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
