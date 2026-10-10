"""Bounded, read-only checkpoint recoverability experiment."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal, Mapping


MAX_DECLARED_STATES = 10_000
MAX_SUCCESSORS_PER_STATE = 1_000
MAX_IDENTIFIER_LENGTH = 256

Status = Literal["REACHABLE", "UNREACHABLE", "UNKNOWN"]


@dataclass(frozen=True)
class RecoverabilityResult:
    status: Status
    path: tuple[str, ...]
    explored_states: int


def evaluate_checkpoint_recoverability(
    *,
    checkpoint: str,
    goal: str,
    transitions: Mapping[str, tuple[str, ...]],
    max_states: int,
) -> RecoverabilityResult:
    """Search declared transitions without executing or modifying anything."""

    if type(max_states) is not int or max_states < 1:
        raise ValueError("max_states must be a positive integer")

    if not isinstance(checkpoint, str) or not checkpoint or len(checkpoint) > MAX_IDENTIFIER_LENGTH:
        raise ValueError("checkpoint must be a nonempty string")

    if not isinstance(goal, str) or not goal or len(goal) > MAX_IDENTIFIER_LENGTH:
        raise ValueError("goal must be a nonempty string")

    if len(transitions) > MAX_DECLARED_STATES:
        raise ValueError("declared graph exceeds state limit")

    for state, successors in transitions.items():
        if not isinstance(state, str) or not state or len(state) > MAX_IDENTIFIER_LENGTH:
            raise ValueError("invalid state identifier")

        if not isinstance(successors, tuple):
            raise ValueError("transitions must contain tuples")

        if len(successors) > MAX_SUCCESSORS_PER_STATE:
            raise ValueError("successor collection exceeds limit")

        for successor in successors:
            if not isinstance(successor, str) or not successor or len(successor) > MAX_IDENTIFIER_LENGTH:
                raise ValueError("invalid successor state")

    if checkpoint not in transitions or goal not in transitions:
        return RecoverabilityResult("UNKNOWN", (), 0)

    queue = deque([(checkpoint, (checkpoint,))])
    visited = {checkpoint}
    incomplete = False
    budget_exhausted = False
    explored = 0

    while queue:
        state, path = queue.popleft()
        explored += 1

        if state == goal:
            return RecoverabilityResult("REACHABLE", path, explored)

        successors = transitions.get(state)

        if successors is None:
            incomplete = True
            continue

        if not isinstance(successors, tuple):
            raise ValueError("transitions must contain tuples")

        for successor in successors:
            if not isinstance(successor, str) or not successor or len(successor) > MAX_IDENTIFIER_LENGTH:
                raise ValueError("invalid successor state")

            if successor in visited:
                continue

            if successor == goal:
                return RecoverabilityResult(
                    "REACHABLE",
                    path + (goal,),
                    explored,
                )

            if successor not in transitions:
                incomplete = True
                continue

            if len(visited) >= max_states:
                budget_exhausted = True
                continue

            visited.add(successor)
            queue.append((successor, path + (successor,)))

    if incomplete or budget_exhausted:
        return RecoverabilityResult("UNKNOWN", (), explored)

    return RecoverabilityResult("UNREACHABLE", (), explored)