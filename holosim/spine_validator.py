"""Read-only domain spine validator for Holo/Sim.

Discovers repository spine documents, verifies structural requirements,
performs lossless round-trip checks, calculates hashes, checks chain health,
and writes a standalone JSON validation report.

It does not modify Master_Index.md or trigger rebirth actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from holosim.config import DEFAULT_CHAIN_FILE, REPO_ROOT
    from holosim.core import HoloChain
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import DEFAULT_CHAIN_FILE, REPO_ROOT
    from holosim.core import HoloChain


REPORT_FILE = "Spine_Validation_Report.json"

HEADER_PATTERN = re.compile(r"█†█ Holo/Sim █†█")

EXPECTED_SPINES = (
    "Physics_Spine.md",
    "Biology_Spine.md",
    "Chemistry_Spine.md",
    "Mathematics_Spine.md",
    "Computation_Systems_Spine.md",
    "Neuroscience_Psychology_Spine.md",
    "Philosophy_Ontology_Spine.md",
    "Logic_Epistemology_Spine.md",
)

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    """Return a full SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def is_skipped(path: Path) -> bool:
    """Return True when a path belongs to a generated or internal directory."""
    return any(part in SKIP_DIRS for part in path.parts)


class HoloSpineValidator:
    """Validate Holo/Sim spine documents without mutating source files."""

    def __init__(
        self,
        repo_root: str | Path = REPO_ROOT,
        chain_path: str | Path = DEFAULT_CHAIN_FILE,
        report_path: str | Path = REPORT_FILE,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.chain_path = Path(chain_path)

        report = Path(report_path)
        self.report_path = report if report.is_absolute() else self.repo_root / report

    def discover_spines(self) -> dict[str, Path]:
        """Discover root-level and nested files ending in `_Spine.md`."""
        discovered: dict[str, Path] = {}

        for path in sorted(self.repo_root.rglob("*_Spine.md")):
            if not path.is_file() or is_skipped(path):
                continue

            discovered[path.name] = path

        return discovered

    def validate_roundtrip(self, raw: bytes) -> bool:
        """Verify a lossless UTF-8 decode and encode round trip."""
        try:
            text = raw.decode("utf-8")
            reconstructed = text.encode("utf-8")
        except UnicodeError:
            return False

        return reconstructed == raw

    def validate_spine(self, path: Path) -> dict[str, Any]:
        """Validate one spine document."""
        issues: list[str] = []

        try:
            raw = path.read_bytes()
        except OSError as exc:
            return {
                "name": path.name,
                "path": path.relative_to(self.repo_root).as_posix(),
                "status": "FAIL",
                "issues": [f"Read error: {exc}"],
            }

        size_bytes = len(raw)
        content_hash = sha256_bytes(raw)
        roundtrip_valid = self.validate_roundtrip(raw)

        try:
            text = raw.decode("utf-8")
        except UnicodeError:
            text = ""

        if size_bytes == 0:
            issues.append("File is empty.")

        if not roundtrip_valid:
            issues.append("UTF-8 round-trip failed.")

        header_valid = bool(HEADER_PATTERN.search(text[:5000]))
        if not header_valid:
            issues.append("Missing required █†█ Holo/Sim █†█ header.")

        status = "PASS" if not issues else "FAIL"

        return {
            "name": path.name,
            "path": path.relative_to(self.repo_root).as_posix(),
            "status": status,
            "size_bytes": size_bytes,
            "sha256": content_hash,
            "header_valid": header_valid,
            "roundtrip_valid": roundtrip_valid,
            "issues": issues,
        }

    def validate_chain(self) -> dict[str, Any]:
        """Verify the configured HoloChain and normalize its health result."""
        try:
            chain = HoloChain(str(self.chain_path))
            entries = chain.load_and_verify()
            health = chain.health()

            recommendation = (
                health.get("recommendation", "UNKNOWN")
                if isinstance(health, dict)
                else str(health)
            )

            return {
                "status": "PASS",
                "entries": len(entries),
                "recommendation": recommendation,
                "health": health,
            }
        except Exception as exc:
            return {
                "status": "FAIL",
                "entries": None,
                "recommendation": "UNAVAILABLE",
                "error": str(exc),
            }

    def run(self, *, write_report: bool = True) -> dict[str, Any]:
        """Run full read-only validation."""
        discovered = self.discover_spines()

        spine_results: list[dict[str, Any]] = []
        missing_spines: list[str] = []

        for expected_name in EXPECTED_SPINES:
            path = discovered.get(expected_name)

            if path is None:
                missing_spines.append(expected_name)
                spine_results.append(
                    {
                        "name": expected_name,
                        "path": None,
                        "status": "MISSING",
                        "issues": ["Expected spine was not found."],
                    }
                )
                continue

            spine_results.append(self.validate_spine(path))

        expected_names = set(EXPECTED_SPINES)
        additional_spines = [
            self.validate_spine(path)
            for name, path in discovered.items()
            if name not in expected_names
        ]

        chain_result = self.validate_chain()

        failed_count = sum(
            1 for result in spine_results + additional_spines
            if result["status"] == "FAIL"
        )
        missing_count = len(missing_spines)

        overall_status = (
            "PASS"
            if failed_count == 0
            and missing_count == 0
            and chain_result["status"] == "PASS"
            else "FAIL"
        )

        report = {
            "type": "holo_spine_validation_report",
            "version": "0.1",
            "timestamp": utc_now(),
            "repo_root": str(self.repo_root),
            "chain_file": str(self.chain_path),
            "overall_status": overall_status,
            "summary": {
                "expected_spines": len(EXPECTED_SPINES),
                "discovered_spines": len(discovered),
                "missing_spines": missing_count,
                "failed_spines": failed_count,
                "additional_spines": len(additional_spines),
            },
            "chain": chain_result,
            "missing": missing_spines,
            "spines": spine_results,
            "additional": additional_spines,
        }

        if write_report:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            report["report_file"] = str(self.report_path)

        return report


def get_validator(
    repo_root: str | Path = REPO_ROOT,
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    report_path: str | Path = REPORT_FILE,
) -> HoloSpineValidator:
    """Create a configured validator."""
    return HoloSpineValidator(repo_root, chain_path, report_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Holo/Sim domain spines."
    )
    parser.add_argument(
        "--repo",
        default=str(REPO_ROOT),
        help="Repository root directory",
    )
    parser.add_argument(
        "--file",
        "-f",
        default=str(DEFAULT_CHAIN_FILE),
        help="HoloChain JSONL file",
    )
    parser.add_argument(
        "--report",
        default=REPORT_FILE,
        help="Validation report path",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run validation without writing a report",
    )

    args = parser.parse_args()

    validator = get_validator(
        repo_root=args.repo,
        chain_path=args.file,
        report_path=args.report,
    )
    result = validator.run(write_report=not args.no_write)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    raise SystemExit(0 if result["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()