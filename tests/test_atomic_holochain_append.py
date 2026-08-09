from concurrent.futures import ThreadPoolExecutor

import pytest

from holosim.core import HoloChain


def test_append_acquires_lock_before_reading_current_head(
    tmp_path,
    monkeypatch,
):
    chain = HoloChain(tmp_path / "chain.jsonl")
    events = []
    original_load = chain.load_and_verify

    def acquire(lock_file):
        events.append("acquire")

    def release(lock_file):
        events.append("release")

    def guarded_load():
        assert events == ["acquire"]
        events.append("read")
        return original_load()

    monkeypatch.setattr(chain, "_acquire_lock", acquire)
    monkeypatch.setattr(chain, "_release_lock", release)
    monkeypatch.setattr(chain, "load_and_verify", guarded_load)

    chain.append("alpha")

    assert events == ["acquire", "read", "release"]


def test_append_releases_lock_when_verification_fails(
    tmp_path,
    monkeypatch,
):
    chain = HoloChain(tmp_path / "chain.jsonl")
    events = []

    monkeypatch.setattr(
        chain,
        "_acquire_lock",
        lambda lock_file: events.append("acquire"),
    )
    monkeypatch.setattr(
        chain,
        "_release_lock",
        lambda lock_file: events.append("release"),
    )

    def fail_verification():
        raise ValueError("invalid existing chain")

    monkeypatch.setattr(chain, "load_and_verify", fail_verification)

    with pytest.raises(ValueError, match="invalid existing chain"):
        chain.append("blocked")

    assert events == ["acquire", "release"]


def test_concurrent_appends_preserve_one_linear_chain(tmp_path):
    path = tmp_path / "chain.jsonl"
    workers = 8
    entries_per_worker = 12

    def append_batch(worker):
        chain = HoloChain(path)
        return [
            chain.append(f"worker-{worker}-entry-{index}")
            for index in range(entries_per_worker)
        ]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        batches = list(executor.map(append_batch, range(workers)))

    entries = HoloChain(path).load_and_verify()
    expected_count = workers * entries_per_worker

    assert len(entries) == expected_count
    assert [entry["idx"] for entry in entries] == list(
        range(1, expected_count + 1)
    )
    assert {entry["content"] for entry in entries} == {
        f"worker-{worker}-entry-{index}"
        for worker in range(workers)
        for index in range(entries_per_worker)
    }
    assert sum(len(batch) for batch in batches) == expected_count


def test_lock_metadata_does_not_enter_chain_history(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)

    entry = chain.append("alpha")

    assert chain.load_and_verify() == [entry]
    assert path.with_name(path.name + ".lock").is_file()
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
