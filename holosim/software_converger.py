"""Bounded software convergence orchestration for HOLO/Sim.

The converger compares observed software against an explicit goal.
It invokes the bounded software builder only while a verified relevant
difference exists, and stops when no relevant difference remains.

Comparison, proposal generation, and verification are injected.
The converger grants no truth, acceptance, or write authority.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from holosim.canonical import stable_hash
from holosim.software_builder import run_software_builder_cycle


RECEIPT_TYPE = "software_converger_receipt"
RECEIPT_VERSION = 1
DEFAULT_MAX_CYCLES = 3


def run_software_converger(
    goal: Any,
    workspace: str | Path,
    comparator: Callable[[Any, Path], Mapping[str, Any]],
    proposer: Callable[..., Mapping[str, Any]],
    verifier: Callable[[Path], Mapping[str, Any]],
    *,
    max_cycles: int = DEFAULT_MAX_CYCLES,
    max_builder_attempts: int = 3,
    environmental_constraints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run bounded compare -> build -> verify -> compare convergence."""
    if not isinstance(max_cycles, int) or isinstance(max_cycles, bool):
        raise TypeError("max_cycles must be an integer")

    if max_cycles < 1:
        raise ValueError("max_cycles must be at least 1")

    workspace_path = Path(workspace).resolve()

    if not workspace_path.is_dir():
        raise ValueError("workspace must be an existing directory")

    constraints = deepcopy(dict(environmental_constraints or {}))

    cycles: list[dict[str, Any]] = []
    build_receipts: list[dict[str, Any]] = []

    converged = False
    terminal_reason: str | None = None

    for cycle_number in range(1, max_cycles + 1):
        comparison = comparator(goal, workspace_path)

        if not isinstance(comparison, Mapping):
            raise TypeError("comparator must return a mapping")

        comparison_record = deepcopy(dict(comparison))

        if (
            comparison_record.get("model_generated") is True
            and comparison_record.get("verified") is not True
        ):
            terminal_reason = "UNVERIFIED_MODEL_COMPARISON"
            cycles.append(
                {
                    "cycle": cycle_number,
                    "comparison": comparison_record,
                    "builder_invoked": False,
                    "builder_receipt_hash": None,
                }
            )
            break

        relevant_difference = (
            comparison_record.get("relevant_difference") is True
        )

        cycle_record: dict[str, Any] = {
            "cycle": cycle_number,
            "comparison": comparison_record,
            "builder_invoked": False,
            "builder_receipt_hash": None,
        }

        if not relevant_difference:
            converged = True
            terminal_reason = comparison_record.get(
                "reason",
                "NO_RELEVANT_DIFFERENCE",
            )
            cycles.append(cycle_record)
            break

        build_receipt = run_software_builder_cycle(
            comparison_record.get("description", goal),
            workspace_path,
            proposer,
            verifier,
            max_attempts=max_builder_attempts,
            environmental_constraints=constraints,
        )

        cycle_record["builder_invoked"] = True
        cycle_record["builder_receipt_hash"] = build_receipt[
            "receipt_hash"
        ]

        cycles.append(cycle_record)
        build_receipts.append(build_receipt)

        final_verification = build_receipt.get(
            "final_verification_state"
        )

        if not isinstance(final_verification, Mapping):
            terminal_reason = "BUILDER_NO_FINAL_VERIFICATION"
            break

        if final_verification.get("passed") is not True:
            terminal_reason = "BUILDER_VERIFICATION_FAILED"
            break

    if not converged and terminal_reason is None:
        terminal_reason = "MAX_CYCLES_REACHED"

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "goal": deepcopy(goal),
        "environmental_constraints": constraints,
        "cycles": cycles,
        "build_receipts": build_receipts,
        "converged": converged,
        "terminal_reason": terminal_reason,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }