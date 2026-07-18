"""Version-bound observations of HoloChain performance.

This module measures bounded, disposable chains.  It does not optimize the
chain, classify hardware as adequate, or grant authority to change behavior.
Timing results are observations of one execution environment only.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import shutil
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

from holosim.config import HOLOSIM_VERSION
from holosim.core import HoloChain


PERFORMANCE_OBSERVATION_TYPE = "holo_chain_performance_observation"
PERFORMANCE_OBSERVATION_VERSION = 1
MAX_ENTRY_COUNTS = 12
MAX_CHAIN_ENTRIES = 10_000
MAX_REPEATS = 20
MAX_PAYLOAD_UTF8_BYTES = 65_536
MAX_RECEIPT_JSON_DEPTH = 10


class PerformanceObservationError(ValueError):
    """Raised when observation inputs or receipts are malformed."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise PerformanceObservationError("value could not be canonicalized") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _materialize_entry_counts(values: Iterable[int]) -> list[int]:
    if type(values) in {str, bytes, bytearray}:
        raise PerformanceObservationError("entry_counts must be an iterable of integers")
    try:
        iterator = iter(values)
    except Exception as exc:
        raise PerformanceObservationError("entry_counts must be iterable") from exc

    result: list[int] = []
    try:
        for _ in range(MAX_ENTRY_COUNTS + 1):
            try:
                value = next(iterator)
            except StopIteration:
                break
            if type(value) is not int or not 1 <= value <= MAX_CHAIN_ENTRIES:
                raise PerformanceObservationError(
                    f"entry counts must be plain integers from 1 to {MAX_CHAIN_ENTRIES}"
                )
            result.append(value)
    except PerformanceObservationError:
        raise
    except Exception as exc:
        raise PerformanceObservationError("entry_counts could not be materialized") from exc

    if len(result) > MAX_ENTRY_COUNTS:
        raise PerformanceObservationError(
            f"entry_counts cannot exceed {MAX_ENTRY_COUNTS} items"
        )
    if not result:
        raise PerformanceObservationError("entry_counts cannot be empty")
    if result != sorted(set(result)):
        raise PerformanceObservationError(
            "entry_counts must be unique and strictly increasing"
        )
    return result


