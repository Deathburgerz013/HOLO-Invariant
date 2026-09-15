"""Bounded observation of repeated correction-state oscillation.

This module detects structural two-state oscillation in one explicitly named
target's ordered state history. It may identify damping as a candidate, but it
does not calculate a damping magnitude, alter a delta, suppress evidence,
mutate state, or grant authority.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from holosim.canonical import stable_hash


RECEIPT_TYPE = "bounded_correction_dampener_receipt"
RECEIPT_VERSION = 1

INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
NO_OSCILLATION_OBSERVED = "NO_OSCILLATION_OBSERVED"
REVERSAL_OBSERVED = "REVERSAL_OBSERVED"
OSCILLATION_OBSERVED = "OSCILLATION_OBSERVED"

MAX_HISTORY_LENGTH = 256
OSCILLATION_WINDOW_LENGTH = 4


class CorrectionDampenerError(ValueError):
    """Raised when a correction-history boundary is invalid."""


def _required_identity(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise CorrectionDampenerError(
            f"{field} must be a nonempty string"
        )
    if value != value.strip():
        raise CorrectionDampenerError(
            f"{field} cannot contain outer whitespace"
        )
    return value


def _validate_state_ids(state_ids: Sequence[str]) -> list[str]:
    if type(state_ids) not in {list, tuple}:
        raise CorrectionDampenerError(
            "state_ids must be a list or tuple"
        )
    if not state_ids:
        raise CorrectionDampenerError(
            "state_ids must not be empty"
        )
    if len(state_ids) > MAX_HISTORY_LENGTH:
        raise CorrectionDampenerError(
            f"state_ids cannot exceed {MAX_HISTORY_LENGTH} entries"
        )

    return [
        _required_identity(state_id, f"state_ids[{index}]")
        for index, state_id in enumerate(state_ids)
    ]


def _is_two_state_oscillation(
    states: list[str],
    end_index: int,
) -> bool:
    if end_index < OSCILLATION_WINDOW_LENGTH - 1:
        return False

    first = states[end_index - 3]
    second = states[end_index - 2]
    third = states[end_index - 1]
    fourth = states[end_index]

    return (
        first != second
        and first == third
        and second == fourth
    )


def assess_correction_oscillation(
    *,
    target_id: str,
    state_ids: Sequence[str],
) -> dict[str, Any]:
    """Observe exact identity recurrence in one ordered target history.

    ``A -> B -> A`` is preserved as one reversal. At least
    ``A -> B -> A -> B`` is required to identify active two-state
    oscillation and expose damping as a candidate.
    """

    checked_target_id = _required_identity(target_id, "target_id")
    checked_state_ids = _validate_state_ids(state_ids)

    change_indices = [
        index
        for index in range(1, len(checked_state_ids))
        if checked_state_ids[index] != checked_state_ids[index - 1]
    ]
    reversal_indices = [
        index
        for index in range(2, len(checked_state_ids))
        if (
            checked_state_ids[index]
            == checked_state_ids[index - 2]
            and checked_state_ids[index]
            != checked_state_ids[index - 1]
        )
    ]

    oscillation_windows = [
        {
            "start_index": end_index - 3,
            "end_index": end_index,
            "state_ids": [
                checked_state_ids[end_index - 3],
                checked_state_ids[end_index - 2],
            ],
        }
        for end_index in range(3, len(checked_state_ids))
        if _is_two_state_oscillation(
            checked_state_ids,
            end_index,
        )
    ]

    active_oscillation = _is_two_state_oscillation(
        checked_state_ids,
        len(checked_state_ids) - 1,
    )

    if len(checked_state_ids) < 3:
        status = INSUFFICIENT_HISTORY
    elif active_oscillation:
        status = OSCILLATION_OBSERVED
    elif reversal_indices:
        status = REVERSAL_OBSERVED
    else:
        status = NO_OSCILLATION_OBSERVED

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "target_id": checked_target_id,
        "state_ids": checked_state_ids,
        "history_length": len(checked_state_ids),
        "latest_state_id": checked_state_ids[-1],
        "distinct_state_ids": list(dict.fromkeys(checked_state_ids)),
        "change_indices": change_indices,
        "reversal_indices": reversal_indices,
        "oscillation_windows": oscillation_windows,
        "active_oscillation": active_oscillation,
        "status": status,
        "damping_candidate": active_oscillation,
        "damping_applied": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": (
            "Identity recurrence is a structural observation only. It does "
            "not establish that a correction was wrong, that two states are "
            "semantically equivalent, that evidence should be suppressed, "
            "or that damping is authorized. No damping magnitude is inferred "
            "or applied."
        ),
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }