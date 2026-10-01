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


## Squared-error descent and movement bounds (main@da0b890 extension)

The same owning evaluator now supplies `evaluate_correction_descent_bounds`.
It first replays the experiment from caller-supplied original inputs. It then
checks each actual stored transition, rather than trusting its rounded norms.
The existing CLI prints descent and movement summaries alongside its prior
outputs. No experiment schema or update rule changes.

For a single unchanged observation x, define r=x-M and the actual applied
movement d=M_after-M_before. Squared error V=sum(r_j^2) satisfies the identity

    delta_V = -2 * dot(r,d) + dot(d,d).

In the ideal unclipped full-projection update d=alpha*r, this reduces to

    delta_V = -alpha*(2-alpha)*V.

A nonzero error strictly decreases for 0<alpha<2; alpha=0 stops, alpha=2
oscillates without decreasing, alpha>2 grows. The condition abs(alpha)<1 is
insufficient because it also admits negative gain. Negative gain remains
rejected by the original experiment. These statements concern the specified
real-arithmetic recurrence with a fixed target, not arbitrary correction maps.

For the experiment's ideal coordinate projection P and clipping factor s in
[0,1], let beta=alpha*s. Outside the deadband with a permitted gate,

    delta_V = -beta*(2-beta)*||P*r||^2.

Thus a retained error outside P can remain untouched. A requested uniform
full-error decay rate c requires sufficient projected error and update gain;
clipping, deadband, and denied gates can prevent that condition. The analyzer
checks delta_V <= -c*V + epsilon on each permitted step, with caller-supplied
positive c and nonnegative epsilon. Denied steps are marked null; if none are
permitted, the aggregate is null, not a vacuous success. A positive epsilon
can let the inequality hold with unresolved error or even increasing error.
Strict decrease and remaining error are reported separately.

Decisions use exact Fraction arithmetic over stored binary-float observations
and actual before/after models. Requested deltas can be lost when added to a
large floating model. Exact applied movement, not requested delta, determines
energy and bounds. JSON numeric displays are rounded; very small energies can
display zero while exact remaining-error and strict-decrease flags are true.
Display overflow fails closed. This is an audit of represented numbers, not a
proof that floating computation exactly implements the ideal real recurrence.

A conservative L1 movement bound includes every actual correction and the gap
jump. At every prefix, the analyzer checks telescoping displacement, the
triangle bound, and ||M||_1 <= ||M_initial||_1 + accumulated_movement_1.
L1 bounds also bound Euclidean norms. Cancellation can make final displacement
zero while accumulated movement is large. RESET requires its recovery jump;
local descent alone does not prevent a reset from increasing error.

Default extension measurements: retained and reconstructed movement 7.875;
reset correction movement 14 plus recovery movement 7 gives 21. Against a
budget of 16, reset exceeds the budget while both other modes fit. Reset's
gap increases squared error by 63 despite every local step passing descent.
Deadband and lost projection fit the budget while failing descent. Denied
gates fit the budget while leaving descent unassessed. Gain 3 fails descent.

A finite movement budget is externally supplied and measured, not enforced.
Passing it over a finite trace does not prove infinite-horizon boundedness.
An infinite total-movement bound would imply a bounded state, but not a correct
state. A changing target can reopen error even when every individual update
improves error against its own observation; fixed_target is reported explicitly.
No general convergence certificate is issued. Replay of the analysis binds the
original experiment, c, epsilon, and budget; forged flags, substituted evidence,
extra fields, and rehashed results fail. All original authority limits remain.


## Repeated recovery boundaries (PARTIAL)

An optional `gap_schedule` extends the existing runner and descent evaluator:

```python
original = dict(
    initial=[0.0], observations=[[8.0]] * 6,
    gap_schedule=[{"after": 2, "mode": "RESET"},
                  {"after": 4, "mode": "RECONSTRUCTED"}],
)
experiment = run_retained_correction_experiment(**original)
audit = evaluate_correction_descent_bounds(experiment, original_inputs=original)
```

