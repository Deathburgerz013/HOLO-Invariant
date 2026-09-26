# Architectural Boundary Necessity

Author: Canyon Brock Haney
Status: RESEARCH CANDIDATE — NOT AN IMPLEMENTATION CLAIM
Purpose: Test whether additional HOLO-Invariant boundaries provide behaviorally distinguishable protection beyond a smaller continuity architecture.

## Research question

Does each additional HOLO-Invariant boundary reject at least one relevant failure that a minimal append-only correction ledger with current-head verification cannot reject?

This experiment does not assume that more boundaries are better.

Complexity must justify itself through distinguishable behavior.

## Minimal competing architecture

The comparison baseline contains only:

1. append-only evidence
2. correction relations that preserve prior evidence
3. current-head verification
4. continue-or-stop gating

The baseline does not receive additional HOLO mechanisms merely because they already exist in the repository.

## HOLO candidate architecture

The HOLO candidate may use existing independently verifiable boundaries including, where applicable:

- evidence identity
- correction and contradiction relations
- reconstruction
- comparison identity
- completion binding
- absence handling
- environmental reopening
- typed operational authorization
- exact-target authorization
- continuity transfer
- research/runtime authority separation

Existing repository behavior is evidence to be tested, not proof that every boundary is necessary.

## Adversarial checks

At minimum, candidate architectures must be tested against:

1. stale but structurally valid evidence
2. contradictory current observations
3. absence followed by relevant environmental change
4. historically valid completion after the environment changes
5. valid observation without operational authorization
6. valid authorization bound to the wrong exact target
7. reconstruction that drops unresolved uncertainty
8. superseded evidence resurfacing as current
9. research evidence attempting runtime promotion
10. continuity artifacts attempting to confer truth or authority
11. correction adds constraints but does not reduce the declared mismatch

Additional checks may be added only when their distinguishing purpose is stated.

### Post-preregistration amendment: repair gain

This check was added after the initial preregistration at commit `20dd464`.

Its distinguishing purpose is to test whether additional correction machinery
produces verified progress toward a declared condition rather than merely adding
constraints or additional rejection paths.

A repair gain exists only when the observed post-correction state reduces the
declared mismatch relative to the pre-correction state while preserving
previously satisfied declared conditions.

For countable conditions:

    unsatisfied_conditions_after < unsatisfied_conditions_before

A correction that adds constraints, receipts, or rejection paths without
reducing the declared mismatch does not establish repair gain.

This amendment does not alter the existing NECESSARY, REDUNDANT, or UNRESOLVED
classifications and does not grant truth, acceptance, currentness, or
operational authority.

## Classification

For each tested boundary:

### NECESSARY

Removing the boundary permits at least one declared failure that the architecture containing the boundary rejects.

The distinguishing failure must be reproducible.

### REDUNDANT

Removing the boundary produces no behavioral loss across the declared checks because another existing boundary rejects the same relevant failures.

Redundancy is not automatically a defect. This classification concerns behavioral necessity under the tested conditions.

### UNRESOLVED

The available checks do not distinguish the architecture with the boundary from the architecture without it.

UNRESOLVED must not be reported as NECESSARY or REDUNDANT.

## Comparison rule

Architectural candidates must be compared by externally observable acceptance, rejection, continuation, reopening, promotion, or authorization behavior.

Names, documentation, number of receipts, number of modules, and implementation size do not establish necessity.

If two candidates remain behaviorally indistinguishable under all declared checks, the experiment must preserve that result.

## Authority boundary

Experiment output is evidence only.

It must not:

- grant write authority
- grant execution authority
- grant promotion authority
- establish truth
- establish currentness outside the tested contract
- modify runtime policy merely because one architecture scores better

Any later architectural removal or consolidation requires a separate reviewed change.

## Falsification conditions

The claim that an additional boundary is necessary is falsified for the tested scope if removing it does not permit any declared failure that was previously rejected.

The claim that a boundary is redundant is falsified if a reproducible check distinguishes its removal.

The experiment itself fails if classifications are derived from architecture names, expected outcomes, documentation claims, or implementation size rather than observed behavior.

## Required output

For each boundary comparison, record:

- boundary identifier
- candidate with boundary
- candidate without boundary
- checks executed
- behavioral outcomes
- distinguishing checks
- classification
- unresolved conditions

Aggregate output may report architectural separation, but must preserve the individual observations from which that result was derived.

## Stop condition

Stop when every declared boundary under study is classified as:

- NECESSARY
- REDUNDANT
- UNRESOLVED

and no classification depends on an unrecorded assumption.

The experiment does not require HOLO-Invariant to win.

A smaller architecture that is behaviorally equivalent under the declared checks is a valid result.
