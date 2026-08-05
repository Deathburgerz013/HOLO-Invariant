from __future__ import annotations

import json

import pytest

from holosim.local_ollama_adapter import LocalOllamaAdapterError
from holosim.local_ollama_capability_proposer import (
    build_local_ollama_capability_proposer,
)


def test_proposer_binds_task_state_constraints_and_feedback():
    observed = {}

    def requester(prompt, **kwargs):
        observed["prompt"] = json.loads(prompt)
        observed["kwargs"] = kwargs
        return {
            "output": {
                "files": {
                    "calculator.py": (
                        "def add(left, right):\n"
                        "    return left + right\n"
                    )
                },
                "reason": "Add the requested bounded capability",
            },
            "accepted": False,
        }

    proposer = build_local_ollama_capability_proposer(
        requester=requester,
        timeout_seconds=9,
    )

    result = proposer(
        {
            "id": "calculator.add",
            "requirement": "provide integer addition",
        },
        {
            "files": {},
            "workspace_hash": "abc123",
        },
        {
            "python_version": "3.13",
        },
        {
            "message": "Previous implementation was missing",
        },
    )

    prompt = observed["prompt"]

    assert prompt["task"] == "propose_software_capability_changes"
    assert prompt["capability_task"]["id"] == "calculator.add"
    assert prompt["observed_starting_state"]["workspace_hash"] == "abc123"
    assert prompt["environmental_constraints"]["python_version"] == "3.13"
    assert prompt["prior_feedback"]["message"] == (
        "Previous implementation was missing"
    )
    assert observed["kwargs"]["timeout_seconds"] == 9

    assert result["files"] == {
        "calculator.py": (
            "def add(left, right):\n"
            "    return left + right\n"
        )
    }
    assert result["reason"] == "Add the requested bounded capability"
    assert result["model_generated"] is True
    assert result["verified"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_proposer_records_last_transport_receipt():
    receipt = {
        "output": {
            "files": {
                "module.py": "VALUE = 1\n",
            },
            "reason": "Create one module",
        },
        "model": "test-model",
    }

    proposer = build_local_ollama_capability_proposer(
        requester=lambda prompt, **kwargs: receipt,
    )

    proposer(
        "task",
        {"files": {}, "workspace_hash": "abc"},
        {},
        None,
    )

    assert proposer.last_receipt == receipt
    assert proposer.last_receipt is not receipt


@pytest.mark.parametrize(
    "output",
    [
        {},
        {
            "files": {},
            "reason": "nothing",
        },
        {
            "files": [],
            "reason": "wrong type",
        },
        {
            "files": {
                "module.py": 1,
            },
            "reason": "content is not text",
        },
        {
            "files": {
                "": "content",
            },
            "reason": "path is empty",
        },
        {
            "files": {
                "module.py": "content",
            },
            "reason": "",
        },
    ],
)
def test_proposer_rejects_malformed_model_output(output):
    proposer = build_local_ollama_capability_proposer(
        requester=lambda prompt, **kwargs: {
            "output": output,
        },
    )

    with pytest.raises(LocalOllamaAdapterError):
        proposer(
            "task",
            {"files": {}, "workspace_hash": "abc"},
            {},
            None,
        )


def test_proposer_rejects_too_many_files():
    proposer = build_local_ollama_capability_proposer(
        max_files=1,
        requester=lambda prompt, **kwargs: {
            "output": {
                "files": {
                    "a.py": "a = 1\n",
                    "b.py": "b = 1\n",
                },
                "reason": "Two files",
            },
        },
    )

    with pytest.raises(
        LocalOllamaAdapterError,
        match="exceeds max_files",
    ):
        proposer(
            "task",
            {"files": {}, "workspace_hash": "abc"},
            {},
            None,
        )


def test_proposer_rejects_total_content_over_byte_limit():
    proposer = build_local_ollama_capability_proposer(
        max_content_bytes=3,
        requester=lambda prompt, **kwargs: {
            "output": {
                "files": {
                    "module.py": "four",
                },
                "reason": "Too large",
            },
        },
    )

    with pytest.raises(
        LocalOllamaAdapterError,
        match="exceeds max_content_bytes",
    ):
        proposer(
            "task",
            {"files": {}, "workspace_hash": "abc"},
            {},
            None,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_files": 0}, "max_files must be a positive integer"),
        (
            {"max_content_bytes": 0},
            "max_content_bytes must be a positive integer",
        ),
    ],
)
def test_proposer_rejects_nonpositive_bounds(kwargs, message):
    with pytest.raises(LocalOllamaAdapterError, match=message):
        build_local_ollama_capability_proposer(**kwargs)


def test_proposer_rejects_invalid_call_mappings():
    proposer = build_local_ollama_capability_proposer(
        requester=lambda prompt, **kwargs: {
            "output": {
                "files": {
                    "module.py": "VALUE = 1\n",
                },
                "reason": "Create module",
            },
        },
    )

    with pytest.raises(
        LocalOllamaAdapterError,
        match="observed_starting_state must be a mapping",
    ):
        proposer("task", [], {}, None)

    with pytest.raises(
        LocalOllamaAdapterError,
        match="environmental_constraints must be a mapping",
    ):
        proposer(
            "task",
            {"files": {}, "workspace_hash": "abc"},
            [],
            None,
        )