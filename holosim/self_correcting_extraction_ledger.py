"""Append-only, evidence-bound extraction with explicit stop conditions.

The ledger records how one observed source relates to prior extracted meaning.
It preserves problems, solutions, evidence, corrections, conflicts, and reopen
lineage without treating an extraction as truth, acceptance, or authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.hook_contract import (
    HookContractError,
    validate_hook_request,
    validate_hook_result,
)


LEDGER_TYPE = "self_correcting_extraction_ledger"
ENTRY_TYPE = "self_correcting_extraction"
VERSION = 1

RELATIONSHIPS = {
    "ADD",
    "SAME",
    "CORRECT",
    "CONFLICT",
    "UNKNOWN",
    "REOPEN",
    "NO_NEW_DISTINCTION",
}

LEDGER_FIELDS = {
    "type",
    "version",
    "ledger_id",
    "objective_id",
    "context_id",
    "entries",
    "head_extraction_id",
    "active_extraction_ids",
    "decision",
    "stop_condition",
    "truth_claimed",
    "accepted",
    "write_authority",
    "interpretation_notice",
    "ledger_hash",
}

ENTRY_FIELDS = {
    "type",
    "version",
    "extraction_index",
    "previous_extraction_id",
    "parent_extraction_id",
    "relationship",
    "meaning_id",
    "problem",
    "solution",
    "request",
    "observation_result",
    "source_result_hash",
    "recheck_conditions",
    "truth_claimed",
    "accepted",
    "write_authority",
    "interpretation_notice",
    "extraction_id",
}

LEDGER_NOTICE = (
    "This ledger records evidence-bound extraction lineage only. It does not "
    "establish truth, acceptance, provenance independence, write authority, or "
    "permission to act."
)

ENTRY_NOTICE = (
    "This extraction records one declared relationship to observed evidence. "
    "The relationship remains non-authoritative and may be corrected or reopened "
    "only by an appended successor."
)


class ExtractionLedgerError(ValueError):
    """Raised when extraction evidence or ledger lineage fails closed."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise ExtractionLedgerError(str(exc)) from exc


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ExtractionLedgerError(f"{field} must be a nonempty plain string")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ExtractionLedgerError(f"{field} must be valid UTF-8") from exc
    return value


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _plain_object(value: Any, field: str, *, allow_empty: bool = False) -> dict:
    if type(value) is not dict or (not value and not allow_empty):
        qualifier = "plain dictionary" if allow_empty else "nonempty plain dictionary"
        raise ExtractionLedgerError(f"{field} must be a {qualifier}")
    _hash(value)
    return deepcopy(value)


def _conditions(value: Any) -> list[str]:
    if type(value) not in {list, tuple}:
        raise ExtractionLedgerError("recheck_conditions must be a list or tuple")
    checked = [_text(item, "recheck condition") for item in value]
    if len(set(checked)) != len(checked):
        raise ExtractionLedgerError("recheck_conditions must not contain duplicates")
    return sorted(checked)


def _no_authority(value: Mapping[str, Any], field: str) -> None:
    if (
        value.get("truth_claimed") is not False
        or value.get("accepted") is not False
        or value.get("write_authority") != "NONE"
    ):
        raise ExtractionLedgerError(f"{field} cannot grant authority")


def _ledger_body(
    *,
    ledger_id: str,
    objective_id: str,
    context_id: str,
    entries: list[dict[str, Any]],
    head_extraction_id: str | None,
    active_extraction_ids: list[str],
    decision: str,
    stop_condition: str | None,
) -> dict[str, Any]:
    return {
        "type": LEDGER_TYPE,
        "version": VERSION,
        "ledger_id": ledger_id,
        "objective_id": objective_id,
        "context_id": context_id,
        "entries": deepcopy(entries),
        "head_extraction_id": head_extraction_id,
        "active_extraction_ids": list(active_extraction_ids),
        "decision": decision,
        "stop_condition": stop_condition,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": LEDGER_NOTICE,
    }


def _finish_ledger(**kwargs: Any) -> dict[str, Any]:
    body = _ledger_body(**kwargs)
    return {**body, "ledger_hash": _hash(body)}


def build_extraction_ledger(
    *, ledger_id: str, objective_id: str, context_id: str
) -> dict[str, Any]:
    """Build an empty deterministic extraction ledger."""
    return _finish_ledger(
        ledger_id=_text(ledger_id, "ledger_id"),
        objective_id=_text(objective_id, "objective_id"),
        context_id=_text(context_id, "context_id"),
        entries=[],
        head_extraction_id=None,
        active_extraction_ids=[],
        decision="CONTINUE",
        stop_condition=None,
    )


