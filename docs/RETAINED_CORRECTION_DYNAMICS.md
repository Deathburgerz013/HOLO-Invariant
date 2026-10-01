# Retained correction dynamics experiment

Author of the proposed loop: Canyon Brock Haney. Implementation and local
verification: Codex. External review is pending.

Status: PARTIAL research specialization. Base: main@861da5b.

Run `python -m holosim.retained_correction_dynamics` to print the comparison.
Run `python -m pytest -q tests/test_retained_correction_dynamics.py` to test it.
Neither command updates production memory, a Spine, or a chain.

## What is tested

This uses explicit finite vectors, Phi(x)=x, B(M,H)=M, and Gamma(r,M,H)=r.
The history H grows by appending observations and trace records; earlier records
are not revised. It contains raw residuals even when their effects are suppressed.
Containment first applies a coordinate mask, then clips the Euclidean norm.
The raw residual norm determines the deadband. Correction is alpha times the
contained residual when a caller-supplied boolean experimental gate is true.
That gate does not validate evidence or establish real authorization.

One declared gap serializes model and history into canonical JSON bytes, clears
working state, and decodes those bytes. RETAINED uses the recovered model;
RESET uses the initial model and deliberately ignores available history;
RECONSTRUCTED starts at the initial model and replays historical observations
with the original controls, without using stored post-update model values.
All three retain the same pre-gap trace. A separate subprocess test verifies a
saved experiment from its original inputs in a fresh Python interpreter.
This is serialization and replay, not a measured period of observer absence,
a hardware crash-recovery test, or a production checkpoint loader.

## Reproducible measurements

Default target is 8, initial model 0, alpha 0.5, threshold 0, clip 10.
There are six updates and a gap after three. All gates permit updates.

| Condition | Model before gap | Model after gap | Final model | Final residual |
| --- | ---: | ---: | ---: | ---: |
| Retained | 7 | 7 | 7.875 | 0.125 |
| Reset | 7 | 0 | 7 | 1 |
| Reconstructed from history | 7 | 7 | 7.875 | 0.125 |
| Deadband threshold 20 | 0 | 0 | 0 | 8 |
| Projection removes the only coordinate | 0 | 0 | 0 | 8 |
| Gain 3, clip 1,000,000 | 72 | 72 | -504 | 512 |
| All gates deny updates | 0 | 0 | 0 | 8 |

These results are derived by running the specified recurrence, not an evaluation
of a language model. The scalar unclipped case has residual recurrence
r_(t+1)=(1-alpha)r_t; the test checks the independent closed-form sequence.
For alpha=0.5 the residual halves. For alpha=3 it alternates and doubles over
the tested six updates. Retention alone does not guarantee improvement.
Deadband and projection yield stopped updates despite nonzero raw errors.
A changing target test shows that a previously resolved mismatch can reopen.

The sum of deltas telescopes to the final model only when recovery preserves
state. RESET also needs its recovery jump (-7 in the default comparison).
Resetting does not erase the historical sum; it changes the current state.
External reconstruction recovers the same numerical behavior as retention
under this deterministic specification. Writable internal persistence is
therefore not the only possible continuity mechanism in this experiment.

## Evidence and limits

Each result binds its normalized numerical configuration, complete trace, gap,
final model, and non-authoritative flags with the existing canonical hash.
Verification reruns from caller-supplied original inputs and compares canonical
bytes. Rehashed altered conclusions, extra fields, integer-for-boolean flags,
and substituted observations are rejected. This does not authenticate those
original inputs or prevent a caller from substituting both input and result.

Bounds are 256 observations and 16 dimensions. Non-finite numbers, booleans as
numbers, invalid controls, dimensional mismatch, and numerical overflow fail.
Inputs are copied. Every result says accepted=false, truth_claimed=false,
write_authority=NONE and execution_authority=NONE.

No general nonlinear convergence, safe-subspace adequacy, environmental truth,
consciousness, actual model self-modification, or correctness of arbitrary
Gamma/B/Phi is established. "Canonical genesis" here names the proposed update;
it is not a new admission or mutation policy. Existing authority boundaries
remain the owners of any future production integration.
