import errno
import sys
from types import SimpleNamespace

import pytest

import holosim.core as core
from holosim.core import HoloChain


def install_windows_lock(monkeypatch, outcomes):
    calls = []
    waits = []
    clock = [0.0]

    def locking(fd, mode, count):
        calls.append((mode, count))
        result = outcomes.pop(0) if outcomes else None
        if result is not None:
            raise result

    def sleep(seconds):
        waits.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(core.platform, "system", lambda: "Windows")
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0, locking=locking))
    monkeypatch.setattr(core.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(core.time, "sleep", sleep)
    return calls, waits


@pytest.mark.parametrize("code", [errno.EACCES, errno.EAGAIN, errno.EDEADLK])
def test_windows_contention_yields_then_acquires(monkeypatch, tmp_path, code):
    calls, waits = install_windows_lock(monkeypatch, [OSError(code, "busy"), None])
    chain = HoloChain(tmp_path / "chain.jsonl")
    entry = chain.append("after contention")
    assert calls == [(2, 1), (2, 1), (0, 1)]
    assert waits == [core.WINDOWS_APPEND_LOCK_RETRY_SECONDS]
    assert chain.load_and_verify() == [entry]
    assert chain.file_path.with_name("chain.jsonl.lock").read_bytes() == b""


def test_windows_timeout_never_reads_writes_or_unlocks(monkeypatch, tmp_path):
    calls, waits = install_windows_lock(monkeypatch, [None])
    monkeypatch.setattr(core, "WINDOWS_APPEND_LOCK_TIMEOUT_SECONDS", 0.025)
    chain = HoloChain(tmp_path / "chain.jsonl")
    chain.append("original")
    before = chain.file_path.read_bytes()
    calls.clear()
    waits.clear()
    # Start a fresh contention clock for the denied transaction.
    calls, waits = install_windows_lock(monkeypatch, [OSError(errno.EACCES, "busy")] * 10)
    monkeypatch.setattr(chain, "load_and_verify", lambda: pytest.fail("read before lock"))
    with pytest.raises(TimeoutError, match="Windows append lock timed out"):
        chain.append("blocked")
    assert chain.file_path.read_bytes() == before
    assert all(mode == 2 for mode, count in calls)
    assert sum(waits) == pytest.approx(0.025)


def test_windows_unexpected_error_is_not_retried(monkeypatch, tmp_path):
    calls, waits = install_windows_lock(monkeypatch, [OSError(errno.EBADF, "bad descriptor")])
    chain = HoloChain(tmp_path / "chain.jsonl")
    with pytest.raises(OSError) as caught:
        chain.append("blocked")
    assert caught.value.errno == errno.EBADF
    assert calls == [(2, 1)] and waits == []
    assert not chain.file_path.exists()


def test_windows_unlocks_acquired_lock_after_verification_failure(monkeypatch, tmp_path):
    calls, waits = install_windows_lock(monkeypatch, [None])
    chain = HoloChain(tmp_path / "chain.jsonl")
    def reject():
        raise ValueError("invalid chain")
    monkeypatch.setattr(chain, "load_and_verify", reject)
    with pytest.raises(ValueError, match="invalid chain"):
        chain.append("blocked")
    assert calls == [(2, 1), (0, 1)]
    assert not chain.file_path.exists()
