"""Bounded invariant reflection receipts.

Reflection compares a verified prior receipt identity and a reflected current
state against an explicitly supplied invariant reference. It reports either
no verified difference or an explicit residual. It does not establish
subjective consciousness, mutate state, accept truth, or grant authority.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Mapping

from holosim.canonical import stable_hash


RECEIPT_TYPE = "invariant_reflection_receipt"
RECEIPT_VERSION = 1
EVIDENCE_STATUSES = {"VERIFIED", "UNVERIFIED", "UNAVAILABLE"}
INTERPRETATION_NOTICE = (
    "Invariant reflection means a verified reflected state was compared with "
    "an explicit invariant reference while preserving the identity of the "
    "verified prior receipt. It does not establish subjective consciousness, "
    "truth, acceptance, mutation, or execution authority."
)
MAX_JSON_DEPTH = 10
MAX_ITEMS = 10_000
MAX_TEXT_UTF8_BYTES = 16_384

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_SHA256 = re.compile(r"[0-9a-f]{64}")

_RECEIPT_FIELDS = {
    "type", "version", "reflection_id", "prior_receipt_hash",
    "invariant_id", "invariant_hash", "reflected_state_hash",
    "evidence_status", "reflection_status", "residual_paths",
    "residual_hash", "state_change_required",
    "subjective_consciousness_claimed", "truth_claimed", "accepted",
    "write_authority", "execution_authority", "interpretation_notice",
    "receipt_hash",
}


class InvariantReflectionError(ValueError):
    """Raised when reflection input or a receipt violates the contract."""


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise InvariantReflectionError(f"{label} is invalid")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise InvariantReflectionError(f"{label} must be SHA-256")
    return value


def _evidence_status(value: Any) -> str:
    if type(value) is not str or value not in EVIDENCE_STATUSES:
        raise InvariantReflectionError("evidence_status is invalid")
    return value


def _canonical(value: Any, *, label: str) -> Any:
    active: set[int] = set()
    count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_ITEMS:
            raise InvariantReflectionError(f"{label} exceeds item limit")
        if depth > MAX_JSON_DEPTH:
            raise InvariantReflectionError(f"{label} exceeds maximum depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise InvariantReflectionError(f"{label} numbers must be finite")
            return
        if type(item) is str:
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise InvariantReflectionError(
                    f"{label} strings must be valid UTF-8"
                ) from exc
            if size > MAX_TEXT_UTF8_BYTES:
                raise InvariantReflectionError(f"{label} text is too large")
            return
        if type(item) not in {dict, list}:
            raise InvariantReflectionError(
                f"{label} must contain only plain JSON values"
            )
        identity = id(item)
        if identity in active:
            raise InvariantReflectionError(f"{label} must not contain cycles")
        active.add(identity)
        try:
            values = item.items() if type(item) is dict else enumerate(item)
            for key, child in values:
                if type(item) is dict and type(key) is not str:
                    raise InvariantReflectionError(f"{label} keys must be strings")
                visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)
    try:
        return json.loads(json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ))
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise InvariantReflectionError(
            f"{label} could not be canonicalized"
        ) from exc


def _path_key(parent: str, key: str) -> str:
    return f"{parent}.{key}" if parent else key


def _path_index(parent: str, index: int) -> str:
    return f"{parent}[{index}]" if parent else f"[{index}]"


def _residual_paths(invariant: Any, reflected: Any, path: str = "") -> list[str]:
    if type(invariant) is not type(reflected):
        return [path or "$root"]
    if type(invariant) is dict:
        paths: list[str] = []
        for key in sorted(set(invariant) | set(reflected)):
            child = _path_key(path, key)
            if key not in invariant or key not in reflected:
                paths.append(child)
            else:
                paths.extend(_residual_paths(invariant[key], reflected[key], child))
        return paths
    if type(invariant) is list:
        paths = []
        length = max(len(invariant), len(reflected))
        for index in range(length):
            child = _path_index(path, index)
            if index >= len(invariant) or index >= len(reflected):
                paths.append(child)
            else:
                paths.extend(
                    _residual_paths(invariant[index], reflected[index], child)
                )
        return paths
    return [] if invariant == reflected else [path or "$root"]


def build_invariant_reflection_receipt(
    *,
    reflection_id: str,
    prior_receipt: Mapping[str, Any],
    invariant_id: str,
    invariant_state: Any,
    reflected_state: Any,
    evidence_status: str,
) -> dict[str, Any]:
    """Compare reflected verified state with an invariant without mutating it."""
    if type(prior_receipt) is not dict:
        raise InvariantReflectionError("prior_receipt must be a plain mapping")
    prior_hash = prior_receipt.get("receipt_hash")
    _sha256(prior_hash, "prior_receipt receipt_hash")
    prior_body = {
        key: value for key, value in prior_receipt.items() if key != "receipt_hash"
    }
    if stable_hash(prior_body) != prior_hash:
        raise InvariantReflectionError("prior_receipt hash mismatch")

    invariant = _canonical(invariant_state, label="invariant_state")
    status = _evidence_status(evidence_status)

    if status == "VERIFIED":
        reflected = _canonical(reflected_state, label="reflected_state")
        reflected_hash = stable_hash(reflected)
        paths = sorted(set(_residual_paths(invariant, reflected)))
        if paths:
            reflection_status = "RESIDUAL"
            residual_hash = stable_hash({
                "invariant_hash": stable_hash(invariant),
                "reflected_state_hash": reflected_hash,
                "residual_paths": paths,
            })
            state_change_required = True
        else:
            reflection_status = "INVARIANT"
            residual_hash = None
            state_change_required = False
    else:
        if reflected_state is not None:
            raise InvariantReflectionError(
                "unverified reflected_state must be null"
            )
        reflected_hash = None
        paths = None
        reflection_status = "UNKNOWN"
        residual_hash = None
        state_change_required = False

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "reflection_id": _identifier(reflection_id, "reflection_id"),
        "prior_receipt_hash": prior_hash,
        "invariant_id": _identifier(invariant_id, "invariant_id"),
        "invariant_hash": stable_hash(invariant),
        "reflected_state_hash": reflected_hash,
        "evidence_status": status,
        "reflection_status": reflection_status,
        "residual_paths": paths,
        "residual_hash": residual_hash,
        "state_change_required": state_change_required,
        "subjective_consciousness_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": INTERPRETATION_NOTICE,
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_invariant_reflection_receipt(receipt: Mapping[str, Any]) -> bool:
    """Validate closed structure, derived relations, identity, and boundaries."""
    if type(receipt) is not dict or set(receipt) != _RECEIPT_FIELDS:
        raise InvariantReflectionError("receipt fields mismatch")
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise InvariantReflectionError("receipt schema mismatch")

    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if stable_hash(body) != supplied_hash:
        raise InvariantReflectionError("receipt hash mismatch")

    _identifier(receipt["reflection_id"], "reflection_id")
    _identifier(receipt["invariant_id"], "invariant_id")
    _sha256(receipt["prior_receipt_hash"], "prior_receipt_hash")
    _sha256(receipt["invariant_hash"], "invariant_hash")
    status = _evidence_status(receipt["evidence_status"])

    reflected_hash = receipt["reflected_state_hash"]
    residual_hash = receipt["residual_hash"]
    paths = receipt["residual_paths"]
    reflection_status = receipt["reflection_status"]
    state_change = receipt["state_change_required"]

    if status == "VERIFIED":
        _sha256(reflected_hash, "reflected_state_hash")
        if type(paths) is not list or paths != sorted(set(paths)):
            raise InvariantReflectionError("residual_paths are invalid")
        if paths:
            if reflection_status != "RESIDUAL" or state_change is not True:
                raise InvariantReflectionError("derived reflection state is inconsistent")
            _sha256(residual_hash, "residual_hash")
            expected_residual_hash = stable_hash({
                "invariant_hash": receipt["invariant_hash"],
                "reflected_state_hash": reflected_hash,
                "residual_paths": paths,
            })
            if residual_hash != expected_residual_hash:
                raise InvariantReflectionError("residual identity mismatch")
        else:
            if (
                reflection_status != "INVARIANT"
                or residual_hash is not None
                or state_change is not False
            ):
                raise InvariantReflectionError("derived reflection state is inconsistent")
    else:
        if (
            reflected_hash is not None
            or paths is not None
            or reflection_status != "UNKNOWN"
            or residual_hash is not None
            or state_change is not False
        ):
            raise InvariantReflectionError("unverified reflection state is inconsistent")

    fixed = {
        "subjective_consciousness_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": INTERPRETATION_NOTICE,
    }
    if any(receipt[key] != value for key, value in fixed.items()):
        raise InvariantReflectionError("forbidden claim or authority")

    return True
