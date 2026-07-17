"""Read-only, lossless Spine protocol engine for HOLO-Invariant.

The raw Spine document remains canonical.

This module:
- recognizes the canonical Holo/Sim header,
- parses ordered Markdown sections without rewriting source text,
- preserves unknown sections,
- reconstructs a derived semantic frame with source locations,
- compares two Spine documents without modifying either source,
- evaluates structured source descriptions against bounded destination profiles.

It does not:
- normalize or rewrite Spine content,
- approve transitions,
- update canonical documents,
- claim inherited memory,
- treat parser output as authoritative truth.
- infer acceptance or grant write authority from compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROTOCOL_TYPE = "holo_spine_protocol"
PROTOCOL_VERSION = 1

HEADER_PATTERN = re.compile(r"█†█\s*Holo/Sim\s*█†█")
HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
RAIL_LINE_PATTERN = re.compile(r"^(?P<prefix>(?:[|\u2502][ \t]*)+)(?P<body>.*)$")
RAIL_DIVIDER_PATTERN = re.compile(r"^\}={3,}\|?$")
RAIL_BORDER_PATTERN = re.compile(r"^={3,}\|?$")

BOUNDARY_NAMES = {
    "observation", "claim", "evidence", "verification", "authority",
    "identity", "uncertainty", "timeline", "compression", "reconstruction",
    "integrity", "semantic", "transition", "termination",
}

SEMANTIC_LABELS = {
    "claim": ("claim", "claims"),
    "observation": ("observation", "observations"),
    "evidence": ("evidence",),
    "verification": ("verification",),
    "uncertainty": ("uncertainty", "unknown", "unknowns"),
    "lineage": ("lineage", "history", "timeline"),
    "correction": ("correction", "corrections", "recovery"),
}


class SpineProtocolError(RuntimeError):
    """Base error for Spine protocol failures."""


class SpineHeaderError(SpineProtocolError):
    """Raised when a canonical Holo/Sim header cannot be recognized."""


class SpineStructureError(SpineProtocolError):
    """Raised when a Spine document cannot be parsed safely."""


def sha256_bytes(data: bytes) -> str:
    """Return a full SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def normalize_heading(value: str) -> str:
    """Normalize a heading only for comparison and classification."""
    return " ".join(value.strip().lower().split())


def line_number_at(text: str, offset: int) -> int:
    """Return the 1-based line number for a character offset."""
    return text.count("\n", 0, offset) + 1


