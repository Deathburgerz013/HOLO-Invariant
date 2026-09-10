"""Bounded proposals for missing uncertainty resolution conditions.

This module does not decide truth, resolve uncertainty, execute checks, select
a verifier, mutate source records, or grant authority.

It only binds externally supplied candidate resolution conditions to uncertainty
that is explicitly present in the supplied source record.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash


PROPOSAL_TYPE = "holo_resolution_condition_proposal"
PROPOSAL_VERSION = 1

_ACTIVE_STATUSES = frozenset(
    {
        "open",
        "bounded",
        "reduced",
        "contradicted",
    }
)


class ResolutionConditionProposalError(ValueError):
    """Raised when a resolution-condition proposal violates its boundary."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResolutionConditionProposalError(
            f"{field} must be a non-empty string"
        )
    return value.strip()


def _text_list(value: Any, field: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ResolutionConditionProposalError(
            f"{field} must be a sequence of strings"
        )

    result: list[str] = []

    for item in value:
        text = _required_text(item, field)

        if text not in result:
            result.append(text)

    return result


def _normalize_source(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ResolutionConditionProposalError(
            "source record must be a mapping"
        )

    status = _required_text(
        record.get("status"),
        "source.status",
    ).lower()

    if status not in _ACTIVE_STATUSES:
        raise ResolutionConditionProposalError(
            "source status must represent unresolved active uncertainty"
        )

    residual_uncertainty = _text_list(
        record.get("residual_uncertainty", []),
        "source.residual_uncertainty",
    )

    if not residual_uncertainty:
        raise ResolutionConditionProposalError(
            "source must declare residual uncertainty"
        )

    declared_conditions = _text_list(
        record.get("resolution_conditions", []),
        "source.resolution_conditions",
    )

    if declared_conditions:
        raise ResolutionConditionProposalError(
            "source already has declared resolution conditions"
        )

    return {
        "idx": record.get("idx"),
        "entry_hash": _required_text(
            record.get("entry_hash"),
            "source.entry_hash",
        ),
        "claim": _required_text(
            record.get("claim"),
            "source.claim",
        ),
        "status": status,
        "resolution_conditions": [],
        "residual_uncertainty": residual_uncertainty,
        "source_refs": _text_list(
            record.get("source_refs", []),
            "source.source_refs",
        ),
    }


def _normalize_candidate(
    candidate: Mapping[str, Any],
    *,
    residual_uncertainty: Sequence[str],
    position: int,
) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        raise ResolutionConditionProposalError(
            f"candidate_conditions[{position}] must be a mapping"
        )

    required_fields = {
        "condition",
        "targets_uncertainty",
        "rationale",
    }

    if set(candidate) != required_fields:
        raise ResolutionConditionProposalError(
            f"candidate_conditions[{position}] fields mismatch"
        )

    condition = _required_text(
        candidate["condition"],
        f"candidate_conditions[{position}].condition",
    )
    target = _required_text(
        candidate["targets_uncertainty"],
        f"candidate_conditions[{position}].targets_uncertainty",
    )
    rationale = _required_text(
        candidate["rationale"],
        f"candidate_conditions[{position}].rationale",
    )

    if target not in residual_uncertainty:
        raise ResolutionConditionProposalError(
            "candidate targets uncertainty not present in source"
        )

    payload = {
        "condition": condition,
        "targets_uncertainty": target,
        "rationale": rationale,
        "truth_claimed": False,
        "accepted": False,
        "execution_authorized": False,
        "write_authority": "NONE",
    }

    try:
        candidate_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise ResolutionConditionProposalError(str(exc)) from exc

    return {
        **payload,
        "candidate_id": candidate_id,
    }


def propose_resolution_conditions(
    record: Mapping[str, Any],
    *,
    candidate_source: Callable[
        [Mapping[str, Any]],
        Mapping[str, Any],
    ],
) -> dict[str, Any]:
    """Bind externally supplied discriminator proposals to declared uncertainty.

    The candidate source may propose conditions, but this contract does not
    establish that those conditions are correct, useful, executable, sufficient,
    or authorized.

    An empty proposal means only that this candidate source supplied no
    candidate. It does not establish that no discriminator exists.
    """

    if not callable(candidate_source):
        raise ResolutionConditionProposalError(
            "candidate_source must be callable"
        )

    source = _normalize_source(record)

    source_for_candidate = deepcopy(source)
    proposal = candidate_source(source_for_candidate)

    if not isinstance(proposal, Mapping):
        raise ResolutionConditionProposalError(
            "candidate_source must return a mapping"
        )

    if set(proposal) != {"candidate_conditions"}:
        raise ResolutionConditionProposalError(
            "candidate_source output fields mismatch"
        )

    raw_candidates = proposal["candidate_conditions"]

    if (
        isinstance(raw_candidates, (str, bytes))
        or not isinstance(raw_candidates, Sequence)
    ):
        raise ResolutionConditionProposalError(
            "candidate_conditions must be a sequence"
        )

    candidates = [
        _normalize_candidate(
            candidate,
            residual_uncertainty=source["residual_uncertainty"],
            position=position,
        )
        for position, candidate in enumerate(raw_candidates)
    ]

    body = {
        "type": PROPOSAL_TYPE,
        "version": PROPOSAL_VERSION,
        "source": source,
        "proposal_status": (
            "CANDIDATES_PROPOSED"
            if candidates
            else "NO_CANDIDATE_PROPOSED"
        ),
        "candidate_conditions": candidates,
        "truth_claimed": False,
        "accepted": False,
        "execution_authorized": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Candidate conditions are externally supplied proposals bound "
            "only to declared residual uncertainty. Their presence does not "
            "establish truth, resolution, sufficiency, execution permission, "
            "acceptance, or write authority. An empty proposal does not prove "
            "that no discriminator exists."
        ),
    }

    try:
        proposal_id = stable_hash(body)
    except CanonicalValueError as exc:
        raise ResolutionConditionProposalError(str(exc)) from exc

    return {
        **body,
        "proposal_id": proposal_id,
    }