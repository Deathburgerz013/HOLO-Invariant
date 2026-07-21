"""End-to-end runner for bounded cross-instance baseline comparison."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.baseline_observation_compare import (
    build_baseline_observation,
    compare_baseline_observations,
)
from holosim.baseline_promotion_gate import evaluate_baseline_promotion
from holosim.canonical import CanonicalValueError, stable_hash

RUN_TYPE = "cross_instance_baseline_run"
RUN_VERSION = 1


class CrossInstanceRunError(ValueError):
    """Raised when a cross-instance run cannot be constructed."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CrossInstanceRunError(f"{field} must be a non-empty string")
    return value


def run_cross_instance_baseline_check(
    *,
    baseline_id: str,
    baseline_state_hash: str,
    left_observer_id: str,
    left_findings: Mapping[str, str],
    right_observer_id: str,
    right_findings: Mapping[str, str],
    justification_references: Mapping[str, str],
) -> dict[str, Any]:
    """Run observation -> comparison -> proposal gate as one inspectable packet.

    This runner composes existing contracts only. It does not accept truth, create a
    next baseline, or grant write authority.
    """
    baseline = _required_text(baseline_id, "baseline_id")
    state_hash = _required_text(baseline_state_hash, "baseline_state_hash")

    left = build_baseline_observation(
        observer_id=left_observer_id,
        baseline_id=baseline,
        baseline_state_hash=state_hash,
        findings=left_findings,
    )
    right = build_baseline_observation(
        observer_id=right_observer_id,
        baseline_id=baseline,
        baseline_state_hash=state_hash,
        findings=right_findings,
    )
    comparison = compare_baseline_observations(left, right)
    gate = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references=justification_references,
    )

    payload = {
        "type": RUN_TYPE,
        "version": RUN_VERSION,
        "baseline_id": baseline,
        "baseline_state_hash": state_hash,
        "observations": [deepcopy(left), deepcopy(right)],
        "comparison": deepcopy(comparison),
        "promotion_gate": deepcopy(gate),
        "summary": {
            "agreement": list(comparison["agreement"]),
            "extension": list(comparison["extension"]),
            "correction": list(comparison["correction"]),
            "conflict": list(comparison["conflict"]),
            "unknown": list(comparison["unknown"]),
            "proposal_status": gate["status"],
        },
        "next_baseline_created": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        run_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise CrossInstanceRunError(str(exc)) from exc
    return {**payload, "run_id": run_id}
