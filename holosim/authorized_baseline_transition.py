"""Authorized bridge from a justified proposal to one exact next baseline.

This module composes two existing boundaries:
1. baseline promotion may be justified to propose without accepting anything;
2. operational authorization may permit one exact promotion target.

The result creates a transition record only. It does not claim that the new
baseline is true, execute arbitrary code, or grant general write authority.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

from .baseline_promotion_gate import (
    GATE_TYPE,
    GATE_VERSION,
    STATUS_JUSTIFIED_TO_PROPOSE,
)
from .canonical import CanonicalValueError, stable_hash
from .typed_operational_authorization import (
    ACTION_BASELINE_PROMOTION,
    OperationalAuthorizationError,
    validate_operational_authorization,
)


CANDIDATE_TYPE = "baseline_transition_candidate"
CANDIDATE_VERSION = 1
TRANSITION_TYPE = "authorized_baseline_transition"
TRANSITION_VERSION = 1
SHA256 = re.compile(r"[0-9a-f]{64}")


class AuthorizedBaselineTransitionError(ValueError):
    """A proposed baseline transition violates a required boundary."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise AuthorizedBaselineTransitionError(f"{field} must be nonempty text")
    return value.strip()


def _digest(value: Any, field: str) -> str:
    value = _text(value, field)
    if SHA256.fullmatch(value) is None:
        raise AuthorizedBaselineTransitionError(
            f"{field} must be lowercase SHA-256"
        )
    return value


def _verify_gate(gate: Mapping[str, Any]) -> dict[str, Any]:
    if type(gate) is not dict:
        raise AuthorizedBaselineTransitionError("promotion_gate must be an object")

    expected = {
        "type", "version", "baseline_id", "baseline_state_hash",
        "comparison_id", "status", "motivating_claims", "conflict_claims",
        "unknown_claims", "justification_references", "missing_justifications",
        "candidate_next_baseline_created", "truth_claimed", "accepted",
        "write_authority", "gate_id",
    }
    if set(gate) != expected:
        raise AuthorizedBaselineTransitionError(
            "promotion_gate fields do not match the versioned schema"
        )

    body = {key: deepcopy(value) for key, value in gate.items() if key != "gate_id"}
    try:
        expected_id = stable_hash(body)
    except CanonicalValueError as exc:
        raise AuthorizedBaselineTransitionError(str(exc)) from exc

    if gate["gate_id"] != expected_id:
        raise AuthorizedBaselineTransitionError(
            "promotion_gate identity is invalid"
        )
    if gate["type"] != GATE_TYPE or gate["version"] != GATE_VERSION:
        raise AuthorizedBaselineTransitionError(
            "promotion_gate type or version is invalid"
        )
    if gate["status"] != STATUS_JUSTIFIED_TO_PROPOSE:
        raise AuthorizedBaselineTransitionError(
            "promotion_gate is not justified to propose"
        )
    if gate["candidate_next_baseline_created"] is not False:
        raise AuthorizedBaselineTransitionError(
            "promotion_gate must not already create a next baseline"
        )
    if gate["truth_claimed"] is not False or gate["accepted"] is not False:
        raise AuthorizedBaselineTransitionError(
            "promotion_gate must remain non-epistemic"
        )
    if gate["write_authority"] != "NONE":
        raise AuthorizedBaselineTransitionError(
            "promotion_gate must have write_authority NONE"
        )
    return deepcopy(gate)


def build_baseline_transition_candidate(
    *,
    promotion_gate: Mapping[str, Any],
    next_baseline_id: str,
    next_baseline_state_hash: str,
) -> dict[str, Any]:
    """Bind one justified proposal to one exact candidate baseline identity."""
    gate = _verify_gate(promotion_gate)

    body = {
        "type": CANDIDATE_TYPE,
        "version": CANDIDATE_VERSION,
        "previous_baseline_id": gate["baseline_id"],
        "previous_baseline_state_hash": gate["baseline_state_hash"],
        "promotion_gate_id": gate["gate_id"],
        "next_baseline_id": _text(next_baseline_id, "next_baseline_id"),
        "next_baseline_state_hash": _digest(
            next_baseline_state_hash, "next_baseline_state_hash"
        ),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "candidate_hash": stable_hash(body)}


def _verify_candidate(
    candidate: Mapping[str, Any],
    *,
    gate: Mapping[str, Any],
) -> dict[str, Any]:
    if type(candidate) is not dict:
        raise AuthorizedBaselineTransitionError("candidate must be an object")

    expected = {
        "type", "version", "previous_baseline_id",
        "previous_baseline_state_hash", "promotion_gate_id",
        "next_baseline_id", "next_baseline_state_hash",
        "truth_claimed", "accepted", "write_authority", "candidate_hash",
    }
    if set(candidate) != expected:
        raise AuthorizedBaselineTransitionError(
            "candidate fields do not match the versioned schema"
        )

    rebuilt = build_baseline_transition_candidate(
        promotion_gate=gate,
        next_baseline_id=candidate["next_baseline_id"],
        next_baseline_state_hash=candidate["next_baseline_state_hash"],
    )
    if rebuilt != candidate:
        raise AuthorizedBaselineTransitionError("candidate identity is invalid")
    return deepcopy(candidate)


def authorize_baseline_transition(
    *,
    promotion_gate: Mapping[str, Any],
    candidate: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one authorized, exact, non-epistemic baseline transition."""
    gate = _verify_gate(promotion_gate)
    checked_candidate = _verify_candidate(candidate, gate=gate)

    try:
        validate_operational_authorization(
            authorization,
            expected_action=ACTION_BASELINE_PROMOTION,
            expected_target_sha256=checked_candidate["candidate_hash"],
        )
    except OperationalAuthorizationError as exc:
        raise AuthorizedBaselineTransitionError(str(exc)) from exc

    body = {
        "type": TRANSITION_TYPE,
        "version": TRANSITION_VERSION,
        "previous_baseline_id": checked_candidate["previous_baseline_id"],
        "previous_baseline_state_hash": checked_candidate[
            "previous_baseline_state_hash"
        ],
        "promotion_gate_id": gate["gate_id"],
        "candidate_hash": checked_candidate["candidate_hash"],
        "next_baseline_id": checked_candidate["next_baseline_id"],
        "next_baseline_state_hash": checked_candidate[
            "next_baseline_state_hash"
        ],
        "authorization_hash": authorization["authorization_hash"],
        "authorized_by_actor_id": authorization["actor_id"],
        "status": "AUTHORIZED",
        "next_baseline_created": True,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "promotion_authority": "EXACT_TARGET_ONLY",
    }
    return {**body, "transition_id": stable_hash(body)}
