from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.metric_evidence import (
    MetricEvidenceError,
    build_metric_evidence,
    validate_metric_evidence,
)


def _metric(**overrides) -> dict:
    values = {
        "value": 9,
        "counted": "dependency edges affected",
        "population": "all dependency edges in candidate scope",
        "source": "dependency-graph:v3",
        "measurement_method": "count matching affected edge identifiers",
        "evidence_reference": "evidence:dependency-scan:sha256:abc123",
    }
    values.update(overrides)
    return build_metric_evidence(**values)


def test_complete_metric_builds_a_bounded_deterministic_receipt():
    metric = _metric()

    assert metric["type"] == "bounded_metric_evidence"
    assert metric["version"] == 1
    assert metric["value"] == 9
    assert metric["accepted"] is False
    assert metric["write_authority"] == "NONE"
    assert metric["execution_authority"] == "NONE"
    assert len(metric["metric_hash"]) == 64
    assert validate_metric_evidence(metric) is True
    assert metric == _metric()


@pytest.mark.parametrize(
    "field",
    [
        "counted",
        "population",
        "source",
        "measurement_method",
        "evidence_reference",
    ],
)
def test_metric_rejects_missing_measurement_ground(field):
    with pytest.raises(
        MetricEvidenceError,
        match=f"{field} must be a non-empty string",
    ):
        _metric(**{field: ""})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "9"])
def test_metric_rejects_non_finite_or_non_numeric_values(value):
    with pytest.raises(
        MetricEvidenceError,
        match="value must be a finite number",
    ):
        _metric(value=value)


def test_metric_hash_changes_when_measurement_ground_changes():
    original = _metric()
    changed = _metric(source="dependency-graph:v4")

    assert original["metric_hash"] != changed["metric_hash"]


def test_tampered_metric_fails_validation():
    tampered = deepcopy(_metric())
    tampered["value"] = 99

    with pytest.raises(MetricEvidenceError, match="metric hash mismatch"):
        validate_metric_evidence(tampered)


def test_metric_cannot_inject_acceptance_or_authority():
    injected = deepcopy(_metric())
    injected["accepted"] = True

    with pytest.raises(MetricEvidenceError, match="metric hash mismatch"):
        validate_metric_evidence(injected)

    unexpected = deepcopy(_metric())
    unexpected["approval"] = True
    with pytest.raises(
        MetricEvidenceError,
        match="fields do not match",
    ):
        validate_metric_evidence(unexpected)


def test_validation_rejects_rehashed_authority_escalation():
    metric = _metric()
    body = {key: value for key, value in metric.items() if key != "metric_hash"}
    body["write_authority"] = "ALL"

    from holosim.canonical import stable_hash

    escalated = {**body, "metric_hash": stable_hash(body)}
    with pytest.raises(
        MetricEvidenceError,
        match="cannot grant write authority",
    ):
        validate_metric_evidence(escalated)
