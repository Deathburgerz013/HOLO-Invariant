from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from holosim import performance
from holosim.performance import (
    PerformanceObservationError,
    observe_chain_performance,
    validate_performance_receipt,
)


class DeterministicClock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> int:
        self.value += 10
        return self.value


def test_observation_is_bounded_tamper_evident_and_non_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(performance.time, "perf_counter_ns", DeterministicClock())

    receipt = observe_chain_performance([1, 2], repeats=2, payload="bounded")

    validate_performance_receipt(receipt)
    assert receipt["type"] == "holo_chain_performance_observation"
    assert receipt["version"] == 1
    assert receipt["entry_counts"] == [1, 2]
    assert receipt["repeats"] == 2
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert re.fullmatch(r"[0-9a-f]{64}", receipt["receipt_hash"])
    assert len(receipt["measurements"]) == 2
    assert len(receipt["scaling_steps"]) == 1
    assert receipt["scaling_steps"][0]["from_entry_count"] == 1
    assert receipt["scaling_steps"][0]["to_entry_count"] == 2


def test_observation_uses_only_disposable_chains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protected = tmp_path / "existing.jsonl"
    protected.write_text("user-owned\n", encoding="utf-8")
    before = protected.read_bytes()

    created_paths: list[Path] = []
    real_chain = performance.HoloChain

    class RecordingChain(real_chain):
        def __init__(self, file_path: str | Path, *args: object, **kwargs: object) -> None:
            created_paths.append(Path(file_path))
            super().__init__(file_path, *args, **kwargs)

    monkeypatch.setattr(performance, "HoloChain", RecordingChain)
    monkeypatch.setattr(performance.time, "perf_counter_ns", DeterministicClock())

    observe_chain_performance([1], repeats=1)

    assert protected.read_bytes() == before
    assert created_paths
    assert all(path != protected for path in created_paths)
    assert all(not path.exists() for path in created_paths)


@pytest.mark.parametrize(
    "entry_counts,repeats,payload",
    [
        ([], 1, "x"),
        ([2, 1], 1, "x"),
        ([1, 1], 1, "x"),
        ([0], 1, "x"),
        ([1], 0, "x"),
        ([1], 1, ""),
    ],
)
def test_invalid_observation_inputs_fail_closed(
    entry_counts: list[int], repeats: int, payload: str
) -> None:
    with pytest.raises(PerformanceObservationError):
        observe_chain_performance(entry_counts, repeats=repeats, payload=payload)


def test_generator_failure_becomes_domain_error() -> None:
    def broken_counts():
        yield 1
        raise RuntimeError("generator failed")

    with pytest.raises(
        PerformanceObservationError,
        match="entry_counts could not be materialized",
    ):
        observe_chain_performance(broken_counts())


def test_oversized_inputs_fail_closed() -> None:
    with pytest.raises(PerformanceObservationError):
        observe_chain_performance(
            range(1, performance.MAX_ENTRY_COUNTS + 2),
            repeats=1,
        )
    with pytest.raises(PerformanceObservationError):
        observe_chain_performance(
            [1],
            repeats=1,
            payload="x" * (performance.MAX_PAYLOAD_UTF8_BYTES + 1),
        )


def test_receipt_hash_tampering_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(performance.time, "perf_counter_ns", DeterministicClock())
    receipt = observe_chain_performance([1], repeats=1)
    tampered = copy.deepcopy(receipt)
    tampered["measurements"][0]["samples"][0]["append_ns"] += 1

    with pytest.raises(PerformanceObservationError):
        validate_performance_receipt(tampered)


def test_cyclic_receipt_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(performance.time, "perf_counter_ns", DeterministicClock())
    receipt = observe_chain_performance([1], repeats=1)
    receipt["cycle"] = receipt

    with pytest.raises(PerformanceObservationError, match="must not contain cycles"):
        validate_performance_receipt(receipt)


def test_nonfinite_timing_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(performance.time, "perf_counter_ns", DeterministicClock())
    receipt = observe_chain_performance([1], repeats=1)
    receipt["measurements"][0]["samples"][0]["append_ns"] = float("inf")

    with pytest.raises(PerformanceObservationError, match="numbers must be finite"):
        validate_performance_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [("accepted", True), ("write_authority", "FULL")],
)
def test_receipt_cannot_grant_authority(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    monkeypatch.setattr(performance.time, "perf_counter_ns", DeterministicClock())
    receipt = observe_chain_performance([1], repeats=1)
    receipt[field] = value

    with pytest.raises(PerformanceObservationError):
        validate_performance_receipt(receipt)


def test_semantic_tampering_is_rejected_even_after_rehash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(performance.time, "perf_counter_ns", DeterministicClock())
    receipt = observe_chain_performance([1, 2], repeats=1)
    tampered = copy.deepcopy(receipt)
    tampered["scaling_steps"][0]["entry_count_ratio"] = 99.0
    body = dict(tampered)
    body.pop("receipt_hash")
    tampered["receipt_hash"] = performance._digest(body)

    with pytest.raises(
        PerformanceObservationError,
        match="scaling step is inconsistent",
    ):
        validate_performance_receipt(tampered)


def test_input_generator_is_consumed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(performance.time, "perf_counter_ns", DeterministicClock())
    consumed: list[int] = []

    def counts():
        for value in (1, 2):
            consumed.append(value)
            yield value

    observe_chain_performance(counts(), repeats=1)

    assert consumed == [1, 2]


def test_observation_does_not_assert_a_hardware_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(performance.time, "perf_counter_ns", DeterministicClock())
    receipt = observe_chain_performance([1, 2], repeats=1)

    assert "verdict" not in receipt
    assert "classification" not in receipt
    assert "threshold_ns" not in receipt
    assert "within_limit" not in receipt
