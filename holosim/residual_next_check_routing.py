"""Read-only routing of unresolved convergence residuals to declared next checks.

This module does not decide truth, resolve contradictions, invent checks,
execute work, mutate source residuals, or grant authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash


class ResidualNextCheckRoutingError(ValueError):
    """Raised when residual routing input violates the bounded contract."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResidualNextCheckRoutingError(
            f"{field} must be a non-empty string"
        )
    return value


def _required_sequence(value: Any, field: str) -> Sequence[Any]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or not value
    ):
        raise ResidualNextCheckRoutingError(
            f"{field} must be a non-empty sequence"
        )
    return value


def _validate_observation(
    observation: Any,
    *,
    scope: str,
    position: str,
) -> None:
    if not isinstance(observation, Mapping):
        raise ResidualNextCheckRoutingError(
            f"{position} must be a mapping"
        )

    for field in (
        "finding_id",
        "statement",
        "scope",
        "status",
        "analysis_id",
        "analysis_receipt_hash",
        "evidence_set_hash",
    ):
        _required_text(observation.get(field), f"{position}.{field}")

    if observation["scope"] != scope:
        raise ResidualNextCheckRoutingError(
            f"{position}.scope must match its scope result"
        )


def _validate_scope_result(scope_result: Any, index: int) -> None:
    position = f"residual.scope_results[{index}]"

    if not isinstance(scope_result, Mapping):
        raise ResidualNextCheckRoutingError(
            f"{position} must be a mapping"
        )

    scope = _required_text(scope_result.get("scope"), f"{position}.scope")
    _required_text(scope_result.get("status"), f"{position}.status")
    _required_text(scope_result.get("reason"), f"{position}.reason")
    _required_sequence(
        scope_result.get("statements"),
        f"{position}.statements",
    )

    observations = _required_sequence(
        scope_result.get("observations"),
        f"{position}.observations",
    )

    for observation_index, observation in enumerate(observations):
        _validate_observation(
            observation,
            scope=scope,
            position=f"{position}.observations[{observation_index}]",
        )


def _validate_residual(residual: Mapping[str, Any]) -> None:
    if residual.get("status") not in {
        "UNRESOLVED",
        "CONDITIONALLY_DIVERGENT",
    }:
        raise ResidualNextCheckRoutingError(
            "residual must have an unresolved convergence status"
        )

    _required_text(residual.get("reason"), "residual.reason")
    _required_sequence(residual.get("statements"), "residual.statements")

    scope_results = _required_sequence(
        residual.get("scope_results"),
        "residual.scope_results",
    )

    fact_id = residual.get("fact_id")
    finding_id = residual.get("finding_id")
    finding_ids = residual.get("finding_ids")

    has_fact_identity = (
        isinstance(fact_id, str)
        and bool(fact_id.strip())
        and not isinstance(finding_ids, (str, bytes))
        and isinstance(finding_ids, Sequence)
        and bool(finding_ids)
        and all(
            isinstance(item, str) and bool(item.strip())
            for item in finding_ids
        )
    )
    has_finding_identity = (
        isinstance(finding_id, str)
        and bool(finding_id.strip())
    )

    if not (has_fact_identity or has_finding_identity):
        raise ResidualNextCheckRoutingError(
            "unresolved residual must preserve fact or finding identity"
        )

    for index, scope_result in enumerate(scope_results):
        _validate_scope_result(scope_result, index)


def route_unresolved_residual(
    *,
    residual: Mapping[str, Any],
    resolution_conditions: Sequence[str],
) -> dict[str, Any]:
    """Route one unresolved residual without inventing a resolution condition."""

    if not isinstance(residual, Mapping):
        raise ResidualNextCheckRoutingError("residual must be a mapping")

    _validate_residual(residual)

    if isinstance(resolution_conditions, (str, bytes)) or not isinstance(
        resolution_conditions, Sequence
    ):
        raise ResidualNextCheckRoutingError(
            "resolution_conditions must be a sequence"
        )

    conditions: list[str] = []
    for index, condition in enumerate(resolution_conditions):
        conditions.append(
            _required_text(
                condition,
                f"resolution_conditions[{index}]",
            ).strip()
        )

    source_residual = deepcopy(dict(residual))

    candidate_checks = [
        {
            "condition": condition,
            "condition_index": index,
            "invented": False,
            "execution_authorized": False,
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
        }
        for index, condition in enumerate(conditions)
    ]

    payload = {
        "type": "residual_next_check_routing",
        "version": 1,
        "routing_status": (
            "DECLARED_CHECK_AVAILABLE"
            if candidate_checks
            else "RESOLUTION_CONDITION_REQUIRED"
        ),
        "source_residual": source_residual,
        "candidate_checks": candidate_checks,
        "conditions_invented": False,
        "truth_claimed": False,
        "accepted": False,
        "execution_authorized": False,
        "state_change_authorized": False,
        "write_authority": "NONE",
    }

    try:
        routing_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise ResidualNextCheckRoutingError(str(exc)) from exc

    return {**payload, "routing_id": routing_id}
