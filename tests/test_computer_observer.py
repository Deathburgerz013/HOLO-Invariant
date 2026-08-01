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