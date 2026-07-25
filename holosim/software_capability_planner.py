"""Bounded software capability planning for HOLO/Sim.

The planner decomposes one software request into an ordered list of
bounded capabilities. It does not generate, verify, complete, accept,
or authorize software changes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping, Sequence

from holosim.canonical import stable_hash


RECEIPT_TYPE = "software_capability_plan_receipt"
RECEIPT_VERSION = 1


def _valid_dependency_order(
    capabilities: Sequence[Mapping[str, Any]],
) -> bool:
    seen_ids: set[str] = set()

    for capability in capabilities:
        capability_id = capability.get("id")
        requirement = capability.get("requirement")
        depends_on = capability.get("depends_on")

        if not isinstance(capability_id, str) or not capability_id:
            return False

        if capability_id in seen_ids:
            return False

        if not isinstance(requirement, str) or not requirement:
            return False

        if not isinstance(depends_on, list):
            return False

        if any(
            not isinstance(dependency_id, str)
            or not dependency_id
            or dependency_id not in seen_ids
            for dependency_id in depends_on
        ):
            return False

        if len(depends_on) != len(set(depends_on)):
            return False

        seen_ids.add(capability_id)

    return bool(capabilities)


def run_software_capability_planner(
    software_request: Any,
    decomposer: Callable[
        [Any, Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
    ],
    *,
    environmental_constraints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce an ordered, bounded capability plan receipt."""

    request = deepcopy(software_request)
    constraints = deepcopy(dict(environmental_constraints or {}))

    proposed_capabilities = decomposer(
        deepcopy(request),
        deepcopy(constraints),
    )

    capabilities: list[dict[str, Any]] = []
    planned = False
    terminal_reason = "INVALID_CAPABILITY_DEPENDENCY_ORDER"

    if (
        isinstance(proposed_capabilities, Sequence)
        and not isinstance(
            proposed_capabilities,
            (str, bytes, bytearray),
        )
        and all(
            isinstance(capability, Mapping)
            for capability in proposed_capabilities
        )
    ):
        copied_capabilities = [
            deepcopy(dict(capability))
            for capability in proposed_capabilities
        ]

        if _valid_dependency_order(copied_capabilities):
            capabilities = copied_capabilities
            planned = True
            terminal_reason = "CAPABILITY_PLAN_COMPLETE"

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "software_request": request,
        "environmental_constraints": constraints,
        "capabilities": capabilities,
        "planned": planned,
        "terminal_reason": terminal_reason,
        "generated": False,
        "verified": False,
        "completed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }