"""Read-only organization of collected invariant candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


CATALOG_TYPE = "holo_invariant_catalog_proposal"
CATALOG_VERSION = 1

_NUMBERED_ENTRY = re.compile(r"^(\d+)\.\s*(.+)$")

_IGNORED_OUTSIDE_LINES = {
    "List Known Invariants.",
}

_SECTION_PREFIXES = (
    "Additional/Missing",
    "Other Invariants",
    "Broader Invariants",
    "Notes Sections",
    "Here are additional",
    "Continuing the list",
)


def _strip_spine_prefix(line: str) -> str:
    value = line.strip()
    while value.startswith("|"):
        value = value[1:].lstrip()
    return value


def _is_divider(value: str) -> bool:
    return bool(value) and all(
        character in "=|-}{" for character in value
    )


def _looks_like_section_boundary(value: str) -> bool:
    if value.startswith(_SECTION_PREFIXES):
        return True
    return bool(re.match(r"^Pass\s+\d+\b", value))


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _normalized_statement(value: str) -> str:
    return _collapse_whitespace(value).casefold()


def inspect_invariant_text(
    text: str,
    *,
    source: str,
) -> dict[str, Any]:
    """Inspect structured candidates and retain unparsed regions."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")

    candidates: list[dict[str, Any]] = []
    unparsed_regions: list[dict[str, Any]] = []

    current_number: int | None = None
    current_parts: list[str] = []

    region_start: int | None = None
    region_end: int | None = None
    region_parts: list[str] = []

    def finish_candidate() -> None:
        nonlocal current_number, current_parts

        if current_number is None:
            return

        statement = _collapse_whitespace(
            " ".join(current_parts)
        )
        if statement:
            candidates.append(
                {
                    "source": source,
                    "source_number": current_number,
                    "statement": statement,
                }
            )

        current_number = None
        current_parts = []

    def finish_region() -> None:
        nonlocal region_start, region_end, region_parts

        if region_start is None or region_end is None:
            return

        unparsed_regions.append(
            {
                "source": source,
                "start_line": region_start,
                "end_line": region_end,
                "text": "\n".join(region_parts),
            }
        )

        region_start = None
        region_end = None
        region_parts = []

    def add_unparsed(line_number: int, value: str) -> None:
        nonlocal region_start, region_end

        if region_start is None:
            region_start = line_number
        region_end = line_number
        region_parts.append(value)

    for line_number, raw_line in enumerate(
        text.splitlines(),
        start=1,
    ):
        value = _strip_spine_prefix(raw_line)

        if not value:
            finish_candidate()
            finish_region()
            continue

        if _is_divider(value):
            finish_candidate()
            finish_region()
            continue

        match = _NUMBERED_ENTRY.match(value)
        if match:
            finish_candidate()
            finish_region()

            current_number = int(match.group(1))
            current_parts = [match.group(2)]
            continue

        if (
            current_number is not None
            and not _looks_like_section_boundary(value)
        ):
            current_parts.append(value)
            continue

        if current_number is not None:
            finish_candidate()

        if value in _IGNORED_OUTSIDE_LINES:
            finish_region()
            continue

        add_unparsed(line_number, value)

    finish_candidate()
    finish_region()

    warnings: list[dict[str, Any]] = []
    if unparsed_regions:
        warnings.append(
            {
                "code": "UNPARSED_CONTENT",
                "source": source,
                "region_count": len(unparsed_regions),
            }
        )

    return {
        "source": source,
        "candidates": candidates,
        "parse_complete": not unparsed_regions,
        "parse_warnings": warnings,
        "unparsed_regions": unparsed_regions,
    }


def extract_numbered_invariants(
    text: str,
    *,
    source: str,
) -> list[dict[str, Any]]:
    """Extract only bounded numbered invariant candidates."""
    inspection = inspect_invariant_text(
        text,
        source=source,
    )
    return inspection["candidates"]


