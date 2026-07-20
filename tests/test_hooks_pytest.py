from __future__ import annotations

import copy

import pytest

from holosim.hook_contract import HookContractError, build_hook_request, validate_hook_result
from holosim.hooks_pytest import run_pytest_hook


def _request(targets):
    return build_hook_request(
        hook_id="pytest",
        action="run_targets",
        reference="bounded pytest evidence",
        payload={"targets": targets},
    )


def test_pytest_hook_observes_passing_target(tmp_path):
    test_file = tmp_path / "test_pass.py"
    test_file.write_text("def test_ok():\n    assert 2 + 2 == 4\n", encoding="utf-8")
    request = _request([str(test_file)])

    result = run_pytest_hook(request, cwd=tmp_path)

    assert result["status"] == "OBSERVED"
    assert result["evidence"]["exit_code"] == 0
    assert result["evidence"]["timed_out"] is False
    assert validate_hook_result(result, request=request)


def test_pytest_hook_preserves_failing_test_as_failed_evidence(tmp_path):
    test_file = tmp_path / "test_fail.py"
    test_file.write_text("def test_no():\n    assert False\n", encoding="utf-8")
    request = _request([str(test_file)])

    result = run_pytest_hook(request, cwd=tmp_path)

    assert result["status"] == "FAILED"
    assert result["evidence"]["exit_code"] != 0
    assert "FAILED" in result["evidence"]["stdout"]
    assert validate_hook_result(result, request=request)


def test_pytest_hook_rejects_wrong_hook_id():
    request = build_hook_request(
        hook_id="other",
        action="run_targets",
        reference="x",
        payload={"targets": ["tests"]},
    )
    with pytest.raises(HookContractError):
        run_pytest_hook(request)


def test_pytest_hook_rejects_wrong_action():
    request = build_hook_request(
        hook_id="pytest",
        action="shell",
        reference="x",
        payload={"targets": ["tests"]},
    )
    with pytest.raises(HookContractError):
        run_pytest_hook(request)


def test_pytest_hook_rejects_options_as_targets():
    with pytest.raises(HookContractError):
        run_pytest_hook(_request(["--collect-only"]))


def test_pytest_hook_rejects_extra_payload_fields():
    request = build_hook_request(
        hook_id="pytest",
        action="run_targets",
        reference="x",
        payload={"targets": ["tests"], "args": ["--pdb"]},
    )
    with pytest.raises(HookContractError):
        run_pytest_hook(request)


def test_pytest_hook_rejects_empty_targets():
    with pytest.raises(HookContractError):
        run_pytest_hook(_request([]))


def test_pytest_hook_rejects_excessive_timeout():
    with pytest.raises(HookContractError):
        run_pytest_hook(_request(["tests"]), timeout_seconds=601)


def test_pytest_hook_result_is_bound_to_exact_request(tmp_path):
    test_file = tmp_path / "test_pass.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    request = _request([str(test_file)])
    result = run_pytest_hook(request, cwd=tmp_path)
    other = _request(["tests/test_hook_contract.py"])

    with pytest.raises(HookContractError):
        validate_hook_result(result, request=other)


def test_pytest_hook_does_not_grant_authority(tmp_path):
    test_file = tmp_path / "test_pass.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    result = run_pytest_hook(_request([str(test_file)]), cwd=tmp_path)

    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["mutation_applied"] is False
