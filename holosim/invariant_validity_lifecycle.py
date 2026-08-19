"""Immutable validity events and compact active-invariant projections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


EVENT_TYPE = "holo_invariant_validity_event"
EVENT_VERSION = 1
PROJECTION_TYPE = "holo_active_invariant_projection"
PROJECTION_VERSION = 1

VALID_STATUSES = {
    "INVARIANT",
    "ESTABLISHED",
    "CONTINGENT",
    "UNKNOWN",
    "SUPERSEDED",
    "INVALID",
    "LIQUIDATED",
}
ACTIVE_STABLE_STATUSES = {
    "INVARIANT",
    "ESTABLISHED",
}


class InvariantValidityLifecycleError(ValueError):
    """Raised when validity history or projection semantics are invalid."""


def _canonical_json(value: Any, *, label: str) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise InvariantValidityLifecycleError(
            f"{label} must contain only JSON values"
        ) from exc


def _canonical_hash(value: Any, *, label: str) -> str:
    return hashlib.sha256(
        _canonical_json(value, label=label).encode("utf-8")
    ).hexdigest()


def _closed_copy(value: Any, *, label: str) -> Any:
    return json.loads(_canonical_json(value, label=label))


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvariantValidityLifecycleError(
            f"{label} must be a non-empty string"
        )
    return value


def _optional_text(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, label=label)


def _evidence_list(value: Any) -> list[str]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or not value
    ):
        raise InvariantValidityLifecycleError(
            "evidence must be a non-empty sequence"
        )
    evidence: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _required_text(item, label=f"evidence[{index}]")
        if text in seen:
            raise InvariantValidityLifecycleError(
                "evidence must not contain duplicates"
            )
        seen.add(text)
        evidence.append(text)
    return sorted(evidence)


def _validate_status_environment(
    status: str,
    environment_fingerprint: str | None,
) -> None:
    if status not in VALID_STATUSES:
        raise InvariantValidityLifecycleError("status is invalid")
    if status == "CONTINGENT" and environment_fingerprint is None:
        raise InvariantValidityLifecycleError(
            "CONTINGENT status requires environment_fingerprint"
        )


def verify_validity_event(event: Mapping[str, Any]) -> bool:
    """Verify one event's identity and self-contained semantics."""
    if not isinstance(event, Mapping):
        raise InvariantValidityLifecycleError("event must be a mapping")
    closed = _closed_copy(dict(event), label="event")
    required_fields = {
        "type",
        "version",
        "sequence",
        "claim_id",
        "status",
        "reason",
        "evidence",
        "observed_at",
        "environment_fingerprint",
        "reopen_reference",
        "previous_event_hash",
        "accepted",
        "truth_claimed",
        "write_authority",
        "execution_authority",
        "canonical_mutation",
        "event_hash",
    }
    if set(closed) != required_fields:
        raise InvariantValidityLifecycleError("event fields are invalid")
    supplied_hash = closed.pop("event_hash")
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise InvariantValidityLifecycleError(
            "event_hash must be a non-empty string"
        )
    if _canonical_hash(closed, label="event") != supplied_hash:
        raise InvariantValidityLifecycleError("event hash mismatch")
    if closed["type"] != EVENT_TYPE:
        raise InvariantValidityLifecycleError("event type mismatch")
    if closed["version"] != EVENT_VERSION:
        raise InvariantValidityLifecycleError("event version mismatch")
    if (
        type(closed["sequence"]) is not int
        or closed["sequence"] < 1
    ):
        raise InvariantValidityLifecycleError(
            "sequence must be a positive integer"
        )
    _required_text(closed["claim_id"], label="claim_id")
    _required_text(closed["reason"], label="reason")
    _required_text(closed["observed_at"], label="observed_at")
    evidence = _evidence_list(closed["evidence"])
    if evidence != closed["evidence"]:
        raise InvariantValidityLifecycleError(
            "evidence is not canonical"
        )
    environment = _optional_text(
        closed["environment_fingerprint"],
        label="environment_fingerprint",
    )
    _optional_text(closed["reopen_reference"], label="reopen_reference")
    _optional_text(
        closed["previous_event_hash"],
        label="previous_event_hash",
    )
    _validate_status_environment(closed["status"], environment)
    bounded = {
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    for field, expected in bounded.items():
        if closed[field] != expected:
            raise InvariantValidityLifecycleError(
                f"invalid bounded field {field}"
            )
    return True


def _validate_history(
    history: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(history, (str, bytes)) or not isinstance(history, Sequence):
        raise InvariantValidityLifecycleError(
            "history must be a sequence"
        )
    closed_history: list[dict[str, Any]] = []
    latest_by_claim: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(history):
        if not isinstance(event, Mapping):
            raise InvariantValidityLifecycleError(
                f"history event {index} must be a mapping"
            )
        closed = _closed_copy(dict(event), label="event")
        verify_validity_event(closed)
        claim_id = closed["claim_id"]
        previous = latest_by_claim.get(claim_id)
        if previous is None:
            if closed["sequence"] != 1:
                raise InvariantValidityLifecycleError(
                    "first claim event must have sequence 1"
                )
            if closed["previous_event_hash"] is not None:
                raise InvariantValidityLifecycleError(
                    "first claim event cannot have previous_event_hash"
                )
            if closed["reopen_reference"] is not None:
                raise InvariantValidityLifecycleError(
                    "first claim event cannot reopen history"
                )
        else:
            if closed["sequence"] != previous["sequence"] + 1:
                raise InvariantValidityLifecycleError(
                    "claim event sequence is not contiguous"
                )
            if closed["previous_event_hash"] != previous["event_hash"]:
                raise InvariantValidityLifecycleError(
                    "previous event hash mismatch"
                )
            if previous["status"] == "LIQUIDATED":
                if (
                    closed["status"] != "UNKNOWN"
                    or closed["reopen_reference"]
                    != previous["event_hash"]
                ):
                    raise InvariantValidityLifecycleError(
                        "liquidated claim requires explicit reopen"
                    )
            elif closed["reopen_reference"] is not None:
                raise InvariantValidityLifecycleError(
                    "reopen_reference requires liquidated predecessor"
                )
        latest_by_claim[claim_id] = closed
        closed_history.append(closed)
    return closed_history


def append_validity_event(
    *,
    history: Sequence[Mapping[str, Any]],
    claim_id: str,
    status: str,
    reason: str,
    evidence: Sequence[str],
    observed_at: str,
    environment_fingerprint: str | None = None,
    reopen_reference: str | None = None,
) -> dict[str, Any]:
    """Build the next immutable event without mutating supplied history."""
    closed_history = _validate_history(history)
    claim = _required_text(claim_id, label="claim_id")
    status = _required_text(status, label="status")
    reason = _required_text(reason, label="reason")
    observed_at = _required_text(observed_at, label="observed_at")
    environment = _optional_text(
        environment_fingerprint,
        label="environment_fingerprint",
    )
    reopen = _optional_text(reopen_reference, label="reopen_reference")
    evidence_items = _evidence_list(evidence)
    _validate_status_environment(status, environment)

    claim_history = [event for event in closed_history if event["claim_id"] == claim]
    previous = claim_history[-1] if claim_history else None
    if previous is None:
        if reopen is not None:
            raise InvariantValidityLifecycleError(
                "first claim event cannot reopen history"
            )
    elif previous["status"] == "LIQUIDATED":
        if status != "UNKNOWN" or reopen != previous["event_hash"]:
            raise InvariantValidityLifecycleError(
                "liquidated claim requires explicit reopen"
            )
    elif reopen is not None:
        raise InvariantValidityLifecycleError(
            "reopen_reference requires liquidated predecessor"
        )

    body: dict[str, Any] = {
        "type": EVENT_TYPE,
        "version": EVENT_VERSION,
        "sequence": 1 if previous is None else previous["sequence"] + 1,
        "claim_id": claim,
        "status": status,
        "reason": reason,
        "evidence": evidence_items,
        "observed_at": observed_at,
        "environment_fingerprint": environment,
        "reopen_reference": reopen,
        "previous_event_hash": None if previous is None else previous["event_hash"],
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    return {**body, "event_hash": _canonical_hash(body, label="event")}


def project_active_invariants(
    history: Sequence[Mapping[str, Any]],
    *,
    current_environment_fingerprint: str,
) -> dict[str, Any]:
    """Project current usable claims while retaining immutable history identity."""
    current_environment = _required_text(
        current_environment_fingerprint,
        label="current_environment_fingerprint",
    )
    closed_history = _validate_history(history)
    latest: dict[str, dict[str, Any]] = {}
    for event in closed_history:
        latest[event["claim_id"]] = event

    active: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for claim_id in sorted(latest):
        event = latest[claim_id]
        status = event["status"]
        summary = {
            "claim_id": claim_id,
            "status": status,
            "event_hash": event["event_hash"],
        }
        if status in ACTIVE_STABLE_STATUSES:
            active.append(summary)
        elif (
            status == "CONTINGENT"
            and event["environment_fingerprint"] == current_environment
        ):
            active.append(summary)
        else:
            exclusion_reason = (
                "STALE_ENVIRONMENT"
                if status == "CONTINGENT"
                else status
            )
            excluded.append(
                {**summary, "exclusion_reason": exclusion_reason}
            )

    body: dict[str, Any] = {
        "type": PROJECTION_TYPE,
        "version": PROJECTION_VERSION,
        "current_environment_fingerprint": current_environment,
        "event_count": len(closed_history),
        "history_hash": _canonical_hash(closed_history, label="history"),
        "active_claims": active,
        "excluded_claims": excluded,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    return {
        **body,
        "projection_hash": _canonical_hash(body, label="projection"),
    }