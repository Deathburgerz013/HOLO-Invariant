"""UI-facing observation model for convergence receipts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def observe_convergence(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a software converger receipt into a stable UI model."""
    if not isinstance(receipt, Mapping):
        raise TypeError("receipt must be a mapping")

    cycles = receipt.get("cycles", [])
    build_receipts = receipt.get("build_receipts", [])

    if not isinstance(cycles, list):
        raise TypeError("receipt cycles must be a list")

    if not isinstance(build_receipts, list):
        raise TypeError("receipt build_receipts must be a list")

    build_receipts_by_hash: dict[str, Mapping[str, Any]] = {}

    for build_receipt in build_receipts:
        if not isinstance(build_receipt, Mapping):
            continue

        receipt_hash = build_receipt.get("receipt_hash")

        if isinstance(receipt_hash, str):
            build_receipts_by_hash[receipt_hash] = build_receipt

    iterations: list[dict[str, Any]] = []

    for cycle in cycles:
        if not isinstance(cycle, Mapping):
            raise TypeError("each cycle must be a mapping")

        comparison = cycle.get("comparison", {})

        if not isinstance(comparison, Mapping):
            raise TypeError("cycle comparison must be a mapping")

        difference_present = (
            comparison.get("relevant_difference") is True
        )
        builder_invoked = cycle.get("builder_invoked") is True
        builder_receipt_hash = cycle.get("builder_receipt_hash")

        matching_build_receipt = None

        if isinstance(builder_receipt_hash, str):
            matching_build_receipt = build_receipts_by_hash.get(
                builder_receipt_hash
            )

        verification_passed = None

        if matching_build_receipt is not None:
            verification = matching_build_receipt.get(
                "final_verification_state"
            )

            if isinstance(verification, Mapping):
                passed = verification.get("passed")

                if isinstance(passed, bool):
                    verification_passed = passed

        if not difference_present:
            status = "CONVERGED"
            difference = comparison.get(
                "reason",
                "NO_RELEVANT_DIFFERENCE",
            )
        elif verification_passed is True:
            status = "CORRECTED"
            difference = comparison.get("description")
        elif verification_passed is False:
            status = "FAILED"
            difference = comparison.get("description")
        else:
            status = "OBSERVED"
            difference = comparison.get("description")

        iterations.append(
            {
                "number": cycle.get("cycle"),
                "status": status,
                "difference_present": difference_present,
                "difference": deepcopy(difference),
                "builder_invoked": builder_invoked,
                "builder_receipt_hash": builder_receipt_hash,
                "verification_passed": verification_passed,
            }
        )

    status = (
        "CONVERGED"
        if receipt.get("converged") is True
        else "STOPPED"
    )

    return {
        "goal": deepcopy(receipt.get("goal")),
        "status": status,
        "terminal_reason": receipt.get("terminal_reason"),
        "iteration_count": len(iterations),
        "correction_count": sum(
            iteration["status"] == "CORRECTED"
            for iteration in iterations
        ),
        "receipt_hash": receipt.get("receipt_hash"),
        "iterations": iterations,
    }