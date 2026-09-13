"""Bounded comparison of solved-condition coverage across two solution states."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def compare_solution_coverage(
    *,
    before: Mapping[str, bool],
    after: Mapping[str, bool],
) -> dict[str, Any]:
    """Compare per-condition solution outcomes without hiding regressions."""

    if set(before) != set(after):
        raise ValueError("before and after must contain the same condition ids")

    condition_ids = sorted(before)

    newly_solved: list[str] = []
    preserved: list[str] = []
    regressed: list[str] = []
    unresolved: list[str] = []

    for condition_id in condition_ids:
        before_value = before[condition_id]
        after_value = after[condition_id]

        if not isinstance(before_value, bool) or not isinstance(after_value, bool):
            raise ValueError("condition outcomes must be booleans")

        if not before_value and after_value:
            newly_solved.append(condition_id)
        elif before_value and after_value:
            preserved.append(condition_id)
        elif before_value and not after_value:
            regressed.append(condition_id)
        else:
            unresolved.append(condition_id)

    before_solved_count = sum(before.values())
    after_solved_count = sum(after.values())
    closure_ready = bool(condition_ids) and not unresolved and not regressed

    return {
        "newly_solved": newly_solved,
        "preserved": preserved,
        "regressed": regressed,
        "unresolved": unresolved,
        "before_solved_count": before_solved_count,
        "after_solved_count": after_solved_count,
        "net_solved_gain": after_solved_count - before_solved_count,
        "closure_ready": closure_ready,
        "accepted": False,
        "write_authority": "NONE",
    }
