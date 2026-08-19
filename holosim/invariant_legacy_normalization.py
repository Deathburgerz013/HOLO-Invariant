"""Lossless review chunks for unparsed invariant material."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from holosim.invariant_catalog import (
    catalog_invariant_files,
)


NORMALIZATION_TYPE = (
    "holo_invariant_legacy_normalization"
)
NORMALIZATION_VERSION = 1
DEFAULT_MAX_CHUNK_CHARS = 1200


class LegacyNormalizationError(ValueError):
    """Raised when legacy normalization loses integrity."""


def _canonical_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
        OverflowError,
        UnicodeError,
    ) as exc:
        raise LegacyNormalizationError(
            "legacy normalization could not be hashed"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def _text_hash(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _require_string(
    value: Any,
    field: str,
) -> str:
    if not isinstance(value, str) or not value:
        raise LegacyNormalizationError(
            f"{field} must be a non-empty string"
        )
    return value


def _require_positive_integer(
    value: Any,
    field: str,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
    ):
        raise LegacyNormalizationError(
            f"{field} must be a positive integer"
        )
    return value


def _validate_region(
    region: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    if not isinstance(region, Mapping):
        raise LegacyNormalizationError(
            f"unparsed_regions[{index}] is invalid"
        )

    source = _require_string(
        region.get("source"),
        f"unparsed_regions[{index}].source",
    )
    start_line = _require_positive_integer(
        region.get("start_line"),
        f"unparsed_regions[{index}].start_line",
    )
    end_line = _require_positive_integer(
        region.get("end_line"),
        f"unparsed_regions[{index}].end_line",
    )
    text = _require_string(
        region.get("text"),
        f"unparsed_regions[{index}].text",
    )

    if end_line < start_line:
        raise LegacyNormalizationError(
            f"unparsed_regions[{index}] line range is invalid"
        )

    return {
        "source": source,
        "start_line": start_line,
        "end_line": end_line,
        "text": text,
    }


def _region_id(
    *,
    source: str,
    start_line: int,
    end_line: int,
    text: str,
) -> str:
    return _canonical_hash(
        {
            "source": source,
            "start_line": start_line,
            "end_line": end_line,
            "content_hash": _text_hash(text),
        }
    )


def _chunk_id(
    *,
    region_id: str,
    chunk_index: int,
    char_start: int,
    char_end: int,
    content_hash: str,
) -> str:
    return _canonical_hash(
        {
            "region_id": region_id,
            "chunk_index": chunk_index,
            "char_start": char_start,
            "char_end": char_end,
            "content_hash": content_hash,
        }
    )


def build_legacy_normalization(
    catalog: Mapping[str, Any],
    *,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> dict[str, Any]:
    """Create exact bounded chunks without interpreting content."""
    if not isinstance(catalog, Mapping):
        raise LegacyNormalizationError(
            "catalog must be a mapping"
        )

    max_chunk_chars = _require_positive_integer(
        max_chunk_chars,
        "max_chunk_chars",
    )

    regions = catalog.get("unparsed_regions", [])
    if (
        isinstance(regions, (str, bytes))
        or not isinstance(regions, Sequence)
    ):
        raise LegacyNormalizationError(
            "catalog unparsed_regions are invalid"
        )

    chunks: list[dict[str, Any]] = []
    region_records: list[dict[str, Any]] = []

    for region_index, supplied_region in enumerate(regions):
        region = _validate_region(
            supplied_region,
            index=region_index,
        )
        source = region["source"]
        start_line = region["start_line"]
        end_line = region["end_line"]
        text = region["text"]

        region_id = _region_id(
            source=source,
            start_line=start_line,
            end_line=end_line,
            text=text,
        )
        first_chunk_index = len(chunks)
        region_chunk_count = 0

        for char_start in range(
            0,
            len(text),
            max_chunk_chars,
        ):
            char_end = min(
                char_start + max_chunk_chars,
                len(text),
            )
            chunk_text = text[char_start:char_end]
            content_hash = _text_hash(chunk_text)
            chunk_index = region_chunk_count

            chunks.append(
                {
                    "chunk_id": _chunk_id(
                        region_id=region_id,
                        chunk_index=chunk_index,
                        char_start=char_start,
                        char_end=char_end,
                        content_hash=content_hash,
                    ),
                    "region_id": region_id,
                    "region_index": region_index,
                    "chunk_index": chunk_index,
                    "source": source,
                    "start_line": start_line,
                    "end_line": end_line,
                    "char_start": char_start,
                    "char_end": char_end,
                    "content_hash": content_hash,
                    "text": chunk_text,
                    "status": "needs_review",
                }
            )
            region_chunk_count += 1

        region_records.append(
            {
                "region_id": region_id,
                "region_index": region_index,
                "source": source,
                "start_line": start_line,
                "end_line": end_line,
                "content_hash": _text_hash(text),
                "character_count": len(text),
                "first_chunk_offset": first_chunk_index,
                "chunk_count": region_chunk_count,
            }
        )

    normalization: dict[str, Any] = {
        "type": NORMALIZATION_TYPE,
        "version": NORMALIZATION_VERSION,
        "source_catalog_hash": catalog.get(
            "catalog_hash"
        ),
        "max_chunk_chars": max_chunk_chars,
        "region_count": len(region_records),
        "chunk_count": len(chunks),
        "regions": region_records,
        "chunks": chunks,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "canonical_mutation": False,
    }
    normalization["normalization_hash"] = (
        _canonical_hash(normalization)
    )
    return normalization


def reconstruct_legacy_region(
    chunks: Sequence[Mapping[str, Any]],
) -> str:
    """Verify and exactly reconstruct one legacy region."""
    if (
        isinstance(chunks, (str, bytes))
        or not isinstance(chunks, Sequence)
        or not chunks
    ):
        raise LegacyNormalizationError(
            "chunks must be a non-empty sequence"
        )

    expected_region_id: str | None = None
    expected_char_start = 0
    reconstructed: list[str] = []

    for expected_index, chunk in enumerate(chunks):
        if not isinstance(chunk, Mapping):
            raise LegacyNormalizationError(
                f"chunks[{expected_index}] is invalid"
            )

        region_id = _require_string(
            chunk.get("region_id"),
            f"chunks[{expected_index}].region_id",
        )
        if expected_region_id is None:
            expected_region_id = region_id
        elif region_id != expected_region_id:
            raise LegacyNormalizationError(
                "chunks contain multiple regions"
            )

        chunk_index = chunk.get("chunk_index")
        if chunk_index != expected_index:
            raise LegacyNormalizationError(
                "chunk order is invalid"
            )

        char_start = chunk.get("char_start")
        char_end = chunk.get("char_end")
        if (
            not isinstance(char_start, int)
            or isinstance(char_start, bool)
            or not isinstance(char_end, int)
            or isinstance(char_end, bool)
            or char_start != expected_char_start
            or char_end <= char_start
        ):
            raise LegacyNormalizationError(
                "chunk character range is invalid"
            )

        text = _require_string(
            chunk.get("text"),
            f"chunks[{expected_index}].text",
        )
        content_hash = _require_string(
            chunk.get("content_hash"),
            f"chunks[{expected_index}].content_hash",
        )
        if _text_hash(text) != content_hash:
            raise LegacyNormalizationError(
                "chunk content hash mismatch"
            )

        if char_end - char_start != len(text):
            raise LegacyNormalizationError(
                "chunk character range does not match text"
            )

        expected_chunk_id = _chunk_id(
            region_id=region_id,
            chunk_index=chunk_index,
            char_start=char_start,
            char_end=char_end,
            content_hash=content_hash,
        )
        if chunk.get("chunk_id") != expected_chunk_id:
            raise LegacyNormalizationError(
                "chunk identity mismatch"
            )

        reconstructed.append(text)
        expected_char_start = char_end

    return "".join(reconstructed)

def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a lossless review envelope for "
            "unparsed invariant material."
        )
    )
    parser.add_argument(
        "sources",
        nargs="+",
        help="Invariant Markdown source files",
    )
    parser.add_argument(
        "--max-chunk-chars",
        type=int,
        default=DEFAULT_MAX_CHUNK_CHARS,
        help="Maximum characters in each review chunk",
    )
    parser.add_argument(
        "--output",
        help="Optional normalization JSON output file",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the read-only legacy normalization command."""
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
                "Legacy normalization refused to "
                "overwrite a source file.",
                file=sys.stderr,
            )
            return 2

    try:
        catalog = catalog_invariant_files(
            source_paths
        )
        normalization = build_legacy_normalization(
            catalog,
            max_chunk_chars=args.max_chunk_chars,
        )
        rendered = (
            json.dumps(
                normalization,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )

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
            f"Legacy normalization failed: {exc}",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
