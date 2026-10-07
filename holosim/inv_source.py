"""Minimal source parser and executor for experimental INV syntax.

WORK IN PROGRESS.
"""

from __future__ import annotations

from dataclasses import dataclass

from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    INVTransition,
    ReplaceTransition,
    SubtractTransition,
    TransitionResult,
    execute_inv_transition,
)


class INVSourceError(ValueError):
    """Raised when INV source is invalid or unsupported."""


@dataclass(frozen=True)
class INVProgram:
    state: int
    invariant: GreaterThanOrEqualInvariant
    transition: INVTransition


def parse(source: str) -> INVProgram:
    """Parse the bounded syntax required by INV experiments."""

    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if len(lines) != 3:
        raise INVSourceError("program must contain exactly three declarations")

    state_parts = lines[0].split()
    invariant_parts = lines[1].split()
    transition_parts = lines[2].split()

    if len(state_parts) != 2 or state_parts[0] != "state":
        raise INVSourceError("invalid state declaration")

    if (
        len(invariant_parts) != 4
        or invariant_parts[0] != "invariant"
        or invariant_parts[1] != "state"
        or invariant_parts[2] != ">="
    ):
        raise INVSourceError("unsupported invariant declaration")

    if not transition_parts or transition_parts[0] != "transition":
        raise INVSourceError("invalid transition declaration")

    try:
        state = int(state_parts[1])
        minimum = int(invariant_parts[3])
    except ValueError as exc:
        raise INVSourceError("INV currently supports integer values only") from exc

    invariant = GreaterThanOrEqualInvariant(minimum=minimum)

    if len(transition_parts) == 2:
        try:
            value = int(transition_parts[1])
        except ValueError as exc:
            raise INVSourceError("invalid replacement transition") from exc

        return INVProgram(
            state=state,
            invariant=invariant,
            transition=ReplaceTransition(value=value),
        )

    if len(transition_parts) == 3 and transition_parts[1] == "subtract":
        try:
            amount = int(transition_parts[2])
        except ValueError as exc:
            raise INVSourceError("invalid subtraction amount") from exc

        return INVProgram(
            state=state,
            invariant=invariant,
            transition=SubtractTransition(amount=amount),
        )

    raise INVSourceError("unsupported transition declaration")


def execute(source: str) -> TransitionResult[int]:
    """Parse and execute a bounded INV program."""

    program = parse(source)
    return execute_inv_transition(
        state=program.state,
        transition=program.transition,
        invariant=program.invariant,
    )
