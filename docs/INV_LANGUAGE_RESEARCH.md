# INV Language Research

> **WORK IN PROGRESS**

INV is an experimental programming-language research project.

Its syntax, semantics, invariants, execution model, and name remain subject to correction as implementation and testing expose contradictions.

Nothing in this document is a finalized language specification. Claims become stable only to the extent that they survive implementation, testing, and independent verification.

## Initial Research Question

Can a programming language make explicit, checkable invariants and justified state transitions first-class parts of execution rather than conventions imposed only by surrounding software?

## Current Status

UNRESOLVED

No implementation claim is established by this document.

## Experiment 001: Invariant-Gated Transition

### Question

Can INV reject a proposed state transition when that transition violates an explicitly declared invariant?

### Minimum Concepts

- `state` — the current value being operated on.
- `invariant` — a condition that must remain satisfied.
- `transition` — a proposed change from one state to another.

### Required Behavior

Given a valid current state and a proposed transition:

1. Evaluate the proposed resulting state.
2. Check the declared invariant against that result.
3. Accept the transition only if the invariant remains satisfied.
4. Reject the transition if the invariant would be violated.

### Falsifiable Boundary

The experiment fails if INV accepts a transition that violates the declared invariant.

The experiment also fails if rejection depends on application-specific code rather than the INV execution mechanism itself.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- The minimal INV runtime rejected a proposed state that violated its declared invariant.
- The rejected transition preserved the previous valid state.
- An invalid starting state failed closed.
- `tests/test_inv_runtime.py`: 3 passed.
- Full repository suite: 3482 passed, 5 skipped.

This establishes only the behavior required by Experiment 001. It does not establish INV as a complete programming language or settle the broader research question.

## Experiment 002: Native INV Source Representation

### Question

Can the behavior established by Experiment 001 be expressed as INV source text without expressing the program in Python syntax?

### Minimum Source Concepts

The source representation must be able to declare:

- an initial `state`
- an `invariant`
- a proposed `transition`

### Initial Candidate Form

    state 5
    invariant state >= 0
    transition -1

This syntax is provisional and exists only to make the experiment executable. It is not a finalized INV syntax.

### Required Behavior

Given the candidate program above:

1. Parse the INV source into a bounded internal representation.
2. Establish the initial state as `5`.
3. Evaluate the declared invariant `state >= 0`.
4. Evaluate the proposed transition to `-1`.
5. Reject that transition because the resulting state violates the invariant.
6. Preserve the previous valid state as `5`.

### Falsifiable Boundary

The experiment fails if the INV source cannot be interpreted without using Python syntax as the source language.

The experiment fails if the proposed transition to `-1` is accepted.

The experiment fails if rejection does not preserve the previous valid state.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- INV source text was parsed without using Python syntax as the source language.
- The source declared an initial state, invariant, and proposed transition.
- The proposed transition from `5` to `-1` was rejected because it violated `state >= 0`.
- Rejection preserved the previous valid state as `5`.
- A transition preserving the invariant was accepted.
- Unsupported invariant syntax failed closed.
- INV runtime and source tests: 7 passed.
- Repository integration contracts: 33 passed.
- Full repository suite: 3486 passed, 5 skipped.

This establishes only the bounded native source behavior required by Experiment 002. The parser currently supports only the deliberately restricted syntax exercised by this experiment. It does not establish INV as a complete programming language.

## Experiment 003: Native Invariant Semantics

### Question

Can an INV invariant remain an explicit INV semantic object through execution rather than being converted into an arbitrary host-language callable?

### Required Behavior

Given an INV program containing:

    state 5
    invariant state >= 0
    transition -1

1. Parse the invariant into an explicit bounded INV representation.
2. Preserve the invariant representation through execution.
3. Evaluate the invariant using INV runtime semantics.
4. Reject the proposed transition to `-1`.
5. Preserve the previous valid state as `5`.
6. Do not require an arbitrary Python callable to express the invariant.

### Falsifiable Boundary

The experiment fails if execution requires converting the parsed invariant into an arbitrary host-language callback.

The experiment fails if unsupported invariant semantics are silently accepted or delegated to host-language evaluation.

The experiment fails if a violating transition is accepted or alters the previous valid state.

### Scope

Experiment 003 does not require a general expression language. The only required invariant semantic is the bounded greater-than-or-equal comparison already exercised by Experiment 002.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- The parser represented the declared invariant as an explicit INV semantic object.
- The invariant remained non-callable through parsing and execution.
- INV runtime semantics evaluated the supported greater-than-or-equal invariant directly.
- The proposed transition from `5` to `-1` was rejected.
- Rejection preserved the previous valid state as `5`.
- An invalid current state failed closed.
- An unsupported invariant semantic failed closed rather than being delegated to host-language evaluation.
- Targeted INV tests: 12 passed.
- Full repository suite: 3491 passed, 5 skipped.

This establishes only the bounded native invariant semantic required by Experiment 003. It does not establish a general INV expression system or a complete programming language.
