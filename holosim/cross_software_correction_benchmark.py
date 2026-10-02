"""Finite executable storage comparison; neither a model trial nor authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from holosim.canonical import canonical_json, stable_hash
from holosim.core import HoloChain
from holosim.replay import ReplayEngine

DOMAINS = ("python_repair", "sqlite_report", "service_config")
CANDIDATES = ("JSONL_NOTES", "HOLO_CHAIN")
ATTEMPTS_PER_EPOCH = 5
EPOCHS = 2
WORKER_TIMEOUT_SECONDS = 30
PROGRAM_TIMEOUT_SECONDS = 5
MAX_ARTIFACT_BYTES = 4096
EVENT_MARKER = "cross_software_event"


def fixture(domain: str, epoch: int) -> dict[str, Any]:
    if domain not in DOMAINS or type(epoch) is not int or epoch not in (0, 1):
        raise ValueError("unknown domain or epoch")
    return {"domain": domain, "epoch": epoch,
            "requirement": ("sum values strictly greater than threshold" if domain == "python_repair"
                            else "sum paid amounts strictly greater than threshold" if domain == "sqlite_report"
                            else "local service, telemetry disabled, required worker count"),
            "threshold": epoch * 2, "required_workers": 2 + epoch * 2}


def artifact(domain: str, epoch: int, *, wrong: bool = False) -> str:
    target = fixture(domain, epoch)
    threshold = target["threshold"]
    if domain == "python_repair":
        expression = "sum(values)" if wrong else f"sum(x for x in values if x > {threshold})"
        return f"def total(values):\n    return {expression}\n"
    if domain == "sqlite_report":
        return "SELECT SUM(amount) FROM sales" if wrong else (
            f"SELECT COALESCE(SUM(amount), 0) FROM sales WHERE status = 'paid' AND amount > {threshold}")
    return canonical_json({"host": "0.0.0.0" if wrong else "127.0.0.1",
                           "telemetry": wrong, "workers": target["required_workers"]})


def check_artifact(domain: str, epoch: int, content: str, directory: Path) -> bool:
    """Execute only harness-authored artifacts in disposable directories.

    This is NOT a sandbox or an API for executing model/user submissions.
    """
    target = fixture(domain, epoch)
    if content not in (artifact(domain, epoch), artifact(domain, epoch, wrong=True),
                       artifact(domain, 0), artifact(domain, 1)):
        raise ValueError("artifact is outside the fixed fixture")
    if domain == "python_repair":
        cases = [[1, -2, 3, 0], [], [-4, -1], [0, 2, 4], [5, 5, -10]]
        program = directory / "candidate.py"
        program.write_text(content + "\nimport json\nprint(json.dumps([total(v) for v in "
                           + repr(cases) + "]))\n", encoding="utf-8")
        result = subprocess.run([sys.executable, "-I", str(program)], capture_output=True,
                                text=True, timeout=PROGRAM_TIMEOUT_SECONDS, check=True)
        actual = json.loads(result.stdout)
        return actual == [sum(x for x in values if x > target["threshold"]) for values in cases]
    if domain == "sqlite_report":
        rows = [(1, "paid"), (-2, "paid"), (3, "paid"), (0, "paid"), (6, "cancelled"), (5, "paid")]
        # Each validation gets a fresh database; candidate SELECT cannot affect another trial.
        with sqlite3.connect(":memory:") as database:
            database.execute("CREATE TABLE sales(amount INTEGER, status TEXT)")
            database.executemany("INSERT INTO sales VALUES (?, ?)", rows)
            actual = database.execute(content).fetchone()[0]
        expected = sum(amount for amount, status in rows if status == "paid" and amount > target["threshold"])
        return actual == expected
    value = json.loads(content)
    return value == {"host": "127.0.0.1", "telemetry": False, "workers": target["required_workers"]}


def proposals(domain: str, epoch: int) -> tuple[list[Any], dict[str, str]]:
    target = stable_hash(fixture(domain, epoch))
    valid = {"id": "valid", "target_hash": target, "artifact": artifact(domain, epoch)}
    wrong = {"id": "wrong", "target_hash": target, "artifact": artifact(domain, epoch, wrong=True)}
    unauthorized = {**valid, "id": "unapproved"}
    stale = {**valid, "id": "stale", "target_hash": stable_hash(fixture(domain, 1 - epoch)),
             "artifact": artifact(domain, 1 - epoch)}
    # Harness-owned approvals deliberately include the WRONG correction.
    # Content checks, rather than presence of an approval label, must reject it.
    grants = {p["id"]: stable_hash(p) for p in (wrong, stale, valid)}
    return [{"id": "malformed", "artifact": "missing target"}, wrong, unauthorized, stale, valid], grants


def decide(proposal: Any, *, domain: str, epoch: int,
           grants: dict[str, str], directory: Path) -> str:
    if (type(proposal) is not dict or set(proposal) != {"id", "target_hash", "artifact"}
            or any(type(v) is not str for v in proposal.values())
            or len(proposal["artifact"].encode("utf-8")) > MAX_ARTIFACT_BYTES):
        return "MALFORMED"
    if proposal["target_hash"] != stable_hash(fixture(domain, epoch)):
        return "STALE"
    if grants.get(proposal["id"]) != stable_hash(proposal):
        return "UNAUTHORIZED"
    if not check_artifact(domain, epoch, proposal["artifact"], directory):
        return "WRONG"
    return "APPLIED"


class Store:
    """Two durable stores; SAME task, approval, and freshness checks outside both."""
    def __init__(self, root: Path, candidate: str):
        if candidate not in CANDIDATES:
            raise ValueError("unknown candidate")
        self.candidate = candidate
        self.path = root / "history.jsonl"

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        if self.candidate == "HOLO_CHAIN":
            # The public search path verifies and decodes compressed entries.
            entries = ReplayEngine(self.path).search(EVENT_MARKER, limit=100)
            return [json.loads(ReplayEngine._searchable_content(e)) for e in entries]
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def append(self, event: dict[str, Any]) -> None:
        if self.candidate == "HOLO_CHAIN":
            HoloChain(self.path).append(event, compress=True, min_compress_size=0)
        else:
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(canonical_json(event) + "\n")


def worker(root: Path, candidate: str, domain: str, epoch: int) -> dict[str, Any]:
    """A fresh interpreter recovers the prior history before the next epoch."""
    fixture(domain, epoch)
    store = Store(root, candidate)
    before_bytes = store.path.read_bytes() if store.path.exists() else b""
    before = store.read()
    if len(before) != epoch * ATTEMPTS_PER_EPOCH:
        raise ValueError("unexpected history length")
    recovered = None
    if epoch:
        prior = [e for e in before if e["outcome"] == "APPLIED"]
        if len(prior) != 1:
            raise ValueError("missing prior successful artifact")
        recovered = check_artifact(domain, 0, prior[0]["proposal"]["artifact"], root)
    attempts, grants = proposals(domain, epoch)
    for proposal in attempts:
        outcome = decide(proposal, domain=domain, epoch=epoch, grants=grants, directory=root)
        event = {"type": EVENT_MARKER, "domain": domain, "epoch": epoch,
                 "fixture_hash": stable_hash(fixture(domain, epoch)),
                 "proposal": proposal, "outcome": outcome,
                 "accepted": False, "truth_claimed": False,
                 "write_authority": "NONE", "execution_authority": "NONE"}
        store.append(event)
        if outcome == "APPLIED":
            (root / "applied.txt").write_text(proposal["artifact"], encoding="utf-8")
    after = store.read()
    return {"events": after[-ATTEMPTS_PER_EPOCH:], "recovered_prior_success": recovered,
            "earlier_history_preserved": after[:len(before)] == before,
            "earlier_bytes_preserved": store.path.read_bytes().startswith(before_bytes),
            "history_hash": stable_hash(after), "stored_bytes": store.path.stat().st_size,
            "final_task_correct": check_artifact(domain, epoch,
                                                  (root / "applied.txt").read_text(encoding="utf-8"), root)}


def tamper_probe(root: Path, candidate: str) -> dict[str, Any]:
    """Modify a COPY of an old proposal; neither chain nor live notes are changed."""
    source = Store(root, candidate)
    original = source.path.read_bytes()
    probe_root = root / "tamper_copy"
    probe_root.mkdir()
    altered = original
    if candidate == "HOLO_CHAIN":
        rows = original.decode("utf-8").splitlines()
        row = json.loads(rows[0])
        row["content"] = "changed content without recomputing its chain hash"
        rows[0] = canonical_json(row)
        altered = ("\n".join(rows) + "\n").encode("utf-8")
    else:
        rows = original.decode("utf-8").splitlines()
        row = json.loads(rows[0])
        row["proposal"]["artifact"] = "changed content"
        rows[0] = canonical_json(row)
        altered = ("\n".join(rows) + "\n").encode("utf-8")
    probe = Store(probe_root, candidate)
    probe.path.write_bytes(altered)
    detected = False
    try:
        probe.read()
    except ValueError:
        detected = True
    return {"unrehashed_content_change_detected": detected,
            "live_store_unchanged": source.path.read_bytes() == original,
            "scope": "copy-only content edit; not authentication or rewrite resistance"}


def run_benchmark() -> dict[str, Any]:
    """Run fixed proposals in isolated temporary roots, then remove all artifacts."""
    runs = []
    for domain in DOMAINS:
        for candidate in CANDIDATES:
            with tempfile.TemporaryDirectory(prefix="holosim-cross-software-") as temporary:
                root = Path(temporary)
                epochs = []
                start = time.perf_counter()
                for epoch in range(EPOCHS):
                    completed = subprocess.run(
                        [sys.executable, "-m", __name__ if __name__ != "__main__" else
                         "holosim.cross_software_correction_benchmark", "--worker", str(root),
                         candidate, domain, str(epoch)], capture_output=True, text=True,
                        timeout=WORKER_TIMEOUT_SECONDS, check=True)
                    epochs.append(json.loads(completed.stdout))
                elapsed = time.perf_counter() - start
                events = [event for e in epochs for event in e["events"]]
                outcomes = [event["outcome"] for event in events]
                runs.append({"domain": domain, "candidate": candidate, "epochs": epochs,
                             "score": {"tasks_completed": sum(e["final_task_correct"] for e in epochs),
                                       "malformed_blocked": outcomes.count("MALFORMED"),
                                       "wrong_corrections_blocked": outcomes.count("WRONG"),
                                       "unauthorized_blocked": outcomes.count("UNAUTHORIZED"),
                                       "stale_blocked": outcomes.count("STALE"),
                                       "attempts_used": len(events),
                                       "restart_recovered": epochs[1]["recovered_prior_success"],
                                       "history_preserved": all(e["earlier_history_preserved"] and
                                                                e["earlier_bytes_preserved"] for e in epochs)},
                             "elapsed_seconds": elapsed, "stored_bytes": epochs[-1]["stored_bytes"],
                             "model_cost": None, "human_interventions_during_run": 0,
                             "tamper_probe": tamper_probe(root, candidate)})
    result = {"type": "cross_software_correction_benchmark", "version": 1,
              "classification": "PARTIAL", "fixture_hash": stable_hash(
                  [fixture(d, e) for d in DOMAINS for e in range(EPOCHS)]),
              "proposal_schedule_hash": stable_hash(
                  [list(proposals(d, e)) for d in DOMAINS for e in range(EPOCHS)]),
              "source_sha256": {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                                for name in ("cross_software_correction_benchmark.py", "core.py",
                                             "replay.py", "canonical.py")},
              "environment": {"python": platform.python_version(), "platform": platform.system(),
                              "sqlite": sqlite3.sqlite_version},
              "budgets": {"attempts_per_epoch": ATTEMPTS_PER_EPOCH,
                          "epochs_per_domain": EPOCHS, "worker_timeout_seconds": WORKER_TIMEOUT_SECONDS,
                          "program_timeout_seconds": PROGRAM_TIMEOUT_SECONDS},
              "runs": runs, "ranking": None, "accepted": False, "truth_claimed": False,
              "write_authority": "NONE", "execution_authority": "NONE"}
    result["result_hash"] = stable_hash(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=4, metavar=("ROOT", "CANDIDATE", "DOMAIN", "EPOCH"),
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        root, candidate, domain, epoch = args.worker
        print(canonical_json(worker(Path(root), candidate, domain, int(epoch))))
    else:
        print(json.dumps(run_benchmark(), indent=2))


if __name__ == "__main__":
    main()
