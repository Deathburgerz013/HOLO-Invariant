from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence


class JudgmentJustifierError(ValueError):
    """Raised when a judgment-justification record is invalid."""


VALID_COMPARISON_STATUSES = {"SUPPORTED", "CONFLICTED", "UNRESOLVED"}
VALID_UNCERTAINTY = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise JudgmentJustifierError(
            "justifier values must be finite, acyclic, JSON-compatible data"
        ) from exc


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_references(values: Sequence[str], *, label: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise JudgmentJustifierError(f"{label} must contain non-empty strings")
        if value in seen:
            raise JudgmentJustifierError(f"duplicate {label}: {value}")
        seen.add(value)
        normalized.append(value)
    return normalized


def evaluate_judgment_justification(
    *,
    judgment_id: str,
    conclusion: Mapping[str, Any],
    reference_state: str,
    evidence_references: Sequence[str],
    rule_references: Sequence[str],
    comparison_status: str,
    uncertainty: str,
    unresolved_conflicts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """
    Evaluate whether a supplied judgment is justified by explicit support.

    This evaluator does not decide whether the conclusion is true. It only
    checks whether the judgment has an explicit state reference, evidence,
    rule/invariant references, a supported comparison result, and no declared
    unresolved conflicts. It never grants acceptance or write authority.
    """
    if not isinstance(judgment_id, str) or not judgment_id.strip():
        raise JudgmentJustifierError("judgment_id must be a non-empty string")
    if not isinstance(conclusion, Mapping) or not conclusion:
        raise JudgmentJustifierError("conclusion must be a non-empty object")
    if not isinstance(reference_state, str) or not reference_state.strip():
        raise JudgmentJustifierError("reference_state must be a non-empty string")
    if comparison_status not in VALID_COMPARISON_STATUSES:
        raise JudgmentJustifierError(
            f"comparison_status must be one of {sorted(VALID_COMPARISON_STATUSES)}"
        )
    if uncertainty not in VALID_UNCERTAINTY:
        raise JudgmentJustifierError(
            f"uncertainty must be one of {sorted(VALID_UNCERTAINTY)}"
        )

    evidence = _normalize_references(evidence_references, label="evidence_reference")
    rules = _normalize_references(rule_references, label="rule_reference")

    conflicts: list[dict[str, Any]] = []
    seen_conflict_ids: set[str] = set()
    for conflict in unresolved_conflicts:
        if not isinstance(conflict, Mapping):
            raise JudgmentJustifierError("unresolved_conflicts must contain objects")
        conflict_id = conflict.get("id")
        if not isinstance(conflict_id, str) or not conflict_id.strip():
            raise JudgmentJustifierError(
                "unresolved conflict requires a non-empty string id"
            )
        if conflict_id in seen_conflict_ids:
            raise JudgmentJustifierError(
                f"duplicate unresolved conflict id: {conflict_id}"
            )
        seen_conflict_ids.add(conflict_id)
        conflicts.append(deepcopy(dict(conflict)))

    missing_support: list[str] = []
    if not evidence:
        missing_support.append("evidence")
    if not rules:
        missing_support.append("rule_or_invariant")

    if missing_support:
        status = "UNJUSTIFIED"
    elif comparison_status == "CONFLICTED" or conflicts:
        status = "CONFLICTED"
    elif comparison_status != "SUPPORTED":
        status = "UNRESOLVED"
    elif uncertainty in {"HIGH", "UNKNOWN"}:
        status = "UNCERTAIN"
    else:
        status = "JUSTIFIED"

    result = {
        "type": "judgment_justification",
        "judgment_id": judgment_id,
        "conclusion": deepcopy(dict(conclusion)),
        "reference_state": reference_state,
        "evidence_references": evidence,
        "rule_references": rules,
        "comparison_status": comparison_status,
        "uncertainty": uncertainty,
        "unresolved_conflicts": conflicts,
        "missing_support": missing_support,
        "status": status,
        "truth_claimed": False,
        "acceptance_granted": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    result["justification_hash"] = _stable_hash(result)
    return result
