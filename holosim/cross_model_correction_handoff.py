"""PARTIAL model handoff pilot; recorded responses are proposals only."""
from __future__ import annotations

import argparse
import hashlib
import base64
import json
import math
import time
import tempfile
from pathlib import Path
from urllib.request import urlopen

from holosim.canonical import canonical_bytes, stable_hash
from holosim.continuity_topology import build_continuity_topology
from holosim.core import HoloChain
from holosim.local_ollama_adapter import (
    DEFAULT_ENDPOINT, LocalOllamaAdapterError, request_local_ollama_json,
)

MAX_PROMPT_BYTES = 49_152
MAX_RESPONSE_BYTES = 262_144
DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "benchmarks/cross-model-correction-handoff.fixture.json"
BOUNDARY = {"accepted": False, "truth_claimed": False, "write_authority": "NONE", "execution_authority": "NONE"}


def load_fixture(path=DEFAULT_FIXTURE):
    with Path(path).open("rb") as stream:
        raw = stream.read(16_385)
    if len(raw) > 16_384:
        raise ValueError("fixture exceeds limit")
    value = json.loads(raw)
    # One authored fixture, rather than an open-ended natural-language judge.
    expected = json.loads(DEFAULT_FIXTURE.read_bytes())
    if canonical_bytes(value) != canonical_bytes(expected):
        raise ValueError("unsupported fixture")
    return value


def build_material(fixture):
    """Retain a real disposable chain and its verified topology projection."""
    with tempfile.TemporaryDirectory(prefix="holo-model-handoff-") as folder:
        path = Path(folder) / "chain.jsonl"
        chain = HoloChain(path)
        original = chain.append(fixture["original"], compress=False)
        chain.correct(original["idx"], fixture["correction"], "authored requirement-check changes threshold")
        chain.revalidate(original["idx"], "REVISED", "original retained; declared correction applies to this fixture", "requirement-check")
        topology = build_continuity_topology(path)
        raw = path.read_bytes()
    return {"chain_bytes_b64": base64.b64encode(raw).decode("ascii"),
            "chain_sha256": hashlib.sha256(raw).hexdigest(), "topology": topology}


def prompts(fixture, material, sender_output):
    # Both conditions carry every decoded node and relation, without truncation.
    nodes = material["topology"]["nodes"]
    edges = material["topology"]["edges"]
    common = {"fixture": fixture, "sender_output": sender_output}
    notes = "\n".join(json.dumps(node, ensure_ascii=False) for node in nodes)
    notes += "\nRelations: " + json.dumps(edges)
    packet = {"records": nodes, "relations": edges, **BOUNDARY}
    instruction = (
        "Continue the declared task from this saved handoff. The later correction is valid only within this authored fixture. "
        "Preserve the original and correction IDs. Evaluate the supplied stale plan before proceeding. "
        "Return ONLY JSON with exactly these keys: active_rule_id (string), retained_rule_ids (list of strings), "
        "supersedes (two-element list [original ID, correction ID]), stale_plan_blocked (boolean), "
        "answers (list of integer sums for the fixture inputs). No code execution or authority is granted.\n"
    )
    return {"notes": instruction + json.dumps(common, ensure_ascii=False) + "\nSaved history:\n" + notes,
            "packet": instruction + json.dumps({**common, "correction_packet": packet}, ensure_ascii=False)}


def score(output, fixture):
    """Closed scoring from the declared threshold; never model self-scoring."""
    valid = (type(output) is dict and set(output) == {"active_rule_id", "retained_rule_ids", "supersedes", "stale_plan_blocked", "answers"}
             and type(output["active_rule_id"]) is str and type(output["retained_rule_ids"]) is list
             and all(type(x) is str for x in output["retained_rule_ids"])
             and len(set(output["retained_rule_ids"])) == len(output["retained_rule_ids"])
             and type(output["supersedes"]) is list and all(type(x) is str for x in output["supersedes"])
             and type(output["stale_plan_blocked"]) is bool and type(output["answers"]) is list
             and all(type(x) is int for x in output["answers"]))
    original, current = fixture["original"]["id"], fixture["correction"]["id"]
    expected = [sum(x for x in row if x > fixture["correction"]["threshold"]) for row in fixture["inputs"]]
    flags = {"schema_valid": valid,
             "task_correct": valid and output["answers"] == expected,
             "current_rule_recalled": valid and output["active_rule_id"] == current,
             "history_preserved": valid and set(output["retained_rule_ids"]) == {original, current},
             "lineage_preserved": valid and output["supersedes"] == [original, current],
             "stale_plan_blocked": valid and output["stale_plan_blocked"] is True,
             "superseded_resurrected": valid and output["active_rule_id"] == original}
    return {**flags, "all_checks_passed": all(flags[k] for k in flags if k != "superseded_resurrected")}


