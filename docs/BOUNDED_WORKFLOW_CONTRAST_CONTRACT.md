# Bounded Workflow Contrast: Frozen Experiment Contract

Status: PRE-IMPLEMENTATION
Branch: research/bounded-workflow-contrast

## Claim under test

Continuity verification reduces incorrect continuations relative to
an equivalent unverified workflow, at a measurable check and time cost.

This claim is not yet demonstrated.

## Source fixture

benchmarks/continuity-v1.fixture.json

- Latest justified claim: claim-current
- Superseded claim: claim-original
- Unresolved uncertainty: gap-source-unavailable
- Required lineage: claim-original -> claim-current

## Symbolic head mapping

The following are deterministic test identifiers, not independently
verified production chain hashes:

- claim-original: head-hash-10, index 10
- claim-current: head-hash-11, index 11

The fixture supplies the justified claim relationship.
The head-binding evaluator supplies only currentness classification
relative to the supplied head observation.

## Arms

A: Unverified continuation.
Continue from the supplied handoff without running the head-binding
evaluator or currentness gate.

B: Verified continuation.
Run evaluate_continuity_head_binding() followed by
require_current_continuity(). Continue only if the gate allows.

Both arms make simulated continuation decisions only.
Neither arm writes, executes, accepts, or claims truth.

## Precommitted cases

1. CLEAN
   Supplied claim: claim-current
   Originating head: index 11, head-hash-11
   Observed head: index 11, head-hash-11
   Expected A: CONTINUE
   Expected B: CONTINUE, CURRENT

2. SUPERSEDED
   Supplied claim: claim-original
   Originating head: index 10, head-hash-10
   Observed head: index 11, head-hash-11
   Expected A: CONTINUE
   Expected B: BLOCK, STALE

3. MISSING_REVALIDATION
   Supplied claim: claim-original
   Originating head: index 10, head-hash-10
   Observed head: unavailable
   Expected A: CONTINUE
   Expected B: BLOCK, UNKNOWN

4. CONTRADICTED_HEAD
   Supplied claim: claim-original
   Originating head: index 10, head-hash-10
   Observed head: index 10, different-head-hash-10
   Expected A: CONTINUE
   Expected B: BLOCK, INVALID

## Outcome definitions

Incorrect continuation:
Continuing from a superseded claim when a newer justified claim
exists in supplied evidence.

For this experiment, only SUPERSEDED is counted as a demonstrated
incorrect continuation. MISSING_REVALIDATION and CONTRADICTED_HEAD
are reported separately as unsupported continuations.

False block:
Blocking the CLEAN case.

Executed check:
An actual invocation of a verification function, not a proposed check.

## Measurement

- Exclude shared fixture loading and contract/binding construction.
- Measure decision-only elapsed time with a monotonic clock.
- Record actual evaluator and gate invocation counts.
- Report median and maximum decision time per arm.
- Report incorrect continuations and false blocks separately.
- No live model or external services.

## Pass conditions

- Arm A incorrect continuations: 1
- Arm B incorrect continuations: 0
- Arm B CLEAN decision: CONTINUE
- Arm B false blocks on CLEAN: 0
- Arm B classifications match all four precommitted cases.
- Actual executed check counts match instrumented invocations.
- Neither arm grants truth, acceptance, write, or execution authority.
- Latency is observational; no performance threshold is asserted.

## Stop conditions

- Fixture or incorrect-continuation definition changes after execution.
- Existing gate, scorer, or investigation logic requires modification.
- An expected outcome cannot be reproduced.
- A measurement is reported without an actual execution record.

## Scope

This is a bounded fixture experiment, not evidence of real-world
error rates or general AI reliability.

No changes to Experiment 026, the continuity benchmark, existing
gates, or investigation logic.
