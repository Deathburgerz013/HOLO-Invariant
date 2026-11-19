"""Fresh-process checks against a separately retained execution-record identity.

The anchor is created from the original parent record, not from the candidate
presented to the observer. This checks substitution relative to the retained
reference, not the authenticity of the original producer or its observations.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from holosim.canonical import stable_hash
from tests.test_continuity_parent_execution_witness import produce


OBSERVER = r"""
import json
import sys
from pathlib import Path

from holosim.canonical import stable_hash

candidate_path = Path(sys.argv[1])
anchor_path = Path(sys.argv[2])


def result(status, reason):
    return {
        "status": status,
        "reason": reason,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


if not anchor_path.is_file():
    print(json.dumps(result("UNVERIFIABLE", "ANCHOR_UNAVAILABLE")))
    sys.exit(0)

try:
    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    if not isinstance(anchor, dict) or set(anchor) != {
        "schema", "record_sha256"
    }:
        raise ValueError("invalid anchor structure")
    if anchor["schema"] != "continuity_independent_anchor_v1":
        raise ValueError("invalid anchor schema")
    expected = anchor["record_sha256"]
    if not isinstance(expected, str) or len(expected) != 64 or any(
        c not in "0123456789abcdef" for c in expected
    ):
        raise ValueError("invalid anchor digest")
except (OSError, ValueError, TypeError, KeyError):
    print(json.dumps(result("UNVERIFIABLE", "ANCHOR_INVALID")))
    sys.exit(0)

try:
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    if not isinstance(candidate, dict):
        raise ValueError("candidate is not an object")
    claimed = candidate.pop("record_hash")
    actual = stable_hash(candidate)
    if not isinstance(claimed, str) or claimed != actual:
        outcome = result("REJECTED", "INTERNAL_IDENTITY_MISMATCH")
    elif actual != expected:
        outcome = result("REJECTED", "INDEPENDENT_ANCHOR_MISMATCH")
    else:
        outcome = result("CONSISTENT", "ANCHOR_MATCH")
except (OSError, ValueError, TypeError, KeyError):
    outcome = result("REJECTED", "CANDIDATE_INVALID_OR_MISSING")

print(json.dumps(outcome, sort_keys=True))
"""


def retain_anchor(anchor_path: Path, original_identity: str) -> None:
    """Retain the original identity outside the candidate record."""
    anchor_path.write_text(
        json.dumps(
            {
                "schema": "continuity_independent_anchor_v1",
                "record_sha256": original_identity,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def observe(candidate_path: Path, anchor_path: Path) -> dict:
    """Read candidate and reference in a fresh process after production."""
    completed = subprocess.run(
        [sys.executable, "-c", OBSERVER, str(candidate_path), str(anchor_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.fixture
def retained_case(tmp_path):
    candidate_path, identity, _, _, _ = produce(
        tmp_path,
        current_hash="head-hash-10",
        current_idx=10,
        mode="gate",
    )
    anchor_path = tmp_path / "independent-anchor.json"
    retain_anchor(anchor_path, identity)
    return candidate_path, anchor_path, identity


def assert_no_promotion(result: dict) -> None:
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_original_matches_separately_retained_reference(retained_case):
    candidate_path, anchor_path, _ = retained_case
    first = observe(candidate_path, anchor_path)
    second = observe(candidate_path, anchor_path)
    assert first == second
    assert first["status"] == "CONSISTENT"
    assert first["reason"] == "ANCHOR_MATCH"
    assert_no_promotion(first)


def test_modified_record_without_rehash_is_rejected(retained_case):
    candidate_path, anchor_path, _ = retained_case
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["pid"] += 1
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    result = observe(candidate_path, anchor_path)
    assert result["status"] == "REJECTED"
    assert result["reason"] == "INTERNAL_IDENTITY_MISMATCH"
    assert_no_promotion(result)


def test_rehashed_substitute_is_rejected_by_independent_reference(retained_case):
    candidate_path, anchor_path, original_identity = retained_case
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate.pop("record_hash")
    candidate["pid"] += 1
    replacement_identity = stable_hash(candidate)
    assert replacement_identity != original_identity
    candidate["record_hash"] = replacement_identity
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    # The replacement is internally valid; the separately retained reference
    # still points to the original and must not be updated from the candidate.
    assert stable_hash({k: v for k, v in candidate.items() if k != "record_hash"}) == replacement_identity
    assert json.loads(anchor_path.read_text(encoding="utf-8"))["record_sha256"] == original_identity
    result = observe(candidate_path, anchor_path)
    assert result["status"] == "REJECTED"
    assert result["reason"] == "INDEPENDENT_ANCHOR_MISMATCH"
    assert_no_promotion(result)


def test_missing_independent_reference_is_unverifiable(retained_case):
    candidate_path, anchor_path, _ = retained_case
    anchor_path.unlink()
    result = observe(candidate_path, anchor_path)
    assert result["status"] == "UNVERIFIABLE"
    assert result["reason"] == "ANCHOR_UNAVAILABLE"
    assert_no_promotion(result)


def test_corrupt_independent_reference_is_unverifiable(retained_case):
    candidate_path, anchor_path, _ = retained_case
    anchor_path.write_text("{}", encoding="utf-8")
    result = observe(candidate_path, anchor_path)
    assert result["status"] == "UNVERIFIABLE"
    assert result["reason"] == "ANCHOR_INVALID"
    assert_no_promotion(result)


def test_missing_candidate_is_rejected_when_reference_exists(retained_case):
    candidate_path, anchor_path, _ = retained_case
    candidate_path.unlink()
    result = observe(candidate_path, anchor_path)
    assert result["status"] == "REJECTED"
    assert result["reason"] == "CANDIDATE_INVALID_OR_MISSING"
    assert_no_promotion(result)
