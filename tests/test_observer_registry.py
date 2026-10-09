"""Bounded observer-registry falsification tests."""
import json
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
import time

import pytest

from holosim.canonical import canonical_json, stable_hash
from holosim.observer_registry import GENESIS, ObserverRegistry, ObserverRegistryError, verify_records

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


def test_repeated_declaration_gets_new_position(tmp_path):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")

    first = registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="same observer declaration",
        expected_previous_record_hash=GENESIS,
    )
    second = registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="same observer declaration",
        expected_previous_record_hash=first["record_hash"],
    )

    assert first["observer_id"] == "AI-000001"
    assert second["observer_id"] == "AI-000002"
    assert first["record_hash"] != second["record_hash"]
    assert len(registry.read()) == 2


def test_sequence_gap_rejected(tmp_path):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")

    first = registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="observer A",
        expected_previous_record_hash=GENESIS,
    )

    entries = registry.chain.load_and_verify()
    record = json.loads(entries[0]["content"])

    record["sequence"] = 3
    record["observer_id"] = "AI-000003"

    body = {k: v for k, v in record.items() if k != "record_hash"}
    record["record_hash"] = stable_hash(body)

    with pytest.raises(ObserverRegistryError, match="succession"):
        verify_records([{"content": canonical_json(record)}])

    assert first["observer_id"] == "AI-000001"


def test_wrong_predecessor_rejected(tmp_path):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")

    first = registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="observer A",
        expected_previous_record_hash=GENESIS,
    )
    registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="observer B",
        expected_previous_record_hash=first["record_hash"],
    )

    records = registry.read()
    records[1]["previous_record_hash"] = "f" * 64

    body = {
        key: value
        for key, value in records[1].items()
        if key != "record_hash"
    }
    records[1]["record_hash"] = stable_hash(body)

    with pytest.raises(ObserverRegistryError, match="succession"):
        verify_records([
            {"content": canonical_json(record)}
            for record in records
        ])


@pytest.mark.parametrize("mutation", ["extra", "missing"])


def test_registry_schema_rejected(tmp_path, mutation):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")

    registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="observer A",
        expected_previous_record_hash=GENESIS,
    )

    record = registry.read()[0]

    if mutation == "extra":
        record["unexpected_field"] = "not permitted"
    else:
        del record["declaration"]

    body = {
        key: value
        for key, value in record.items()
        if key != "record_hash"
    }
    record["record_hash"] = stable_hash(body)

    with pytest.raises(ObserverRegistryError, match="schema"):
        verify_records([{"content": canonical_json(record)}])


@pytest.mark.parametrize("declaration", ["", "   ", None, 123, [], {}])


def test_invalid_declaration_rejected(tmp_path, declaration):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")

    with pytest.raises(ObserverRegistryError, match="declaration"):
        registry.register(
            source_checkpoint_hash=SOURCE,
            declaration=declaration,
            expected_previous_record_hash=GENESIS,
        )

    assert registry.read() == []


def test_oversized_declaration_rejected(tmp_path):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")

    with pytest.raises(ObserverRegistryError, match="declaration.*limit"):
        registry.register(
            source_checkpoint_hash=SOURCE,
            declaration="A" * 65537,
            expected_previous_record_hash=GENESIS,
        )

    assert registry.read() == []


@pytest.mark.parametrize(
    "declaration,accepted",
    [
        ("A" * 65536, True),
        ("A" * 65537, False),
        ("\u00e9" * 32768, True),
        ("\u00e9" * 32769, False),
    ],
    ids=[
        "ascii-at-limit",
        "ascii-over-limit",
        "unicode-at-limit",
        "unicode-over-limit",
    ],
)


def test_declaration_utf8_byte_boundary(tmp_path, declaration, accepted):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")

    if accepted:
        record = registry.register(
            source_checkpoint_hash=SOURCE,
            declaration=declaration,
            expected_previous_record_hash=GENESIS,
        )
        assert record["declaration"] == declaration
        assert len(registry.read()) == 1
    else:
        with pytest.raises(
            ObserverRegistryError,
            match="declaration.*limit",
        ):
            registry.register(
                source_checkpoint_hash=SOURCE,
                declaration=declaration,
                expected_previous_record_hash=GENESIS,
            )
        assert registry.read() == []


def test_oversized_historical_record_rejected(tmp_path):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")

    registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="observer A",
        expected_previous_record_hash=GENESIS,
    )

    record = registry.read()[0]
    record["declaration"] = "A" * 65537

    body = {
        key: value
        for key, value in record.items()
        if key != "record_hash"
    }
    record["record_hash"] = stable_hash(body)

    with pytest.raises(
        ObserverRegistryError,
        match="declaration.*limit",
    ):
        verify_records([{"content": canonical_json(record)}])


