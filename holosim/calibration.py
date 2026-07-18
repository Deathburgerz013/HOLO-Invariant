"""Version-bound forecast calibration receipts for Holo/Sim.

Calibration is measured only against supplied resolved forecasts. A receipt
does not establish global calibration, truth, acceptance, or write authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping


CALIBRATION_RECEIPT_TYPE = "holo_forecast_calibration_observation"
CALIBRATION_RECEIPT_VERSION = 1
CALIBRATION_METHOD = "brier_binary_v1"
MAX_CALIBRATION_RECORDS = 1_000_000
MAX_FORECAST_ID_UTF8_BYTES = 1024
MAX_RECEIPT_JSON_DEPTH = 8


class CalibrationReceiptError(ValueError):
    """Raised when calibration inputs or receipts are malformed."""


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise CalibrationReceiptError("value could not be canonicalized") from exc


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _materialize_records(records: Iterable[Any]) -> list[Any]:
    try:
        iterator = iter(records)
    except Exception as exc:
        raise CalibrationReceiptError("records must be iterable") from exc

    materialized: list[Any] = []
    try:
        for _ in range(MAX_CALIBRATION_RECORDS + 1):
            try:
                materialized.append(next(iterator))
            except StopIteration:
                return materialized
    except Exception as exc:
        raise CalibrationReceiptError("records could not be materialized") from exc
    raise CalibrationReceiptError(
        f"records cannot exceed {MAX_CALIBRATION_RECORDS} items"
    )


def _require_forecast_id(value: Any) -> str:
    if type(value) is not str or not value.strip():
        raise CalibrationReceiptError("forecast_id must be a nonempty plain string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise CalibrationReceiptError("forecast_id must be valid UTF-8") from exc
    if len(encoded) > MAX_FORECAST_ID_UTF8_BYTES:
        raise CalibrationReceiptError(
            f"forecast_id cannot exceed {MAX_FORECAST_ID_UTF8_BYTES} UTF-8 bytes"
        )
    return value


def _require_confidence(value: Any) -> float:
    if type(value) not in {int, float}:
        raise CalibrationReceiptError(
            "confidence must be a finite number from 0 to 1"
        )
    try:
        confidence = float(value)
    except (OverflowError, ValueError) as exc:
        raise CalibrationReceiptError(
            "confidence must be a finite number from 0 to 1"
        ) from exc
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise CalibrationReceiptError(
            "confidence must be a finite number from 0 to 1"
        )
    return confidence


def _normalize_records(records: Iterable[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in _materialize_records(records):
        if type(record) is not dict:
            raise CalibrationReceiptError("each forecast record must be a plain object")
        keys = tuple(record.keys())
        if any(type(key) is not str for key in keys):
            raise CalibrationReceiptError(
                "forecast record keys must be plain strings"
            )
        if set(keys) != {"forecast_id", "confidence", "outcome"}:
            raise CalibrationReceiptError(
                "forecast record fields must be forecast_id, confidence, and outcome"
            )
        forecast_id = _require_forecast_id(record["forecast_id"])
        if forecast_id in seen_ids:
            raise CalibrationReceiptError("forecast_id values must be unique")
        seen_ids.add(forecast_id)
        confidence = _require_confidence(record["confidence"])
        outcome = record["outcome"]
        if type(outcome) is not bool:
            raise CalibrationReceiptError("outcome must be a resolved boolean")
        normalized.append(
            {
                "forecast_id": forecast_id,
                "confidence": confidence,
                "outcome": outcome,
            }
        )
    return normalized


def _metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(records)
    if count == 0:
        return {
            "sample_count": 0,
            "brier_score": None,
            "mean_confidence": None,
            "observed_frequency": None,
            "absolute_calibration_gap": None,
            "status": "INSUFFICIENT_DATA",
        }
    confidences = [record["confidence"] for record in records]
    outcomes = [1.0 if record["outcome"] else 0.0 for record in records]
    mean_confidence = math.fsum(confidences) / count
    observed_frequency = math.fsum(outcomes) / count
    brier_score = math.fsum(
        (confidence - outcome) ** 2
        for confidence, outcome in zip(confidences, outcomes)
    ) / count
    return {
        "sample_count": count,
        "brier_score": brier_score,
        "mean_confidence": mean_confidence,
        "observed_frequency": observed_frequency,
        "absolute_calibration_gap": abs(mean_confidence - observed_frequency),
        "status": "SCORED",
    }


def evaluate_forecast_calibration(
    records: Iterable[Any],
) -> dict[str, Any]:
    """Score an ordered history of resolved binary forecasts without mutation."""
    normalized = _normalize_records(records)
    record_hashes = [_canonical_hash(record) for record in normalized]
    body = {
        "type": CALIBRATION_RECEIPT_TYPE,
        "version": CALIBRATION_RECEIPT_VERSION,
        "method": CALIBRATION_METHOD,
        "records": normalized,
        "record_hashes": record_hashes,
        **_metrics(normalized),
        "current": True,
        "stale_reason": None,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This receipt scores only the supplied resolved forecasts. "
            "It does not prove global calibration, truth, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": _canonical_hash(body)}


def _validate_closed_json(value: Any) -> None:
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > MAX_RECEIPT_JSON_DEPTH:
            raise CalibrationReceiptError("receipt exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise CalibrationReceiptError("receipt numbers must be finite")
            return
        if type(item) is str:
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise CalibrationReceiptError(
                    "receipt strings must be valid UTF-8"
                ) from exc
            return
        if type(item) not in {dict, list}:
            raise CalibrationReceiptError(
                "receipt must contain only plain JSON values"
            )
        identity = id(item)
        if identity in active:
            raise CalibrationReceiptError("receipt must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise CalibrationReceiptError(
                            "receipt object keys must be strings"
                        )
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _validate_calibration_receipt(receipt: Mapping[str, Any]) -> None:
    if type(receipt) is not dict:
        raise CalibrationReceiptError("receipt must be a plain object")
    _validate_closed_json(receipt)
    expected_fields = {
        "type",
        "version",
        "method",
        "records",
        "record_hashes",
        "sample_count",
        "brier_score",
        "mean_confidence",
        "observed_frequency",
        "absolute_calibration_gap",
        "status",
        "current",
        "stale_reason",
        "accepted",
        "write_authority",
        "interpretation_notice",
        "receipt_hash",
    }
    if set(receipt) != expected_fields:
        raise CalibrationReceiptError(
            "receipt fields do not match the versioned schema"
        )
    if receipt["type"] != CALIBRATION_RECEIPT_TYPE:
        raise CalibrationReceiptError("receipt type is invalid")
    if (
        type(receipt["version"]) is not int
        or receipt["version"] != CALIBRATION_RECEIPT_VERSION
    ):
        raise CalibrationReceiptError("receipt version is invalid")
    if receipt["method"] != CALIBRATION_METHOD:
        raise CalibrationReceiptError("receipt method is invalid")
    if receipt["accepted"] is not False:
        raise CalibrationReceiptError("receipt cannot grant acceptance")
    if receipt["write_authority"] != "NONE":
        raise CalibrationReceiptError("receipt cannot grant write authority")
    receipt_hash = receipt["receipt_hash"]
    if type(receipt_hash) is not str or not re.fullmatch(
        r"[0-9a-f]{64}", receipt_hash
    ):
        raise CalibrationReceiptError(
            "receipt_hash must be 64 lowercase hex characters"
        )
    body = dict(receipt)
    body.pop("receipt_hash")
    if _canonical_hash(body) != receipt_hash:
        raise CalibrationReceiptError("receipt hash mismatch")

    records = receipt["records"]
    if type(records) is not list:
        raise CalibrationReceiptError("receipt records must be a list")
    expected = evaluate_forecast_calibration(records)
    if dict(receipt) != expected:
        raise CalibrationReceiptError(
            "receipt is internally inconsistent with its forecast records"
        )


def check_calibration_receipt_current(
    receipt: Mapping[str, Any], records: Iterable[Any]
) -> dict[str, Any]:
    """Check whether a calibration receipt still binds the supplied history."""
    _validate_calibration_receipt(receipt)
    current_records = _normalize_records(records)
    current_hashes = [_canonical_hash(record) for record in current_records]
    if current_hashes != receipt["record_hashes"]:
        return {"current": False, "stale_reason": "FORECAST_HISTORY_CHANGED"}
    expected = evaluate_forecast_calibration(current_records)
    if dict(receipt) != expected:
        return {"current": False, "stale_reason": "OBSERVATION_CHANGED"}
    return {"current": True, "stale_reason": None}