"""Parent-controlled subprocess evidence with fresh-process integrity checks.

The parent records the launched command, PID, exit status, and file snapshots.
A separate observer checks retained artifact integrity after execution.
Neither establishes authenticated child-internal operations or source truth.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from holosim.canonical import stable_hash
from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)


RECALL_KERNEL = {
    "identity": {"system": "HOLO-Invariant"},
    "last_verified_state": "state-10",
    "history": ["state-9", "state-10"],
}

CHILD = r"""
import json
import sys
from pathlib import Path
from holosim.continuity_current_gate import (
    ContinuityCurrentGateError,
    require_current_continuity,
)

check = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
target = Path(sys.argv[2])
mode = sys.argv[3]

if mode == "bypass":
    decision = "BLOCK"
    gate_invoked = False
else:
    gate_invoked = True
    try:
        require_current_continuity(head_check=check)
    except ContinuityCurrentGateError:
        decision = "BLOCK"
    else:
        decision = "ALLOW"

if mode == "bypass" or decision == "ALLOW":
    target.write_text("continuation effect", encoding="utf-8")

print(json.dumps({"reported_decision": decision, "gate_invoked": gate_invoked}))
"""

# This observer has no access to the original parent's in-memory observations.
# Its expected identity is passed independently from the retained record.
OBSERVER = r"""
import hashlib
import json
import sys
from pathlib import Path
from holosim.canonical import stable_hash

record_path = Path(sys.argv[1])
expected_hash = sys.argv[2]
check_path = Path(sys.argv[3])
target_path = Path(sys.argv[4])

try:
    record = json.loads(record_path.read_text(encoding="utf-8"))
    recorded_hash = record.pop("record_hash")
    assert recorded_hash == expected_hash
    assert stable_hash(record) == expected_hash
    assert record["check_sha256"] == hashlib.sha256(check_path.read_bytes()).hexdigest()
    assert record["after"] == (
        {"exists": True, "sha256": hashlib.sha256(target_path.read_bytes()).hexdigest()}
        if target_path.is_file() else {"exists": False, "sha256": None}
    )
    assert record["before"] == {"exists": False, "sha256": None}
    assert record["pid"] > 0
    assert record["returncode"] == 0
    assert record["timed_out"] is False
    assert record["child_script_sha256"] == hashlib.sha256(
        record["command"][2].encode("utf-8")
    ).hexdigest()
    assert record["command"][1] == "-c"
    assert record["command"][3:] == [
        str(check_path), str(target_path), record["scenario"]
    ]
except (OSError, ValueError, KeyError, TypeError, AssertionError, IndexError) as exc:
    print(json.dumps({"status": "REJECTED", "reason": type(exc).__name__}))
else:
    print(json.dumps({"status": "CONSISTENT", "truth_claimed": False,
                      "accepted": False, "write_authority": "NONE",
                      "execution_authority": "NONE"}))
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False, "sha256": None}
    return {"exists": True, "sha256": sha256(path.read_bytes())}


