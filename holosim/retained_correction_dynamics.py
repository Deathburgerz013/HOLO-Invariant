"""Bounded numerical experiment, not a runtime memory or admission policy.

Specialization: Phi(x)=x, B(M,H)=M, Gamma(r,M,H)=r. H is an
append-only trace, available for reconstruction but not used by B. A supplied
boolean gate is an experimental control, not proof of external authorization.
The gap destroys working state and recovers it from canonical JSON bytes.
"""
from __future__ import annotations

import json
import math
from copy import deepcopy
from fractions import Fraction
from typing import Any

from holosim.canonical import canonical_bytes, stable_hash

MAX_STEPS = 256
MAX_DIMENSIONS = 16
MODES = ("RETAINED", "RESET", "RECONSTRUCTED")


class RetainedCorrectionDynamicsError(ValueError):
    """Invalid or non-finite experimental data."""


def _number(value: Any) -> float:
    if type(value) not in (int, float):
        raise RetainedCorrectionDynamicsError("numbers must be finite, not booleans")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise RetainedCorrectionDynamicsError("number outside finite range") from exc
    if not math.isfinite(result):
        raise RetainedCorrectionDynamicsError("numbers must be finite")
    return result


def _vector(value: Any, dimension: int | None = None) -> list[float]:
    if type(value) is not list or not 1 <= len(value) <= MAX_DIMENSIONS:
        raise RetainedCorrectionDynamicsError("vector dimension outside bounds")
    if dimension is not None and len(value) != dimension:
        raise RetainedCorrectionDynamicsError("vector dimensions differ")
    return [_number(item) for item in value]


def _norm(value: list[float]) -> float:
    return _number(math.hypot(*value))


def run_retained_correction_experiment(
    *, initial: list, observations: list, alpha: float = 0.5,
    threshold: float = 0.0, clip: float = 10.0, projection: list | None = None,
    gates: list | None = None, gap_after: int = 1, mode: str = "RETAINED",
) -> dict:
    """Run finite linear correction cycles with one serialization/recovery gap.

    gap_after counts completed updates (0 and len(observations) are valid).
    Projection is a coordinate mask followed by Euclidean clipping; deadband
    uses the raw residual norm. History preserves every raw residual, including
    suppressed and gated updates. RESET retains history but deliberately does
    not consult it. RECONSTRUCTED replays observations using the same controls,
    not stored post-update models. All mutation is confined to local copies.
    """
    model = _vector(initial)
    dimension = len(model)
    if type(observations) is not list or not 1 <= len(observations) <= MAX_STEPS:
        raise RetainedCorrectionDynamicsError("observation count outside bounds")
    samples = [_vector(item, dimension) for item in observations]
    alpha, threshold, clip = map(_number, (alpha, threshold, clip))
    if alpha < 0 or threshold < 0 or clip <= 0:
        raise RetainedCorrectionDynamicsError("invalid alpha, threshold, or clip")
    if type(mode) is not str or mode not in MODES:
        raise RetainedCorrectionDynamicsError("unknown recovery mode")
    if type(gap_after) is not int or not 0 <= gap_after <= len(samples):
        raise RetainedCorrectionDynamicsError("gap index outside bounds")
    mask = [True] * dimension if projection is None else deepcopy(projection)
    gate_values = [True] * len(samples) if gates is None else deepcopy(gates)
    for values, count in ((mask, dimension), (gate_values, len(samples))):
        if type(values) is not list or len(values) != count or any(type(v) is not bool for v in values):
            raise RetainedCorrectionDynamicsError("projection and gates require exact boolean lists")
    config = dict(initial=_vector(initial), observations=samples, alpha=alpha,
                  threshold=threshold, clip=clip, projection=mask, gates=gate_values,
                  gap_after=gap_after, mode=mode)

    def step(before: list[float], observed: list[float], gate: bool) -> dict:
        raw = [_number(x - m) for x, m in zip(observed, before)]
        raw_norm = _norm(raw)
        contained = [r if keep else 0.0 for r, keep in zip(raw, mask)]
        projected_norm = _norm(contained)
        if raw_norm <= threshold:
            contained = [0.0] * dimension
        elif projected_norm > clip:
            contained = [_number((r / projected_norm) * clip) for r in contained]
        delta = [_number(alpha * r) if gate else 0.0 for r in contained]
        after = [_number(m + d) for m, d in zip(before, delta)]
        remaining = [_number(x - m) for x, m in zip(observed, after)]
        return dict(observation=observed[:], model_before=before[:], raw_residual=raw,
                    contained_residual=contained, gate=gate, delta=delta, model_after=after,
                    residual_before=raw_norm, residual_after=_norm(remaining),
                    update_stopped=all(d == 0 for d in delta))

    history: list[dict] = []
    gap = None
    for index in range(len(samples) + 1):
        if index == gap_after:
            # Snapshot bytes are the only retained state across this boundary.
            checkpoint = canonical_bytes(dict(model=model, history=history))
            before = model[:]
            history_bytes = canonical_bytes(history)
            model, history = [], []
            recovered = json.loads(checkpoint)
            history = recovered["history"]
            if mode == "RETAINED":
                model = recovered["model"]
            else:
                model = config["initial"][:]
                if mode == "RECONSTRUCTED":
                    for past in history:
                        model = step(model, past["observation"], past["gate"])["model_after"]
            gap = dict(before=before, after=model[:], checkpoint_sha256=stable_hash(recovered),
                       history_preserved=canonical_bytes(history) == history_bytes,
                       recovery_jump=[_number(a - b) for a, b in zip(model, before)])
        if index == len(samples):
            break
        record = step(model, samples[index], gate_values[index])
        history.append(record)
        model = record["model_after"][:]
    body = dict(type="retained_correction_dynamics", version=1, config=config,
                history=history, gap=gap, final_model=model,
                accepted=False, truth_claimed=False, write_authority="NONE",
                execution_authority="NONE")
    return {**body, "receipt_hash": stable_hash(body)}


