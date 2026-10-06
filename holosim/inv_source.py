"""Minimal source parser and executor for experimental INV syntax.

WORK IN PROGRESS.
"""

from __future__ import annotations

from dataclasses import dataclass

from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    TransitionResult,
    transition_with_inv_invariant,
)


class INVSourceError(ValueError):
    """Raised when INV source is invalid or unsupported."""


@dataclass(frozen=True)
class INVProgram:
    state: int
    invariant: GreaterThanOrEqualInvariant
    proposed_state: int


def parse(source: str) -> INVProgram:
    """Parse the bounded syntax required by Experiments 002 and 003."""

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

    if len(transition_parts) != 2 or transition_parts[0] != "transition":
        raise INVSourceError("invalid transition declaration")

    try:
        state = int(state_parts[1])
        minimum = int(invariant_parts[3])
        proposed_state = int(transition_parts[1])
    except ValueError as exc:
        raise INVSourceError("INV currently supports integer values only") from exc

    return INVProgram(
        state=state,
        invariant=GreaterThanOrEqualInvariant(minimum=minimum),
        proposed_state=proposed_state,
    )


def execute(source: str) -> TransitionResult[int]:
    """Parse and execute a bounded INV program."""

    program = parse(source)
    return transition_with_inv_invariant(
        state=program.state,
        proposed_state=program.proposed_state,
        invariant=program.invariant,
    )
