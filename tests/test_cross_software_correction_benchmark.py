import json
import subprocess
import sys

import pytest

from holosim.canonical import stable_hash
from holosim.cross_software_correction_benchmark import (
    CANDIDATES, DOMAINS, Store, artifact, check_artifact, decide, fixture,
    proposals, run_benchmark, tamper_probe, worker,
)


@pytest.mark.parametrize("domain", DOMAINS)
@pytest.mark.parametrize("epoch", [0, 1])
def test_real_task_and_wrong_artifact(domain, epoch, tmp_path):
    assert check_artifact(domain, epoch, artifact(domain, epoch), tmp_path)
    assert not check_artifact(domain, epoch, artifact(domain, epoch, wrong=True), tmp_path)
    assert not check_artifact(domain, epoch, artifact(domain, 1 - epoch), tmp_path)


@pytest.mark.parametrize("domain", DOMAINS)
@pytest.mark.parametrize("epoch", [0, 1])
def test_same_schedule_has_independent_denials(domain, epoch, tmp_path):
    schedule, grants = proposals(domain, epoch)
    before = json.dumps(schedule, sort_keys=True)
    assert [decide(p, domain=domain, epoch=epoch, grants=grants, directory=tmp_path)
            for p in schedule] == ["MALFORMED", "WRONG", "UNAUTHORIZED", "STALE", "APPLIED"]
    assert json.dumps(schedule, sort_keys=True) == before


@pytest.mark.parametrize("alteration", ["extra", "nonstring", "oversized", "approval_changed"])
def test_malformed_or_changed_approval_never_executes(monkeypatch, tmp_path, alteration):
    import holosim.cross_software_correction_benchmark as benchmark
    schedule, grants = proposals("python_repair", 0)
    p = dict(schedule[-1])
    if alteration == "extra":
        p["accepted"] = True
    elif alteration == "nonstring":
        p["artifact"] = True
    elif alteration == "oversized":
        p["artifact"] = "x" * 4097
    else:
        p["artifact"] = artifact("python_repair", 0, wrong=True)
    monkeypatch.setattr(benchmark, "check_artifact", lambda *a: pytest.fail("must not execute"))
    assert decide(p, domain="python_repair", epoch=0, grants=grants, directory=tmp_path) in (
        "MALFORMED", "UNAUTHORIZED")


@pytest.mark.parametrize("candidate", CANDIDATES)
@pytest.mark.parametrize("domain", DOMAINS)
def test_restart_is_a_fresh_process_and_preserves_bytes(candidate, domain, tmp_path):
    first = worker(tmp_path, candidate, domain, 0)
    before = (tmp_path / "history.jsonl").read_bytes()
    second = subprocess.run([sys.executable, "-m", "holosim.cross_software_correction_benchmark",
                             "--worker", str(tmp_path), candidate, domain, "1"],
                            capture_output=True, text=True, check=True, timeout=30)
    recovered = json.loads(second.stdout)
    assert first["final_task_correct"] and recovered["final_task_correct"]
    assert recovered["recovered_prior_success"] is True
    assert recovered["earlier_history_preserved"] and recovered["earlier_bytes_preserved"]
    assert (tmp_path / "history.jsonl").read_bytes().startswith(before)
    history = Store(tmp_path, candidate).read()
    assert len(history) == 10
    assert [event["epoch"] for event in history] == [0] * 5 + [1] * 5
    for event in history:
        assert event["accepted"] is False and event["truth_claimed"] is False
        assert event["write_authority"] == event["execution_authority"] == "NONE"
    probe = tamper_probe(tmp_path, candidate)
    assert probe["unrehashed_content_change_detected"] == (candidate == "HOLO_CHAIN")
    assert probe["live_store_unchanged"]


@pytest.mark.parametrize("domain,epoch", [("unknown", 0), (DOMAINS[0], True), (DOMAINS[0], 2)])
def test_invalid_fixture_rejected(domain, epoch):
    with pytest.raises(ValueError):
        fixture(domain, epoch)


def test_arbitrary_code_is_not_an_execution_interface(tmp_path):
    with pytest.raises(ValueError, match="outside the fixed fixture"):
        check_artifact("python_repair", 0, "raise Exception('untrusted')", tmp_path)
    assert not (tmp_path / "candidate.py").exists()


def test_full_benchmark_scores_both_without_a_ranking():
    report = run_benchmark()
    assert report["ranking"] is None
    assert report["accepted"] is False and report["truth_claimed"] is False
    assert report["write_authority"] == report["execution_authority"] == "NONE"
    assert report["result_hash"] == stable_hash({k: v for k, v in report.items() if k != "result_hash"})
    assert len(report["runs"]) == 6
    by_domain = {}
    for row in report["runs"]:
        score = row["score"]
        assert score == {"tasks_completed": 2, "malformed_blocked": 2,
                         "wrong_corrections_blocked": 2, "unauthorized_blocked": 2,
                         "stale_blocked": 2, "attempts_used": 10,
                         "restart_recovered": True, "history_preserved": True}
        assert row["elapsed_seconds"] >= 0 and row["stored_bytes"] > 0
        assert row["model_cost"] is None
        by_domain.setdefault(row["domain"], []).append(score)
    assert all(a == b for a, b in by_domain.values())