def verify_retained_correction_experiment(receipt: dict, **inputs: Any) -> bool:
    """Replay from caller-supplied original inputs; a self-hash is insufficient."""
    expected = run_retained_correction_experiment(**inputs)
    if type(receipt) is not dict or canonical_bytes(receipt) != canonical_bytes(expected):
        raise RetainedCorrectionDynamicsError("experiment does not match supplied inputs")
    return True



def evaluate_correction_descent_bounds(
    experiment: dict, *, original_inputs: dict, decay_rate: float = 0.5,
    deadband_allowance: float = 0.0, movement_budget: float = 16.0,
) -> dict:
    """Measure finite-trace descent and movement after original-input replay.

    Exact rational comparisons use the stored finite binary floats. Energy is
    computed from observation minus actual before/after models, rather than
    rounded residual norms. Movement includes actual applied updates AND the
    recovery jump. A supplied finite budget is a measurement threshold, not an
    enforced cap or infinite-horizon bound. Gates remain experimental controls.
    """
    if type(original_inputs) is not dict:
        raise RetainedCorrectionDynamicsError("original inputs must be a dictionary")
    verify_retained_correction_experiment(experiment, **original_inputs)
    controls = [decay_rate, deadband_allowance, movement_budget]
    c, epsilon, budget = [Fraction(_number(value)) for value in controls]
    if c <= 0 or epsilon < 0 or budget < 0:
        raise RetainedCorrectionDynamicsError("invalid decay rate, allowance, or budget")

    def vec(values: list) -> list[Fraction]:
        return [Fraction(value) for value in values]

    def difference(left: list, right: list) -> list[Fraction]:
        return [a - b for a, b in zip(vec(left), vec(right))]

    def energy(observed: list, model: list) -> Fraction:
        return sum((v * v for v in difference(observed, model)), Fraction(0))

    def l1(values: list[Fraction]) -> Fraction:
        return sum(map(abs, values), Fraction(0))

    def display(value: Fraction) -> float:
        # Decisions are exact; the finite JSON display can round/underflow.
        try:
            return _number(float(value))
        except OverflowError as exc:
            raise RetainedCorrectionDynamicsError("analysis outside finite display range") from exc

    initial = experiment["config"]["initial"]
    gap_index = experiment["config"]["gap_after"]
    rows = experiment["history"]
    correction_total = Fraction(0)
    gap_move = difference(experiment["gap"]["after"], experiment["gap"]["before"])
    recovery_total = l1(gap_move)
    total = Fraction(0)
    accumulated = [Fraction(0)] * len(initial)
    prefixes = []
    checked = []

    def movement(move: list[Fraction], model: list) -> None:
        nonlocal total, accumulated
        total += l1(move)
        accumulated = [a + d for a, d in zip(accumulated, move)]
        displacement = difference(model, initial)
        prefixes.append(dict(
            movement_l1=display(total), displacement_l1=display(l1(displacement)),
            triangle_bound_held=l1(displacement) <= total,
            model_bound_held=l1(vec(model)) <= l1(vec(initial)) + total,
            telescoping_held=displacement == accumulated,
            within_budget=total <= budget,
        ))

    for index in range(len(rows) + 1):
        if index == gap_index:
            movement(gap_move, experiment["gap"]["after"])
        if index == len(rows):
            break
        row = rows[index]
        v_before = energy(row["observation"], row["model_before"])
        v_after = energy(row["observation"], row["model_after"])
        dv = v_after - v_before
        actual_delta = difference(row["model_after"], row["model_before"])
        raw = difference(row["observation"], row["model_before"])
        identity_rhs = -2 * sum((r * d for r, d in zip(raw, actual_delta)), Fraction(0)) + sum((d*d for d in actual_delta), Fraction(0))
        requested_delta = vec(row["delta"])
        correction_total += l1(actual_delta)
        checked.append(dict(
            index=index, gate=row["gate"], energy_before=display(v_before),
            energy_after=display(v_after), energy_change=display(dv),
            energy_identity_held=dv == identity_rhs,
            strictly_decreased=dv < 0, nonincreasing=dv <= 0,
            descent_inequality_held=(dv <= -c * v_before + epsilon) if row["gate"] else None,
            requested_update_applied_exactly=actual_delta == requested_delta,
            error_remains=v_after > 0, applied_update_stopped=not any(actual_delta),
        ))
        movement(actual_delta, row["model_after"])

    target = rows[min(gap_index, len(rows) - 1)]["observation"]
    gap_dv = energy(target, experiment["gap"]["after"]) - energy(target, experiment["gap"]["before"])
    permitted = [row for row in checked if row["gate"]]
    body = dict(
        type="correction_descent_bounds", version=1,
        experiment_hash=experiment["receipt_hash"],
        decay_rate=display(c), deadband_allowance=display(epsilon),
        movement_budget=display(budget), steps=checked, prefixes=prefixes,
        fixed_target=all(row["observation"] == rows[0]["observation"] for row in rows),
        permitted_step_count=len(permitted),
        descent_inequality_held_on_permitted_steps=(all(row["descent_inequality_held"] for row in permitted) if permitted else None),
        all_steps_strictly_decrease=all(row["strictly_decreased"] for row in checked),
        gap_energy_change=display(gap_dv), gap_nonincreasing=gap_dv <= 0,
        correction_movement_l1=display(correction_total),
        recovery_movement_l1=display(recovery_total), total_movement_l1=display(total),
        movement_within_budget=total <= budget,
        all_prefix_bounds_held=all(p["triangle_bound_held"] and p["model_bound_held"] and p["telescoping_held"] for p in prefixes),
        accepted=False, truth_claimed=False, write_authority="NONE",
        execution_authority="NONE",
    )
    return {**body, "receipt_hash": stable_hash(body)}


