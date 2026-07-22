"""Deterministic scoring for bounded reconstruction/recall experiments.

This module does not call a model and does not decide truth. It scores a supplied
reconstruction against an explicit reference fixture so baseline and grounded
conditions can be compared without changing the rubric between runs.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash

BENCHMARK_TYPE = "reconstruction_benchmark_result"
BENCHMARK_VERSION = 1


class ReconstructionBenchmarkError(ValueError):
    """Raised when a reconstruction benchmark input is invalid."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReconstructionBenchmarkError(f"{field} must be a non-empty string")
    return value


def _unique_texts(values: Sequence[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ReconstructionBenchmarkError(f"{field} must be a sequence of strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _required_text(value, field)
        if text in seen:
            raise ReconstructionBenchmarkError(f"{field} must not contain duplicates")
        seen.add(text)
        normalized.append(text)
    return tuple(normalized)


def _normalize_claim_sources(
    claim_sources: Mapping[str, Sequence[str]],
    *,
    allowed_claims: set[str],
) -> dict[str, tuple[str, ...]]:
    if not isinstance(claim_sources, Mapping):
        raise ReconstructionBenchmarkError("claim_sources must be a mapping")
    normalized: dict[str, tuple[str, ...]] = {}
    for claim, sources in claim_sources.items():
        claim_id = _required_text(claim, "claim_sources key")
        if claim_id not in allowed_claims:
            raise ReconstructionBenchmarkError(
                f"claim_sources contains unknown reconstructed claim: {claim_id}"
            )
        normalized[claim_id] = _unique_texts(sources, f"claim_sources[{claim_id}]")
    return normalized


def score_reconstruction(
    *,
    benchmark_id: str,
    condition_id: str,
    reference_claims: Sequence[str],
    reconstructed_claims: Sequence[str],
    required_order: Sequence[str] = (),
    reconstructed_order: Sequence[str] = (),
    claim_sources: Mapping[str, Sequence[str]] | None = None,
    context_units: int = 0,
) -> dict[str, Any]:
    """Score one bounded reconstruction against an explicit reference fixture.

    Metrics are intentionally mechanical:
    - recovered reference claims
    - missed reference claims
    - unsupported claims not present in the reference fixture
    - exact relative order for the required ordered subsequence
    - recovered claims carrying at least one source reference
    - reference claims recovered per supplied context unit

    The reference fixture is an input, not a truth authority. The result therefore
    records no acceptance or write authority.
    """
    bench = _required_text(benchmark_id, "benchmark_id")
    condition = _required_text(condition_id, "condition_id")
    if not isinstance(context_units, int) or isinstance(context_units, bool) or context_units < 0:
        raise ReconstructionBenchmarkError("context_units must be a non-negative integer")

    reference = _unique_texts(reference_claims, "reference_claims")
    reconstructed = _unique_texts(reconstructed_claims, "reconstructed_claims")
    required = _unique_texts(required_order, "required_order")
    observed_order = _unique_texts(reconstructed_order, "reconstructed_order")

    reference_set = set(reference)
    reconstructed_set = set(reconstructed)
    if not set(required).issubset(reference_set):
        raise ReconstructionBenchmarkError("required_order must contain only reference claims")
    if not set(observed_order).issubset(reconstructed_set):
        raise ReconstructionBenchmarkError(
            "reconstructed_order must contain only reconstructed claims"
        )

    sources = _normalize_claim_sources(
        claim_sources or {},
        allowed_claims=reconstructed_set,
    )

    recovered = tuple(claim for claim in reference if claim in reconstructed_set)
    missed = tuple(claim for claim in reference if claim not in reconstructed_set)
    unsupported = tuple(claim for claim in reconstructed if claim not in reference_set)

    required_recovered = tuple(claim for claim in required if claim in reconstructed_set)
    observed_required = tuple(claim for claim in observed_order if claim in set(required_recovered))
    order_correct = observed_required == required_recovered

    sourced_recovered = tuple(
        claim for claim in recovered if sources.get(claim)
    )

    reference_count = len(reference)
    recovered_count = len(recovered)
    unsupported_count = len(unsupported)
    recall = recovered_count / reference_count if reference_count else 1.0
    precision_denominator = recovered_count + unsupported_count
    precision = recovered_count / precision_denominator if precision_denominator else 1.0
    sourced_recall = (
        len(sourced_recovered) / recovered_count if recovered_count else 1.0
    )
    recovery_per_context_unit = (
        recovered_count / context_units if context_units else None
    )

    payload = {
        "type": BENCHMARK_TYPE,
        "version": BENCHMARK_VERSION,
        "benchmark_id": bench,
        "condition_id": condition,
        "reference_claims": list(reference),
        "reconstructed_claims": list(reconstructed),
        "required_order": list(required),
        "reconstructed_order": list(observed_order),
        "recovered_claims": list(recovered),
        "missed_claims": list(missed),
        "unsupported_claims": list(unsupported),
        "sourced_recovered_claims": list(sourced_recovered),
        "metrics": {
            "reference_count": reference_count,
            "recovered_count": recovered_count,
            "unsupported_count": unsupported_count,
            "recall": recall,
            "precision": precision,
            "sourced_recall": sourced_recall,
            "order_correct": order_correct,
            "context_units": context_units,
            "recovery_per_context_unit": recovery_per_context_unit,
        },
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        result_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise ReconstructionBenchmarkError(str(exc)) from exc
    return {**payload, "result_id": result_id}


def compare_reconstruction_conditions(
    *,
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two results produced against the same explicit benchmark fixture."""
    if baseline.get("type") != BENCHMARK_TYPE or candidate.get("type") != BENCHMARK_TYPE:
        raise ReconstructionBenchmarkError("both inputs must be reconstruction benchmark results")
    if baseline.get("benchmark_id") != candidate.get("benchmark_id"):
        raise ReconstructionBenchmarkError("benchmark_id must match across conditions")
    if baseline.get("reference_claims") != candidate.get("reference_claims"):
        raise ReconstructionBenchmarkError("reference_claims must match across conditions")
    if baseline.get("required_order") != candidate.get("required_order"):
        raise ReconstructionBenchmarkError("required_order must match across conditions")

    base_metrics = baseline.get("metrics", {})
    candidate_metrics = candidate.get("metrics", {})
    payload = {
        "type": "reconstruction_benchmark_comparison",
        "version": BENCHMARK_VERSION,
        "benchmark_id": baseline["benchmark_id"],
        "baseline_condition_id": baseline["condition_id"],
        "candidate_condition_id": candidate["condition_id"],
        "delta": {
            "recovered_count": candidate_metrics.get("recovered_count", 0)
            - base_metrics.get("recovered_count", 0),
            "unsupported_count": candidate_metrics.get("unsupported_count", 0)
            - base_metrics.get("unsupported_count", 0),
            "recall": candidate_metrics.get("recall", 0.0)
            - base_metrics.get("recall", 0.0),
            "precision": candidate_metrics.get("precision", 0.0)
            - base_metrics.get("precision", 0.0),
            "sourced_recall": candidate_metrics.get("sourced_recall", 0.0)
            - base_metrics.get("sourced_recall", 0.0),
        },
        "candidate_improves_reconstruction": (
            candidate_metrics.get("recovered_count", 0)
            > base_metrics.get("recovered_count", 0)
            and candidate_metrics.get("unsupported_count", 0)
            <= base_metrics.get("unsupported_count", 0)
        ),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        comparison_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise ReconstructionBenchmarkError(str(exc)) from exc
    return {**payload, "comparison_id": comparison_id}
