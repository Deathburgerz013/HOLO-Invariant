"""Deterministic evidence receipts for consequential numeric metrics.

The measurement-ground contract is derived from the metric discipline in
Manny536/excellence-engine-v4. HOLO/Sim extends that contract with canonical
identity and explicit authority separation.

Provenance:
    Manny536/excellence-engine-v4, excellence_engine_v4/firewall.py,
    commit 944d073681f08665363e855d995ae4b006dba6d8
    Copyright (c) 2026 Manuel Coleman, MIT License.

A metric receipt establishes only what number was supplied and how its
measurement was described. It does not establish truth, acceptance, or
authority.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash


METRIC_TYPE = "bounded_metric_evidence"
METRIC_VERSION = 1
METRIC_FIELDS = {
    "type",
    "version",
    "value",
    "counted",
    "population",
    "source",
    "measurement_method",
    "evidence_reference",
    "accepted",
    "write_authority",
    "execution_authority",
    "metric_hash",
}


class MetricEvidenceError(ValueError):
    """Raised when a metric lacks bounded, recoverable measurement grounds."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MetricEvidenceError(f"{field} must be a non-empty string")
    return value


def _finite_number(value: Any) -> float | int:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise MetricEvidenceError("value must be a finite number")
    return value


def _metric_hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise MetricEvidenceError(str(exc)) from exc


def build_metric_evidence(
    *,
    value: float | int,
    counted: str,
    population: str,
    source: str,
    measurement_method: str,
    evidence_reference: str,
) -> dict[str, Any]:
    """Build one bounded metric receipt with explicit measurement grounds."""
    body = {
        "type": METRIC_TYPE,
        "version": METRIC_VERSION,
        "value": _finite_number(value),
        "counted": _required_text(counted, "counted"),
        "population": _required_text(population, "population"),
        "source": _required_text(source, "source"),
        "measurement_method": _required_text(
            measurement_method,
            "measurement_method",
        ),
        "evidence_reference": _required_text(
            evidence_reference,
            "evidence_reference",
        ),
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "metric_hash": _metric_hash(body)}


def validate_metric_evidence(metric: Mapping[str, Any]) -> bool:
    """Validate schema, canonical identity, measurement grounds, and bounds."""
    if not isinstance(metric, Mapping):
        raise MetricEvidenceError("metric must be an object")
    if set(metric) != METRIC_FIELDS:
        raise MetricEvidenceError(
            "metric fields do not match the versioned schema"
        )

    copied = deepcopy(dict(metric))
    actual_hash = copied.pop("metric_hash")
    if actual_hash != _metric_hash(copied):
        raise MetricEvidenceError("metric hash mismatch")

    if metric["type"] != METRIC_TYPE:
        raise MetricEvidenceError("metric type is invalid")
    if metric["version"] != METRIC_VERSION:
        raise MetricEvidenceError("metric version is invalid")
    _finite_number(metric["value"])
    for field in (
        "counted",
        "population",
        "source",
        "measurement_method",
        "evidence_reference",
    ):
        _required_text(metric[field], field)
    if metric["accepted"] is not False:
        raise MetricEvidenceError("metric cannot grant acceptance")
    if metric["write_authority"] != "NONE":
        raise MetricEvidenceError("metric cannot grant write authority")
    if metric["execution_authority"] != "NONE":
        raise MetricEvidenceError("metric cannot grant execution authority")
    return True