def _check_relationship(
    *,
    relationship: str,
    meaning_id: str | None,
    solution: dict[str, Any] | None,
    parent_extraction_id: str | None,
    recheck_conditions: list[str],
    entries_by_id: Mapping[str, Mapping[str, Any]],
    active_ids: Sequence[str],
    evidence_status: str,
) -> None:
    if relationship not in RELATIONSHIPS:
        raise ExtractionLedgerError("relationship is not declared by this version")

    parent = entries_by_id.get(parent_extraction_id) if parent_extraction_id else None
    requires_solution = {"ADD", "SAME", "CORRECT", "CONFLICT", "REOPEN"}
    if relationship in requires_solution and solution is None:
        raise ExtractionLedgerError(f"{relationship} requires a solution")
    if relationship in {"UNKNOWN", "NO_NEW_DISTINCTION"} and solution is not None:
        raise ExtractionLedgerError(f"{relationship} cannot invent a solution")
    if evidence_status != "OBSERVED" and relationship not in {
        "UNKNOWN",
        "NO_NEW_DISTINCTION",
    }:
        raise ExtractionLedgerError(
            "failed or unavailable evidence cannot establish a meaningful relationship"
        )

    if relationship in {"ADD", "NO_NEW_DISTINCTION", "UNKNOWN"}:
        if parent_extraction_id is not None:
            raise ExtractionLedgerError(f"{relationship} cannot declare a parent")
    elif parent is None:
        label = "active parent" if relationship in {"SAME", "CORRECT", "CONFLICT"} else "parent"
        raise ExtractionLedgerError(f"{relationship} requires an existing {label}")

    if relationship in {"SAME", "CORRECT", "CONFLICT"} and parent_extraction_id not in active_ids:
        raise ExtractionLedgerError(f"{relationship} requires an existing active parent")
    if relationship == "REOPEN" and parent is not None and parent["relationship"] not in {
        "UNKNOWN",
        "CONFLICT",
        "SAME",
        "NO_NEW_DISTINCTION",
    }:
        raise ExtractionLedgerError("REOPEN requires a prior stopped extraction")

    if relationship == "NO_NEW_DISTINCTION":
        if meaning_id is not None:
            raise ExtractionLedgerError("NO_NEW_DISTINCTION cannot declare meaning_id")
    elif meaning_id is None:
        raise ExtractionLedgerError(f"{relationship} requires meaning_id")

    if parent is not None and meaning_id != parent["meaning_id"]:
        raise ExtractionLedgerError("successor meaning_id must match its parent")
    if relationship in {"CONFLICT", "UNKNOWN"} and not recheck_conditions:
        raise ExtractionLedgerError(f"{relationship} requires recheck_conditions")


def _append_checked(
    *,
    ledger: Mapping[str, Any],
    relationship: str,
    meaning_id: str | None,
    problem: Mapping[str, Any],
    solution: Mapping[str, Any] | None,
    request: Mapping[str, Any],
    observation_result: Mapping[str, Any],
    parent_extraction_id: str | None,
    recheck_conditions: Sequence[str],
) -> dict[str, Any]:
    checked_relationship = _text(relationship, "relationship")
    checked_meaning = _optional_text(meaning_id, "meaning_id")
    checked_parent = _optional_text(parent_extraction_id, "parent_extraction_id")
    checked_problem = _plain_object(problem, "problem")
    checked_solution = (
        None if solution is None else _plain_object(solution, "solution")
    )
    checked_conditions = _conditions(recheck_conditions)
    try:
        validate_hook_request(request)
        validate_hook_result(observation_result, request=request)
    except HookContractError as exc:
        raise ExtractionLedgerError(f"observation evidence is invalid: {exc}") from exc

    entries = deepcopy(ledger["entries"])
    active_ids = list(ledger["active_extraction_ids"])
    entries_by_id = {entry["extraction_id"]: entry for entry in entries}
    _check_relationship(
        relationship=checked_relationship,
        meaning_id=checked_meaning,
        solution=checked_solution,
        parent_extraction_id=checked_parent,
        recheck_conditions=checked_conditions,
        entries_by_id=entries_by_id,
        active_ids=active_ids,
        evidence_status=observation_result["status"],
    )

    entry_body = {
        "type": ENTRY_TYPE,
        "version": VERSION,
        "extraction_index": len(entries) + 1,
        "previous_extraction_id": ledger["head_extraction_id"],
        "parent_extraction_id": checked_parent,
        "relationship": checked_relationship,
        "meaning_id": checked_meaning,
        "problem": checked_problem,
        "solution": checked_solution,
        "request": deepcopy(dict(request)),
        "observation_result": deepcopy(dict(observation_result)),
        "source_result_hash": observation_result["result_hash"],
        "recheck_conditions": checked_conditions,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": ENTRY_NOTICE,
    }
    entry = {**entry_body, "extraction_id": _hash(entry_body)}
    entries.append(entry)

    if checked_relationship == "ADD":
        active_ids.append(entry["extraction_id"])
        decision, stop = "CONTINUE", None
    elif checked_relationship == "CORRECT":
        active_ids = [item for item in active_ids if item != checked_parent]
        active_ids.append(entry["extraction_id"])
        decision, stop = "CONTINUE", None
    elif checked_relationship == "REOPEN":
        retired_ids: set[str] = set()
        lineage_id = checked_parent
        while lineage_id is not None:
            if lineage_id in active_ids:
                retired_ids.add(lineage_id)
            lineage_entry = entries_by_id.get(lineage_id)
            lineage_id = (
                lineage_entry["parent_extraction_id"]
                if lineage_entry is not None
                else None
            )
        active_ids = [item for item in active_ids if item not in retired_ids]
        active_ids.append(entry["extraction_id"])
        decision, stop = "CONTINUE", None
    elif checked_relationship in {"SAME", "NO_NEW_DISTINCTION"}:
        decision, stop = "STOP", "NO_NEW_DISTINCTION"
    elif checked_relationship == "CONFLICT":
        decision, stop = "STOP", "CONTRADICTION_REQUIRES_REVIEW"
    else:
        decision, stop = "STOP", "BLOCKED_BY_UNCERTAINTY"

    return _finish_ledger(
        ledger_id=ledger["ledger_id"],
        objective_id=ledger["objective_id"],
        context_id=ledger["context_id"],
        entries=entries,
        head_extraction_id=entry["extraction_id"],
        active_extraction_ids=active_ids,
        decision=decision,
        stop_condition=stop,
    )


