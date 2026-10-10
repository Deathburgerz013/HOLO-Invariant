"""Regression tests for HoloChain diagnostic reconstruction integrity."""

import json

from holosim.core import HoloChain
from holosim.holochain_terminal_tail_diagnosis import (
    diagnose_holochain_terminal_tail,
)


def test_hash_valid_but_undecodable_compressed_entry_is_reported(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)
    chain.append({"message": "historical content"})

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
