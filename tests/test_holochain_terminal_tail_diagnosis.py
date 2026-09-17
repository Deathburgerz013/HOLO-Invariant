import hashlib
import json

import pytest

from holosim.core import HoloChain
from holosim.holochain_terminal_tail_diagnosis import (
    FAILURE_HASH_MISMATCH,
    FAILURE_INVALID_JSON,
    FAILURE_INVALID_UTF8,
    FAILURE_MISSING_FIELD,
    STATUS_CLEAN,
    STATUS_INTERIOR_INTEGRITY_FAILURE,
    STATUS_TERMINAL_INVALID_RECORD,
    diagnose_holochain_terminal_tail,
)


EXPECTED_KEYS = {
    "type",
    "version",
    "source_exists",
    "source_sha256",
    "byte_count",
    "terminal_newline_present",
    "status",
    "complete_entry_count",
    "failure_line",
    "failure_kind",
    "repair_performed",
    "accepted",
    "write_authority",
    "interpretation_notice",
}


def test_missing_chain_is_clean_read_only_observation(tmp_path):
    parent = tmp_path / "absent"
    path = parent / "missing.jsonl"

    result = diagnose_holochain_terminal_tail(path)

    assert set(result) == EXPECTED_KEYS
    assert result["status"] == STATUS_CLEAN
    assert result["source_exists"] is False
    assert result["source_sha256"] == hashlib.sha256(b"").hexdigest()
    assert result["byte_count"] == 0
    assert result["complete_entry_count"] == 0
    assert result["failure_line"] is None
    assert result["failure_kind"] is None
    assert result["repair_performed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert not path.exists()
    assert not parent.exists()


def test_complete_chain_is_clean_and_source_bound(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)
    chain.append("alpha")
    chain.append("beta")
    before = path.read_bytes()

    result = diagnose_holochain_terminal_tail(path)

    assert result["status"] == STATUS_CLEAN
    assert result["source_exists"] is True
    assert result["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert result["byte_count"] == len(before)
    assert result["terminal_newline_present"] is True
    assert result["complete_entry_count"] == 2
    assert path.read_bytes() == before


def test_partial_terminal_json_is_classified_without_repair(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)
    chain.append("alpha")
    with path.open("ab") as stream:
        stream.write(b'{"idx": 2, "content": "interrupted"')
    before = path.read_bytes()

    result = diagnose_holochain_terminal_tail(path)

    assert result["status"] == STATUS_TERMINAL_INVALID_RECORD
    assert result["failure_line"] == 2
    assert result["failure_kind"] == FAILURE_INVALID_JSON
    assert result["complete_entry_count"] == 1
    assert result["terminal_newline_present"] is False
    assert result["repair_performed"] is False
    assert path.read_bytes() == before


def test_invalid_terminal_utf8_is_classified_without_exposing_bytes(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("alpha")
    with path.open("ab") as stream:
        stream.write(b"\xff\xfe")

    result = diagnose_holochain_terminal_tail(path)

    assert result["status"] == STATUS_TERMINAL_INVALID_RECORD
    assert result["failure_kind"] == FAILURE_INVALID_UTF8
    assert result["failure_line"] == 2
    assert result["complete_entry_count"] == 1
    assert "raw_bytes" not in result


def test_invalid_record_before_later_data_is_interior_failure(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("alpha")
    with path.open("ab") as stream:
        stream.write(b'{"broken":\n')
        stream.write(b'{"later": "data"}\n')

    result = diagnose_holochain_terminal_tail(path)

    assert result["status"] == STATUS_INTERIOR_INTEGRITY_FAILURE
    assert result["failure_line"] == 2
    assert result["failure_kind"] == FAILURE_INVALID_JSON
    assert result["complete_entry_count"] == 1


def test_terminal_json_missing_required_field_is_classified(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("alpha")
    with path.open("ab") as stream:
        stream.write(b'{"idx": 2}\n')

    result = diagnose_holochain_terminal_tail(path)

    assert result["status"] == STATUS_TERMINAL_INVALID_RECORD
    assert result["failure_kind"] == FAILURE_MISSING_FIELD
    assert result["failure_line"] == 2


def test_terminal_hash_mismatch_is_not_called_an_interrupted_write(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)
    chain.append("alpha")
    entry = chain.append("beta")
    lines = path.read_text(encoding="utf-8").splitlines()
    damaged = dict(entry)
    damaged["hash"] = "f" * 64
    lines[-1] = json.dumps(damaged)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = diagnose_holochain_terminal_tail(path)

    assert result["status"] == STATUS_TERMINAL_INVALID_RECORD
    assert result["failure_kind"] == FAILURE_HASH_MISMATCH
    assert "does not prove its cause" in result["interpretation_notice"]


def test_diagnosis_does_not_make_malformed_chain_appendable(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)
    chain.append("alpha")
    with path.open("ab") as stream:
        stream.write(b"{")
    before = path.read_bytes()

    result = diagnose_holochain_terminal_tail(path)

    assert result["status"] == STATUS_TERMINAL_INVALID_RECORD
    with pytest.raises(json.JSONDecodeError):
        chain.append("blocked")
    assert path.read_bytes() == before


def test_diagnosis_uses_supplied_genesis_hash(tmp_path):
    path = tmp_path / "chain.jsonl"
    genesis_hash = "a" * 64
    HoloChain(path, genesis_hash=genesis_hash).append("alpha")

    matching = diagnose_holochain_terminal_tail(
        path,
        genesis_hash=genesis_hash,
    )
    mismatching = diagnose_holochain_terminal_tail(path)

    assert matching["status"] == STATUS_CLEAN
    assert mismatching["status"] == STATUS_TERMINAL_INVALID_RECORD
    assert mismatching["failure_kind"] == FAILURE_HASH_MISMATCH
