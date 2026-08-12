"""Operator-facing handoffs over portable verified re-entry bundles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.portable_verified_reentry import (
    PortableVerifiedReentryError,
    consume_portable_reentry_bundle,
    validate_portable_reentry_bundle,
)

HANDOFF_TYPE = "operator_resume_handoff"
HANDOFF_VERSION = 1
HANDOFF_FIELDS = {
    "type", "version", "handoff_id", "portable_bundle",
    "portable_bundle_hash", "objective", "completed",
    "constraints", "unresolved", "next_action", "restart_cost",
    "truth_claimed", "accepted", "write_authority",
    "execution_authority", "handoff_hash",
}


class OperatorResumeHandoffError(ValueError):
    """Raised when an operator handoff cannot be trusted or resumed."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise OperatorResumeHandoffError(
            f"{field} must be a non-empty plain string"
        )
    return value


def _texts(values: Sequence[str], field: str) -> list[str]:
    if type(values) not in {list, tuple}:
        raise OperatorResumeHandoffError(f"{field} must be a list or tuple")
    checked = [_text(value, f"{field}[{index}]") for index, value in enumerate(values)]
    if len(checked) != len(set(checked)):
        raise OperatorResumeHandoffError(f"{field} values must be unique")
    return checked


def build_operator_resume_handoff(
    *,
    handoff_id: str,
    portable_bundle: Mapping[str, Any],
    objective: str,
    completed: Sequence[str],
    constraints: Sequence[str],
    unresolved: Sequence[str],
    next_action: str,
    baseline_restart_steps: int,
) -> dict[str, Any]:
    """Bind concise operator instructions to verified reconstructable state."""
    if type(portable_bundle) is not dict:
        raise OperatorResumeHandoffError("portable_bundle must be a plain dictionary")
    try:
        validate_portable_reentry_bundle(portable_bundle)
        consume_portable_reentry_bundle(portable_bundle)
    except PortableVerifiedReentryError as exc:
        raise OperatorResumeHandoffError(f"portable bundle is not resumable: {exc}") from exc
    if type(baseline_restart_steps) is not int or baseline_restart_steps < 1:
        raise OperatorResumeHandoffError("baseline_restart_steps must be a positive integer")

    body = {
        "type": HANDOFF_TYPE,
        "version": HANDOFF_VERSION,
        "handoff_id": _text(handoff_id, "handoff_id"),
        "portable_bundle": deepcopy(portable_bundle),
        "portable_bundle_hash": portable_bundle["bundle_hash"],
        "objective": _text(objective, "objective"),
        "completed": _texts(completed, "completed"),
        "constraints": _texts(constraints, "constraints"),
        "unresolved": _texts(unresolved, "unresolved"),
        "next_action": _text(next_action, "next_action"),
        "restart_cost": {
            "baseline_operator_steps": baseline_restart_steps,
            "handoff_operator_steps": 1,
            "claimed_steps_avoided": baseline_restart_steps - 1,
            "measured": False,
        },
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    try:
        return {**body, "handoff_hash": stable_hash(body)}
    except CanonicalValueError as exc:
        raise OperatorResumeHandoffError(str(exc)) from exc


def validate_operator_resume_handoff(handoff: Mapping[str, Any]) -> bool:
    """Regenerate a handoff and require exact schema and evidence equality."""
    if type(handoff) is not dict:
        raise OperatorResumeHandoffError("handoff must be a plain dictionary")
    if set(handoff) != HANDOFF_FIELDS:
        raise OperatorResumeHandoffError("handoff fields do not match the versioned schema")
    if handoff.get("type") != HANDOFF_TYPE or handoff.get("version") != HANDOFF_VERSION:
        raise OperatorResumeHandoffError("handoff type or version is invalid")
    if (
        handoff.get("truth_claimed") is not False
        or handoff.get("accepted") is not False
        or handoff.get("write_authority") != "NONE"
        or handoff.get("execution_authority") != "NONE"
    ):
        raise OperatorResumeHandoffError("handoff cannot grant authority")
    cost = handoff.get("restart_cost")
    if type(cost) is not dict or set(cost) != {
        "baseline_operator_steps", "handoff_operator_steps",
        "claimed_steps_avoided", "measured",
    }:
        raise OperatorResumeHandoffError("restart_cost schema is invalid")
    if cost.get("handoff_operator_steps") != 1 or cost.get("measured") is not False:
        raise OperatorResumeHandoffError("restart_cost cannot claim an unobserved measurement")
    try:
        rebuilt = build_operator_resume_handoff(
            handoff_id=handoff["handoff_id"],
            portable_bundle=handoff["portable_bundle"],
            objective=handoff["objective"],
            completed=handoff["completed"],
            constraints=handoff["constraints"],
            unresolved=handoff["unresolved"],
            next_action=handoff["next_action"],
            baseline_restart_steps=cost["baseline_operator_steps"],
        )
    except OperatorResumeHandoffError:
        raise
    except (KeyError, TypeError) as exc:
        raise OperatorResumeHandoffError("handoff evidence is malformed") from exc
    if rebuilt != handoff:
        raise OperatorResumeHandoffError("handoff does not match its verified evidence")
    return True


def resume_operator_handoff(handoff: Mapping[str, Any]) -> dict[str, Any]:
    """Emit the concise operator frame and exact reconstructed working state."""
    validate_operator_resume_handoff(handoff)
    replay = consume_portable_reentry_bundle(handoff["portable_bundle"])
    return {
        "status": "OPERATOR_RESUME_READY",
        "handoff_id": handoff["handoff_id"],
        "handoff_hash": handoff["handoff_hash"],
        "objective": handoff["objective"],
        "completed": list(handoff["completed"]),
        "constraints": list(handoff["constraints"]),
        "unresolved": list(handoff["unresolved"]),
        "next_action": handoff["next_action"],
        "restart_cost": deepcopy(handoff["restart_cost"]),
        "packet_hash": replay["packet_hash"],
        "working_state": replay["working_state"],
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
