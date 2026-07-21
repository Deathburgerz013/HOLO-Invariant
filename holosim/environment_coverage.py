from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence


class EnvironmentCoverageError(ValueError):
    """Raised when an environment-coverage record is invalid."""


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise EnvironmentCoverageError(
            "coverage values must be finite, acyclic, JSON-compatible data"
        ) from exc


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_ids(values: Sequence[str], *, label: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise EnvironmentCoverageError(
                f"{label} must contain non-empty strings"
            )
        if value in seen:
            raise EnvironmentCoverageError(
                f"duplicate {label[:-1] if label.endswith('s') else label}: {value}"
            )
        seen.add(value)
        normalized.append(value)

    return normalized


def evaluate_environment_coverage(
    *,
    environment_id: str,
    environment_reference: str,
    required_function_ids: Sequence[str],
    observed_function_ids: Sequence[str],
    reproduced_function_ids: Sequence[str],
    unchecked_boundaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """
    Evaluate bounded functional coverage for one explicit environment.

    This evaluator does not discover requirements, prove truth, grant
    acceptance, mutate state, or claim global completeness. It only compares
    supplied function identities and explicit unchecked boundaries.
    """
    if not isinstance(environment_id, str) or not environment_id.strip():
        raise EnvironmentCoverageError(
            "environment_id must be a non-empty string"
        )
    if not isinstance(environment_reference, str) or not environment_reference.strip():
        raise EnvironmentCoverageError(
            "environment_reference must be a non-empty string"
        )

    required = _normalize_ids(required_function_ids, label="required_function_ids")
    observed = _normalize_ids(observed_function_ids, label="observed_function_ids")
    reproduced = _normalize_ids(
        reproduced_function_ids,
        label="reproduced_function_ids",
    )

    required_set = set(required)
    observed_set = set(observed)
    reproduced_set = set(reproduced)

    unknown_observed = sorted(observed_set - required_set)
    unknown_reproduced = sorted(reproduced_set - observed_set)
    if unknown_reproduced:
        raise EnvironmentCoverageError(
            "reproduced functions must also be present in observed_function_ids"
        )

    normalized_boundaries: list[dict[str, Any]] = []
    seen_boundary_ids: set[str] = set()

    for boundary in unchecked_boundaries:
        if not isinstance(boundary, Mapping):
            raise EnvironmentCoverageError(
                "unchecked_boundaries must contain objects"
            )

        boundary_id = boundary.get("id")
        if not isinstance(boundary_id, str) or not boundary_id.strip():
            raise EnvironmentCoverageError(
                "unchecked boundary requires a non-empty string id"
            )
        if boundary_id in seen_boundary_ids:
            raise EnvironmentCoverageError(
                f"duplicate unchecked boundary id: {boundary_id}"
            )

        seen_boundary_ids.add(boundary_id)
        normalized_boundaries.append(deepcopy(dict(boundary)))

    unresolved_required = [
        function_id
        for function_id in required
        if function_id not in reproduced_set
    ]

    observed_not_reproduced = [
        function_id
        for function_id in observed
        if function_id in required_set and function_id not in reproduced_set
    ]

    if unresolved_required:
        status = "INCOMPLETE"
    elif normalized_boundaries:
        status = "BLOCKED"
    else:
        status = "COMPLETE_AT_BOUNDARY"

    result = {
        "type": "environment_function_coverage",
        "environment_id": environment_id,
        "environment_reference": environment_reference,
        "required_function_ids": required,
        "observed_function_ids": observed,
        "reproduced_function_ids": reproduced,
        "unresolved_required_function_ids": unresolved_required,
        "observed_not_reproduced_function_ids": observed_not_reproduced,
        "observed_outside_required_scope": unknown_observed,
        "unchecked_boundaries": normalized_boundaries,
        "status": status,
        "global_completeness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    result["coverage_hash"] = _stable_hash(result)
    return result
