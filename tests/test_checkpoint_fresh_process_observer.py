"""Fresh-process, source-backed continuity checkpoint verification."""

import json
import subprocess
import sys
from copy import deepcopy

import pytest

from holosim.continuity_checkpoint import (
    _canonical_hash,
    build_continuity_checkpoint,
)
from holosim.core import HoloChain


OBSERVER_SCRIPT = r"""
import json
import sys

from holosim.continuity_checkpoint import (
    verify_continuity_checkpoint_against_chain,
)
from holosim.core import HoloChain

source_path, checkpoint_path = sys.argv[1:3]

with open(checkpoint_path, encoding="utf-8") as stream:
    checkpoint = json.load(stream)

try:
    result = verify_continuity_checkpoint_against_chain(
        checkpoint,
        HoloChain(source_path),
    )
except (ValueError, TypeError) as exc:
    print(json.dumps({"status": "REJECTED", "reason": str(exc)}))
else:
    print(json.dumps({"status": "VERIFIED", "result": result}))
"""


def _run_fresh_observer(source_path, checkpoint_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            OBSERVER_SCRIPT,
            str(source_path),
            str(checkpoint_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.fixture
def retained_source(tmp_path):
    source_path = tmp_path / "chain.jsonl"
    checkpoint_path = tmp_path / "checkpoint.json"

    observer_a = HoloChain(source_path)
    original = observer_a.append({"claim": "Initial observation"})
    observer_a.correct(
        original["idx"],
        {"claim": "Corrected observation"},
        reason="New evidence",
    )

    checkpoint = build_continuity_checkpoint(observer_a)

    checkpoint_path.write_text(
        json.dumps(checkpoint, sort_keys=True),
        encoding="utf-8",
    )

    return source_path, checkpoint_path, checkpoint


def test_fresh_process_verifies_retained_source(retained_source):
    source_path, checkpoint_path, checkpoint = retained_source
    source_before = source_path.read_bytes()

    result = _run_fresh_observer(source_path, checkpoint_path)

    assert result["status"] == "VERIFIED"
    assert result["result"]["source_verified"] is True
    assert (
        result["result"]["checkpoint_hash"]
        == checkpoint["checkpoint_hash"]
    )
    assert source_path.read_bytes() == source_before


def test_fresh_process_rejects_self_consistent_forgery(retained_source):
    source_path, checkpoint_path, checkpoint = retained_source
    source_before = source_path.read_bytes()

    forged = deepcopy(checkpoint)
    forged["claims"][0]["content"] = {"claim": "Forged observation"}
    forged["claims"][0]["content_hash"] = _canonical_hash(
        forged["claims"][0]["content"]
    )
    forged["checkpoint_hash"] = _canonical_hash({
        key: forged[key]
        for key in ("version", "source", "claims")
    })

    checkpoint_path.write_text(
        json.dumps(forged, sort_keys=True),
        encoding="utf-8",
    )

    result = _run_fresh_observer(source_path, checkpoint_path)

    assert result["status"] == "REJECTED"
    assert "does not match verified source chain" in result["reason"]
    assert source_path.read_bytes() == source_before
