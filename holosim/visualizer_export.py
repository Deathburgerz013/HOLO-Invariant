"""Export real HOLO-Invariant repository structure for the visualizer.

This module converts parsed Spine documents, lineage reports, and feedback
reports into one deterministic JSON payload consumed by the HTML visualizer.

It never modifies source artifacts.
It never invents integrity percentages.
It never claims relationships that are not derived from visible structure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from holosim.spine_feedback import run_feedback
    from holosim.spine_lineage import analyze_paths
    from holosim.spine_protocol import parse_spine_file, reconstruct_frame
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.spine_feedback import run_feedback
    from holosim.spine_lineage import analyze_paths
    from holosim.spine_protocol import parse_spine_file, reconstruct_frame


EXPORT_TYPE = "holo_visualizer_export"
EXPORT_VERSION = 1

HEADER_TOKEN = "█†█ Holo/Sim █†█"

DEFAULT_OBJECTIVE = (
    "Preserve the structure required for compatible reconstruction, "
    "verification, challenge, correction, and continuity."
)

GROUP_BY_SUFFIX = {
    ".py": "code",
    ".md": "document",
    ".json": "artifact",
    ".jsonl": "artifact",
}

GROUP_COLORS = {
    "core": "#fbbf24",
    "document": "#a855f7",
    "code": "#22ff88",
    "artifact": "#00f3ff",
    "archive": "#fbbf24",
}

CORE_TITLES = {
    "spine_constitution.md",
    "spine_boundary_spec.md",
    "spine_invariant_spec.md",
    "spine_transfer_spec.md",
    "reconstruction_operator.md",
}


class VisualizerExportError(RuntimeError):
    """Base error for visualizer export failures."""


@dataclass(frozen=True)
class ExportNode:
    id: str
    label: str
    group: str
    description: str
    path: str
    source_hash: str
    geometry_hash: str | None
    header_present: bool | None
    section_count: int | None
    feedback_status: str | None
    blocking_count: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "group": self.group,
            "description": self.description,
            "path": self.path,
            "source_hash": self.source_hash,
            "geometry_hash": self.geometry_hash,
            "header_present": self.header_present,
            "section_count": self.section_count,
            "feedback_status": self.feedback_status,
            "blocking_count": self.blocking_count,
            "color": GROUP_COLORS[self.group],
        }


@dataclass(frozen=True)
class ExportLink:
    source: str
    target: str
    relation: str
    weight: float
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
            "evidence": self.evidence,
        }


def stable_hash(value: Any) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def normalize_id(value: str) -> str:
    cleaned = []
    previous_dash = False

    for character in value.lower():
        if character.isalnum():
            cleaned.append(character)
            previous_dash = False
        elif not previous_dash:
            cleaned.append("-")
            previous_dash = True

    result = "".join(cleaned).strip("-")
    return result or "artifact"


def classify_group(path: Path) -> str:
    name = path.name.lower()

    if name in CORE_TITLES:
        return "core"

    if "archive" in name or "analysis" in name:
        return "archive"

    return GROUP_BY_SUFFIX.get(path.suffix.lower(), "artifact")


def describe_node(
    *,
    path: Path,
    group: str,
    section_count: int | None,
    feedback_status: str | None,
    blocking_count: int | None,
) -> str:
    pieces = [f"{group.title()} artifact: {path.as_posix()}."]

    if section_count is not None:
        pieces.append(f"Contains {section_count} detected structural sections.")

    if feedback_status is not None:
        pieces.append(f"Feedback status: {feedback_status}.")
        if blocking_count:
            pieces.append(f"Blocking findings: {blocking_count}.")

    return " ".join(pieces)


def discover_files(
    repo_root: Path,
    *,
    include: Sequence[str] | None = None,
) -> list[Path]:
    """Discover exportable repository files deterministically."""
    if include:
        files = []
        for value in include:
            path = Path(value)
            if not path.is_absolute():
                path = repo_root / path
            if not path.exists():
                raise VisualizerExportError(f"Included path does not exist: {path}")
            if path.is_file():
                files.append(path.resolve())
        return sorted(set(files), key=lambda path: path.as_posix().lower())

    candidates: list[Path] = []

    for base in (repo_root / "docs", repo_root / "holosim"):
        if not base.exists():
            continue

        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in GROUP_BY_SUFFIX:
                continue
            if "__pycache__" in path.parts:
                continue
            candidates.append(path.resolve())

    return sorted(candidates, key=lambda path: path.as_posix().lower())


def build_document_node(
    path: Path,
    repo_root: Path,
    *,
    objective: str,
) -> tuple[ExportNode, dict[str, Any] | None, dict[str, Any] | None]:
    relative = path.relative_to(repo_root).as_posix()
    raw_bytes = path.read_bytes()
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    group = classify_group(path)

    frame: dict[str, Any] | None = None
    feedback: dict[str, Any] | None = None
    geometry_hash: str | None = None
    header_present: bool | None = None
    section_count: int | None = None
    feedback_status: str | None = None
    blocking_count: int | None = None

    if path.suffix.lower() == ".md":
        try:
            text_value = raw_bytes.decode("utf-8")
        except UnicodeError:
            text_value = ""

        header_present = HEADER_TOKEN in text_value

        if header_present:
            try:
                document = parse_spine_file(path)
                frame = reconstruct_frame(document)
                geometry_hash = frame["geometry"]["geometry_hash"]
                section_count = frame["geometry"]["section_count"]

                feedback = run_feedback(
                    path,
                    objective=objective,
                )
                feedback_status = feedback["status"]
                blocking_count = feedback["blocking_count"]
            except Exception as exc:
                frame = {
                    "error": str(exc),
                    "type": exc.__class__.__name__,
                }
                feedback = None
        else:
            # Ordinary Markdown remains visible as a repository artifact.
            # It is not judged by Spine-specific protocol requirements.
            frame = None
            feedback = None

    node = ExportNode(
        id=normalize_id(relative),
        label=path.name,
        group=group,
        description=describe_node(
            path=Path(relative),
            group=group,
            section_count=section_count,
            feedback_status=feedback_status,
            blocking_count=blocking_count,
        ),
        path=relative,
        source_hash=source_hash,
        geometry_hash=geometry_hash,
        header_present=header_present,
        section_count=section_count,
        feedback_status=feedback_status,
        blocking_count=blocking_count,
    )

    return node, frame, feedback

def _shared_section_links(
    document_nodes: Sequence[ExportNode],
    frames_by_id: Mapping[str, dict[str, Any] | None],
) -> list[ExportLink]:
    links: list[ExportLink] = []

    for left_index, left in enumerate(document_nodes):
        left_frame = frames_by_id.get(left.id)
        if not left_frame or "geometry" not in left_frame:
            continue

        left_titles = {
            title.lower()
            for title in left_frame["geometry"]["ordered_titles"]
        }

        for right in document_nodes[left_index + 1 :]:
            right_frame = frames_by_id.get(right.id)
            if not right_frame or "geometry" not in right_frame:
                continue

            right_titles = {
                title.lower()
                for title in right_frame["geometry"]["ordered_titles"]
            }

            shared = sorted(left_titles & right_titles)
            if not shared:
                continue

            denominator = max(len(left_titles), len(right_titles), 1)
            weight = round(len(shared) / denominator, 4)

            links.append(
                ExportLink(
                    source=left.id,
                    target=right.id,
                    relation="shared_sections",
                    weight=weight,
                    evidence=", ".join(shared[:12]),
                )
            )

    return links


def _lineage_links(
    ordered_paths: Sequence[Path],
    repo_root: Path,
) -> tuple[list[ExportLink], dict[str, Any] | None]:
    if len(ordered_paths) < 2:
        return [], None

    report = analyze_paths(ordered_paths)
    links: list[ExportLink] = []

    for transition in report["transitions"]:
        from_id = normalize_id(
            Path(transition["from_path"]).relative_to(repo_root).as_posix()
        )
        to_id = normalize_id(
            Path(transition["to_path"]).relative_to(repo_root).as_posix()
        )

        magnitude = (
            len(transition["added"])
            + len(transition["removed"])
            + len(transition["changed"])
            + len(transition["moved"])
        )
        weight = round(1.0 / max(1, magnitude), 4)

        links.append(
            ExportLink(
                source=from_id,
                target=to_id,
                relation="lineage_transition",
                weight=weight,
                evidence=(
                    f"added={len(transition['added'])}; "
                    f"removed={len(transition['removed'])}; "
                    f"changed={len(transition['changed'])}; "
                    f"moved={len(transition['moved'])}"
                ),
            )
        )

    return links, report


def export_visualizer_data(
    *,
    repo_root: Path,
    include: Sequence[str] | None = None,
    lineage_paths: Sequence[str] | None = None,
    objective: str = DEFAULT_OBJECTIVE,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    files = discover_files(repo_root, include=include)

    nodes: list[ExportNode] = []
    frames_by_id: dict[str, dict[str, Any] | None] = {}
    feedback_by_id: dict[str, dict[str, Any] | None] = {}

    for path in files:
        node, frame, feedback = build_document_node(
            path,
            repo_root,
            objective=objective,
        )
        nodes.append(node)
        frames_by_id[node.id] = frame
        feedback_by_id[node.id] = feedback

    document_nodes = [
        node for node in nodes if Path(node.path).suffix.lower() == ".md"
    ]

    links = _shared_section_links(document_nodes, frames_by_id)

    lineage_report: dict[str, Any] | None = None
    if lineage_paths:
        ordered_paths = []
        for value in lineage_paths:
            path = Path(value)
            if not path.is_absolute():
                path = repo_root / path
            ordered_paths.append(path.resolve())

        lineage_links, lineage_report = _lineage_links(
            ordered_paths,
            repo_root,
        )
        links.extend(lineage_links)

    unique_links: dict[tuple[str, str, str], ExportLink] = {}
    for link in links:
        key = (link.source, link.target, link.relation)
        unique_links[key] = link

    link_values = sorted(
        unique_links.values(),
        key=lambda link: (link.relation, link.source, link.target),
    )

    md_nodes = [
        node for node in nodes
        if Path(node.path).suffix.lower() == ".md"
    ]
    spine_nodes = [
        node for node in md_nodes
        if node.header_present is True
    ]
    ordinary_md_nodes = [
        node for node in md_nodes
        if node.header_present is not True
    ]
    parsed_spine_nodes = [
        node for node in spine_nodes
        if node.section_count is not None
    ]
    blocked_spine_nodes = [
        node for node in spine_nodes
        if node.feedback_status == "BLOCKED"
    ]

    integrity_checks = {
        "all_sources_hashed": all(bool(node.source_hash) for node in nodes),
        "all_spine_documents_parsed": (
            len(parsed_spine_nodes) == len(spine_nodes)
        ),
        "all_spine_documents_have_header": all(
            node.header_present is True for node in spine_nodes
        ),
        "no_blocking_feedback": len(blocked_spine_nodes) == 0,
    }
    integrity_passed = sum(1 for value in integrity_checks.values() if value)
    integrity_total = len(integrity_checks)

    payload: dict[str, Any] = {
        "type": EXPORT_TYPE,
        "version": EXPORT_VERSION,
        "objective": objective,
        "repo_root": repo_root.as_posix(),
        "metrics": {
            "node_count": len(nodes),
            "link_count": len(link_values),
            "markdown_document_count": len(md_nodes),
            "ordinary_markdown_count": len(ordinary_md_nodes),
            "spine_document_count": len(spine_nodes),
            "parsed_spine_count": len(parsed_spine_nodes),
            "header_present_count": len(spine_nodes),
            "blocking_feedback_count": len(blocked_spine_nodes),
            "integrity_checks_passed": integrity_passed,
            "integrity_checks_total": integrity_total,
            "integrity_ratio": (
                integrity_passed / integrity_total
                if integrity_total
                else 1.0
            ),
        },
        "integrity_checks": integrity_checks,
        "nodes": [node.to_dict() for node in nodes],
        "links": [link.to_dict() for link in link_values],
        "frames": frames_by_id,
        "feedback": feedback_by_id,
        "lineage": lineage_report,
        "interpretation_notice": (
            "All metrics in this export are derived from repository files "
            "visible to the exporter. No display-only values are fabricated."
        ),
    }

    return {**payload, "export_hash": stable_hash(payload)}


def write_export(
    report: Mapping[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def run_self_test() -> None:
    header = (
        "|===========================================|\n"
        "| █†█ Holo/Sim █†█ █†█ HSSCE █†█ |\n"
        "|===========================================|\n"
    )

    first = (
        header
        + "\n# Purpose\nPreserve structure.\n"
        + "\n# Objective\nPreserve structure.\n"
        + "\n# Verification\nRun test.\n"
        + "\n# Uncertainty\nNone known.\n"
        + "\n# Termination\nStop when complete.\n"
    )

    second = (
        header
        + "\n# Purpose\nPreserve structure.\n"
        + "\n# Objective\nPreserve structure.\n"
        + "\n# Verification\nRun test and compare.\n"
        + "\n# Uncertainty\nNone known.\n"
        + "\n# Termination\nStop when complete.\n"
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        docs = root / "docs"
        holosim = root / "holosim"
        docs.mkdir()
        holosim.mkdir()

        first_path = docs / "pass1.md"
        second_path = docs / "pass2.md"
        code_path = holosim / "example.py"
        ordinary_path = docs / "notes.md"

        first_path.write_bytes(first.encode("utf-8"))
        second_path.write_bytes(second.encode("utf-8"))
        ordinary_path.write_text(
            "# Notes\nOrdinary Markdown, not a Spine document.\n",
            encoding="utf-8",
        )
        code_path.write_text(
            "# ==================== MODEL ====================\n"
            "VALUE = 1\n",
            encoding="utf-8",
        )

        report = export_visualizer_data(
            repo_root=root,
            include=[
                "docs/pass1.md",
                "docs/pass2.md",
                "holosim/example.py",
                "docs/notes.md",
            ],
            lineage_paths=[
                "docs/pass1.md",
                "docs/pass2.md",
            ],
            objective="Preserve structure.",
        )

        output_path = root / "visualizer_data.json"
        write_export(report, output_path)

        loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert loaded["metrics"]["node_count"] == 4
    assert loaded["metrics"]["markdown_document_count"] == 3
    assert loaded["metrics"]["parsed_spine_count"] == 2
    assert loaded["metrics"]["header_present_count"] == 2
    assert loaded["metrics"]["ordinary_markdown_count"] == 1
    assert loaded["lineage"] is not None
    assert len(loaded["links"]) >= 1
    assert len(loaded["export_hash"]) == 64

    print("✅ Visualizer export self-test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export measured HOLO-Invariant repository structure "
            "for the visualizer."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export",
        help="Generate visualizer JSON from repository artifacts",
    )
    export_parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root",
    )
    export_parser.add_argument(
        "--output",
        "-o",
        default="visualizer/visualizer_data.json",
        help="JSON output path",
    )
    export_parser.add_argument(
        "--include",
        action="append",
        default=None,
        help=(
            "Specific repository-relative file to export. "
            "Repeat to include multiple files."
        ),
    )
    export_parser.add_argument(
        "--lineage",
        action="append",
        default=None,
        help=(
            "Repository-relative artifact in chronological lineage order. "
            "Repeat for each artifact."
        ),
    )
    export_parser.add_argument(
        "--objective",
        default=DEFAULT_OBJECTIVE,
        help="Objective passed to spine_feedback",
    )

    subparsers.add_parser(
        "self-test",
        help="Run isolated exporter tests",
    )

    args = parser.parse_args()

    try:
        if args.command == "export":
            report = export_visualizer_data(
                repo_root=Path(args.repo_root),
                include=args.include,
                lineage_paths=args.lineage,
                objective=args.objective,
            )
            output_path = Path(args.output)
            write_export(report, output_path)
            print(f"Visualizer export written: {output_path}")
            print(
                f"Nodes: {report['metrics']['node_count']} | "
                f"Links: {report['metrics']['link_count']} | "
                f"Integrity: "
                f"{report['metrics']['integrity_checks_passed']}/"
                f"{report['metrics']['integrity_checks_total']}"
            )
            raise SystemExit(0)

        if args.command == "self-test":
            run_self_test()
            raise SystemExit(0)

        raise SystemExit(f"Unknown command: {args.command}")
    except VisualizerExportError as exc:
        print(f"Visualizer export: FAIL\n{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
