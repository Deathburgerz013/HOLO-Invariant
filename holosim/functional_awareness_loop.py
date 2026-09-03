"""Functional problem-awareness and bounded adaptation receipts.

The loop makes a goal mismatch available to the next evaluation, measures
whether an observed post-solution state reduced that mismatch, and may emit a
non-executing adaptation proposal.  It does not establish subjective
consciousness, execute a solution, train a model, accept a result, or grant
write or execution authority.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Mapping

from holosim.canonical import stable_hash


RECEIPT_TYPE = "functional_awareness_loop_receipt"
RECEIPT_VERSION = 1
EVIDENCE_STATUSES = {"VERIFIED", "UNVERIFIED", "UNAVAILABLE"}
INTERPRETATION_NOTICE = (
    "Functional awareness means a verified goal mismatch was represented "
    "and affected the next bounded evaluation. It does not establish "
    "subjective consciousness. Adaptation is a proposal only and does not "
    "execute a solution, train a model, accept a result, or grant authority."
)
MAX_JSON_DEPTH = 10
MAX_ITEMS = 10_000
MAX_TEXT_UTF8_BYTES = 16_384

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SOLUTION_FIELDS = {
    "solution_id", "description", "execution_status", "execution_receipt_hash",
}
_ADAPTATION_FIELDS = {"adaptation_id", "statement"}
_RECEIPT_FIELDS = {
    "type", "version", "loop_id", "goal_state_hash", "before_state_hash",
    "after_state_hash", "before_evidence_status", "after_evidence_status",
    "before_mismatch_paths", "after_mismatch_paths", "problem_visible",
    "solution", "effect", "effect_reason", "awareness_carried_forward",
    "adaptation", "adaptation_status", "solution_executed_by_loop",
    "training_applied", "subjective_consciousness_claimed", "accepted",
    "write_authority", "execution_authority", "interpretation_notice",
    "receipt_hash",
}


class FunctionalAwarenessLoopError(ValueError):
    """Raised when awareness-loop input or receipt violates the contract."""


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise FunctionalAwarenessLoopError(f"{label} must be nonempty text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise FunctionalAwarenessLoopError(f"{label} must be valid UTF-8") from exc
    if size > MAX_TEXT_UTF8_BYTES:
        raise FunctionalAwarenessLoopError(f"{label} is too large")
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise FunctionalAwarenessLoopError(f"{label} is invalid")
    return value


def _sha256_or_none(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise FunctionalAwarenessLoopError(f"{label} must be SHA-256 or null")
    return value


def _evidence_status(value: Any, label: str) -> str:
    if type(value) is not str or value not in EVIDENCE_STATUSES:
        raise FunctionalAwarenessLoopError(f"{label} is invalid")
    return value


def _canonical(value: Any, *, label: str) -> Any:
    active: set[int] = set()
    count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_ITEMS:
            raise FunctionalAwarenessLoopError(f"{label} exceeds item limit")
        if depth > MAX_JSON_DEPTH:
            raise FunctionalAwarenessLoopError(f"{label} exceeds maximum depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise FunctionalAwarenessLoopError(f"{label} numbers must be finite")
            return
        if type(item) is str:
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise FunctionalAwarenessLoopError(
                    f"{label} strings must be valid UTF-8"
                ) from exc
            if size > MAX_TEXT_UTF8_BYTES:
                raise FunctionalAwarenessLoopError(f"{label} text is too large")
            return
        if type(item) not in {dict, list}:
            raise FunctionalAwarenessLoopError(
                f"{label} must contain only plain JSON values"
            )
        identity = id(item)
        if identity in active:
            raise FunctionalAwarenessLoopError(f"{label} must not contain cycles")
        active.add(identity)
        try:
            values = item.items() if type(item) is dict else enumerate(item)
            for key, child in values:
                if type(item) is dict and type(key) is not str:
                    raise FunctionalAwarenessLoopError(
                        f"{label} keys must be strings"
                    )
                visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)
    try:
        return json.loads(json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ))
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise FunctionalAwarenessLoopError(f"{label} could not be canonicalized") from exc


def _path_key(parent: str, key: str) -> str:
    return f"{parent}.{key}" if parent else key


def _path_index(parent: str, index: int) -> str:
    return f"{parent}[{index}]" if parent else f"[{index}]"


def _mismatch_paths(goal: Any, observed: Any, path: str = "") -> list[str]:
    if type(goal) is not type(observed):
        return [path or "$root"]
    if type(goal) is dict:
        paths: list[str] = []
        for key in sorted(set(goal) | set(observed)):
            child = _path_key(path, key)
            if key not in goal or key not in observed:
                paths.append(child)
            else:
                paths.extend(_mismatch_paths(goal[key], observed[key], child))
        return paths
    if type(goal) is list:
        paths = []
        length = max(len(goal), len(observed))
        for index in range(length):
            child = _path_index(path, index)
            if index >= len(goal) or index >= len(observed):
                paths.append(child)
            else:
                paths.extend(_mismatch_paths(goal[index], observed[index], child))
        return paths
    return [] if goal == observed else [path or "$root"]


def _normalize_solution(value: Any) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _SOLUTION_FIELDS:
        raise FunctionalAwarenessLoopError("solution fields mismatch")
    status = value["execution_status"]
    if status not in {"VERIFIED_EXECUTED", "NOT_EXECUTED", "UNKNOWN"}:
        raise FunctionalAwarenessLoopError("solution execution_status is invalid")
    receipt_hash = _sha256_or_none(
        value["execution_receipt_hash"], "execution_receipt_hash"
    )
    if (status == "VERIFIED_EXECUTED") != (receipt_hash is not None):
        raise FunctionalAwarenessLoopError(
            "verified execution requires exactly one execution receipt hash"
        )
    return {
        "solution_id": _identifier(value["solution_id"], "solution_id"),
        "description": _text(value["description"], "solution description"),
        "execution_status": status,
        "execution_receipt_hash": receipt_hash,
    }


def _normalize_adaptation(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if type(value) is not dict or set(value) != _ADAPTATION_FIELDS:
        raise FunctionalAwarenessLoopError("adaptation fields mismatch")
    return {
        "adaptation_id": _identifier(value["adaptation_id"], "adaptation_id"),
        "statement": _text(value["statement"], "adaptation statement"),
    }


def _derive_effect(
    before_status: str,
    after_status: str,
    before_paths: list[str],
    after_paths: list[str] | None,
) -> tuple[str, str, bool, str]:
    if before_status != "VERIFIED":
        return "UNKNOWN", "BEFORE_EVIDENCE_NOT_VERIFIED", False, "WITHHELD"
    if not before_paths:
        return "NO_PROBLEM", "GOAL_ALREADY_MATCHED", False, "WITHHELD"
    if after_status != "VERIFIED" or after_paths is None:
        return "UNKNOWN", "AFTER_EVIDENCE_NOT_VERIFIED", True, "WITHHELD"
    before_set, after_set = set(before_paths), set(after_paths)
    if not after_paths:
        return "RESOLVED", "ALL_MISMATCHES_REMOVED", True, "PROPOSED"
    if after_set < before_set:
        return "IMPROVED", "MISMATCH_SET_REDUCED", True, "PROPOSED"
    if after_set == before_set:
        return "UNCHANGED", "MISMATCH_SET_UNCHANGED", True, "WITHHELD"
    if before_set < after_set:
        return "WORSENED", "MISMATCH_SET_EXPANDED", True, "WITHHELD"
    return "CHANGED", "MISMATCH_SET_CHANGED_WITHOUT_SUBSET_GAIN", True, "WITHHELD"


def build_functional_awareness_receipt(
    *,
    loop_id: str,
    goal_state: Any,
    before_state: Any,
    after_state: Any,
    before_evidence_status: str,
    after_evidence_status: str,
    solution: Mapping[str, Any],
    adaptation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Measure whether a verified solution outcome reduced a visible mismatch."""
    goal = _canonical(goal_state, label="goal_state")
    before = _canonical(before_state, label="before_state")
    before_status = _evidence_status(
        before_evidence_status, "before_evidence_status"
    )
    after_status = _evidence_status(after_evidence_status, "after_evidence_status")
    checked_solution = _normalize_solution(dict(solution))
    checked_adaptation = _normalize_adaptation(
        None if adaptation is None else dict(adaptation)
    )
    before_paths = _mismatch_paths(goal, before) if before_status == "VERIFIED" else []
    if after_status == "VERIFIED":
        after = _canonical(after_state, label="after_state")
        after_hash = stable_hash(after)
        after_paths: list[str] | None = _mismatch_paths(goal, after)
    else:
        if after_state is not None:
            raise FunctionalAwarenessLoopError(
                "unverified after_state must be null"
            )
        after_hash = None
        after_paths = None
    effect, reason, carried, adaptation_status = _derive_effect(
        before_status, after_status, before_paths, after_paths
    )
    if (adaptation_status == "PROPOSED") != (checked_adaptation is not None):
        raise FunctionalAwarenessLoopError(
            "adaptation is required exactly when verified mismatch reduction occurs"
        )
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "loop_id": _identifier(loop_id, "loop_id"),
        "goal_state_hash": stable_hash(goal),
        "before_state_hash": stable_hash(before) if before_status == "VERIFIED" else None,
        "after_state_hash": after_hash,
        "before_evidence_status": before_status,
        "after_evidence_status": after_status,
        "before_mismatch_paths": before_paths,
        "after_mismatch_paths": after_paths,
        "problem_visible": before_status == "VERIFIED" and bool(before_paths),
        "solution": checked_solution,
        "effect": effect,
        "effect_reason": reason,
        "awareness_carried_forward": carried,
        "adaptation": checked_adaptation,
        "adaptation_status": adaptation_status,
        "solution_executed_by_loop": False,
        "training_applied": False,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": INTERPRETATION_NOTICE,
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_functional_awareness_receipt(receipt: Mapping[str, Any]) -> bool:
    """Validate closed structure, derived relations, and authority boundaries."""
    if type(receipt) is not dict or set(receipt) != _RECEIPT_FIELDS:
        raise FunctionalAwarenessLoopError("receipt fields mismatch")
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise FunctionalAwarenessLoopError("receipt schema mismatch")
    supplied_hash = _sha256_or_none(receipt["receipt_hash"], "receipt_hash")
    if supplied_hash is None:
        raise FunctionalAwarenessLoopError("receipt_hash cannot be null")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if stable_hash(body) != supplied_hash:
        raise FunctionalAwarenessLoopError("receipt hash mismatch")
    _identifier(receipt["loop_id"], "loop_id")
    if _sha256_or_none(receipt["goal_state_hash"], "goal_state_hash") is None:
        raise FunctionalAwarenessLoopError("goal_state_hash cannot be null")
    before_status = _evidence_status(
        receipt["before_evidence_status"], "before_evidence_status"
    )
    after_status = _evidence_status(
        receipt["after_evidence_status"], "after_evidence_status"
    )
    before_hash = _sha256_or_none(receipt["before_state_hash"], "before_state_hash")
    after_hash = _sha256_or_none(receipt["after_state_hash"], "after_state_hash")
    if (before_status == "VERIFIED") != (before_hash is not None):
        raise FunctionalAwarenessLoopError("before evidence and hash are inconsistent")
    if (after_status == "VERIFIED") != (after_hash is not None):
        raise FunctionalAwarenessLoopError("after evidence and hash are inconsistent")
    before_paths = receipt["before_mismatch_paths"]
    after_paths = receipt["after_mismatch_paths"]
    if type(before_paths) is not list or before_paths != sorted(set(before_paths)):
        raise FunctionalAwarenessLoopError("before mismatch paths are invalid")
    if after_paths is not None and (
        type(after_paths) is not list or after_paths != sorted(set(after_paths))
    ):
        raise FunctionalAwarenessLoopError("after mismatch paths are invalid")
    effect, reason, carried, adaptation_status = _derive_effect(
        before_status, after_status, before_paths, after_paths
    )
    expected_problem = before_status == "VERIFIED" and bool(before_paths)
    if (
        receipt["effect"] != effect
        or receipt["effect_reason"] != reason
        or receipt["awareness_carried_forward"] is not carried
        or receipt["problem_visible"] is not expected_problem
        or receipt["adaptation_status"] != adaptation_status
    ):
        raise FunctionalAwarenessLoopError("derived awareness state is inconsistent")
    _normalize_solution(receipt["solution"])
    checked_adaptation = _normalize_adaptation(receipt["adaptation"])
    if (adaptation_status == "PROPOSED") != (checked_adaptation is not None):
        raise FunctionalAwarenessLoopError("adaptation state is inconsistent")
    fixed = {
        "solution_executed_by_loop": False,
        "training_applied": False,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    if any(receipt[key] != value for key, value in fixed.items()):
        raise FunctionalAwarenessLoopError("receipt grants forbidden claim or authority")
    if receipt["interpretation_notice"] != INTERPRETATION_NOTICE:
        raise FunctionalAwarenessLoopError("interpretation boundary is invalid")
    return True
