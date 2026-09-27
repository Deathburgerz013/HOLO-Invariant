"""Behavioral necessity experiment for HOLO-Invariant architectural boundaries.

This research module compares architectures by observable behavior only.
It does not infer necessity from module names, documentation, implementation
size, receipt count, or architectural intent.

Experimental classifications are evidence only and grant no operational
authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from holosim.canonical import stable_hash
from holosim.experimental_distinguishability import derive_distinguishability


CLASSIFICATION_NECESSARY = "NECESSARY"
CLASSIFICATION_REDUNDANT = "REDUNDANT"
CLASSIFICATION_UNRESOLVED = "UNRESOLVED"

WRITE_AUTHORITY = "NONE"
EXECUTION_AUTHORITY = "NONE"


class ArchitecturalBoundaryExperimentError(ValueError):
    """Raised when a boundary experiment violates its declared contract."""


def classify_boundary_comparison(
    *,
    boundary_id: str,
    candidate_with_boundary: Any,
    candidate_without_boundary: Any,
    checks: Mapping[str, Callable[[Any], Any]],
    declared_failure: Callable[[Mapping[str, Any]], bool],
    equivalent_rejection_proven: bool | None,
) -> dict[str, Any]:
    """Classify one boundary from observed behavioral separation.

    The declared failure predicate is evaluated against the observed check
    outcomes for each candidate. The experiment derives whether removal
    permits the declared failure; callers do not supply that conclusion.

    NECESSARY requires behavioral distinguishability plus an observed transition
    from failure absent with the boundary to failure present without it.

    REDUNDANT requires behavioral indistinguishability plus affirmative evidence
    that another boundary rejects the same declared failures.

    Everything else remains UNRESOLVED.
    """

    if type(boundary_id) is not str or not boundary_id.strip():
        raise ArchitecturalBoundaryExperimentError(
            "boundary_id must be a non-empty string"
        )
    if not isinstance(checks, Mapping):
        raise ArchitecturalBoundaryExperimentError("checks must be a mapping")
    if not callable(declared_failure):
        raise ArchitecturalBoundaryExperimentError(
            "declared_failure must be callable"
        )
    if equivalent_rejection_proven not in {True, False, None}:
        raise ArchitecturalBoundaryExperimentError(
            "equivalent_rejection_proven must be boolean or None"
        )

    distinguishability = derive_distinguishability(
        candidates={
            "WITH_BOUNDARY": deepcopy(candidate_with_boundary),
            "WITHOUT_BOUNDARY": deepcopy(candidate_without_boundary),
        },
        checks=dict(checks),
    )

    pair = {"WITH_BOUNDARY", "WITHOUT_BOUNDARY"}
    distinguished = any(
        set(item) == pair
        for item in distinguishability["distinguished_pairs"]
    )
    indistinguishable = any(
        set(item) == pair
        for item in distinguishability["indistinguishable_pairs"]
    )
    unresolved = any(
        set(item) == pair
        for item in distinguishability["unresolved_pairs"]
    )

    outcome_matrix = distinguishability["outcome_matrix"]
    with_observations = deepcopy(outcome_matrix["WITH_BOUNDARY"])
    without_observations = deepcopy(outcome_matrix["WITHOUT_BOUNDARY"])

    failure_with_boundary = declared_failure(with_observations)
    failure_without_boundary = declared_failure(without_observations)

    if type(failure_with_boundary) is not bool:
        raise ArchitecturalBoundaryExperimentError(
            "declared_failure must return bool for WITH_BOUNDARY observations"
        )
    if type(failure_without_boundary) is not bool:
        raise ArchitecturalBoundaryExperimentError(
            "declared_failure must return bool for WITHOUT_BOUNDARY observations"
        )

    removal_permits_declared_failure = (
        failure_with_boundary is False
        and failure_without_boundary is True
    )

    if distinguished and removal_permits_declared_failure:
        classification = CLASSIFICATION_NECESSARY
    elif (
        indistinguishable
        and equivalent_rejection_proven is True
        and failure_with_boundary is False
        and failure_without_boundary is False
    ):
        classification = CLASSIFICATION_REDUNDANT
    else:
        classification = CLASSIFICATION_UNRESOLVED

    body = {
        "type": "architectural_boundary_comparison_receipt",
        "version": 1,
        "boundary_id": boundary_id,
        "candidate_with_boundary": deepcopy(candidate_with_boundary),
        "candidate_without_boundary": deepcopy(candidate_without_boundary),
        "checks_executed": sorted(checks),
        "observations_with_boundary": with_observations,
        "observations_without_boundary": without_observations,
        "distinguished": distinguished,
        "indistinguishable": indistinguishable,
        "unresolved": unresolved,
        "distinguishing_checks": deepcopy(
            distinguishability.get("check_separation", {})
        ),
        "failure_with_boundary": failure_with_boundary,
        "failure_without_boundary": failure_without_boundary,
        "removal_permits_declared_failure": removal_permits_declared_failure,
        "equivalent_rejection_proven": equivalent_rejection_proven,
        "classification": classification,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": WRITE_AUTHORITY,
        "execution_authority": EXECUTION_AUTHORITY,
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }
