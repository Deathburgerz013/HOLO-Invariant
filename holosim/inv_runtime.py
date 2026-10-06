"""Minimal experimental runtime for INV.

WORK IN PROGRESS.

This module implements bounded invariant-gated state transitions.
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


@dataclass(frozen=True)
class GreaterThanOrEqualInvariant:
    """Bounded INV semantic object for state >= minimum."""

    minimum: int


@dataclass(frozen=True)
class ReplaceTransition:
    """Bounded INV semantic object for replacing state."""

    value: int


@dataclass(frozen=True)
class SubtractTransition:
    """Bounded INV semantic object for subtracting from state."""

    amount: int


INVTransition = ReplaceTransition | SubtractTransition


def evaluate_invariant(
    invariant: GreaterThanOrEqualInvariant,
    state: int,
) -> bool:
    """Evaluate a supported INV invariant using runtime semantics."""

    if not isinstance(invariant, GreaterThanOrEqualInvariant):
        raise TypeError("unsupported INV invariant semantic")

    return state >= invariant.minimum


def evaluate_transition(
    transition: INVTransition,
    state: int,
) -> int:
    """Evaluate a supported INV transition without mutating state."""

    if isinstance(transition, ReplaceTransition):
        return transition.value

    if isinstance(transition, SubtractTransition):
        return state - transition.amount

    raise TypeError("unsupported INV transition semantic")


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


def transition_with_inv_invariant(
    state: int,
    proposed_state: int,
    invariant: GreaterThanOrEqualInvariant,
) -> TransitionResult[int]:
    """Apply a transition using an explicit INV invariant semantic."""

    if not evaluate_invariant(invariant, state):
        raise InvariantViolation("current state violates invariant")

    if not evaluate_invariant(invariant, proposed_state):
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


def execute_inv_transition(
    state: int,
    transition: INVTransition,
    invariant: GreaterThanOrEqualInvariant,
) -> TransitionResult[int]:
    """Evaluate a native transition, then gate its candidate state."""

    if not evaluate_invariant(invariant, state):
        raise InvariantViolation("current state violates invariant")

    candidate_state = evaluate_transition(transition, state)

    if not evaluate_invariant(invariant, candidate_state):
        return TransitionResult(
            previous_state=state,
            proposed_state=candidate_state,
            state=state,
            accepted=False,
        )

    return TransitionResult(
        previous_state=state,
        proposed_state=candidate_state,
        state=candidate_state,
        accepted=True,
    )