def verify_correction_descent_bounds(receipt: dict, experiment: dict, **inputs: Any) -> bool:
    """Recompute the analysis with its original experiment and external controls."""
    expected = evaluate_correction_descent_bounds(experiment, **inputs)
    if type(receipt) is not dict or canonical_bytes(receipt) != canonical_bytes(expected):
        raise RetainedCorrectionDynamicsError("analysis does not match supplied evidence")
    return True


def main() -> None:
    """Print a reproducible comparison and counterexamples; no files are written."""
    cases = {mode: dict(mode=mode) for mode in MODES}
    cases.update(DEADBAND=dict(threshold=20.0), PROJECTION_LOSS=dict(projection=[False]),
                 UNSTABLE_GAIN=dict(alpha=3.0, clip=1_000_000.0),
                 GATED=dict(gates=[False] * 6))
    results = {}
    for name, overrides in cases.items():
        inputs = dict(initial=[0.0], observations=[[8.0]] * 6, gap_after=3)
        inputs.update(overrides)
        result = run_retained_correction_experiment(**inputs)
        analysis = evaluate_correction_descent_bounds(result, original_inputs=inputs)
        results[name] = dict(analysis_hash=analysis["receipt_hash"],
                             descent_held=analysis["descent_inequality_held_on_permitted_steps"],
                             gap_nonincreasing=analysis["gap_nonincreasing"],
                             total_movement_l1=analysis["total_movement_l1"],
                             movement_within_budget=analysis["movement_within_budget"],
                             final_model=result["final_model"], gap=result["gap"],
                             residuals=[r["residual_after"] for r in result["history"]],
                             receipt_hash=result["receipt_hash"])
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
