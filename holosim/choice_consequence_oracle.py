"""Bounded choice-consequence scenarios for HOLO/Sim.

This module records declared choices, assumptions, and conditional outcomes.
It does not infer the future, prove causation, assign probability, recommend a
choice, or grant acceptance, write, or execution authority.
"""

from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import stable_hash


RECEIPT_TYPE = "bounded_choice_consequence_receipt"
RECEIPT_VERSION = 1
MAX_ITEMS = 1_000
MAX_TEXT_UTF8_BYTES = 16_384
MAX_JSON_DEPTH = 10
ASSUMPTION_STATUSES = {"VERIFIED", "DECLARED", "UNKNOWN"}
CONSEQUENCE_VALENCES = {"BENEFIT", "RISK", "NEUTRAL", "UNKNOWN"}
PREDICTION_STATUS = "CONDITIONAL_ONLY"

_ASSUMPTION_FIELDS = {
    "assumption_id", "statement", "status", "evidence_references",
}
_CHOICE_FIELDS = {"choice_id", "action", "consequences"}
_CONSEQUENCE_FIELDS = {
    "consequence_id", "statement", "condition_assumption_ids", "valence",
}
_RECEIPT_FIELDS = {
    "type", "version", "decision_id", "observed_state",
    "observed_state_hash", "assumptions", "choices", "scenario_branches",
    "prediction_status", "recommended_choice_id", "probability_claimed",
    "causation_claimed", "accepted", "truth_claimed", "write_authority",
    "execution_authority", "interpretation_notice", "receipt_hash",
}
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class ChoiceConsequenceOracleError(ValueError):
    """Raised when an oracle input or receipt violates the closed contract."""