def _classify_domain(
    statement: str,
) -> tuple[str, str]:
    value = statement.casefold()

    logic_terms = (
        "non-contradiction",
        "proposition",
        "logical",
        "zfc",
        "axiom",
        "proof",
        "provability",
    )
    mathematics_terms = (
        "theorem",
        "integer",
        "prime",
        "matrix",
        "vector space",
        "factorization",
        "arithmetic",
        "algebra",
        "topological",
        "homotopy",
    )
    physics_terms = (
        "energy",
        "momentum",
        "charge",
        "relativ",
        "light",
        "thermodynamic",
        "quantum",
        "particle",
        "spacetime",
        "lorentz",
        "mass",
    )
    computation_terms = (
        "algorithm",
        "computation",
        "information",
        "software",
        "program",
        "data structure",
        "binary search",
        "linear search",
        "sorting",
        "insertion sort",
        "selection sort",
        "quicksort",
        "factorial",
        "processed prefix",
        "loop invariant",
    )

    if any(term in value for term in logic_terms):
        return (
            "logic_epistemology",
            "docs/Logic_Epistemology_Spine.md",
        )
    if any(term in value for term in mathematics_terms):
        return (
            "mathematics",
            "docs/Mathematics_Spine.md",
        )
    if any(term in value for term in physics_terms):
        return (
            "physics",
            "docs/Physics_Spine.md",
        )
    if any(term in value for term in computation_terms):
        return (
            "computation_systems",
            "docs/Computation_Systems_Spine.md",
        )

    return (
        "unclassified",
        "docs/Invariant_Archive.md",
    )


def _classify_kind(statement: str) -> str:
    value = statement.casefold()

    if "conservation" in value or "conserved" in value:
        return "conservation"
    if (
        "non-contradiction" in value
        or "proposition" in value
        or "logical" in value
    ):
        return "logical"
    if "theorem" in value:
        return "theorem"
    if "symmetry" in value or "invariance" in value:
        return "symmetry"
    if "constant" in value or "unchanged" in value:
        return "preservation"
    if (
        "sort" in value
        or "search" in value
        or "processed prefix" in value
        or "iteration" in value
    ):
        return "algorithmic"

    return "unclassified"


