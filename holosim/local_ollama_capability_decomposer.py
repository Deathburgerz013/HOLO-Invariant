"""Local Ollama capability decomposition for software convergence.

The model proposes a bounded capability sequence.  The existing software
capability planner remains responsible for validating dependency order.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable, Mapping, Sequence

from holosim.local_ollama_adapter import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    LocalOllamaAdapterError,
    request_local_ollama_json,
)


_TASK = "decompose_software_request"
_SCHEMA = {
    "capabilities": [
        {
            "id": "unique.nonempty.string",
            "requirement": "one bounded observable requirement",
            "depends_on": ["earlier.capability.id"],
        }
    ]
}


class LocalOllamaCapabilityDecomposer:
    """Callable planner dependency backed by one bounded Ollama transport."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = 120.0,
        requester: Callable[..., Mapping[str, Any]] = (
            request_local_ollama_json
        ),
    ) -> None:
        if not callable(requester):
            raise TypeError("requester must be callable")
        self._model = model
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._requester = requester
        self.last_receipt: dict[str, Any] | None = None

    def __call__(
        self,
        software_request: Any,
        environmental_constraints: Mapping[str, Any],
    ) -> Sequence[Mapping[str, Any]]:
        if not isinstance(environmental_constraints, Mapping):
            raise LocalOllamaAdapterError(
                "environmental_constraints must be a mapping"
            )

        prompt_body = {
            "task": _TASK,
            "instruction": (
                "Return only the JSON object matching output_schema. "
                "Capabilities must be smallest-first and dependency ordered. "
                "Each depends_on id must appear earlier. Do not claim that "
                "any capability is implemented, verified, or accepted."
            ),
            "software_request": deepcopy(software_request),
            "environmental_constraints": deepcopy(
                dict(environmental_constraints)
            ),
            "output_schema": deepcopy(_SCHEMA),
        }
        prompt = json.dumps(
            prompt_body,
            sort_keys=True,
            separators=(",", ":"),
        )
        receipt = self._requester(
            prompt,
            model=self._model,
            endpoint=self._endpoint,
            timeout_seconds=self._timeout_seconds,
        )
        if not isinstance(receipt, Mapping):
            raise LocalOllamaAdapterError(
                "local Ollama requester must return a mapping"
            )
        output = receipt.get("output")
        if not isinstance(output, Mapping):
            raise LocalOllamaAdapterError(
                "local Ollama receipt output must be a mapping"
            )
        capabilities = output.get("capabilities")
        if (
            not isinstance(capabilities, list)
            or not capabilities
            or not all(
                isinstance(capability, Mapping)
                for capability in capabilities
            )
        ):
            raise LocalOllamaAdapterError(
                "local Ollama output must contain non-empty capabilities"
            )

        copied: list[dict[str, Any]] = []

        for capability in capabilities:
            copied_capability = deepcopy(dict(capability))
            copied_capability.setdefault("depends_on", [])
            copied.append(copied_capability)
        self.last_receipt = deepcopy(dict(receipt))
        return copied


def build_local_ollama_capability_decomposer(
    *,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout_seconds: float = 120.0,
    requester: Callable[..., Mapping[str, Any]] = request_local_ollama_json,
) -> LocalOllamaCapabilityDecomposer:
    """Build one injectable decomposer without granting model authority."""
    return LocalOllamaCapabilityDecomposer(
        model=model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        requester=requester,
    )
