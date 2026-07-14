from pathlib import Path

from holosim.holo_cli import check_spine_headers


HEADER = "| | █†█ Holo/Sim █†█"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_raw_loop_with_bound_analysis_passes(tmp_path: Path) -> None:
    raw = tmp_path / "docs" / "Video_Software_Loop.md"
    analysis = tmp_path / "docs" / "Video_Software_Loop_Analysis.md"

    write(raw, "raw evidence without an injected header\n")
    write(
        analysis,
        (
            f"{HEADER}\n"
            "| | SOURCE_FILE: docs/Video_Software_Loop.md\n"
            "| | SOURCE_ROLE: RAW_EVIDENCE_TRACE\n"
        ),
    )

    assert check_spine_headers(tmp_path) == []


def test_raw_loop_without_analysis_fails(tmp_path: Path) -> None:
    raw = tmp_path / "docs" / "Video_Software_Loop.md"
    write(raw, "raw evidence without an injected header\n")

    issues = check_spine_headers(tmp_path)

    assert issues == [
        "Missing █†█ Holo/Sim █†█ header in docs/Video_Software_Loop.md"
    ]


def test_analysis_must_bind_exact_source_path(tmp_path: Path) -> None:
    raw = tmp_path / "docs" / "Video_Software_Loop.md"
    analysis = tmp_path / "docs" / "Video_Software_Loop_Analysis.md"

    write(raw, "raw evidence without an injected header\n")
    write(
        analysis,
        (
            f"{HEADER}\n"
            "| | SOURCE_FILE: docs/Different_Loop.md\n"
            "| | SOURCE_ROLE: RAW_EVIDENCE_TRACE\n"
        ),
    )

    issues = check_spine_headers(tmp_path)

    assert issues == [
        "Missing █†█ Holo/Sim █†█ header in docs/Video_Software_Loop.md"
    ]


def test_structural_document_still_requires_header(tmp_path: Path) -> None:
    spine = tmp_path / "docs" / "Example_Spine.md"
    write(spine, "structural document without header\n")

    issues = check_spine_headers(tmp_path)

    assert issues == [
        "Missing █†█ Holo/Sim █†█ header in docs/Example_Spine.md"
    ]