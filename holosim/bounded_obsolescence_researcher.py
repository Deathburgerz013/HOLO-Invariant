"""Read-only research into bounded substrate redundancy.

Findings concern supplied observations only. They do not establish global
obsolescence, dependency completeness, truth, or removal authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.compression_observer_coverage import (
    evaluate_compression_observer_coverage,
    verify_compression_observer_coverage_receipt,
)
from holosim.evidence_bound_reproduction import (
    validate_evidence_bound_reproduction,
)

TYPE = "bounded_obsolescence_research"
VERSION = 1


class BoundedObsolescenceResearchError(ValueError):
    """Invalid or unreplayable research evidence."""


def _checked_hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise BoundedObsolescenceResearchError(
            "evidence cannot be canonicalized"
        ) from exc


def _verified_coverage(receipt: dict[str, Any]) -> None:
    if type(receipt) is not dict:
        raise BoundedObsolescenceResearchError("invalid coverage receipt")

    try:
        result = verify_compression_observer_coverage_receipt(receipt)
        expected = evaluate_compression_observer_coverage(
            required_observations=receipt["required_observations"],
            declared_observers=receipt["declared_observers"],
            observer_identities=receipt["observer_identities"],
            requirement_basis_ref=receipt["requirement_basis_ref"],
        )
    except (KeyError, ValueError, TypeError, RecursionError) as exc:
        raise BoundedObsolescenceResearchError(
            "invalid coverage evidence"
        ) from exc

    if (
        result["valid"] is not True
        or set(receipt) != set(expected)
        or _checked_hash(receipt) != _checked_hash(expected)
    ):
        raise BoundedObsolescenceResearchError(
            "coverage receipt does not replay exactly"
        )


def build_bounded_obsolescence_research(
    *,
    reproduction_receipt: dict[str, Any],
    coverage_receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    """Classify observed redundancy without claiming global obsolescence."""

    try:
        if validate_evidence_bound_reproduction(reproduction_receipt) is not True:
            raise BoundedObsolescenceResearchError(
                "reproduction verification failed"
            )
    except (ValueError, TypeError, RecursionError) as exc:
        raise BoundedObsolescenceResearchError(
            "invalid reproduction evidence"
        ) from exc

    if coverage_receipt is not None:
        _verified_coverage(coverage_receipt)

    reproduction = reproduction_receipt["reproduction"]
    reproduced = reproduction["status"] == "REPRODUCED"
    removed = reproduction["removed_substrate_ids"]
    coverage_complete = (
        coverage_receipt is not None
        and coverage_receipt["coverage_complete"] is True
    )

    baseline_outcome_ids = {
        outcome["id"]
        for outcome in reproduction_receipt["inputs"]["baseline_outcomes"]
    }
    covered_observations = (
        set(coverage_receipt["covered_observations"])
        if coverage_receipt is not None else set()
    )
    coverage_matches_outcomes = baseline_outcome_ids <= covered_observations

    if not reproduced:
        status = "CONTRADICTED"
    elif removed and coverage_complete and coverage_matches_outcomes:
        status = "SUPPORTED"
    else:
        status = "UNAVAILABLE"

    limitations = [
        "OBSERVATION_TRUTH_UNVERIFIED",
        "REQUIREMENT_COMPLETENESS_UNVERIFIED",
        "DEPENDENCY_FRESHNESS_UNVERIFIED",
        "GLOBAL_OBSOLESCENCE_UNESTABLISHED",
    ]
    if coverage_receipt is None:
        limitations.append("OBSERVER_COVERAGE_UNAVAILABLE")
    elif not coverage_complete:
        limitations.append("OBSERVER_COVERAGE_INCOMPLETE")
    if coverage_receipt is not None and not coverage_matches_outcomes:
        limitations.append("COVERAGE_OUTCOME_MISMATCH")
    if not removed:
        limitations.append("NO_REMOVED_SUBSTRATE")
    if not reproduced:
        limitations.append("BASELINE_OUTCOMES_NOT_REPRODUCED")

    body = {
        "type": TYPE,
        "version": VERSION,
        "reproduction_receipt": deepcopy(reproduction_receipt),
        "coverage_receipt": deepcopy(coverage_receipt),
        "reproduction_evidence_hash": reproduction_receipt["verification_hash"],
        "coverage_evidence_hash": (
            coverage_receipt["receipt_id"]
            if coverage_receipt is not None else None
        ),
        "status": status,
        "observed_redundancy_candidates": (
            deepcopy(removed) if reproduced else []
        ),
        "dependency_freshness": "UNVERIFIED",
        "limitations": sorted(limitations),
        "accepted": False,
        "truth_claimed": False,
        "obsolete_claimed": False,
        "deletion_authorized": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "SUPPORTED means only that removed substrate items were not "
            "required for the supplied reproduced outcomes, with declared "
            "observer coverage. It does not establish global obsolescence, "
            "complete requirements, actual observer execution, or authority."
        ),
    }
    return {**body, "research_hash": _checked_hash(body)}


def validate_bounded_obsolescence_research(receipt: Any) -> bool:
    """Replay all embedded evidence and require exact receipt identity."""

    if type(receipt) is not dict:
        raise BoundedObsolescenceResearchError("invalid research receipt")

    if (
        receipt.get("type") != TYPE
        or type(receipt.get("version")) is not int
        or receipt["version"] != VERSION
    ):
        raise BoundedObsolescenceResearchError(
            "invalid research type or version"
        )

    try:
        expected = build_bounded_obsolescence_research(
            reproduction_receipt=receipt["reproduction_receipt"],
            coverage_receipt=receipt["coverage_receipt"],
        )
    except (KeyError, ValueError, TypeError, RecursionError) as exc:
        raise BoundedObsolescenceResearchError(
            "research evidence cannot be replayed"
        ) from exc

    if (
        set(receipt) != set(expected)
        or _checked_hash(receipt) != _checked_hash(expected)
    ):
        raise BoundedObsolescenceResearchError(
            "research receipt does not match replay"
        )

    return True
