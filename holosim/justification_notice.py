"""Versioned, evidence-bound notices preserving why a change was selected.

A notice records rationale and epistemic boundaries.  It does not prove truth,
approve the selected change, or grant permission to apply it.  Later rules use
successor notices so prior reasons and unknowns remain reconstructable.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .canonical import CanonicalValueError, stable_hash


NOTICE_TYPE = "holo_notice_of_justification"
NOTICE_VERSION = 1
SHA256 = re.compile(r"[0-9a-f]{64}")

UNKNOWN_STATUSES = {
    "NOT_YET_KNOWN",
    "UNDETERMINABLE_UNDER_DECLARED_METHOD",
}

TARGET_FIELDS = {"target_id", "target_type", "target_sha256"}
EVIDENCE_FIELDS = {"evidence_id", "evidence_sha256"}
ALTERNATIVE_FIELDS = {
    "alternative_id", "description", "rejection_reason", "evidence_ids",
}
UNKNOWN_FIELDS = {
    "unknown_id", "statement", "status", "method_boundary",
    "resolution_condition",
}
CONTRIBUTOR_FIELDS = {"contributor_id", "role"}


class JustificationNoticeError(ValueError):
    """Notice input or a stored notice violates the closed contract."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise JustificationNoticeError(f"{field} must be a nonempty plain string")
    return value


def _hash(value: Any, field: str) -> str:
    text = _text(value, field)
    if SHA256.fullmatch(text) is None:
        raise JustificationNoticeError(
            f"{field} must be 64 lowercase hexadecimal characters"
        )
    return text


def _closed(value: Any, field: str) -> Any:
    try:
        stable_hash(value)
    except CanonicalValueError as exc:
        raise JustificationNoticeError(
            f"{field} must contain strict canonical JSON values"
        ) from exc
    return deepcopy(value)


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise JustificationNoticeError(
            f"{label} fields do not match the versioned schema"
        )
    return deepcopy(value)


def _target(value: Mapping[str, Any]) -> dict[str, str]:
    item = _exact(value, TARGET_FIELDS, "target")
    _text(item["target_id"], "target.target_id")
    _text(item["target_type"], "target.target_type")
    _hash(item["target_sha256"], "target.target_sha256")
    return item


