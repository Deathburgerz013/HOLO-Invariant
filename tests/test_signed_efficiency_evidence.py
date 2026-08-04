from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.metric_evidence import build_metric_evidence
from holosim.signed_efficiency_evidence import (
    SignedEfficiencyEvidenceError,
    evaluate_signed_outcome_efficiency,
)
from holosim.signed_occurrence import build_signed_occurrence


SECRET = b"s" * 32
SOURCE_ID = "source:efficiency-observer"
SECRETS = {SOURCE_ID: SECRET}
EVALUATION_ID = "evaluation:gap-closure:0001"


def _metric(
    value: float,
    *,
    counted: str = "unresolved checks",
    method: str = "count unresolved checks",
) -> dict[str, object]:
    return build_metric_evidence(
        value=value,
        counted=counted,
        population="bounded validation run",
        source="signed test observer",
        measurement_method=method,
        evidence_reference=f"{counted}:{value}",
    )


def _occurrence(
    *,
    number: int,
    role: str,
    metric: dict[str, object],
    evaluation_id: str = EVALUATION_ID,
) -> dict[str, object]:
    return build_signed_occurrence(
        source_id=SOURCE_ID,
        occurrence_id=f"occurrence:efficiency:{number}",
        payload={
            "evaluation_id": evaluation_id,
            "role": role,
            "metric": metric,
        },
        observed_at=f"2026-08-04T13:00:{number:02d}Z",
        sequence=number,
        nonce=f"nonce:efficiency:{number:016d}",
        secret=SECRET,
    )


def _occurrences() -> list[dict[str, object]]:
    return [
        _occurrence(number=1, role="BEFORE_GAP", metric=_metric(10)),
        _occurrence(number=2, role="AFTER_GAP", metric=_metric(4)),
        _occurrence(
            number=3,
            role="MEASURED_COST",
            metric=_metric(
                3,
                counted="processor seconds",
                method="monotonic elapsed-time observation",
            ),
        ),
    ]


def test_signed_metrics_produce_bounded_efficiency_observation() -> None:
    result = evaluate_signed_outcome_efficiency(
        evaluation_id=EVALUATION_ID,
        occurrences=_occurrences(),
        source_secrets=SECRETS,
    )

    assert result["efficiency"]["gap_reduction"] == 6
    assert result["efficiency"]["closure_fraction"] == 0.6
    assert result["efficiency"]["efficiency"] == 2
    assert result["efficiency"]["outcome"] == "IMPROVED"
    assert list(result["observations"]) == [
        "BEFORE_GAP",
        "AFTER_GAP",
        "MEASURED_COST",
    ]
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert len(result["binding_hash"]) == 64


def test_tampered_metric_cannot_enter_efficiency_calculation() -> None:
    occurrences = _occurrences()
    occurrences[1]["payload"]["metric"]["value"] = 1

    with pytest.raises(
        SignedEfficiencyEvidenceError,
        match="was not verified: REJECTED_TAMPERED",
    ):
        evaluate_signed_outcome_efficiency(
            evaluation_id=EVALUATION_ID,
            occurrences=occurrences,
            source_secrets=SECRETS,
        )


def test_signed_but_invalid_metric_receipt_is_rejected() -> None:
    metric = _metric(4)
    metric["value"] = 1
    occurrences = _occurrences()
    occurrences[1] = _occurrence(
        number=2,
        role="AFTER_GAP",
        metric=metric,
    )

    with pytest.raises(
        SignedEfficiencyEvidenceError,
        match="payload.metric is invalid: metric hash mismatch",
    ):
        evaluate_signed_outcome_efficiency(
            evaluation_id=EVALUATION_ID,
            occurrences=occurrences,
            source_secrets=SECRETS,
        )


def test_metrics_from_different_evaluations_cannot_be_mixed() -> None:
    occurrences = _occurrences()
    occurrences[1] = _occurrence(
        number=2,
        role="AFTER_GAP",
        metric=_metric(4),
        evaluation_id="evaluation:other",
    )

    with pytest.raises(
        SignedEfficiencyEvidenceError,
        match="bound to a different evaluation",
    ):
        evaluate_signed_outcome_efficiency(
            evaluation_id=EVALUATION_ID,
            occurrences=occurrences,
            source_secrets=SECRETS,
        )


def test_duplicate_role_is_rejected() -> None:
    occurrences = _occurrences()
    occurrences[2] = _occurrence(
        number=3,
        role="AFTER_GAP",
        metric=_metric(3),
    )

    with pytest.raises(
        SignedEfficiencyEvidenceError,
        match="duplicate signed efficiency role: AFTER_GAP",
    ):
        evaluate_signed_outcome_efficiency(
            evaluation_id=EVALUATION_ID,
            occurrences=occurrences,
            source_secrets=SECRETS,
        )


def test_missing_role_is_rejected() -> None:
    with pytest.raises(
        SignedEfficiencyEvidenceError,
        match="missing signed efficiency roles: MEASURED_COST",
    ):
        evaluate_signed_outcome_efficiency(
            evaluation_id=EVALUATION_ID,
            occurrences=_occurrences()[:2],
            source_secrets=SECRETS,
        )


def test_unknown_source_cannot_supply_efficiency_metric() -> None:
    with pytest.raises(
        SignedEfficiencyEvidenceError,
        match="was not verified: REJECTED_UNKNOWN_SOURCE",
    ):
        evaluate_signed_outcome_efficiency(
            evaluation_id=EVALUATION_ID,
            occurrences=_occurrences(),
            source_secrets={},
        )


def test_incompatible_signed_gap_metrics_remain_rejected() -> None:
    occurrences = _occurrences()
    occurrences[1] = _occurrence(
        number=2,
        role="AFTER_GAP",
        metric=_metric(4, method="estimate unresolved checks"),
    )

    with pytest.raises(
        SignedEfficiencyEvidenceError,
        match=(
            "signed efficiency metrics are incompatible: before_gap and "
            "after_gap measurement_method must match"
        ),
    ):
        evaluate_signed_outcome_efficiency(
            evaluation_id=EVALUATION_ID,
            occurrences=occurrences,
            source_secrets=SECRETS,
        )


def test_inputs_are_not_mutated_and_binding_is_order_independent() -> None:
    occurrences = _occurrences()
    original = deepcopy(occurrences)

    first = evaluate_signed_outcome_efficiency(
        evaluation_id=EVALUATION_ID,
        occurrences=occurrences,
        source_secrets=SECRETS,
    )
    second = evaluate_signed_outcome_efficiency(
        evaluation_id=EVALUATION_ID,
        occurrences=list(reversed(occurrences)),
        source_secrets=SECRETS,
    )

    assert occurrences == original
    assert first == second
