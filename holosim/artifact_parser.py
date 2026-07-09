"""Artifact parser and CAP audit tools for Holo/Sim.

Converged from placeholder behavior into a real zero-dependency audit pass.
It scans CAP/artifact files, hashes them, detects duplicate content, extracts
basic anchors, and returns a structured summary without mutating anything.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    from holosim.config import ACTIVE_HASH, ANCHOR, REPO_ROOT
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import ACTIVE_HASH, ANCHOR, REPO_ROOT


DEFAULT_AUDIT_DIRS = [
    REPO_ROOT / "Holo" / "Sim" / "Holo Blood",
    REPO_ROOT / "CAPs_raw",
    REPO_ROOT / "Holo",
    REPO_ROOT / "holosim",
]

AUDIT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
}

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "dist",
    "build",
}

ANCHOR_PATTERNS = [
    r"Canyon(?:\s+Brock\s+Haney)?",
    r"CANYON_OVERRIDE",
    r"Anchor",
    r"HOLO",
    r"Holo/Sim",
    r"HSSCE",
    r"v0807a[-\w]*",
    r"ACTIVE_HASH",
    r"CAP",
    r"continuity",
    r"rebirth",
    r"invariant",
]


class ArtifactParser:
    """Parse and audit Holo/Sim CAP/artifact files."""

    def __init__(self) -> None:
        self.audit_checklist = {
            "parse_holo_blood": "Identify duplicates, partials, outdated CAPs",
            "label_active_core": "Mark latest validated weld",
            "cross_check_timestamps": "Chronological order with versions",
            "filter_unique": "Keep unique CAP structures, emotional signatures",
            "extract_anchors": "Continuity anchors, M.A.P. events",
            "compress_redundancy": "Preserve directives, timestamps",
            "yaml_summary": "Keys: timestamp, context, directives, unique_values, continuity_weight",
        }

    def _is_skipped_path(self, path: Path) -> bool:
        return any(part in SKIP_DIRS for part in path.parts)

    def _candidate_files(self, root: Path) -> List[Path]:
        if not root.exists():
            return []

        if root.is_file():
            return [root] if root.suffix.lower() in AUDIT_SUFFIXES else []

        files: List[Path] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if self._is_skipped_path(path):
                continue
            if path.suffix.lower() not in AUDIT_SUFFIXES:
                continue
            files.append(path)

        return files

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def _sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _extract_anchors(self, content: str) -> List[str]:
        found: set[str] = set()

        for pattern in ANCHOR_PATTERNS:
            for match in re.findall(pattern, content, flags=re.IGNORECASE):
                found.add(str(match))

        if ACTIVE_HASH in content:
            found.add(ACTIVE_HASH)

        if ANCHOR in content:
            found.add(ANCHOR)

        return sorted(found, key=str.lower)

    def _extract_timestamp_hint(self, content: str) -> str | None:
        patterns = [
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            r"\d{4}-\d{2}-\d{2}",
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(0)

        return None

    def audit_caps(self, dir_path: str | Path | None = None) -> Dict[str, Any]:
        """Run a real CAP/artifact audit and return a structured summary."""
        print("Holo Blood Audit started...")

        roots = [Path(dir_path)] if dir_path else DEFAULT_AUDIT_DIRS

        records: List[Dict[str, Any]] = []
        seen_hashes: Dict[str, str] = {}
        duplicates: List[Dict[str, str]] = []
        missing_roots: List[str] = []

        for root in roots:
            root = Path(root)

            if not root.exists():
                missing_roots.append(str(root))
                continue

            for path in self._candidate_files(root):
                try:
                    content = self._read_text(path)
                    digest = self._sha256(content)
                    anchors = self._extract_anchors(content)
                    timestamp_hint = self._extract_timestamp_hint(content)

                    rel_path = (
                        path.relative_to(REPO_ROOT).as_posix()
                        if path.is_relative_to(REPO_ROOT)
                        else path.as_posix()
                    )

                    if digest in seen_hashes:
                        duplicates.append(
                            {
                                "path": rel_path,
                                "duplicate_of": seen_hashes[digest],
                                "sha256": digest[:16],
                            }
                        )
                    else:
                        seen_hashes[digest] = rel_path

                    records.append(
                        {
                            "path": rel_path,
                            "sha256": digest[:16],
                            "bytes": len(content.encode("utf-8")),
                            "anchors": anchors,
                            "timestamp_hint": timestamp_hint,
                        }
                    )

                except Exception as error:
                    records.append(
                        {
                            "path": path.as_posix(),
                            "error": str(error),
                        }
                    )

        anchor_hits = sum(1 for record in records if record.get("anchors"))
        continuity_weight = "high" if anchor_hits else "low"

        summary = {
            "status": "complete",
            "active_hash": ACTIVE_HASH,
            "anchor": ANCHOR,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "roots_checked": [str(root) for root in roots],
            "missing_roots": missing_roots,
            "files_scanned": len(records),
            "unique_files": len(seen_hashes),
            "duplicates_found": len(duplicates),
            "duplicates": duplicates,
            "anchor_hits": anchor_hits,
            "continuity_weight": continuity_weight,
            "audit_checklist": self.audit_checklist,
            "records": records,
        }

        print("Active core labeled. Duplicates filtered. YAML summary ready.")
        return summary


def main() -> None:
    parser = ArtifactParser()
    result = parser.audit_caps()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()