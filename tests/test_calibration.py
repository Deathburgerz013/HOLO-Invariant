import hashlib
import json

import pytest

import holosim.calibration as calibration
from holosim.calibration import (
    CalibrationReceiptError,
    check_calibration_receipt_current,
    evaluate_forecast_calibration,
)


def forecast(forecast_id, confidence, outcome):
    return {
        "forecast_id": forecast_id,
        "confidence": confidence,
        "outcome": outcome,
    }


def rehash(receipt):
    body = dict(receipt)
    body.pop("receipt_hash", None)
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    receipt["receipt_hash"] = hashlib.sha256(encoded).hexdigest()


def test_known_brier_score_and_summary_metrics():
    receipt = evaluate_forecast_calibration(
        [forecast("a", 0.8, True), forecast("b", 0.6, False)]
    )

    assert receipt["sample_count"] == 2
    assert receipt["brier_score"] == pytest.approx(0.2)
    assert receipt["mean_confidence"] == pytest.approx(0.7)
    assert receipt["observed_frequency"] == pytest.approx(0.5)
    assert receipt["absolute_calibration_gap"] == pytest.approx(0.2)
    assert receipt["status"] == "SCORED"
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert "does not prove global calibration" in receipt["interpretation_notice"]


def test_perfect_forecasts_have_zero_brier_score():
    receipt = evaluate_forecast_calibration(
        [forecast("yes", 1, True), forecast("no", 0, False)]
    )

    assert receipt["brier_score"] == 0.0
    assert receipt["absolute_calibration_gap"] == 0.0


def test_empty_history_is_explicitly_insufficient():
    receipt = evaluate_forecast_calibration([])

    assert receipt["sample_count"] == 0
    assert receipt["status"] == "INSUFFICIENT_DATA"
    for field in (
        "brier_score",
        "mean_confidence",
        "observed_frequency",
        "absolute_calibration_gap",
    ):
        assert receipt[field] is None


def test_receipt_binds_ordered_normalized_records():
    receipt = evaluate_forecast_calibration([forecast("a", 1, True)])

    assert receipt["records"] == [forecast("a", 1.0, True)]
    assert len(receipt["record_hashes"]) == 1
    assert len(receipt["record_hashes"][0]) == 64
    assert len(receipt["receipt_hash"]) == 64


def test_receipt_is_current_for_same_history():
    records = [forecast("a", 0.75, True), forecast("b", 0.25, False)]
    receipt = evaluate_forecast_calibration(records)

    assert check_calibration_receipt_current(receipt, records) == {
        "current": True,
        "stale_reason": None,
    }


@pytest.mark.parametrize(
    "changed",
    [
        [forecast("a", 0.7, True), forecast("b", 0.2, False)],
        [forecast("a", 0.8, False), forecast("b", 0.2, False)],
        [forecast("b", 0.2, False), forecast("a", 0.8, True)],
        [forecast("a", 0.8, True)],
        [
            forecast("a", 0.8, True),
            forecast("b", 0.2, False),
            forecast("c", 0.5, True),
        ],
    ],
)
def test_changed_history_makes_receipt_stale(changed):
    receipt = evaluate_forecast_calibration(
        [forecast("a", 0.8, True), forecast("b", 0.2, False)]
    )

    assert check_calibration_receipt_current(receipt, changed) == {
        "current": False,
        "stale_reason": "FORECAST_HISTORY_CHANGED",
    }


@pytest.mark.parametrize(
    ("confidence", "message"),
    [
        (True, "finite number"),
        (None, "finite number"),
        (-0.01, "finite number"),
        (1.01, "finite number"),
        (float("nan"), "finite number"),
        (float("inf"), "finite number"),
        (10**400, "finite number"),
    ],
)
def test_invalid_confidence_fails_closed(confidence, message):
    with pytest.raises(CalibrationReceiptError, match=message):
        evaluate_forecast_calibration([forecast("a", confidence, True)])


@pytest.mark.parametrize("outcome", [0, 1, None, "true"])
def test_unresolved_or_nonboolean_outcome_fails_closed(outcome):
    with pytest.raises(CalibrationReceiptError, match="resolved boolean"):
        evaluate_forecast_calibration([forecast("a", 0.5, outcome)])


@pytest.mark.parametrize(
    "record",
    [
        "not-an-object",
        {"forecast_id": "a", "confidence": 0.5},
        {
            "forecast_id": "a",
            "confidence": 0.5,
            "outcome": True,
            "extra": "field",
        },
    ],
)
def test_invalid_record_shape_fails_closed(record):
    with pytest.raises(CalibrationReceiptError):
        evaluate_forecast_calibration([record])


def test_duplicate_forecast_ids_fail_closed():
    with pytest.raises(CalibrationReceiptError, match="unique"):
        evaluate_forecast_calibration(
            [forecast("same", 0.8, True), forecast("same", 0.2, False)]
        )


class StringSubclass(str):
    pass


@pytest.mark.parametrize(
    "forecast_id",
    ["", "   ", StringSubclass("a"), "\ud800", "x" * 1025],
)
def test_invalid_forecast_id_fails_closed(forecast_id):
    with pytest.raises(CalibrationReceiptError, match="forecast_id"):
        evaluate_forecast_calibration([forecast(forecast_id, 0.5, True)])


class DictSubclass(dict):
    pass


def test_record_requires_plain_object():
    with pytest.raises(CalibrationReceiptError, match="plain object"):
        evaluate_forecast_calibration(
            [DictSubclass(forecast("a", 0.5, True))]
        )


