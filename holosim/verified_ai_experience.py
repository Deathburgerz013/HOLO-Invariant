"""Bounded, evidence-relative comparison of recorded model task attempts.

This module never executes a model, authenticates a transport, or claims learning.
An independent runner must capture requests/responses and correction provenance.
"""
from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping

PHASES = ("baseline", "immediate_treatment", "cold_start_control", "cold_start_treatment")
EXPOSED = {"baseline": False, "immediate_treatment": True,
           "cold_start_control": False, "cold_start_treatment": True}
MAX_TASKS = 64
MAX_RAW_BYTES = 65536


class ExperienceEvidenceError(ValueError):
    """The experimental record cannot support a comparison."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(_exact(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(_exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _plain(value, fields, what):
    if type(value) is not dict or set(value) != set(fields):
        raise ExperienceEvidenceError(f"{what}: invalid fields")


def _identifier(value, what):
    if type(value) is not str or not value or len(value) > 128:
        raise ExperienceEvidenceError(f"{what}: invalid identifier")


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ExperienceEvidenceError('duplicate JSON key')
        result[key] = value
    return result


def _raw_json(encoded, what):
    if type(encoded) is not str:
        raise ExperienceEvidenceError(f"{what}: missing encoded bytes")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_RAW_BYTES:
            raise ExperienceEvidenceError(f"{what}: exceeds byte limit")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        _canonical(value)
        return value
    except ExperienceEvidenceError:
        raise
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExperienceEvidenceError(f"{what}: invalid captured JSON") from exc


def evaluate_experience(contract: Mapping, attempts: list[dict]) -> dict:
    """Recalculate outcomes from exact captured JSON, without trusting pass flags.

    Contract schema: {type, version, model_id, correction_id, tasks}.
    Each task: {slot, phase, task_id, prompt, expected}. A slot occurs once
    per phase. Each attempt: {task_id, model_id, correction_exposed,
    correction_id, request_bytes_b64, response_bytes_b64}.
    Captured request: {model, prompt}; response: {model, output, error}.
    A non-null error is a failed attempt, not missing evidence.
    """
    _plain(contract, {"type", "version", "model_id", "correction_id", "tasks"}, "contract")
    if contract["type"] != "verified_ai_experience_contract" or type(contract["version"]) is not int or contract["version"] != 1:
        raise ExperienceEvidenceError("unsupported contract")
    _identifier(contract["model_id"], "model_id")
    _identifier(contract["correction_id"], "correction_id")
    tasks = contract["tasks"]
    if type(tasks) is not list or not (4 <= len(tasks) <= MAX_TASKS):
        raise ExperienceEvidenceError("invalid task count")
    task_by_id = {}
    slot_phases = {}
    for task in tasks:
        _plain(task, {"slot", "phase", "task_id", "prompt", "expected"}, "task")
        for field in ("slot", "task_id"):
            _identifier(task[field], field)
        if task["phase"] not in PHASES:
            raise ExperienceEvidenceError("unknown phase")
        if type(task["prompt"]) is not str or not task["prompt"] or len(task["prompt"].encode()) > MAX_RAW_BYTES:
            raise ExperienceEvidenceError("invalid prompt")
        try:
            _canonical(task["expected"])
        except (TypeError, ValueError) as exc:
            raise ExperienceEvidenceError("invalid expected answer") from exc
        if task["task_id"] in task_by_id or task["phase"] in slot_phases.setdefault(task["slot"], set()):
            raise ExperienceEvidenceError("duplicate task or slot/phase")
        task_by_id[task["task_id"]] = task
        slot_phases[task["slot"]].add(task["phase"])
    slot_reference = {}
    for task in tasks:
        signature = _canonical([task["prompt"], task["expected"]])
        slot = task["slot"]
        if slot in slot_reference and slot_reference[slot] != signature:
            raise ExperienceEvidenceError("slot: mismatched prompt or expected answer")
        slot_reference[slot] = signature
    if any(phases != set(PHASES) for phases in slot_phases.values()):
        raise ExperienceEvidenceError("incomplete phase coverage")
    if type(attempts) is not list or len(attempts) != len(tasks):
        raise ExperienceEvidenceError("missing or extra attempts")
    seen = set()
    outcomes = {}
    for attempt in attempts:
        _plain(attempt, {"task_id", "model_id", "correction_exposed", "correction_id",
                         "request_bytes_b64", "response_bytes_b64"}, "attempt")
        task_id = attempt["task_id"]
        if type(task_id) is not str or task_id not in task_by_id or task_id in seen:
            raise ExperienceEvidenceError("unknown or repeated attempt")
        seen.add(task_id)
        task = task_by_id[task_id]
        exposed = EXPOSED[task["phase"]]
        if (attempt["model_id"] != contract["model_id"]
                or type(attempt["correction_exposed"]) is not bool
                or attempt["correction_exposed"] is not exposed
                or attempt["correction_id"] != (contract["correction_id"] if exposed else None)):
            raise ExperienceEvidenceError("model or correction declaration mismatch")
        request = _raw_json(attempt["request_bytes_b64"], "request")
        response = _raw_json(attempt["response_bytes_b64"], "response")
        _plain(request, {"model", "prompt"}, "captured request")
        _plain(response, {"model", "output", "error"}, "captured response")
        if request != {"model": contract["model_id"], "prompt": task["prompt"]}:
            raise ExperienceEvidenceError("captured request differs from contract")
        if response["model"] != contract["model_id"]:
            raise ExperienceEvidenceError("captured response model differs")
        if response["error"] is not None and (type(response["error"]) is not str or not response["error"]):
            raise ExperienceEvidenceError("invalid error field")
        passed = response["error"] is None and _exact(response["output"], task["expected"])
        outcomes[task_id] = {"passed": passed, "error": response["error"] is not None,
                             "request_sha256": hashlib.sha256(base64.b64decode(attempt["request_bytes_b64"])).hexdigest(),
                             "response_sha256": hashlib.sha256(base64.b64decode(attempt["response_bytes_b64"])).hexdigest()}
    phase_counts = {phase: {"passed": 0, "total": 0, "errors": 0} for phase in PHASES}
    by_slot = {}
    for task in tasks:
        result = outcomes[task["task_id"]]
        counts = phase_counts[task["phase"]]
        counts["total"] += 1
        counts["passed"] += int(result["passed"])
        counts["errors"] += int(result["error"])
        by_slot.setdefault(task["slot"], {})[task["phase"]] = result["passed"]
    changes = {"newly_solved": 0, "preserved": 0, "regressed": 0, "unresolved": 0}
    for slot in by_slot.values():
        before, after = slot["baseline"], slot["cold_start_treatment"]
        key = "preserved" if before and after else "regressed" if before else "newly_solved" if after else "unresolved"
        changes[key] += 1
    treatment_gain = phase_counts["cold_start_treatment"]["passed"] - phase_counts["baseline"]["passed"]
    control_gain = phase_counts["cold_start_control"]["passed"] - phase_counts["baseline"]["passed"]
    body = {
        "type": "verified_ai_experience_comparison", "version": 1,
        "contract_hash": _digest(contract), "attempts_hash": _digest(attempts),
        "outcomes": outcomes, "phase_counts": phase_counts, "changes": changes,
        "treatment_gain": treatment_gain, "control_gain": control_gain,
        "difference_in_gains": treatment_gain - control_gain,
        "status": "EVIDENCE_RELATIVE_COMPARISON_ONLY",
        "interpretation_notice": "Recorded-byte consistency only; no independently authenticated model execution, correction provenance, causal learning, or retention claim.",
        "truth_claimed": False, "accepted": False,
        "write_authority": "NONE", "execution_authority": "NONE",
    }
    return {**body, "result_hash": _digest(body)}


def verify_experience_comparison(contract: Mapping, attempts: list[dict], comparison: Mapping) -> bool:
    """Recompute every field, including the comparison hash."""
    if type(comparison) is not dict or comparison != evaluate_experience(contract, attempts):
        raise ExperienceEvidenceError("comparison differs from source evidence")
    return True
