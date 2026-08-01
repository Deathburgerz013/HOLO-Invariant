"""Alignment-driven selection and execution of bounded observations.

The selector composes existing hook, judgment, attention, and computer
observation contracts.  It selects at most one justified, attended, currently
available observation.  It does not grant truth, acceptance, or write authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from holosim.attention_cost_value import evaluate_attention_candidate
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.computer_observer import ALLOWED_ACTIONS, execute_observation
from holosim.hook_contract import validate_hook_request
from holosim.judgment_justifier import evaluate_judgment_justification


SELECTION_TYPE = "aligned_action_selection"
SELECTION_VERSION = 1
RUN_TYPE = "aligned_observation_run"
RUN_VERSION = 1

CANDIDATE_FIELDS = {
    "candidate_id",
    "request",
    "evidence_references",
    "rule_references",
    "comparison_status",
    "uncertainty",
    "unresolved_conflicts",
    "value",
    "cost",
    "urgency",
    "dependency_impact",
}


class AlignedActionSelectorError(ValueError):
    """Raised when aligned action selection cannot be evaluated honestly."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AlignedActionSelectorError(
            f"{field} must be a non-empty string"
        )
    return value


def _selection_hash(value: Mapping[str, Any]) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise AlignedActionSelectorError(str(exc)) from exc


def select_aligned_action(
    *,
    goal_reference: str,
    reference_state: str,
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Select at most one justified, attended, executable observation."""
    goal = _required_text(goal_reference, "goal_reference")
    state = _required_text(reference_state, "reference_state")
    if isinstance(candidates, (str, bytes)) or not isinstance(
        candidates,
        Sequence,
    ):
        raise AlignedActionSelectorError("candidates must be a sequence")

    evaluations: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()

    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise AlignedActionSelectorError(
                f"candidate at index {index} must be an object"
            )
        if set(candidate) != CANDIDATE_FIELDS:
            raise AlignedActionSelectorError(
                "candidate fields do not match the versioned schema"
            )

        candidate_id = _required_text(
            candidate["candidate_id"],
            "candidate_id",
        )
        if candidate_id in candidate_ids:
            raise AlignedActionSelectorError("duplicate candidate_id")
        candidate_ids.add(candidate_id)

        request = candidate["request"]
        validate_hook_request(request)
        capable = request["action"] in ALLOWED_ACTIONS

        judgment = evaluate_judgment_justification(
            judgment_id=f"alignment:{candidate_id}",
            conclusion={
                "goal_reference": goal,
                "request_hash": request["request_hash"],
                "action": request["action"],
                "reference": request["reference"],
            },
            reference_state=state,
            evidence_references=candidate["evidence_references"],
            rule_references=candidate["rule_references"],
            comparison_status=candidate["comparison_status"],
            uncertainty=candidate["uncertainty"],
            unresolved_conflicts=candidate["unresolved_conflicts"],
        )
        attention = evaluate_attention_candidate(
            candidate_id=candidate_id,
            value=candidate["value"],
            cost=candidate["cost"],
            urgency=candidate["urgency"],
            dependency_impact=candidate["dependency_impact"],
        )
        eligible = (
            capable
            and judgment["status"] == "JUSTIFIED"
            and attention["decision"] == "EARN_CYCLES"
        )

        evaluations.append(
            {
                "candidate_id": candidate_id,
                "request": deepcopy(request),
                "capable": capable,
                "judgment": judgment,
                "attention": attention,
                "eligible": eligible,
            }
        )

    evaluations.sort(key=lambda item: item["candidate_id"])
    eligible = [item for item in evaluations if item["eligible"]]
    eligible.sort(
        key=lambda item: (
            -item["attention"]["score"],
            item["candidate_id"],
            item["request"]["request_hash"],
        )
    )

    selected = eligible[0] if eligible else None
    body: dict[str, Any] = {
        "type": SELECTION_TYPE,
        "version": SELECTION_VERSION,
        "goal_reference": goal,
        "reference_state": state,
        "evaluations": evaluations,
        "decision": "SELECTED" if selected else "HALT",
        "selected_candidate_id": (
            selected["candidate_id"] if selected else None
        ),
        "selected_request": (
            deepcopy(selected["request"]) if selected else None
        ),
        "execution_performed": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Selection establishes alignment only relative to the supplied "
            "goal, state, evidence, invariant references, conflicts, and "
            "attention values. It does not establish truth, acceptance, or "
            "write authority."
        ),
    }
    return {**body, "selection_hash": _selection_hash(body)}


def run_aligned_observation(
    *,
    goal_reference: str,
    reference_state: str,
    candidates: Sequence[Mapping[str, Any]],
    allowed_root: str | Path,
) -> dict[str, Any]:
    """Select and execute one aligned, bounded observation or halt."""
    selection = select_aligned_action(
        goal_reference=goal_reference,
        reference_state=reference_state,
        candidates=candidates,
    )

    selected_request = selection["selected_request"]
    if selected_request is None:
        observation_result = None
        execution_performed = False
    else:
        observation_result = execute_observation(
            request=selected_request,
            allowed_root=allowed_root,
        )
        execution_performed = True

    body = {
        "type": RUN_TYPE,
        "version": RUN_VERSION,
        "selection": selection,
        "execution_performed": execution_performed,
        "observation_result": observation_result,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "run_hash": _selection_hash(body)}
