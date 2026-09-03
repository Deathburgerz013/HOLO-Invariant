"""Time-scoped, evidence-derived truth states for HOLO/Sim.

Truth here is bounded to a declared claim, environment, observation time, state,
and verification receipts.  Later observations may differ without rewriting
what an earlier receipt established inside its original boundary.  An
unbounded future claim cannot be established by a present observation.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping, Sequence

from holosim.canonical import stable_hash


TRUTH_RECEIPT_TYPE = "time_scoped_truth_state_receipt"
TRUTH_RECEIPT_VERSION = 1
COMPARISON_RECEIPT_TYPE = "time_scoped_truth_comparison_receipt"
COMPARISON_RECEIPT_VERSION = 1
TRUTH_STATUSES = {"TRUE", "FALSE", "UNKNOWN"}
TEMPORAL_SCOPES = {"AT_OBSERVATION", "UNBOUNDED_FUTURE"}
CHECK_TYPES = {"EVIDENCE", "FORMAL_PROOF"}
VERIFICATION_STATUSES = {"VERIFIED", "INVALID", "UNAVAILABLE"}
OUTCOMES = {"SUPPORTS", "CONTRADICTS", "UNKNOWN"}
MAX_ITEMS = 10_000
MAX_TEXT_UTF8_BYTES = 16_384

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CLAIM_FIELDS = {"claim_id", "statement", "temporal_scope"}
_OBSERVATION_FIELDS = {
    "observation_id", "environment_id", "observed_at", "clock_id", "state_hash",
}
_CHECK_FIELDS = {
    "check_id", "check_type", "verification_receipt_hash",
    "verification_status", "outcome",
}
_TRUTH_FIELDS = {
    "type", "version", "claim", "observation", "checks", "checks_hash",
    "truth_status", "status_reason", "bounded_truth_established",
    "global_truth_claimed", "future_truth_claimed", "accepted",
    "write_authority", "execution_authority", "interpretation_notice",
    "receipt_hash",
}
_COMPARISON_FIELDS = {
    "type", "version", "claim_id", "prior_receipt_hash", "current_receipt_hash",
    "prior_observed_at", "current_observed_at", "prior_truth_status",
    "current_truth_status", "relation", "historical_rewritten",
    "accepted", "write_authority", "execution_authority",
    "interpretation_notice", "receipt_hash",
}


class TimeScopedTruthError(ValueError):
    """Raised when a truth-state input or receipt violates the contract."""


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise TimeScopedTruthError(f"{label} must be nonempty text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise TimeScopedTruthError(f"{label} must be valid UTF-8") from exc
    if size > MAX_TEXT_UTF8_BYTES:
        raise TimeScopedTruthError(f"{label} is too large")
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise TimeScopedTruthError(f"{label} is invalid")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise TimeScopedTruthError(f"{label} must be a SHA-256 hex digest")
    return value


def _timestamp(value: Any, label: str) -> str:
    text = _text(value, label)
    parse_value = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError as exc:
        raise TimeScopedTruthError(f"{label} must be valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TimeScopedTruthError(f"{label} must include an explicit timezone")
    return text


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def _closed(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise TimeScopedTruthError(f"{label} fields mismatch")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TimeScopedTruthError(f"{label} must be a sequence")
    if len(value) > MAX_ITEMS:
        raise TimeScopedTruthError(f"{label} exceeds item limit")
    return list(value)


def _normalize_claim(value: Any) -> dict[str, str]:
    item = _closed(value, _CLAIM_FIELDS, "claim")
    temporal_scope = item["temporal_scope"]
    if type(temporal_scope) is not str or temporal_scope not in TEMPORAL_SCOPES:
        raise TimeScopedTruthError("temporal_scope is invalid")
    return {
        "claim_id": _identifier(item["claim_id"], "claim_id"),
        "statement": _text(item["statement"], "claim statement"),
        "temporal_scope": temporal_scope,
    }


def _normalize_observation(value: Any) -> dict[str, str]:
    item = _closed(value, _OBSERVATION_FIELDS, "observation")
    return {
        "observation_id": _identifier(item["observation_id"], "observation_id"),
        "environment_id": _identifier(item["environment_id"], "environment_id"),
        "observed_at": _timestamp(item["observed_at"], "observed_at"),
        "clock_id": _identifier(item["clock_id"], "clock_id"),
        "state_hash": _sha256(item["state_hash"], "state_hash"),
    }


def _normalize_checks(values: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in _sequence(values, "checks"):
        item = _closed(raw, _CHECK_FIELDS, "check")
        check_id = _identifier(item["check_id"], "check_id")
        if check_id in seen:
            raise TimeScopedTruthError("check_id values must be unique")
        seen.add(check_id)
        check_type = item["check_type"]
        verification_status = item["verification_status"]
        outcome = item["outcome"]
        if type(check_type) is not str or check_type not in CHECK_TYPES:
            raise TimeScopedTruthError("check_type is invalid")
        if (
            type(verification_status) is not str
            or verification_status not in VERIFICATION_STATUSES
        ):
            raise TimeScopedTruthError("verification_status is invalid")
        if type(outcome) is not str or outcome not in OUTCOMES:
            raise TimeScopedTruthError("check outcome is invalid")
        if verification_status != "VERIFIED" and outcome != "UNKNOWN":
            raise TimeScopedTruthError(
                "unverified checks must have UNKNOWN outcome"
            )
        result.append({
            "check_id": check_id,
            "check_type": check_type,
            "verification_receipt_hash": _sha256(
                item["verification_receipt_hash"], "verification_receipt_hash"
            ),
            "verification_status": verification_status,
            "outcome": outcome,
        })
    if not result:
        raise TimeScopedTruthError("at least one check is required")
    return sorted(result, key=lambda item: item["check_id"])


def _derive_truth(claim: Mapping[str, str], checks: Sequence[Mapping[str, str]]):
    if claim["temporal_scope"] == "UNBOUNDED_FUTURE":
        return "UNKNOWN", "UNBOUNDED_FUTURE_NOT_OBSERVED", False
    supports = [item for item in checks if item["outcome"] == "SUPPORTS"]
    contradicts = [item for item in checks if item["outcome"] == "CONTRADICTS"]
    unknown = [item for item in checks if item["outcome"] == "UNKNOWN"]
    if supports and not contradicts and not unknown:
        return "TRUE", "VERIFIED_SUPPORT_WITHOUT_CONTRADICTION", True
    if contradicts and not supports and not unknown:
        return "FALSE", "VERIFIED_CONTRADICTION_WITHOUT_SUPPORT", True
    if supports and contradicts:
        return "UNKNOWN", "CONFLICTING_VERIFIED_CHECKS", False
    if unknown:
        return "UNKNOWN", "UNRESOLVED_CHECKS_REMAIN", False
    return "UNKNOWN", "NO_DIRECTIONAL_VERIFIED_CHECK", False


def build_time_scoped_truth_receipt(
    *,
    claim: Mapping[str, Any],
    observation: Mapping[str, Any],
    checks: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive truth only inside one explicit observation boundary."""
    normalized_claim = _normalize_claim(claim)
    normalized_observation = _normalize_observation(observation)
    normalized_checks = _normalize_checks(checks)
    status, reason, established = _derive_truth(normalized_claim, normalized_checks)
    body = {
        "type": TRUTH_RECEIPT_TYPE,
        "version": TRUTH_RECEIPT_VERSION,
        "claim": normalized_claim,
        "observation": normalized_observation,
        "checks": normalized_checks,
        "checks_hash": stable_hash(normalized_checks),
        "truth_status": status,
        "status_reason": reason,
        "bounded_truth_established": established,
        "global_truth_claimed": False,
        "future_truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "TRUE or FALSE is established only for the declared claim, state, "
            "environment, observation time, and verified check receipts. The "
            "timestamp is caller-supplied unless independently attested. No "
            "present receipt establishes an unbounded future claim."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_time_scoped_truth_receipt(receipt: Mapping[str, Any]) -> bool:
    """Rebuild the closed truth receipt and reject semantic forgery."""
    if type(receipt) is not dict or set(receipt) != _TRUTH_FIELDS:
        raise TimeScopedTruthError("truth receipt fields mismatch")
    if (
        receipt["type"] != TRUTH_RECEIPT_TYPE
        or receipt["version"] != TRUTH_RECEIPT_VERSION
    ):
        raise TimeScopedTruthError("truth receipt schema mismatch")
    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if stable_hash(body) != supplied_hash:
        raise TimeScopedTruthError("truth receipt hash mismatch")
    expected = build_time_scoped_truth_receipt(
        claim=receipt["claim"],
        observation=receipt["observation"],
        checks=receipt["checks"],
    )
    if dict(receipt) != expected:
        raise TimeScopedTruthError("truth receipt is internally inconsistent")
    return True


def compare_time_scoped_truth_receipts(
    prior: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any]:
    """Relate two verified observations without rewriting either receipt."""
    verify_time_scoped_truth_receipt(prior)
    verify_time_scoped_truth_receipt(current)
    prior_claim = prior["claim"]
    current_claim = current["claim"]
    if prior_claim["claim_id"] != current_claim["claim_id"]:
        raise TimeScopedTruthError("truth comparison requires the same claim_id")
    if prior_claim["statement"] != current_claim["statement"]:
        raise TimeScopedTruthError("truth comparison requires the same statement")
    prior_at = prior["observation"]["observed_at"]
    current_at = current["observation"]["observed_at"]
    if _instant(current_at) < _instant(prior_at):
        raise TimeScopedTruthError("current observation cannot precede prior observation")
    relation = (
        "PRESERVED"
        if prior["truth_status"] == current["truth_status"]
        else "CHANGED"
    )
    body = {
        "type": COMPARISON_RECEIPT_TYPE,
        "version": COMPARISON_RECEIPT_VERSION,
        "claim_id": prior_claim["claim_id"],
        "prior_receipt_hash": prior["receipt_hash"],
        "current_receipt_hash": current["receipt_hash"],
        "prior_observed_at": prior_at,
        "current_observed_at": current_at,
        "prior_truth_status": prior["truth_status"],
        "current_truth_status": current["truth_status"],
        "relation": relation,
        "historical_rewritten": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "CHANGED means the bounded truth status differs between two ordered "
            "observations. It does not invalidate or rewrite the prior receipt."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_time_scoped_truth_comparison(receipt: Mapping[str, Any]) -> bool:
    """Validate the closed structural consistency of a comparison receipt."""
    if type(receipt) is not dict or set(receipt) != _COMPARISON_FIELDS:
        raise TimeScopedTruthError("comparison receipt fields mismatch")
    if (
        receipt["type"] != COMPARISON_RECEIPT_TYPE
        or receipt["version"] != COMPARISON_RECEIPT_VERSION
    ):
        raise TimeScopedTruthError("comparison receipt schema mismatch")
    _identifier(receipt["claim_id"], "claim_id")
    _sha256(receipt["prior_receipt_hash"], "prior_receipt_hash")
    _sha256(receipt["current_receipt_hash"], "current_receipt_hash")
    prior_at = _timestamp(receipt["prior_observed_at"], "prior_observed_at")
    current_at = _timestamp(receipt["current_observed_at"], "current_observed_at")
    if _instant(current_at) < _instant(prior_at):
        raise TimeScopedTruthError("current observation cannot precede prior observation")
    for field in ("prior_truth_status", "current_truth_status"):
        if receipt[field] not in TRUTH_STATUSES:
            raise TimeScopedTruthError(f"{field} is invalid")
    expected_relation = (
        "PRESERVED"
        if receipt["prior_truth_status"] == receipt["current_truth_status"]
        else "CHANGED"
    )
    if receipt["relation"] != expected_relation:
        raise TimeScopedTruthError("comparison relation is inconsistent")
    if (
        receipt["historical_rewritten"] is not False
        or receipt["accepted"] is not False
        or receipt["write_authority"] != "NONE"
        or receipt["execution_authority"] != "NONE"
    ):
        raise TimeScopedTruthError("comparison rewrites history or grants authority")
    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if stable_hash(body) != supplied_hash:
        raise TimeScopedTruthError("comparison receipt hash mismatch")
    return True