def _require_repeats(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_REPEATS:
        raise PerformanceObservationError(
            f"repeats must be a plain integer from 1 to {MAX_REPEATS}"
        )
    return value


def _require_payload(value: str) -> str:
    if type(value) is not str or not value:
        raise PerformanceObservationError("payload must be a nonempty plain string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise PerformanceObservationError("payload must be valid UTF-8") from exc
    if len(encoded) > MAX_PAYLOAD_UTF8_BYTES:
        raise PerformanceObservationError(
            f"payload cannot exceed {MAX_PAYLOAD_UTF8_BYTES} UTF-8 bytes"
        )
    return value


def _environment_identity() -> dict[str, str]:
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "operating_system": platform.system(),
        "operating_system_release": platform.release(),
        "machine": platform.machine(),
        "holosim_version": HOLOSIM_VERSION,
        "clock": "time.perf_counter_ns",
    }


def _elapsed_ns(start: int, end: int, field: str) -> int:
    if type(start) is not int or type(end) is not int or end < start:
        raise PerformanceObservationError(f"clock produced an invalid {field} interval")
    return end - start


def _measure_once(entry_count: int, payload: str) -> dict[str, Any]:
    directory: Path | None = None
    setup_start = time.perf_counter_ns()
    try:
        directory = Path(tempfile.mkdtemp(prefix="holosim-performance-"))
        chain = HoloChain(directory / "performance.jsonl")
        setup_ns = _elapsed_ns(
            setup_start, time.perf_counter_ns(), "temporary setup"
        )

        append_start = time.perf_counter_ns()
        for index in range(entry_count):
            chain.append({"sequence": index, "payload": payload})
        append_ns = _elapsed_ns(append_start, time.perf_counter_ns(), "append")

        health_start = time.perf_counter_ns()
        health = chain.health()
        health_ns = _elapsed_ns(health_start, time.perf_counter_ns(), "health")
        if health.get("recommendation") != "Healthy":
            raise PerformanceObservationError(
                "disposable chain did not report Healthy after measurement"
            )

        entries = chain.load_and_verify()
        if len(entries) != entry_count:
            raise PerformanceObservationError(
                "disposable chain entry count changed during measurement"
            )
        root_hash = entries[-1]["hash"]
    except PerformanceObservationError:
        raise
    except Exception as exc:
        raise PerformanceObservationError("performance measurement failed") from exc
    finally:
        cleanup_start = time.perf_counter_ns()
        if directory is not None:
            shutil.rmtree(directory, ignore_errors=False)
        cleanup_end = time.perf_counter_ns()

    return {
        "setup_ns": setup_ns,
        "append_ns": append_ns,
        "health_ns": health_ns,
        "cleanup_ns": _elapsed_ns(cleanup_start, cleanup_end, "cleanup"),
        "root_hash": root_hash,
    }


def _median_ns(samples: list[dict[str, Any]], field: str) -> int:
    return int(statistics.median(sample[field] for sample in samples))


def _summarize(entry_count: int, samples: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "entry_count": entry_count,
        "samples": samples,
        "median_setup_ns": _median_ns(samples, "setup_ns"),
        "median_append_ns": _median_ns(samples, "append_ns"),
        "median_health_ns": _median_ns(samples, "health_ns"),
        "median_cleanup_ns": _median_ns(samples, "cleanup_ns"),
    }


def _scaling_steps(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for previous, current in zip(summaries, summaries[1:]):
        previous_time = previous["median_append_ns"]
        ratio = None if previous_time == 0 else current["median_append_ns"] / previous_time
        steps.append(
            {
                "from_entry_count": previous["entry_count"],
                "to_entry_count": current["entry_count"],
                "entry_count_ratio": current["entry_count"] / previous["entry_count"],
                "median_append_time_ratio": ratio,
            }
        )
    return steps


def observe_chain_performance(
    entry_counts: Iterable[int],
    *,
    repeats: int = 3,
    payload: str = "holo-performance-observation",
) -> dict[str, Any]:
    """Measure bounded disposable chains and return a tamper-evident receipt.

    The function creates and removes its own temporary chains.  It never opens
    a caller-owned chain.  Ratios are reported without classifying them as a
    defect, regression, limit, or hardware requirement.
    """
    checked_counts = _materialize_entry_counts(entry_counts)
    checked_repeats = _require_repeats(repeats)
    checked_payload = _require_payload(payload)

    summaries = []
    for entry_count in checked_counts:
        samples = [
            _measure_once(entry_count, checked_payload)
            for _ in range(checked_repeats)
        ]
        summaries.append(_summarize(entry_count, samples))

    body = {
        "type": PERFORMANCE_OBSERVATION_TYPE,
        "version": PERFORMANCE_OBSERVATION_VERSION,
        "environment": _environment_identity(),
        "entry_counts": checked_counts,
        "repeats": checked_repeats,
        "payload_sha256": hashlib.sha256(
            checked_payload.encode("utf-8")
        ).hexdigest(),
        "measurements": summaries,
        "scaling_steps": _scaling_steps(summaries),
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Timings describe this bounded execution only. They do not establish "
            "a defect, regression, hardware limit, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": _digest(body)}


def _validate_closed_json(value: Any) -> None:
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > MAX_RECEIPT_JSON_DEPTH:
            raise PerformanceObservationError("receipt exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise PerformanceObservationError("receipt numbers must be finite")
            return
        if type(item) is str:
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise PerformanceObservationError(
                    "receipt strings must be valid UTF-8"
                ) from exc
            return
        if type(item) not in {dict, list}:
            raise PerformanceObservationError(
                "receipt must contain only plain JSON values"
            )
        identity = id(item)
        if identity in active:
            raise PerformanceObservationError("receipt must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise PerformanceObservationError(
                            "receipt object keys must be plain strings"
                        )
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _require_nonnegative_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise PerformanceObservationError(f"{field} must be a nonnegative integer")
    return value


def _require_ratio(value: Any, field: str, *, optional: bool = False) -> float | None:
    if optional and value is None:
        return None
    if type(value) not in {int, float} or type(value) is bool:
        raise PerformanceObservationError(f"{field} must be a finite nonnegative number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise PerformanceObservationError(f"{field} must be a finite nonnegative number")
    return result


def validate_performance_receipt(receipt: Mapping[str, Any]) -> None:
    """Fail closed if a performance receipt is malformed or inconsistent."""
    if type(receipt) is not dict:
        raise PerformanceObservationError("receipt must be a plain object")
    _validate_closed_json(receipt)

    expected_fields = {
        "type",
        "version",
        "environment",
        "entry_counts",
        "repeats",
        "payload_sha256",
        "measurements",
        "scaling_steps",
        "accepted",
        "write_authority",
        "interpretation_notice",
        "receipt_hash",
    }
    if set(receipt) != expected_fields:
        raise PerformanceObservationError(
            "receipt fields do not match the versioned schema"
        )
    if receipt["type"] != PERFORMANCE_OBSERVATION_TYPE:
        raise PerformanceObservationError("receipt type is invalid")
    if (
        type(receipt["version"]) is not int
        or receipt["version"] != PERFORMANCE_OBSERVATION_VERSION
    ):
        raise PerformanceObservationError("receipt version is invalid")
    if receipt["accepted"] is not False:
        raise PerformanceObservationError("receipt cannot grant acceptance")
    if receipt["write_authority"] != "NONE":
        raise PerformanceObservationError("receipt cannot grant write authority")
    if type(receipt["interpretation_notice"]) is not str:
        raise PerformanceObservationError("interpretation_notice must be a string")

    environment = receipt["environment"]
    environment_fields = {
        "python_implementation",
        "python_version",
        "operating_system",
        "operating_system_release",
        "machine",
        "holosim_version",
        "clock",
    }
    if type(environment) is not dict or set(environment) != environment_fields:
        raise PerformanceObservationError("environment fields are invalid")
    if any(type(value) is not str for value in environment.values()):
        raise PerformanceObservationError("environment values must be strings")

    counts = _materialize_entry_counts(receipt["entry_counts"])
    repeats = _require_repeats(receipt["repeats"])
    if type(receipt["payload_sha256"]) is not str or not re.fullmatch(
        r"[0-9a-f]{64}", receipt["payload_sha256"]
    ):
        raise PerformanceObservationError("payload_sha256 is invalid")

    measurements = receipt["measurements"]
    if type(measurements) is not list or len(measurements) != len(counts):
        raise PerformanceObservationError("measurement count must match entry_counts")
    measurement_fields = {
        "entry_count",
        "samples",
        "median_setup_ns",
        "median_append_ns",
        "median_health_ns",
        "median_cleanup_ns",
    }
    sample_fields = {
        "setup_ns",
        "append_ns",
        "health_ns",
        "cleanup_ns",
        "root_hash",
    }
    for index, measurement in enumerate(measurements):
        if type(measurement) is not dict or set(measurement) != measurement_fields:
            raise PerformanceObservationError("measurement fields are invalid")
        if measurement["entry_count"] != counts[index]:
            raise PerformanceObservationError("measurement entry_count is inconsistent")
        samples = measurement["samples"]
        if type(samples) is not list or len(samples) != repeats:
            raise PerformanceObservationError("sample count must match repeats")
        for sample in samples:
            if type(sample) is not dict or set(sample) != sample_fields:
                raise PerformanceObservationError("sample fields are invalid")
            for field in ("setup_ns", "append_ns", "health_ns", "cleanup_ns"):
                _require_nonnegative_int(sample[field], field)
            if type(sample["root_hash"]) is not str or not re.fullmatch(
                r"[0-9a-f]{64}", sample["root_hash"]
            ):
                raise PerformanceObservationError("sample root_hash is invalid")
        for field, sample_field in (
            ("median_setup_ns", "setup_ns"),
            ("median_append_ns", "append_ns"),
            ("median_health_ns", "health_ns"),
            ("median_cleanup_ns", "cleanup_ns"),
        ):
            value = _require_nonnegative_int(measurement[field], field)
            if value != int(statistics.median(item[sample_field] for item in samples)):
                raise PerformanceObservationError(f"{field} is inconsistent with samples")

    expected_steps = _scaling_steps(measurements)
    steps = receipt["scaling_steps"]
    if type(steps) is not list or len(steps) != len(expected_steps):
        raise PerformanceObservationError("scaling_steps count is invalid")
    step_fields = {
        "from_entry_count",
        "to_entry_count",
        "entry_count_ratio",
        "median_append_time_ratio",
    }
    for step, expected in zip(steps, expected_steps):
        if type(step) is not dict or set(step) != step_fields:
            raise PerformanceObservationError("scaling step fields are invalid")
        _require_ratio(step["entry_count_ratio"], "entry_count_ratio")
        _require_ratio(
            step["median_append_time_ratio"],
            "median_append_time_ratio",
            optional=True,
        )
        if step != expected:
            raise PerformanceObservationError("scaling step is inconsistent")

    receipt_hash = receipt["receipt_hash"]
    if type(receipt_hash) is not str or not re.fullmatch(
        r"[0-9a-f]{64}", receipt_hash
    ):
        raise PerformanceObservationError("receipt_hash is invalid")
    body = dict(receipt)
    body.pop("receipt_hash")
    if _digest(body) != receipt_hash:
        raise PerformanceObservationError("receipt hash mismatch")
