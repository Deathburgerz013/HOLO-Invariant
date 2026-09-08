"""Frame-relative information evaluation for HOLO/Sim.

This module does not decide truth, acceptance, authority, or a universal
importance score. It records how unchanged information sits inside one
explicitly declared measurement frame.

Only relationships that can be derived without semantic guessing are
evaluated here. Arbitrary constraints and conditions are preserved as
declarations until a separately identified verifier evaluates them.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from holosim.canonical import stable_hash


RECEIPT_TYPE = "frame_information_evaluation"
RECEIPT_VERSION = 1


class FrameInformationEvaluationError(ValueError):
    """Raised when the declared evaluation inputs are malformed."""


def _require_mapping(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FrameInformationEvaluationError(f"{name} must be a dict")
    return deepcopy(value)


def _require_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FrameInformationEvaluationError(
            f"{name} must be a non-empty string"
        )
    return value


def _require_string_list(value: Any, *, name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise FrameInformationEvaluationError(
            f"{name} must be a list of non-empty strings"
        )
    return list(value)


def _scope_relation(
    information_tags: list[str],
    frame_scope: list[str],
) -> dict[str, Any]:
    tag_set = set(information_tags)
    scope_set = set(frame_scope)

    matched = [tag for tag in information_tags if tag in scope_set]
    outside = [tag for tag in information_tags if tag not in scope_set]
    unmatched_scope = [item for item in frame_scope if item not in tag_set]

    if not information_tags:
        status = "UNDECLARED_INFORMATION_TAGS"
    elif len(matched) == len(information_tags):
        status = "IN_SCOPE"
    elif matched:
        status = "PARTIAL_SCOPE"
    else:
        status = "OUT_OF_SCOPE"

    return {
        "status": status,
        "matched_information_tags": matched,
        "outside_information_tags": outside,
        "unmatched_frame_scope": unmatched_scope,
    }


def evaluate_information_in_frame(
    information: dict[str, Any],
    frame: dict[str, Any],
) -> dict[str, Any]:
    """Return a deterministic receipt for information under a declared frame.

    The same information may produce a different receipt under a different
    frame while retaining the same information identity.

    This function deliberately does not:
    - infer a universal numeric weight or importance score,
    - parse arbitrary natural-language statements into hidden facts,
    - evaluate arbitrary constraints or conditions without a named verifier,
    - claim truth or acceptance,
    - authorize state change, execution, or writes.
    """

    info = _require_mapping(information, name="information")
    declared_frame = _require_mapping(frame, name="frame")

    _require_string(info.get("information_id"), name="information.information_id")
    _require_string(info.get("statement"), name="information.statement")
    tags = _require_string_list(info.get("tags", []), name="information.tags")
    _require_string_list(
        info.get("source_refs", []),
        name="information.source_refs",
    )

    _require_string(
        declared_frame.get("frame_id"),
        name="frame.frame_id",
    )
    _require_string(
        declared_frame.get("measurement"),
        name="frame.measurement",
    )
    scope = _require_string_list(
        declared_frame.get("scope", []),
        name="frame.scope",
    )
    _require_string_list(
        declared_frame.get("priorities", []),
        name="frame.priorities",
    )

    constraints = declared_frame.get("constraints")
    conditions = declared_frame.get("conditions")
    if not isinstance(constraints, dict):
        raise FrameInformationEvaluationError(
            "frame.constraints must be a dict"
        )
    if not isinstance(conditions, dict):
        raise FrameInformationEvaluationError(
            "frame.conditions must be a dict"
        )

    information_hash = stable_hash(info)
    frame_hash = stable_hash(declared_frame)

    relation = _scope_relation(tags, scope)

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "information": info,
        "information_hash": information_hash,
        "frame": declared_frame,
        "frame_hash": frame_hash,
        "scope_relation": relation,
        "measurement_status": "DECLARED",
        "priority_status": "DECLARED",
        "constraint_status": (
            "DECLARED_NOT_EVALUATED"
            if constraints
            else "NO_CONSTRAINTS_DECLARED"
        ),
        "condition_status": (
            "DECLARED_NOT_EVALUATED"
            if conditions
            else "NO_CONDITIONS_DECLARED"
        ),
        "universal_weight_claimed": False,
        "accepted": False,
        "truth_claimed": False,
        "state_change_authorized": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    receipt = dict(body)
    receipt["evaluation_hash"] = stable_hash(body)
    return receipt