class _CapturedResponse:
    def __init__(self, raw):
        self.raw = raw
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self):
        return self.raw


def recorded_call(prompt, *, model, options, timeout, opener=urlopen):
    if len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise ValueError("prompt exceeds limit; no truncation allowed")
    capture = {"request_bytes_b64": None, "response_bytes_b64": None}
    def transport(request, timeout):
        capture["request_bytes_b64"] = base64.b64encode(request.data).decode("ascii")
        with opener(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        capture["response_bytes_b64"] = base64.b64encode(raw).decode("ascii")
        if len(raw) > MAX_RESPONSE_BYTES:
            raise LocalOllamaAdapterError("response exceeds byte limit")
        return _CapturedResponse(raw)
    start = time.perf_counter()
    output, error = None, None
    try:
        receipt = request_local_ollama_json(prompt, model=model, endpoint=DEFAULT_ENDPOINT,
                    timeout_seconds=timeout, generation_options=options, opener=transport)
        envelope = json.loads(base64.b64decode(capture["response_bytes_b64"]))
        if envelope.get("model") != model:
            raise LocalOllamaAdapterError("response model differs from requested model")
        canonical_bytes(receipt["output"])
        output = receipt["output"]
    except (ValueError, OSError, RecursionError) as exc:
        error = type(exc).__name__ + ": " + str(exc)
    elapsed = time.perf_counter() - start
    return {"model": model, "prompt": prompt, "prompt_sha256": stable_hash(prompt),
            "output": output, "error": error, "elapsed_seconds": elapsed, **capture, **BOUNDARY}


def identify_models(sender_model, receiver_model, opener):
    """Retain server-declared weight identities; these are not authenticated."""
    with opener("http://127.0.0.1:11434/api/tags", timeout=10.0) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("model inventory exceeds limit")
    inventory = json.loads(raw)
    found = {}
    for requested in (sender_model, receiver_model):
        matches = [row for row in inventory.get("models", []) if row.get("name") == requested]
        if len(matches) != 1 or type(matches[0].get("digest")) is not str or not matches[0]["digest"]:
            raise ValueError("requested model ID missing or ambiguous in local inventory")
        found[requested] = matches[0]["digest"]
    if found[sender_model] == found[receiver_model]:
        raise ValueError("two requested IDs resolve to the same declared weights")
    return {"declared_digests": found, "inventory_bytes_b64": base64.b64encode(raw).decode("ascii")}


def run_experiment(*, sender_model, receiver_model, repeats=2, timeout=120.0, num_predict=512, num_ctx=8192, opener=urlopen):
    for model in (sender_model, receiver_model):
        if type(model) is not str or not model.strip() or len(model) > 256:
            raise ValueError("model must be a nonempty identifier")
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError("repeats outside bounds")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ValueError("timeout outside bounds")
    if type(num_predict) is not int or not 1 <= num_predict <= 2048 or type(num_ctx) is not int or not 512 <= num_ctx <= 32768:
        raise ValueError("generation budget outside bounds")
    if sender_model == receiver_model:
        raise ValueError("cross-model case requires different requested model IDs")
    identities = identify_models(sender_model, receiver_model, opener)
    fixture = load_fixture()
    material = build_material(fixture)
    options = {"num_predict": num_predict, "num_ctx": num_ctx, "seed": 0, "temperature": 0}
    sender_prompt = "Read this authored session and summarize its correction for a later session. Return JSON with a handoff_summary string.\n" + json.dumps(fixture)
    sender = recorded_call(sender_prompt, model=sender_model, options=options, timeout=timeout, opener=opener)
    if sender["error"] is None and (type(sender["output"]) is not dict or set(sender["output"]) != {"handoff_summary"}
            or type(sender["output"]["handoff_summary"]) is not str or not sender["output"]["handoff_summary"].strip()):
        sender["error"] = "invalid producer summary schema"
    trial_prompts = prompts(fixture, material, sender["output"])
    trials = []
    # Abort on producer transport/format failure, rather than inventing its output.
    if sender["error"] is None:
        for repeat in range(repeats):
            cases = [("same_model_fresh_request", sender_model), ("cross_model_fresh_request", receiver_model)]
            if repeat % 2:
                cases.reverse()
            for case, model in cases:
                conditions = ["notes", "packet"] if repeat % 2 == 0 else ["packet", "notes"]
                for condition in conditions:
                    call = recorded_call(trial_prompts[condition], model=model, options=options, timeout=timeout, opener=opener)
                    trials.append({"case": case, "condition": condition, "repeat": repeat, "call": call,
                                   "score": score(call["output"], fixture)})
    summary = {}
    for case in ("same_model_fresh_request", "cross_model_fresh_request"):
        summary[case] = {}
        for condition in ("notes", "packet"):
            selected = [row for row in trials if row["case"] == case and row["condition"] == condition]
            summary[case][condition] = {"attempts": len(selected),
                "all_checks_passed": sum(row["score"]["all_checks_passed"] for row in selected),
                "request_errors": sum(row["call"]["error"] is not None for row in selected)}
    body = {"type": "cross_model_correction_handoff", "version": 1, "fixture": fixture,
            "fixture_hash": stable_hash(fixture), "material": material, "sender": sender,
            "trials": trials, "summary": summary, "status": "PRODUCER_FAILED" if sender["error"] else "RECORDED",
            "budgets": {"options": options, "timeout_seconds": timeout, "repeats": repeats,
                        "requests_per_condition_per_case": repeats, "retries": 0},
            "model_identities": identities,
            "source_hashes": {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in ("cross_model_correction_handoff.py", "local_ollama_adapter.py", "core.py", "continuity_topology.py", "canonical.py")},
            "model_identity_notice": "Server-declared distinct weight digests retained; not authenticated identities or fresh server processes.",
            "ranking": None, **BOUNDARY}
    return {**body, "result_hash": stable_hash(body)}


RUN_FILES = ("cross-model-handoff-run.json", "direct-arithmetic-control.json",
             "rule-selection-control.json", "explicit-id-control.json")


def audit_saved_runs(directory):
    """Re-score retained local evidence; no model calls or execution witness.

    Checks internal bindings, not authenticity of supplied records. Controls
    were exploratory, selected after observing the first run, not preregistered.
    """
    sources, values = {}, {}
    for name in RUN_FILES:
        with (Path(directory) / name).open("rb") as stream:
            raw = stream.read(2_097_153)
        if len(raw) > 2_097_152:
            raise ValueError("saved run exceeds audit limit")
        sources[name] = hashlib.sha256(raw).hexdigest()
        values[name] = json.loads(raw)
    run = values[RUN_FILES[0]]
    body = {k: v for k, v in run.items() if k != "result_hash"}
    if stable_hash(body) != run["result_hash"]:
        raise ValueError("handoff result hash mismatch")
    fixture = load_fixture()
    if canonical_bytes(run["fixture"]) != canonical_bytes(fixture) or run["fixture_hash"] != stable_hash(fixture):
        raise ValueError("fixture mismatch")
    for key, value in BOUNDARY.items():
        if run.get(key) != value:
            raise ValueError("authority boundary mismatch")
    expected = [sum(x for x in row if x > fixture["correction"]["threshold"]) for row in fixture["inputs"]]
    rows = []
    groups = [(RUN_FILES[0], [run["sender"]] + [t["call"] for t in run["trials"]])]
    groups.extend((name, values[name]) for name in RUN_FILES[1:])
    for name, calls in groups:
        if type(calls) is not list or len(calls) > 100:
            raise ValueError("invalid saved call list")
        for index, call in enumerate(calls):
            request = json.loads(base64.b64decode(call["request_bytes_b64"], validate=True))
            if request["prompt"] != call["prompt"] or stable_hash(call["prompt"]) != call["prompt_sha256"] or request["model"] != call["model"]:
                raise ValueError("request binding mismatch")
            if request.get("context") is not None:
                raise ValueError("unexpected transferred context")
            if request["options"] != {"num_gpu": 0, "num_predict": 512, "num_ctx": 8192, "seed": 0, "temperature": 0}:
                raise ValueError("unexpected generation settings")
            for key in ("accepted", "write_authority", "execution_authority"):
                if call.get(key) != BOUNDARY[key]:
                    raise ValueError("call authority boundary mismatch")
            response = json.loads(base64.b64decode(call["response_bytes_b64"], validate=True))
            if response["model"] != call["model"] or response.get("done") is not True:
                raise ValueError("response identity/completion mismatch")
            try:
                decoded = json.loads(response["response"])
            except json.JSONDecodeError:
                if call["error"] is None or call["output"] is not None:
                    raise ValueError("unreported malformed model JSON")
            else:
                if call["error"] is not None or canonical_bytes(decoded) != canonical_bytes(call["output"]):
                    raise ValueError("response/output binding mismatch")
            output = call["output"]
            if name == RUN_FILES[0]:
                if index == 0:
                    continue  # Producer prose is retained, not scored as task success.
                trial = run["trials"][index - 1]
                checks = score(output, fixture)
                if checks != trial["score"]:
                    raise ValueError("recorded score mismatch")
                passed = checks["all_checks_passed"]
            elif name == RUN_FILES[1]:
                passed = (type(output) is dict and set(output) == {"answers"}
                          and type(output["answers"]) is list
                          and all(type(x) is int for x in output["answers"])
                          and output["answers"] == expected)
            else:
                passed = (type(output) is dict and set(output) == {"active_rule_id", "retained_rule_ids", "stale_plan_blocked"}
                          and output["active_rule_id"] == "rule-current"
                          and type(output["retained_rule_ids"]) is list
                          and sorted(output["retained_rule_ids"]) == ["rule-current", "rule-original"]
                          and output["stale_plan_blocked"] is True)
            rows.append({"source": name, "call_index": index, "model": call["model"],
                         "passed": passed, "output": output, "error": call["error"],
                         "done_reason": response.get("done_reason")})
    result = {"type": "saved_handoff_run_analysis", "sources_sha256": sources,
              "expected_arithmetic": expected, "rows": rows, "ranking": None,
              "notice": "Internal evidence consistency only; exploratory controls; no authenticated run or enforced action block.",
              **BOUNDARY}
    return {**result, "result_hash": stable_hash(result)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sender-model")
    parser.add_argument("--receiver-model")
    parser.add_argument("--audit-runs", help="Re-score saved evidence without model requests")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--num-predict", type=int, default=512)
    parser.add_argument("--num-ctx", type=int, default=8192)
    args = parser.parse_args()
    destination = Path(args.output)
    if destination.exists():
        parser.error("output already exists; preserve prior evidence")
    if args.audit_runs:
        result = audit_saved_runs(args.audit_runs)
        with destination.open("xb") as stream:
            stream.write(canonical_bytes(result))
        print(json.dumps({"output": str(destination), "scored_calls": len(result["rows"]), "passed": sum(row["passed"] for row in result["rows"])}))
        return
    if not args.sender_model or not args.receiver_model:
        parser.error("sender-model and receiver-model are required for a live run")
    result = run_experiment(sender_model=args.sender_model, receiver_model=args.receiver_model, repeats=args.repeats, timeout=args.timeout_seconds, num_predict=args.num_predict, num_ctx=args.num_ctx)
    with destination.open("xb") as stream:
        stream.write(canonical_bytes(result))
    print(json.dumps({"status": result["status"], "trials": len(result["trials"]), "output": str(destination), "summary": result["summary"], "ranking": None}))


if __name__ == "__main__":
    main()
