"""Signed, replay-resistant permission gate for one Temporal-style activity.

The module intentionally has no Temporal dependency.  Workflow runtimes may
place this gate immediately before a side-effecting activity invocation.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.signed_occurrence import (
    SignedOccurrenceError,
    verify_signed_occurrence,
)


PERMIT_TYPE = "temporal_activity_permit"
PERMIT_VERSION = 1
PERMIT_PAYLOAD_FIELDS = {
    "type",
    "version",
    "workflow_id",
    "run_id",
    "activity_id",
    "activity_type",
    "target_sha256",
    "input_sha256",
    "not_before",
    "not_after",
}
RUN_TYPE = "permitted_temporal_activity"
RUN_VERSION = 1


class TemporalActivityGateError(ValueError):
    """Raised when an activity permit violates its bounded contract."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TemporalActivityGateError(
            f"{field} must be a non-empty string"
        )
    return value


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise TemporalActivityGateError(str(exc)) from exc


def _instant(value: Any, field: str) -> datetime:
    text = _required_text(value, field)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TemporalActivityGateError(
            f"{field} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TemporalActivityGateError(
            f"{field} must include a UTC offset"
        )
    return parsed.astimezone(timezone.utc)


def _result(
    *,
    permit_verification: Mapping[str, Any],
    decision: str,
    reason: str,
    activity_result: Any = None,
) -> dict[str, Any]:
    executed = decision == "EXECUTED"
    body = {
        "type": RUN_TYPE,
        "version": RUN_VERSION,
        "permit_verification": deepcopy(dict(permit_verification)),
        "decision": decision,
        "reason": reason,
        "activity_executed": executed,
        "activity_result": deepcopy(activity_result),
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "run_hash": _hash(body)}


def run_permitted_temporal_activity(
    *,
    workflow_id: str,
    run_id: str,
    activity_id: str,
    activity_type: str,
    target: Any,
    activity_input: Any,
    observed_at: str,
    permit_occurrence: Mapping[str, Any],
    permit_source_secrets: Mapping[str, bytes],
    seen_occurrence_ids: Collection[str],
    activity: Callable[[Any], Any],
) -> dict[str, Any]:
    """Execute one callable only when its exact signed permit is current."""
    expected = {
        "workflow_id": _required_text(workflow_id, "workflow_id"),
        "run_id": _required_text(run_id, "run_id"),
        "activity_id": _required_text(activity_id, "activity_id"),
        "activity_type": _required_text(activity_type, "activity_type"),
        "target_sha256": _hash(target),
        "input_sha256": _hash(activity_input),
    }
    if not callable(activity):
        raise TemporalActivityGateError("activity must be callable")

    try:
        verification = verify_signed_occurrence(
            occurrence=permit_occurrence,
            source_secrets=permit_source_secrets,
            seen_occurrence_ids=seen_occurrence_ids,
        )
    except SignedOccurrenceError as exc:
        raise TemporalActivityGateError(str(exc)) from exc

    if not verification["verified"]:
        return _result(
            permit_verification=verification,
            decision="HALT_UNAUTHORIZED",
            reason=verification["status"],
        )

    payload = permit_occurrence["payload"]
    if not isinstance(payload, Mapping) or set(payload) != PERMIT_PAYLOAD_FIELDS:
        raise TemporalActivityGateError(
            "permit payload fields do not match the versioned schema"
        )
    if payload["type"] != PERMIT_TYPE or payload["version"] != PERMIT_VERSION:
        raise TemporalActivityGateError(
            "permit payload type or version is invalid"
        )

    for field, expected_value in expected.items():
        if payload[field] != expected_value:
            return _result(
                permit_verification=verification,
                decision="HALT_UNAUTHORIZED",
                reason=f"permit is bound to a different {field}",
            )

    current = _instant(observed_at, "observed_at")
    not_before = _instant(payload["not_before"], "not_before")
    not_after = _instant(payload["not_after"], "not_after")
    if not_before > not_after:
        raise TemporalActivityGateError("permit time window is inverted")
    if current < not_before:
        return _result(
            permit_verification=verification,
            decision="HALT_UNAUTHORIZED",
            reason="permit is not active yet",
        )
    if current > not_after:
        return _result(
            permit_verification=verification,
            decision="HALT_UNAUTHORIZED",
            reason="permit has expired",
        )

    result = activity(deepcopy(activity_input))
    return _result(
        permit_verification=verification,
        decision="EXECUTED",
        reason="signed permit matched the exact activity boundary",
        activity_result=result,
    )