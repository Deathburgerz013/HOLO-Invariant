"""Replayable feedback episodes for alignment-driven observations."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from holosim.aligned_action_selector import run_aligned_observation
from holosim.canonical import CanonicalValueError, stable_hash


EPISODE_TYPE = "aligned_observation_feedback_episode"
EPISODE_VERSION = 1
MAX_EPISODE_STEPS = 64
VALID_STATUSES = {
    "READY",
    "HALT_NO_CHANGE",
    "HALT_UNALIGNED",
    "HALT_BUDGET",
}

EPISODE_FIELDS = {
    "type",
    "version",
    "episode_id",
    "goal_reference",
    "initial_state_reference",
    "current_state_reference",
    "max_steps",
    "steps",
    "observed_evidence_hashes",
    "status",
    "step_count",
    "accepted",
    "write_authority",
    "episode_hash",
}


class AlignedObservationFeedbackError(ValueError):
    """Raised when a feedback episode cannot continue honestly."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AlignedObservationFeedbackError(
            f"{field} must be a non-empty string"
        )
    return value


def _bounded_steps(value: Any) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_EPISODE_STEPS
    ):
        raise AlignedObservationFeedbackError(
            f"max_steps must be an integer from 1 to {MAX_EPISODE_STEPS}"
        )
    return value


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise AlignedObservationFeedbackError(str(exc)) from exc


def _episode_identity(
    *,
    goal_reference: str,
    initial_state_reference: str,
    max_steps: int,
) -> str:
    return _hash(
        {
            "type": EPISODE_TYPE,
            "version": EPISODE_VERSION,
            "goal_reference": goal_reference,
            "initial_state_reference": initial_state_reference,
            "max_steps": max_steps,
        }
    )


def _with_episode_hash(body: Mapping[str, Any]) -> dict[str, Any]:
    copied = deepcopy(dict(body))
    return {**copied, "episode_hash": _hash(copied)}


def build_observation_episode(
    *,
    goal_reference: str,
    initial_state_reference: str,
    max_steps: int,
) -> dict[str, Any]:
    """Create an empty, bounded feedback episode."""
    goal = _required_text(goal_reference, "goal_reference")
    initial = _required_text(
        initial_state_reference,
        "initial_state_reference",
    )
    limit = _bounded_steps(max_steps)
    body = {
        "type": EPISODE_TYPE,
        "version": EPISODE_VERSION,
        "episode_id": _episode_identity(
            goal_reference=goal,
            initial_state_reference=initial,
            max_steps=limit,
        ),
        "goal_reference": goal,
        "initial_state_reference": initial,
        "current_state_reference": initial,
        "max_steps": limit,
        "steps": [],
        "observed_evidence_hashes": [],
        "status": "READY",
        "step_count": 0,
        "accepted": False,
        "write_authority": "NONE",
    }
    return _with_episode_hash(body)


