"""Immutable, non-authoritative receipts for reopening completed episodes."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.environment_completion_evaluator import (
    CERTIFICATE_TYPE,
    CERTIFICATE_VERSION,
    COMPLETION_CERTIFICATE_FIELDS,
)
from holosim.environment_snapshot import verify_snapshot


REOPEN_RECEIPT_TYPE = "environment_episode_reopen_receipt"
REOPEN_RECEIPT_VERSION = 1
REOPEN_RELATION = "reopens"

RECEIPT_FIELDS = (
    "type",
    "version",
    "relation",
    "parent_certificate_id",
    "prior_episode_id",
    "reopened_episode_id",
    "environment_id",
    "trigger_snapshot_id",
    "reasons",
    "completion_certificate",
    "trigger_snapshot",
    "provenance",
    "accepted",
    "write_authority",
    "interpretation_notice",
)


class EpisodeReopenError(ValueError):
    """Raised when an episode-reopen receipt violates its contract."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EpisodeReopenError(f"{field} must be a nonempty string")
    return value.strip()


def _sha256(value: Any, field: str) -> str:
    normalized = _required_text(value, field)
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef"
        for character in normalized
    ):
        raise EpisodeReopenError(
            f"{field} must be lowercase SHA-256 hex"
        )
    return normalized


def _timestamp(value: Any, field: str) -> datetime:
    normalized = _required_text(value, field)
    parse_value = (
        normalized[:-1] + "+00:00"
        if normalized.endswith("Z")
        else normalized
    )
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError as exc:
        raise EpisodeReopenError(
            f"{field} must be a valid ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EpisodeReopenError(
            f"{field} must include an explicit timezone"
        )
    return parsed


def _reasons(values: Sequence[str]) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise EpisodeReopenError("reasons must be a list of strings")
    normalized = [_required_text(value, "reasons") for value in values]
    if not normalized:
        raise EpisodeReopenError("reasons cannot be empty")
    if len(set(normalized)) != len(normalized):
        raise EpisodeReopenError("reasons cannot contain duplicates")
    return sorted(normalized)


def _completion_certificate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EpisodeReopenError(
            "completion_certificate must be an object"
        )
    certificate = deepcopy(dict(value))
    missing = sorted(set(COMPLETION_CERTIFICATE_FIELDS) - set(certificate))
    extra = sorted(set(certificate) - set(COMPLETION_CERTIFICATE_FIELDS))
    if missing:
        raise EpisodeReopenError(
            "completion certificate is missing fields: "
            + ", ".join(missing)
        )
    if extra:
        raise EpisodeReopenError(
            "completion certificate has unsupported fields: "
            + ", ".join(extra)
        )
    if certificate.get("type") != CERTIFICATE_TYPE:
        raise EpisodeReopenError("completion certificate type is invalid")
    if certificate.get("version") != CERTIFICATE_VERSION:
        raise EpisodeReopenError("completion certificate version is invalid")
    if certificate.get("status") != "COMPLETE_ELIGIBLE":
        raise EpisodeReopenError(
            "completion certificate must be COMPLETE_ELIGIBLE"
        )
    if certificate.get("evaluation_eligible") is not True:
        raise EpisodeReopenError(
            "completion certificate must be evaluation eligible"
        )
    if certificate.get("accepted") is not False:
        raise EpisodeReopenError(
            "completion certificate must remain non-accepting"
        )
    if certificate.get("write_authority") != "NONE":
        raise EpisodeReopenError(
            "completion certificate must have no write authority"
        )

    certificate_id = _sha256(
        certificate.get("certificate_id"),
        "completion_certificate.certificate_id",
    )
    try:
        expected_id = stable_hash(
            {
                key: item
                for key, item in certificate.items()
                if key != "certificate_id"
            }
        )
    except CanonicalValueError as exc:
        raise EpisodeReopenError(str(exc)) from exc
    if certificate_id != expected_id:
        raise EpisodeReopenError("completion certificate identity mismatch")

    _required_text(certificate.get("episode_id"), "certificate.episode_id")
    _required_text(
        certificate.get("environment_id"),
        "certificate.environment_id",
    )
    _timestamp(certificate.get("window_end"), "certificate.window_end")
    return certificate


def _trigger_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EpisodeReopenError("trigger_snapshot must be an object")
    snapshot = deepcopy(dict(value))
    verification = verify_snapshot(snapshot)
    if not verification["valid"]:
        details = "; ".join(verification["violations"])
        raise EpisodeReopenError(f"trigger snapshot is invalid: {details}")
    return snapshot