def test_concurrent_registration_loser_is_stale(tmp_path):
    registry = ObserverRegistry(tmp_path / "observers.jsonl")

    def attempt(declaration):
        try:
            return registry.register(
                source_checkpoint_hash=SOURCE,
                declaration=declaration,
                expected_previous_record_hash=GENESIS,
            )
        except ObserverRegistryError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ["observer A", "observer B"]))

    successes = [r for r in results if isinstance(r, dict)]
    failures = [r for r in results if isinstance(r, ObserverRegistryError)]

    assert len(successes) == 1
    assert len(failures) == 1
    assert "stale registry head" in str(failures[0])

    records = registry.read()
    assert len(records) == 1
    assert records[0]["record_hash"] == successes[0]["record_hash"]


def test_cross_process_registration_contention(tmp_path):
    path = tmp_path / "observers.jsonl"
    start = tmp_path / "start.signal"

    worker = """
import sys
import time
from pathlib import Path
from holosim.observer_registry import ObserverRegistry, ObserverRegistryError

path = Path(sys.argv[1])
start = Path(sys.argv[2])
declaration = sys.argv[3]

Path(sys.argv[4]).touch()
print("READY", flush=True)

deadline = time.monotonic() + 10
while not start.exists():
    if time.monotonic() > deadline:
        raise TimeoutError("start signal timeout")
    time.sleep(0.001)

try:
    record = ObserverRegistry(path).register(
        source_checkpoint_hash="a" * 64,
        declaration=declaration,
        expected_previous_record_hash="0" * 64,
    )
    print("SUCCESS:" + record["observer_id"])
except ObserverRegistryError as exc:
    print("REJECTED:" + str(exc))
"""

    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                worker,
                str(path),
                str(start),
                f"process-{i}",
                str(tmp_path / f"ready-{i}"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(2)
    ]

    try:
        # Each worker creates its own readiness receipt.
        deadline = time.monotonic() + 10
        while not all(
            (tmp_path / f"ready-{i}").exists()
            for i in range(2)
        ):
            if time.monotonic() > deadline:
                raise TimeoutError("workers did not become ready")
            time.sleep(0.001)

        start.touch()

        outputs = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, stderr
            assert "READY" in stdout
            outputs.append(stdout)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate()

    assert sum("SUCCESS:AI-000001" in x for x in outputs) == 1
    assert sum("REJECTED:stale registry head" in x for x in outputs) == 1

    records = ObserverRegistry(path).read()
    assert len(records) == 1



@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("sequence_gap", "succession"),
        ("wrong_predecessor", "succession"),
        ("oversized_declaration", "declaration.*limit"),
    ],
)
def test_rehashed_disk_chain_rejected(tmp_path, mutation, expected):
    path = tmp_path / "observers.jsonl"
    registry = ObserverRegistry(path)

    first = registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="observer A",
        expected_previous_record_hash=GENESIS,
    )
    registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="observer B",
        expected_previous_record_hash=first["record_hash"],
    )

    entries = registry.chain.load_and_verify()
    record = json.loads(entries[1]["content"])

    if mutation == "sequence_gap":
        record["sequence"] = 3
        record["observer_id"] = "AI-000003"
    elif mutation == "wrong_predecessor":
        record["previous_record_hash"] = "f" * 64
    else:
        record["declaration"] = "A" * 65537

    body = {
        key: value
        for key, value in record.items()
        if key != "record_hash"
    }
    record["record_hash"] = stable_hash(body)

    entries[1]["content"] = canonical_json(record)
    entries[1]["hash"] = registry.chain._compute_hash(
        entries[0]["hash"],
        entries[1]["content"],
        entries[1]["timestamp"],
        entries[1]["idx"],
    )

    path.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries),
        encoding="utf-8",
    )

    # The enclosing chain hashes are internally consistent.
    assert len(registry.chain.load_and_verify()) == 2

    # Observer-specific rules must still reject the altered record.
    with pytest.raises(ObserverRegistryError, match=expected):
        registry.read()



@pytest.mark.parametrize("mutation", ["duplicate_key", "reformatted"])
def test_noncanonical_disk_record_rejected(tmp_path, mutation):
    path = tmp_path / "observers.jsonl"
    registry = ObserverRegistry(path)

    registry.register(
        source_checkpoint_hash=SOURCE,
        declaration="observer A",
        expected_previous_record_hash=GENESIS,
    )

    entries = registry.chain.load_and_verify()
    record = json.loads(entries[0]["content"])

    if mutation == "duplicate_key":
        content = (
            '{"sequence":999,'
            + canonical_json(record)[1:]
        )
    else:
        content = json.dumps(record, indent=2)

    entries[0]["content"] = content
    entries[0]["hash"] = registry.chain._compute_hash(
        GENESIS,
        content,
        entries[0]["timestamp"],
        entries[0]["idx"],
    )

    path.write_text(
        json.dumps(entries[0]) + "\n",
        encoding="utf-8",
    )

    assert len(registry.chain.load_and_verify()) == 1

    with pytest.raises(
        ObserverRegistryError,
        match="noncanonical",
    ):
        registry.read()
