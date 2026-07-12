"""Read-only lineage analysis for HOLO-Invariant Spine artifacts.

This module compares an ordered sequence of Markdown or Python artifacts and
tracks how explicit structural sections emerge, persist, move, change, split,
merge, or disappear over time.

The source files remain canonical. This module never rewrites them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

LINEAGE_TYPE = "holo_spine_lineage_report"
LINEAGE_VERSION = 1

MARKDOWN_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
SEPARATOR = re.compile(
    r"^[ \t]*#?[ \t]*={3,}[ \t]*(.*?)[ \t]*={3,}[ \t]*$",
    re.MULTILINE,
)
WORD_PATTERN = re.compile(r"[a-z0-9]+")
HEADER_PATTERN = re.compile(r"█†█\s*Holo/Sim\s*█†█")


class SpineLineageError(RuntimeError):
    """Base error for lineage analysis failures."""


class ArtifactReadError(SpineLineageError):
    """Raised when an artifact cannot be read as UTF-8 text."""


@dataclass(frozen=True)
class Section:
    index: int
    section_id: str
    title: str
    kind: str
    level: int | None
    start_line: int
    end_line: int
    raw: str
    content_hash: str
    body_hash: str

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        value: dict[str, Any] = {
            "index": self.index,
            "section_id": self.section_id,
            "title": self.title,
            "kind": self.kind,
            "level": self.level,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_hash": self.content_hash,
            "body_hash": self.body_hash,
        }
        if include_raw:
            value["raw"] = self.raw
        return value


@dataclass(frozen=True)
class Artifact:
    order: int
    path: str
    source_hash: str
    header_present: bool
    header_text: str | None
    header_hash: str | None
    header_line: int | None
    sections: tuple[Section, ...]

    @property
    def compartments(self) -> tuple[Section, ...]:
        return tuple(
            section for section in self.sections
            if section.kind == "separator"
        )

    @property
    def compartments_after_header(self) -> tuple[Section, ...]:
        if self.header_line is None:
            return tuple()
        return tuple(
            section for section in self.compartments
            if section.start_line > self.header_line
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "path": self.path,
            "source_hash": self.source_hash,
            "header": {
                "present": self.header_present,
                "text": self.header_text,
                "sha256": self.header_hash,
                "line": self.header_line,
            },
            "section_count": len(self.sections),
            "compartment_count": len(self.compartments),
            "compartments_after_header": len(self.compartments_after_header),
            "header_precedes_compartments": (
                self.header_present
                and len(self.compartments_after_header) > 0
            ),
            "ordered_section_ids": [
                section.section_id for section in self.sections
            ],
            "ordered_compartment_ids": [
                section.section_id for section in self.compartments
            ],
        }


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_title(value: str) -> str:
    words = WORD_PATTERN.findall(value.lower())
    return "_".join(words) or "untitled"


def line_number_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _marker_matches(text: str) -> list[tuple[int, int, str, str, int | None]]:
    candidates: list[tuple[int, int, str, str, int | None]] = []

    for match in MARKDOWN_HEADING.finditer(text):
        title = match.group(2).strip().rstrip("\r")
        # Treat decorative code separators as separators, not Markdown headings.
        if re.fullmatch(r"={3,}.*={3,}", title):
            continue
        candidates.append(
            (match.start(), match.end(), title, "markdown_heading", len(match.group(1)))
        )

    for match in SEPARATOR.finditer(text):
        title = match.group(1).strip().strip("|#/*- \t\r")
        if not title:
            continue
        candidates.append((match.start(), match.end(), title, "separator", None))

    by_start: dict[int, tuple[int, int, str, str, int | None]] = {}
    for item in sorted(candidates, key=lambda value: (value[0], value[3] != "markdown_heading")):
        by_start.setdefault(item[0], item)

    return [by_start[key] for key in sorted(by_start)]


def parse_artifact(path: str | Path, order: int) -> Artifact:
    resolved = Path(path)
    try:
        raw_bytes = resolved.read_bytes()
        text = raw_bytes.decode("utf-8")
    except OSError as exc:
        raise ArtifactReadError(f"Unable to read {resolved}: {exc}") from exc
    except UnicodeError as exc:
        raise ArtifactReadError(f"{resolved} is not valid UTF-8 text.") from exc

    header_match = HEADER_PATTERN.search(text[:5000])
    header_present = header_match is not None
    header_text: str | None = None
    header_hash: str | None = None
    header_line: int | None = None

    if header_match is not None:
        line_start = text.rfind("\n", 0, header_match.start()) + 1
        line_end = text.find("\n", header_match.end())
        if line_end == -1:
            line_end = len(text)
        header_text = text[line_start:line_end].rstrip("\r")
        header_hash = sha256_text(header_text)
        header_line = line_number_at(text, line_start)

    markers = _marker_matches(text)
    sections: list[Section] = []
    occurrence_counts: dict[str, int] = {}

    for index, marker in enumerate(markers):
        start, marker_end, title, kind, level = marker
        end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        raw = text[start:end]
        body = text[marker_end:end]
        normalized = normalize_title(title)

        occurrence = occurrence_counts.get(normalized, 0) + 1
        occurrence_counts[normalized] = occurrence
        section_id = normalized if occurrence == 1 else f"{normalized}__{occurrence}"

        sections.append(
            Section(
                index=index,
                section_id=section_id,
                title=title,
                kind=kind,
                level=level,
                start_line=line_number_at(text, start),
                end_line=line_number_at(text, max(start, end - 1)),
                raw=raw,
                content_hash=sha256_text(raw),
                body_hash=sha256_text(body),
            )
        )

    return Artifact(
        order=order,
        path=resolved.as_posix(),
        source_hash=hashlib.sha256(raw_bytes).hexdigest(),
        header_present=header_present,
        header_text=header_text,
        header_hash=header_hash,
        header_line=header_line,
        sections=tuple(sections),
    )


def _token_set(title: str) -> set[str]:
    return set(WORD_PATTERN.findall(title.lower()))


def _similarity(left: Section, right: Section) -> float:
    left_tokens = _token_set(left.title)
    right_tokens = _token_set(right.title)
    if not left_tokens or not right_tokens:
        return 0.0

    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    title_score = intersection / union if union else 0.0
    body_score = 1.0 if left.body_hash == right.body_hash else 0.0
    kind_score = 1.0 if left.kind == right.kind else 0.0
    return (0.7 * title_score) + (0.2 * body_score) + (0.1 * kind_score)


def _detect_split_merge_events(
    previous: Artifact,
    current: Artifact,
    threshold: float = 0.45,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    previous_ids = {section.section_id for section in previous.sections}
    current_ids = {section.section_id for section in current.sections}

    removed = [section for section in previous.sections if section.section_id not in current_ids]
    added = [section for section in current.sections if section.section_id not in previous_ids]

    splits: list[dict[str, Any]] = []
    merges: list[dict[str, Any]] = []

    for old in removed:
        matches = [
            (new, _similarity(old, new))
            for new in added
            if _similarity(old, new) >= threshold
        ]
        if len(matches) >= 2:
            splits.append(
                {
                    "from": old.section_id,
                    "into": [section.section_id for section, _ in matches],
                    "scores": {
                        section.section_id: round(score, 4)
                        for section, score in matches
                    },
                    "status": "candidate",
                }
            )

    for new in added:
        matches = [
            (old, _similarity(old, new))
            for old in removed
            if _similarity(old, new) >= threshold
        ]
        if len(matches) >= 2:
            merges.append(
                {
                    "from": [section.section_id for section, _ in matches],
                    "into": new.section_id,
                    "scores": {
                        section.section_id: round(score, 4)
                        for section, score in matches
                    },
                    "status": "candidate",
                }
            )

    return splits, merges


def build_lineage(artifacts: Sequence[Artifact]) -> dict[str, Any]:
    if not artifacts:
        raise SpineLineageError("At least one artifact is required.")

    section_history: dict[str, dict[str, Any]] = {}
    transitions: list[dict[str, Any]] = []

    for artifact in artifacts:
        for section in artifact.sections:
            history = section_history.setdefault(
                section.section_id,
                {
                    "section_id": section.section_id,
                    "title_variants": [],
                    "introduced_at": artifact.order,
                    "last_seen_at": artifact.order,
                    "appearances": [],
                    "changes": 0,
                    "moves": 0,
                    "present_in": [],
                },
            )

            if section.title not in history["title_variants"]:
                history["title_variants"].append(section.title)

            history["last_seen_at"] = artifact.order
            history["present_in"].append(artifact.path)
            history["appearances"].append(
                {
                    "artifact_order": artifact.order,
                    "artifact_path": artifact.path,
                    "index": section.index,
                    "kind": section.kind,
                    "level": section.level,
                    "content_hash": section.content_hash,
                    "body_hash": section.body_hash,
                    "start_line": section.start_line,
                    "end_line": section.end_line,
                }
            )

    for history in section_history.values():
        appearances = history["appearances"]
        for previous, current in zip(appearances, appearances[1:]):
            if previous["content_hash"] != current["content_hash"]:
                history["changes"] += 1
            if previous["index"] != current["index"]:
                history["moves"] += 1

        history["stable_content"] = history["changes"] == 0
        history["stable_position"] = history["moves"] == 0
        history["persistence_count"] = len(appearances)

    for previous, current in zip(artifacts, artifacts[1:]):
        previous_map = {section.section_id: section for section in previous.sections}
        current_map = {section.section_id: section for section in current.sections}

        previous_ids = set(previous_map)
        current_ids = set(current_map)
        shared = sorted(previous_ids & current_ids)

        added = sorted(current_ids - previous_ids)
        removed = sorted(previous_ids - current_ids)
        changed = sorted(
            section_id
            for section_id in shared
            if previous_map[section_id].content_hash != current_map[section_id].content_hash
        )
        moved = sorted(
            section_id
            for section_id in shared
            if previous_map[section_id].index != current_map[section_id].index
        )
        unchanged = sorted(
            section_id
            for section_id in shared
            if previous_map[section_id].content_hash == current_map[section_id].content_hash
            and previous_map[section_id].index == current_map[section_id].index
        )

        splits, merges = _detect_split_merge_events(previous, current)

        transitions.append(
            {
                "from_order": previous.order,
                "to_order": current.order,
                "from_path": previous.path,
                "to_path": current.path,
                "added": added,
                "removed": removed,
                "changed": changed,
                "moved": moved,
                "unchanged": unchanged,
                "candidate_splits": splits,
                "candidate_merges": merges,
            }
        )

    ordered_histories = sorted(
        section_history.values(),
        key=lambda value: (
            value["introduced_at"],
            value["appearances"][0]["index"],
            value["section_id"],
        ),
    )

    geometry_sequence = [
        {
            "artifact_order": artifact.order,
            "artifact_path": artifact.path,
            "header_present": artifact.header_present,
            "header_hash": artifact.header_hash,
            "ordered_section_ids": [
                section.section_id for section in artifact.sections
            ],
            "ordered_compartment_ids": [
                section.section_id for section in artifact.compartments
            ],
        }
        for artifact in artifacts
    ]
    geometry_hash = sha256_text(
        json.dumps(
            geometry_sequence,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )

    return {
        "type": LINEAGE_TYPE,
        "version": LINEAGE_VERSION,
        "artifact_count": len(artifacts),
        "geometry_hash": geometry_hash,
        "artifacts": [artifact.to_dict() for artifact in artifacts],
        "sections": ordered_histories,
        "transitions": transitions,
        "header_compartment_relationship": {
            "artifacts_with_header": sum(
                1 for artifact in artifacts if artifact.header_present
            ),
            "artifacts_without_header": sum(
                1 for artifact in artifacts if not artifact.header_present
            ),
            "artifacts_with_compartments": sum(
                1 for artifact in artifacts if artifact.compartments
            ),
            "artifacts_where_header_precedes_compartments": sum(
                1
                for artifact in artifacts
                if artifact.header_present
                and artifact.compartments_after_header
            ),
            "header_hashes": sorted(
                {
                    artifact.header_hash
                    for artifact in artifacts
                    if artifact.header_hash is not None
                }
            ),
            "observation": (
                "This report records whether the canonical Holo/Sim header "
                "appears before explicit separator-defined compartments. "
                "It does not by itself prove that the header caused the "
                "compartments to emerge."
            ),
        },
        "summary": {
            "unique_sections": len(ordered_histories),
            "total_compartments": sum(
                len(artifact.compartments) for artifact in artifacts
            ),
            "total_compartments_after_header": sum(
                len(artifact.compartments_after_header)
                for artifact in artifacts
            ),
            "total_section_appearances": sum(
                len(history["appearances"]) for history in ordered_histories
            ),
            "total_changes": sum(history["changes"] for history in ordered_histories),
            "total_moves": sum(history["moves"] for history in ordered_histories),
            "candidate_splits": sum(
                len(transition["candidate_splits"]) for transition in transitions
            ),
            "candidate_merges": sum(
                len(transition["candidate_merges"]) for transition in transitions
            ),
        },
        "interpretation_notice": (
            "Section identity is derived from normalized visible labels. "
            "Split and merge events are candidates inferred from similarity, "
            "not proven ancestry."
        ),
    }


def analyze_paths(paths: Sequence[str | Path]) -> dict[str, Any]:
    artifacts = [
        parse_artifact(path, order=index)
        for index, path in enumerate(paths, start=1)
    ]
    return build_lineage(artifacts)


def run_self_test() -> None:
    header = (
        "|===========================================|\n"
        "| █†█ Holo/Sim █†█ █†█ HSSCE █†█ |\n"
        "|===========================================|\n"
    )

    first = header + textwrap.dedent(
        """
        # Purpose
        Base purpose.

        # ==================== MODEL ====================
        model-v1

        # ==================== CORRECTION ====================
        correction-v1
        """
    ).lstrip()

    second = header + textwrap.dedent(
        """
        # Purpose
        Refined purpose.

        # ==================== MODEL ====================
        model-v1

        # ==================== PACKETS ====================
        packet-v1

        # ==================== CORRECTION ====================
        correction-v2
        """
    ).lstrip()

    third = header + textwrap.dedent(
        """
        # Purpose
        Refined purpose.

        # ==================== MODEL ====================
        model-v2

        # ==================== CORRECTION ====================
        correction-v2

        # ==================== PACKETS ====================
        packet-v1
        """
    ).lstrip()

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        paths = []
        for name, value in (
            ("pass1.md", first),
            ("pass2.md", second),
            ("pass3.md", third),
        ):
            path = root / name
            path.write_bytes(value.encode("utf-8"))
            paths.append(path)

        report = analyze_paths(paths)

    assert report["artifact_count"] == 3
    by_id = {item["section_id"]: item for item in report["sections"]}
    assert "purpose" in by_id
    assert "model" in by_id
    assert "correction" in by_id
    assert "packets" in by_id
    assert by_id["purpose"]["changes"] == 1
    assert by_id["model"]["changes"] == 1
    assert by_id["correction"]["moves"] >= 1
    assert by_id["packets"]["introduced_at"] == 2

    first_transition = report["transitions"][0]
    assert "packets" in first_transition["added"]
    assert "purpose" in first_transition["changed"]

    print("✅ Spine lineage self-test passed.")


def _print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Trace structural section lineage across ordered Markdown "
            "or Python artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze an ordered sequence of artifacts",
    )
    analyze_parser.add_argument(
        "files",
        nargs="+",
        help="Artifact paths in chronological order",
    )
    analyze_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional JSON report path",
    )

    subparsers.add_parser("self-test", help="Run isolated lineage tests")
    args = parser.parse_args()

    try:
        if args.command == "analyze":
            report = analyze_paths(args.files)
            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                print(f"Lineage report written: {output_path}")
            else:
                _print_json(report)
        elif args.command == "self-test":
            run_self_test()
        else:
            raise SystemExit(f"Unknown command: {args.command}")
    except SpineLineageError as exc:
        print(f"Spine lineage: FAIL\n{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
