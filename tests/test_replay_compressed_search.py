import json
import zlib
from argparse import Namespace

import pytest

from holosim.core import HoloChain
from holosim.holo_cli import run_replay_command
from holosim.replay import MAX_SEARCH_DECODED_BYTES, ReplayEngine, SearchDecodeError


def compressed(data, **metadata):
    return {"type": "compressed", "content": zlib.compress(data).hex(), **metadata}


def test_search_recovers_plain_and_compressed_after_restart_without_writes(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(str(path))
    text = "sum positive numbers: café 雪 " * 100
    original = chain.append(text, compress=True)
    plain = chain.append("plain positive record")
    assert original["type"] == "compressed"
    before = path.read_bytes()
    replay = ReplayEngine(path)
    assert replay.search(" POSITIVE ") == [original, plain]
    assert replay.search("雪") == [original]
    assert replay.search("missing") == []
    assert replay.search("positive", limit=1) == [original]
    assert path.read_bytes() == before
    assert replay.verify()["entries"] == 2


@pytest.mark.parametrize("size", [0, -1, 1, True, None])
def test_original_size_is_not_a_byte_limit(size):
    text = "雪 café" * 100
    assert ReplayEngine._searchable_content(compressed(text.encode(), original_size=size)) == text


@pytest.mark.parametrize("size", [MAX_SEARCH_DECODED_BYTES - 1, MAX_SEARCH_DECODED_BYTES])
def test_decoded_byte_cap_boundary(size):
    assert len(ReplayEngine._searchable_content(compressed(b"a" * size))) == size


def test_over_cap_rejected_even_with_zero_declared_size():
    with pytest.raises(SearchDecodeError, match="exceeds limit"):
        ReplayEngine._searchable_content(compressed(b"a" * (MAX_SEARCH_DECODED_BYTES + 1), original_size=0))


@pytest.mark.parametrize("content,reason", [
    ("not hex", "malformed hex"),
    (b"invalid".hex(), "invalid zlib"),
    (zlib.compress(b"abc")[:-1].hex(), "incomplete zlib"),
    ((zlib.compress(b"abc") + b"trailing").hex(), "trailing compressed data"),
    ((zlib.compress(b"abc") + zlib.compress(b"def")).hex(), "trailing compressed data"),
    (zlib.compress(b"\xff").hex(), "invalid utf-8"),
    ("", "incomplete zlib"),
])
def test_decode_errors_are_explicit(content, reason):
    with pytest.raises(SearchDecodeError, match=reason):
        ReplayEngine._searchable_content({"type": "compressed", "content": content})


def test_valid_empty_compressed_stream():
    assert ReplayEngine._searchable_content(compressed(b"")) == ""


def test_later_bad_record_does_not_return_partial_search(monkeypatch, tmp_path):
    replay = ReplayEngine(tmp_path / "chain.jsonl")
    monkeypatch.setattr(replay, "entries", lambda: [compressed(b"positive"), {"type": "compressed", "content": "bad"}])
    with pytest.raises(SearchDecodeError):
        replay.search("positive")


def test_chain_verification_precedes_search(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(str(path)).append("positive")
    record = json.loads(path.read_text())
    record["content"] = "altered positive"
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError):
        ReplayEngine(path).search("positive")


def test_cli_reports_decode_error_and_leaves_chain_unchanged(tmp_path, capsys):
    path = tmp_path / "chain.jsonl"
    entry = HoloChain(str(path)).append("bad hex")
    entry["type"] = "compressed"
    path.write_text(json.dumps(entry) + "\n")
    before = path.read_bytes()
    assert run_replay_command(Namespace(file=str(path), search="positive", limit=20)) == 1
    output = capsys.readouterr().out
    assert "Replay command failed" in output and "malformed hex" in output
    assert path.read_bytes() == before
