"""Bounded comparison of two attempts against declared expected outcomes.

This module measures fixture-relative performance only. It does not establish
general intelligence, external truth, causation, or action authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from holosim.canonical import canonical_bytes, canonical_json, stable_hash


RECEIPT_TYPE = "intelligence_check"
RECEIPT_VERSION = 1
MAX_CRITERIA = 1_000
MAX_INPUT_BYTES = 65_536


def evaluate_intelligence_check(
    *,
    task_id: str,
    criteria: list[dict[str, Any]],
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compare complete attempts against one unchanged declared criterion set."""

    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id must be a non-empty string")

    if not isinstance(criteria, list) or not criteria:
        raise ValueError("criteria must be a non-empty list")

    if type(before) is not dict or type(after) is not dict:
        raise ValueError("attempts must be dictionaries")

    if len(criteria) > MAX_CRITERIA:
        raise ValueError("criteria exceed maximum count")

    input_packet = {
        "task_id": task_id,
        "criteria": criteria,
        "before": before,
        "after": after,
    }
    if len(canonical_bytes(input_packet)) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds maximum canonical byte size")

    expected: dict[str, Any] = {}

    for criterion in criteria:
        if type(criterion) is not dict or set(criterion) != {"id", "expected"}:
            raise ValueError("invalid criterion schema")

        criterion_id = criterion["id"]
        if not isinstance(criterion_id, str) or not criterion_id.strip():
            raise ValueError("invalid criterion id")
        if criterion_id in expected:
            raise ValueError("duplicate criterion id")

        expected[criterion_id] = deepcopy(criterion["expected"])

    declared_ids = set(expected)

    if set(before) - declared_ids or set(after) - declared_ids:
        raise ValueError("unexpected observation")

    complete = set(before) == declared_ids and set(after) == declared_ids

    def score(attempt: dict[str, Any]) -> int:
        return sum(
            canonical_json(attempt[key]) == canonical_json(expected[key])
            for key in declared_ids
            if key in attempt
        )

    before_score = score(before)
    after_score = score(after)

    if not complete:
        result = "UNAVAILABLE"
    elif after_score > before_score:
        result = "IMPROVED"
    elif after_score < before_score:
        result = "REGRESSED"
    else:
        result = "UNCHANGED"

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "task_id": task_id,
        "criteria": deepcopy(criteria),
        "before": deepcopy(before),
        "after": deepcopy(after),
        "before_score": before_score if complete else None,
        "after_score": after_score if complete else None,
        "result": result,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {**body, "receipt_hash": stable_hash(body)}



def verify_intelligence_check_receipt(receipt: Any) -> bool:
    """Replay declared inputs and require exact receipt identity."""

    if type(receipt) is not dict:
        return False

    if (
        receipt.get("type") != RECEIPT_TYPE
        or type(receipt.get("version")) is not int
        or receipt["version"] != RECEIPT_VERSION
    ):
        return False

    try:
        expected = evaluate_intelligence_check(
            task_id=receipt["task_id"],
            criteria=receipt["criteria"],
            before=receipt["before"],
            after=receipt["after"],
        )

        return (
            set(receipt) == set(expected)
            and canonical_json(receipt) == canonical_json(expected)
        )
    except (KeyError, ValueError, TypeError, RecursionError):
        return False