def _validate_json(value: Any, *, label: str) -> Any:
    active: set[int] = set()
    item_count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal item_count
        item_count += 1
        if item_count > MAX_ITEMS:
            raise ChoiceConsequenceOracleError(f"{label} exceeds item limit")
        if depth > MAX_JSON_DEPTH:
            raise ChoiceConsequenceOracleError(f"{label} exceeds maximum depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise ChoiceConsequenceOracleError(f"{label} numbers must be finite")
            return
        if type(item) is str:
            try:
                encoded = item.encode("utf-8")
            except UnicodeError as exc:
                raise ChoiceConsequenceOracleError(
                    f"{label} strings must be valid UTF-8"
                ) from exc
            if len(encoded) > MAX_TEXT_UTF8_BYTES:
                raise ChoiceConsequenceOracleError(f"{label} text is too large")
            return
        if type(item) not in {dict, list}:
            raise ChoiceConsequenceOracleError(
                f"{label} must contain only plain JSON values"
            )
        identity = id(item)
        if identity in active:
            raise ChoiceConsequenceOracleError(f"{label} must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise ChoiceConsequenceOracleError(
                            f"{label} keys must be strings"
                        )
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ChoiceConsequenceOracleError(
            f"{label} could not be canonicalized"
        ) from exc


def _plain_text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ChoiceConsequenceOracleError(f"{label} must be nonempty text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise ChoiceConsequenceOracleError(f"{label} must be valid UTF-8") from exc
    if size > MAX_TEXT_UTF8_BYTES:
        raise ChoiceConsequenceOracleError(f"{label} is too large")
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ChoiceConsequenceOracleError(f"{label} is invalid")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ChoiceConsequenceOracleError(f"{label} must be a sequence")
    if len(value) > MAX_ITEMS:
        raise ChoiceConsequenceOracleError(f"{label} exceeds item limit")
    return list(value)


def _closed_mapping(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise ChoiceConsequenceOracleError(f"{label} fields mismatch")
    return value


def _normalize_assumptions(values: Any) -> list[dict[str, Any]]:
    assumptions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in _sequence(values, "assumptions"):
        item = _closed_mapping(value, _ASSUMPTION_FIELDS, "assumption")
        assumption_id = _identifier(item["assumption_id"], "assumption_id")
        if assumption_id in seen:
            raise ChoiceConsequenceOracleError("assumption_id values must be unique")
        seen.add(assumption_id)
        status = item["status"]
        if type(status) is not str or status not in ASSUMPTION_STATUSES:
            raise ChoiceConsequenceOracleError("assumption status is invalid")
        references = [
            _plain_text(reference, "evidence reference")
            for reference in _sequence(
                item["evidence_references"], "evidence_references"
            )
        ]
        if len(references) != len(set(references)):
            raise ChoiceConsequenceOracleError("evidence references must be unique")
        if status == "VERIFIED" and not references:
            raise ChoiceConsequenceOracleError(
                "verified assumption requires evidence references"
            )
        assumptions.append(
            {
                "assumption_id": assumption_id,
                "statement": _plain_text(item["statement"], "assumption statement"),
                "status": status,
                "evidence_references": sorted(references),
            }
        )
    return sorted(assumptions, key=lambda item: item["assumption_id"])


def _normalize_choices(
    values: Any, assumption_ids: set[str]
) -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    choice_ids: set[str] = set()
    consequence_ids: set[str] = set()
    for value in _sequence(values, "choices"):
        item = _closed_mapping(value, _CHOICE_FIELDS, "choice")
        choice_id = _identifier(item["choice_id"], "choice_id")
        if choice_id in choice_ids:
            raise ChoiceConsequenceOracleError("choice_id values must be unique")
        choice_ids.add(choice_id)
        consequences: list[dict[str, Any]] = []
        for raw in _sequence(item["consequences"], "consequences"):
            consequence = _closed_mapping(
                raw, _CONSEQUENCE_FIELDS, "consequence"
            )
            consequence_id = _identifier(
                consequence["consequence_id"], "consequence_id"
            )
            if consequence_id in consequence_ids:
                raise ChoiceConsequenceOracleError(
                    "consequence_id values must be globally unique"
                )
            consequence_ids.add(consequence_id)
            conditions = [
                _identifier(condition, "condition assumption id")
                for condition in _sequence(
                    consequence["condition_assumption_ids"],
                    "condition_assumption_ids",
                )
            ]
            if len(conditions) != len(set(conditions)):
                raise ChoiceConsequenceOracleError(
                    "condition assumption ids must be unique"
                )
            if any(condition not in assumption_ids for condition in conditions):
                raise ChoiceConsequenceOracleError(
                    "consequence references an unknown assumption_id"
                )
            valence = consequence["valence"]
            if type(valence) is not str or valence not in CONSEQUENCE_VALENCES:
                raise ChoiceConsequenceOracleError("consequence valence is invalid")
            consequences.append(
                {
                    "consequence_id": consequence_id,
                    "statement": _plain_text(
                        consequence["statement"], "consequence statement"
                    ),
                    "condition_assumption_ids": sorted(conditions),
                    "valence": valence,
                }
            )
        if not consequences:
            raise ChoiceConsequenceOracleError(
                "each choice requires at least one consequence"
            )
        choices.append(
            {
                "choice_id": choice_id,
                "action": _plain_text(item["action"], "choice action"),
                "consequences": sorted(
                    consequences, key=lambda result: result["consequence_id"]
                ),
            }
        )
    if len(choices) < 2:
        raise ChoiceConsequenceOracleError("at least two choices are required")
    return sorted(choices, key=lambda item: item["choice_id"])


def _branches(choices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "choice_id": choice["choice_id"],
            "consequence_id": consequence["consequence_id"],
            "statement": consequence["statement"],
            "condition_assumption_ids": consequence["condition_assumption_ids"],
            "valence": consequence["valence"],
            "status": "POSSIBLE_IF_ASSUMPTIONS_HOLD",
        }
        for choice in choices
        for consequence in choice["consequences"]
    ]


def build_choice_consequence_receipt(
    *,
    decision_id: str,
    observed_state: Any,
    assumptions: Sequence[Mapping[str, Any]],
    choices: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic, non-authorizing conditional scenario receipt."""
    normalized_state = _validate_json(observed_state, label="observed_state")
    normalized_assumptions = _normalize_assumptions(assumptions)
    normalized_choices = _normalize_choices(
        choices,
        {item["assumption_id"] for item in normalized_assumptions},
    )
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "decision_id": _identifier(decision_id, "decision_id"),
        "observed_state": normalized_state,
        "observed_state_hash": stable_hash(normalized_state),
        "assumptions": normalized_assumptions,
        "choices": normalized_choices,
        "scenario_branches": _branches(normalized_choices),
        "prediction_status": PREDICTION_STATUS,
        "recommended_choice_id": None,
        "probability_claimed": False,
        "causation_claimed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "A scenario branch records a declared possible consequence under "
            "named assumptions. It does not establish probability, causation, "
            "future occurrence, recommendation, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_choice_consequence_receipt(receipt: Mapping[str, Any]) -> bool:
    """Recompute the complete closed receipt and reject semantic tampering."""
    if type(receipt) is not dict:
        raise ChoiceConsequenceOracleError("receipt must be a plain object")
    _validate_json(receipt, label="receipt")
    if set(receipt) != _RECEIPT_FIELDS:
        raise ChoiceConsequenceOracleError("receipt fields mismatch")
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise ChoiceConsequenceOracleError("receipt schema mismatch")
    supplied_hash = receipt["receipt_hash"]
    if type(supplied_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", supplied_hash) is None:
        raise ChoiceConsequenceOracleError("receipt_hash is invalid")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if stable_hash(body) != supplied_hash:
        raise ChoiceConsequenceOracleError("receipt hash mismatch")
    expected = build_choice_consequence_receipt(
        decision_id=receipt["decision_id"],
        observed_state=receipt["observed_state"],
        assumptions=receipt["assumptions"],
        choices=receipt["choices"],
    )
    if dict(receipt) != expected:
        raise ChoiceConsequenceOracleError("receipt is internally inconsistent")
    return True