def _evidence(values: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    if type(values) not in {list, tuple} or not values:
        raise JustificationNoticeError("evidence_bindings must be a nonempty list or tuple")
    result: list[dict[str, str]] = []
    ids: set[str] = set()
    for index, value in enumerate(values):
        item = _exact(value, EVIDENCE_FIELDS, f"evidence_bindings[{index}]")
        evidence_id = _text(item["evidence_id"], f"evidence_bindings[{index}].evidence_id")
        _hash(item["evidence_sha256"], f"evidence_bindings[{index}].evidence_sha256")
        if evidence_id in ids:
            raise JustificationNoticeError(f"duplicate evidence_id: {evidence_id}")
        ids.add(evidence_id)
        result.append(item)
    return sorted(result, key=lambda item: item["evidence_id"])


def _alternatives(
    values: Sequence[Mapping[str, Any]], evidence_ids: set[str]
) -> list[dict[str, Any]]:
    if type(values) not in {list, tuple}:
        raise JustificationNoticeError("rejected_alternatives must be a list or tuple")
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, value in enumerate(values):
        item = _exact(value, ALTERNATIVE_FIELDS, f"rejected_alternatives[{index}]")
        alternative_id = _text(
            item["alternative_id"], f"rejected_alternatives[{index}].alternative_id"
        )
        _text(item["description"], f"rejected_alternatives[{index}].description")
        _text(item["rejection_reason"], f"rejected_alternatives[{index}].rejection_reason")
        references = item["evidence_ids"]
        if type(references) is not list or any(type(ref) is not str or not ref for ref in references):
            raise JustificationNoticeError(
                f"rejected_alternatives[{index}].evidence_ids must be a list of strings"
            )
        if len(references) != len(set(references)):
            raise JustificationNoticeError("alternative evidence_ids must be unique")
        missing = sorted(set(references) - evidence_ids)
        if missing:
            raise JustificationNoticeError(
                "alternative references unbound evidence: " + ", ".join(missing)
            )
        if alternative_id in ids:
            raise JustificationNoticeError(f"duplicate alternative_id: {alternative_id}")
        ids.add(alternative_id)
        item["evidence_ids"] = sorted(references)
        result.append(item)
    return sorted(result, key=lambda item: item["alternative_id"])


def _unknowns(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if type(values) not in {list, tuple}:
        raise JustificationNoticeError("unknowns must be a list or tuple")
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, value in enumerate(values):
        item = _exact(value, UNKNOWN_FIELDS, f"unknowns[{index}]")
        unknown_id = _text(item["unknown_id"], f"unknowns[{index}].unknown_id")
        _text(item["statement"], f"unknowns[{index}].statement")
        status = item["status"]
        if status not in UNKNOWN_STATUSES:
            raise JustificationNoticeError(
                f"unknowns[{index}].status must be one of {sorted(UNKNOWN_STATUSES)}"
            )
        method = item["method_boundary"]
        resolution = item["resolution_condition"]
        if method is not None and (type(method) is not str or not method.strip()):
            raise JustificationNoticeError("method_boundary must be null or nonempty text")
        if resolution is not None and (
            type(resolution) is not str or not resolution.strip()
        ):
            raise JustificationNoticeError(
                "resolution_condition must be null or nonempty text"
            )
        if status == "NOT_YET_KNOWN" and resolution is None:
            raise JustificationNoticeError(
                "NOT_YET_KNOWN requires a resolution_condition"
            )
        if status == "UNDETERMINABLE_UNDER_DECLARED_METHOD" and method is None:
            raise JustificationNoticeError(
                "UNDETERMINABLE_UNDER_DECLARED_METHOD requires a method_boundary"
            )
        if unknown_id in ids:
            raise JustificationNoticeError(f"duplicate unknown_id: {unknown_id}")
        ids.add(unknown_id)
        result.append(item)
    return sorted(result, key=lambda item: item["unknown_id"])


def _contributors(values: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    if type(values) not in {list, tuple} or not values:
        raise JustificationNoticeError("contributors must be a nonempty list or tuple")
    result: list[dict[str, str]] = []
    ids: set[str] = set()
    for index, value in enumerate(values):
        item = _exact(value, CONTRIBUTOR_FIELDS, f"contributors[{index}]")
        contributor_id = _text(
            item["contributor_id"], f"contributors[{index}].contributor_id"
        )
        _text(item["role"], f"contributors[{index}].role")
        if contributor_id in ids:
            raise JustificationNoticeError(f"duplicate contributor_id: {contributor_id}")
        ids.add(contributor_id)
        result.append(item)
    return sorted(result, key=lambda item: item["contributor_id"])


def build_justification_notice(
    *,
    notice_id: str,
    parent_notice_hash: str | None,
    target: Mapping[str, Any],
    observed_failure: Mapping[str, Any],
    evidence_bindings: Sequence[Mapping[str, Any]],
    selected_change: Mapping[str, Any],
    why_selected: str,
    rejected_alternatives: Sequence[Mapping[str, Any]],
    declared_scope: Mapping[str, Any],
    established_findings: Sequence[Mapping[str, Any]],
    unknowns: Sequence[Mapping[str, Any]],
    reopen_conditions: Sequence[str],
    contributors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one immutable rationale record for an exact target version."""
    parent = None if parent_notice_hash is None else _hash(
        parent_notice_hash, "parent_notice_hash"
    )
    evidence = _evidence(evidence_bindings)
    evidence_ids = {item["evidence_id"] for item in evidence}
    if type(observed_failure) is not dict or not observed_failure:
        raise JustificationNoticeError("observed_failure must be a nonempty dictionary")
    if type(selected_change) is not dict or not selected_change:
        raise JustificationNoticeError("selected_change must be a nonempty dictionary")
    if type(declared_scope) is not dict or not declared_scope:
        raise JustificationNoticeError("declared_scope must be a nonempty dictionary")
    if type(established_findings) not in {list, tuple}:
        raise JustificationNoticeError("established_findings must be a list or tuple")
    findings = [_closed(item, f"established_findings[{index}]")
                for index, item in enumerate(established_findings)]
    conditions = list(reopen_conditions) if type(reopen_conditions) in {list, tuple} else None
    if not conditions or any(type(item) is not str or not item.strip() for item in conditions):
        raise JustificationNoticeError("reopen_conditions must contain nonempty strings")
    if len(conditions) != len(set(conditions)):
        raise JustificationNoticeError("reopen_conditions must be unique")
    normalized_unknowns = _unknowns(unknowns)
    body: dict[str, Any] = {
        "type": NOTICE_TYPE,
        "version": NOTICE_VERSION,
        "notice_id": _text(notice_id, "notice_id"),
        "parent_notice_hash": parent,
        "target": _target(target),
        "observed_failure": _closed(observed_failure, "observed_failure"),
        "evidence_bindings": evidence,
        "selected_change": _closed(selected_change, "selected_change"),
        "why_selected": _text(why_selected, "why_selected"),
        "rejected_alternatives": _alternatives(rejected_alternatives, evidence_ids),
        "declared_scope": _closed(declared_scope, "declared_scope"),
        "established_findings": findings,
        "unknowns": normalized_unknowns,
        "epistemic_status": (
            "SUPPORTED_WITH_DECLARED_UNKNOWNS" if normalized_unknowns else "SUPPORTED"
        ),
        "reopen_conditions": sorted(conditions),
        "contributors": _contributors(contributors),
        "truth_claimed": False,
        "change_approved": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "This notice preserves why a bounded change was selected and what remains "
            "unknown. It does not prove truth, approve the change, or make the rationale "
            "immune to later evidence and correction."
        ),
    }
    return {**body, "notice_hash": stable_hash(body)}


def validate_justification_notice(notice: Mapping[str, Any]) -> bool:
    """Rebuild a notice and require exact schema, relationships, and identity."""
    fields = {
        "type", "version", "notice_id", "parent_notice_hash", "target",
        "observed_failure", "evidence_bindings", "selected_change", "why_selected",
        "rejected_alternatives", "declared_scope", "established_findings",
        "unknowns", "epistemic_status", "reopen_conditions", "contributors",
        "truth_claimed", "change_approved", "accepted", "write_authority",
        "execution_authority", "interpretation_notice", "notice_hash",
    }
    if type(notice) is not dict or set(notice) != fields:
        raise JustificationNoticeError(
            "notice fields do not match the versioned schema"
        )
    if notice["type"] != NOTICE_TYPE or notice["version"] != NOTICE_VERSION:
        raise JustificationNoticeError("notice type or version is invalid")
    if (notice["truth_claimed"] is not False or notice["change_approved"] is not False or
            notice["accepted"] is not False or notice["write_authority"] != "NONE" or
            notice["execution_authority"] != "NONE"):
        raise JustificationNoticeError("notice grants forbidden authority")
    expected_epistemic = (
        "SUPPORTED_WITH_DECLARED_UNKNOWNS" if notice["unknowns"] else "SUPPORTED"
    )
    if notice["epistemic_status"] != expected_epistemic:
        raise JustificationNoticeError("epistemic_status contradicts unknowns")
    rebuilt = build_justification_notice(
        notice_id=notice["notice_id"],
        parent_notice_hash=notice["parent_notice_hash"],
        target=notice["target"],
        observed_failure=notice["observed_failure"],
        evidence_bindings=notice["evidence_bindings"],
        selected_change=notice["selected_change"],
        why_selected=notice["why_selected"],
        rejected_alternatives=notice["rejected_alternatives"],
        declared_scope=notice["declared_scope"],
        established_findings=notice["established_findings"],
        unknowns=notice["unknowns"],
        reopen_conditions=notice["reopen_conditions"],
        contributors=notice["contributors"],
    )
    if rebuilt != notice:
        raise JustificationNoticeError("notice does not match its canonical identity")
    return True
