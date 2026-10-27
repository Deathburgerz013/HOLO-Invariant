"""Bounded, exact arithmetic means over compatible metric-evidence receipts.

A valid receipt proves consistency with supplied metric declarations, not the
truth of the measurements or the representativeness of their population.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.metric_evidence import MetricEvidenceError, validate_metric_evidence

RECEIPT_TYPE = "bounded_objective_average"
RECEIPT_VERSION = 1
MAX_OBSERVATIONS = 1000
MAX_VALUE_BITS = 4096
MAX_TOTAL_BITS = 16384
MAX_TEXT_BYTES = 1024


class ObjectiveAverageError(ValueError):
    """Invalid observations, incompatible measurements, or inconsistent receipt."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ObjectiveAverageError(f"{field} must be nonempty text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise ObjectiveAverageError(f"{field} must be valid UTF-8") from exc
    if size > MAX_TEXT_BYTES:
        raise ObjectiveAverageError(f"{field} exceeds text bound")
    return value


def _fraction(value: Any) -> Fraction:
    if type(value) is int:
        if value.bit_length() > MAX_VALUE_BITS:
            raise ObjectiveAverageError("integer exceeds numeric bound")
        return Fraction(value)
    if type(value) is float and math.isfinite(value):
        return Fraction.from_float(value)
    raise ObjectiveAverageError("metric value must be a finite plain number")


def _metrics(values: Any) -> list[dict[str, Any]]:
    if type(values) is not list or not 1 <= len(values) <= MAX_OBSERVATIONS:
        raise ObjectiveAverageError("metrics must be a nonempty bounded list")
    result = []
    seen = set()
    definition = None
    for item in values:
        if type(item) is not dict:
            raise ObjectiveAverageError("each metric must be a plain object")
        try:
            validate_metric_evidence(item)
        except (MetricEvidenceError, CanonicalValueError, OverflowError, RecursionError) as exc:
            raise ObjectiveAverageError("invalid metric evidence") from exc
        value = _fraction(item["value"])
        if value.numerator.bit_length() > MAX_VALUE_BITS or value.denominator.bit_length() > MAX_VALUE_BITS:
            raise ObjectiveAverageError("metric exceeds numeric bound")
        key = item["metric_hash"]
        if key in seen:
            raise ObjectiveAverageError("duplicate metric evidence")
        seen.add(key)
        current = (item["counted"], item["population"], item["measurement_method"])
        if definition is None:
            definition = current
        elif current != definition:
            raise ObjectiveAverageError("incompatible measurement definitions")
        result.append(dict(item))
    return result


def build_objective_average(*, metrics: list[dict[str, Any]], unit: str) -> dict[str, Any]:
    """Build a hash-bound arithmetic mean, exact for supplied Python numbers.

    The unit is a caller declaration shared by all inputs, not an independently
    verified conversion. Metric evidence v1 has no native unit field.
    """
    normalized = _metrics(metrics)
    declared_unit = _text(unit, "unit")
    total = Fraction(0)
    for metric in normalized:
        total += _fraction(metric["value"])
        if total.numerator.bit_length() > MAX_TOTAL_BITS or total.denominator.bit_length() > MAX_TOTAL_BITS:
            raise ObjectiveAverageError("sum exceeds numeric bound")
    mean = total / len(normalized)
    if mean.numerator.bit_length() > MAX_TOTAL_BITS or mean.denominator.bit_length() > MAX_TOTAL_BITS:
        raise ObjectiveAverageError("mean exceeds numeric bound")
    first = normalized[0]
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "method": "arithmetic_mean_exact_binary_v1",
        "unit": declared_unit,
        "counted": first["counted"],
        "population": first["population"],
        "measurement_method": first["measurement_method"],
        "sample_count": len(normalized),
        "metrics": normalized,
        "metric_hashes": [metric["metric_hash"] for metric in normalized],
        "mean_numerator": mean.numerator,
        "mean_denominator": mean.denominator,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    try:
        return {**body, "receipt_hash": stable_hash(body)}
    except (CanonicalValueError, OverflowError, RecursionError) as exc:
        raise ObjectiveAverageError("average cannot be canonically hashed") from exc


def verify_objective_average(receipt: Mapping[str, Any]) -> bool:
    """Rebuild and compare the entire closed receipt, not only its hash."""
    if type(receipt) is not dict:
        raise ObjectiveAverageError("receipt must be a plain object")
    expected_keys = {
        "type", "version", "method", "unit", "counted", "population",
        "measurement_method", "sample_count", "metrics", "metric_hashes",
        "mean_numerator", "mean_denominator", "accepted", "truth_claimed",
        "write_authority", "execution_authority", "receipt_hash",
    }
    if set(receipt) != expected_keys:
        raise ObjectiveAverageError("receipt fields do not match schema")
    expected = build_objective_average(metrics=receipt["metrics"], unit=receipt["unit"])
    if type(receipt["sample_count"]) is not int or type(receipt["mean_numerator"]) is not int or type(receipt["mean_denominator"]) is not int:
        raise ObjectiveAverageError("receipt numeric fields must be plain integers")
    if receipt != expected:
        raise ObjectiveAverageError("receipt differs from independently recomputed average")
    return True
