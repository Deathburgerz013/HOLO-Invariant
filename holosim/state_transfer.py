"""Version-bound, read-only state transfer envelopes.

Hashes in this module bind canonical bytes and internal relationships. They do
not prove truth, authorship, execution, consensus, acceptance, or authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from typing import Any


STATE_TRANSFER_TYPE = "holo_invariant_state_transfer"
STATE_TRANSFER_OBSERVATION_TYPE = "holo_invariant_state_transfer_observation"
STATE_TRANSFER_VERSION = 1
MAX_TEXT_UTF8_BYTES = 16_384
MAX_JSON_DEPTH = 12
MAX_JSON_ITEMS = 20_000
MAX_INVARIANT_IDS = 256
MAX_COMMANDS = 256
MAX_ARTIFACTS = 1_024
MAX_KNOWN_STATE_HASHES = 4_096


class StateTransferError(ValueError):
    """Raised when an envelope or observation fails closed."""


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
        raise StateTransferError("value could not be canonicalized") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validate_closed_json(value: Any, field: str) -> None:
    active: set[int] = set()
    count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_JSON_ITEMS:
            raise StateTransferError(f"{field} exceeds the JSON item limit")
        if depth > MAX_JSON_DEPTH:
            raise StateTransferError(f"{field} exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise StateTransferError(f"{field} numbers must be finite")
            return
        if type(item) is str:
            try:
                encoded = item.encode("utf-8")
            except UnicodeError as exc:
                raise StateTransferError(f"{field} strings must be valid UTF-8") from exc
            if len(encoded) > MAX_TEXT_UTF8_BYTES:
                raise StateTransferError(
                    f"{field} strings cannot exceed {MAX_TEXT_UTF8_BYTES} UTF-8 bytes"
                )
            return
        if type(item) not in {dict, list}:
            raise StateTransferError(f"{field} must contain only plain JSON values")
        identity = id(item)
        if identity in active:
            raise StateTransferError(f"{field} must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise StateTransferError(
                            f"{field} object keys must be plain strings"
                        )
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _object(value: Any, field: str, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise StateTransferError(f"{field} must be a plain object")
    if set(value) != expected:
        raise StateTransferError(f"{field} fields do not match the versioned schema")
    return value


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise StateTransferError(f"{field} must be a nonempty plain string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise StateTransferError(f"{field} must be valid UTF-8") from exc
    if len(encoded) > MAX_TEXT_UTF8_BYTES:
        raise StateTransferError(
            f"{field} cannot exceed {MAX_TEXT_UTF8_BYTES} UTF-8 bytes"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise StateTransferError(f"{field} must be 64 lowercase hex characters")
    return value


def _materialize_texts(
    values: Iterable[str], field: str, maximum: int
) -> list[str]:
    if isinstance(values, (str, bytes, Mapping)):
        raise StateTransferError(f"{field} must be an iterable of strings")
    try:
        items = list(values)
    except (TypeError, RuntimeError) as exc:
        raise StateTransferError(f"{field} could not be materialized") from exc
    if len(items) > maximum:
        raise StateTransferError(f"{field} exceeds its item limit")
    result = [_text(item, f"{field}[{index}]") for index, item in enumerate(items)]
    if len(result) != len(set(result)):
        raise StateTransferError(f"{field} values must be unique")
    return result


def _copy_json(value: Any, field: str) -> Any:
    _validate_closed_json(value, field)
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise StateTransferError(f"{field} could not be copied") from exc


def _normalize_sender(value: Any) -> dict[str, str]:
    root = _object(
        value,
        "declared_sender",
        {"provider_label", "model_label", "model_version", "interface"},
    )
    return {key: _text(root[key], f"declared_sender.{key}") for key in root}


def _normalize_evidence(value: Any) -> dict[str, Any]:
    root = _object(
        value,
        "evidence",
        {"commands", "observed_results", "artifact_hashes", "execution_status"},
    )
    commands = _materialize_texts(root["commands"], "evidence.commands", MAX_COMMANDS)
    results = _materialize_texts(
        root["observed_results"], "evidence.observed_results", MAX_COMMANDS
    )
    if len(commands) != len(results):
        raise StateTransferError("evidence commands and results must have equal length")
    artifacts = root["artifact_hashes"]
    if type(artifacts) is not dict or any(type(key) is not str for key in artifacts):
        raise StateTransferError("evidence.artifact_hashes must be a plain object")
    if len(artifacts) > MAX_ARTIFACTS:
        raise StateTransferError("evidence.artifact_hashes exceeds its item limit")
    normalized_artifacts: dict[str, str] = {}
    for path, digest in artifacts.items():
        normalized_artifacts[_text(path, "evidence artifact path")] = _sha256(
            digest, f"evidence artifact hash for {path!r}"
        )
    status = _text(root["execution_status"], "evidence.execution_status")
    if status not in {"NOT_RUN", "CALLER_REPORTED"}:
        raise StateTransferError("evidence execution status is invalid")
    if status == "NOT_RUN" and (commands or results):
        raise StateTransferError("NOT_RUN evidence cannot contain commands or results")
    if status == "CALLER_REPORTED" and not commands:
        raise StateTransferError(
            "CALLER_REPORTED evidence requires a command and observed result"
        )
    return {
        "commands": commands,
        "observed_results": results,
        "artifact_hashes": normalized_artifacts,
        "execution_status": status,
    }


def build_state_transfer(
    *,
    transfer_id: str,
    base_snapshot: Any,
    payload: Any,
    applied_invariant_ids: Iterable[str],
    evidence: Mapping[str, Any],
    declared_sender: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a self-contained transfer envelope without applying its payload."""
    base_copy = _copy_json(base_snapshot, "base_snapshot")
    payload_copy = _copy_json(payload, "payload")
    invariants = _materialize_texts(
        applied_invariant_ids, "applied_invariant_ids", MAX_INVARIANT_IDS
    )
    if not invariants:
        raise StateTransferError("applied_invariant_ids must not be empty")
    normalized_evidence = _normalize_evidence(evidence)
    sender = _normalize_sender(declared_sender)
    body = {
        "type": STATE_TRANSFER_TYPE,
        "version": STATE_TRANSFER_VERSION,
        "transfer_id": _text(transfer_id, "transfer_id"),
        "base_snapshot": base_copy,
        "base_state_hash": _digest(base_copy),
        "payload": payload_copy,
        "payload_hash": _digest(payload_copy),
        "applied_invariant_ids": invariants,
        "evidence": normalized_evidence,
        "declared_sender": sender,
        "authentication_status": "NOT_AUTHENTICATED",
        "application_status": "NOT_APPLIED",
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Hashes bind canonical bytes and internal relationships only. This "
            "envelope does not prove truth, authorship, execution, consensus, "
            "acceptance, application, or authority."
        ),
    }
    return {**body, "envelope_hash": _digest(body)}


