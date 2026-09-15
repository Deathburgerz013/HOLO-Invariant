from __future__ import annotations

import hashlib
import json
from itertools import combinations
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


def _outcome_key(outcome: Any) -> tuple[str, str]:
    return type(outcome).__name__, repr(outcome)


def _pair_separation_score(groups: list[list[str]]) -> int:
    observed_count = sum(len(group) for group in groups)

    total_pairs = observed_count * (observed_count - 1) // 2
    unresolved_pairs = sum(
        len(group) * (len(group) - 1) // 2
        for group in groups
    )

    return total_pairs - unresolved_pairs


def _classify_candidate_pairs(
    *,
    candidate_ids: list[str],
    check_ids: list[str],
    internal_outcomes: dict[str, dict[str, Any]],
) -> tuple[list[list[str]], list[list[str]], list[list[str]]]:
    distinguished_pairs: list[list[str]] = []
    indistinguishable_pairs: list[list[str]] = []
    unresolved_pairs: list[list[str]] = []

    for left_id, right_id in combinations(candidate_ids, 2):
        separated = False
        observation_unavailable = False

        for check_id in check_ids:
            left_outcome = internal_outcomes[left_id][check_id]
            right_outcome = internal_outcomes[right_id][check_id]

            if (
                left_outcome is _UNAVAILABLE_SENTINEL
                or right_outcome is _UNAVAILABLE_SENTINEL
            ):
                observation_unavailable = True
                continue

            if _outcome_key(left_outcome) != _outcome_key(right_outcome):
                separated = True
                break

        pair = [left_id, right_id]

        if separated:
            distinguished_pairs.append(pair)
        elif observation_unavailable or not check_ids:
            unresolved_pairs.append(pair)
        else:
            indistinguishable_pairs.append(pair)

    return distinguished_pairs, indistinguishable_pairs, unresolved_pairs


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
                internal_outcomes[candidate_id][
                    check_id
                ] = _UNAVAILABLE_SENTINEL
                outcome_matrix[candidate_id][check_id] = UNAVAILABLE

    partitions: dict[str, list[list[str]]] = {}
    discrimination_scores: dict[str, int] = {}

    for check_id in check_ids:
        groups: dict[tuple[str, str], list[str]] = {}

        for candidate_id in candidate_ids:
            outcome = internal_outcomes[candidate_id][check_id]

            if outcome is _UNAVAILABLE_SENTINEL:
                continue

            groups.setdefault(
                _outcome_key(outcome),
                [],
            ).append(candidate_id)

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

    (
        distinguished_pairs,
        indistinguishable_pairs,
        unresolved_pairs,
    ) = _classify_candidate_pairs(
        candidate_ids=candidate_ids,
        check_ids=check_ids,
        internal_outcomes=internal_outcomes,
    )

    declared_pair_count = len(candidate_ids) * (len(candidate_ids) - 1) // 2
    distinguishability_complete = (
        declared_pair_count > 0
        and len(distinguished_pairs) == declared_pair_count
    )

    receipt = {
        "outcome_matrix": outcome_matrix,
        "partitions": partitions,
        "discrimination_scores": discrimination_scores,
        "ranking": ranking,
        "distinguished_pairs": distinguished_pairs,
        "indistinguishable_pairs": indistinguishable_pairs,
        "unresolved_pairs": unresolved_pairs,
        "distinguishability_complete": distinguishability_complete,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    receipt["receipt_hash"] = _canonical_hash(receipt)

    return receipt