def validate_observation_episode(episode: Mapping[str, Any]) -> bool:
    """Validate episode structure, identity, history, and canonical hash."""
    if not isinstance(episode, Mapping):
        raise AlignedObservationFeedbackError("episode must be an object")
    if set(episode) != EPISODE_FIELDS:
        raise AlignedObservationFeedbackError(
            "episode fields do not match the versioned schema"
        )

    body = deepcopy(dict(episode))
    actual_hash = body.pop("episode_hash")
    if actual_hash != _hash(body):
        raise AlignedObservationFeedbackError("episode hash mismatch")

    if episode["type"] != EPISODE_TYPE:
        raise AlignedObservationFeedbackError("episode type is invalid")
    if episode["version"] != EPISODE_VERSION:
        raise AlignedObservationFeedbackError("episode version is invalid")
    goal = _required_text(episode["goal_reference"], "goal_reference")
    initial = _required_text(
        episode["initial_state_reference"],
        "initial_state_reference",
    )
    _required_text(
        episode["current_state_reference"],
        "current_state_reference",
    )
    limit = _bounded_steps(episode["max_steps"])

    expected_id = _episode_identity(
        goal_reference=goal,
        initial_state_reference=initial,
        max_steps=limit,
    )
    if episode["episode_id"] != expected_id:
        raise AlignedObservationFeedbackError("episode identity mismatch")
    if not isinstance(episode["steps"], list):
        raise AlignedObservationFeedbackError("steps must be a list")
    if not isinstance(episode["observed_evidence_hashes"], list):
        raise AlignedObservationFeedbackError(
            "observed_evidence_hashes must be a list"
        )
    if episode["step_count"] != len(episode["steps"]):
        raise AlignedObservationFeedbackError("step_count mismatch")
    if len(episode["steps"]) > limit:
        raise AlignedObservationFeedbackError("episode exceeds step budget")

    evidence_hashes = episode["observed_evidence_hashes"]
    if len(evidence_hashes) != len(set(evidence_hashes)):
        raise AlignedObservationFeedbackError(
            "observed evidence hashes must be unique"
        )
    for evidence_hash in evidence_hashes:
        if not isinstance(evidence_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}",
            evidence_hash,
        ):
            raise AlignedObservationFeedbackError(
                "observed evidence hash is invalid"
            )

    if episode["status"] not in VALID_STATUSES:
        raise AlignedObservationFeedbackError("episode status is invalid")
    if episode["accepted"] is not False:
        raise AlignedObservationFeedbackError(
            "episode cannot grant acceptance"
        )
    if episode["write_authority"] != "NONE":
        raise AlignedObservationFeedbackError(
            "episode cannot grant write authority"
        )
    return True


def advance_observation_episode(
    *,
    episode: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    allowed_root: str | Path,
) -> dict[str, Any]:
    """Advance one aligned observation step or return a terminal halt."""
    validate_observation_episode(episode)
    if episode["status"] != "READY":
        raise AlignedObservationFeedbackError(
            "only a READY episode may advance"
        )

    run = run_aligned_observation(
        goal_reference=episode["goal_reference"],
        reference_state=episode["current_state_reference"],
        candidates=candidates,
        allowed_root=allowed_root,
    )

    prior_evidence_hashes = list(episode["observed_evidence_hashes"])
    observation = run["observation_result"]
    evidence_hash = (
        _hash(observation["evidence"])
        if observation is not None
        else None
    )
    state_changed = (
        evidence_hash is not None
        and evidence_hash not in prior_evidence_hashes
    )

    step_body = {
        "step_number": len(episode["steps"]) + 1,
        "input_state_reference": episode["current_state_reference"],
        "run": run,
        "evidence_hash": evidence_hash,
        "state_changed": state_changed,
    }
    step = {**step_body, "step_hash": _hash(step_body)}
    steps = deepcopy(episode["steps"])
    steps.append(step)

    current_state_reference = episode["current_state_reference"]
    if not run["execution_performed"]:
        status = "HALT_UNALIGNED"
    elif not state_changed:
        status = "HALT_NO_CHANGE"
    else:
        prior_evidence_hashes.append(evidence_hash)
        current_state_reference = (
            f"observation:{observation['result_hash']}"
        )
        status = (
            "HALT_BUDGET"
            if len(steps) >= episode["max_steps"]
            else "READY"
        )

    body = {
        "type": EPISODE_TYPE,
        "version": EPISODE_VERSION,
        "episode_id": episode["episode_id"],
        "goal_reference": episode["goal_reference"],
        "initial_state_reference": episode[
            "initial_state_reference"
        ],
        "current_state_reference": current_state_reference,
        "max_steps": episode["max_steps"],
        "steps": steps,
        "observed_evidence_hashes": prior_evidence_hashes,
        "status": status,
        "step_count": len(steps),
        "accepted": False,
        "write_authority": "NONE",
    }
    return _with_episode_hash(body)
