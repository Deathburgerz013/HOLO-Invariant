import argparse
import hashlib
import json
import sys
from pathlib import Path

import pytest

from holosim.holo_cli import main, run_idx_check_command


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_idx(path: Path) -> None:
    path.write_text(
        "IDX:v=1;n=1\n"
        f"S1=CORE@{digest('original')}\n"
        "ACTIVE_HASH=frozen-head\n",
        encoding="utf-8",
    )


def write_packet(
    path: Path,
    *,
    payload: str = "original",
) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "active_hash": "frozen-head",
                "slots": [
                    {
                        "name": "CORE",
                        "payload": payload,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def build_args(
    idx_path: Path,
    packet_path: Path,
) -> argparse.Namespace:
    return argparse.Namespace(
        idx=str(idx_path),
        packet=str(packet_path),
    )


def test_idx_check_passes_without_mutation(
    tmp_path: Path,
    capsys,
):
    idx_path = tmp_path / "frozen.idx"
    packet_path = tmp_path / "spine.json"
    write_idx(idx_path)
    write_packet(packet_path)

    before_idx = idx_path.read_bytes()
    before_packet = packet_path.read_bytes()

    exit_code = run_idx_check_command(
        build_args(idx_path, packet_path)
    )

    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert receipt == {
        "status": "PASS",
        "code": "IDX_MATCH",
        "fused": False,
        "slot": None,
        "expected": None,
        "observed": None,
    }
    assert idx_path.read_bytes() == before_idx
    assert packet_path.read_bytes() == before_packet


def test_idx_check_returns_abort_receipt_on_mismatch(
    tmp_path: Path,
    capsys,
):
    idx_path = tmp_path / "frozen.idx"
    packet_path = tmp_path / "spine.json"
    write_idx(idx_path)
    write_packet(packet_path, payload="changed")

    exit_code = run_idx_check_command(
        build_args(idx_path, packet_path)
    )

    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert receipt["status"] == "ABORT"
    assert receipt["code"] == "SLOT_HASH_MISMATCH"
    assert receipt["fused"] is False
    assert receipt["slot"] == "CORE"


def test_idx_check_rejects_malformed_packet(
    tmp_path: Path,
    capsys,
):
    idx_path = tmp_path / "frozen.idx"
    packet_path = tmp_path / "spine.json"
    write_idx(idx_path)
    packet_path.write_text(
        '{"version": 1}',
        encoding="utf-8",
    )

    exit_code = run_idx_check_command(
        build_args(idx_path, packet_path)
    )

    captured = capsys.readouterr()
    receipt = json.loads(captured.out)

    assert exit_code == 2
    assert receipt["status"] == "ERROR"
    assert receipt["code"] == "IDX_PACKET_INVALID"
    assert receipt["fused"] is False

def test_idx_check_cli_entrypoint(
    tmp_path: Path,
    capsys,
    monkeypatch,
):
    idx_path = tmp_path / "frozen.idx"
    packet_path = tmp_path / "spine.json"
    write_idx(idx_path)
    write_packet(packet_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "holo",
            "idx-check",
            "--idx",
            str(idx_path),
            "--packet",
            str(packet_path),
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        main()

    receipt = json.loads(capsys.readouterr().out)

    assert exit_info.value.code == 0
    assert receipt["status"] == "PASS"
    assert receipt["code"] == "IDX_MATCH"
