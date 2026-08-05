from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from holosim import holo_cli


def test_local_converge_prints_receipt_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        software_request,
        workspace,
        *,
        model,
        endpoint,
        max_cycles,
        max_builder_attempts,
    ):
        captured.update(
            {
                "software_request": software_request,
                "workspace": workspace,
                "model": model,
                "endpoint": endpoint,
                "max_cycles": max_cycles,
                "max_builder_attempts": max_builder_attempts,
            }
        )
        return {
            "status": "CONVERGED",
            "converged": True,
            "runnable": True,
            "terminal_reason": "PROJECT_VERIFIED_RUNNABLE",
        }

    monkeypatch.setattr(
        holo_cli,
        "run_local_ollama_software_convergence",
        fake_run,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "holosim",
            "local-converge",
            "build a calculator",
            str(tmp_path),
            "--model",
            "qwen-test",
            "--endpoint",
            "http://127.0.0.1:11434/api/generate",
            "--max-cycles",
            "4",
            "--max-builder-attempts",
            "5",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        holo_cli.main()

    assert exc_info.value.code == 0

    output = json.loads(capsys.readouterr().out)

    assert output["converged"] is True
    assert output["runnable"] is True
    assert captured == {
        "software_request": "build a calculator",
        "workspace": tmp_path,
        "model": "qwen-test",
        "endpoint": "http://127.0.0.1:11434/api/generate",
        "max_cycles": 4,
        "max_builder_attempts": 5,
    }


def test_local_converge_exits_one_when_not_runnable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def fake_run(*args, **kwargs):
        return {
            "status": "STOPPED",
            "converged": False,
            "runnable": False,
            "terminal_reason": "PROJECT_NOT_RUNNABLE",
        }

    monkeypatch.setattr(
        holo_cli,
        "run_local_ollama_software_convergence",
        fake_run,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "holosim",
            "local-converge",
            "build a calculator",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        holo_cli.main()

    assert exc_info.value.code == 1

    output = json.loads(capsys.readouterr().out)

    assert output["converged"] is False
    assert output["runnable"] is False