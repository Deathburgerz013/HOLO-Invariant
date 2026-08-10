"""Evaluate evidence-bound rule applicability without granting authority.

The gate answers whether one intact rule binding applies to one declared
subject in the examined context.  ``APPLICABLE`` is observational only: it
does not permit an effect or establish truth, acceptance, or authorization.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash


RULE_TYPE = "evidence_bound_rule"
EVALUATION_TYPE = "evidence_bound_rule_applicability"
RULE_VERSION = 1

APPLICABLE = "APPLICABLE"
WRONG_SCOPE = "WRONG_SCOPE"
MISSING_BINDING = "MISSING_BINDING"
STALE_LINEAGE = "STALE_LINEAGE"
CONFLICT = "CONFLICT"
UNJUSTIFIED = "UNJUSTIFIED"

RULE_FIELDS = {
    "type",
    "version",
    "rule_id",
    "scope_type",
    "scope_id",
    "source_evidence",
    "source_evidence_hash",
    "parent_rule_id",
    "justification",
    "applicability_conditions",
    "conflict_ids",
    "truth_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "interpretation_notice",
    "rule_hash",
}


class EvidenceBoundRuleError(ValueError):
    """Raised when a rule binding cannot be validated exactly."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise EvidenceBoundRuleError(str(exc)) from exc


def _plain_string_list(value: Sequence[str] | None, field: str) -> list[str]:
    if value is None:
        return []
    if type(value) is not list or any(type(item) is not str for item in value):
        raise EvidenceBoundRuleError(f"{field} must be a list of strings")
    if len(set(value)) != len(value):
        raise EvidenceBoundRuleError(f"{field} must not contain duplicates")
    return list(value)


