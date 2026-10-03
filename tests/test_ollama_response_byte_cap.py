"""Bounded transport checks; no live model or memory-exhaustion experiment."""
import io
import json

import pytest

from holosim import local_ollama_adapter as adapter


class Response(io.BytesIO):
    def __init__(self, raw):
        super().__init__(raw)
        self.requests = []

    def read(self, size=-1):
        assert size >= 0, "unbounded read"
        self.requests.append(size)
        return super().read(size)


def payload(size):
    raw = json.dumps({"done": True, "response": "{}"}).encode()
    return raw + b" " * (size - len(raw))


@pytest.mark.parametrize("extra", [-1, 0, 1, 20])
def test_boundary_before_parse(monkeypatch, extra):
    limit = 128
    monkeypatch.setattr(adapter, "MAX_RESPONSE_BYTES", limit)
    response = Response(payload(limit + extra))
    loads = adapter.json.loads
    parses = []

    def tracked_loads(raw):
        parses.append(raw)
        return loads(raw)

    monkeypatch.setattr(adapter.json, "loads", tracked_loads)
    if extra > 0:
        with pytest.raises(adapter.LocalOllamaAdapterError, match="exceeds byte limit"):
            adapter.request_local_ollama_json("test", opener=lambda *a, **k: response)
        assert parses == []
    else:
        receipt = adapter.request_local_ollama_json("test", opener=lambda *a, **k: response)
        assert receipt["output"] == {}
        assert receipt["accepted"] is False
        assert receipt["write_authority"] == receipt["execution_authority"] == "NONE"
        assert len(parses) == 2
    assert response.requests == [limit + 1]
    assert response.closed


def test_production_cap_is_requested():
    assert adapter.MAX_RESPONSE_BYTES == 1_048_576
    response = Response(payload(64))
    adapter.request_local_ollama_json("test", opener=lambda *a, **k: response)
    assert response.requests == [1_048_577]


def test_small_invalid_json_retains_error_contract():
    response = Response(b"not json")
    with pytest.raises(adapter.LocalOllamaAdapterError, match="invalid JSON envelope"):
        adapter.request_local_ollama_json("test", opener=lambda *a, **k: response)
    assert response.closed


def test_read_failure_retains_error_contract():
    class Broken(Response):
        def read(self, size=-1):
            assert size == adapter.MAX_RESPONSE_BYTES + 1
            raise OSError("read failed")
    response = Broken(b"")
    with pytest.raises(adapter.LocalOllamaAdapterError, match="request failed"):
        adapter.request_local_ollama_json("test", opener=lambda *a, **k: response)
    assert response.closed