The list contains at most 32 closed `{after, mode}` objects. Indices must be
strictly increasing integers from zero through the observation count. An empty
list means no gap. Mixed modes are supported; scheduled calls must leave legacy
`gap_after` and `mode` at their defaults. Bounds of 256 observations and 16
coordinates remain. A scheduled experiment and analysis use version 2 with a
`gaps` list. Omitting the schedule preserves the version-1 schema and receipt
hashes, including the default CLI output.

Each boundary serializes the model and full raw history, destroys working
state, then recovers. A later RECONSTRUCTED boundary replays observations,
original gates and previous RESET boundaries. It does not erase reset history
by replaying an uninterrupted trajectory. The schedule is supplied experimental
input, not a discovered environmental history or a production checkpoint policy.

### Rates, jumps and rounding

The same exact rational audit over stored floats measures actual applied updates.
Each scheduled step adds the squared-error contraction ratio `V_after/V_before`;
zero initial energy gives `None`. Displays may round or underflow. Exact flags,
not displayed ratios, determine decrease, remaining error and the decay inequality.
Gates, clipping and rounding can prevent uniform contraction.

Every gap is measured against the same declared target on both sides: the next
observation, or the final observation for an endpoint gap. Gap audit records
before/after energy, ratio, signed energy change and positive progress loss.
`total_gap_progress_loss` sums positive gap changes; `gap_energy_change` is the
signed sum, so improvements cannot cancel the reported loss. `gap_nonincreasing`
requires every jump to be nonincreasing (an empty schedule has no violating jump).
For moving targets these are local comparisons, not global progress certificates.
Every recovery jump enters the L1 path and prefix telescoping bounds.

With target 8, initial 0, alpha 0.5 and boundaries after steps 2 and 4:

| Recovery modes | Final model | L1 movement | Sum of positive gap energy changes |
| --- | ---: | ---: | ---: |
| RETAINED / RETAINED | 7.875 | 7.875 | 0 |
| RECONSTRUCTED / RECONSTRUCTED | 7.875 | 7.875 | 0 |
| RESET / RESET | 6 | 30 | 120 |
| RESET / RECONSTRUCTED | 7.5 | 19.5 | 60 |

Combined rounding tests use initial `[1e16, 0]`, target `[1e16+2, 8]` and
alpha 0.25 across repeated gaps. The requested 0.5 update in the large coordinate
is lost on addition while the other coordinate changes. Exact applied movement
still satisfies the energy identity; retention cannot repair lost updates.

### Defined projection metric and hidden residual

Here the projection is the existing fixed coordinate mask `P`, not an arbitrary
manifold chart. For the map from full residual coordinates to projected residuals,
`J=P` and the Euclidean pullback is `G=J^T J=P`: diagonal entries are 1 for retained
coordinates and 0 for excluded coordinates. The audit derives that diagonal from
the supplied mask. It is positive semidefinite, and positive definite on the full
space only when no coordinate is excluded. It is unchanged by recovery boundaries.
This is NOT a Jacobian or metric of RESET, reconstruction, clipping or the whole
correction map. No differentiable geometry across a discontinuous jump is assumed.

For each scheduled step, exact pre-update energy is split into projected/visible
energy and excluded/hidden energy. Hidden energy is also measured after the step,
with exact unchanged and remaining-error flags (even when a tiny display becomes
zero). Projection does not transfer excluded error into retained coordinates in
this coordinate-wise specialization. Exclusion leaves error uncorrected; it does
not establish a general bound on cross-coordinate leakage in nonlinear models.
For target `[8,3]` and mask `[True,False]`, visible energy shrinks while hidden
energy stays 9; the final total energy is 9.015625, and the metric is singular.

Run the combined demonstration without writing files:

```powershell
python -m holosim.retained_correction_dynamics --multi-gap
```

Replay still requires caller-supplied original inputs and external audit controls.
Rehashed gap, rate, metric, hidden-error, authority or budget changes fail replay.
No acceptance, truth, write or execution authority is added. These finite tests
establish neither general convergence nor production recovery under absence.
