"""Evaluate supplied recall-kernel ablation results without claiming universal necessity.

The evaluator consumes reconstruction benchmark results produced against one fixed
reference fixture. It identifies which omitted kernel fields caused an observed
material degradation relative to the full-kernel condition.

It does not call a model, decide truth, or prove that a field is universally
required. It records only what the supplied bounded experiment demonstrates.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.reconstruction_benchmark import BENCHMARK_TYPE

EVALUATION_TYPE = "recall_kernel_falsification"
EVALUATION_VERSION = 1


class RecallKernelFalsificationError(ValueError):
    """Raised when a recall-kernel falsification input is invalid."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecallKernelFalsificationError(f"{field} must be a non-empty string")
    return value


def _unique_texts(values: Sequence[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise RecallKernelFalsificationError(f"{field} must be a sequence of strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _required_text(value, field)
        if text in seen:
            raise RecallKernelFalsificationError(f"{field} must not contain duplicates")
        seen.add(text)
        normalized.append(text)
    if not normalized:
        raise RecallKernelFalsificationError(f"{field} must not be empty")
    return tuple(normalized)


def _validate_result(result: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    if not isinstance(result, Mapping):
        raise RecallKernelFalsificationError(f"{field} must be a mapping")
    if result.get("type") != BENCHMARK_TYPE:
        raise RecallKernelFalsificationError(
            f"{field} must be a reconstruction benchmark result"
        )
    if not isinstance(result.get("metrics"), Mapping):
        raise RecallKernelFalsificationError(f"{field} requires metrics")
    return result


def _material_degradation(
    full_metrics: Mapping[str, Any],
    ablated_metrics: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if ablated_metrics.get("recovered_count", 0) < full_metrics.get("recovered_count", 0):
        reasons.append("recovered_count_decreased")
    if ablated_metrics.get("unsupported_count", 0) > full_metrics.get("unsupported_count", 0):
        reasons.append("unsupported_count_increased")
    if ablated_metrics.get("precision", 0.0) < full_metrics.get("precision", 0.0):
        reasons.append("precision_decreased")
    if ablated_metrics.get("sourced_recall", 0.0) < full_metrics.get("sourced_recall", 0.0):
        reasons.append("sourced_recall_decreased")
    if full_metrics.get("order_correct") is True and ablated_metrics.get("order_correct") is not True:
        reasons.append("required_order_failed")

    return bool(reasons), reasons


def evaluate_recall_kernel_ablations(
    *,
    experiment_id: str,
    kernel_fields: Sequence[str],
    full_kernel_result: Mapping[str, Any],
    ablation_results: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify observed one-field ablations against a full-kernel reconstruction.

    Each key in ``ablation_results`` names exactly one omitted kernel field. A field
    is classified ``OBSERVED_REQUIRED`` only when that supplied ablation materially
    degrades reconstruction under the fixed benchmark rubric. Otherwise it is
    ``NOT_SHOWN_REQUIRED``. The latter does not prove dispensability outside the
    checked experiment.
    """
    experiment = _required_text(experiment_id, "experiment_id")
    fields = _unique_texts(kernel_fields, "kernel_fields")
    full = _validate_result(full_kernel_result, "full_kernel_result")

    if not isinstance(ablation_results, Mapping):
        raise RecallKernelFalsificationError("ablation_results must be a mapping")
    if set(ablation_results) != set(fields):
        raise RecallKernelFalsificationError(
            "ablation_results must contain exactly one result for each kernel field"
        )

    benchmark_id = full.get("benchmark_id")
    reference_claims = full.get("reference_claims")
    required_order = full.get("required_order")
    full_metrics = full["metrics"]

    classifications: dict[str, dict[str, Any]] = {}
    observed_required: list[str] = []
    not_shown_required: list[str] = []

    for field in fields:
        result = _validate_result(ablation_results[field], f"ablation_results[{field}]")
        if result.get("benchmark_id") != benchmark_id:
            raise RecallKernelFalsificationError("benchmark_id must match across all conditions")
        if result.get("reference_claims") != reference_claims:
            raise RecallKernelFalsificationError("reference_claims must match across all conditions")
        if result.get("required_order") != required_order:
            raise RecallKernelFalsificationError("required_order must match across all conditions")

        degraded, reasons = _material_degradation(full_metrics, result["metrics"])
        status = "OBSERVED_REQUIRED" if degraded else "NOT_SHOWN_REQUIRED"
        classifications[field] = {
            "status": status,
            "condition_id": result.get("condition_id"),
            "degradation_reasons": reasons,
            "result_id": result.get("result_id"),
        }
        if degraded:
            observed_required.append(field)
        else:
            not_shown_required.append(field)

    payload = {
        "type": EVALUATION_TYPE,
        "version": EVALUATION_VERSION,
        "experiment_id": experiment,
        "benchmark_id": benchmark_id,
        "kernel_fields": list(fields),
        "full_kernel_result_id": full.get("result_id"),
        "field_classifications": classifications,
        "observed_required_fields": observed_required,
        "not_shown_required_fields": not_shown_required,
        "universal_requirement_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        evaluation_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise RecallKernelFalsificationError(str(exc)) from exc
    return {**payload, "evaluation_id": evaluation_id}
