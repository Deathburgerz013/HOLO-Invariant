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
from holosim.fact_identity import (
    VerifiedFactIdentityError,
    verify_fact_identity_receipt,
)
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.receipt_graph import (
    build_receipt_graph,
    plan_dependency_rechecks,
    RECHECK_REQUIRED,
)


RECEIPT_TYPE = "verified_convergence_agent_receipt"
RECEIPT_VERSION = 1
DEPENDENCY_CHECKED_RECEIPT_TYPE = "dependency_checked_convergence_agent_receipt"
DEPENDENCY_CHECKED_RECEIPT_VERSION = 1
MAX_ITEMS = 10_000
MAX_TEXT_UTF8_BYTES = 16_384

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
UNRESOLVED = "UNRESOLVED"
CONDITIONALLY_DIVERGENT = "CONDITIONALLY_DIVERGENT"

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_RECEIPT_FIELDS = {
    "type", "version", "run_id", "objective", "analysis_receipts",
    "fact_identity_bindings", "fact_identity_receipts",
    "source_receipt_hashes", "finding_groups",
    "converged_findings",
    "rejected_findings", "unresolved_findings", "run_status",
    "pending_stages", "stopped", "method_executed", "usefulness_inferred",
    "truth_claimed", "recommended_action", "accepted", "selection_authority",
    "write_authority", "execution_authority", "interpretation_notice",
    "receipt_hash",
}
_FACT_IDENTITY_MEMBER_FIELDS = {"analysis_id", "finding_id"}
_FACT_IDENTITY_BINDING_FIELDS = {"fact_id", "members"}
_DEPENDENCY_BINDING_FIELDS = {
    "analysis_receipt_hash", "dependency_receipt_hashes",
}
_DEPENDENCY_CHECKED_RECEIPT_FIELDS = {
    "type", "version", "run_id", "base_agent_receipt",
    "dependency_bindings", "dependency_receipts", "recheck_plan",
    "eligible_converged_findings", "eligible_rejected_findings",
    "eligible_unresolved_findings", "withheld_findings", "run_status",
    "pending_stages", "stopped", "validity_claimed", "truth_claimed",
    "recommended_action", "accepted", "selection_authority",
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


def _normalize_fact_identity_bindings(
    values: Any,
    receipts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    known_members = {
        (receipt["analysis_id"], finding["finding_id"])
        for receipt in receipts
        for finding in receipt["findings"]
    }
    bindings: list[dict[str, Any]] = []
    fact_ids: set[str] = set()
    claimed_members: set[tuple[str, str]] = set()

    for raw in _sequence(values, "fact_identity_bindings"):
        if type(raw) is not dict or set(raw) != _FACT_IDENTITY_BINDING_FIELDS:
            raise VerifiedConvergenceAgentError("fact identity binding fields mismatch")
        fact_id = _identifier(raw["fact_id"], "fact_id")
        if fact_id in fact_ids:
            raise VerifiedConvergenceAgentError("fact_id values must be unique")
        fact_ids.add(fact_id)

        members: list[dict[str, str]] = []
        local_members: set[tuple[str, str]] = set()
        for member in _sequence(raw["members"], "fact identity members"):
            if type(member) is not dict or set(member) != _FACT_IDENTITY_MEMBER_FIELDS:
                raise VerifiedConvergenceAgentError("fact identity member fields mismatch")
            analysis_id = _identifier(member["analysis_id"], "analysis_id")
            finding_id = _identifier(member["finding_id"], "finding_id")
            key = (analysis_id, finding_id)
            if key not in known_members:
                raise VerifiedConvergenceAgentError(
                    "fact identity member does not reference a supplied finding"
                )
            if key in local_members or key in claimed_members:
                raise VerifiedConvergenceAgentError(
                    "fact identity member cannot belong to more than one binding"
                )
            local_members.add(key)
            claimed_members.add(key)
            members.append({"analysis_id": analysis_id, "finding_id": finding_id})
        if not members:
            raise VerifiedConvergenceAgentError(
                "fact identity binding requires at least one member"
            )
        bindings.append({
            "fact_id": fact_id,
            "members": sorted(
                members, key=lambda item: (item["analysis_id"], item["finding_id"])
            ),
        })

    return sorted(bindings, key=lambda item: item["fact_id"])


def _verified_fact_identity_receipts(
    values: Any,
    receipts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []

    for raw in _sequence(values, "fact_identity_receipts"):
        if type(raw) is not dict:
            raise VerifiedConvergenceAgentError(
                "fact identity receipt must be a plain object"
            )

        try:
            verify_fact_identity_receipt(raw)
        except VerifiedFactIdentityError as exc:
            raise VerifiedConvergenceAgentError(
                "fact identity receipt verification failed"
            ) from exc

        verified.append(deepcopy(raw))

    bindings = [
        {
            "fact_id": item["fact_id"],
            "members": deepcopy(item["members"]),
        }
        for item in verified
    ]

    _normalize_fact_identity_bindings(bindings, receipts)

    return sorted(
        verified,
        key=lambda item: (item["fact_id"], item["receipt_hash"]),
    )


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


def _finding_groups(
    receipts: Sequence[Mapping[str, Any]],
    fact_identity_bindings: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    member_fact = {
        (member["analysis_id"], member["finding_id"]): binding["fact_id"]
        for binding in fact_identity_bindings
        for member in binding["members"]
    }
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for observation in _observations(receipts):
        member = (observation["analysis_id"], observation["finding_id"])
        fact_id = member_fact.get(member)
        key = ("fact", fact_id) if fact_id is not None else ("finding", observation["finding_id"])
        grouped.setdefault(key, []).append(observation)

    groups = []
    for key in sorted(grouped):
        observations = grouped[key]
        by_scope: dict[str, list[dict[str, str]]] = {}
        for observation in observations:
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

        identity = (
            {
                "fact_id": key[1],
                "finding_ids": sorted({item["finding_id"] for item in observations}),
            }
            if key[0] == "fact"
            else {"finding_id": key[1]}
        )
        groups.append({
            **identity,
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
    fact_identity_bindings: Sequence[Mapping[str, Any]] = (),
    fact_identity_receipts: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Verify Analyst receipts and converge only bounded supported findings."""
    receipts = _verified_receipts(analysis_receipts)
    verified_identity_receipts = _verified_fact_identity_receipts(
        fact_identity_receipts,
        receipts,
    )
    receipt_bindings = [
        {
            "fact_id": item["fact_id"],
            "members": deepcopy(item["members"]),
        }
        for item in verified_identity_receipts
    ]
    identities = _normalize_fact_identity_bindings(
        list(fact_identity_bindings) + receipt_bindings,
        receipts,
    )
    groups = _finding_groups(receipts, identities)
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
        "fact_identity_bindings": identities,
        "fact_identity_receipts": verified_identity_receipts,
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
            "support within a finding identity or an explicitly declared fact identity "
            "across their declared scopes. The agent does not infer fact identity from "
            "wording, execute methods, infer usefulness or truth, resolve "
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
            fact_identity_bindings=receipt["fact_identity_bindings"],
            fact_identity_receipts=receipt["fact_identity_receipts"],
        )
    except (KeyError, TypeError) as exc:
        raise VerifiedConvergenceAgentError("receipt is malformed") from exc
    if dict(receipt) != expected:
        raise VerifiedConvergenceAgentError("receipt is internally inconsistent")
    return True


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise VerifiedConvergenceAgentError(f"{label} must be a SHA-256 hash")
    return value


def _normalize_dependency_bindings(
    values: Any,
    source_hashes: Sequence[str],
) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in _sequence(values, "dependency_bindings"):
        if type(raw) is not dict or set(raw) != _DEPENDENCY_BINDING_FIELDS:
            raise VerifiedConvergenceAgentError("dependency binding fields mismatch")
        analysis_hash = _sha256(
            raw["analysis_receipt_hash"], "analysis_receipt_hash"
        )
        if analysis_hash in seen:
            raise VerifiedConvergenceAgentError(
                "analysis dependency bindings must be unique"
            )
        seen.add(analysis_hash)
        dependencies = [
            _sha256(value, "dependency_receipt_hash")
            for value in _sequence(
                raw["dependency_receipt_hashes"], "dependency_receipt_hashes"
            )
        ]
        if len(dependencies) != len(set(dependencies)):
            raise VerifiedConvergenceAgentError(
                "dependency receipt hashes must be unique"
            )
        bindings.append({
            "analysis_receipt_hash": analysis_hash,
            "dependency_receipt_hashes": sorted(dependencies),
        })
    if seen != set(source_hashes):
        raise VerifiedConvergenceAgentError(
            "dependency bindings must cover every analysis receipt exactly once"
        )
    return sorted(bindings, key=lambda item: item["analysis_receipt_hash"])


def _normalize_dependency_receipts(values: Any) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in _sequence(values, "dependency_receipts"):
        if type(raw) is not dict:
            raise VerifiedConvergenceAgentError(
                "dependency receipt must be a plain object"
            )
        receipt_hash = _sha256(raw.get("receipt_hash"), "dependency receipt_hash")
        if receipt_hash in seen:
            raise VerifiedConvergenceAgentError(
                "dependency receipt hashes must be unique"
            )
        seen.add(receipt_hash)
        receipts.append(deepcopy(raw))
    return sorted(receipts, key=lambda item: item["receipt_hash"])


def _finding_source_hashes(finding: Mapping[str, Any]) -> set[str]:
    return {
        observation["analysis_receipt_hash"]
        for scope in finding["scope_results"]
        for observation in scope["observations"]
    }


def run_dependency_checked_convergence_agent(
    *,
    run_id: str,
    base_agent_receipt: Mapping[str, Any],
    dependency_bindings: Sequence[Mapping[str, Any]],
    dependency_receipts: Sequence[Mapping[str, Any]],
    changed_dependency_hashes: Sequence[str],
) -> dict[str, Any]:
    """Withhold findings reached from explicitly changed dependencies.

    Dependency receipts and changed hashes are caller-declared graph inputs.
    This stage verifies the base Agent receipt and computes reachability; it does
    not execute the required rechecks or establish validity from graph silence.
    """
    if type(base_agent_receipt) is not dict:
        raise VerifiedConvergenceAgentError("base_agent_receipt must be a plain object")
    try:
        verify_agent_convergence_receipt(base_agent_receipt)
    except VerifiedConvergenceAgentError as exc:
        raise VerifiedConvergenceAgentError(
            "base Agent receipt verification failed"
        ) from exc
    base = deepcopy(base_agent_receipt)
    bindings = _normalize_dependency_bindings(
        dependency_bindings, base["source_receipt_hashes"]
    )
    declared_receipts = _normalize_dependency_receipts(dependency_receipts)
    source_hashes = set(base["source_receipt_hashes"])
    if source_hashes & {item["receipt_hash"] for item in declared_receipts}:
        raise VerifiedConvergenceAgentError(
            "dependency receipts must not replace analysis receipt nodes"
        )

    graph_receipts = [
        {
            "receipt_hash": binding["analysis_receipt_hash"],
            "evidence_receipt_hashes": binding["dependency_receipt_hashes"],
        }
        for binding in bindings
    ]
    graph_receipts.extend(declared_receipts)
    try:
        graph = build_receipt_graph(graph_receipts)
        plan = plan_dependency_rechecks(graph, changed_dependency_hashes)
    except (KeyError, TypeError, ValueError) as exc:
        raise VerifiedConvergenceAgentError("dependency recheck planning failed") from exc

    impacted = {
        item["receipt_hash"]: item["trigger_paths"]
        for item in plan["results"]
        if item["status"] == RECHECK_REQUIRED
        and item["receipt_hash"] in source_hashes
    }
    withheld: list[dict[str, Any]] = []
    eligible_by_status: dict[str, list[dict[str, Any]]] = {
        SUPPORTED: [],
        CONTRADICTED: [],
        UNRESOLVED: [],
        CONDITIONALLY_DIVERGENT: [],
    }
    for finding in base["finding_groups"]:
        affected_sources = sorted(_finding_source_hashes(finding) & set(impacted))
        if affected_sources:
            withheld.append({
                "finding": deepcopy(finding),
                "affected_analysis_receipt_hashes": affected_sources,
                "trigger_paths": [
                    path
                    for source_hash in affected_sources
                    for path in impacted[source_hash]
                ],
                "reason": "DECLARED_DEPENDENCY_RECHECK_REQUIRED",
            })
        else:
            eligible_by_status[finding["status"]].append(deepcopy(finding))

    eligible_unresolved = [
        *eligible_by_status[UNRESOLVED],
        *eligible_by_status[CONDITIONALLY_DIVERGENT],
    ]
    if withheld:
        run_status = "RECHECK_REQUIRED"
    elif eligible_unresolved:
        run_status = "PARTIAL_NO_DECLARED_RECHECK_IMPACT"
    else:
        run_status = "NO_DECLARED_RECHECK_IMPACT"

    body = {
        "type": DEPENDENCY_CHECKED_RECEIPT_TYPE,
        "version": DEPENDENCY_CHECKED_RECEIPT_VERSION,
        "run_id": _identifier(run_id, "run_id"),
        "base_agent_receipt": base,
        "dependency_bindings": bindings,
        "dependency_receipts": declared_receipts,
        "recheck_plan": plan,
        "eligible_converged_findings": eligible_by_status[SUPPORTED],
        "eligible_rejected_findings": eligible_by_status[CONTRADICTED],
        "eligible_unresolved_findings": eligible_unresolved,
        "withheld_findings": withheld,
        "run_status": run_status,
        "pending_stages": ["DEPENDENCY_RECHECK_EXECUTION", "ADMISSION", "PERSISTENCE"],
        "stopped": True,
        "validity_claimed": False,
        "truth_claimed": False,
        "recommended_action": None,
        "accepted": False,
        "selection_authority": "NONE",
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Affected findings are withheld because declared graph paths require "
            "recheck. Eligible means only that no supplied changed hash reaches the "
            "finding; it does not establish present validity, usefulness, or truth."
        ),
    }
    return {**body, "receipt_hash": _hash(body)}


def verify_dependency_checked_agent_receipt(receipt: Mapping[str, Any]) -> bool:
    """Rebuild a dependency-checked Agent receipt exactly."""
    if type(receipt) is not dict or set(receipt) != _DEPENDENCY_CHECKED_RECEIPT_FIELDS:
        raise VerifiedConvergenceAgentError("dependency-checked receipt fields mismatch")
    if (
        receipt["type"] != DEPENDENCY_CHECKED_RECEIPT_TYPE
        or receipt["version"] != DEPENDENCY_CHECKED_RECEIPT_VERSION
    ):
        raise VerifiedConvergenceAgentError("dependency-checked receipt schema mismatch")
    supplied_hash = receipt["receipt_hash"]
    _sha256(supplied_hash, "receipt_hash")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if _hash(body) != supplied_hash:
        raise VerifiedConvergenceAgentError("dependency-checked receipt hash mismatch")
    try:
        expected = run_dependency_checked_convergence_agent(
            run_id=receipt["run_id"],
            base_agent_receipt=receipt["base_agent_receipt"],
            dependency_bindings=receipt["dependency_bindings"],
            dependency_receipts=receipt["dependency_receipts"],
            changed_dependency_hashes=receipt["recheck_plan"][
                "changed_dependency_hashes"
            ],
        )
    except (KeyError, TypeError) as exc:
        raise VerifiedConvergenceAgentError(
            "dependency-checked receipt is malformed"
        ) from exc
    if dict(receipt) != expected:
        raise VerifiedConvergenceAgentError(
            "dependency-checked receipt is internally inconsistent"
        )
    return True
