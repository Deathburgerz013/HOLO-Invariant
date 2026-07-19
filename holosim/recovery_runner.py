"""Transport-neutral run records for model-recovery challenges.

This module exports a public challenge packet and records one caller-supplied
structured response.  It does not contact, authenticate, or identify a model;
interpret prose; execute tools; retry; accept a result; or grant authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping

from holosim.recovery import (
    RECOVERY_CHALLENGE_VERSION,
    RecoveryChallengeError,
    evaluate_recovery_response,
    public_recovery_packet,
    validate_recovery_evaluation,
)


RECOVERY_RUN_REQUEST_TYPE = "holo_model_recovery_run_request"
RECOVERY_RUN_RECEIPT_TYPE = "holo_model_recovery_run_receipt"
RECOVERY_RUNNER_VERSION = 1
MAX_TEXT_UTF8_BYTES = 16_384
MAX_JSON_DEPTH = 14
MAX_JSON_ITEMS = 20_000


class RecoveryRunnerError(ValueError):
    """Raised when a recovery run request or receipt fails closed."""


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
        raise RecoveryRunnerError("value could not be canonicalized") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validate_closed_json(value: Any, field: str) -> None:
    active: set[int] = set()
    count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_JSON_ITEMS:
            raise RecoveryRunnerError(f"{field} exceeds the JSON item limit")
        if depth > MAX_JSON_DEPTH:
            raise RecoveryRunnerError(f"{field} exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise RecoveryRunnerError(f"{field} numbers must be finite")
            return
        if type(item) is str:
            try:
                encoded = item.encode("utf-8")
            except UnicodeError as exc:
                raise RecoveryRunnerError(f"{field} strings must be valid UTF-8") from exc
            if len(encoded) > MAX_TEXT_UTF8_BYTES:
                raise RecoveryRunnerError(
                    f"{field} strings cannot exceed {MAX_TEXT_UTF8_BYTES} UTF-8 bytes"
                )
            return
        if type(item) not in {dict, list}:
            raise RecoveryRunnerError(f"{field} must contain only plain JSON values")
        identity = id(item)
        if identity in active:
            raise RecoveryRunnerError(f"{field} must not contain cycles")
        active.add(identity)
        try:
            children = item.items() if type(item) is dict else enumerate(item)
            for key, child in children:
                if type(item) is dict and type(key) is not str:
                    raise RecoveryRunnerError(
                        f"{field} object keys must be plain strings"
                    )
                visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _object(value: Any, field: str, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise RecoveryRunnerError(f"{field} must be a plain object")
    if set(value) != expected:
        raise RecoveryRunnerError(f"{field} fields do not match the versioned schema")
    return value


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise RecoveryRunnerError(f"{field} must be a nonempty plain string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise RecoveryRunnerError(f"{field} must be valid UTF-8") from exc
    if len(encoded) > MAX_TEXT_UTF8_BYTES:
        raise RecoveryRunnerError(
            f"{field} cannot exceed {MAX_TEXT_UTF8_BYTES} UTF-8 bytes"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RecoveryRunnerError(f"{field} must be 64 lowercase hex characters")
    return value


def _target(value: Any) -> dict[str, str]:
    root = _object(
        value,
        "declared_target",
        {"provider_label", "model_label", "model_version", "interface"},
    )
    return {key: _text(root[key], f"declared_target.{key}") for key in root}


def build_recovery_run_request(
    bundle: Mapping[str, Any],
    *,
    run_id: str,
    provider_label: str,
    model_label: str,
    model_version: str,
    interface: str,
) -> dict[str, Any]:
    """Export one public, transport-neutral request without private oracle data."""
    try:
        packet = public_recovery_packet(bundle)
    except RecoveryChallengeError as exc:
        raise RecoveryRunnerError("recovery bundle is invalid") from exc
    target = _target(
        {
            "provider_label": provider_label,
            "model_label": model_label,
            "model_version": model_version,
            "interface": interface,
        }
    )
    body = {
        "type": RECOVERY_RUN_REQUEST_TYPE,
        "version": RECOVERY_RUNNER_VERSION,
        "run_id": _text(run_id, "run_id"),
        "declared_target": target,
        "packet": packet,
        "transport_status": "NOT_SENT",
        "authentication_status": "NOT_AUTHENTICATED",
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Target labels are caller-supplied routing metadata. This request does "
            "not contact or authenticate a model, establish identity or memory, "
            "accept a result, or grant authority."
        ),
    }
    return {**body, "request_hash": _digest(body)}


def validate_recovery_run_request(
    bundle: Mapping[str, Any], request: Mapping[str, Any]
) -> None:
    """Fail closed unless a request is exactly bound to the public packet."""
    _validate_closed_json(request, "run request")
    root = _object(
        request,
        "run request",
        {
            "type",
            "version",
            "run_id",
            "declared_target",
            "packet",
            "transport_status",
            "authentication_status",
            "accepted",
            "write_authority",
            "interpretation_notice",
            "request_hash",
        },
    )
    if (
        root["type"] != RECOVERY_RUN_REQUEST_TYPE
        or type(root["version"]) is not int
        or root["version"] != RECOVERY_RUNNER_VERSION
    ):
        raise RecoveryRunnerError("run request type or version is invalid")
    _text(root["run_id"], "run_id")
    _target(root["declared_target"])
    if root["transport_status"] != "NOT_SENT":
        raise RecoveryRunnerError("run request transport status is invalid")
    if root["authentication_status"] != "NOT_AUTHENTICATED":
        raise RecoveryRunnerError("run request authentication status is invalid")
    if root["accepted"] is not False or root["write_authority"] != "NONE":
        raise RecoveryRunnerError("run request cannot grant acceptance or authority")
    _text(root["interpretation_notice"], "interpretation_notice")
    _sha256(root["request_hash"], "request_hash")
    try:
        expected_packet = public_recovery_packet(bundle)
    except RecoveryChallengeError as exc:
        raise RecoveryRunnerError("recovery bundle is invalid") from exc
    if root["packet"] != expected_packet:
        raise RecoveryRunnerError("run request packet does not match bundle")
    body = dict(root)
    request_hash = body.pop("request_hash")
    if _digest(body) != request_hash:
        raise RecoveryRunnerError("run request hash mismatch")


def record_recovery_run_response(
    bundle: Mapping[str, Any],
    request: Mapping[str, Any],
    response: Mapping[str, Any],
) -> dict[str, Any]:
    """Record one supplied structured response and its deterministic evaluation."""
    validate_recovery_run_request(bundle, request)
    _validate_closed_json(response, "run response")
    if type(response) is not dict:
        raise RecoveryRunnerError("run response must be a plain object")
    try:
        evaluation = evaluate_recovery_response(bundle, response)
    except RecoveryChallengeError as exc:
        raise RecoveryRunnerError("run response could not be evaluated") from exc
    response_copy = json.loads(json.dumps(response, ensure_ascii=False, allow_nan=False))
    body = {
        "type": RECOVERY_RUN_RECEIPT_TYPE,
        "version": RECOVERY_RUNNER_VERSION,
        "run_id": request["run_id"],
        "declared_target": json.loads(
            json.dumps(request["declared_target"], ensure_ascii=False)
        ),
        "request_hash": request["request_hash"],
        "challenge_hash": request["packet"]["challenge_hash"],
        "response": response_copy,
        "response_hash": _digest(response_copy),
        "evaluation": evaluation,
        "transport_status": "RESPONSE_SUPPLIED_BY_CALLER",
        "authentication_status": "NOT_AUTHENTICATED",
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This receipt records caller-supplied target labels and response data. "
            "It does not prove who or what produced the response, establish model "
            "identity or memory, accept the result, or grant authority."
        ),
    }
    return {**body, "receipt_hash": _digest(body)}


def validate_recovery_run_receipt(
    bundle: Mapping[str, Any],
    request: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    """Regenerate and validate a complete run receipt against its bundle/request."""
    validate_recovery_run_request(bundle, request)
    _validate_closed_json(receipt, "run receipt")
    root = _object(
        receipt,
        "run receipt",
        {
            "type",
            "version",
            "run_id",
            "declared_target",
            "request_hash",
            "challenge_hash",
            "response",
            "response_hash",
            "evaluation",
            "transport_status",
            "authentication_status",
            "accepted",
            "write_authority",
            "interpretation_notice",
            "receipt_hash",
        },
    )
    if (
        root["type"] != RECOVERY_RUN_RECEIPT_TYPE
        or type(root["version"]) is not int
        or root["version"] != RECOVERY_RUNNER_VERSION
    ):
        raise RecoveryRunnerError("run receipt type or version is invalid")
    if root["run_id"] != request["run_id"]:
        raise RecoveryRunnerError("run receipt run_id does not match request")
    if root["declared_target"] != request["declared_target"]:
        raise RecoveryRunnerError("run receipt target does not match request")
    if root["request_hash"] != request["request_hash"]:
        raise RecoveryRunnerError("run receipt request hash does not match request")
    if root["challenge_hash"] != request["packet"]["challenge_hash"]:
        raise RecoveryRunnerError("run receipt challenge hash does not match request")
    for field in ("request_hash", "challenge_hash", "response_hash", "receipt_hash"):
        _sha256(root[field], field)
    if type(root["response"]) is not dict:
        raise RecoveryRunnerError("run receipt response must be a plain object")
    if root["response_hash"] != _digest(root["response"]):
        raise RecoveryRunnerError("run receipt response hash mismatch")
    if root["transport_status"] != "RESPONSE_SUPPLIED_BY_CALLER":
        raise RecoveryRunnerError("run receipt transport status is invalid")
    if root["authentication_status"] != "NOT_AUTHENTICATED":
        raise RecoveryRunnerError("run receipt authentication status is invalid")
    if root["accepted"] is not False or root["write_authority"] != "NONE":
        raise RecoveryRunnerError("run receipt cannot grant acceptance or authority")
    _text(root["interpretation_notice"], "interpretation_notice")
    try:
        validate_recovery_evaluation(root["evaluation"])
        expected_evaluation = evaluate_recovery_response(bundle, root["response"])
    except RecoveryChallengeError as exc:
        raise RecoveryRunnerError("run receipt evaluation is invalid") from exc
    if root["evaluation"] != expected_evaluation:
        raise RecoveryRunnerError("run receipt evaluation is semantically inconsistent")
    body = dict(root)
    receipt_hash = body.pop("receipt_hash")
    if _digest(body) != receipt_hash:
        raise RecoveryRunnerError("run receipt hash mismatch")