@dataclass(frozen=True)
class SourceSpan:
    start_offset: int
    end_offset: int
    start_line: int
    end_line: int

    def to_dict(self) -> dict[str, int]:
        return {
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass(frozen=True)
class RailLine:
    line_number: int
    depth: int
    prefix: str
    body: str
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_number": self.line_number,
            "depth": self.depth,
            "prefix": self.prefix,
            "body": self.body,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class SpineSection:
    index: int
    level: int
    title: str
    normalized_title: str
    heading_text: str
    body: str
    raw: str
    sha256: str
    span: SourceSpan

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        value: dict[str, Any] = {
            "index": self.index,
            "level": self.level,
            "title": self.title,
            "normalized_title": self.normalized_title,
            "heading_text": self.heading_text,
            "body": self.body,
            "sha256": self.sha256,
            "span": self.span.to_dict(),
        }
        if include_raw:
            value["raw"] = self.raw
        return value


@dataclass(frozen=True)
class SpineDocument:
    source_name: str
    raw_text: str
    raw_bytes: bytes
    source_sha256: str
    header_text: str
    header_span: SourceSpan
    preamble: str
    sections: tuple[SpineSection, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def reconstruct_text(self) -> str:
        return self.raw_text

    def to_dict(
        self,
        *,
        include_raw: bool = False,
        include_section_raw: bool = False,
    ) -> dict[str, Any]:
        value: dict[str, Any] = {
            "type": PROTOCOL_TYPE,
            "version": PROTOCOL_VERSION,
            "source_name": self.source_name,
            "source_sha256": self.source_sha256,
            "header": {
                "text": self.header_text,
                "sha256": sha256_bytes(self.header_text.encode("utf-8")),
                "span": self.header_span.to_dict(),
            },
            "preamble": self.preamble,
            "sections": [
                section.to_dict(include_raw=include_section_raw)
                for section in self.sections
            ],
            "warnings": list(self.warnings),
        }
        if include_raw:
            value["raw_text"] = self.raw_text
        return value


def _find_header(text: str) -> tuple[str, SourceSpan]:
    match = HEADER_PATTERN.search(text[:5000])
    if match is None:
        raise SpineHeaderError(
            "Missing required canonical Holo/Sim recognition header."
        )
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    if line_end == -1:
        line_end = len(text)
    header_text = text[line_start:line_end]
    return header_text, SourceSpan(
        start_offset=line_start,
        end_offset=line_end,
        start_line=line_number_at(text, line_start),
        end_line=line_number_at(text, max(line_start, line_end - 1)),
    )


def parse_spine_text(text: str, *, source_name: str = "<memory>") -> SpineDocument:
    """Parse one Spine document without modifying or normalizing its source."""
    try:
        raw_bytes = text.encode("utf-8")
    except UnicodeError as exc:
        raise SpineStructureError("Spine source is not valid UTF-8 text.") from exc

    header_text, header_span = _find_header(text)
    matches = list(HEADING_PATTERN.finditer(text))
    sections: list[SpineSection] = []
    warnings: list[str] = []
    preamble = text[:matches[0].start()] if matches else text
    if not matches:
        warnings.append("No Markdown headings were found.")

    seen_titles: dict[str, int] = {}

    for index, match in enumerate(matches):
        section_start = match.start()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw = text[section_start:section_end]
        body = text[match.end():section_end]
        title = match.group(2).strip()
        normalized = normalize_heading(title)
        seen_titles[normalized] = seen_titles.get(normalized, 0) + 1

        sections.append(
            SpineSection(
                index=index,
                level=len(match.group(1)),
                title=title,
                normalized_title=normalized,
                heading_text=match.group(0),
                body=body,
                raw=raw,
                sha256=sha256_bytes(raw.encode("utf-8")),
                span=SourceSpan(
                    start_offset=section_start,
                    end_offset=section_end,
                    start_line=line_number_at(text, section_start),
                    end_line=line_number_at(text, max(section_start, section_end - 1)),
                ),
            )
        )

    duplicate_titles = sorted(k for k, v in seen_titles.items() if v > 1)
    if duplicate_titles:
        warnings.append("Duplicate normalized section titles: " + ", ".join(duplicate_titles))

    document = SpineDocument(
        source_name=source_name,
        raw_text=text,
        raw_bytes=raw_bytes,
        source_sha256=sha256_bytes(raw_bytes),
        header_text=header_text,
        header_span=header_span,
        preamble=preamble,
        sections=tuple(sections),
        warnings=tuple(warnings),
    )

    if document.reconstruct_text().encode("utf-8") != raw_bytes:
        raise SpineStructureError("Lossless source reconstruction failed.")
    return document


def parse_spine_file(path: str | Path) -> SpineDocument:
    resolved = Path(path)
    try:
        raw = resolved.read_bytes()
        text = raw.decode("utf-8")
    except OSError as exc:
        raise SpineStructureError(f"Unable to read Spine file: {exc}") from exc
    except UnicodeError as exc:
        raise SpineStructureError("Spine file is not valid UTF-8.") from exc

    document = parse_spine_text(text, source_name=resolved.as_posix())
    if document.raw_bytes != raw:
        raise SpineStructureError("Byte-for-byte round trip failed.")
    return document


def classify_rail_body(body: str) -> str:
    """Classify one rail-attached line without changing its source."""
    stripped = body.strip()

    if not stripped:
        return "empty"
    if RAIL_DIVIDER_PATTERN.fullmatch(stripped):
        return "divider"
    if RAIL_BORDER_PATTERN.fullmatch(stripped):
        return "border"
    return "content"


def analyze_rail_structure(text: str) -> dict[str, Any]:
    """Read visible Spine rails as structural metadata.

    The raw text remains canonical. This function reports rail attachment,
    nesting depth, dividers, and any non-empty line that falls off the rail
    after a rail-framed document has begun.
    """
    rail_lines: list[RailLine] = []
    unframed_lines: list[int] = []
    rail_started = False

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue

        match = RAIL_LINE_PATTERN.match(raw_line)
        if match is None:
            if rail_started:
                unframed_lines.append(line_number)
            continue

        rail_started = True
        prefix = match.group("prefix")
        body = match.group("body")
        rail_lines.append(
            RailLine(
                line_number=line_number,
                depth=prefix.count("|") + prefix.count("\u2502"),
                prefix=prefix,
                body=body,
                kind=classify_rail_body(body),
            )
        )

    divider_lines = [
        item.line_number
        for item in rail_lines
        if item.kind in {"divider", "border"}
    ]
    depths = [item.depth for item in rail_lines]

    return {
        "type": "holo_spine_rail_analysis",
        "version": PROTOCOL_VERSION,
        "rail_present": bool(rail_lines),
        "rail_line_count": len(rail_lines),
        "divider_lines": divider_lines,
        "depths": depths,
        "maximum_depth": max(depths, default=0),
        "unframed_lines_after_rail_start": unframed_lines,
        "continuous": bool(rail_lines) and not unframed_lines,
        "lines": [item.to_dict() for item in rail_lines],
        "interpretation_notice": (
            "Rail analysis is derived metadata. "
            "The raw Spine source remains canonical."
        ),
    }


def summarize_rail_analysis(analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact terminal-safe view of a full rail analysis."""
    divider_lines = list(analysis.get("divider_lines", []))
    depths = list(analysis.get("depths", []))
    unframed = list(analysis.get("unframed_lines_after_rail_start", []))

    depth_counts: dict[str, int] = {}
    for depth in depths:
        key = str(depth)
        depth_counts[key] = depth_counts.get(key, 0) + 1

    return {
        "type": analysis.get("type"),
        "version": analysis.get("version"),
        "rail_present": analysis.get("rail_present"),
        "continuous": analysis.get("continuous"),
        "rail_line_count": analysis.get("rail_line_count"),
        "divider_count": len(divider_lines),
        "maximum_depth": analysis.get("maximum_depth"),
        "depth_counts": depth_counts,
        "unframed_line_count": len(unframed),
        "unframed_lines_after_rail_start": unframed,
        "interpretation_notice": analysis.get("interpretation_notice"),
    }



def validate_rail_grammar(
    text: str,
    *,
    minimum_depth: int = 2,
) -> dict[str, Any]:
    """Validate rail serialization without rewriting or approving the source."""
    if minimum_depth < 1:
        raise ValueError("minimum_depth must be at least 1")

    analysis = analyze_rail_structure(text)
    rail_lines = {item["line_number"]: item for item in analysis["lines"]}
    violations: list[dict[str, Any]] = []
    depth_changes: list[dict[str, int]] = []
    previous_depth: int | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue

        item = rail_lines.get(line_number)
        if item is None:
            violations.append({
                "line": line_number,
                "kind": "detached_line",
                "observed_depth": 0,
                "required_depth": minimum_depth,
                "text": raw_line,
            })
            continue

        depth = int(item["depth"])
        if depth < minimum_depth:
            violations.append({
                "line": line_number,
                "kind": "insufficient_rail_depth",
                "observed_depth": depth,
                "required_depth": minimum_depth,
                "text": raw_line,
            })

        stripped_body = str(item["body"]).strip()
        if stripped_body.startswith("}=") and item["kind"] != "divider":
            violations.append({
                "line": line_number,
                "kind": "malformed_divider",
                "observed_depth": depth,
                "required_depth": minimum_depth,
                "text": raw_line,
            })

        if previous_depth is not None and depth != previous_depth:
            depth_changes.append({
                "line": line_number,
                "from_depth": previous_depth,
                "to_depth": depth,
            })
        previous_depth = depth

    counts: dict[str, int] = {}
    for violation in violations:
        kind = str(violation["kind"])
        counts[kind] = counts.get(kind, 0) + 1

    return {
        "type": "holo_spine_rail_validation",
        "version": PROTOCOL_VERSION,
        "valid": not violations,
        "minimum_depth": minimum_depth,
        "checked_nonempty_line_count": sum(
            1 for line in text.splitlines() if line.strip()
        ),
        "violation_count": len(violations),
        "violation_counts": counts,
        "violations": violations,
        "depth_changes": depth_changes,
        "source_sha256": sha256_bytes(text.encode("utf-8")),
        "write_authority": "NONE",
        "interpretation_notice": (
            "Validation is a read-only structural observation. "
            "It does not rewrite, repair, or approve the Spine."
        ),
    }


def _section_matches_label(section: SpineSection, labels: Sequence[str]) -> bool:
    return any(label in section.normalized_title for label in labels)


def _extract_list_items(section: SpineSection) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    base_line = section.span.start_line

    for offset, raw_line in enumerate(section.body.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped in {"---", "***", "___"}:
            continue
        cleaned = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", stripped).strip()
        if not cleaned:
            continue
        results.append({
            "text": cleaned,
            "section_index": section.index,
            "section_title": section.title,
            "source_line": base_line + offset,
        })
    return results


def reconstruct_frame(document: SpineDocument) -> dict[str, Any]:
    """Build a derived semantic frame while retaining source references."""
    rail = analyze_rail_structure(document.raw_text)
    boundaries: list[dict[str, Any]] = []
    semantic: dict[str, list[dict[str, Any]]] = {key: [] for key in SEMANTIC_LABELS}

    for section in document.sections:
        title_words = set(re.findall(r"[a-z0-9]+", section.normalized_title))
        matching_boundaries = sorted(BOUNDARY_NAMES.intersection(title_words))
        if matching_boundaries:
            boundaries.append({
                "names": matching_boundaries,
                "section_index": section.index,
                "section_title": section.title,
                "sha256": section.sha256,
                "span": section.span.to_dict(),
            })

        for key, labels in SEMANTIC_LABELS.items():
            if _section_matches_label(section, labels):
                semantic[key].extend(_extract_list_items(section))

    geometry_input = [
        {"index": s.index, "level": s.level, "title": s.normalized_title}
        for s in document.sections
    ]
    geometry_hash = sha256_bytes(json.dumps(
        geometry_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8"))

    return {
        "type": "holo_spine_reconstruction_frame",
        "version": PROTOCOL_VERSION,
        "source": {"name": document.source_name, "sha256": document.source_sha256},
        "header": {"text": document.header_text, "span": document.header_span.to_dict()},
        "rail": rail,
        "geometry": {
            "section_count": len(document.sections),
            "ordered_titles": [s.title for s in document.sections],
            "ordered_levels": [s.level for s in document.sections],
            "geometry_hash": geometry_hash,
        },
        "boundaries": boundaries,
        "semantic": semantic,
        "warnings": list(document.warnings),
        "interpretation_notice": (
            "This frame is derived from the canonical raw Spine source. "
            "It is not the source and does not replace it."
        ),
    }


def _occurrence_keys(
    sections: Iterable[SpineSection],
) -> list[tuple[str, int, SpineSection]]:
    counters: dict[str, int] = {}
    result: list[tuple[str, int, SpineSection]] = []
    for section in sections:
        count = counters.get(section.normalized_title, 0) + 1
        counters[section.normalized_title] = count
        result.append((section.normalized_title, count, section))
    return result


def _comparison_hash(section: SpineSection) -> str:
    """Hash section meaning for comparison without changing canonical source.

    Only boundary whitespace introduced by section movement is ignored.
    Internal text remains byte-significant.
    """
    comparable = section.heading_text.rstrip() + "\n" + section.body.strip()
    return sha256_bytes(comparable.encode("utf-8"))


def compare_spines(before: SpineDocument, after: SpineDocument) -> dict[str, Any]:
    """Compare two parsed Spine documents without modifying either source."""
    before_map = {(t, n): s for t, n, s in _occurrence_keys(before.sections)}
    after_map = {(t, n): s for t, n, s in _occurrence_keys(after.sections)}

    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    moved: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []

    for key in sorted(set(before_map) | set(after_map)):
        old = before_map.get(key)
        new = after_map.get(key)
        if old is None and new is not None:
            added.append(new.to_dict())
            continue
        if old is not None and new is None:
            removed.append(old.to_dict())
            continue
        assert old is not None and new is not None

        old_comparison_hash = _comparison_hash(old)
        new_comparison_hash = _comparison_hash(new)
        item = {
            "title": new.title,
            "occurrence": key[1],
            "before_index": old.index,
            "after_index": new.index,
            "before_sha256": old.sha256,
            "after_sha256": new.sha256,
            "before_comparison_hash": old_comparison_hash,
            "after_comparison_hash": new_comparison_hash,
        }
        if old_comparison_hash != new_comparison_hash:
            changed.append(item)
        elif old.index != new.index:
            moved.append(item)
        else:
            unchanged.append(item)

    before_frame = reconstruct_frame(before)
    after_frame = reconstruct_frame(after)
    before_uncertainty = {x["text"] for x in before_frame["semantic"]["uncertainty"]}
    after_uncertainty = {x["text"] for x in after_frame["semantic"]["uncertainty"]}

    return {
        "type": "holo_spine_comparison",
        "version": PROTOCOL_VERSION,
        "before": {
            "source_name": before.source_name,
            "sha256": before.source_sha256,
            "geometry_hash": before_frame["geometry"]["geometry_hash"],
        },
        "after": {
            "source_name": after.source_name,
            "sha256": after.source_sha256,
            "geometry_hash": after_frame["geometry"]["geometry_hash"],
        },
        "geometry_changed": (
            before_frame["geometry"]["geometry_hash"]
            != after_frame["geometry"]["geometry_hash"]
        ),
        "added": added,
        "removed": removed,
        "moved": moved,
        "changed": changed,
        "unchanged": unchanged,
        "uncertainty_lost": sorted(before_uncertainty - after_uncertainty),
        "source_changed": before.source_sha256 != after.source_sha256,
    }


def build_transfer_packet(document: SpineDocument) -> dict[str, Any]:
    """Create a deterministic, non-approving transfer packet."""
    frame = reconstruct_frame(document)
    packet_body = {
        "type": "holo_spine_transfer_packet",
        "version": PROTOCOL_VERSION,
        "source_name": document.source_name,
        "source_sha256": document.source_sha256,
        "raw_text": document.raw_text,
        "frame": frame,
        "section_hashes": [
            {"index": s.index, "title": s.title, "sha256": s.sha256}
            for s in document.sections
        ],
    }
    packet_hash = sha256_bytes(json.dumps(
        packet_body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8"))
    return {**packet_body, "packet_hash": packet_hash}


DESTINATION_FINDING_TYPE = "holo_destination_compatibility_finding"
DESTINATION_FINDING_VERSION = 1
DESTINATION_COMPARATORS = {"EXISTS", "EXACT_VALUE"}
DESTINATION_MAX_JSON_DEPTH = 100
_MISSING = object()


def _require_nonempty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpineStructureError(f"{field_name} must be a non-empty string")
    if value != value.strip():
        raise SpineStructureError(
            f"{field_name} must not contain surrounding whitespace"
        )
    return value


def _require_positive_int(value: Any, field_name: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
    ):
        raise SpineStructureError(f"{field_name} must be a positive integer")
    return value


def _resolve_structured_path(source: Mapping[str, Any], path: str) -> Any:
    """Resolve a dotted mapping path without interpreting free text."""
    current: Any = source
    for component in path.split("."):
        if not component or not isinstance(current, Mapping) or component not in current:
            return _MISSING
        current = current[component]
    return current


def _exact_structured_equal(actual: Any, expected: Any) -> bool:
    """Compare validated JSON values without Python's cross-type equality."""
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, Mapping):
        if set(actual) != set(expected):
            return False
        return all(
            _exact_structured_equal(actual[key], expected[key]) for key in actual
        )
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(
            _exact_structured_equal(left, right)
            for left, right in zip(actual, expected)
        )
    return bool(actual == expected)


def _validate_json_value(
    value: Any,
    field_name: str,
    *,
    _seen: set[int] | None = None,
    _depth: int = 0,
) -> None:
    """Require a closed JSON value model with string-only object keys."""
    if _depth > DESTINATION_MAX_JSON_DEPTH:
        raise SpineStructureError(f"{field_name} exceeds maximum JSON depth")
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise SpineStructureError(f"{field_name} contains a non-finite float")
        return
    if type(value) is list:
        seen = set() if _seen is None else _seen
        identity = id(value)
        if identity in seen:
            raise SpineStructureError(f"{field_name} contains a cyclic JSON value")
        seen.add(identity)
        try:
            for index, item in enumerate(value):
                _validate_json_value(
                    item,
                    f"{field_name}[{index}]",
                    _seen=seen,
                    _depth=_depth + 1,
                )
        finally:
            seen.remove(identity)
        return
    if type(value) is dict:
        seen = set() if _seen is None else _seen
        identity = id(value)
        if identity in seen:
            raise SpineStructureError(f"{field_name} contains a cyclic JSON value")
        seen.add(identity)
        try:
            for key, item in value.items():
                if not isinstance(key, str):
                    raise SpineStructureError(
                        f"{field_name} object keys must be strings"
                    )
                _validate_json_value(
                    item,
                    f"{field_name}.{key}",
                    _seen=seen,
                    _depth=_depth + 1,
                )
        finally:
            seen.remove(identity)
        return
    raise SpineStructureError(f"{field_name} contains a non-JSON value")


def _destination_bindings(
    source: Mapping[str, Any],
    destination_profile: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(source, Mapping):
        raise SpineStructureError("source must be a mapping")
    if not isinstance(destination_profile, Mapping):
        raise SpineStructureError("destination_profile must be a mapping")
    return (
        {
            "source_id": _require_nonempty_string(
                source.get("source_id"), "source_id"
            ),
            "source_version": _require_positive_int(
                source.get("source_version"), "source_version"
            ),
            "source_hash": _require_nonempty_string(
                source.get("source_hash"), "source_hash"
            ),
        },
        {
            "destination_id": _require_nonempty_string(
                destination_profile.get("destination_id"), "destination_id"
            ),
            "profile_version": _require_positive_int(
                destination_profile.get("profile_version"), "profile_version"
            ),
            "profile_hash": _require_nonempty_string(
                destination_profile.get("profile_hash"), "profile_hash"
            ),
        },
    )


def _validate_destination_inputs(
    source: Mapping[str, Any],
    destination_profile: Mapping[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[str],
]:
    """Validate the complete structured contract before evaluating any rule."""
    source_binding, profile_binding = _destination_bindings(
        source, destination_profile
    )

    fields = source.get("fields")
    if type(fields) is not dict:
        raise SpineStructureError("source.fields must be a JSON object")
    _validate_json_value(fields, "source.fields")

    raw_requirements = destination_profile.get("requirements")
    if not isinstance(raw_requirements, list) or not raw_requirements:
        raise SpineStructureError(
            "destination_profile.requirements must be a non-empty list"
        )

    normalized: list[dict[str, Any]] = []
    invalid_requirements: list[str] = []
    seen_ids: set[str] = set()
    for position, raw in enumerate(raw_requirements, start=1):
        if not isinstance(raw, Mapping):
            raise SpineStructureError(
                f"requirement at position {position} must be a mapping"
            )
        requirement_id = _require_nonempty_string(
            raw.get("id"), f"requirement {position} id"
        )
        if requirement_id in seen_ids:
            raise SpineStructureError(f"duplicate requirement id: {requirement_id}")
        seen_ids.add(requirement_id)

        comparator = _require_nonempty_string(
            raw.get("comparator"), f"requirement {requirement_id} comparator"
        )
        source_path = _require_nonempty_string(
            raw.get("source_path"), f"requirement {requirement_id} source_path"
        )
        if any(not component for component in source_path.split(".")):
            raise SpineStructureError(
                f"requirement {requirement_id} has an invalid source_path"
            )

        item = {
            "id": requirement_id,
            "comparator": comparator,
            "source_path": source_path,
        }
        if comparator not in DESTINATION_COMPARATORS:
            invalid_requirements.append(requirement_id)
            normalized.append(item)
            continue
        if comparator == "EXISTS":
            if raw.get("required") is not True:
                raise SpineStructureError(
                    f"EXISTS requirement {requirement_id} must declare required=true"
                )
            item["required"] = True
        else:
            if "expected" not in raw:
                raise SpineStructureError(
                    f"EXACT_VALUE requirement {requirement_id} lacks expected"
                )
            _validate_json_value(
                raw["expected"], f"requirement {requirement_id} expected"
            )
            item["expected"] = raw["expected"]
            unavailable_as = raw.get("unavailable_as")
            if unavailable_as is not None and unavailable_as != "UNCERTAIN":
                raise SpineStructureError(
                    f"requirement {requirement_id} has invalid unavailable_as"
                )
            if unavailable_as is not None:
                item["unavailable_as"] = unavailable_as
        normalized.append(item)

    return source_binding, profile_binding, normalized, invalid_requirements


def _finalize_destination_finding(body: Mapping[str, Any]) -> dict[str, Any]:
    try:
        canonical = json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SpineStructureError(
            "destination finding must be canonically JSON-serializable"
        ) from exc
    return {**body, "finding_hash": sha256_bytes(canonical)}


def _validate_destination_finding_integrity(
    finding: Mapping[str, Any],
) -> None:
    """Verify finding integrity and enforce its non-authorizing schema."""
    if type(finding) is not dict:
        raise SpineStructureError("finding must be a JSON object")
    _validate_json_value(finding, "finding")
    if finding.get("type") != DESTINATION_FINDING_TYPE:
        raise SpineStructureError("unsupported destination finding type")
    _require_positive_int(finding.get("version"), "finding version")
    if finding["version"] != DESTINATION_FINDING_VERSION:
        raise SpineStructureError("unsupported destination finding version")
    for key in ("source_version", "profile_version"):
        _require_positive_int(finding.get(key), f"finding {key}")
    for key in (
        "source_id",
        "source_hash",
        "destination_id",
        "profile_hash",
    ):
        _require_nonempty_string(finding.get(key), f"finding {key}")

    supplied_hash = _require_nonempty_string(
        finding.get("finding_hash"), "finding_hash"
    )
    if re.fullmatch(r"[0-9a-f]{64}", supplied_hash) is None:
        raise SpineStructureError("finding_hash must be 64 lowercase hex characters")
    body = dict(finding)
    body.pop("finding_hash", None)
    expected = _finalize_destination_finding(body)["finding_hash"]
    if not hmac.compare_digest(supplied_hash, expected):
        raise SpineStructureError("destination finding hash mismatch")

    partitions: list[list[str]] = []
    for key in (
        "verified_requirements",
        "missing_requirements",
        "conflicts",
        "uncertain",
        "invalid_requirements",
    ):
        values = finding.get(key)
        if (
            not isinstance(values, list)
            or any(not isinstance(item, str) or not item for item in values)
            or len(values) != len(set(values))
        ):
            raise SpineStructureError(f"finding {key} must contain unique ids")
        partitions.append(values)
    flattened = [item for values in partitions for item in values]
    if len(flattened) != len(set(flattened)):
        raise SpineStructureError("finding partitions overlap")

    if type(finding.get("compatible")) is not bool:
        raise SpineStructureError("finding compatible must be boolean")
    expected_compatible = not any(partitions[1:])
    if finding["compatible"] is not expected_compatible:
        raise SpineStructureError("finding compatible contradicts partitions")
    if finding.get("accepted") is not False:
        raise SpineStructureError("destination finding cannot grant acceptance")
    if finding.get("write_authority") != "NONE":
        raise SpineStructureError("destination finding cannot grant write authority")
    if finding.get("finding_current") is not True:
        raise SpineStructureError("stored destination finding must begin current")
    if finding.get("stale_reason") is not None:
        raise SpineStructureError("current destination finding cannot be stale")
    if finding["invalid_requirements"]:
        if finding.get("profile_status") != "INVALID_PROFILE":
            raise SpineStructureError("invalid requirements need INVALID_PROFILE")
    elif "profile_status" in finding:
        raise SpineStructureError("valid profile cannot report INVALID_PROFILE")


def evaluate_destination_compatibility(
    source: Mapping[str, Any],
    destination_profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate a structured source against a deterministic destination profile.

    Compatibility is descriptive only. This function never accepts a transfer,
    persists a finding, mutates a destination, or grants write authority.
    """
    (
        source_binding,
        profile_binding,
        requirements,
        invalid_requirements,
    ) = _validate_destination_inputs(source, destination_profile)

    if invalid_requirements:
        invalid_body = {
            "type": DESTINATION_FINDING_TYPE,
            "version": DESTINATION_FINDING_VERSION,
            **source_binding,
            **profile_binding,
            "profile_status": "INVALID_PROFILE",
            "verified_requirements": [],
            "missing_requirements": [],
            "conflicts": [],
            "uncertain": [],
            "invalid_requirements": invalid_requirements,
            "compatible": False,
            "accepted": False,
            "write_authority": "NONE",
            "finding_current": True,
            "stale_reason": None,
        }
        return _finalize_destination_finding(invalid_body)

    fields = source["fields"]
    verified: list[str] = []
    missing: list[str] = []
    conflicts: list[str] = []
    uncertain: list[str] = []

    for requirement in requirements:
        requirement_id = requirement["id"]
        actual = _resolve_structured_path(fields, requirement["source_path"])
        if actual is _MISSING:
            missing.append(requirement_id)
        elif requirement["comparator"] == "EXISTS":
            verified.append(requirement_id)
        elif (
            actual == "UNAVAILABLE"
            and requirement.get("unavailable_as") == "UNCERTAIN"
        ):
            uncertain.append(requirement_id)
        elif _exact_structured_equal(actual, requirement["expected"]):
            verified.append(requirement_id)
        else:
            conflicts.append(requirement_id)

    compatible = not (missing or conflicts or uncertain)
    finding_body = {
        "type": DESTINATION_FINDING_TYPE,
        "version": DESTINATION_FINDING_VERSION,
        **source_binding,
        **profile_binding,
        "verified_requirements": verified,
        "missing_requirements": missing,
        "conflicts": conflicts,
        "uncertain": uncertain,
        "invalid_requirements": [],
        "compatible": compatible,
        "accepted": False,
        "write_authority": "NONE",
        "finding_current": True,
        "stale_reason": None,
    }
    return _finalize_destination_finding(finding_body)


def check_destination_finding_current(
    finding: Mapping[str, Any],
    source: Mapping[str, Any],
    destination_profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Check whether a prior finding still binds the exact current inputs."""
    _validate_destination_finding_integrity(finding)
    source_binding, profile_binding, _, _ = _validate_destination_inputs(
        source, destination_profile
    )

    for key in ("source_id", "source_version", "source_hash"):
        if finding.get(key) != source_binding[key]:
            return {"finding_current": False, "stale_reason": "SOURCE_CHANGED"}
    for key in ("destination_id", "profile_version", "profile_hash"):
        if finding.get(key) != profile_binding[key]:
            return {
                "finding_current": False,
                "stale_reason": "DESTINATION_PROFILE_CHANGED",
            }
    expected_finding = evaluate_destination_compatibility(
        source, destination_profile
    )
    if not _exact_structured_equal(finding, expected_finding):
        raise SpineStructureError(
            "destination finding does not match current evaluation"
        )
    return {"finding_current": True, "stale_reason": None}


def run_self_test() -> None:
    header = (
        "|===========================================|\n"
        "| █†█ Holo/Sim █†█ █†█ HSSCE █†█ |\n"
        "|===========================================|\n"
    )
    original = (
        header
        + "\n# Purpose\nPreserve reconstruction.\n"
        + "\n# Uncertainty Boundary\n- Unknown origin remains unresolved.\n"
        + "\n# Evidence\n- artifact-a\n"
    )
    revised = (
        header
        + "\n# Purpose\nPreserve compatible reconstruction.\n"
        + "\n# Evidence\n- artifact-a\n"
        + "\n# Uncertainty Boundary\n- Unknown origin remains unresolved.\n"
        + "\n# Correction\n- Purpose wording refined.\n"
    )

    first = parse_spine_text(original, source_name="original.md")
    second = parse_spine_text(revised, source_name="revised.md")

    assert first.reconstruct_text() == original
    assert first.raw_bytes == original.encode("utf-8")
    assert len(first.sections) == 3

    frame = reconstruct_frame(first)
    assert frame["geometry"]["section_count"] == 3
    assert frame["rail"]["rail_present"] is True
    assert frame["semantic"]["uncertainty"]
    assert frame["boundaries"][0]["names"] == ["uncertainty"]

    comparison = compare_spines(first, second)
    assert comparison["geometry_changed"] is True
    assert any(item["title"] == "Evidence" for item in comparison["moved"])
    assert any(item["title"] == "Purpose" for item in comparison["changed"])
    assert any(item["title"] == "Correction" for item in comparison["added"])
    assert comparison["uncertainty_lost"] == []

    packet = build_transfer_packet(first)
    assert packet["source_sha256"] == first.source_sha256
    assert len(packet["packet_hash"]) == 64

    destination_source = {
        "source_id": "source-spine-alpha",
        "source_version": 1,
        "source_hash": "fixture-source-hash-alpha-v1",
        "fields": {
            "document_type": "HOLO_CONTINUITY_SPINE",
            "protocol_version": 1,
            "sections": {"IDENTITY": {"present": True}},
            "evidence": {"content_support": "UNAVAILABLE"},
        },
    }
    mixed_profile = {
        "destination_id": "destination-beta",
        "profile_version": 1,
        "profile_hash": "fixture-profile-hash-beta-v1",
        "requirements": [
            {
                "id": "R1",
                "comparator": "EXISTS",
                "source_path": "sections.IDENTITY.present",
                "required": True,
            },
            {
                "id": "R2",
                "comparator": "EXACT_VALUE",
                "source_path": "document_type",
                "expected": "HOLO_CONTINUITY_SPINE",
            },
            {
                "id": "R3",
                "comparator": "EXISTS",
                "source_path": "sections.AUTHORITY.present",
                "required": True,
            },
            {
                "id": "R4",
                "comparator": "EXACT_VALUE",
                "source_path": "protocol_version",
                "expected": 2,
            },
            {
                "id": "R5",
                "comparator": "EXACT_VALUE",
                "source_path": "evidence.content_support",
                "expected": "VERIFIED",
                "unavailable_as": "UNCERTAIN",
            },
        ],
    }
    mixed_finding = evaluate_destination_compatibility(
        destination_source, mixed_profile
    )
    assert mixed_finding["verified_requirements"] == ["R1", "R2"]
    assert mixed_finding["missing_requirements"] == ["R3"]
    assert mixed_finding["conflicts"] == ["R4"]
    assert mixed_finding["uncertain"] == ["R5"]
    assert mixed_finding["compatible"] is False
    assert mixed_finding["accepted"] is False
    assert mixed_finding["write_authority"] == "NONE"

    compatible_profile = {
        "destination_id": "destination-gamma-compatible",
        "profile_version": 1,
        "profile_hash": "fixture-profile-hash-gamma-v1",
        "requirements": mixed_profile["requirements"][:2],
    }
    compatible_finding = evaluate_destination_compatibility(
        destination_source, compatible_profile
    )
    assert compatible_finding["verified_requirements"] == ["R1", "R2"]
    assert compatible_finding["compatible"] is True
    assert compatible_finding["accepted"] is False
    assert compatible_finding["write_authority"] == "NONE"

    changed_source = dict(destination_source)
    changed_source["source_hash"] = "fixture-source-hash-alpha-v2"
    assert check_destination_finding_current(
        mixed_finding, changed_source, mixed_profile
    ) == {"finding_current": False, "stale_reason": "SOURCE_CHANGED"}

    changed_profile = dict(mixed_profile)
    changed_profile["profile_hash"] = "fixture-profile-hash-beta-v2"
    assert check_destination_finding_current(
        mixed_finding, destination_source, changed_profile
    ) == {
        "finding_current": False,
        "stale_reason": "DESTINATION_PROFILE_CHANGED",
    }

    malformed_profile = dict(mixed_profile)
    malformed_profile["requirements"] = [{
        "id": "MX1",
        "comparator": "MODEL_JUDGED_SIMILARITY",
        "source_path": "document_type",
        "expected": "approximately a continuity document",
    }]
    malformed_finding = evaluate_destination_compatibility(
        destination_source, malformed_profile
    )
    assert malformed_finding["profile_status"] == "INVALID_PROFILE"
    assert malformed_finding["invalid_requirements"] == ["MX1"]
    assert malformed_finding["compatible"] is False
    assert malformed_finding["accepted"] is False
    assert malformed_finding["write_authority"] == "NONE"
    assert check_destination_finding_current(
        malformed_finding, destination_source, malformed_profile
    ) == {"finding_current": True, "stale_reason": None}

    typed_source = dict(destination_source)
    typed_source["fields"] = dict(destination_source["fields"])
    typed_source["fields"]["typed_value"] = True
    typed_profile = dict(compatible_profile)
    typed_profile["requirements"] = [{
        "id": "TYPE",
        "comparator": "EXACT_VALUE",
        "source_path": "typed_value",
        "expected": 1,
    }]
    typed_finding = evaluate_destination_compatibility(
        typed_source, typed_profile
    )
    assert typed_finding["conflicts"] == ["TYPE"]

    tampered_finding = dict(mixed_finding)
    tampered_finding["accepted"] = True
    try:
        check_destination_finding_current(
            tampered_finding, destination_source, mixed_profile
        )
    except SpineStructureError:
        pass
    else:
        raise AssertionError("Tampered finding did not fail integrity validation.")

    non_json_source = dict(destination_source)
    non_json_source["fields"] = dict(destination_source["fields"])
    non_json_source["fields"]["typed_value"] = {True: "x"}
    try:
        evaluate_destination_compatibility(non_json_source, typed_profile)
    except SpineStructureError:
        pass
    else:
        raise AssertionError("Non-JSON object key did not fail closed.")

    forged_body = dict(mixed_finding)
    forged_body.pop("finding_hash")
    forged_body["conflicts"] = []
    forged_body["missing_requirements"] = ["R3", "R4"]
    forged_finding = _finalize_destination_finding(forged_body)
    try:
        check_destination_finding_current(
            forged_finding, destination_source, mixed_profile
        )
    except SpineStructureError:
        pass
    else:
        raise AssertionError("Rehashed semantic forgery did not fail closed.")

    padded_source = dict(destination_source)
    padded_source["source_hash"] = f" {destination_source['source_hash']} "
    try:
        check_destination_finding_current(
            mixed_finding, padded_source, mixed_profile
        )
    except SpineStructureError:
        pass
    else:
        raise AssertionError("Whitespace-modified binding did not fail closed.")

    padded_finding_hash = dict(mixed_finding)
    padded_finding_hash["finding_hash"] = (
        f" {mixed_finding['finding_hash']} "
    )
    try:
        check_destination_finding_current(
            padded_finding_hash, destination_source, mixed_profile
        )
    except SpineStructureError:
        pass
    else:
        raise AssertionError("Padded finding hash did not fail closed.")

    cyclic_source = dict(destination_source)
    cyclic_source["fields"] = dict(destination_source["fields"])
    cyclic_value: dict[str, Any] = {}
    cyclic_value["self"] = cyclic_value
    cyclic_source["fields"]["cyclic"] = cyclic_value
    try:
        evaluate_destination_compatibility(cyclic_source, mixed_profile)
    except SpineStructureError:
        pass
    else:
        raise AssertionError("Cyclic JSON value did not fail closed.")

    deep_source = dict(destination_source)
    deep_source["fields"] = dict(destination_source["fields"])
    nested_value: dict[str, Any] = {}
    current_value = nested_value
    for _ in range(102):
        child_value: dict[str, Any] = {}
        current_value["next"] = child_value
        current_value = child_value
    deep_source["fields"]["deep"] = nested_value
    try:
        evaluate_destination_compatibility(deep_source, mixed_profile)
    except SpineStructureError:
        pass
    else:
        raise AssertionError("Excessive JSON depth did not fail closed.")

    rail_source = (
        "|===============================|\n"
        "| █†█ Holo/Sim █†█              |\n"
        "| }=============================|\n"
        "| | FRAME_ID: test-frame\n"
        "| | INPUT: source-a\n"
        "| | VERIFICATION: pending\n"
        "| }=============================|\n"
    )
    rail_analysis = analyze_rail_structure(rail_source)
    assert rail_analysis["rail_present"] is True
    assert rail_analysis["continuous"] is True
    assert rail_analysis["maximum_depth"] == 2
    assert rail_analysis["unframed_lines_after_rail_start"] == []
    assert any(item["kind"] == "divider" for item in rail_analysis["lines"])

    broken_rail_source = (
        "|===============================|\n"
        "| | FRAME_ID: broken\n"
        "THIS LINE FELL OFF THE RAIL\n"
        "| | OUTPUT: none\n"
    )
    broken_analysis = analyze_rail_structure(broken_rail_source)
    assert broken_analysis["continuous"] is False
    assert broken_analysis["unframed_lines_after_rail_start"] == [3]

    rail_validation = validate_rail_grammar(rail_source)
    assert rail_validation["valid"] is False
    assert rail_validation["violation_counts"]["insufficient_rail_depth"] == 4

    valid_two_bar_source = (
        "| |=============================|\\n"
        "| | █†█ Holo/Sim █†█            |\\n"
        "| | }===========================|\\n"
        "| | FRAME_ID: valid-frame\\n"
    )
    valid_two_bar_result = validate_rail_grammar(valid_two_bar_source)
    assert valid_two_bar_result["valid"] is True
    assert valid_two_bar_result["violations"] == []

    rail_summary = summarize_rail_analysis(rail_analysis)
    assert rail_summary["continuous"] is True
    assert rail_summary["rail_line_count"] == len(rail_analysis["lines"])
    assert rail_summary["unframed_line_count"] == 0
    assert "lines" not in rail_summary

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "Spine.md"
        path.write_bytes(original.encode("utf-8"))
        parsed = parse_spine_file(path)
        assert parsed.raw_bytes == original.encode("utf-8")

    try:
        parse_spine_text("# Missing Header\nNo protocol marker.")
    except SpineHeaderError:
        pass
    else:
        raise AssertionError("Missing header was not rejected.")

    print("✅ Spine protocol self-test passed.")


def _print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only, lossless Holo/Sim Spine protocol engine."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse")
    parse_parser.add_argument("file")
    parse_parser.add_argument("--include-raw", action="store_true")

    reconstruct_parser = subparsers.add_parser("reconstruct")
    reconstruct_parser.add_argument("file")

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("before")
    compare_parser.add_argument("after")

    transfer_parser = subparsers.add_parser("transfer")
    transfer_parser.add_argument("file")

    rail_parser = subparsers.add_parser(
        "rail",
        help="Analyze visible Spine rails without rewriting the source.",
    )
    rail_parser.add_argument("file")
    rail_parser.add_argument(
        "--include-lines",
        action="store_true",
        help="Include every parsed rail line. Default output is a compact summary.",
    )

    rail_validate_parser = subparsers.add_parser(
        "rail-validate",
        help="Validate the strict rail grammar without rewriting the source.",
    )
    rail_validate_parser.add_argument("file")
    rail_validate_parser.add_argument(
        "--minimum-depth",
        type=int,
        default=2,
        help="Required visible rail bars per non-empty line. Default: 2.",
    )

    subparsers.add_parser("self-test")

    args = parser.parse_args()

    try:
        if args.command == "parse":
            doc = parse_spine_file(args.file)
            _print_json(doc.to_dict(
                include_raw=args.include_raw,
                include_section_raw=args.include_raw,
            ))
        elif args.command == "reconstruct":
            _print_json(reconstruct_frame(parse_spine_file(args.file)))
        elif args.command == "compare":
            _print_json(compare_spines(
                parse_spine_file(args.before),
                parse_spine_file(args.after),
            ))
        elif args.command == "transfer":
            _print_json(build_transfer_packet(parse_spine_file(args.file)))
        elif args.command == "rail":
            document = parse_spine_file(args.file)
            analysis = analyze_rail_structure(document.raw_text)
            _print_json(
                analysis if args.include_lines else summarize_rail_analysis(analysis)
            )
        elif args.command == "rail-validate":
            document = parse_spine_file(args.file)
            result = validate_rail_grammar(
                document.raw_text,
                minimum_depth=args.minimum_depth,
            )
            _print_json(result)
            if not result["valid"]:
                raise SystemExit(2)
        elif args.command == "self-test":
            run_self_test()
        else:
            raise SystemExit(f"Unknown command: {args.command}")
    except SpineProtocolError as exc:
        print(f"Spine protocol: FAIL\n{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
