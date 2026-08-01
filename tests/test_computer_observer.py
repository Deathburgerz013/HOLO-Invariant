from __future__ import annotations

import hashlib

import pytest

from holosim.computer_observer import (
    ComputerObserverError,
    execute_observation,
)
from holosim.hook_contract import (
    build_hook_request,
    validate_hook_result,
)


def _request(reference: str = "state.txt") -> dict[str, object]:
    return build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference=reference,
        payload={"encoding": "utf-8"},
    )


def _list_request(
    reference: str = ".",
    max_entries: int = 100,
) -> dict[str, object]:
    return build_hook_request(
        hook_id="local-computer",
        action="list_directory",
        reference=reference,
        payload={"max_entries": max_entries},
    )


def test_read_text_executes_inside_allowed_root_and_binds_evidence(tmp_path):
    content = "observed state\n"
    (tmp_path / "state.txt").write_bytes(content.encode("utf-8"))
    request = _request()

    result = execute_observation(request=request, allowed_root=tmp_path)

    assert result["status"] == "OBSERVED"
    assert result["evidence"] == {
        "operation": "read_text",
        "reference": "state.txt",
        "encoding": "utf-8",
        "content": content,
        "byte_count": len(content.encode("utf-8")),
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }
    assert result["mutation_applied"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert validate_hook_result(result, request=request) is True


def test_reference_cannot_escape_allowed_root(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("must not be observed", encoding="utf-8")

    with pytest.raises(ComputerObserverError, match="allowed root"):
        execute_observation(
            request=_request("../outside.txt"),
            allowed_root=tmp_path,
        )


def test_symlink_cannot_escape_allowed_root(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("must not be observed", encoding="utf-8")
    link = tmp_path / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable in this environment")

    with pytest.raises(ComputerObserverError, match="allowed root"):
        execute_observation(
            request=_request("linked.txt"),
            allowed_root=tmp_path,
        )


def test_executor_rejects_undeclared_actions_without_running_them(tmp_path):
    request = build_hook_request(
        hook_id="local-computer",
        action="run_command",
        reference="echo unsafe",
        payload={},
    )

    with pytest.raises(ComputerObserverError, match="not allowed"):
        execute_observation(request=request, allowed_root=tmp_path)


def test_list_directory_observes_sorted_nonrecursive_entries(tmp_path):
    (tmp_path / "zeta.txt").write_bytes(b"z")
    (tmp_path / "alpha.txt").write_bytes(b"a")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "hidden-from-result.txt").write_bytes(b"nested")
    request = _list_request()

    result = execute_observation(request=request, allowed_root=tmp_path)

    assert result["status"] == "OBSERVED"
    assert result["evidence"] == {
        "operation": "list_directory",
        "reference": ".",
        "entries": [
            {"name": "alpha.txt", "kind": "file"},
            {"name": "nested", "kind": "directory"},
            {"name": "zeta.txt", "kind": "file"},
        ],
        "entry_count": 3,
        "truncated": False,
    }
    assert result["mutation_applied"] is False
    assert validate_hook_result(result, request=request) is True


def test_list_directory_reports_bounded_truncation(tmp_path):
    for name in ["c.txt", "a.txt", "b.txt"]:
        (tmp_path / name).write_bytes(name.encode("utf-8"))

    result = execute_observation(
        request=_list_request(max_entries=2),
        allowed_root=tmp_path,
    )

    assert result["evidence"]["entries"] == [
        {"name": "a.txt", "kind": "file"},
        {"name": "b.txt", "kind": "file"},
    ]
    assert result["evidence"]["entry_count"] == 3
    assert result["evidence"]["truncated"] is True