def validate_state_transfer(envelope: Mapping[str, Any]) -> None:
    """Fail closed unless an envelope is structurally and internally consistent."""
    _validate_closed_json(envelope, "state transfer envelope")
    root = _object(
        envelope,
        "state transfer envelope",
        {
            "type",
            "version",
            "transfer_id",
            "base_snapshot",
            "base_state_hash",
            "payload",
            "payload_hash",
            "applied_invariant_ids",
            "evidence",
            "declared_sender",
            "authentication_status",
            "application_status",
            "accepted",
            "write_authority",
            "interpretation_notice",
            "envelope_hash",
        },
    )
    if (
        root["type"] != STATE_TRANSFER_TYPE
        or type(root["version"]) is not int
        or root["version"] != STATE_TRANSFER_VERSION
    ):
        raise StateTransferError("state transfer type or version is invalid")
    _text(root["transfer_id"], "transfer_id")
    _sha256(root["base_state_hash"], "base_state_hash")
    _sha256(root["payload_hash"], "payload_hash")
    _sha256(root["envelope_hash"], "envelope_hash")
    if root["base_state_hash"] != _digest(root["base_snapshot"]):
        raise StateTransferError("base state hash mismatch")
    if root["payload_hash"] != _digest(root["payload"]):
        raise StateTransferError("payload hash mismatch")
    _materialize_texts(
        root["applied_invariant_ids"], "applied_invariant_ids", MAX_INVARIANT_IDS
    )
    _normalize_evidence(root["evidence"])
    _normalize_sender(root["declared_sender"])
    if root["authentication_status"] != "NOT_AUTHENTICATED":
        raise StateTransferError("authentication status is invalid")
    if root["application_status"] != "NOT_APPLIED":
        raise StateTransferError("application status is invalid")
    if root["accepted"] is not False or root["write_authority"] != "NONE":
        raise StateTransferError("state transfer cannot grant acceptance or authority")
    _text(root["interpretation_notice"], "interpretation_notice")
    body = dict(root)
    envelope_hash = body.pop("envelope_hash")
    if _digest(body) != envelope_hash:
        raise StateTransferError("state transfer envelope hash mismatch")


