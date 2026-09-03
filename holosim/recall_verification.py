"""Exact, external verification of bounded recall claims.

This module compares a supplied candidate with a named external reference under
one canonical encoding.  It does not inspect model weights or claim memory,
truth, authorship, relevance, acceptance, or authority.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Mapping

from holosim.canonical import stable_hash


RECEIPT_TYPE = "verified_recall_claim_receipt"
RECEIPT_VERSION = 1
ENCODING = "canonical-json-v1"
ACCESS_STATUSES = {"AVAILABLE", "ABSENT", "INACCESSIBLE", "UNCERTAIN"}
RECALL_STATUSES = {"VALID", "INVALID", "UNKNOWN"}
MAX_ITEMS = 10_000
MAX_JSON_DEPTH = 10
MAX_TEXT_UTF8_BYTES = 1_048_576

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_RECEIPT_FIELDS = {
    "type", "version", "claim_id", "reference_id", "reference_version",
    "encoding", "reference_access_status", "expected_reference_hash",
    "observed_reference_hash", "candidate_access_status", "candidate_hash",
    "recall_status", "status_reason", "exact_match", "memory_claimed",
    "truth_claimed", "authorship_claimed", "relevance_claimed", "accepted",
    "write_authority", "execution_authority", "interpretation_notice",
    "receipt_hash",
}


class RecallVerificationError(ValueError):
    """Raised when recall input or a receipt violates the closed contract."""


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise RecallVerificationError(f"{label} is invalid")
    return value


def _sha256_or_none(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise RecallVerificationError(f"{label} must be a SHA-256 hex digest or null")
    return value


def _access_status(value: Any, label: str) -> str:
    if type(value) is not str or value not in ACCESS_STATUSES:
        raise RecallVerificationError(f"{label} is invalid")
    return value


def _canonical_value(value: Any, *, label: str) -> Any:
    active: set[int] = set()
    count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_ITEMS:
            raise RecallVerificationError(f"{label} exceeds item limit")
        if depth > MAX_JSON_DEPTH:
            raise RecallVerificationError(f"{label} exceeds maximum depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise RecallVerificationError(f"{label} numbers must be finite")
            return
        if type(item) is str:
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise RecallVerificationError(
                    f"{label} strings must be valid UTF-8"
                ) from exc
            if size > MAX_TEXT_UTF8_BYTES:
                raise RecallVerificationError(f"{label} text is too large")
            return
        if type(item) not in {dict, list}:
            raise RecallVerificationError(
                f"{label} must contain only plain JSON values"
            )
        identity = id(item)
        if identity in active:
            raise RecallVerificationError(f"{label} must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise RecallVerificationError(f"{label} keys must be strings")
                    visit(child, depth + 1)
            else:
                for child in item:
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
        raise RecallVerificationError(f"{label} could not be canonicalized") from exc


def _derive_status(
    *,
    reference_access_status: str,
    expected_reference_hash: str | None,
    observed_reference_hash: str | None,
    candidate_access_status: str,
    candidate_hash: str | None,
) -> tuple[str, str, bool | None]:
    if reference_access_status != "AVAILABLE":
        return "UNKNOWN", f"REFERENCE_{reference_access_status}", None
    if expected_reference_hash is None:
        return "UNKNOWN", "REFERENCE_HASH_UNAVAILABLE", None
    if observed_reference_hash != expected_reference_hash:
        return "UNKNOWN", "REFERENCE_CORRUPT", None
    if candidate_access_status != "AVAILABLE":
        return "UNKNOWN", f"CANDIDATE_{candidate_access_status}", None
    if candidate_hash == expected_reference_hash:
        return "VALID", "EXACT_HASH_MATCH", True
    return "INVALID", "EXACT_HASH_MISMATCH", False


def build_recall_verification_receipt(
    *,
    claim_id: str,
    reference_id: str,
    reference_version: str,
    reference_access_status: str,
    expected_reference_hash: str | None,
    reference_value: Any,
    candidate_access_status: str,
    candidate_value: Any,
    encoding: str = ENCODING,
) -> dict[str, Any]:
    """Compare values externally and emit hashes plus a bounded verdict."""
    if encoding != ENCODING:
        raise RecallVerificationError("encoding is unsupported")
    reference_access = _access_status(
        reference_access_status, "reference_access_status"
    )
    candidate_access = _access_status(
        candidate_access_status, "candidate_access_status"
    )
    expected_hash = _sha256_or_none(
        expected_reference_hash, "expected_reference_hash"
    )
    if reference_access == "AVAILABLE":
        reference = _canonical_value(reference_value, label="reference_value")
        observed_hash = stable_hash(reference)
    else:
        if reference_value is not None:
            raise RecallVerificationError(
                "unavailable reference_value must be null"
            )
        observed_hash = None
    if candidate_access == "AVAILABLE":
        candidate = _canonical_value(candidate_value, label="candidate_value")
        candidate_hash = stable_hash(candidate)
    else:
        if candidate_value is not None:
            raise RecallVerificationError(
                "unavailable candidate_value must be null"
            )
        candidate_hash = None
    status, reason, exact_match = _derive_status(
        reference_access_status=reference_access,
        expected_reference_hash=expected_hash,
        observed_reference_hash=observed_hash,
        candidate_access_status=candidate_access,
        candidate_hash=candidate_hash,
    )
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "claim_id": _identifier(claim_id, "claim_id"),
        "reference_id": _identifier(reference_id, "reference_id"),
        "reference_version": _identifier(reference_version, "reference_version"),
        "encoding": ENCODING,
        "reference_access_status": reference_access,
        "expected_reference_hash": expected_hash,
        "observed_reference_hash": observed_hash,
        "candidate_access_status": candidate_access,
        "candidate_hash": candidate_hash,
        "recall_status": status,
        "status_reason": reason,
        "exact_match": exact_match,
        "memory_claimed": False,
        "truth_claimed": False,
        "authorship_claimed": False,
        "relevance_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "VALID means exact identity with an intact named reference under "
            "canonical-json-v1. It does not prove internal model memory, truth, "
            "authorship, relevance, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_recall_verification_receipt(receipt: Mapping[str, Any]) -> bool:
    """Reject malformed, contradictory, tampered, or authority-bearing receipts."""
    if type(receipt) is not dict:
        raise RecallVerificationError("receipt must be a plain object")
    _canonical_value(receipt, label="receipt")
    if set(receipt) != _RECEIPT_FIELDS:
        raise RecallVerificationError("receipt fields mismatch")
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise RecallVerificationError("receipt schema mismatch")
    _identifier(receipt["claim_id"], "claim_id")
    _identifier(receipt["reference_id"], "reference_id")
    _identifier(receipt["reference_version"], "reference_version")
    if receipt["encoding"] != ENCODING:
        raise RecallVerificationError("encoding is unsupported")
    reference_access = _access_status(
        receipt["reference_access_status"], "reference_access_status"
    )
    candidate_access = _access_status(
        receipt["candidate_access_status"], "candidate_access_status"
    )
    expected_hash = _sha256_or_none(
        receipt["expected_reference_hash"], "expected_reference_hash"
    )
    observed_hash = _sha256_or_none(
        receipt["observed_reference_hash"], "observed_reference_hash"
    )
    candidate_hash = _sha256_or_none(receipt["candidate_hash"], "candidate_hash")
    if (reference_access == "AVAILABLE") != (observed_hash is not None):
        raise RecallVerificationError("reference access and hash are inconsistent")
    if (candidate_access == "AVAILABLE") != (candidate_hash is not None):
        raise RecallVerificationError("candidate access and hash are inconsistent")
    status, reason, exact_match = _derive_status(
        reference_access_status=reference_access,
        expected_reference_hash=expected_hash,
        observed_reference_hash=observed_hash,
        candidate_access_status=candidate_access,
        candidate_hash=candidate_hash,
    )
    if receipt["recall_status"] != status:
        raise RecallVerificationError("recall_status is inconsistent")
    if receipt["status_reason"] != reason:
        raise RecallVerificationError("status_reason is inconsistent")
    if receipt["exact_match"] is not exact_match:
        raise RecallVerificationError("exact_match is inconsistent")
    fixed = {
        "memory_claimed": False,
        "truth_claimed": False,
        "authorship_claimed": False,
        "relevance_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    if any(receipt[field] != value for field, value in fixed.items()):
        raise RecallVerificationError("receipt cannot claim memory or authority")
    supplied_hash = receipt["receipt_hash"]
    if type(supplied_hash) is not str or _SHA256.fullmatch(supplied_hash) is None:
        raise RecallVerificationError("receipt_hash is invalid")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if stable_hash(body) != supplied_hash:
        raise RecallVerificationError("receipt hash mismatch")
    return True
