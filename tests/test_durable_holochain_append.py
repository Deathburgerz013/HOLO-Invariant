import json
import os

import pytest

from holosim.core import HoloChain


def test_append_fsyncs_written_entry_before_reporting_success(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)
    observed_hashes = []

    def observe_fsync(file_descriptor):
        assert os.fstat(file_descriptor).st_size > 0
        stored = json.loads(path.read_text(encoding="utf-8"))
        observed_hashes.append(stored["hash"])

    monkeypatch.setattr(os, "fsync", observe_fsync)

    entry = chain.append("durable")

    assert observed_hashes == [entry["hash"]]
    assert chain.load_and_verify() == [entry]


def test_append_does_not_report_success_when_fsync_fails(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)
    releases = []
    original_release = chain._release_lock

    def fail_fsync(file_descriptor):
        raise OSError("durability unavailable")

    def record_release(lock_file):
        releases.append("release")
        original_release(lock_file)

    monkeypatch.setattr(os, "fsync", fail_fsync)
    monkeypatch.setattr(chain, "_release_lock", record_release)

    with pytest.raises(OSError, match="durability unavailable"):
        chain.append("not acknowledged")

    assert releases == ["release"]
