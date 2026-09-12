from __future__ import annotations

import hashlib
import json
from typing import Any, Callable


UNAVAILABLE = "UNAVAILABLE"
_UNAVAILABLE_SENTINEL = object()


class ObservationUnavailable(Exception):
    """A check explicitly could not observe this candidate."""


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _pair_separation_score(groups: list[list[str]]) -> int:
    observed_count = sum(len(group) for group in groups)

    total_pairs = observed_count * (observed_count - 1) // 2
    unresolved_pairs = sum(
        len(group) * (len(group) - 1) // 2
        for group in groups
    )

    return total_pairs - unresolved_pairs


def derive_distinguishability(
    *,
    candidates: dict[str, Any],
    checks: dict[str, Callable[[Any], Any]],
) -> dict[str, Any]:
    candidate_ids = sorted(candidates)
    check_ids = sorted(checks)

    internal_outcomes: dict[str, dict[str, Any]] = {}
    outcome_matrix: dict[str, dict[str, Any]] = {}

    for candidate_id in candidate_ids:
        candidate = candidates[candidate_id]
        internal_outcomes[candidate_id] = {}
        outcome_matrix[candidate_id] = {}

        for check_id in check_ids:
            try:
                outcome = checks[check_id](candidate)
                internal_outcomes[candidate_id][check_id] = outcome
                outcome_matrix[candidate_id][check_id] = outcome
            except ObservationUnavailable:
                internal_outcomes[candidate_id][check_id] = _UNAVAILABLE_SENTINEL
                outcome_matrix[candidate_id][check_id] = UNAVAILABLE

    partitions: dict[str, list[list[str]]] = {}
    discrimination_scores: dict[str, int] = {}

    for check_id in check_ids:
        groups: dict[tuple[str, str], list[str]] = {}

        for candidate_id in candidate_ids:
            outcome = internal_outcomes[candidate_id][check_id]

            if outcome is _UNAVAILABLE_SENTINEL:
                continue

            key = (type(outcome).__name__, repr(outcome))
            groups.setdefault(key, []).append(candidate_id)

        partition = sorted(
            (sorted(group) for group in groups.values()),
            key=lambda group: tuple(group),
        )

        partitions[check_id] = partition
        discrimination_scores[check_id] = _pair_separation_score(partition)

    ranking = sorted(
        check_ids,
        key=lambda check_id: (
            -discrimination_scores[check_id],
            check_id,
        ),
    )

    receipt = {
        "outcome_matrix": outcome_matrix,
        "partitions": partitions,
        "discrimination_scores": discrimination_scores,
        "ranking": ranking,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    receipt["receipt_hash"] = _canonical_hash(receipt)

    return receipt
