"""Bounded comparison harness for continuity reconstruction conditions.

This module does not claim that one architecture universally outperforms another.
It scores supplied condition outputs against one explicit continuity fixture so plain
logs, retrieval systems, HOLO, or other approaches can be compared under the same
rubric without changing the target after seeing the result.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash

BENCHMARK_TYPE = "continuity_baseline_benchmark"
BENCHMARK_VERSION = 1
RESULT_TYPE = "continuity_baseline_result"
COMPARISON_TYPE = "continuity_baseline_comparison"


class ContinuityBaselineBenchmarkError(ValueError):
    """Raised when a benchmark fixture or condition result is malformed."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContinuityBaselineBenchmarkError(f"{field} must be a non-empty string")
    return value


def _unique_texts(values: Sequence[str], field: str) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ContinuityBaselineBenchmarkError(f"{field} must be a sequence of strings")
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _required_text(value, field)
        if text in seen:
            raise ContinuityBaselineBenchmarkError(f"{field} must not contain duplicates")
        seen.add(text)
        out.append(text)
    return out


def _lineage_edges(values: Sequence[Sequence[str]], field: str) -> list[list[str]]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ContinuityBaselineBenchmarkError(f"{field} must be a sequence")
    out: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
            raise ContinuityBaselineBenchmarkError(f"{field} entries must be [from, to]")
        edge = (_required_text(value[0], field), _required_text(value[1], field))
        if edge in seen:
            raise ContinuityBaselineBenchmarkError(f"{field} must not contain duplicates")
        seen.add(edge)
        out.append([edge[0], edge[1]])
    return out


