"""Bounded coordinator for verified evidence-finding convergence.

This first agent vertical slice verifies complete evidence-analysis receipts,
groups their findings without erasing scope, and emits an inspectable candidate
state. It does not replace the read-only agent runtime, execute analytical
methods, infer usefulness, run dependency rechecks, admit state, or persist it.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.bounded_evidence_analyst import (
    BoundedEvidenceAnalystError,
    verify_evidence_analysis_receipt,
)
from holosim.canonical import CanonicalValueError, stable_hash


RECEIPT_TYPE = "verified_convergence_agent_receipt"
RECEIPT_VERSION = 1
MAX_ITEMS = 10_000
MAX_TEXT_UTF8_BYTES = 16_384

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
UNRESOLVED = "UNRESOLVED"
CONDITIONALLY_DIVERGENT = "CONDITIONALLY_DIVERGENT"

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_RECEIPT_FIELDS = {
    "type", "version", "run_id", "objective", "analysis_receipts",
    "source_receipt_hashes", "finding_groups", "converged_findings",
    "rejected_findings", "unresolved_findings", "run_status",
    "pending_stages", "stopped", "method_executed", "usefulness_inferred",
    "truth_claimed", "recommended_action", "accepted", "selection_authority",
    "write_authority", "execution_authority", "interpretation_notice",
    "receipt_hash",
}


class VerifiedConvergenceAgentError(ValueError):
    """Raised when agent input or output violates the bounded contract."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise VerifiedConvergenceAgentError(str(exc)) from exc


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise VerifiedConvergenceAgentError(f"{label} is invalid")
    return value


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise VerifiedConvergenceAgentError(f"{label} must be nonempty text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise VerifiedConvergenceAgentError(f"{label} must be valid UTF-8") from exc
    if size > MAX_TEXT_UTF8_BYTES:
        raise VerifiedConvergenceAgentError(f"{label} is too large")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise VerifiedConvergenceAgentError(f"{label} must be a sequence")
    if len(value) > MAX_ITEMS:
        raise VerifiedConvergenceAgentError(f"{label} exceeds item limit")
    return list(value)


def _verified_receipts(values: Any) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    analysis_ids: set[str] = set()
    hashes: set[str] = set()
    for raw in _sequence(values, "analysis_receipts"):
        if type(raw) is not dict:
            raise VerifiedConvergenceAgentError(
                "analysis receipt must be a plain object"
            )
        try:
            verify_evidence_analysis_receipt(raw)
        except BoundedEvidenceAnalystError as exc:
            raise VerifiedConvergenceAgentError(
                "analysis receipt verification failed"
            ) from exc
        analysis_id = _identifier(raw["analysis_id"], "analysis_id")
        receipt_hash = raw["receipt_hash"]
        if analysis_id in analysis_ids:
            raise VerifiedConvergenceAgentError("analysis_id values must be unique")
        if receipt_hash in hashes:
            raise VerifiedConvergenceAgentError("analysis receipt hashes must be unique")
        analysis_ids.add(analysis_id)
        hashes.add(receipt_hash)
        receipts.append(deepcopy(raw))
    if not receipts:
        raise VerifiedConvergenceAgentError(
            "at least one analysis receipt is required"
        )
    return sorted(receipts, key=lambda item: item["analysis_id"])


def _observations(receipts: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    observations: list[dict[str, str]] = []
    for receipt in receipts:
        findings = {item["finding_id"]: item for item in receipt["findings"]}
        results = {item["finding_id"]: item for item in receipt["finding_results"]}
        if set(findings) != set(results):
            raise VerifiedConvergenceAgentError("analysis finding results mismatch")
        for finding_id in sorted(findings):
            finding = findings[finding_id]
            result = results[finding_id]
            observations.append({
                "finding_id": finding_id,
                "statement": finding["statement"],
                "scope": receipt["scope"],
                "status": result["status"],
                "analysis_id": receipt["analysis_id"],
                "analysis_receipt_hash": receipt["receipt_hash"],
                "evidence_set_hash": receipt["evidence_set_hash"],
            })
    return observations


def _scope_result(observations: list[dict[str, str]]) -> dict[str, Any]:
    statements = sorted({item["statement"] for item in observations})
    statuses = sorted({item["status"] for item in observations})
    if len(statements) == 1 and statuses == [SUPPORTED]:
        status = SUPPORTED
        reason = "VERIFIED_SUPPORT_WITHIN_SCOPE"
    elif len(statements) == 1 and statuses == [CONTRADICTED]:
        status = CONTRADICTED
        reason = "VERIFIED_CONTRADICTION_WITHIN_SCOPE"
    elif len(statements) > 1:
        status = UNRESOLVED
        reason = "STATEMENT_IDENTITY_CONFLICT_WITHIN_SCOPE"
    else:
        status = UNRESOLVED
        reason = "FINDING_STATUS_UNRESOLVED_WITHIN_SCOPE"
    return {
        "scope": observations[0]["scope"],
        "status": status,
        "reason": reason,
        "statements": statements,
        "observations": sorted(
            observations,
            key=lambda item: (item["analysis_id"], item["analysis_receipt_hash"]),
        ),
    }


def _finding_groups(receipts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_finding: dict[str, list[dict[str, str]]] = {}
    for observation in _observations(receipts):
        by_finding.setdefault(observation["finding_id"], []).append(observation)

    groups = []
    for finding_id in sorted(by_finding):
        by_scope: dict[str, list[dict[str, str]]] = {}
        for observation in by_finding[finding_id]:
            by_scope.setdefault(observation["scope"], []).append(observation)
        scopes = [_scope_result(by_scope[scope]) for scope in sorted(by_scope)]
        scope_statuses = {item["status"] for item in scopes}
        statements = sorted(
            {statement for item in scopes for statement in item["statements"]}
        )
        if UNRESOLVED in scope_statuses:
            status = UNRESOLVED
            reason = "AT_LEAST_ONE_SCOPE_UNRESOLVED"
        elif len(statements) > 1:
            status = UNRESOLVED
            reason = "STATEMENT_IDENTITY_DIFFERS_ACROSS_SCOPES"
        elif scope_statuses == {SUPPORTED}:
            status = SUPPORTED
            reason = "VERIFIED_SUPPORT_ACROSS_DECLARED_SCOPES"
        elif scope_statuses == {CONTRADICTED}:
            status = CONTRADICTED
            reason = "VERIFIED_CONTRADICTION_ACROSS_DECLARED_SCOPES"
        else:
            status = CONDITIONALLY_DIVERGENT
            reason = "STATUS_DIFFERS_BY_DECLARED_SCOPE"
        groups.append({
            "finding_id": finding_id,
            "status": status,
            "reason": reason,
            "statements": statements,
            "scope_results": scopes,
        })
    return groups


def run_verified_convergence_agent(
    *,
    run_id: str,
    objective: str,
    analysis_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify Analyst receipts and converge only bounded supported findings."""
    receipts = _verified_receipts(analysis_receipts)
    groups = _finding_groups(receipts)
    converged = [deepcopy(item) for item in groups if item["status"] == SUPPORTED]
    rejected = [deepcopy(item) for item in groups if item["status"] == CONTRADICTED]
    unresolved = [
        deepcopy(item)
        for item in groups
        if item["status"] in {UNRESOLVED, CONDITIONALLY_DIVERGENT}
    ]
    if unresolved:
        run_status = "PARTIAL"
    elif converged:
        run_status = "CONVERGED_CANDIDATE"
    else:
        run_status = "NO_SUPPORTED_FINDINGS"

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "run_id": _identifier(run_id, "run_id"),
        "objective": _text(objective, "objective"),
        "analysis_receipts": receipts,
        "source_receipt_hashes": [item["receipt_hash"] for item in receipts],
        "finding_groups": groups,
        "converged_findings": converged,
        "rejected_findings": rejected,
        "unresolved_findings": unresolved,
        "run_status": run_status,
        "pending_stages": ["DEPENDENCY_RECHECK", "ADMISSION", "PERSISTENCE"],
        "stopped": True,
        "method_executed": False,
        "usefulness_inferred": False,
        "truth_claimed": False,
        "recommended_action": None,
        "accepted": False,
        "selection_authority": "NONE",
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Convergence means only that intact Analyst receipts repeatedly derive "
            "support for the same finding statement across their declared scopes. "
            "The agent does not execute methods, infer usefulness or truth, resolve "
            "conditional differences, perform pending stages, or grant authority."
        ),
    }
    return {**body, "receipt_hash": _hash(body)}


def verify_agent_convergence_receipt(receipt: Mapping[str, Any]) -> bool:
    """Rebuild the closed agent receipt and reject semantic forgery."""
    if type(receipt) is not dict or set(receipt) != _RECEIPT_FIELDS:
        raise VerifiedConvergenceAgentError("receipt fields mismatch")
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise VerifiedConvergenceAgentError("receipt schema mismatch")
    supplied_hash = receipt["receipt_hash"]
    if type(supplied_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", supplied_hash) is None:
        raise VerifiedConvergenceAgentError("receipt_hash is invalid")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if _hash(body) != supplied_hash:
        raise VerifiedConvergenceAgentError("receipt hash mismatch")
    try:
        expected = run_verified_convergence_agent(
            run_id=receipt["run_id"],
            objective=receipt["objective"],
            analysis_receipts=receipt["analysis_receipts"],
        )
    except (KeyError, TypeError) as exc:
        raise VerifiedConvergenceAgentError("receipt is malformed") from exc
    if dict(receipt) != expected:
        raise VerifiedConvergenceAgentError("receipt is internally inconsistent")
    return True
