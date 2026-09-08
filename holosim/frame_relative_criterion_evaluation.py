"""Frame-bound criterion aggregation for unchanged information.

This module does not run criterion verifiers, infer criteria from prose, decide
truth, accept information, or grant action authority. It binds caller-supplied
criterion results to one declared frame and derives only the aggregate result
allowed by that frame.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from holosim.canonical import stable_hash
from holosim.frame_information_evaluator import (
    FrameInformationEvaluationError,
    evaluate_information_in_frame,
)


RECEIPT_TYPE = "frame_relative_criterion_evaluation"
RECEIPT_VERSION = 1

ALLOWED_RESULTS = {"PASS", "FAIL", "INDETERMINATE"}
SUCCESS_RULES = {"ALL_REQUIRED_PASS"}


class FrameRelativeCriterionEvaluationError(ValueError):
    """Raised when frame-relative criterion inputs are malformed."""


def _require_mapping(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FrameRelativeCriterionEvaluationError(f"{name} must be a dict")
    return deepcopy(value)


def _require_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FrameRelativeCriterionEvaluationError(
            f"{name} must be a non-empty string"
        )
    return value


def _require_string_list(value: Any, *, name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise FrameRelativeCriterionEvaluationError(
            f"{name} must be a list of non-empty strings"
        )
    if len(set(value)) != len(value):
        raise FrameRelativeCriterionEvaluationError(
            f"{name} must not contain duplicates"
        )
    return list(value)


def _validate_criterion_result(value: Any, *, index: int) -> dict[str, Any]:
    item = _require_mapping(value, name=f"criterion_results[{index}]")
    _require_string(
        item.get("criterion_id"),
        name=f"criterion_results[{index}].criterion_id",
    )
    result = _require_string(
        item.get("result"),
        name=f"criterion_results[{index}].result",
    ).upper()
    if result not in ALLOWED_RESULTS:
        raise FrameRelativeCriterionEvaluationError(
            f"criterion_results[{index}].result is invalid"
        )
    item["result"] = result

    evidence_hash = _require_string(
        item.get("evidence_hash"),
        name=f"criterion_results[{index}].evidence_hash",
    )
    if (
        len(evidence_hash) != 64
        or any(character not in "0123456789abcdef" for character in evidence_hash)
    ):
        raise FrameRelativeCriterionEvaluationError(
            f"criterion_results[{index}].evidence_hash must be a SHA-256 hex digest"
        )

    _require_string(
        item.get("verifier_id"),
        name=f"criterion_results[{index}].verifier_id",
    )
    return item


def _aggregate(
    *,
    required: list[str],
    bound_by_id: dict[str, dict[str, Any]],
) -> tuple[str, list[str]]:
    missing = [criterion_id for criterion_id in required if criterion_id not in bound_by_id]
    if missing:
        return "INDETERMINATE", missing

    required_results = [
        bound_by_id[criterion_id]["result"]
        for criterion_id in required
    ]

    if any(result == "FAIL" for result in required_results):
        return "FAIL", []
    if any(result == "INDETERMINATE" for result in required_results):
        return "INDETERMINATE", []
    return "PASS", []


def build_frame_criterion_evaluation_receipt(
    *,
    information: dict[str, Any],
    frame: dict[str, Any],
    criterion_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bind declared criterion results to one frame and derive a bounded result."""

    info = _require_mapping(information, name="information")
    declared_frame = _require_mapping(frame, name="frame")

    try:
        base = evaluate_information_in_frame(info, declared_frame)
    except FrameInformationEvaluationError as exc:
        raise FrameRelativeCriterionEvaluationError(
            "base frame information evaluation is invalid"
        ) from exc

    required = _require_string_list(
        declared_frame.get("required_criteria"),
        name="frame.required_criteria",
    )
    if not required:
        raise FrameRelativeCriterionEvaluationError(
            "frame.required_criteria must not be empty"
        )

    success_rule = _require_string(
        declared_frame.get("success_rule"),
        name="frame.success_rule",
    ).upper()
    if success_rule not in SUCCESS_RULES:
        raise FrameRelativeCriterionEvaluationError(
            "frame.success_rule is unsupported"
        )

    if not isinstance(criterion_results, list):
        raise FrameRelativeCriterionEvaluationError(
            "criterion_results must be a list"
        )

    validated_results = [
        _validate_criterion_result(value, index=index)
        for index, value in enumerate(criterion_results)
    ]

    seen: set[str] = set()
    for item in validated_results:
        criterion_id = item["criterion_id"]
        if criterion_id in seen:
            raise FrameRelativeCriterionEvaluationError(
                "criterion_results must not contain duplicate criterion_id values"
            )
        seen.add(criterion_id)

    required_set = set(required)
    bound = [
        item
        for item in validated_results
        if item["criterion_id"] in required_set
    ]
    unbound = [
        item["criterion_id"]
        for item in validated_results
        if item["criterion_id"] not in required_set
    ]
    bound_by_id = {item["criterion_id"]: item for item in bound}

    result, missing = _aggregate(
        required=required,
        bound_by_id=bound_by_id,
    )

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "information": base["information"],
        "information_hash": base["information_hash"],
        "frame": base["frame"],
        "frame_hash": base["frame_hash"],
        "required_criteria": required,
        "success_rule": success_rule,
        "criterion_results": validated_results,
        "bound_criterion_results": bound,
        "unbound_criterion_results": unbound,
        "missing_required_criteria": missing,
        "result": result,
        "accepted": False,
        "truth_claimed": False,
        "state_change_authorized": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    receipt = dict(body)
    receipt["evaluation_hash"] = stable_hash(body)
    return receipt
