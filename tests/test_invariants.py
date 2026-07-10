#!/usr/bin/env python3
"""HOLO-Invariant verification tests."""

from __future__ import annotations

import difflib
import hashlib
import json
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings, strategies as st

from holosim.core import HoloChain


def simple_compress(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def simple_decompress(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))


def extract_invariants(state: dict) -> dict:
    return {
        "anchor_hash": hashlib.sha256(str(state.get("anchor", "")).encode("utf-8")).hexdigest(),
        "core_keys": sorted(k for k in state.keys() if not str(k).startswith("_")),
        "structure_hash": hashlib.sha256(
            json.dumps(state, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        ).hexdigest()[:16],
    }


def invariant_distance(a: dict, b: dict) -> float:
    ia = extract_invariants(a)
    ib = extract_invariants(b)
    if ia == ib:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, str(ia), str(ib)).ratio()


def assert_chain_healthy(chain: HoloChain) -> None:
    health = chain.health()
    assert isinstance(health, dict)
    assert health.get("recommendation") == "Healthy"


json_scalar = st.one_of(
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=200),
    st.booleans(),
    st.none(),
)

spine_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=50),
    values=json_scalar,
    min_size=5,
    max_size=50,
)

delta_strategy = st.dictionaries(
    keys=st.text(min_size=3, max_size=30),
    values=json_scalar,
    min_size=1,
    max_size=10,
)


def make_temp_chain(name: str) -> tuple[tempfile.TemporaryDirectory, HoloChain]:
    temp_dir = tempfile.TemporaryDirectory()
    chain_path = Path(temp_dir.name) / name
    return temp_dir, HoloChain(str(chain_path))


@given(initial_state=spine_strategy)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_invariant_preservation_roundtrip(initial_state: dict) -> None:
    compressed = simple_compress(initial_state)
    reconstructed = simple_decompress(compressed)

    assert extract_invariants(initial_state) == extract_invariants(reconstructed)


@given(base_state=spine_strategy, deltas=st.lists(delta_strategy, min_size=1, max_size=5))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_differential_fuzzing_chain_integrity(base_state: dict, deltas: list[dict]) -> None:
    temp_dir, chain = make_temp_chain("test_fuzz_memory.jsonl")
    try:
        current = base_state.copy()
        chain.append({"state_snapshot": current, "invariant": extract_invariants(current)})

        for delta in deltas:
            current = current.copy()
            current.update(delta)
            chain.append({"state_snapshot": current, "invariant": extract_invariants(current)})

        assert_chain_healthy(chain)
    finally:
        temp_dir.cleanup()


@given(state=spine_strategy)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_hash_chain_monotonicity(state: dict) -> None:
    temp_dir, chain = make_temp_chain("test_monotonic.jsonl")
    try:
        chain.append({"test_state": state, "invariant": extract_invariants(state)})

        mutated = state.copy()
        mutated["_noise"] = "fuzz"
        chain.append({"test_state": mutated, "invariant": extract_invariants(mutated)})

        assert_chain_healthy(chain)
    finally:
        temp_dir.cleanup()