def append_extraction(
    *,
    ledger: Mapping[str, Any],
    relationship: str,
    meaning_id: str | None,
    problem: Mapping[str, Any],
    solution: Mapping[str, Any] | None,
    request: Mapping[str, Any],
    observation_result: Mapping[str, Any],
    parent_extraction_id: str | None,
    recheck_conditions: Sequence[str],
) -> dict[str, Any]:
    """Return a successor ledger without mutating the supplied ledger."""
    validate_extraction_ledger(ledger)
    return _append_checked(
        ledger=ledger,
        relationship=relationship,
        meaning_id=meaning_id,
        problem=problem,
        solution=solution,
        request=request,
        observation_result=observation_result,
        parent_extraction_id=parent_extraction_id,
        recheck_conditions=recheck_conditions,
    )


def validate_extraction_ledger(ledger: Mapping[str, Any]) -> bool:
    """Replay the ledger and require exact schema, evidence, and lineage."""
    if type(ledger) is not dict:
        raise ExtractionLedgerError("ledger must be a plain dictionary")
    if set(ledger) != LEDGER_FIELDS:
        raise ExtractionLedgerError("ledger fields do not match the versioned schema")
    if ledger.get("type") != LEDGER_TYPE or ledger.get("version") != VERSION:
        raise ExtractionLedgerError("ledger type or version is invalid")
    _no_authority(ledger, "ledger")
    if ledger.get("interpretation_notice") != LEDGER_NOTICE:
        raise ExtractionLedgerError("ledger interpretation_notice is invalid")
    _text(ledger.get("ledger_id"), "ledger_id")
    _text(ledger.get("objective_id"), "objective_id")
    _text(ledger.get("context_id"), "context_id")
    if type(ledger.get("entries")) is not list:
        raise ExtractionLedgerError("entries must be a list")
    if type(ledger.get("active_extraction_ids")) is not list:
        raise ExtractionLedgerError("active_extraction_ids must be a list")

    body = dict(ledger)
    claimed_hash = body.pop("ledger_hash")
    if type(claimed_hash) is not str or _hash(body) != claimed_hash:
        raise ExtractionLedgerError("ledger hash mismatch")

    replayed = build_extraction_ledger(
        ledger_id=ledger["ledger_id"],
        objective_id=ledger["objective_id"],
        context_id=ledger["context_id"],
    )
    for supplied in ledger["entries"]:
        if type(supplied) is not dict or set(supplied) != ENTRY_FIELDS:
            raise ExtractionLedgerError(
                "entry fields do not match the versioned schema"
            )
        if supplied.get("type") != ENTRY_TYPE or supplied.get("version") != VERSION:
            raise ExtractionLedgerError("entry type or version is invalid")
        _no_authority(supplied, "entry")
        if supplied.get("interpretation_notice") != ENTRY_NOTICE:
            raise ExtractionLedgerError("entry interpretation_notice is invalid")
        rebuilt = _append_checked(
            ledger=replayed,
            relationship=supplied["relationship"],
            meaning_id=supplied["meaning_id"],
            problem=supplied["problem"],
            solution=supplied["solution"],
            request=supplied["request"],
            observation_result=supplied["observation_result"],
            parent_extraction_id=supplied["parent_extraction_id"],
            recheck_conditions=supplied["recheck_conditions"],
        )
        if rebuilt["entries"][-1] != supplied:
            raise ExtractionLedgerError(
                "entry does not match its evidence or declared lineage"
            )
        replayed = rebuilt

    if replayed != ledger:
        raise ExtractionLedgerError("ledger does not match replayed extraction history")
    return True
