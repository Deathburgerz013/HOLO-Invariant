"""Bounded JSON transport for a local Ollama model.

The adapter is transport only.  It does not accept claims, grant write or
execution authority, or decide whether generated software is correct.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_MODEL = "qwen2.5-coder:7b-instruct-q3_K_S"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434/api/generate"
RECEIPT_TYPE = "local_ollama_json_receipt"
RECEIPT_VERSION = 1


class LocalOllamaAdapterError(ValueError):
    """Raised when a bounded local-model request cannot be verified."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocalOllamaAdapterError(f"{field} must be a non-empty string")
    return value.strip()


def _loopback_endpoint(value: Any) -> str:
    endpoint = _required_text(value, "endpoint")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "http":
        raise LocalOllamaAdapterError("endpoint must use http")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise LocalOllamaAdapterError("endpoint must be loopback-only")
    if parsed.path != "/api/generate" or parsed.query or parsed.fragment:
        raise LocalOllamaAdapterError(
            "endpoint must target the local /api/generate route"
        )
    return endpoint


def request_local_ollama_json(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout_seconds: float = 120.0,
    context: Mapping[str, Any] | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Request one JSON object while explicitly disabling GPU offload."""
    clean_prompt = _required_text(prompt, "prompt")
    clean_model = _required_text(model, "model")
    clean_endpoint = _loopback_endpoint(endpoint)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds <= 0
    ):
        raise LocalOllamaAdapterError("timeout_seconds must be positive")
    if context is not None and not isinstance(context, Mapping):
        raise LocalOllamaAdapterError("context must be a mapping")

    request_body = {
        "model": clean_model,
        "prompt": clean_prompt,
        "stream": False,
        "format": "json",
        "options": {"num_gpu": 0},
    }
    if context:
        request_body["context"] = deepcopy(dict(context))

    request = Request(
        clean_endpoint,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=float(timeout_seconds)) as response:
            raw_response = response.read()
    except (HTTPError, URLError, OSError) as exc:
        raise LocalOllamaAdapterError(
            f"local Ollama request failed: {exc}"
        ) from exc

    try:
        envelope = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocalOllamaAdapterError(
            "local Ollama returned an invalid JSON envelope"
        ) from exc
    if not isinstance(envelope, dict):
        raise LocalOllamaAdapterError("local Ollama envelope must be an object")
    if envelope.get("done") is not True:
        raise LocalOllamaAdapterError("local Ollama response is incomplete")

    response_text = envelope.get("response")
    if not isinstance(response_text, str):
        raise LocalOllamaAdapterError(
            "local Ollama response field must be a string"
        )
    try:
        output = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise LocalOllamaAdapterError(
            "local Ollama response is not valid JSON"
        ) from exc
    if not isinstance(output, dict):
        raise LocalOllamaAdapterError(
            "local Ollama response must decode to an object"
        )

    return {
        "receipt_type": RECEIPT_TYPE,
        "receipt_version": RECEIPT_VERSION,
        "model": clean_model,
        "endpoint": clean_endpoint,
        "output": deepcopy(output),
        "done_reason": envelope.get("done_reason"),
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
