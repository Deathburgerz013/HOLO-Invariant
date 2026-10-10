import json
import zlib

import pytest

from holosim.core import HoloChain


def test_reconstruction_error_identifies_entry_and_derived_action(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    chain.append((zlib.compress(b"history") + b"TRAILING").hex())
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["type"] = "compressed"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    with pytest.raises(ValueError) as failure:
        chain.get_state()

    message = str(failure.value)
    assert f"idx={entry['idx']}" in message
    assert f"hash={entry['hash']}" in message
    assert "trailing compressed data" in message
    assert "inspect compressed payload boundaries" in message.lower()
    assert path.read_text(encoding="utf-8") == json.dumps(entry) + "\n"


@pytest.mark.parametrize(
    ("payload", "reason", "action"),
    [
        ("not-hex", "malformed hex", "inspect stored payload encoding"),
        (b"not-zlib", "invalid zlib", "inspect compression format and payload integrity"),
        (
            zlib.compress(b"A" * 1_048_577),
            "decoded content exceeds limit",
            "inspect the 1 MiB reconstruction boundary",
        ),
        (
            zlib.compress(b"history")[:-2],
            "incomplete zlib stream",
            "inspect possible payload truncation",
        ),
        (
            zlib.compress(b"\xff"),
            "invalid utf-8",
            "inspect decoded text encoding",
        ),
    ],
)
def test_reconstruction_diagnostic_matches_failure(tmp_path, payload, reason, action):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    content = payload if isinstance(payload, str) else payload.hex()
    chain.append(content)

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["type"] = "compressed"
    original = json.dumps(entry) + "\n"
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError) as failure:
        chain.get_state()

    message = str(failure.value)
    assert f"idx={entry['idx']}" in message
    assert f"hash={entry['hash']}" in message
    assert reason in message
    assert action in message
    assert path.read_text(encoding="utf-8") == original
