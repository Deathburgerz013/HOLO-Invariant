"""Signed, single-use permission for one bounded computer observation.

Alignment can justify an observation, but justification is not permission.
This module requires a verified occurrence authorizing the exact selected
request, resolved root, and observation time before any read is performed.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from holosim.aligned_action_selector import select_aligned_action
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.computer_observer import execute_observation
from holosim.signed_occurrence import (
    SignedOccurrenceError,
    verify_signed_occurrence,
)


PERMIT_TYPE = "bounded_observation_permit"
PERMIT_VERSION = 1
RUN_TYPE = "permitted_aligned_observation"
RUN_VERSION = 1
PERMIT_PAYLOAD_FIELDS = {
    "type",
    "version",
    "request_hash",
    "allowed_root_sha256",
    "not_before",
    "not_after",
}


class ObservationPermitError(ValueError):
    """Raised when observation permission cannot be evaluated honestly."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservationPermitError(f"{field} must be a non-empty string")
    return value


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise ObservationPermitError(str(exc)) from exc


def _instant(value: Any, field: str) -> datetime:
    text = _required_text(value, field)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ObservationPermitError(
            f"{field} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ObservationPermitError(f"{field} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def observation_root_sha256(allowed_root: str | Path) -> str:
    """Hash the resolved observation root used by the computer boundary."""
    try:
        root = Path(allowed_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ObservationPermitError("allowed root is unavailable") from exc
    if not root.is_dir():
        raise ObservationPermitError("allowed root must be a directory")
    return _hash({"resolved_allowed_root": str(root)})


def _result(
    *,
    selection: Mapping[str, Any],
    permit_verification: Mapping[str, Any] | None,
    decision: str,
    reason: str,
    observation_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    performed = observation_result is not None
    body = {
        "type": RUN_TYPE,
        "version": RUN_VERSION,
        "selection": deepcopy(dict(selection)),
        "permit_verification": (
            None
            if permit_verification is None
            else deepcopy(dict(permit_verification))
        ),
        "decision": decision,
        "reason": reason,
        "observation_performed": performed,
        "observation_result": (
            None
            if observation_result is None
            else deepcopy(dict(observation_result))
        ),
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "run_hash": _hash(body)}


def run_permitted_aligned_observation(
    *,
    goal_reference: str,
    reference_state: str,
    candidates: Sequence[Mapping[str, Any]],
    allowed_root: str | Path,
    observed_at: str,
    permit_occurrence: Mapping[str, Any],
    permit_source_secrets: Mapping[str, bytes],
    seen_occurrence_ids: Collection[str],
) -> dict[str, Any]:
    """Execute one selected read only when its signed permit is currently valid."""
    selection = select_aligned_action(
        goal_reference=goal_reference,
        reference_state=reference_state,
        candidates=candidates,
    )
    selected_request = selection["selected_request"]
    if selected_request is None:
        return _result(
            selection=selection,
            permit_verification=None,
            decision="HALT_UNALIGNED",
            reason="no aligned observation was selected",
        )

    try:
        verification = verify_signed_occurrence(
            occurrence=permit_occurrence,
            source_secrets=permit_source_secrets,
            seen_occurrence_ids=seen_occurrence_ids,
        )
    except SignedOccurrenceError as exc:
        raise ObservationPermitError(str(exc)) from exc

    if not verification["verified"]:
        return _result(
            selection=selection,
            permit_verification=verification,
            decision="HALT_UNPERMITTED",
            reason=verification["status"],
        )

    payload = permit_occurrence["payload"]
    if not isinstance(payload, Mapping) or set(payload) != PERMIT_PAYLOAD_FIELDS:
        raise ObservationPermitError(
            "permit payload fields do not match the versioned schema"
        )
    if payload["type"] != PERMIT_TYPE or payload["version"] != PERMIT_VERSION:
        raise ObservationPermitError("permit payload type or version is invalid")

    request_hash = _required_text(payload["request_hash"], "request_hash")
    if request_hash != selected_request["request_hash"]:
        return _result(
            selection=selection,
            permit_verification=verification,
            decision="HALT_UNPERMITTED",
            reason="permit is bound to a different request",
        )

    expected_root_hash = observation_root_sha256(allowed_root)
    root_hash = _required_text(
        payload["allowed_root_sha256"],
        "allowed_root_sha256",
    )
    if root_hash != expected_root_hash:
        return _result(
            selection=selection,
            permit_verification=verification,
            decision="HALT_UNPERMITTED",
            reason="permit is bound to a different allowed root",
        )

    current = _instant(observed_at, "observed_at")
    not_before = _instant(payload["not_before"], "not_before")
    not_after = _instant(payload["not_after"], "not_after")
    if not_before > not_after:
        raise ObservationPermitError("permit time window is inverted")
    if current < not_before:
        return _result(
            selection=selection,
            permit_verification=verification,
            decision="HALT_UNPERMITTED",
            reason="permit is not active yet",
        )
    if current > not_after:
        return _result(
            selection=selection,
            permit_verification=verification,
            decision="HALT_UNPERMITTED",
            reason="permit has expired",
        )

    observation = execute_observation(
        request=selected_request,
        allowed_root=allowed_root,
    )
    return _result(
        selection=selection,
        permit_verification=verification,
        decision="OBSERVED",
        reason="signed permit matched request, root, and time window",
        observation_result=observation,
    )
