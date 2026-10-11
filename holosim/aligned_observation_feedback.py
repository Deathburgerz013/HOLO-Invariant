"""Replayable feedback episodes for alignment-driven observations."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from holosim.aligned_action_selector import run_aligned_observation
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.hook_contract import (
    HookContractError,
    validate_hook_request,
    validate_hook_result,
)


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
    replay_state = initial
    replay_evidence_hashes = []
    replay_status = "READY"

    for number, step in enumerate(episode["steps"], start=1):
        if not isinstance(step, Mapping):
            raise AlignedObservationFeedbackError("step must be an object")
        if set(step) != {
            "step_number",
            "input_state_reference",
            "run",
            "evidence_hash",
            "state_changed",
            "step_hash",
        }:
            raise AlignedObservationFeedbackError("step fields mismatch")

        step_body = deepcopy(dict(step))
        step_hash = step_body.pop("step_hash")
        if step_hash != _hash(step_body):
            raise AlignedObservationFeedbackError("step hash mismatch")
        if step["step_number"] != number:
            raise AlignedObservationFeedbackError("step number mismatch")
        if step["input_state_reference"] != replay_state:
            raise AlignedObservationFeedbackError("input state mismatch")
        if replay_status != "READY":
            raise AlignedObservationFeedbackError(
                "step recorded after terminal halt"
            )

        run = step["run"]
        if not isinstance(run, Mapping):
            raise AlignedObservationFeedbackError("run must be an object")
        if not isinstance(run.get("execution_performed"), bool):
            raise AlignedObservationFeedbackError(
                "execution_performed must be boolean"
            )

        observation = run.get("observation_result")
        if observation is not None and not isinstance(
            observation, Mapping
        ):
            raise AlignedObservationFeedbackError(
                "observation_result must be an object or null"
            )

        run_body = {k: v for k, v in run.items() if k != "run_hash"}
        if run.get("run_hash") != _hash(run_body):
            raise AlignedObservationFeedbackError("run hash mismatch")

        selection = run.get("selection")
        if not isinstance(selection, Mapping):
            raise AlignedObservationFeedbackError(
                "selection must be an object"
            )
        if selection.get("reference_state") != replay_state:
            raise AlignedObservationFeedbackError(
                "selection reference state mismatch"
            )
        selection_body = {
            k: v for k, v in selection.items()
            if k != "selection_hash"
        }
        if selection.get("selection_hash") != _hash(selection_body):
            raise AlignedObservationFeedbackError(
                "selection hash mismatch"
            )

        evaluations = selection.get("evaluations")
        if not isinstance(evaluations, list):
            raise AlignedObservationFeedbackError(
                "selection evaluations must be a list"
            )

        eligible = []
        candidate_ids = set()
        for evaluation in evaluations:
            candidate_id = evaluation.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id.strip():
                raise AlignedObservationFeedbackError(
                    "selection candidate identity invalid"
                )
            if candidate_id in candidate_ids:
                raise AlignedObservationFeedbackError(
                    "duplicate selection candidate identity"
                )
            candidate_ids.add(candidate_id)
            if not isinstance(evaluation, Mapping):
                raise AlignedObservationFeedbackError(
                    "selection evaluation must be an object"
                )
            judgment = evaluation.get("judgment")
            attention = evaluation.get("attention")
            if not isinstance(judgment, Mapping) or not isinstance(
                attention, Mapping
            ):
                raise AlignedObservationFeedbackError(
                    "selection evaluation contracts missing"
                )

            from holosim.judgment_justifier import (
                JudgmentJustifierError,
                evaluate_judgment_justification,
            )

            try:
                expected_judgment = evaluate_judgment_justification(
                    judgment_id=judgment["judgment_id"],
                    conclusion=judgment["conclusion"],
                    reference_state=judgment["reference_state"],
                    evidence_references=judgment["evidence_references"],
                    rule_references=judgment["rule_references"],
                    comparison_status=judgment["comparison_status"],
                    uncertainty=judgment["uncertainty"],
                    unresolved_conflicts=judgment["unresolved_conflicts"],
                )
            except (JudgmentJustifierError, KeyError, TypeError) as exc:
                raise AlignedObservationFeedbackError(
                    "selection judgment mismatch"
                ) from exc

            if judgment != expected_judgment:
                raise AlignedObservationFeedbackError(
                    "selection judgment mismatch"
                )

            if judgment.get("judgment_id") != (
                f"alignment:{evaluation.get('candidate_id')}"
            ):
                raise AlignedObservationFeedbackError(
                    "selection judgment identity mismatch"
                )

            if judgment.get("reference_state") != replay_state:
                raise AlignedObservationFeedbackError(
                    "selection judgment reference state mismatch"
                )

            candidate_request = evaluation.get("request")
            if not isinstance(candidate_request, Mapping):
                raise AlignedObservationFeedbackError(
                    "selection judgment conclusion mismatch"
                )
            try:
                validate_hook_request(candidate_request)
            except HookContractError as exc:
                raise AlignedObservationFeedbackError(
                    "selection candidate request invalid"
                ) from exc

            expected_conclusion = {
                "goal_reference": selection.get("goal_reference"),
                "request_hash": candidate_request.get("request_hash"),
                "action": candidate_request.get("action"),
                "reference": candidate_request.get("reference"),
            }
            if judgment.get("conclusion") != expected_conclusion:
                raise AlignedObservationFeedbackError(
                    "selection judgment conclusion mismatch"
                )

            from holosim.attention_cost_value import (
                AttentionCostValueError,
                evaluate_attention_candidate,
            )

            try:
                expected_attention = evaluate_attention_candidate(
                    candidate_id=attention["candidate_id"],
                    value=attention["value"],
                    cost=attention["cost"],
                    urgency=attention["urgency"],
                    dependency_impact=attention["dependency_impact"],
                )
            except (
                AttentionCostValueError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                raise AlignedObservationFeedbackError(
                    "selection attention mismatch"
                ) from exc

            if attention != expected_attention:
                raise AlignedObservationFeedbackError(
                    "selection attention mismatch"
                )

            if attention.get("candidate_id") != evaluation.get("candidate_id"):
                raise AlignedObservationFeedbackError(
                    "selection attention candidate mismatch"
                )

            from holosim.computer_observer import ALLOWED_ACTIONS

            candidate_request = evaluation.get("request")
            expected_capable = (
                isinstance(candidate_request, Mapping)
                and candidate_request.get("action") in ALLOWED_ACTIONS
            )
            if evaluation.get("capable") is not expected_capable:
                raise AlignedObservationFeedbackError(
                    "selection capability mismatch"
                )

            expected_eligible = (
                evaluation.get("capable") is True
                and judgment.get("status") == "JUSTIFIED"
                and attention.get("decision") == "EARN_CYCLES"
            )
            if evaluation.get("eligible") is not expected_eligible:
                raise AlignedObservationFeedbackError(
                    "selection eligibility mismatch"
                )
            if expected_eligible:
                eligible.append(evaluation)

        eligible.sort(
            key=lambda item: (
                -item["attention"]["score"],
                item["candidate_id"],
                item["request"]["request_hash"],
            )
        )
        winner = eligible[0] if eligible else None

        if selection.get("selected_candidate_id") != (
            winner["candidate_id"] if winner else None
        ):
            raise AlignedObservationFeedbackError(
                "selection candidate mismatch"
            )
        if selection.get("selected_request") != (
            winner["request"] if winner else None
        ):
            raise AlignedObservationFeedbackError(
                "selection request mismatch"
            )
        if selection.get("decision") != (
            "SELECTED" if winner else "HALT"
        ):
            raise AlignedObservationFeedbackError(
                "selection decision mismatch"
            )

        request = selection.get("selected_request")
        try:
            if request is not None:
                validate_hook_request(request)
            if observation is not None:
                if request is None:
                    raise AlignedObservationFeedbackError(
                        "observation has no selected request"
                    )
                validate_hook_result(observation, request=request)
        except HookContractError as exc:
            raise AlignedObservationFeedbackError(
                f"observation {exc}"
            ) from exc
        if run["execution_performed"] != (observation is not None):
            raise AlignedObservationFeedbackError(
                "observation execution mismatch"
            )

        if observation is None:
            expected_evidence_hash = None
        else:
            if "evidence" not in observation:
                raise AlignedObservationFeedbackError(
                    "observation evidence missing"
                )
            expected_evidence_hash = _hash(observation["evidence"])

        if step["evidence_hash"] != expected_evidence_hash:
            raise AlignedObservationFeedbackError(
                "evidence hash mismatch"
            )

        expected_change = (
            expected_evidence_hash is not None
            and expected_evidence_hash not in replay_evidence_hashes
        )
        if step["state_changed"] is not expected_change:
            raise AlignedObservationFeedbackError(
                "state change mismatch"
            )

        if not run["execution_performed"]:
            replay_status = "HALT_UNALIGNED"
        elif not expected_change:
            replay_status = "HALT_NO_CHANGE"
        else:
            result_hash = observation.get("result_hash")
            if not isinstance(result_hash, str) or not re.fullmatch(
                r"[0-9a-f]{64}", result_hash
            ):
                raise AlignedObservationFeedbackError(
                    "observation result hash invalid"
                )
            replay_evidence_hashes.append(expected_evidence_hash)
            replay_state = f"observation:{result_hash}"
            replay_status = (
                "HALT_BUDGET" if number >= limit else "READY"
            )

    if episode["current_state_reference"] != replay_state:
        raise AlignedObservationFeedbackError("current state mismatch")
    if episode["observed_evidence_hashes"] != replay_evidence_hashes:
        raise AlignedObservationFeedbackError(
            "observed evidence history mismatch"
        )
    if episode["status"] != replay_status:
        raise AlignedObservationFeedbackError("episode status mismatch")

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