def observe_state_transfer(
    envelope: Mapping[str, Any],
    *,
    receiver_snapshot: Any | None,
    known_state_hashes: Iterable[str] = (),
) -> dict[str, Any]:
    """Classify base-state relationship without applying or accepting payload."""
    validate_state_transfer(envelope)
    known = _materialize_texts(
        known_state_hashes, "known_state_hashes", MAX_KNOWN_STATE_HASHES
    )
    for index, digest in enumerate(known):
        _sha256(digest, f"known_state_hashes[{index}]")
    if receiver_snapshot is None:
        receiver_hash = None
        status = "UNAVAILABLE"
    else:
        receiver_copy = _copy_json(receiver_snapshot, "receiver_snapshot")
        receiver_hash = _digest(receiver_copy)
        if receiver_hash == envelope["base_state_hash"]:
            status = "CURRENT"
        elif envelope["base_state_hash"] in known:
            status = "STALE"
        else:
            status = "CONFLICT"
    body = {
        "type": STATE_TRANSFER_OBSERVATION_TYPE,
        "version": STATE_TRANSFER_VERSION,
        "transfer_id": envelope["transfer_id"],
        "envelope_hash": envelope["envelope_hash"],
        "base_state_hash": envelope["base_state_hash"],
        "receiver_state_hash": receiver_hash,
        "known_state_hashes": known,
        "known_state_hashes_hash": _digest(known),
        "state_status": status,
        "payload_applied": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "State status compares canonical hashes only. CURRENT does not prove "
            "truth, endorse the payload, apply it, establish consensus, accept "
            "the transfer, or grant authority."
        ),
    }
    return {**body, "observation_hash": _digest(body)}


def validate_state_transfer_observation(
    envelope: Mapping[str, Any], observation: Mapping[str, Any]
) -> None:
    """Validate and semantically regenerate a receiver observation."""
    validate_state_transfer(envelope)
    _validate_closed_json(observation, "state transfer observation")
    root = _object(
        observation,
        "state transfer observation",
        {
            "type",
            "version",
            "transfer_id",
            "envelope_hash",
            "base_state_hash",
            "receiver_state_hash",
            "known_state_hashes",
            "known_state_hashes_hash",
            "state_status",
            "payload_applied",
            "accepted",
            "write_authority",
            "interpretation_notice",
            "observation_hash",
        },
    )
    if (
        root["type"] != STATE_TRANSFER_OBSERVATION_TYPE
        or type(root["version"]) is not int
        or root["version"] != STATE_TRANSFER_VERSION
    ):
        raise StateTransferError("state transfer observation type or version is invalid")
    if root["transfer_id"] != envelope["transfer_id"]:
        raise StateTransferError("observation transfer_id does not match envelope")
    if root["envelope_hash"] != envelope["envelope_hash"]:
        raise StateTransferError("observation envelope hash does not match envelope")
    if root["base_state_hash"] != envelope["base_state_hash"]:
        raise StateTransferError("observation base hash does not match envelope")
    for field in ("envelope_hash", "base_state_hash", "known_state_hashes_hash", "observation_hash"):
        _sha256(root[field], field)
    receiver_hash = root["receiver_state_hash"]
    if receiver_hash is not None:
        _sha256(receiver_hash, "receiver_state_hash")
    known = _materialize_texts(
        root["known_state_hashes"], "known_state_hashes", MAX_KNOWN_STATE_HASHES
    )
    for index, digest in enumerate(known):
        _sha256(digest, f"known_state_hashes[{index}]")
    if root["known_state_hashes_hash"] != _digest(known):
        raise StateTransferError("known state hashes hash mismatch")
    if receiver_hash is None:
        expected_status = "UNAVAILABLE"
    elif receiver_hash == envelope["base_state_hash"]:
        expected_status = "CURRENT"
    elif envelope["base_state_hash"] in known:
        expected_status = "STALE"
    else:
        expected_status = "CONFLICT"
    if root["state_status"] != expected_status:
        raise StateTransferError("state transfer status is semantically inconsistent")
    if root["payload_applied"] is not False:
        raise StateTransferError("observation cannot claim payload application")
    if root["accepted"] is not False or root["write_authority"] != "NONE":
        raise StateTransferError("observation cannot grant acceptance or authority")
    _text(root["interpretation_notice"], "interpretation_notice")
    body = dict(root)
    observation_hash = body.pop("observation_hash")
    if _digest(body) != observation_hash:
        raise StateTransferError("state transfer observation hash mismatch")