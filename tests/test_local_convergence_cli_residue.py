from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from holosim import holo_cli
from holosim.auditable_residue_verifier import (
    AuditableResidueVerifier,
)


def test_cli_residue_failure_exits_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    preserved_path = tmp_path / "preserved.json"
    reconstructed_path = tmp_path / "reconstructed.json"

    preserved_path.write_text(
        json.dumps(
            {
                "contradictions": [
                    {
                        "id": "status-conflict",
                        "field": "status",
                        "observed_values": [
                            "ready",
                            "blocked",
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    reconstructed_path.write_text(
        json.dumps(
            {
                "contradictions": [],
            }
        ),
        encoding="utf-8",
    )

    def fake_run(
        software_request,
        workspace,
        *,
        model,
        endpoint,
        max_cycles,
        max_builder_attempts,
        residue_verifier,
        preserved_record,
        reconstructed_state,
    ):
        assert isinstance(
            residue_verifier,
            AuditableResidueVerifier,
        )

        residue_receipt = residue_verifier(
            preserved_record=preserved_record,
            reconstructed_state=reconstructed_state,
        )

        return {
            "status": "RESIDUE_VERIFICATION_FAILED",
            "converged": False,
            "runnable": False,
            "terminal_reason": residue_receipt["reason"],
            "residue_verification": residue_receipt,
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
            "--preserved-record",
            str(preserved_path),
            "--reconstructed-state",
            str(reconstructed_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        holo_cli.main()

    assert exc_info.value.code == 1

    output = json.loads(capsys.readouterr().out)

    assert output["status"] == (
        "RESIDUE_VERIFICATION_FAILED"
    )
    assert output["terminal_reason"] == (
        "RECORDED_CONTRADICTION_OMITTED"
    )
    assert output["converged"] is False
    assert output["runnable"] is False
    assert output["residue_verification"][
        "verified"
    ] is False