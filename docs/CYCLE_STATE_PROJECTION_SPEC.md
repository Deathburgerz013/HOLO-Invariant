# Cycle-State Projection Specification

Version: 0.1
Status: Proposed specification
Project: HOLO-Invariant
Authority: Descriptive only

## Purpose

This specification defines a deterministic, read-only projection over existing
HOLO receipts and state-bound evidence.

Its purpose is to answer one bounded question:

> Given one exact validated snapshot of relevant HOLO receipts, what is the
> highest-priority currently justified operational observation about whether
> another bounded check is warranted?

This specification does not create a controller, scheduler, executor, mutable
global state, truth authority, admission authority, or autonomous reasoning loop.

The projection is a view over existing state.

It must not become a new source of truth.

## Core distinction

HOLO operates as a conditional cycle, not an unconditional loop.

A bounded cycle may terminate when present evidence establishes that no further
transition is currently warranted.

Later evidence may reopen evaluation without invalidating the historical result
that was valid for the earlier bounded frame or episode.

The intended lifecycle is:

```text
retain
→ observe
→ evaluate inside a declared frame
→ preserve uncertainty, contradiction, or incompleteness
→ identify only declared next checks
→ bind only explicitly declared verifiers
→ evaluate bounded completion
→ stop when present conditions warrant restraint
→ reopen only when later evidence or dependency change warrants it
```

Stopping means:

```text
No currently justified transition is warranted from this exact snapshot.
```

It does not mean:

```text
No future evidence can ever warrant another transition.
```

## Existing contracts remain authoritative for their own domains

This specification must compose existing receipts without replacing their local
semantics.

Relevant existing domains include:

* Frozen IDX admission and continuity checking.
* Uncertainty records and declared resolution conditions.
* Next-check organization.
* Explicit verifier binding.
* Frame-relative criterion evaluation.
* Environment completion eligibility.
* Environment episode reopening.
* Receipt dependency invalidation and recheck planning.
* Canonical receipt identity.

The projection may summarize those outputs.

It must not reinterpret them into stronger claims.

## Non-authority invariant

Every cycle-state projection is non-authoritative.

A projection must preserve:

```text
truth_claimed: false
accepted: false
execution_authorized: false
state_change_authorized: false
write_authority: NONE
```

No combination of non-authoritative receipts may produce authority that was not
present in the inputs.

A projected state never grants permission to:

* execute a verifier,
* select a verifier,
* accept a claim,
* admit a Spine state,
* mutate IDX,
* append a correction,
* persist state,
* schedule another cycle,
* or declare external truth.

## Snapshot model

A projection must operate over one explicit immutable snapshot manifest.

The snapshot manifest must identify the exact inputs used to derive the
projection.

At minimum it must bind:

```text
PROJECTION_VERSION
IDX_IDENTITY
RECEIPT_HASHES
FRAME_IDENTITIES
EPISODE_IDENTITIES
DEPENDENCY_PLAN_IDENTITIES
```

Where available, it should also preserve:

```text
ENVIRONMENT_ID
CLOCK_ID
WINDOW_START
WINDOW_END
SOURCE_RECEIPT_TYPES
```

The projection must never inspect moving repository or runtime state while
simultaneously deriving and persisting a mutable "current" flag.

Instead:

```text
same projection version
+ same canonical snapshot manifest
+ same validated input receipts
= same cycle-state projection
```

New evidence produces a new snapshot manifest and therefore a new projection.

## Snapshot coherence

Before state derivation, the projection must determine whether supplied receipts
can coherently participate in the same requested projection.

The projection must fail closed when relationships are missing, contradictory,
or cannot be established from explicit identifiers.

It must not guess relationships from natural language.

The following boundaries must be checked when applicable:

### IDX coherence

All projected state must be anchored to the intended IDX identity.

An IDX mismatch, active-hash mismatch, missing slot, unexpected slot, slot-order
mismatch, or slot-hash mismatch must prevent ordinary cycle-state progression.

### Frame coherence

Frame-relative results remain bound to their exact frame identity.

A result produced under one frame must not silently satisfy requirements for
another frame.

The same information may legitimately produce different results under different
frames.

### Episode coherence

Environment completion certificates remain bound to their exact episode,
environment, clock, window, contract, observations, comparisons, measurements,
evidence snapshot, and provenance.

