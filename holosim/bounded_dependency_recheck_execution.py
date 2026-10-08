"""Bounded execution of an INV check for a declared dependency recheck."""

from __future__ import annotations

from copy import deepcopy

from holosim.agent import verify_dependency_checked_agent_receipt
from holosim.canonical import stable_hash
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    ReplaceTransition,
    SubtractTransition,
    execute_inv_transition_with_receipt,
)


class DependencyINVRecheckError(ValueError):
    """Invalid dependency recheck request or receipt."""


def _transition(kind, value):
    if type(value) is not int:
        raise DependencyINVRecheckError("transition value must be an integer")
    if kind == "subtract":
        return SubtractTransition(value)
    if kind == "replace":
        return ReplaceTransition(value)
    raise DependencyINVRecheckError("unsupported transition kind")


def execute_dependency_inv_recheck(
    *,
    dependency_checked_receipt,
    analysis_receipt_hash,
    changed_dependency_hash,
    state,
    transition_kind,
    transition_value,
    minimum,
):
    if not verify_dependency_checked_agent_receipt(dependency_checked_receipt):
        raise DependencyINVRecheckError("invalid dependency-checked receipt")

    if type(state) is not int or type(minimum) is not int:
        raise DependencyINVRecheckError("state and minimum must be integers")

    plan = dependency_checked_receipt["recheck_plan"]
    if dependency_checked_receipt["run_status"] != "RECHECK_REQUIRED":
        raise DependencyINVRecheckError("recheck is not required")

    if changed_dependency_hash not in plan["changed_dependency_hashes"]:
        raise DependencyINVRecheckError("dependency change is not declared")

    matching_paths = [
        path
        for finding in dependency_checked_receipt["withheld_findings"]
        for path in finding["trigger_paths"]
        if path[0] == changed_dependency_hash
        and path[-1] == analysis_receipt_hash
    ]
    if not matching_paths:
        raise DependencyINVRecheckError("no affected analysis path")

    decision = execute_inv_transition_with_receipt(
        state,
        _transition(transition_kind, transition_value),
        GreaterThanOrEqualInvariant(minimum),
    )

    inv_decision = {
        "previous_state": decision.previous_state,
        "candidate_state": decision.candidate_state,
        "accepted": decision.accepted,
        "resulting_state": decision.resulting_state,
    }

    body = {
        "type": "BOUNDED_DEPENDENCY_INV_RECHECK",
        "version": 1,
        "dependency_checked_receipt": deepcopy(dependency_checked_receipt),
        "dependency_checked_receipt_hash": dependency_checked_receipt["receipt_hash"],
        "analysis_receipt_hash": analysis_receipt_hash,
        "changed_dependency_hash": changed_dependency_hash,
        "state": state,
        "transition_kind": transition_kind,
        "transition_value": transition_value,
        "minimum": minimum,
        "inv_decision": inv_decision,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_dependency_inv_recheck_receipt(receipt):
    if type(receipt) is not dict:
        return False
    try:
        expected = execute_dependency_inv_recheck(
            dependency_checked_receipt=receipt["dependency_checked_receipt"],
            analysis_receipt_hash=receipt["analysis_receipt_hash"],
            changed_dependency_hash=receipt["changed_dependency_hash"],
            state=receipt["state"],
            transition_kind=receipt["transition_kind"],
            transition_value=receipt["transition_value"],
            minimum=receipt["minimum"],
        )
        return receipt == expected
    except (KeyError, TypeError, ValueError):
        return False