def _candidate_id(
    *,
    source: str,
    source_number: int,
    statement: str,
) -> str:
    identity = (
        f"{source}\0{source_number}\0"
        f"{_normalized_statement(statement)}"
    )
    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def organize_invariants(
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic proposal without canonical mutation."""
    if isinstance(candidates, (str, bytes)) or not isinstance(
        candidates,
        Sequence,
    ):
        raise TypeError("candidates must be a sequence")

    organized: list[dict[str, Any]] = []
    first_by_statement: dict[str, str] = {}

    for index, candidate in enumerate(candidates):
        source = candidate.get("source")
        source_number = candidate.get("source_number")
        statement = candidate.get("statement")

        if not isinstance(source, str) or not source.strip():
            raise ValueError(
                f"candidates[{index}].source is invalid"
            )
        if (
            not isinstance(source_number, int)
            or isinstance(source_number, bool)
            or source_number < 1
        ):
            raise ValueError(
                f"candidates[{index}].source_number is invalid"
            )
        if (
            not isinstance(statement, str)
            or not statement.strip()
        ):
            raise ValueError(
                f"candidates[{index}].statement is invalid"
            )

        statement = _collapse_whitespace(statement)
        normalized = _normalized_statement(statement)
        candidate_id = _candidate_id(
            source=source,
            source_number=source_number,
            statement=statement,
        )
        domain, destination = _classify_domain(statement)

        duplicate_of = first_by_statement.get(normalized)
        if duplicate_of is None:
            first_by_statement[normalized] = candidate_id

        organized.append(
            {
                "candidate_id": candidate_id,
                "source": source,
                "source_number": source_number,
                "statement": statement,
                "domain": domain,
                "kind": _classify_kind(statement),
                "proposed_destination": destination,
                "status": "candidate",
                "duplicate_of": duplicate_of,
            }
        )

    duplicate_count = sum(
        item["duplicate_of"] is not None
        for item in organized
    )

    catalog: dict[str, Any] = {
        "type": CATALOG_TYPE,
        "version": CATALOG_VERSION,
        "candidate_count": len(organized),
        "unique_count": len(organized) - duplicate_count,
        "duplicate_count": duplicate_count,
        "candidates": organized,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "canonical_mutation": False,
    }
    catalog["catalog_hash"] = _canonical_hash(catalog)
    return catalog


def catalog_invariant_files(
    paths: Sequence[str | Path],
) -> dict[str, Any]:
    """Read Markdown sources and build a non-mutating proposal."""
    if isinstance(paths, (str, bytes)) or not isinstance(
        paths,
        Sequence,
    ):
        raise TypeError("paths must be a sequence")

    source_files: list[str] = []
    candidates: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    unparsed_regions: list[dict[str, Any]] = []

    for index, supplied_path in enumerate(paths):
        if not isinstance(supplied_path, (str, Path)):
            raise TypeError(
                f"paths[{index}] must be a path"
            )

        path = Path(supplied_path)
        source = str(path)
        text = path.read_text(encoding="utf-8")
        inspection = inspect_invariant_text(
            text,
            source=source,
        )

        source_files.append(source)
        candidates.extend(inspection["candidates"])
        warnings.extend(inspection["parse_warnings"])
        unparsed_regions.extend(
            inspection["unparsed_regions"]
        )

    catalog = organize_invariants(candidates)
    catalog.pop("catalog_hash")
    catalog["source_files"] = source_files
    catalog["parse_complete"] = not unparsed_regions
    catalog["parse_warnings"] = warnings
    catalog["unparsed_regions"] = unparsed_regions
    catalog["catalog_hash"] = _canonical_hash(catalog)
    return catalog


def render_catalog_markdown(
    catalog: Mapping[str, Any],
) -> str:
    """Render a bounded human-review surface."""
    candidates = catalog.get("candidates")
    if (
        isinstance(candidates, (str, bytes))
        or not isinstance(candidates, Sequence)
    ):
        raise ValueError("catalog candidates are invalid")

    grouped: dict[str, list[Mapping[str, Any]]] = {}

    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("catalog candidate is invalid")

        destination = candidate.get(
            "proposed_destination"
        )
        if (
            not isinstance(destination, str)
            or not destination
        ):
            raise ValueError(
                "candidate proposed_destination is invalid"
            )

        grouped.setdefault(
            destination,
            [],
        ).append(candidate)

    lines = [
        "# Invariant Catalog Proposal",
        "",
        (
            "This report does not promote canonical "
            "knowledge."
        ),
        "",
        f"Candidates: `{catalog.get('candidate_count', 0)}`",
        f"Unique: `{catalog.get('unique_count', 0)}`",
        f"Duplicates: `{catalog.get('duplicate_count', 0)}`",
        (
            "Parse complete: "
            f"`{catalog.get('parse_complete', True)}`"
        ),
        "Write authority: `NONE`",
        "",
    ]

    warnings = catalog.get("parse_warnings", [])
    if warnings:
        lines.extend(
            [
                "## Parse warnings",
                "",
            ]
        )
        for warning in warnings:
            lines.append(
                f"- `{warning['code']}` in "
                f"`{warning['source']}`: "
                f"{warning['region_count']} unparsed "
                "region(s)"
            )
        lines.append("")

    regions = catalog.get("unparsed_regions", [])
    if regions:
        lines.extend(
            [
                "## Unparsed legacy regions",
                "",
            ]
        )
        for region in regions:
            lines.extend(
                [
                    (
                        f"### {region['source']} lines "
                        f"{region['start_line']}-"
                        f"{region['end_line']}"
                    ),
                    "",
                    "```text",
                    region["text"],
                    "```",
                    "",
                ]
            )

    for destination in sorted(grouped):
        lines.extend(
            [
                f"## {destination}",
                "",
            ]
        )

        for candidate in grouped[destination]:
            lines.extend(
                [
                    (
                        "### Candidate "
                        f"{candidate['candidate_id'][:12]}"
                    ),
                    "",
                    f"**Status:** {candidate['status']}",
                    f"**Kind:** {candidate['kind']}",
                    (
                        "**Source:** "
                        f"`{candidate['source']}` "
                        f"entry "
                        f"`{candidate['source_number']}`"
                    ),
                ]
            )

            duplicate_of = candidate.get("duplicate_of")
            if duplicate_of is not None:
                lines.append(
                    f"**Duplicate of:** `{duplicate_of}`"
                )

            lines.extend(
                [
                    "",
                    candidate["statement"],
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"

def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only invariant catalog proposal."
        )
    )
    parser.add_argument(
        "sources",
        nargs="+",
        help="Markdown candidate source files",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Proposal output format",
    )
    parser.add_argument(
        "--output",
        help="Optional proposal output file",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the read-only invariant catalog command."""
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    source_paths = [
        Path(source)
        for source in args.sources
    ]

    output_path = (
        Path(args.output)
        if args.output is not None
        else None
    )

    if output_path is not None:
        resolved_output = output_path.resolve()
        if any(
            source.resolve() == resolved_output
            for source in source_paths
        ):
            print(
                "Invariant catalog refused to overwrite "
                "a source file.",
                file=sys.stderr,
            )
            return 2

    try:
        catalog = catalog_invariant_files(source_paths)

        if args.format == "json":
            rendered = (
                json.dumps(
                    catalog,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            )
        else:
            rendered = render_catalog_markdown(catalog)

        if output_path is None:
            print(rendered, end="")
        else:
            output_path.write_text(
                rendered,
                encoding="utf-8",
            )
    except (
        OSError,
        UnicodeError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"Invariant catalog failed: {exc}",
            file=sys.stderr,
        )
        return 2

    if catalog["parse_complete"] is not True:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
