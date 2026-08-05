"""Bounded local Ollama proposals for one software capability.

The model may propose complete file contents. It receives no write or
execution authority. The existing software builder remains responsible for
bounded application and verification.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable, Mapping

from holosim.local_ollama_adapter import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    LocalOllamaAdapterError,
    request_local_ollama_json,
)


_TASK = "propose_software_capability_changes"
_SCHEMA = {
    "files": {
        "relative/path.py": "complete UTF-8 file content",
    },
    "reason": "bounded explanation of the proposed changes",
}


class LocalOllamaCapabilityProposer:
    """Propose bounded file contents without applying or executing them."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = 120.0,
        max_files: int = 16,
        max_content_bytes: int = 65_536,
        requester: Callable[..., Mapping[str, Any]] = (
            request_local_ollama_json
        ),
    ) -> None:
        if not callable(requester):
            raise TypeError("requester must be callable")

        if (
            not isinstance(max_files, int)
            or isinstance(max_files, bool)
            or max_files < 1
        ):
            raise LocalOllamaAdapterError(
                "max_files must be a positive integer"
            )

        if (
            not isinstance(max_content_bytes, int)
            or isinstance(max_content_bytes, bool)
            or max_content_bytes < 1
        ):
            raise LocalOllamaAdapterError(
                "max_content_bytes must be a positive integer"
            )

        self._model = model
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._max_files = max_files
        self._max_content_bytes = max_content_bytes
        self._requester = requester
        self.last_receipt: dict[str, Any] | None = None

    def __call__(
        self,
        task: Any,
        observed_starting_state: Mapping[str, Any],
        environmental_constraints: Mapping[str, Any],
        prior_feedback: Any,
    ) -> dict[str, Any]:
        if not isinstance(observed_starting_state, Mapping):
            raise LocalOllamaAdapterError(
                "observed_starting_state must be a mapping"
            )

        if not isinstance(environmental_constraints, Mapping):
            raise LocalOllamaAdapterError(
                "environmental_constraints must be a mapping"
            )

        prompt_body = {
            "task": _TASK,
            "instruction": (
                "Return only the JSON object matching output_schema. "
                "Propose complete UTF-8 contents for relative workspace paths. "
                "Do not use absolute paths, parent traversal, shell commands, "
                "or markdown fences. Respect prior verification feedback. "
                "Do not claim files were written, executed, verified, accepted, "
                "or proven correct."
            ),
            "capability_task": deepcopy(task),
            "observed_starting_state": deepcopy(
                dict(observed_starting_state)
            ),
            "environmental_constraints": deepcopy(
                dict(environmental_constraints)
            ),
            "prior_feedback": deepcopy(prior_feedback),
            "limits": {
                "max_files": self._max_files,
                "max_content_bytes": self._max_content_bytes,
            },
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

        files = output.get("files")
        reason = output.get("reason")

        if not isinstance(files, Mapping) or not files:
            raise LocalOllamaAdapterError(
                "local Ollama output must contain a non-empty files mapping"
            )

        if len(files) > self._max_files:
            raise LocalOllamaAdapterError(
                "local Ollama output exceeds max_files"
            )

        copied_files: dict[str, str] = {}
        total_content_bytes = 0

        for path, content in files.items():
            if not isinstance(path, str) or not path.strip():
                raise LocalOllamaAdapterError(
                    "proposed file paths must be non-empty strings"
                )

            if not isinstance(content, str):
                raise LocalOllamaAdapterError(
                    "proposed file contents must be strings"
                )

            normalized_path = path.strip()
            content_bytes = len(content.encode("utf-8"))
            total_content_bytes += content_bytes

            if total_content_bytes > self._max_content_bytes:
                raise LocalOllamaAdapterError(
                    "local Ollama output exceeds max_content_bytes"
                )

            copied_files[normalized_path] = content

        if not isinstance(reason, str) or not reason.strip():
            raise LocalOllamaAdapterError(
                "local Ollama output reason must be a non-empty string"
            )

        self.last_receipt = deepcopy(dict(receipt))

        return {
            "files": copied_files,
            "reason": reason.strip(),
            "model_generated": True,
            "verified": False,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }


def build_local_ollama_capability_proposer(
    **kwargs: Any,
) -> LocalOllamaCapabilityProposer:
    """Build one proposer injectable into the bounded software builder."""

    return LocalOllamaCapabilityProposer(**kwargs)