def _provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise EpisodeReopenError("provenance must be a nonempty object")
    normalized = deepcopy(dict(value))
    try:
        stable_hash(normalized)
    except CanonicalValueError as exc:
        raise EpisodeReopenError(str(exc)) from exc
    return normalized


def create_reopen_receipt(
    *,
    completion_certificate: Mapping[str, Any],
    trigger_snapshot: Mapping[str, Any],
    relation: str,
    reasons: Sequence[str],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind a completed episode to a distinct later observation episode."""
    certificate = _completion_certificate(completion_certificate)
    snapshot = _trigger_snapshot(trigger_snapshot)
    normalized_relation = _required_text(relation, "relation")
    if normalized_relation != REOPEN_RELATION:
        raise EpisodeReopenError("relation must be reopens")
    normalized_reasons = _reasons(reasons)
    normalized_provenance = _provenance(provenance)

    prior_episode_id = certificate["episode_id"]
    reopened_episode_id = snapshot["episode_id"]
    if reopened_episode_id == prior_episode_id:
        raise EpisodeReopenError(
            "reopened episode must have a distinct episode_id"
        )
    if snapshot["environment_id"] != certificate["environment_id"]:
        raise EpisodeReopenError(
            "trigger snapshot must reference the same environment"
        )
    if _timestamp(snapshot["observed_at"], "trigger_snapshot.observed_at") <= (
        _timestamp(certificate["window_end"], "certificate.window_end")
    ):
        raise EpisodeReopenError(
            "trigger snapshot must be later than the completed window"
        )

    payload: dict[str, Any] = {
        "type": REOPEN_RECEIPT_TYPE,
        "version": REOPEN_RECEIPT_VERSION,
        "relation": REOPEN_RELATION,
        "parent_certificate_id": certificate["certificate_id"],
        "prior_episode_id": prior_episode_id,
        "reopened_episode_id": reopened_episode_id,
        "environment_id": certificate["environment_id"],
        "trigger_snapshot_id": snapshot["snapshot_id"],
        "reasons": normalized_reasons,
        "completion_certificate": certificate,
        "trigger_snapshot": snapshot,
        "provenance": normalized_provenance,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This receipt records evidence that reopened a completed "
            "observation boundary. It does not invalidate the earlier "
            "certificate relative to its recorded window, establish truth, "
            "accept a correction, or authorize mutation."
        ),
    }
    try:
        receipt_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise EpisodeReopenError(str(exc)) from exc
    return {**payload, "receipt_id": receipt_id}


def verify_reopen_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Verify receipt structure, embedded lineage, and deterministic identity."""
    violations: list[str] = []
    expected_receipt_id: str | None = None
    actual_receipt_id = (
        receipt.get("receipt_id")
        if isinstance(receipt, Mapping)
        else None
    )

    try:
        if not isinstance(receipt, Mapping):
            raise EpisodeReopenError("receipt must be an object")
        missing = sorted(set(RECEIPT_FIELDS) - set(receipt))
        extra = sorted(
            set(receipt) - set(RECEIPT_FIELDS) - {"receipt_id"}
        )
        if missing:
            raise EpisodeReopenError(
                "receipt is missing fields: " + ", ".join(missing)
            )
        if extra:
            raise EpisodeReopenError(
                "receipt has unsupported fields: " + ", ".join(extra)
            )

        rebuilt = create_reopen_receipt(
            completion_certificate=receipt["completion_certificate"],
            trigger_snapshot=receipt["trigger_snapshot"],
            relation=receipt["relation"],
            reasons=receipt["reasons"],
            provenance=receipt["provenance"],
        )
        for field in RECEIPT_FIELDS:
            if receipt[field] != rebuilt[field]:
                raise EpisodeReopenError(
                    f"receipt field does not match embedded lineage: {field}"
                )
        expected_receipt_id = rebuilt["receipt_id"]
        _sha256(actual_receipt_id, "receipt_id")
        if actual_receipt_id != expected_receipt_id:
            raise EpisodeReopenError("reopen receipt identity mismatch")
    except (EpisodeReopenError, CanonicalValueError) as exc:
        violations.append(str(exc))

    return {
        "valid": not violations,
        "receipt_id": actual_receipt_id,
        "expected_receipt_id": expected_receipt_id,
        "violations": violations,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Verification establishes receipt structure and lineage only; "
            "it does not establish observation truth or authorize mutation."
        ),
    }
