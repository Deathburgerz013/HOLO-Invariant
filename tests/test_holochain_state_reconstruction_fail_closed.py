"""Regression tests for fail-closed HoloChain state reconstruction."""

import json
import zlib

import pytest

from holosim.core import HoloChain


def test_hash_valid_invalid_compression_cannot_become_state(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    chain.append({"message": "historical content"})

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["type"] = "compressed"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    # Historical hash validity is not proof of reconstructability.
    assert len(chain.load_and_verify()) == 1

    # Reconstruction failure must not be returned as historical state.
    with pytest.raises(ValueError):
        chain.get_state()


def test_valid_compressed_json_reconstructs(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")
    chain.append({"message": "valid history"}, compress=True)

    assert chain.get_state() == [{"message": "valid history"}]


def test_trailing_compressed_data_cannot_become_state(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    payload = zlib.compress(b"historical content") + b"TRAILING"
    chain.append(payload.hex())

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["type"] = "compressed"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    assert len(chain.load_and_verify()) == 1

    with pytest.raises(ValueError):
        chain.get_state()


def test_oversized_compressed_content_cannot_become_state(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    payload = zlib.compress(b"A" * 1_048_577)
    chain.append(payload.hex())

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["type"] = "compressed"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    assert len(chain.load_and_verify()) == 1

    with pytest.raises(ValueError):
        chain.get_state()
