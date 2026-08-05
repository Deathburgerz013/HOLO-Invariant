from __future__ import annotations

import json
from urllib.error import URLError

import pytest

from holosim.local_ollama_adapter import (
    LocalOllamaAdapterError,
    request_local_ollama_json,
)


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_request_forces_cpu_and_returns_bounded_json_receipt():
    observed = {}

    def opener(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        observed["body"] = json.loads(request.data.decode("utf-8"))
        return _Response(
            {
                "response": json.dumps({"capabilities": []}),
                "done": True,
                "done_reason": "stop",
            }
        )

    result = request_local_ollama_json(
        "Return a capability plan.",
        timeout_seconds=7,
        opener=opener,
    )

    assert observed == {
        "url": "http://127.0.0.1:11434/api/generate",
        "timeout": 7.0,
        "body": {
            "model": "qwen2.5-coder:7b-instruct-q3_K_S",
            "prompt": "Return a capability plan.",
            "stream": False,
            "format": "json",
            "options": {"num_gpu": 0},
        },
    }
    assert result["output"] == {"capabilities": []}
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:11434/api/generate",
        "http://example.com/api/generate",
        "http://127.0.0.1:11434/api/chat",
    ],
)
def test_request_rejects_nonlocal_or_unexpected_endpoints(endpoint):
    with pytest.raises(LocalOllamaAdapterError):
        request_local_ollama_json(
            "prompt",
            endpoint=endpoint,
            opener=lambda *_args, **_kwargs: None,
        )


def test_request_rejects_incomplete_response():
    def opener(request, timeout):
        return _Response({"response": "{}", "done": False})

    with pytest.raises(LocalOllamaAdapterError, match="incomplete"):
        request_local_ollama_json("prompt", opener=opener)


def test_request_rejects_non_json_model_output():
    def opener(request, timeout):
        return _Response({"response": "not json", "done": True})

    with pytest.raises(LocalOllamaAdapterError, match="not valid JSON"):
        request_local_ollama_json("prompt", opener=opener)


def test_request_reports_connection_failure_without_authority():
    def opener(request, timeout):
        raise URLError("offline")

    with pytest.raises(LocalOllamaAdapterError, match="request failed"):
        request_local_ollama_json("prompt", opener=opener)
