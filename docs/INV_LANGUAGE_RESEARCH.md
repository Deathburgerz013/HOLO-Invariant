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

## Experiment 004: Native Transition Semantics

### Question

Can INV represent a state transition as an explicit semantic operation, evaluate its proposed consequence, and check that consequence against an INV invariant before state changes?

### Required Behavior

Given an INV program containing:

    state 5
    invariant state >= 0
    transition subtract 6

1. Parse the transition into an explicit bounded INV semantic representation.
2. Preserve that transition representation through execution.
3. Evaluate the transition against the current state to produce a candidate state.
4. Evaluate the candidate state against the existing INV invariant semantic.
5. Reject the candidate state `-1` because it violates `state >= 0`.
6. Preserve the previous valid state as `5`.
7. Do not require an arbitrary host-language callable to express the transition.

### Falsifiable Boundary

The experiment fails if the parsed transition must be converted into an arbitrary host-language callback before execution.

The experiment fails if unsupported transition semantics are silently accepted or delegated to host-language evaluation.

The experiment fails if the transition mutates committed state before invariant validation.

The experiment fails if rejection does not preserve the previous valid state.

### Scope

Experiment 004 does not require a general expression or arithmetic system. The only required transition semantic is bounded integer subtraction.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- The parser represented bounded integer subtraction as an explicit INV transition semantic object.
- The transition representation remained non-callable through parsing and execution.
- INV runtime semantics evaluated the transition against the current state to produce a candidate state.
- `state 5` with `transition subtract 6` produced candidate state `-1` without mutating the committed state.
- The existing INV invariant semantic rejected candidate state `-1` against `state >= 0`.
- Rejection preserved the previous valid state as `5`.
- A valid subtraction transition was accepted and committed its candidate state.
- Unsupported transition source failed closed.
- An unsupported transition semantic failed closed rather than being delegated to host-language evaluation.
- Targeted INV tests: 19 passed.
- Full repository suite: 3498 passed, 5 skipped.

This establishes only the bounded native subtraction transition semantic required by Experiment 004. It does not establish a general arithmetic system, expression system, or complete programming language.

## Experiment 005: Unified Transition Semantics

### Question

Can every accepted INV transition declaration be represented and executed through one explicit transition-semantic path without a separate raw proposed-state execution path?

### Required Behavior

Given the existing INV programs:

    state 5
    invariant state >= 0
    transition -1

and:

    state 5
    invariant state >= 0
    transition subtract 6

1. Parse `transition -1` into an explicit bounded replacement-transition semantic.
2. Continue parsing `transition subtract 6` into its explicit subtraction-transition semantic.
3. Represent both declarations through the same transition field in the parsed INV program.
4. Evaluate both transition semantics through the same bounded transition-evaluation path.
5. Produce candidate state `-1` for both programs.
6. Reject both candidates against `state >= 0`.
7. Preserve the previous valid state as `5`.
8. Preserve the observable behavior established by the earlier experiments.

### Falsifiable Boundary

The experiment fails if an accepted transition declaration remains represented as a raw proposed state outside the explicit transition-semantic model.

The experiment fails if execution requires separate semantic and raw proposed-state transition paths.

The experiment fails if unifying the representation changes the established accept, reject, candidate-state, or preserved-state behavior.

The experiment fails if unsupported transition semantics are silently accepted or delegated to arbitrary host-language evaluation.

### Scope

Experiment 005 does not add new arithmetic operators or a general expression system. It only tests whether the two transition forms already established by earlier experiments can share one explicit semantic representation and execution path.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- `transition -1` is represented as an explicit `ReplaceTransition` semantic rather than a raw proposed-state field.
- `transition subtract 6` remains represented as an explicit `SubtractTransition` semantic.
- Both accepted transition forms are carried through the same `INVProgram.transition` field.
- Both transition forms are evaluated through the same bounded `evaluate_transition` semantic path.
- Both forms produce candidate state `-1` from the bounded test programs.
- Both candidates are rejected against `state >= 0` while preserving previous valid state `5`.
- Valid replacement transitions remain accepted through the unified native path.
- Unsupported transition semantics continue to fail closed.
- The legacy `proposed_state` field is no longer part of `INVProgram`.
- Targeted INV suite: 27 passed.
- Full repository suite: 3506 passed, 5 skipped.

This establishes only that the two transition forms already introduced by earlier experiments can share one explicit transition-semantic representation and execution path. It does not establish a general transition algebra, arithmetic system, expression system, or complete programming language.