class HostileKey(str):
    __hash__ = str.__hash__

    def __eq__(self, other):
        raise RuntimeError("hostile key equality")


def hostile_key_record():
    return {
        HostileKey("forecast_id"): "a",
        HostileKey("confidence"): 0.5,
        HostileKey("outcome"): True,
    }


@pytest.mark.parametrize("operation", ["evaluate", "currentness"])
def test_hostile_string_subclass_keys_fail_with_domain_error(operation):
    with pytest.raises(CalibrationReceiptError, match="keys must be plain strings"):
        if operation == "evaluate":
            evaluate_forecast_calibration([hostile_key_record()])
        else:
            receipt = evaluate_forecast_calibration([forecast("a", 0.5, True)])
            check_calibration_receipt_current(receipt, [hostile_key_record()])


def test_noniterable_history_fails_with_domain_error():
    with pytest.raises(CalibrationReceiptError, match="iterable"):
        evaluate_forecast_calibration(None)


def test_generator_failure_fails_with_domain_error():
    def broken():
        yield forecast("a", 0.5, True)
        raise RuntimeError("generator failed")

    with pytest.raises(CalibrationReceiptError, match="materialized"):
        evaluate_forecast_calibration(broken())


def test_record_limit_fails_closed_without_unbounded_materialization(monkeypatch):
    monkeypatch.setattr(calibration, "MAX_CALIBRATION_RECORDS", 2)

    with pytest.raises(CalibrationReceiptError, match="cannot exceed 2"):
        evaluate_forecast_calibration(
            (
                forecast(str(index), 0.5, True)
                for index in range(3)
            )
        )


def test_evaluation_does_not_mutate_records():
    records = [forecast("a", 0.8, True), forecast("b", 0.2, False)]
    before = [dict(record) for record in records]

    evaluate_forecast_calibration(records)

    assert records == before


def test_generator_is_consumed_once_per_public_call():
    yielded = []

    def records():
        for item in [forecast("a", 0.8, True), forecast("b", 0.2, False)]:
            yielded.append(item["forecast_id"])
            yield item

    evaluate_forecast_calibration(records())

    assert yielded == ["a", "b"]


def test_unrehashed_tampering_fails_integrity():
    receipt = evaluate_forecast_calibration([forecast("a", 0.8, True)])
    receipt["brier_score"] = 0.9

    with pytest.raises(CalibrationReceiptError, match="hash mismatch"):
        check_calibration_receipt_current(receipt, [forecast("a", 0.8, True)])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("accepted", True, "cannot grant acceptance"),
        ("write_authority", "ALL", "cannot grant write authority"),
    ],
)
def test_rehashed_authority_tampering_fails_closed(field, value, message):
    receipt = evaluate_forecast_calibration([forecast("a", 0.8, True)])
    receipt[field] = value
    rehash(receipt)

    with pytest.raises(CalibrationReceiptError, match=message):
        check_calibration_receipt_current(receipt, [forecast("a", 0.8, True)])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda receipt: receipt.update(brier_score=0.0),
        lambda receipt: receipt.update(mean_confidence=0.0),
        lambda receipt: receipt.update(observed_frequency=0.0),
        lambda receipt: receipt.update(absolute_calibration_gap=0.9),
        lambda receipt: receipt.update(sample_count=99),
        lambda receipt: receipt.update(status="SCORED_WRONG"),
        lambda receipt: receipt["record_hashes"].reverse(),
        lambda receipt: receipt["records"][0].update(outcome=False),
    ],
)
def test_rehashed_semantic_tampering_fails_closed(mutation):
    receipt = evaluate_forecast_calibration(
        [forecast("a", 0.8, True), forecast("b", 0.2, False)]
    )
    mutation(receipt)
    rehash(receipt)

    with pytest.raises(CalibrationReceiptError, match="internally inconsistent"):
        check_calibration_receipt_current(
            receipt,
            [forecast("changed", 0.5, True)],
        )


def test_rehashed_missing_field_fails_schema_before_stale_path():
    receipt = evaluate_forecast_calibration([forecast("a", 0.8, True)])
    receipt.pop("status")
    rehash(receipt)

    with pytest.raises(CalibrationReceiptError, match="schema"):
        check_calibration_receipt_current(
            receipt, [forecast("changed", 0.5, True)]
        )


def test_boolean_version_fails_closed():
    receipt = evaluate_forecast_calibration([forecast("a", 0.8, True)])
    receipt["version"] = True
    rehash(receipt)

    with pytest.raises(CalibrationReceiptError, match="version"):
        check_calibration_receipt_current(receipt, [])


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_nonfinite_receipt_value_fails_with_domain_error(bad_value):
    receipt = evaluate_forecast_calibration([forecast("a", 0.8, True)])
    receipt["brier_score"] = bad_value

    with pytest.raises(CalibrationReceiptError, match="finite"):
        check_calibration_receipt_current(receipt, [])


def test_cyclic_receipt_fails_with_domain_error():
    receipt = evaluate_forecast_calibration([forecast("a", 0.8, True)])
    receipt["cycle"] = receipt

    with pytest.raises(CalibrationReceiptError, match="cycles"):
        check_calibration_receipt_current(receipt, [])


def test_excessively_deep_receipt_fails_with_domain_error():
    receipt = evaluate_forecast_calibration([forecast("a", 0.8, True)])
    nested = []
    cursor = nested
    for _ in range(10):
        child = []
        cursor.append(child)
        cursor = child
    receipt["deep"] = nested

    with pytest.raises(CalibrationReceiptError, match="depth"):
        check_calibration_receipt_current(receipt, [])