A historical completion certificate remains valid only for the bounded episode
it evaluated.

### Reopen coherence

A valid later reopen receipt may supersede the currentness of an earlier
completion certificate without invalidating that certificate for its historical
window.

A projection must distinguish:

```text
historically valid
```

from:

```text
currently sufficient
```

### Dependency coherence

If a current dependency-recheck plan marks a receipt or dependent result as
requiring recheck, an older successful result must not remain sufficient for the
current projection.

### Organizer coherence

Next-check candidates must preserve source record identity and declared
resolution-condition identity.

A projection must not invent a check for an unresolved record that lacks a
declared resolution condition.

### Verifier-binding coherence

A verifier binding applies only to the exact declared candidate and explicitly
named verifier identity it encloses.

Natural-language similarity must never be treated as verifier identity.

## Cycle-state vocabulary

The initial projected states are:

```text
BLOCKED_INVARIANT
RECHECK_REQUIRED
RESOLUTION_CONDITION_REQUIRED
DECLARED_CHECK_UNBOUND
BOUND_CHECK_AVAILABLE
UNCERTAIN
INCOMPLETE_EVIDENCE
COMPLETE_ELIGIBLE
CURRENTLY_RESTRAINED
```

These states are observations over existing receipts.

They are not commands.

## State semantics

### BLOCKED_INVARIANT

Meaning:

A required continuity or snapshot-coherence boundary failed.

Typical sources include:

* IDX mismatch,
* incompatible snapshot identities,
* contradictory frame relationships,
* incompatible episode relationships,
* missing required identity bindings.

This state is fail-closed.

It must not be collapsed into ordinary restraint.

### RECHECK_REQUIRED

Meaning:

A declared dependency change invalidates present reliance on one or more prior
receipts or results.

An older receipt may remain historically valid while being insufficient for the
current projection.

### RESOLUTION_CONDITION_REQUIRED

Meaning:

An active unresolved record exists but no declared resolution condition is
available.

The projection must not invent one.

### DECLARED_CHECK_UNBOUND

Meaning:

A declared check exists, but its required verifier identity is absent,
unavailable, or otherwise not explicitly bound.

This state must preserve the underlying binding status, including:

```text
VERIFIER_ID_REQUIRED
DECLARED_VERIFIER_UNAVAILABLE
```

### BOUND_CHECK_AVAILABLE

Meaning:

A declared check is explicitly bound to an available verifier.

This means only that the verifier binding exists.

It does not mean:

```text
verified
passed
executed
accepted
true
```

The name `VERIFIED_CHECK_AVAILABLE` must not be used because binding is not
verification.

### UNCERTAIN

Meaning:

The currently relevant bounded evaluation cannot establish a determinate
completion result because an uncertainty or provenance boundary remains open.

The projection must preserve the domain and reason for uncertainty.

Examples may include:

* completion provenance uncertainty,
* completion uncertainty bound failure,
* frame-relative indeterminacy,
* unresolved convergence state.

These must not be flattened into one reasonless global uncertainty.

### INCOMPLETE_EVIDENCE

Meaning:

The current bounded completion episode is structurally evaluable but one or more
required substantive completion conditions failed.

The projection must preserve the failed checks.

### COMPLETE_ELIGIBLE

Meaning:

The currently relevant bounded completion episode satisfies its declared
completion contract and no later relevant reopen or dependency invalidation
supersedes its currentness.

This state means completion eligibility only.

It does not establish truth, acceptance, correction gain, or authority.

### CURRENTLY_RESTRAINED

Meaning:

The validated snapshot contains no currently warranted unresolved transition,
recheck requirement, bound check, incompleteness, uncertainty, invariant
failure, or later reopen that requires another bounded operation.

This is a conditional stop state.

It means:

```text
Nothing in this exact validated snapshot currently warrants another transition.
```

It does not mean:

```text
Nothing will ever need to be checked again.
```

## Required precedence

State derivation must define explicit precedence so two compliant readers cannot
choose different states from the same snapshot.

The initial precedence is:

