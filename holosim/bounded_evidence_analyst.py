"""Bounded evidence-to-finding analysis for HOLO/Sim.

The analyst accounts for every supplied evidence item and derives finding
statuses from declared evidence relations.  It does not establish truth,
execute an analytical method, recommend action, accept results, or grant
selection, write, or execution authority.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash


RECEIPT_TYPE = "bounded_evidence_analysis_receipt"
RECEIPT_VERSION = 1
MAX_ITEMS = 10_000
MAX_TEXT_UTF8_BYTES = 16_384
EVIDENCE_AVAILABILITY = {"VERIFIED", "DECLARED", "UNAVAILABLE"}
DISPOSITIONS = {"INCLUDED", "EXCLUDED"}
RELATIONS = {"SUPPORTS", "CONTRADICTS", "NEUTRAL", "UNKNOWN", "NOT_APPLIED"}
FINDING_STATUSES = {"SUPPORTED", "CONTRADICTED", "UNRESOLVED"}

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_METHOD_FIELDS = {"method_id", "method_version", "description"}
_EVIDENCE_FIELDS = {
    "evidence_id", "content_sha256", "source_reference", "availability",
}
_ASSESSMENT_FIELDS = {"evidence_id", "disposition", "relation", "rationale"}
_FINDING_FIELDS = {"finding_id", "statement", "evidence_assessments"}
_RECEIPT_FIELDS = {
    "type", "version", "analysis_id", "scope", "method", "evidence",
    "evidence_set_hash", "findings", "finding_results", "analysis_status",
    "method_executed", "truth_claimed", "recommended_action", "accepted",
    "selection_authority", "write_authority", "execution_authority",
    "interpretation_notice", "receipt_hash",
}


class BoundedEvidenceAnalystError(ValueError):
    """Raised when analyst input or a receipt violates the closed contract."""


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise BoundedEvidenceAnalystError(f"{label} must be nonempty text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise BoundedEvidenceAnalystError(f"{label} must be valid UTF-8") from exc
    if size > MAX_TEXT_UTF8_BYTES:
        raise BoundedEvidenceAnalystError(f"{label} is too large")
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise BoundedEvidenceAnalystError(f"{label} is invalid")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise BoundedEvidenceAnalystError(f"{label} must be a SHA-256 hex digest")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise BoundedEvidenceAnalystError(f"{label} must be a sequence")
    if len(value) > MAX_ITEMS:
        raise BoundedEvidenceAnalystError(f"{label} exceeds item limit")
    return list(value)


def _closed(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise BoundedEvidenceAnalystError(f"{label} fields mismatch")
    return value


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise BoundedEvidenceAnalystError(str(exc)) from exc


def _normalize_method(value: Any) -> dict[str, str]:
    item = _closed(value, _METHOD_FIELDS, "method")
    return {
        "method_id": _identifier(item["method_id"], "method_id"),
        "method_version": _identifier(item["method_version"], "method_version"),
        "description": _text(item["description"], "method description"),
    }


def _normalize_evidence(values: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in _sequence(values, "evidence"):
        item = _closed(raw, _EVIDENCE_FIELDS, "evidence item")
        evidence_id = _identifier(item["evidence_id"], "evidence_id")
        if evidence_id in seen:
            raise BoundedEvidenceAnalystError("evidence_id values must be unique")
        seen.add(evidence_id)
        availability = item["availability"]
        if type(availability) is not str or availability not in EVIDENCE_AVAILABILITY:
            raise BoundedEvidenceAnalystError("evidence availability is invalid")
        result.append({
            "evidence_id": evidence_id,
            "content_sha256": _sha256(item["content_sha256"], "content_sha256"),
            "source_reference": _text(item["source_reference"], "source_reference"),
            "availability": availability,
        })
    if not result:
        raise BoundedEvidenceAnalystError("at least one evidence item is required")
    return sorted(result, key=lambda item: item["evidence_id"])


def _normalize_assessments(
    values: Any,
    availability: Mapping[str, str],
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in _sequence(values, "evidence_assessments"):
        item = _closed(raw, _ASSESSMENT_FIELDS, "evidence assessment")
        evidence_id = _identifier(item["evidence_id"], "assessment evidence_id")
        if evidence_id not in availability or evidence_id in seen:
            raise BoundedEvidenceAnalystError("assessment evidence ids mismatch")
        seen.add(evidence_id)
        disposition = item["disposition"]
        relation = item["relation"]
        if type(disposition) is not str or disposition not in DISPOSITIONS:
            raise BoundedEvidenceAnalystError("assessment disposition is invalid")
        if type(relation) is not str or relation not in RELATIONS:
            raise BoundedEvidenceAnalystError("assessment relation is invalid")
        if disposition == "EXCLUDED" and relation != "NOT_APPLIED":
            raise BoundedEvidenceAnalystError(
                "excluded evidence relation must be NOT_APPLIED"
            )
        if disposition == "INCLUDED" and relation == "NOT_APPLIED":
            raise BoundedEvidenceAnalystError(
                "included evidence relation cannot be NOT_APPLIED"
            )
        if availability[evidence_id] == "UNAVAILABLE" and (
            disposition != "INCLUDED" or relation != "UNKNOWN"
        ):
            raise BoundedEvidenceAnalystError(
                "unavailable evidence must remain included as UNKNOWN"
            )
        result.append({
            "evidence_id": evidence_id,
            "disposition": disposition,
            "relation": relation,
            "rationale": _text(item["rationale"], "assessment rationale"),
        })
    if seen != set(availability):
        raise BoundedEvidenceAnalystError(
            "every evidence item must be assessed exactly once"
        )
    return sorted(result, key=lambda item: item["evidence_id"])


def _normalize_findings(
    values: Any,
    availability: Mapping[str, str],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in _sequence(values, "findings"):
        item = _closed(raw, _FINDING_FIELDS, "finding")
        finding_id = _identifier(item["finding_id"], "finding_id")
        if finding_id in seen:
            raise BoundedEvidenceAnalystError("finding_id values must be unique")
        seen.add(finding_id)
        result.append({
            "finding_id": finding_id,
            "statement": _text(item["statement"], "finding statement"),
            "evidence_assessments": _normalize_assessments(
                item["evidence_assessments"], availability
            ),
        })
    if not result:
        raise BoundedEvidenceAnalystError("at least one finding is required")
    return sorted(result, key=lambda item: item["finding_id"])


def _derive_result(finding: Mapping[str, Any]) -> dict[str, Any]:
    included = [
        item for item in finding["evidence_assessments"]
        if item["disposition"] == "INCLUDED"
    ]
    supporting = [item["evidence_id"] for item in included if item["relation"] == "SUPPORTS"]
    contradicting = [
        item["evidence_id"] for item in included if item["relation"] == "CONTRADICTS"
    ]
    unknown = [item["evidence_id"] for item in included if item["relation"] == "UNKNOWN"]
    neutral = [item["evidence_id"] for item in included if item["relation"] == "NEUTRAL"]
    excluded = [
        item["evidence_id"] for item in finding["evidence_assessments"]
        if item["disposition"] == "EXCLUDED"
    ]
    if supporting and not contradicting and not unknown:
        status, reason = "SUPPORTED", "SUPPORT_WITHOUT_CONTRADICTION_OR_UNKNOWN"
    elif contradicting and not supporting and not unknown:
        status, reason = "CONTRADICTED", "CONTRADICTION_WITHOUT_SUPPORT_OR_UNKNOWN"
    elif supporting and contradicting:
        status, reason = "UNRESOLVED", "CONFLICTING_EVIDENCE"
    elif unknown:
        status, reason = "UNRESOLVED", "UNKNOWN_EVIDENCE_REMAINS"
    else:
        status, reason = "UNRESOLVED", "NO_DIRECTIONAL_EVIDENCE"
    return {
        "finding_id": finding["finding_id"],
        "status": status,
        "status_reason": reason,
        "supporting_evidence_ids": supporting,
        "contradicting_evidence_ids": contradicting,
        "unknown_evidence_ids": unknown,
        "neutral_evidence_ids": neutral,
        "excluded_evidence_ids": excluded,
    }


def build_evidence_analysis_receipt(
    *,
    analysis_id: str,
    scope: str,
    method: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic receipt from fully accounted evidence relations."""
    normalized_evidence = _normalize_evidence(evidence)
    availability = {
        item["evidence_id"]: item["availability"] for item in normalized_evidence
    }
    normalized_findings = _normalize_findings(findings, availability)
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "analysis_id": _identifier(analysis_id, "analysis_id"),
        "scope": _text(scope, "scope"),
        "method": _normalize_method(method),
        "evidence": normalized_evidence,
        "evidence_set_hash": _hash(normalized_evidence),
        "findings": normalized_findings,
        "finding_results": [_derive_result(item) for item in normalized_findings],
        "analysis_status": "DERIVED_FROM_DECLARED_RELATIONS",
        "method_executed": False,
        "truth_claimed": False,
        "recommended_action": None,
        "accepted": False,
        "selection_authority": "NONE",
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Finding statuses are deterministic consequences of supplied evidence "
            "relations and exclusions. The receipt does not authenticate evidence, "
            "execute the declared method, establish truth, recommend action, accept "
            "results, or grant authority."
        ),
    }
    return {**body, "receipt_hash": _hash(body)}


def verify_evidence_analysis_receipt(receipt: Mapping[str, Any]) -> bool:
    """Rebuild the closed receipt and reject omitted or forged semantics."""
    if type(receipt) is not dict:
        raise BoundedEvidenceAnalystError("receipt must be a plain object")
    if set(receipt) != _RECEIPT_FIELDS:
        raise BoundedEvidenceAnalystError("receipt fields mismatch")
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise BoundedEvidenceAnalystError("receipt schema mismatch")
    supplied_hash = receipt["receipt_hash"]
    _sha256(supplied_hash, "receipt_hash")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if _hash(body) != supplied_hash:
        raise BoundedEvidenceAnalystError("receipt hash mismatch")
    try:
        expected = build_evidence_analysis_receipt(
            analysis_id=receipt["analysis_id"],
            scope=receipt["scope"],
            method=receipt["method"],
            evidence=receipt["evidence"],
            findings=receipt["findings"],
        )
    except (KeyError, TypeError) as exc:
        raise BoundedEvidenceAnalystError("receipt is malformed") from exc
    if dict(receipt) != expected:
        raise BoundedEvidenceAnalystError("receipt is internally inconsistent")
    return True
