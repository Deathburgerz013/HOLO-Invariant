"""Minimal experimental runtime for INV.

WORK IN PROGRESS.

This module implements only Experiment 001:
an invariant-gated state transition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class TransitionResult(Generic[T]):
    previous_state: T
    proposed_state: T
    state: T
    accepted: bool


class InvariantViolation(ValueError):
    """Raised when a proposed transition violates an invariant."""


def transition(
    state: T,
    proposed_state: T,
    invariant: Callable[[T], bool],
) -> TransitionResult[T]:
    """Apply a proposed state only when the invariant accepts it."""

    if not invariant(state):
        raise InvariantViolation("current state violates invariant")

    if not invariant(proposed_state):
        return TransitionResult(
            previous_state=state,
            proposed_state=proposed_state,
            state=state,
            accepted=False,
        )

    return TransitionResult(
        previous_state=state,
        proposed_state=proposed_state,
        state=proposed_state,
        accepted=True,
    )
