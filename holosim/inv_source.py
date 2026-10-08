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
    TransitionDecisionReceipt,
    TransitionResult,
    execute_inv_transition,
    execute_inv_transition_with_receipt,
)


class INVSourceError(ValueError):
    """Raised when INV source is invalid or unsupported."""


@dataclass(frozen=True)
class INVProgram:
    state: int
    invariant: GreaterThanOrEqualInvariant
    transition: INVTransition


@dataclass(frozen=True)
class INVSequenceProgram:
    state: int
    invariant: GreaterThanOrEqualInvariant
    transitions: tuple[INVTransition, ...]


@dataclass(frozen=True)
class INVSequenceResult:
    final_state: int
    receipts: tuple[TransitionDecisionReceipt, ...]


def _parse_transition(line: str) -> INVTransition:
    parts = line.split()

    if not parts or parts[0] != "transition":
        raise INVSourceError("invalid transition declaration")

    if len(parts) == 2:
        try:
            return ReplaceTransition(value=int(parts[1]))
        except ValueError as exc:
            raise INVSourceError("invalid replacement transition") from exc

    if len(parts) == 3 and parts[1] == "subtract":
        try:
            return SubtractTransition(amount=int(parts[2]))
        except ValueError as exc:
            raise INVSourceError("invalid subtraction amount") from exc

    raise INVSourceError("unsupported transition declaration")


def parse_sequence(source: str) -> INVSequenceProgram:
    """Parse one state, one invariant, and one or more transitions."""

    if not isinstance(source, str):
        raise INVSourceError("source must be text")

    lines = [line.strip() for line in source.splitlines() if line.strip()]

    if len(lines) < 3:
        raise INVSourceError("program requires at least three declarations")

    state_parts = lines[0].split()
    invariant_parts = lines[1].split()

    if len(state_parts) != 2 or state_parts[0] != "state":
        raise INVSourceError("invalid state declaration")

    if (
        len(invariant_parts) != 4
        or invariant_parts[0] != "invariant"
        or invariant_parts[1] != "state"
        or invariant_parts[2] != ">="
    ):
        raise INVSourceError("unsupported invariant declaration")

    try:
        state = int(state_parts[1])
        minimum = int(invariant_parts[3])
    except ValueError as exc:
        raise INVSourceError("INV currently supports integer values only") from exc

    transitions = tuple(_parse_transition(line) for line in lines[2:])

    return INVSequenceProgram(
        state=state,
        invariant=GreaterThanOrEqualInvariant(minimum=minimum),
        transitions=transitions,
    )


def parse(source: str) -> INVProgram | INVSequenceProgram:
    """Preserve single-transition behavior; accept sequential programs."""

    program = parse_sequence(source)

    if len(program.transitions) == 1:
        return INVProgram(
            state=program.state,
            invariant=program.invariant,
            transition=program.transitions[0],
        )

    return program


def execute(source: str) -> TransitionResult[int]:
    """Execute a single-transition INV program."""

    program = parse(source)

    if not isinstance(program, INVProgram):
        raise INVSourceError("execute supports one transition; use execute_sequence")

    return execute_inv_transition(
        state=program.state,
        transition=program.transition,
        invariant=program.invariant,
    )


def execute_sequence(source: str) -> INVSequenceResult:
    """Execute transitions in order, retaining a receipt for every decision."""

    program = parse_sequence(source)
    state = program.state
    receipts: list[TransitionDecisionReceipt] = []

    for operation in program.transitions:
        receipt = execute_inv_transition_with_receipt(
            state=state,
            transition=operation,
            invariant=program.invariant,
        )
        receipts.append(receipt)
        state = receipt.resulting_state

    return INVSequenceResult(
        final_state=state,
        receipts=tuple(receipts),
    )
