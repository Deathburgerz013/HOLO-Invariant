"""Contract tests for the measured visualizer export boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import holosim.visualizer_export as visualizer
from holosim.visualizer_export import (
    ExportNode,
    VisualizerExportError,
    _shared_section_links,
    export_visualizer_data,
    stable_hash,
    write_export,
)


def _node(node_id: str, path: str) -> ExportNode:
    return ExportNode(
        id=node_id,
        label=Path(path).name,
        group="document",
        description="test",
        path=path,
        source_hash="0" * 64,
        geometry_hash="1" * 64,
        header_present=True,
        section_count=1,
        feedback_status="COMPLETE",
        blocking_count=0,
    )


def test_export_is_deterministic_and_hash_covers_payload(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "holosim").mkdir()
    (tmp_path / "docs" / "notes.md").write_text("# Notes\nVisible fact.\n", encoding="utf-8")
    (tmp_path / "holosim" / "model.py").write_text("VALUE = 1\n", encoding="utf-8")

    include = ["holosim/model.py", "docs/notes.md", "docs/notes.md"]
    first = export_visualizer_data(repo_root=tmp_path, include=include)
    second = export_visualizer_data(repo_root=tmp_path, include=list(reversed(include)))

    assert first == second
    assert [node["path"] for node in first["nodes"]] == [
        "docs/notes.md",
        "holosim/model.py",
    ]

    claimed_hash = first["export_hash"]
    unhashed_payload = {key: value for key, value in first.items() if key != "export_hash"}
    assert claimed_hash == stable_hash(unhashed_payload)
    assert len(claimed_hash) == 64


def test_source_hashes_are_measured_from_exact_bytes(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    raw = b"# Notes\r\nExact bytes matter.\r\n"
    source = tmp_path / "docs" / "notes.md"
    source.write_bytes(raw)

    report = export_visualizer_data(repo_root=tmp_path, include=["docs/notes.md"])

    assert report["nodes"][0]["source_hash"] == hashlib.sha256(raw).hexdigest()
    assert report["integrity_checks"]["all_sources_hashed"] is True


def test_missing_explicit_include_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(VisualizerExportError, match="Included path does not exist"):
        export_visualizer_data(repo_root=tmp_path, include=["docs/missing.md"])


def test_parser_failure_is_visible_and_marks_integrity_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "docs").mkdir()
    source = tmp_path / "docs" / "broken.md"
    source.write_text(
        "|===========================================|\n"
        "| █†█ Holo/Sim █†█ █†█ HSSCE █†█ |\n"
        "|===========================================|\n"
        "# Purpose\nPreserve the failure as evidence.\n",
        encoding="utf-8",
    )

    def fail_parse(_path: Path) -> object:
        raise ValueError("synthetic parse failure")

    monkeypatch.setattr(visualizer, "parse_spine_file", fail_parse)

    report = export_visualizer_data(repo_root=tmp_path, include=["docs/broken.md"])
    node = report["nodes"][0]
    frame = report["frames"][node["id"]]

    assert node["header_present"] is True
    assert node["section_count"] is None
    assert frame == {"error": "synthetic parse failure", "type": "ValueError"}
    assert report["metrics"]["spine_document_count"] == 1
    assert report["metrics"]["parsed_spine_count"] == 0
    assert report["integrity_checks"]["all_spine_documents_parsed"] is False


def test_shared_section_links_require_visible_overlap() -> None:
    left = _node("left", "docs/left.md")
    right = _node("right", "docs/right.md")
    unrelated = _node("unrelated", "docs/unrelated.md")
    frames = {
        "left": {"geometry": {"ordered_titles": ["Purpose", "Verification"]}},
        "right": {"geometry": {"ordered_titles": ["purpose", "Termination"]}},
        "unrelated": {"geometry": {"ordered_titles": ["Uncertainty"]}},
    }

    links = _shared_section_links([left, right, unrelated], frames)

    assert len(links) == 1
    link = links[0]
    assert (link.source, link.target, link.relation) == (
        "left",
        "right",
        "shared_sections",
    )
    assert link.evidence == "purpose"
    assert link.weight == 0.5


def test_every_exported_link_references_nodes_and_carries_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "docs").mkdir()
    header = (
        "|===========================================|\n"
        "| █†█ Holo/Sim █†█ █†█ HSSCE █†█ |\n"
        "|===========================================|\n"
    )
    body = (
        "# Purpose\nPreserve structure.\n"
        "# Objective\nPreserve structure.\n"
        "# Verification\nRun the parser.\n"
        "# Uncertainty\nNone known.\n"
        "# Termination\nStop when complete.\n"
    )
    for name in ("first.md", "second.md"):
        (tmp_path / "docs" / name).write_text(header + body, encoding="utf-8")

    report = export_visualizer_data(
        repo_root=tmp_path,
        include=["docs/first.md", "docs/second.md"],
        objective="Preserve structure.",
    )
    node_ids = {node["id"] for node in report["nodes"]}

    assert report["links"]
    for link in report["links"]:
        assert link["source"] in node_ids
        assert link["target"] in node_ids
        assert link["source"] != link["target"]
        assert link["relation"] in {"shared_sections", "lineage_transition"}
        assert 0 < link["weight"] <= 1
        assert link["evidence"].strip()


def test_written_json_round_trips_without_changing_contract(tmp_path: Path) -> None:
    (tmp_path / "holosim").mkdir()
    (tmp_path / "holosim" / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
    report = export_visualizer_data(
        repo_root=tmp_path,
        include=["holosim/model.py"],
    )
    output = tmp_path / "visualizer" / "visualizer_data.json"

    write_export(report, output)
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert loaded == report
    assert loaded["metrics"]["node_count"] == len(loaded["nodes"])
    assert loaded["metrics"]["link_count"] == len(loaded["links"])
