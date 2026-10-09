"""Bounded observer-registry falsification tests."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from holosim.canonical import canonical_json, stable_hash
from holosim.observer_registry import GENESIS, ObserverRegistry, ObserverRegistryError

SOURCE = "a" * 64


def test_serialized_succession(tmp_path):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")
    first = registry.register(source_checkpoint_hash=SOURCE, declaration="observer A", expected_previous_record_hash=GENESIS)
    second = registry.register(source_checkpoint_hash=SOURCE, declaration="observer B", expected_previous_record_hash=first["record_hash"])
    assert [r["observer_id"] for r in registry.read()] == ["AI-000001", "AI-000002"]
    assert second["previous_record_hash"] == first["record_hash"]
    assert second["record_hash"] == stable_hash({k: v for k, v in second.items() if k != "record_hash"})
    assert json.loads(canonical_json(second)) == second


def test_stale_does_not_append(tmp_path):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")
    registry.register(source_checkpoint_hash=SOURCE, declaration="A", expected_previous_record_hash=GENESIS)
    with pytest.raises(ObserverRegistryError, match="stale"):
        registry.register(source_checkpoint_hash=SOURCE, declaration="B", expected_previous_record_hash=GENESIS)
    assert len(registry.read()) == 1


def test_concurrent_same_head_only_one_wins(tmp_path):
    path = tmp_path / "observers.jsonl"
    def register(name):
        try:
            return ObserverRegistry(path).register(source_checkpoint_hash=SOURCE, declaration=name,
                                                   expected_previous_record_hash=GENESIS)
        except ObserverRegistryError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, ("A", "B")))
    assert sum(result is not None for result in results) == 1
    assert len(ObserverRegistry(path).read()) == 1


def test_tampered_record_rejected_even_when_chain_rehashed(tmp_path):
    path = tmp_path / "observers.jsonl"
    registry = ObserverRegistry(path)
    registry.register(source_checkpoint_hash=SOURCE, declaration="A", expected_previous_record_hash=GENESIS)
    entry = json.loads(path.read_text(encoding="utf-8"))
    record = json.loads(entry["content"])
    record["observer_id"] = "AI-999999"
    entry["content"] = canonical_json(record)
    entry["original_size"] = len(entry["content"])
    entry["hash"] = registry.chain._compute_hash(entry["prev_hash"], entry["content"], entry["timestamp"], entry["idx"])
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    with pytest.raises(ObserverRegistryError):
        registry.read()


def test_invalid_input_does_not_append(tmp_path):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")
    with pytest.raises(ObserverRegistryError):
        registry.register(source_checkpoint_hash="invalid", declaration="A", expected_previous_record_hash=GENESIS)
    assert registry.read() == []
