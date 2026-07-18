"""Version-bound theory states for possibility-driven navigation.

A theory state preserves what could be happening, what would test it, what
has been checked, and what remains missing. Surviving checks never promote a
theory to truth or proof. A contradiction may falsify the supplied theory.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping


THEORY_STATE_TYPE = "holo_theory_state_observation"
THEORY_STATE_VERSION = 1
MAX_THEORY_ITEMS = 100_000
MAX_TEXT_UTF8_BYTES = 16_384
MAX_RECEIPT_JSON_DEPTH = 10
CHECK_OUTCOMES = {"CONSISTENT", "CONTRADICTED", "UNAVAILABLE"}


class TheoryStateError(ValueError):
    """Raised when theory inputs or receipts are malformed."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise TheoryStateError("value could not be canonicalized") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _plain_text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise TheoryStateError(f"{field} must be a nonempty plain string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise TheoryStateError(f"{field} must be valid UTF-8") from exc
    if len(encoded) > MAX_TEXT_UTF8_BYTES:
        raise TheoryStateError(
            f"{field} cannot exceed {MAX_TEXT_UTF8_BYTES} UTF-8 bytes"
        )
    return value


def _plain_keys(value: dict[Any, Any], field: str) -> tuple[str, ...]:
    keys = tuple(value.keys())
    if any(type(key) is not str for key in keys):
        raise TheoryStateError(f"{field} keys must be plain strings")
    return keys


def _materialize(values: Iterable[Any], field: str) -> list[Any]:
    if type(values) in {str, bytes, bytearray}:
        raise TheoryStateError(f"{field} must be a collection, not text or bytes")
    try:
        iterator = iter(values)
    except Exception as exc:
        raise TheoryStateError(f"{field} must be iterable") from exc
    result: list[Any] = []
    try:
        for _ in range(MAX_THEORY_ITEMS + 1):
            try:
                result.append(next(iterator))
            except StopIteration:
                return result
    except Exception as exc:
        raise TheoryStateError(f"{field} could not be materialized") from exc
    raise TheoryStateError(f"{field} cannot exceed {MAX_THEORY_ITEMS} items")


def _normalize_string_list(values: Any, field: str) -> list[str]:
    result = _materialize(values, field)
    return [_plain_text(value, f"{field}[{index}]") for index, value in enumerate(result)]


def _normalize_predictions(values: Any) -> list[dict[str, str]]:
    predictions: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in _materialize(values, "predictions"):
        if type(value) is not dict:
            raise TheoryStateError("each prediction must be a plain object")
        keys = _plain_keys(value, "prediction")
        if set(keys) != {"prediction_id", "statement"}:
            raise TheoryStateError(
                "prediction fields must be prediction_id and statement"
            )
        prediction_id = _plain_text(value["prediction_id"], "prediction_id")
        if prediction_id in seen:
            raise TheoryStateError("prediction_id values must be unique")
        seen.add(prediction_id)
        predictions.append(
            {
                "prediction_id": prediction_id,
                "statement": _plain_text(value["statement"], "prediction statement"),
            }
        )
    return predictions


def _normalize_theory(theory: Any) -> dict[str, Any]:
    if type(theory) is not dict:
        raise TheoryStateError("theory must be a plain object")
    keys = _plain_keys(theory, "theory")
    if set(keys) != {"theory_id", "statement", "basis", "predictions"}:
        raise TheoryStateError(
            "theory fields must be theory_id, statement, basis, and predictions"
        )
    return {
        "theory_id": _plain_text(theory["theory_id"], "theory_id"),
        "statement": _plain_text(theory["statement"], "theory statement"),
        "basis": _normalize_string_list(theory["basis"], "basis"),
        "predictions": _normalize_predictions(theory["predictions"]),
    }