```text
if required IDX or snapshot coherence fails
    => BLOCKED_INVARIANT

else if a relevant dependency plan requires recheck
    => RECHECK_REQUIRED

else if an active unresolved record lacks a declared resolution condition
    => RESOLUTION_CONDITION_REQUIRED

else if a declared check exists but its required verifier is unbound or unavailable
    => DECLARED_CHECK_UNBOUND

else if a declared check is explicitly bound to an available verifier
    => BOUND_CHECK_AVAILABLE

else if the current relevant completion state is uncertain
    => UNCERTAIN

else if the current relevant completion state is incomplete
    => INCOMPLETE_EVIDENCE

else if the current relevant completion state is complete-eligible
     and no later valid reopen or dependency invalidation supersedes it
    => COMPLETE_ELIGIBLE

else
    => CURRENTLY_RESTRAINED
```

This precedence is provisional until falsification fixtures demonstrate that it
is sufficient and non-contradictory.

## Temporal supersession rule

Currentness must be derived from explicit temporal and identity relationships,
not from whichever receipt is read last.

A later valid reopen receipt may supersede the currentness of an earlier
completion certificate.

The earlier certificate remains valid for its original bounded episode.

The projection therefore must preserve both:

```text
historical_status
current_projection_state
```

where needed.

## Reason codes

Every projected state must include one or more reason codes.

Reason codes must preserve existing repository distinctions rather than replacing
them with weaker labels.

Examples include:

```text
IDX_VERSION_MISMATCH
IDX_ACTIVE_HASH_MISMATCH
IDX_SLOT_MISSING
IDX_SLOT_UNEXPECTED
IDX_SLOT_ORDER_MISMATCH
IDX_SLOT_HASH_MISMATCH
DEPENDENCY_RECHECK_REQUIRED
RESOLUTION_CONDITION_REQUIRED
VERIFIER_ID_REQUIRED
DECLARED_VERIFIER_UNAVAILABLE
DECLARED_VERIFIER_BOUND
COMPLETION_PROVENANCE_UNCERTAIN
COMPLETION_UNCERTAINTY_OUT_OF_BOUNDS
COMPLETION_REQUIREMENT_FAILED
LATER_EPISODE_REOPENED
NO_CURRENT_TRANSITION_WARRANTED
```

Existing exact status codes should be preserved wherever available.

## Source binding

Every projection must identify the receipts that caused the projected result.

A projection without source-receipt identity is invalid.

At minimum:

```text
SOURCE_RECEIPT_TYPE
SOURCE_RECEIPT_HASH
SOURCE_SCOPE
```

should be recoverable for every reason code.

The projection must preserve enough information to answer:

```text
Why did this state exist?
Which receipt caused it?
Under which frame, episode, IDX, or dependency context?
```

## Proposed projection shape

A future implementation, if warranted, may use a shape similar to:

```json
{
  "type": "holo_cycle_state_projection",
  "version": 1,
  "snapshot": {
    "idx_identity": "<id>",
    "receipt_hashes": [],
    "frame_ids": [],
    "episode_ids": [],
    "dependency_plan_ids": []
  },
  "state": "CURRENTLY_RESTRAINED",
  "reason_codes": [],
  "source_receipts": [],
  "current_scope": {
    "frame_id": null,
    "episode_id": null,
    "environment_id": null
  },
  "truth_claimed": false,
  "accepted": false,
  "execution_authorized": false,
  "state_change_authorized": false,
  "write_authority": "NONE",
  "projection_hash": "<stable hash>"
}
```

This is a specification example, not a committed runtime schema.

Field names remain subject to repository review before implementation.

## Falsification fixtures

The specification must be tested with fixtures before any runtime projection
module is added.

### Fixture 1: independent reducer

Two independent implementations receive:

* this specification,
* the same canonical snapshot,
* the same fixture set.

They must independently derive the same:

```text
state
reason_codes
source_receipt identities
scope
```

If both agree across the fixture matrix, a runtime reference reducer may be
unnecessary.

### Fixture 2: permutation invariance

Input receipt order must not change the projected result where order is not
explicitly semantic.

If permutation changes the result without a declared ordering rule, the
specification is incomplete.

### Fixture 3: historical completion and reopen

```text
episode A
→ COMPLETE_ELIGIBLE

later valid reopen
→ episode B
```

The current projection must not return `COMPLETE_ELIGIBLE` solely because
episode A remains historically valid.

