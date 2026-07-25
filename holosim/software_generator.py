"""Bounded correct-software generation orchestration for HOLO/Sim.

The generator records the starting workspace state, delegates bounded
construction and verification to the software converger, and emits a
version-bound generation receipt.

Generation is successful only when verified convergence is reached.
The generator grants no truth, acceptance, or write authority.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from holosim.canonical import stable_hash
from holosim.software_builder import _observe_workspace
from holosim.software_converger import run_software_converger


RECEIPT_TYPE = "software_generation_receipt"
RECEIPT_VERSION = 1


def run_software_generator(
    requested_capability: Any,
    workspace: str | Path,
    comparator: Callable[[Any, Path], Mapping[str, Any]],
    proposer: Callable[..., Mapping[str, Any]],
    verifier: Callable[[Path], Mapping[str, Any]],
    *,
    max_cycles: int = 3,
    max_builder_attempts: int = 3,
    environmental_constraints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate one capability through bounded verified convergence."""

    workspace_path = Path(workspace).resolve()

    if not workspace_path.is_dir():
        raise ValueError("workspace must be an existing directory")

    constraints = deepcopy(dict(environmental_constraints or {}))
    capability = deepcopy(requested_capability)

    starting_state = _observe_workspace(workspace_path)
    base_state_hash = starting_state["workspace_hash"]

    convergence_receipt = run_software_converger(
        capability,
        workspace_path,
        comparator,
        proposer,
        verifier,
        max_cycles=max_cycles,
        max_builder_attempts=max_builder_attempts,
        environmental_constraints=constraints,
    )

    converged = convergence_receipt.get("converged") is True

    build_receipts = convergence_receipt.get("build_receipts")
    changed_software = (
        isinstance(build_receipts, list)
        and len(build_receipts) > 0
    )

    generated = converged and changed_software

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "requested_capability": capability,
        "environmental_constraints": constraints,
        "base_state_hash": base_state_hash,
        "convergence_receipt_hash": convergence_receipt[
            "receipt_hash"
        ],
        "generated": generated,
        "converged": converged,
        "terminal_reason": convergence_receipt.get(
            "terminal_reason"
        ),
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }
