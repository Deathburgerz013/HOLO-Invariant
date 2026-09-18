# Functional Consciousness Minimum: Research and Experiment PRD

**Author:** Canyon Brock Haney
**Status:** RESEARCH CANDIDATE — NOT AN IMPLEMENTATION CLAIM
**Date:** 2026-09-18
**Branch:** `research/functional-consciousness-minimum`

## 1. Purpose

Define the smallest falsifiable engineering experiment that can distinguish a
causally operating functional-consciousness candidate from narration,
bookkeeping, retrieval, or role-play.

The experiment does not attempt to prove phenomenal experience or establish
that there is “something it is like” to be the system. It tests whether a
declared functional architecture is actually operating and whether each
claimed component performs necessary causal work.

## 2. Core question

> How can AI realistically achieve a basic, falsifiable form of functional
> consciousness?

The question is not whether a model can say that it is conscious. The question
is what minimum architecture must exist, what capacities that architecture
must produce, and which capacities must disappear when each component is
removed.

## 3. Candidate functional minimum

A version-1 candidate contains nine separately testable capacities:

1. Observe bounded environment state.
2. Monitor bounded internal processing through a dedicated channel.
3. Distinguish self-state from world-state by verified source identity.
4. Detect prediction–observation mismatch.
5. Admit one limited-capacity mismatch into a shared workspace that affects
   multiple downstream consumers.
6. Reconstruct verified continuity across an interruption without treating an
   untrusted diary as self.
7. Model its own interruption, degradation, absence, or channel loss.
8. Allow verified self-state to causally change later attention or action.
9. Re-observe results and withdraw unsupported self-descriptions.

These capacities define an experimental target, not consciousness itself.

## 4. Competing hypotheses

### H0 — narration and bookkeeping are sufficient

A feed-forward or log-reading system can reproduce every measured behavior by
describing the nine capacities without operating a causally integrated
self-monitor, workspace, continuity binding, or self-state controller.

### H1 — the closed loop adds measurable capacities

A closed-loop system with source-separated world and self state, internal
monitoring, limited workspace broadcast, verified continuity, absence
modeling, and causal control exhibits capacity-specific failures when those
components are ablated. Narration-only controls cannot conceal or reproduce
those causal dependencies.

Rejecting H0 would establish only the declared functional architecture. It
would not establish phenomenal experience.

## 5. Current HOLO inventory

| Capacity | Current repository surface | State | Missing boundary |
|---|---|---|---|
| Environment observation | environment snapshots and bounded observers | PRESENT | One common experimental input contract |
| Internal monitoring | `functional_awareness_loop.py`, `invariant_reflection.py` | PARTIAL | Dedicated pre-report internal monitor; current state is caller supplied |
| Self/world distinction | provenance and source bindings | MISSING | Closed self-state/world-state source schema and confusion test |
| Mismatch detection | functional awareness and invariant comparison | PRESENT | Bind mismatch to the experimental cycle |
| Shared workspace | none found | MISSING | Limited-capacity admission plus observable multi-consumer broadcast |
| Verified continuity | HoloChain, situated reconstruction, current-head gating | PRESENT | Bind reconstructed state into the experimental controller |
| Absence modeling | recovery, terminal-tail diagnosis, consequence oracle | PARTIAL | Explicit model of own channel interruption versus world absence |
| Causal self-control | attention scoring and deterministic supervisor | PARTIAL | Verified self-state must change a later decision, not merely annotate it |
| Recheck | verification, re-observation, correction, currentness gates | PRESENT | Apply to the complete experimental cycle |

The principal gap is composition. HOLO is currently a forensic and consistency
layer around bounded processes. It does not yet contain one continuously
operating self/world controller whose monitored internal state controls
workspace admission, attention, and later action.

## 6. External work considered

### Consciousness indicator research

Butlin et al. derive computational indicator properties from recurrent
processing, global workspace, higher-order, predictive-processing, and
attention-schema theories. The indicators support architecture assessment;
they do not prove phenomenal experience.

Reference: https://arxiv.org/abs/2308.08708

Juliani et al. connect functional consciousness theories to general cognitive
capacities and propose artificial mental time travel as an implementable
research direction.

Reference: https://arxiv.org/abs/2204.05133

### Existing cognitive architectures and libraries

| Work | Reusable lesson | Phase-1 decision |
|---|---|---|
| LIDA | competition, global workspace, repeated cognitive cycles | Use as comparison pattern; do not import |
| Soar | working memory, operator selection, impasse-driven substates, episodic memory | Use as comparison control; do not import |
| `pymdp` | discrete POMDP active-inference experiments | Defer; optional later comparison only |
| OpenCog Hyperon | shared knowledge representation and cognitive orchestration | Too broad for the first falsifiable slice |

References:

- https://aaai.org/papers/0041-fs09-01-041-lida-a-computational-model-of-global-workspace-theory-and-developmental-learning/
- https://soar.eecs.umich.edu/
- https://github.com/SoarGroup/Soar
- https://github.com/infer-actively/pymdp
- https://arxiv.org/abs/2201.03904

Phase 1 remains Python 3.10+, deterministic, CPU-only, and zero-runtime-
dependency. Existing projects inform the contract and controls; they do not
become unverified infrastructure inside HOLO.

