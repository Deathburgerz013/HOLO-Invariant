import logging
import sys
from pathlib import Path

import pytest

import holosim.holo_cli as cli
from holosim.continuity_demo import (
    build_continuity_demo,
    run_continuity_demo,
)
from holosim.continuity_topology import build_continuity_topology


def test_demo_builds_verified_relational_chain(tmp_path):
    chain_path = build_continuity_demo(tmp_path)

    assert chain_path == tmp_path / "continuity-demo.jsonl"
    topology = build_continuity_topology(chain_path)
    assert topology["verified"] is True
    assert topology["source_entries"] == 3
    assert [node["kind"] for node in topology["nodes"]] == [
        "record",
        "correction",
        "revalidation",
    ]
    assert [edge["kind"] for edge in topology["edges"]] == [
        "continuity",
        "continuity",
        "correction",
        "revalidation",
    ]
    assert topology["accepted"] is False
    assert topology["truth_claimed"] is False
    assert topology["write_authority"] == "NONE"
    assert topology["execution_authority"] == "NONE"


def test_demo_refuses_to_replace_existing_evidence(tmp_path):
    chain_path = tmp_path / "continuity-demo.jsonl"
    chain_path.write_bytes(b"existing evidence")

    with pytest.raises(FileExistsError, match="Demo chain already exists"):
        build_continuity_demo(tmp_path)

    assert chain_path.read_bytes() == b"existing evidence"


def test_demo_launches_topology_without_real_chain_mutation(tmp_path, monkeypatch):
    calls = []

    def fake_serve(chain_path, **options):
        calls.append((Path(chain_path), options))
        return 0

    monkeypatch.setattr(cli, "serve_operator_console", fake_serve)

    result = run_continuity_demo(
        tmp_path,
        host="127.0.0.1",
        port=0,
        open_browser=False,
    )

    assert result == 0
    assert calls == [
        (
            tmp_path / "continuity-demo.jsonl",
            {
                "host": "127.0.0.1",
                "port": 0,
                "open_browser": False,
                "initial_path": "/topology",
            },
        )
    ]


def test_holo_demo_entrypoint_dispatches(monkeypatch, tmp_path):
    calls = []

    def fake_demo(demo_dir, **options):
        calls.append((Path(demo_dir), options))
        return 0

    monkeypatch.setattr(cli, "run_continuity_demo", fake_demo)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "holo",
            "demo",
            "--demo-dir",
            str(tmp_path),
            "--port",
            "0",
            "--no-browser",
        ],
    )

    with pytest.raises(SystemExit) as stopped:
        cli.main()

    assert stopped.value.code == 0
    assert calls == [
        (
            tmp_path,
            {
                "host": "127.0.0.1",
                "port": 0,
                "open_browser": False,
            },
        )
    ]

def test_demo_suppresses_internal_info_noise(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="holosim.core")

    build_continuity_demo(tmp_path)

    assert not [
        record
        for record in caplog.records
        if record.name == "holosim.core"
        and record.levelno <= logging.INFO
    ]
