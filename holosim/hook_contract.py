"""Generic, read-only hook request/result envelopes for Holo/Sim.

The hook contract preserves correspondence between a runtime request and returned
observations. It does not execute hooks, grant authority, apply mutations, or
establish that returned evidence is true.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping

HOOK_REQUEST_TYPE = "holo_hook_request"
HOOK_RESULT_TYPE = "holo_hook_result"
HOOK_VERSION = 1
MAX_JSON_DEPTH = 8


class HookContractError(ValueError):
    """Raised when hook envelopes are malformed or inconsistent."""


def _closed_json(value: Any) -> None:
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > MAX_JSON_DEPTH:
            raise HookContractError("value exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int, str}:
            if type(item) is str:
                try:
                    item.encode("utf-8")
                except UnicodeError as exc:
                    raise HookContractError("strings must be valid UTF-8") from exc
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise HookContractError("numbers must be finite")
            return
        if type(item) not in {dict, list}:
            raise HookContractError("values must contain only plain JSON types")
        identity = id(item)
        if identity in active:
            raise HookContractError("values must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise HookContractError("object keys must be strings")
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _digest(value: Mapping[str, Any]) -> str:
    _closed_json(value)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise HookContractError("hook envelope could not be canonicalized") from exc
    return hashlib.sha256(encoded).hexdigest()


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise HookContractError(f"{field} must be a nonempty plain string")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise HookContractError(f"{field} must be valid UTF-8") from exc
    return value


def build_hook_request(
    *,
    hook_id: str,
    action: str,
    reference: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a deterministic request envelope without executing any hook."""
    checked_hook_id = _text(hook_id, "hook_id")
    checked_action = _text(action, "action")
    checked_reference = _text(reference, "reference")
    if type(payload) is not dict:
        raise HookContractError("payload must be a plain dictionary")
    _closed_json(payload)

    body: dict[str, Any] = {
        "type": HOOK_REQUEST_TYPE,
        "version": HOOK_VERSION,
        "hook_id": checked_hook_id,
        "action": checked_action,
        "reference": checked_reference,
        "payload": dict(payload),
        "accepted": False,
        "write_authority": "NONE",
        "execution_status": "NOT_EXECUTED",
        "interpretation_notice": (
            "A hook request describes requested work only. It does not execute a hook, "
            "authorize mutation, establish truth, acceptance, or write authority."
        ),
    }
    return {**body, "request_hash": _digest(body)}


def validate_hook_request(request: Mapping[str, Any]) -> bool:
    if type(request) is not dict:
        raise HookContractError("request must be a plain dictionary")
    _closed_json(request)
    expected = {
        "type", "version", "hook_id", "action", "reference", "payload",
        "accepted", "write_authority", "execution_status",
        "interpretation_notice", "request_hash",
    }
    if set(request) != expected:
        raise HookContractError("request fields do not match the versioned schema")
    if request["type"] != HOOK_REQUEST_TYPE or request["version"] != HOOK_VERSION:
        raise HookContractError("request type or version is invalid")
    _text(request["hook_id"], "hook_id")
    _text(request["action"], "action")
    _text(request["reference"], "reference")
    if type(request["payload"]) is not dict:
        raise HookContractError("payload must be a plain dictionary")
    if request["accepted"] is not False or request["write_authority"] != "NONE":
        raise HookContractError("hook request cannot grant acceptance or write authority")
    if request["execution_status"] != "NOT_EXECUTED":
        raise HookContractError("hook request cannot claim execution")
    if type(request["interpretation_notice"]) is not str:
        raise HookContractError("interpretation_notice must be a string")
    digest = request["request_hash"]
    if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise HookContractError("request_hash must be a SHA-256 hex digest")
    body = dict(request)
    body.pop("request_hash")
    if _digest(body) != digest:
        raise HookContractError("request hash mismatch")
    return True


def build_hook_result(
    *,
    request: Mapping[str, Any],
    status: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind returned evidence to one validated hook request."""
    validate_hook_request(request)
    checked_status = _text(status, "status")
    if checked_status not in {"OBSERVED", "FAILED", "UNAVAILABLE"}:
        raise HookContractError("status must be OBSERVED, FAILED, or UNAVAILABLE")
    if type(evidence) is not dict:
        raise HookContractError("evidence must be a plain dictionary")
    _closed_json(evidence)

    body: dict[str, Any] = {
        "type": HOOK_RESULT_TYPE,
        "version": HOOK_VERSION,
        "hook_id": request["hook_id"],
        "action": request["action"],
        "reference": request["reference"],
        "request_hash": request["request_hash"],
        "status": checked_status,
        "evidence": dict(evidence),
        "accepted": False,
        "write_authority": "NONE",
        "mutation_applied": False,
        "interpretation_notice": (
            "A hook result records returned evidence bound to one request. It does not "
            "establish truth, acceptance, write authority, or prove that a mutation occurred."
        ),
    }
    return {**body, "result_hash": _digest(body)}


def validate_hook_result(
    result: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
) -> bool:
    validate_hook_request(request)
    if type(result) is not dict:
        raise HookContractError("result must be a plain dictionary")
    _closed_json(result)
    expected = {
        "type", "version", "hook_id", "action", "reference", "request_hash",
        "status", "evidence", "accepted", "write_authority", "mutation_applied",
        "interpretation_notice", "result_hash",
    }
    if set(result) != expected:
        raise HookContractError("result fields do not match the versioned schema")
    if result["type"] != HOOK_RESULT_TYPE or result["version"] != HOOK_VERSION:
        raise HookContractError("result type or version is invalid")
    if result["hook_id"] != request["hook_id"]:
        raise HookContractError("result hook_id does not match request")
    if result["action"] != request["action"]:
        raise HookContractError("result action does not match request")
    if result["reference"] != request["reference"]:
        raise HookContractError("result reference does not match request")
    if result["request_hash"] != request["request_hash"]:
        raise HookContractError("result is bound to a different request")
    if result["status"] not in {"OBSERVED", "FAILED", "UNAVAILABLE"}:
        raise HookContractError("result status is invalid")
    if type(result["evidence"]) is not dict:
        raise HookContractError("evidence must be a plain dictionary")
    if result["accepted"] is not False or result["write_authority"] != "NONE":
        raise HookContractError("hook result cannot grant acceptance or write authority")
    if result["mutation_applied"] is not False:
        raise HookContractError("hook result cannot claim mutation through this contract")
    if type(result["interpretation_notice"]) is not str:
        raise HookContractError("interpretation_notice must be a string")
    digest = result["result_hash"]
    if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise HookContractError("result_hash must be a SHA-256 hex digest")
    body = dict(result)
    body.pop("result_hash")
    if _digest(body) != digest:
        raise HookContractError("result hash mismatch")
    return True
