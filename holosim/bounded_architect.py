"""Bounded architecture alternatives for HOLO/Sim.

The architect records candidate structures, interfaces, constraint assessments,
and quality tradeoffs.  It does not select, approve, implement, execute, or
authorize an architecture.
"""

from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import stable_hash


RECEIPT_TYPE = "bounded_architecture_proposal_receipt"
RECEIPT_VERSION = 1
MAX_ITEMS = 1_000
MAX_TEXT_UTF8_BYTES = 16_384
MAX_JSON_DEPTH = 10
CONSTRAINT_STATUSES = {"VERIFIED", "DECLARED", "UNKNOWN"}
ASSESSMENT_STATUSES = {"SATISFIED", "AT_RISK", "UNKNOWN"}
TRADEOFF_EFFECTS = {"BENEFIT", "COST", "NEUTRAL", "UNKNOWN"}
PROPOSAL_STATUS = "ALTERNATIVES_ONLY"

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_CONSTRAINT_FIELDS = {
    "constraint_id", "statement", "status", "evidence_references",
}
_QUALITY_FIELDS = {"quality_id", "scenario"}
_COMPONENT_FIELDS = {
    "component_id", "responsibility", "depends_on_component_ids",
}
_INTERFACE_FIELDS = {
    "interface_id", "source_component_id", "target_component_id", "contract",
}
_ASSESSMENT_FIELDS = {"constraint_id", "status", "rationale"}
_TRADEOFF_FIELDS = {"quality_id", "effect", "rationale"}
_CANDIDATE_FIELDS = {
    "candidate_id", "summary", "components", "interfaces",
    "constraint_assessments", "quality_tradeoffs", "risks",
}
_RECEIPT_FIELDS = {
    "type", "version", "proposal_id", "observed_context",
    "observed_context_hash", "constraints", "quality_goals", "candidates",
    "proposal_status", "selected_candidate_id", "recommended_candidate_id",
    "implemented", "verified", "accepted", "truth_claimed",
    "write_authority", "execution_authority", "selection_authority",
    "interpretation_notice", "receipt_hash",
}


class BoundedArchitectError(ValueError):
    """Raised when architect input or receipt violates the closed contract."""


