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
        results[name] = dict(final_model=result["final_model"], gap=result["gap"],
                             residuals=[r["residual_after"] for r in result["history"]],
                             receipt_hash=result["receipt_hash"])
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
