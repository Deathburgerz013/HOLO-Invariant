
"""Read-only book view over a retained general-system lineage report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from holosim.canonical import stable_hash
from holosim.general_system_lineage import (
    IDS,
    KINDS,
    GeneralSystemLineageError,
    validate_general_system_lineage,
)


class MechanicalContinuityBookError(ValueError):
    """The requested book cannot be reconstructed or verified."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise MechanicalContinuityBookError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def open_book(path: str | Path, expected_hash: str) -> dict[str, Any]:
    """Read and verify a lineage report against retained identity."""
    if (
        type(expected_hash) is not str
        or len(expected_hash) != 64
        or any(c not in "0123456789abcdef" for c in expected_hash)
    ):
        raise MechanicalContinuityBookError(
            "expected_hash must be a lowercase SHA-256 digest"
        )

    try:
        report = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicates,
        )
        validate_general_system_lineage(report)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise MechanicalContinuityBookError(
            f"cannot open verified book: {exc}"
        ) from exc

    if report["lineage_hash"] != expected_hash:
        raise MechanicalContinuityBookError(
            "retained lineage identity mismatch"
        )

    return report


def contents(report: dict[str, Any]) -> list[dict[str, str]]:
    """Return addressable record entries without changing their order."""
    entries = []
    for kind in KINDS:
        for record in report[kind]:
            entries.append({
                "kind": kind,
                "id": record[IDS[kind]],
                "record_hash": stable_hash(record),
            })
    return entries


def read_page(
    report: dict[str, Any], kind: str, record_id: str
) -> dict[str, Any]:
    """Locate an exact record by kind and explicit identity."""
    if kind not in KINDS:
        raise MechanicalContinuityBookError("unknown record kind")

    for record in report[kind]:
        if record[IDS[kind]] == record_id:
            return {
                "kind": kind,
                "id": record_id,
                "record_hash": stable_hash(record),
                "record": json.loads(json.dumps(record)),
            }

    raise MechanicalContinuityBookError(
        "requested record does not exist"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Holo/Sim Invariants: Mechanical Continuity"
    )
    parser.add_argument("path", help="Persisted lineage JSON path")
    parser.add_argument(
        "--expected-hash",
        required=True,
        help="Separately retained lineage_hash",
    )
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--id", dest="record_id")
    args = parser.parse_args()

    if (args.kind is None) != (args.record_id is None):
        parser.error("--kind and --id must be supplied together")

    try:
        report = open_book(args.path, args.expected_hash)
        if args.kind is None:
            result = {
                "title": "Holo/Sim",
                "subtitle": "Invariants",
                "description": "Mechanical Continuity",
                "lineage_hash": report["lineage_hash"],
                "verified": True,
                "contents": contents(report),
            }
        else:
            result = read_page(report, args.kind, args.record_id)
    except MechanicalContinuityBookError as exc:
        print(json.dumps({
            "status": "REJECTED",
            "reason": str(exc),
        }))
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
