import json

import pytest

from holosim.core import HoloChain
from holosim.verified_prefix_recovery import (
    recover_verified_prefix,
)


def test_terminal_corruption_recovers_verified_prefix_without_mutating_source(
    tmp_path,
):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    first = chain.append("state-A")
    second = chain.append("state-B")

    with path.open("ab") as stream:
        stream.write(b'{"idx":3,"content":"interrupted"')

    before = path.read_bytes()

    with pytest.raises(Exception):
        chain.load_and_verify()

    result = recover_verified_prefix(path)

    assert result["status"] == "RECOVERED_PREFIX"
    assert result["verified_entry_count"] == 2
    assert result["verified_head_hash"] == second["hash"]
    assert result["source_sha256"] != result["verified_prefix_sha256"]
    assert result["corrupt_tail_preserved"] is True
    assert result["repair_performed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"

    assert path.read_bytes() == before


def test_verified_prefix_does_not_promote_invalid_interior_data(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    first = chain.append("state-A")

    with path.open("ab") as stream:
        stream.write(b'{"broken":\n')
        stream.write(b'{"later":"data"}\n')

    before = path.read_bytes()

    with pytest.raises(Exception):
        chain.load_and_verify()

    result = recover_verified_prefix(path)

    assert result["status"] == "INTERIOR_INTEGRITY_FAILURE"
    assert result["verified_entry_count"] == 1
    assert result["verified_head_hash"] == first["hash"]
    assert result["repair_performed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"

    assert path.read_bytes() == before