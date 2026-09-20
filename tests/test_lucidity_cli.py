import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from holosim.bounded_evidence_analyst import build_evidence_analysis_receipt
from holosim.holo_cli import main, run_lucidity_command


def build_analysis(relation: str = "CONTRADICTS") -> dict:
    return build_evidence_analysis_receipt(
        analysis_id="lucidity-cli-test",
        scope="offline replay",
        method={
            "method_id": "replay-check",
            "method_version": "1",
            "description": "compare replay finding with retained evidence",
        },
        evidence=[
            {
                "evidence_id": "e1",
                "content_sha256": "a" * 64,
                "source_reference": "replay:episode:1",
                "availability": "VERIFIED",
            }
        ],
        findings=[
            {
                "finding_id": "f1",
                "statement": "candidate behavior succeeds",
                "evidence_assessments": [
                    {
                        "evidence_id": "e1",
                        "disposition": "INCLUDED",
                        "relation": relation,
                        "rationale": "observed replay outcome differs",
                    }
                ],
            }
        ],
    )


def write_analysis(path: Path, analysis: dict) -> None:
    path.write_text(json.dumps(analysis), encoding="utf-8")


def test_lucidity_cli_extracts_demonstrated_failure(tmp_path: Path, capsys):
    path = tmp_path / "analysis.json"
    write_analysis(path, build_analysis())

    exit_code = run_lucidity_command(
        argparse.Namespace(analysis=str(path))
    )
    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert receipt["status"] == "DEMONSTRATED_FAILURES_EXTRACTED"
    assert receipt["failure_count"] == 1
    assert receipt["failures"][0]["finding_id"] == "f1"
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_lucidity_cli_no_failure_is_success(tmp_path: Path, capsys):
    path = tmp_path / "analysis.json"
    write_analysis(path, build_analysis("SUPPORTS"))

    exit_code = run_lucidity_command(
        argparse.Namespace(analysis=str(path))
    )
    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert receipt["status"] == "NO_DEMONSTRATED_FAILURE"
    assert receipt["failure_count"] == 0
    assert receipt["failures"] == []


def test_lucidity_cli_rejects_tampered_analysis(tmp_path: Path, capsys):
    path = tmp_path / "analysis.json"
    analysis = deepcopy(build_analysis())
    analysis["finding_results"][0]["status"] = "SUPPORTED"
    write_analysis(path, analysis)

    exit_code = run_lucidity_command(
        argparse.Namespace(analysis=str(path))
    )
    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert receipt["status"] == "ERROR"
    assert receipt["code"] == "LUCIDITY_ANALYSIS_INVALID"


def test_lucidity_cli_entrypoint(tmp_path: Path, capsys, monkeypatch):
    path = tmp_path / "analysis.json"
    write_analysis(path, build_analysis())

    monkeypatch.setattr(
        sys,
        "argv",
        ["holo", "lucidity", "--analysis", str(path)],
    )

    with pytest.raises(SystemExit) as exit_info:
        main()

    receipt = json.loads(capsys.readouterr().out)

    assert exit_info.value.code == 0
    assert receipt["status"] == "DEMONSTRATED_FAILURES_EXTRACTED"
    assert receipt["failure_count"] == 1