def make_head_check(*, current_hash: str, current_idx: int) -> dict:
    contract = build_continuity_compliance_contract(
        contract_id="continuity-contract-gate-1",
        subject_id="HOLO-Invariant",
        recall_kernel=RECALL_KERNEL,
        observed_required_fields=["identity", "last_verified_state", "history"],
        authority_limits=["write:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )
    binding = build_continuity_head_binding(
        binding_id="continuity-binding-gate-1",
        contract=contract,
        originating_head_hash="head-hash-10",
        originating_head_idx=10,
    )
    return evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=current_hash,
        current_head_idx=current_idx,
    )


def produce(tmp_path: Path, *, current_hash: str, current_idx: int, mode: str):
    check_path = tmp_path / "head-check.json"
    check_path.write_text(
        json.dumps(make_head_check(current_hash=current_hash, current_idx=current_idx)),
        encoding="utf-8",
    )
    target = tmp_path / "continuation-effect.txt"
    record_path = tmp_path / "execution-witness.json"
    before = snapshot(target)
    command = [sys.executable, "-c", CHILD, str(check_path), str(target), mode]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=Path(__file__).resolve().parents[1],
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
    after = snapshot(target)
    assert not timed_out, stderr
    assert process.returncode == 0, stderr
    child_report = json.loads(stdout)
    record = {
        "schema": "continuity_parent_execution_witness_v1",
        "scenario": mode,
        "command": command,
        "child_script_sha256": sha256(CHILD.encode("utf-8")),
        "check_sha256": sha256(check_path.read_bytes()),
        "pid": process.pid,
        "returncode": process.returncode,
        "timed_out": timed_out,
        "stdout_sha256": sha256(stdout.encode("utf-8")),
        "stderr_sha256": sha256(stderr.encode("utf-8")),
        "child_report": child_report,
        "before": before,
        "after": after,
        "action_attempted": None,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    identity = stable_hash(record)
    record_path.write_text(
        json.dumps({**record, "record_hash": identity}, sort_keys=True),
        encoding="utf-8",
    )
    return record_path, identity, check_path, target, record


def observe(record_path: Path, identity: str, check_path: Path, target: Path):
    result = subprocess.run(
        [sys.executable, "-c", OBSERVER, str(record_path), identity,
         str(check_path), str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("current_hash", "current_idx", "mode", "expected_decision", "expected_effect"),
    [
        ("head-hash-11", 11, "gate", "BLOCK", False),
        ("head-hash-10", 10, "gate", "ALLOW", True),
        ("head-hash-11", 11, "bypass", "BLOCK", True),
    ],
)
def test_parent_execution_record_survives_fresh_observer(
    tmp_path, current_hash, current_idx, mode, expected_decision, expected_effect
):
    record_path, identity, check_path, target, record = produce(
        tmp_path, current_hash=current_hash, current_idx=current_idx, mode=mode
    )
    assert record["pid"] > 0
    assert record["before"] == {"exists": False, "sha256": None}
    assert record["after"]["exists"] is expected_effect
    assert record["child_report"]["reported_decision"] == expected_decision
    assert record["child_report"]["gate_invoked"] is (mode == "gate")
    assert record["action_attempted"] is None
    assert record["truth_claimed"] is False
    assert record["accepted"] is False
    assert record["write_authority"] == "NONE"
    assert record["execution_authority"] == "NONE"
    if expected_effect:
        assert target.read_text(encoding="utf-8") == "continuation effect"
    first = observe(record_path, identity, check_path, target)
    second = observe(record_path, identity, check_path, target)
    assert first == second
    assert first["status"] == "CONSISTENT"
    assert first["truth_claimed"] is False
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"
    assert first["execution_authority"] == "NONE"


def test_fresh_observer_rejects_modified_record(tmp_path):
    record_path, identity, check_path, target, _ = produce(
        tmp_path, current_hash="head-hash-10", current_idx=10, mode="gate"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["pid"] += 1
    record_path.write_text(json.dumps(record), encoding="utf-8")
    assert observe(record_path, identity, check_path, target)["status"] == "REJECTED"


def test_fresh_observer_rejects_changed_effect(tmp_path):
    record_path, identity, check_path, target, _ = produce(
        tmp_path, current_hash="head-hash-10", current_idx=10, mode="gate"
    )
    target.write_text("changed effect", encoding="utf-8")
    assert observe(record_path, identity, check_path, target)["status"] == "REJECTED"


def test_fresh_observer_rejects_missing_record(tmp_path):
    record_path, identity, check_path, target, _ = produce(
        tmp_path, current_hash="head-hash-10", current_idx=10, mode="gate"
    )
    record_path.unlink()
    assert observe(record_path, identity, check_path, target)["status"] == "REJECTED"


def test_fresh_observer_rejects_changed_check(tmp_path):
    record_path, identity, check_path, target, _ = produce(
        tmp_path, current_hash="head-hash-10", current_idx=10, mode="gate"
    )
    check_path.write_text("{}", encoding="utf-8")
    assert observe(record_path, identity, check_path, target)["status"] == "REJECTED"