def _validate_json(value: Any, *, label: str) -> Any:
    active: set[int] = set()
    count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_ITEMS:
            raise BoundedArchitectError(f"{label} exceeds item limit")
        if depth > MAX_JSON_DEPTH:
            raise BoundedArchitectError(f"{label} exceeds maximum depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise BoundedArchitectError(f"{label} numbers must be finite")
            return
        if type(item) is str:
            try:
                encoded = item.encode("utf-8")
            except UnicodeError as exc:
                raise BoundedArchitectError(
                    f"{label} strings must be valid UTF-8"
                ) from exc
            if len(encoded) > MAX_TEXT_UTF8_BYTES:
                raise BoundedArchitectError(f"{label} text is too large")
            return
        if type(item) not in {dict, list}:
            raise BoundedArchitectError(
                f"{label} must contain only plain JSON values"
            )
        identity = id(item)
        if identity in active:
            raise BoundedArchitectError(f"{label} must not contain cycles")
        active.add(identity)
        try:
            values = item.items() if type(item) is dict else enumerate(item)
            for key, child in values:
                if type(item) is dict and type(key) is not str:
                    raise BoundedArchitectError(f"{label} keys must be strings")
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
        raise BoundedArchitectError(f"{label} could not be canonicalized") from exc


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise BoundedArchitectError(f"{label} must be nonempty text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise BoundedArchitectError(f"{label} must be valid UTF-8") from exc
    if size > MAX_TEXT_UTF8_BYTES:
        raise BoundedArchitectError(f"{label} is too large")
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise BoundedArchitectError(f"{label} is invalid")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise BoundedArchitectError(f"{label} must be a sequence")
    if len(value) > MAX_ITEMS:
        raise BoundedArchitectError(f"{label} exceeds item limit")
    return list(value)


def _closed(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise BoundedArchitectError(f"{label} fields mismatch")
    return value


def _normalize_constraints(values: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in _sequence(values, "constraints"):
        item = _closed(raw, _CONSTRAINT_FIELDS, "constraint")
        item_id = _identifier(item["constraint_id"], "constraint_id")
        if item_id in seen:
            raise BoundedArchitectError("constraint_id values must be unique")
        seen.add(item_id)
        status = item["status"]
        if type(status) is not str or status not in CONSTRAINT_STATUSES:
            raise BoundedArchitectError("constraint status is invalid")
        references = sorted(
            _text(value, "evidence reference")
            for value in _sequence(item["evidence_references"], "evidence_references")
        )
        if len(references) != len(set(references)):
            raise BoundedArchitectError("evidence references must be unique")
        if status == "VERIFIED" and not references:
            raise BoundedArchitectError(
                "verified constraint requires evidence references"
            )
        result.append({
            "constraint_id": item_id,
            "statement": _text(item["statement"], "constraint statement"),
            "status": status,
            "evidence_references": references,
        })
    if not result:
        raise BoundedArchitectError("at least one constraint is required")
    return sorted(result, key=lambda item: item["constraint_id"])


def _normalize_quality_goals(values: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in _sequence(values, "quality_goals"):
        item = _closed(raw, _QUALITY_FIELDS, "quality goal")
        item_id = _identifier(item["quality_id"], "quality_id")
        if item_id in seen:
            raise BoundedArchitectError("quality_id values must be unique")
        seen.add(item_id)
        result.append({
            "quality_id": item_id,
            "scenario": _text(item["scenario"], "quality scenario"),
        })
    if not result:
        raise BoundedArchitectError("at least one quality goal is required")
    return sorted(result, key=lambda item: item["quality_id"])


def _assert_acyclic(components: list[dict[str, Any]]) -> None:
    dependencies = {
        item["component_id"]: item["depends_on_component_ids"]
        for item in components
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(component_id: str) -> None:
        if component_id in visiting:
            raise BoundedArchitectError("component dependency cycle detected")
        if component_id in visited:
            return
        visiting.add(component_id)
        for dependency_id in dependencies[component_id]:
            visit(dependency_id)
        visiting.remove(component_id)
        visited.add(component_id)

    for component_id in dependencies:
        visit(component_id)


def _normalize_components(values: Any) -> list[dict[str, Any]]:
    raw_items = _sequence(values, "components")
    ids = {
        _identifier(_closed(item, _COMPONENT_FIELDS, "component")["component_id"],
                    "component_id")
        for item in raw_items
    }
    if len(ids) != len(raw_items):
        raise BoundedArchitectError("component_id values must be unique")
    if not ids:
        raise BoundedArchitectError("each candidate requires components")
    result = []
    for item in raw_items:
        dependencies = sorted(
            _identifier(value, "component dependency id")
            for value in _sequence(
                item["depends_on_component_ids"], "depends_on_component_ids"
            )
        )
        if len(dependencies) != len(set(dependencies)):
            raise BoundedArchitectError("component dependencies must be unique")
        if any(value not in ids for value in dependencies):
            raise BoundedArchitectError("component references unknown dependency")
        if item["component_id"] in dependencies:
            raise BoundedArchitectError("component cannot depend on itself")
        result.append({
            "component_id": item["component_id"],
            "responsibility": _text(item["responsibility"], "responsibility"),
            "depends_on_component_ids": dependencies,
        })
    result.sort(key=lambda item: item["component_id"])
    _assert_acyclic(result)
    return result


def _normalize_interfaces(values: Any, component_ids: set[str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in _sequence(values, "interfaces"):
        item = _closed(raw, _INTERFACE_FIELDS, "interface")
        item_id = _identifier(item["interface_id"], "interface_id")
        if item_id in seen:
            raise BoundedArchitectError("interface_id values must be unique")
        seen.add(item_id)
        source = _identifier(item["source_component_id"], "source_component_id")
        target = _identifier(item["target_component_id"], "target_component_id")
        if source not in component_ids or target not in component_ids:
            raise BoundedArchitectError("interface references unknown component")
        if source == target:
            raise BoundedArchitectError("interface endpoints must differ")
        result.append({
            "interface_id": item_id,
            "source_component_id": source,
            "target_component_id": target,
            "contract": _text(item["contract"], "interface contract"),
        })
    return sorted(result, key=lambda item: item["interface_id"])


def _normalize_assessments(values: Any, expected_ids: set[str]) -> list[dict[str, str]]:
    result = []
    seen: set[str] = set()
    for raw in _sequence(values, "constraint_assessments"):
        item = _closed(raw, _ASSESSMENT_FIELDS, "constraint assessment")
        item_id = _identifier(item["constraint_id"], "constraint_id")
        if item_id in seen or item_id not in expected_ids:
            raise BoundedArchitectError("constraint assessment ids mismatch")
        seen.add(item_id)
        status = item["status"]
        if type(status) is not str or status not in ASSESSMENT_STATUSES:
            raise BoundedArchitectError("constraint assessment status is invalid")
        result.append({
            "constraint_id": item_id,
            "status": status,
            "rationale": _text(item["rationale"], "constraint rationale"),
        })
    if seen != expected_ids:
        raise BoundedArchitectError("each constraint must be assessed exactly once")
    return sorted(result, key=lambda item: item["constraint_id"])


def _normalize_tradeoffs(values: Any, expected_ids: set[str]) -> list[dict[str, str]]:
    result = []
    seen: set[str] = set()
    for raw in _sequence(values, "quality_tradeoffs"):
        item = _closed(raw, _TRADEOFF_FIELDS, "quality tradeoff")
        item_id = _identifier(item["quality_id"], "quality_id")
        if item_id in seen or item_id not in expected_ids:
            raise BoundedArchitectError("quality tradeoff ids mismatch")
        seen.add(item_id)
        effect = item["effect"]
        if type(effect) is not str or effect not in TRADEOFF_EFFECTS:
            raise BoundedArchitectError("quality tradeoff effect is invalid")
        result.append({
            "quality_id": item_id,
            "effect": effect,
            "rationale": _text(item["rationale"], "tradeoff rationale"),
        })
    if seen != expected_ids:
        raise BoundedArchitectError("each quality goal must be assessed exactly once")
    return sorted(result, key=lambda item: item["quality_id"])


def _normalize_candidates(
    values: Any, constraint_ids: set[str], quality_ids: set[str]
) -> list[dict[str, Any]]:
    result = []
    seen: set[str] = set()
    for raw in _sequence(values, "candidates"):
        item = _closed(raw, _CANDIDATE_FIELDS, "candidate")
        candidate_id = _identifier(item["candidate_id"], "candidate_id")
        if candidate_id in seen:
            raise BoundedArchitectError("candidate_id values must be unique")
        seen.add(candidate_id)
        components = _normalize_components(item["components"])
        component_ids = {value["component_id"] for value in components}
        risks = sorted(_text(value, "risk") for value in _sequence(item["risks"], "risks"))
        if len(risks) != len(set(risks)):
            raise BoundedArchitectError("risks must be unique")
        result.append({
            "candidate_id": candidate_id,
            "summary": _text(item["summary"], "candidate summary"),
            "components": components,
            "interfaces": _normalize_interfaces(item["interfaces"], component_ids),
            "constraint_assessments": _normalize_assessments(
                item["constraint_assessments"], constraint_ids
            ),
            "quality_tradeoffs": _normalize_tradeoffs(
                item["quality_tradeoffs"], quality_ids
            ),
            "risks": risks,
        })
    if len(result) < 2:
        raise BoundedArchitectError("at least two architecture candidates are required")
    return sorted(result, key=lambda item: item["candidate_id"])


def build_architecture_proposal_receipt(
    *, proposal_id: str, observed_context: Any,
    constraints: Sequence[Mapping[str, Any]],
    quality_goals: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic, non-authorizing architecture proposal receipt."""
    context = _validate_json(observed_context, label="observed_context")
    normalized_constraints = _normalize_constraints(constraints)
    normalized_goals = _normalize_quality_goals(quality_goals)
    normalized_candidates = _normalize_candidates(
        candidates,
        {item["constraint_id"] for item in normalized_constraints},
        {item["quality_id"] for item in normalized_goals},
    )
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "proposal_id": _identifier(proposal_id, "proposal_id"),
        "observed_context": context,
        "observed_context_hash": stable_hash(context),
        "constraints": normalized_constraints,
        "quality_goals": normalized_goals,
        "candidates": normalized_candidates,
        "proposal_status": PROPOSAL_STATUS,
        "selected_candidate_id": None,
        "recommended_candidate_id": None,
        "implemented": False,
        "verified": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "selection_authority": "NONE",
        "interpretation_notice": (
            "Candidates are inspectable architecture alternatives under declared "
            "constraints and quality scenarios. They are not selections, "
            "recommendations, implementations, verification, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_architecture_proposal_receipt(receipt: Mapping[str, Any]) -> bool:
    """Recompute the closed receipt and reject semantic or hash tampering."""
    if type(receipt) is not dict:
        raise BoundedArchitectError("receipt must be a plain object")
    _validate_json(receipt, label="receipt")
    if set(receipt) != _RECEIPT_FIELDS:
        raise BoundedArchitectError("receipt fields mismatch")
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise BoundedArchitectError("receipt schema mismatch")
    supplied_hash = receipt["receipt_hash"]
    if type(supplied_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", supplied_hash) is None:
        raise BoundedArchitectError("receipt_hash is invalid")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if stable_hash(body) != supplied_hash:
        raise BoundedArchitectError("receipt hash mismatch")
    expected = build_architecture_proposal_receipt(
        proposal_id=receipt["proposal_id"],
        observed_context=receipt["observed_context"],
        constraints=receipt["constraints"],
        quality_goals=receipt["quality_goals"],
        candidates=receipt["candidates"],
    )
    if dict(receipt) != expected:
        raise BoundedArchitectError("receipt is internally inconsistent")
    return True
