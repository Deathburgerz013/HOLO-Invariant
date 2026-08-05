"""Request-level entrypoint for bounded software convergence.

One software request is planned into dependency-ordered capabilities. Each
capability is converged in order, then the resulting project is verified as a
whole. The receipt returns either one runnable result or the exact stage that
blocked convergence.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from holosim.canonical import stable_hash
from holosim.software_capability_planner import (
    run_software_capability_planner,
)
from holosim.software_generator import run_software_generator


RECEIPT_TYPE = "software_convergence_request_receipt"
RECEIPT_VERSION = 1


def _bind_capability_verifier(
    capability_verifier: Any,
    capability: Mapping[str, Any],
) -> Callable[[Path], Mapping[str, Any]]:
    """Bind a capability-aware verifier to the builder verifier contract."""
    bind = getattr(capability_verifier, "bind", None)

    if callable(bind):
        bound_verifier = bind(deepcopy(dict(capability)))
        if not callable(bound_verifier):
            raise TypeError(
                "capability_verifier.bind must return a callable"
            )
        return bound_verifier

    if not callable(capability_verifier):
        raise TypeError("capability_verifier must be callable")

    return capability_verifier


def run_software_convergence_request(
    software_request: Any,
    workspace: str | Path,
    decomposer: Callable[
        [Any, Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
    ],
    comparator: Callable[[Any, Path], Mapping[str, Any]],
    proposer: Callable[..., Mapping[str, Any]],
    capability_verifier: Any,
    project_verifier: Callable[[Path], Mapping[str, Any]],
    *,
    max_cycles: int = 3,
    max_builder_attempts: int = 3,
    environmental_constraints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Converge one request into a verified runnable project or exact blocker."""
    workspace_path = Path(workspace).resolve()
    if not workspace_path.is_dir():
        raise ValueError("workspace must be an existing directory")

    request = deepcopy(software_request)
    constraints = deepcopy(dict(environmental_constraints or {}))
    plan = run_software_capability_planner(
        request,
        decomposer,
        environmental_constraints=constraints,
    )

    generation_receipts: list[dict[str, Any]] = []
    completed_capability_ids: list[str] = []
    blocked_capability_id: str | None = None
    final_verification: dict[str, Any] | None = None

    if plan["planned"] is not True:
        status = "PLANNING_FAILED"
        terminal_reason = plan["terminal_reason"]
        converged = False
        runnable = False
    else:
        status = "BUILDING"
        terminal_reason = "CAPABILITY_CONVERGENCE_IN_PROGRESS"
        converged = False
        runnable = False

        for capability in plan["capabilities"]:
            bound_capability_verifier = _bind_capability_verifier(
                capability_verifier,
                capability,
            )
            receipt = run_software_generator(
                capability,
                workspace_path,
                comparator,
                proposer,
                bound_capability_verifier,
                max_cycles=max_cycles,
                max_builder_attempts=max_builder_attempts,
                environmental_constraints=constraints,
            )
            generation_receipts.append(receipt)

            if receipt["converged"] is not True:
                blocked_capability_id = capability["id"]
                status = "CAPABILITY_FAILED"
                terminal_reason = receipt["terminal_reason"]
                break

            completed_capability_ids.append(capability["id"])
        else:
            verification = project_verifier(workspace_path)
            if not isinstance(verification, Mapping):
                raise TypeError("project_verifier must return a mapping")
            final_verification = deepcopy(dict(verification))
            project_passed = final_verification.get("passed") is True
            project_runnable = final_verification.get("runnable") is True
            run_command = final_verification.get("command")
            has_run_command = (
                isinstance(run_command, str) and bool(run_command.strip())
            )

            if project_passed and project_runnable and has_run_command:
                status = "CONVERGED"
                terminal_reason = "PROJECT_VERIFIED_RUNNABLE"
                converged = True
                runnable = True
            else:
                status = "PROJECT_VERIFICATION_FAILED"
                if project_runnable and not has_run_command:
                    terminal_reason = "PROJECT_RUN_COMMAND_MISSING"
                else:
                    terminal_reason = final_verification.get(
                        "reason",
                        "PROJECT_NOT_VERIFIED_RUNNABLE",
                    )

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "software_request": request,
        "workspace": str(workspace_path),
        "environmental_constraints": constraints,
        "plan_receipt_hash": plan["receipt_hash"],
        "planned_capabilities": deepcopy(plan["capabilities"]),
        "generation_receipts": generation_receipts,
        "completed_capability_ids": completed_capability_ids,
        "blocked_capability_id": blocked_capability_id,
        "final_verification": final_verification,
        "status": status,
        "terminal_reason": terminal_reason,
        "converged": converged,
        "runnable": runnable,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}