def build_continuity_benchmark(
    *,
    benchmark_id: str,
    latest_justified_claim_ids: Sequence[str],
    superseded_claim_ids: Sequence[str],
    uncertainty_claim_ids: Sequence[str],
    required_lineage_edges: Sequence[Sequence[str]],
    stale_continuation_must_block: bool = True,
) -> dict[str, Any]:
    """Build one explicit, deterministic continuity benchmark fixture."""
    benchmark = _required_text(benchmark_id, "benchmark_id")
    latest = _unique_texts(latest_justified_claim_ids, "latest_justified_claim_ids")
    superseded = _unique_texts(superseded_claim_ids, "superseded_claim_ids")
    uncertain = _unique_texts(uncertainty_claim_ids, "uncertainty_claim_ids")
    lineage = _lineage_edges(required_lineage_edges, "required_lineage_edges")

    overlap = set(latest) & set(superseded)
    if overlap:
        raise ContinuityBaselineBenchmarkError(
            "latest_justified_claim_ids and superseded_claim_ids must be disjoint"
        )

    body = {
        "type": BENCHMARK_TYPE,
        "version": BENCHMARK_VERSION,
        "benchmark_id": benchmark,
        "latest_justified_claim_ids": latest,
        "superseded_claim_ids": superseded,
        "uncertainty_claim_ids": uncertain,
        "required_lineage_edges": lineage,
        "stale_continuation_must_block": bool(stale_continuation_must_block),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        fixture_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise ContinuityBaselineBenchmarkError(str(exc)) from exc
    return {**body, "fixture_hash": fixture_hash}


def _validate_fixture(fixture: Mapping[str, Any]) -> None:
    if not isinstance(fixture, Mapping) or fixture.get("type") != BENCHMARK_TYPE:
        raise ContinuityBaselineBenchmarkError("fixture must be a continuity baseline benchmark")
    stored = fixture.get("fixture_hash")
    if not isinstance(stored, str) or not stored:
        raise ContinuityBaselineBenchmarkError("fixture requires fixture_hash")
    body = {key: deepcopy(value) for key, value in fixture.items() if key != "fixture_hash"}
    try:
        if stable_hash(body) != stored:
            raise ContinuityBaselineBenchmarkError("fixture hash does not match content")
    except CanonicalValueError as exc:
        raise ContinuityBaselineBenchmarkError(str(exc)) from exc


def score_continuity_condition(
    *,
    fixture: Mapping[str, Any],
    condition_id: str,
    recovered_claim_ids: Sequence[str],
    claimed_current_claim_ids: Sequence[str],
    preserved_uncertainty_claim_ids: Sequence[str],
    reconstructed_lineage_edges: Sequence[Sequence[str]],
    stale_continuation_decision: str,
) -> dict[str, Any]:
    """Score one supplied condition output without inferring missing behavior."""
    _validate_fixture(fixture)
    condition = _required_text(condition_id, "condition_id")
    recovered = _unique_texts(recovered_claim_ids, "recovered_claim_ids")
    claimed_current = _unique_texts(claimed_current_claim_ids, "claimed_current_claim_ids")
    preserved_uncertainty = _unique_texts(
        preserved_uncertainty_claim_ids, "preserved_uncertainty_claim_ids"
    )
    lineage = _lineage_edges(reconstructed_lineage_edges, "reconstructed_lineage_edges")
    stale_decision = _required_text(stale_continuation_decision, "stale_continuation_decision")
    if stale_decision not in {"ALLOW", "BLOCK", "UNKNOWN"}:
        raise ContinuityBaselineBenchmarkError(
            "stale_continuation_decision must be ALLOW, BLOCK, or UNKNOWN"
        )

    latest = list(fixture["latest_justified_claim_ids"])
    superseded = list(fixture["superseded_claim_ids"])
    uncertain = list(fixture["uncertainty_claim_ids"])
    required_lineage = [list(edge) for edge in fixture["required_lineage_edges"]]

    latest_recovered = [claim for claim in latest if claim in set(recovered)]
    resurrected = [claim for claim in superseded if claim in set(claimed_current)]
    uncertainty_preserved = [claim for claim in uncertain if claim in set(preserved_uncertainty)]
    lineage_recovered = [edge for edge in required_lineage if edge in lineage]

    latest_recall = len(latest_recovered) / len(latest) if latest else 1.0
    uncertainty_recall = len(uncertainty_preserved) / len(uncertain) if uncertain else 1.0
    lineage_recall = len(lineage_recovered) / len(required_lineage) if required_lineage else 1.0
    stale_blocked = (
        stale_decision == "BLOCK"
        if fixture["stale_continuation_must_block"]
        else stale_decision != "BLOCK"
    )

    passes = (
        latest_recall == 1.0
        and not resurrected
        and uncertainty_recall == 1.0
        and lineage_recall == 1.0
        and stale_blocked
    )

    payload = {
        "type": RESULT_TYPE,
        "version": BENCHMARK_VERSION,
        "benchmark_id": fixture["benchmark_id"],
        "fixture_hash": fixture["fixture_hash"],
        "condition_id": condition,
        "latest_justified_recovered": latest_recovered,
        "superseded_resurrected_as_current": resurrected,
        "uncertainty_preserved": uncertainty_preserved,
        "lineage_edges_recovered": lineage_recovered,
        "stale_continuation_decision": stale_decision,
        "metrics": {
            "latest_justified_recall": latest_recall,
            "superseded_resurrection_count": len(resurrected),
            "uncertainty_recall": uncertainty_recall,
            "lineage_recall": lineage_recall,
            "stale_continuation_blocked": stale_blocked,
            "passes_bounded_continuity_fixture": passes,
        },
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        result_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise ContinuityBaselineBenchmarkError(str(exc)) from exc
    return {**payload, "result_hash": result_hash}


def compare_continuity_conditions(
    *,
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two scored conditions from the exact same benchmark fixture."""
    for name, result in (("baseline", baseline), ("candidate", candidate)):
        if not isinstance(result, Mapping) or result.get("type") != RESULT_TYPE:
            raise ContinuityBaselineBenchmarkError(f"{name} must be a continuity baseline result")
    if baseline.get("benchmark_id") != candidate.get("benchmark_id"):
        raise ContinuityBaselineBenchmarkError("benchmark_id must match across conditions")
    if baseline.get("fixture_hash") != candidate.get("fixture_hash"):
        raise ContinuityBaselineBenchmarkError("fixture_hash must match across conditions")

    base = baseline["metrics"]
    cand = candidate["metrics"]
    payload = {
        "type": COMPARISON_TYPE,
        "version": BENCHMARK_VERSION,
        "benchmark_id": baseline["benchmark_id"],
        "fixture_hash": baseline["fixture_hash"],
        "baseline_condition_id": baseline["condition_id"],
        "candidate_condition_id": candidate["condition_id"],
        "delta": {
            "latest_justified_recall": cand["latest_justified_recall"]
            - base["latest_justified_recall"],
            "superseded_resurrection_count": cand["superseded_resurrection_count"]
            - base["superseded_resurrection_count"],
            "uncertainty_recall": cand["uncertainty_recall"] - base["uncertainty_recall"],
            "lineage_recall": cand["lineage_recall"] - base["lineage_recall"],
        },
        "candidate_passes_where_baseline_does_not": (
            cand["passes_bounded_continuity_fixture"]
            and not base["passes_bounded_continuity_fixture"]
        ),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        comparison_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise ContinuityBaselineBenchmarkError(str(exc)) from exc
    return {**payload, "comparison_hash": comparison_hash}