Episode A must remain preserved.

### Fixture 4: stale dependency

```text
receipt A supports result B
A changes
dependency plan marks B RECHECK_REQUIRED
old B remains PASS or COMPLETE_ELIGIBLE
```

The projection must return `RECHECK_REQUIRED`.

### Fixture 5: IDX dominance

For an otherwise runnable or complete fixture, mutate one of:

```text
IDX version
active hash
slot presence
slot membership
slot order
slot payload
```

The projection must return `BLOCKED_INVARIANT`.

It must never return `BOUND_CHECK_AVAILABLE` or `COMPLETE_ELIGIBLE`.

### Fixture 6: no invention

An active unresolved record without a declared resolution condition must return:

```text
RESOLUTION_CONDITION_REQUIRED
```

No check may be synthesized from claim text.

### Fixture 7: verifier non-inference

A declared condition that resembles a known verifier must remain unbound until
the verifier identity is explicitly supplied.

### Fixture 8: binding is not verification

`DECLARED_VERIFIER_BOUND` must project only to:

```text
BOUND_CHECK_AVAILABLE
```

It must never imply:

```text
PASS
VERIFIED
TRUE
ACCEPTED
```

### Fixture 9: frame conflict

The same information may pass in one frame and fail or remain indeterminate in
another.

The projection must preserve frame identity and must not collapse those results
into a universal conclusion.

### Fixture 10: missing criterion

A missing required frame criterion must remain:

```text
INDETERMINATE
```

and must not become pass-by-absence.

### Fixture 11: authority monotonicity

No combination of non-authoritative receipts may produce a projection with any
of the following:

```text
truth_claimed: true
accepted: true
execution_authorized: true
state_change_authorized: true
write_authority != NONE
```

### Fixture 12: snapshot coherence

Mix otherwise valid receipts from incompatible:

```text
IDX identities
frames
environments
episodes
dependency contexts
```

The projection must fail closed.

It must not guess which relationships the caller intended.

### Fixture 13: byte and repeat determinism

The same projection version plus the same canonical snapshot must produce the
same projection identity repeatedly.

## Implementation boundary

This specification does not justify production code by itself.

The next implementation step is permitted only if falsification demonstrates
that independent compliant readers cannot reproducibly derive the same result
from this specification and fixture matrix.

If documentation plus fixtures are sufficient, stop.

Do not add a runtime reducer merely because one would be convenient.

## Conditional reference implementation

Only if the specification is falsified by reproducible interpretation
divergence may the repository consider a tiny pure function such as:

```text
derive_cycle_state(snapshot)
```

Any such function must:

* perform no I/O,
* persist nothing,
* schedule nothing,
* execute no verifier,
* select no verifier,
* mutate nothing,
* accept nothing,
* claim no truth,
* grant no authority,
* use explicit immutable inputs,
* preserve source receipt identities,
* and produce deterministic output.

## External evidence boundary

External research systems, models, agents, connected sources, and public
standards may contribute evidence.

Their outputs remain evidence inputs.

They do not become admission authority merely because they are:

* cited,
* recent,
* repeated,
* produced by another model,
* produced by Deep Research,
* produced by a GitHub agent,
* or consistent with prior project conclusions.

External evidence must enter HOLO through the same provenance, frame,
verification, uncertainty, and authority boundaries as other evidence.

## Repository policy separation

Repository operational controls such as branch protection, rulesets, required
checks, and merge restrictions are separate from cycle-state semantics.

Weak repository enforcement may justify operational hardening.

It does not justify changing the meaning of HOLO receipts or adding a new cycle
controller.

## Stop condition for this work

This specification work stops when:

1. snapshot coherence is explicitly defined,
2. precedence is explicit,
3. state meanings preserve existing receipt semantics,
4. authority remains non-increasing,
5. all falsification fixtures are defined,
6. two independent readers can attempt the same fixture matrix.

If independent readers agree, no runtime projection component is warranted.

If they reproducibly disagree, preserve the disagreement and implement only the
smallest pure reference reducer necessary to eliminate that ambiguity.

## Final invariant

> Derive only what the exact current receipts justify, preserve why the result
> exists, stop when no transition is warranted, and reopen only when explicit
> later evidence or dependency change makes another bounded check necessary.
