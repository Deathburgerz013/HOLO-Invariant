"""Saved evidence checks do not authenticate a run or authorize action."""
import json
import shutil
from pathlib import Path
import pytest
from holosim.cross_model_correction_handoff import audit_saved_runs

RUNS = Path(__file__).resolve().parents[1] / "benchmarks/cross-model-correction-handoff-runs"


def test_retained_results_and_read_only_audit():
    before = {p.name: p.read_bytes() for p in RUNS.iterdir()}
    report = audit_saved_runs(RUNS)
    assert len(report["rows"]) == 20
    assert sum(r["passed"] for r in report["rows"]) == 2
    assert all(r["source"] == "explicit-id-control.json" for r in report["rows"] if r["passed"])
    assert report["expected_arithmetic"] == [3, 4, 0]
    assert report["ranking"] is None
    assert report["accepted"] is False
    assert report["truth_claimed"] is False
    assert report["write_authority"] == report["execution_authority"] == "NONE"
    assert before == {p.name: p.read_bytes() for p in RUNS.iterdir()}


@pytest.mark.parametrize("mutation", ["request", "output", "budget"])
def test_altered_control_bindings_rejected(tmp_path, mutation):
    shutil.copytree(RUNS, tmp_path / "runs")
    p = tmp_path / "runs/explicit-id-control.json"
    rows = json.loads(p.read_bytes())
    if mutation == "request":
        rows[0]["prompt"] += " altered"
    elif mutation == "output":
        rows[0]["output"]["stale_plan_blocked"] = False
    else:
        import base64
        request = json.loads(base64.b64decode(rows[0]["request_bytes_b64"]))
        request["options"]["num_predict"] = 1024
        rows[0]["request_bytes_b64"] = base64.b64encode(json.dumps(request).encode()).decode()
    p.write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        audit_saved_runs(tmp_path / "runs")


def test_changed_handoff_receipt_rejected(tmp_path):
    shutil.copytree(RUNS, tmp_path / "runs")
    p = tmp_path / "runs/cross-model-handoff-run.json"
    d = json.loads(p.read_bytes())
    d["trials"][0]["score"]["all_checks_passed"] = True
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="hash mismatch"):
        audit_saved_runs(tmp_path / "runs")