def _optional_identifier(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value.strip():
        raise EvidenceBoundRuleError(f"{field} must be null or a non-empty string")
    return value


def build_evidence_bound_rule(
    *,
    rule_id: str,
    scope_type: str,
    scope_id: str | None,
    source_evidence: Mapping[str, Any] | None,
    parent_rule_id: str | None,
    justification: str,
    applicability_conditions: Sequence[str],
    conflict_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Bind a rule to its declared scope, evidence, and lineage."""
    if type(rule_id) is not str or not rule_id.strip():
        raise EvidenceBoundRuleError("rule_id must be a non-empty string")
    if scope_type not in {"project", "session", "global"}:
        raise EvidenceBoundRuleError("scope_type is invalid")
    if scope_type == "global":
        if scope_id is not None:
            raise EvidenceBoundRuleError("global scope_id must be null")
    elif type(scope_id) is not str or not scope_id.strip():
        raise EvidenceBoundRuleError(
            "project and session rules require a non-empty scope_id"
        )
    if type(justification) is not str:
        raise EvidenceBoundRuleError("justification must be a string")
    parent = _optional_identifier(parent_rule_id, "parent_rule_id")
    conditions = _plain_string_list(applicability_conditions, "applicability_conditions")
    conflicts = _plain_string_list(
        conflict_ids, "conflict_ids"
    )
    if source_evidence is not None and type(source_evidence) is not dict:
        raise EvidenceBoundRuleError("source_evidence must be a plain dictionary or null")

    evidence = None if source_evidence is None else deepcopy(dict(source_evidence))
    evidence_hash = None if evidence is None else _hash(evidence)
    body = {
        "type": RULE_TYPE,
        "version": RULE_VERSION,
        "rule_id": rule_id,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "source_evidence": evidence,
        "source_evidence_hash": evidence_hash,
        "parent_rule_id": parent,
        "justification": justification,
        "applicability_conditions": conditions,
        "conflict_ids": conflicts,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "This binding records a proposed rule, evidence identity, scope, and "
            "lineage. It does not establish truth, acceptance, authorization, or "
            "permission to produce an effect."
        ),
    }
    return {**body, "rule_hash": _hash(body)}


def validate_evidence_bound_rule(rule: Mapping[str, Any]) -> bool:
    """Regenerate a rule binding and require exact schema and identity."""
    if type(rule) is not dict:
        raise EvidenceBoundRuleError("rule must be a plain dictionary")
    if set(rule) != RULE_FIELDS:
        raise EvidenceBoundRuleError("rule fields do not match the versioned schema")
    if rule.get("type") != RULE_TYPE or rule.get("version") != RULE_VERSION:
        raise EvidenceBoundRuleError("rule type or version is invalid")
    if (
        rule.get("truth_claimed") is not False
        or rule.get("accepted") is not False
        or rule.get("write_authority") != "NONE"
        or rule.get("execution_authority") != "NONE"
    ):
        raise EvidenceBoundRuleError("rule cannot grant authority")
    if type(rule.get("interpretation_notice")) is not str:
        raise EvidenceBoundRuleError("interpretation_notice must be a string")

    try:
        rebuilt = build_evidence_bound_rule(
            rule_id=rule["rule_id"],
            scope_type=rule["scope_type"],
            scope_id=rule["scope_id"],
            source_evidence=rule["source_evidence"],
            parent_rule_id=rule["parent_rule_id"],
            justification=rule["justification"],
            applicability_conditions=rule["applicability_conditions"],
            conflict_ids=rule["conflict_ids"],
        )
    except (KeyError, TypeError) as exc:
        raise EvidenceBoundRuleError("rule binding is malformed") from exc
    if rebuilt.get("source_evidence_hash") != rule.get("source_evidence_hash"):
        raise EvidenceBoundRuleError("evidence binding does not match its source evidence")
    if rebuilt != rule:
        raise EvidenceBoundRuleError("rule does not match its evidence-bound identity")
    return True


def _result(
    *,
    rule: Mapping[str, Any],
    subject_type: str,
    subject_id: str,
    result: str,
    reason: str,
) -> dict[str, Any]:
    body = {
        "type": EVALUATION_TYPE,
        "version": RULE_VERSION,
        "rule_hash": rule["rule_hash"],
        "rule_id": rule["rule_id"],
        "subject_type": subject_type,
        "subject_id": subject_id,
        "result": result,
        "reason": reason,
        "effect_permitted": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Applicability is a bounded observation only and never permits an effect."
        ),
    }
    return {**body, "evaluation_hash": _hash(body)}


def evaluate_rule_applicability(
    *,
    rule: Mapping[str, Any],
    subject_type: str,
    subject_id: str,
    current_rule_id: str | None,
    satisfied_conditions: Sequence[str],
    unresolved_conflict_ids: Sequence[str],
) -> dict[str, Any]:
    """Observe whether an intact rule applies within one declared context."""
    validate_evidence_bound_rule(rule)
    if type(subject_type) is not str or not subject_type.strip():
        raise EvidenceBoundRuleError("subject_type must be a non-empty string")
    if type(subject_id) is not str or not subject_id.strip():
        raise EvidenceBoundRuleError("subject_id must be a non-empty string")
    satisfied = set(_plain_string_list(satisfied_conditions, "satisfied_conditions"))
    unresolved = set(
        _plain_string_list(unresolved_conflict_ids, "unresolved_conflict_ids")
    )

    common = {"rule": rule, "subject_type": subject_type, "subject_id": subject_id}
    if rule["source_evidence"] is None or rule["source_evidence_hash"] is None:
        return _result(
            **common,
            result=MISSING_BINDING,
            reason="No exact source-evidence binding is present.",
        )
    if rule["scope_type"] != "global" and (
        rule["scope_type"] != subject_type or rule["scope_id"] != subject_id
    ):
        return _result(
            **common,
            result=WRONG_SCOPE,
            reason="The rule scope does not match the examined subject.",
        )
    if current_rule_id != rule["rule_id"]:
        return _result(
            **common,
            result=STALE_LINEAGE,
            reason="The examined rule is not the declared current lineage head.",
        )
    if set(rule["conflict_ids"]) & unresolved:
        return _result(
            **common,
            result=CONFLICT,
            reason="At least one bound conflict remains unresolved.",
        )
    if not rule["justification"].strip():
        return _result(
            **common,
            result=UNJUSTIFIED,
            reason="The rule has no explicit justification.",
        )
    missing_conditions = set(rule["applicability_conditions"]) - satisfied
    if missing_conditions:
        return _result(
            **common,
            result=UNJUSTIFIED,
            reason="Not every declared applicability condition is satisfied.",
        )
    return _result(
        **common,
        result=APPLICABLE,
        reason="The bounded evidence, scope, lineage, conflict, and condition checks passed.",
    )