
"""General system lineage recovery after the producing process exits."""

import json
import subprocess
import sys

from holosim.canonical import stable_hash
from tests.test_general_system_lineage_persistence import OBSERVER


PRODUCER = r"""
import json
import sys
from pathlib import Path

from holosim.general_system_lineage import (
    build_general_system_lineage,
    validate_general_system_lineage,
)
from holosim.transition_receipt import atomic_write_json

artifact_path = Path(sys.argv[1])
identity_path = Path(sys.argv[2])

systems = [
    {"system_id": "a", "domain": "software", "label": "Original"},
    {"system_id": "b", "domain": "software", "label": "Successor"},
]

observations = [
    {
        "observation_id": "o1",
        "system_id": "a",
        "source_id": "source-1",
        "boundary": "bounded",
        "evidence_hash": "a" * 64,
        "finding": "original observation",
    }
]

relationships = [
    {
        "relationship_id": "r1",
        "source_system_id": "a",
        "target_system_id": "b",
        "relationship_type": "transition",
        "evidence_observation_ids": ["o1"],
        "status": "OBSERVED",
    }
]

report = build_general_system_lineage(
    systems,
    observations,
    relationships,
    [],
)

assert validate_general_system_lineage(report)

atomic_write_json(artifact_path, report)
identity_path.write_text(report["lineage_hash"], encoding="utf-8")
"""


def run_script(script, *args):
    return subprocess.run(
        [sys.executable, "-c", script, *(str(a) for a in args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )


def produce(tmp_path):
    artifact = tmp_path / "lineage.json"
    identity = tmp_path / "identity.txt"

    result = run_script(PRODUCER, artifact, identity)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert artifact.is_file()
    assert identity.is_file()

    return artifact, identity


def observe(artifact, identity):
    expected_hash = identity.read_text(encoding="utf-8")
    result = run_script(OBSERVER, artifact, expected_hash)

    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_reconstructs_after_producer_process_exits(tmp_path):
    artifact, identity = produce(tmp_path)
    before = artifact.read_bytes()
    expected = identity.read_text(encoding="utf-8")

    result = observe(artifact, identity)

    assert result["status"] == "RECONSTRUCTED"
    assert result["lineage_hash"] == expected
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert artifact.read_bytes() == before


def test_repeated_fresh_observers_agree_after_producer_exits(tmp_path):
    artifact, identity = produce(tmp_path)

    first = observe(artifact, identity)
    second = observe(artifact, identity)

    assert first == second
    assert first["status"] == "RECONSTRUCTED"


def test_rejects_replaced_artifact_after_producer_exits(tmp_path):
    artifact, identity = produce(tmp_path)

    original = json.loads(artifact.read_text(encoding="utf-8"))
    replacement = json.loads(json.dumps(original))

    replacement["systems"][0]["label"] = "Replacement"
    replacement["lineage_hash"] = stable_hash({
        key: value
        for key, value in replacement.items()
        if key != "lineage_hash"
    })

    artifact.write_text(
        json.dumps(replacement, sort_keys=True),
        encoding="utf-8",
    )

    result = observe(artifact, identity)

    assert result["status"] == "REJECTED"
    assert "retained identity mismatch" in result["reason"]


def test_rejects_missing_artifact_after_producer_exits(tmp_path):
    artifact, identity = produce(tmp_path)
    artifact.unlink()

    result = observe(artifact, identity)

    assert result["status"] == "REJECTED"


def test_rejects_missing_retained_identity(tmp_path):
    artifact, identity = produce(tmp_path)
    identity.unlink()

    try:
        observe(artifact, identity)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing retained identity was accepted")