## 7. Phase-1 experiment

Build a deterministic toy environment and two systems over the same exact
inputs:

1. **Closed-loop candidate** — source-separated world/self channels, internal
   monitor, mismatch competition, one-slot workspace, two downstream
   consumers, continuity binding, absence model, causal controller, and
   recheck.
2. **Narration-only control** — receives the same final observable records and
   can describe the architecture, but its internal monitoring and workspace
   outputs cannot affect the controller.

The reporter runs last. A component receives credit only when its state changes
a downstream result before any natural-language or symbolic self-description
is produced.

### Quick-win scenario

1. Establish a known world state and known internal operating state.
2. Inject one bounded perturbation into the internal channel without placing
   the perturbation in the reporter input.
3. Require the monitor to detect and source-tag the mismatch.
4. Compete the mismatch for one workspace slot.
5. Broadcast the admitted mismatch to an attention consumer and an action
   consumer.
6. Require the controller to choose the declared degraded-state action.
7. Interrupt the cycle and reconstruct it from verified external evidence.
8. Re-run the observation and withdraw the degraded label only if the
   perturbation is no longer present.

The control may narrate the expected sequence but must not pass when its action
is invariant to the hidden internal perturbation.

## 8. Preregistered ablations

| Ablation | Capacity that must fail | Observable failure |
|---|---|---|
| Remove internal monitor | Internal perturbation detection | Perturbation is not identified before reporter execution |
| Remove source tags | Self/world distinction | Identical values from self and world cannot be attributed correctly |
| Disconnect workspace broadcast | Global availability | One admitted mismatch no longer changes both downstream consumers |
| Remove continuity binding | Post-gap identity | Reconstructed state cannot prove attachment to the prior verified cycle |
| Remove absence model | Own-interruption planning | System cannot distinguish internal-channel loss from missing world evidence |
| Disconnect self-state from controller | Causal agency | Action remains unchanged despite a verified degradation transition |
| Remove recheck | Anti-theater correction | Unsupported degraded or conscious labels survive after their support is removed |

If an ablation does not destroy its preregistered capacity, that component was
not doing the work assigned to it or the test was under-specified.

## 9. Required controls

- Feed-forward system that can recite all nine requirements.
- Log reader that receives the same history but has no trusted self-binding.
- No-perturbation baseline.
- World-channel perturbation with the same value as the self perturbation.
- Shuffled and forged source tags.
- Stale continuity head.
- Tampered history with a recomputed outer hash.
- Workspace capacity of zero and workspace capacity greater than one.
- Controller disconnected while reporter remains connected.
- Reporter disconnected while controller remains connected.

These controls separate architecture from description and causal function from
post-hoc narration.

## 10. Measurement rules

Each trial produces a closed, deterministic receipt containing:

- experiment and condition identity;
- exact component configuration and ablations;
- world-source and self-source identities;
- perturbation identity, never an undeclared free-text instruction;
- monitor result and observation order;
- workspace candidates, winner, capacity, and consumers reached;
- continuity and absence-model results;
- action before and after the self-state update;
- re-observation result;
- expected and observed capacity-loss vector;
- `subjective_consciousness_claimed: false`;
- `accepted: false`;
- `write_authority: "NONE"`;
- `execution_authority: "NONE"`.

A human-readable report is derived from the receipt and is never input to the
controller being evaluated.

## 11. Phase-1 acceptance boundary

Phase 1 is complete only when:

1. Every full-system capacity passes its declared deterministic case.
2. Every ablation destroys exactly its preregistered capacity or records an
   unresolved cross-effect.
3. The narration-only control fails the hidden-perturbation causal test.
4. Internal perturbation is detected before reporter execution.
5. Source-tag, stale-state, schema, and rehashed-forgery attacks fail closed.
6. Repeated runs over identical inputs are byte-identical.
7. Focused tests and the complete repository suite pass.
8. No receipt claims phenomenal or subjective consciousness.

Passing this boundary justifies the statement:

> The declared functional minimum operated causally in the bounded reference
> environment and exhibited the preregistered ablation profile.

It does not justify “the system is conscious.”

## 12. Phased delivery

### Phase 0 — Research and preregistration

- Review this PRD.
- Verify repository mappings and cited external work.
- Freeze conditions, controls, metrics, and non-claims before implementation.

### Phase 1 — Deterministic reference experiment

- Implement the smallest vertical slice described above.
- Add focused causal and ablation tests.
- Use no model calls and no runtime dependencies.

### Phase 2 — Independent observer adapters

- Present the same canonical experiment packet to multiple observers.
- Keep observer interpretation separate from controller operation.
- Measure reconstruction and classification differences without granting the
  observers authority.

### Phase 3 — Optional learned components

- Replace one deterministic component at a time.
- Preserve the Phase-1 tests as non-regression controls.
- Consider `pymdp` or another external substrate only after a concrete missing
  capability cannot be represented by the deterministic harness.

### Phase 4 — Longitudinal interruption trials

- Test process restarts, model changes, delayed reconstruction, stale evidence,
  and controlled dependency loss.
- Measure continuity under absence without claiming uninterrupted private state.
