
"""Persisted general-system-lineage reconstruction across process absence."""

import json
import subprocess
import sys
from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.transition_receipt import atomic_write_json

from tests.test_general_system_lineage_fresh_process import make_report


OBSERVER = r"""
import json
import sys
from pathlib import Path

from holosim.general_system_lineage import (
    build_general_system_lineage,
    validate_general_system_lineage,
)

artifact_path = Path(sys.argv[1])
expected_hash = sys.argv[2]

try:
    report = json.loads(artifact_path.read_text(encoding="utf-8"))

    if not validate_general_system_lineage(report):
        raise ValueError("lineage validation failed")

    rebuilt = build_general_system_lineage(
        report["systems"],
        report["observations"],
        report["relationships"],
        report["corrections"],
    )

    if rebuilt != report:
        raise ValueError("reconstruction mismatch")

    if rebuilt["lineage_hash"] != expected_hash:
        raise ValueError("retained identity mismatch")

except (OSError, ValueError, TypeError, KeyError) as exc:
    print(json.dumps({
        "status": "REJECTED",
        "reason": str(exc),
    }))
else:
    print(json.dumps({
        "status": "RECONSTRUCTED",
        "lineage_hash": rebuilt["lineage_hash"],
        "truth_claimed": rebuilt["truth_claimed"],
        "accepted": rebuilt["accepted"],
        "write_authority": rebuilt["write_authority"],
    }))
"""


def observe(path, expected_hash):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            OBSERVER,
            str(path),
            expected_hash,
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def persist(tmp_path):
    report = make_report()
    path = tmp_path / "lineage.json"

    atomic_write_json(path, report)

    return path, report


def test_persisted_lineage_reconstructs_in_fresh_process(tmp_path):
    path, report = persist(tmp_path)
    original_bytes = path.read_bytes()

    result = observe(path, report["lineage_hash"])

    assert result["status"] == "RECONSTRUCTED"
    assert result["lineage_hash"] == report["lineage_hash"]
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"

    assert path.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "mutation",
    [
        "changed_hash",
        "changed_authority",
        "reordered_corrections",
        "invalid_json",
        "missing_artifact",
    ],
)
def test_persisted_lineage_rejects_invalid_artifact(tmp_path, mutation):
    path, report = persist(tmp_path)
    expected_hash = report["lineage_hash"]

    if mutation == "changed_hash":
        report["lineage_hash"] = "0" * 64

    elif mutation == "changed_authority":
        report["write_authority"] = "WRITE"

    elif mutation == "reordered_corrections":
        report["corrections"].reverse()

    elif mutation == "invalid_json":
        path.write_text("{invalid", encoding="utf-8")

    elif mutation == "missing_artifact":
        path.unlink()

    if mutation not in ("invalid_json", "missing_artifact"):
        atomic_write_json(path, report)

    result = observe(path, expected_hash)

    assert result["status"] == "REJECTED"


def test_self_consistent_replacement_rejected_by_retained_identity(tmp_path):
    path, original = persist(tmp_path)
    expected_hash = original["lineage_hash"]

    replacement = deepcopy(original)

    replacement["systems"][0]["label"] = "Replaced system"

    replacement["lineage_hash"] = stable_hash({
        key: value
        for key, value in replacement.items()
        if key != "lineage_hash"
    })

    result_without_anchor = observe(
        path,
        expected_hash,
    )

    assert result_without_anchor["status"] == "RECONSTRUCTED"

    atomic_write_json(path, replacement)

    result = observe(path, expected_hash)

    assert result["status"] == "REJECTED"
    assert "retained identity mismatch" in result["reason"]