def _normalize_checks(
    values: Any, prediction_ids: set[str]
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    seen: set[str] = set()
    required = {"check_id", "prediction_id", "outcome", "evidence", "method"}
    for value in _materialize(values, "checks"):
        if type(value) is not dict:
            raise TheoryStateError("each check must be a plain object")
        keys = _plain_keys(value, "check")
        if set(keys) != required:
            raise TheoryStateError(
                "check fields must be check_id, prediction_id, outcome, evidence, and method"
            )
        check_id = _plain_text(value["check_id"], "check_id")
        if check_id in seen:
            raise TheoryStateError("check_id values must be unique")
        seen.add(check_id)
        prediction_id = _plain_text(value["prediction_id"], "check prediction_id")
        if prediction_id not in prediction_ids:
            raise TheoryStateError("check references an unknown prediction_id")
        outcome = value["outcome"]
        if type(outcome) is not str or outcome not in CHECK_OUTCOMES:
            raise TheoryStateError(
                "outcome must be CONSISTENT, CONTRADICTED, or UNAVAILABLE"
            )
        checks.append(
            {
                "check_id": check_id,
                "prediction_id": prediction_id,
                "outcome": outcome,
                "evidence": _plain_text(value["evidence"], "check evidence"),
                "method": _plain_text(value["method"], "check method"),
            }
        )
    return checks


def _derive_navigation(
    theory: dict[str, Any], checks: list[dict[str, str]]
) -> dict[str, Any]:
    prediction_ids = [item["prediction_id"] for item in theory["predictions"]]
    resolved = {
        check["prediction_id"]
        for check in checks
        if check["outcome"] in {"CONSISTENT", "CONTRADICTED"}
    }
    contradicted = [
        check["check_id"] for check in checks if check["outcome"] == "CONTRADICTED"
    ]
    unavailable = [
        check["check_id"] for check in checks if check["outcome"] == "UNAVAILABLE"
    ]
    unchecked = [item for item in prediction_ids if item not in resolved]

    if not prediction_ids:
        state = "UNTESTABLE"
        next_action = "DEFINE_PREDICTION"
    elif contradicted:
        state = "FALSIFIED"
        next_action = "REVISE_OR_REPLACE_THEORY"
    else:
        state = "POSSIBLE"
        next_action = (
            f"CHECK:{unchecked[0]}" if unchecked else "SEEK_NEW_FALSIFIER"
        )

    return {
        "state": state,
        "checked_prediction_ids": [item for item in prediction_ids if item in resolved],
        "unchecked_prediction_ids": unchecked,
        "contradicting_check_ids": contradicted,
        "unavailable_check_ids": unavailable,
        "next_missing_check": unchecked[0] if unchecked else None,
        "next_action": next_action,
    }


def evaluate_theory_state(theory: Any, checks: Iterable[Any]) -> dict[str, Any]:
    """Return a read-only state and navigation receipt for one theory."""
    normalized_theory = _normalize_theory(theory)
    prediction_ids = {
        item["prediction_id"] for item in normalized_theory["predictions"]
    }
    normalized_checks = _normalize_checks(checks, prediction_ids)
    body = {
        "type": THEORY_STATE_TYPE,
        "version": THEORY_STATE_VERSION,
        "theory": normalized_theory,
        "theory_hash": _digest(normalized_theory),
        "checks": normalized_checks,
        "check_hashes": [_digest(check) for check in normalized_checks],
        **_derive_navigation(normalized_theory, normalized_checks),
        "current": True,
        "stale_reason": None,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "POSSIBLE means not falsified by the supplied checks. It does not mean "
            "true, proven, probable, accepted, or authorized. Evidence authenticity "
            "and mathematical validity are not established by this receipt."
        ),
    }
    return {**body, "receipt_hash": _digest(body)}


def _validate_closed_json(value: Any) -> None:
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > MAX_RECEIPT_JSON_DEPTH:
            raise TheoryStateError("receipt exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if item != item or item in {float("inf"), float("-inf")}:
                raise TheoryStateError("receipt numbers must be finite")
            return
        if type(item) is str:
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise TheoryStateError("receipt strings must be valid UTF-8") from exc
            return
        if type(item) not in {dict, list}:
            raise TheoryStateError("receipt must contain only plain JSON values")
        identity = id(item)
        if identity in active:
            raise TheoryStateError("receipt must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise TheoryStateError("receipt object keys must be plain strings")
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _validate_theory_receipt(receipt: Mapping[str, Any]) -> None:
    if type(receipt) is not dict:
        raise TheoryStateError("receipt must be a plain object")
    _validate_closed_json(receipt)
    expected_fields = {
        "type",
        "version",
        "theory",
        "theory_hash",
        "checks",
        "check_hashes",
        "state",
        "checked_prediction_ids",
        "unchecked_prediction_ids",
        "contradicting_check_ids",
        "unavailable_check_ids",
        "next_missing_check",
        "next_action",
        "current",
        "stale_reason",
        "accepted",
        "write_authority",
        "interpretation_notice",
        "receipt_hash",
    }
    if set(receipt) != expected_fields:
        raise TheoryStateError("receipt fields do not match the versioned schema")
    if receipt["type"] != THEORY_STATE_TYPE:
        raise TheoryStateError("receipt type is invalid")
    if type(receipt["version"]) is not int or receipt["version"] != THEORY_STATE_VERSION:
        raise TheoryStateError("receipt version is invalid")
    if receipt["accepted"] is not False:
        raise TheoryStateError("receipt cannot grant acceptance")
    if receipt["write_authority"] != "NONE":
        raise TheoryStateError("receipt cannot grant write authority")
    receipt_hash = receipt["receipt_hash"]
    if type(receipt_hash) is not str or not re.fullmatch(r"[0-9a-f]{64}", receipt_hash):
        raise TheoryStateError("receipt_hash must be 64 lowercase hex characters")
    body = dict(receipt)
    body.pop("receipt_hash")
    if _digest(body) != receipt_hash:
        raise TheoryStateError("receipt hash mismatch")
    if type(receipt["checks"]) is not list:
        raise TheoryStateError("receipt checks must be a list")
    expected = evaluate_theory_state(receipt["theory"], receipt["checks"])
    if dict(receipt) != expected:
        raise TheoryStateError("receipt is internally inconsistent")


def check_theory_receipt_current(
    receipt: Mapping[str, Any], theory: Any, checks: Iterable[Any]
) -> dict[str, Any]:
    """Check whether a theory receipt still binds the supplied state."""
    _validate_theory_receipt(receipt)
    normalized_theory = _normalize_theory(theory)
    if _digest(normalized_theory) != receipt["theory_hash"]:
        return {"current": False, "stale_reason": "THEORY_CHANGED"}
    prediction_ids = {
        item["prediction_id"] for item in normalized_theory["predictions"]
    }
    normalized_checks = _normalize_checks(checks, prediction_ids)
    check_hashes = [_digest(check) for check in normalized_checks]
    if check_hashes != receipt["check_hashes"]:
        return {"current": False, "stale_reason": "CHECK_HISTORY_CHANGED"}
    expected = evaluate_theory_state(normalized_theory, normalized_checks)
    if expected != dict(receipt):
        return {"current": False, "stale_reason": "OBSERVATION_CHANGED"}
    return {"current": True, "stale_reason": None}