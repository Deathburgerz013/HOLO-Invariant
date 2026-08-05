from __future__ import annotations

import json

import pytest

from holosim.local_ollama_adapter import LocalOllamaAdapterError
from holosim.local_ollama_capability_comparator import (
    build_local_ollama_capability_comparator,
)


def test_comparator_binds_model_observation_to_sorted_workspace_snapshot(
    tmp_path,
):
    (tmp_path / "z.py").write_text("z = 1\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    observed = {}

    def requester(prompt, **kwargs):
        observed["prompt"] = json.loads(prompt)
        observed["kwargs"] = kwargs
        return {
            "output": {
                "relevant_difference": True,
                "reason": "calculator.add is missing",
                "observations": ["No calculator module is present"],
            },
            "accepted": False,
        }

    comparator = build_local_ollama_capability_comparator(
        requester=requester,
        timeout_seconds=8,
    )
    result = comparator(
        {"id": "calculator.module", "requirement": "create add"},
        tmp_path,
    )

    snapshot = observed["prompt"]["workspace_snapshot"]
    assert [entry["path"] for entry in snapshot["files"]] == [
        "a.py",
        "z.py",
    ]
    assert snapshot["truncated"] is False
    assert all(len(entry["sha256"]) == 64 for entry in snapshot["files"])
    assert observed["kwargs"]["timeout_seconds"] == 8
    assert result["relevant_difference"] is True
    assert result["description"]["observations"] == [
        "No calculator module is present"
    ]
    assert result["verified"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_empty_workspace_is_a_difference_without_model_inference(tmp_path):
    def requester(prompt, **kwargs):
        raise AssertionError("empty workspace must not invoke the model")

    result = build_local_ollama_capability_comparator(
        requester=requester
    )({"id": "calculator.module"}, tmp_path)

    assert result["relevant_difference"] is True
    assert result["reason"] == "WORKSPACE_EMPTY"
    assert result["model_generated"] is False
    assert result["workspace_snapshot"]["file_count"] == 0
    assert result["verified"] is False
    assert result["accepted"] is False


def test_comparator_marks_bounded_snapshot_truncation(tmp_path):
    (tmp_path / "a.txt").write_text("1234", encoding="utf-8")
    (tmp_path / "b.txt").write_text("5678", encoding="utf-8")

    def requester(prompt, **kwargs):
        snapshot = json.loads(prompt)["workspace_snapshot"]
        assert snapshot["file_count"] == 1
        assert snapshot["truncated"] is True
        return {
            "output": {
                "relevant_difference": True,
                "reason": "bounded evidence is incomplete",
                "observations": [],
            }
        }

    comparator = build_local_ollama_capability_comparator(
        requester=requester,
        max_files=1,
    )
    result = comparator("goal", tmp_path)

    assert result["workspace_snapshot"]["truncated"] is True


def test_comparator_does_not_follow_workspace_symlinks(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")

    def requester(prompt, **kwargs):
        paths = [
            item["path"]
            for item in json.loads(prompt)["workspace_snapshot"]["files"]
        ]
        assert paths == ["target.txt"]
        return {
            "output": {
                "relevant_difference": False,
                "reason": "no relevant difference",
                "observations": [],
            }
        }

    result = build_local_ollama_capability_comparator(
        requester=requester
    )("goal", tmp_path)
    assert result["relevant_difference"] is False
    assert result["verified"] is False


@pytest.mark.parametrize(
    "output",
    [
        {},
        {
            "relevant_difference": "yes",
            "reason": "difference",
            "observations": [],
        },
        {
            "relevant_difference": True,
            "reason": "",
            "observations": [],
        },
        {
            "relevant_difference": True,
            "reason": "difference",
            "observations": [1],
        },
    ],
)
def test_comparator_rejects_malformed_model_decisions(tmp_path, output):
    (tmp_path / "state.txt").write_text("state", encoding="utf-8")
    comparator = build_local_ollama_capability_comparator(
        requester=lambda prompt, **kwargs: {"output": output}
    )

    with pytest.raises(LocalOllamaAdapterError):
        comparator("goal", tmp_path)


def test_comparator_rejects_nonpositive_snapshot_bounds():
    with pytest.raises(LocalOllamaAdapterError):
        build_local_ollama_capability_comparator(max_files=0)
