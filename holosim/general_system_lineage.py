
"""Read-only, evidence-referenced lineage for explicitly described systems.

Structural integrity does not establish external truth or causal independence.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash

TYPE = "general_system_lineage"
VERSION = 1
MAX_RECORDS = 1000
KINDS = ("systems", "observations", "relationships", "corrections")

FIELDS = {
    "systems": {"system_id", "domain", "label"},
    "observations": {
        "observation_id", "system_id", "source_id",
        "boundary", "evidence_hash", "finding",
    },
    "relationships": {
        "relationship_id", "source_system_id", "target_system_id",
        "relationship_type", "evidence_observation_ids", "status",
    },
    "corrections": {
        "correction_id", "target_record_hash",
        "evidence_observation_ids", "assessment",
    },
}

IDS = {
    "systems": "system_id",
    "observations": "observation_id",
    "relationships": "relationship_id",
    "corrections": "correction_id",
}

STATUS = {"OBSERVED", "PROPOSED", "UNKNOWN"}


class GeneralSystemLineageError(ValueError):
    """Malformed or internally inconsistent general-system lineage."""


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise GeneralSystemLineageError(
            f"{name} must be non-empty text"
        )
    return value


def _digest(value: Any, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise GeneralSystemLineageError(
            f"{name} must be lowercase SHA-256"
        )
    return value


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except (CanonicalValueError, TypeError, ValueError) as exc:
        raise GeneralSystemLineageError(
            f"non-canonical record: {exc}"
        ) from exc


def _evidence_ids(value: Any) -> list[str]:
    if type(value) is not list or not value:
        raise GeneralSystemLineageError(
            "evidence_observation_ids must be a nonempty list"
        )

    ids = [
        _text(item, "evidence observation id")
        for item in value
    ]

    if len(set(ids)) != len(ids):
        raise GeneralSystemLineageError(
            "duplicate evidence observation id"
        )

    return ids


def _records(kind: str, supplied: Any) -> list[dict[str, Any]]:
    if type(supplied) is not list or len(supplied) > MAX_RECORDS:
        raise GeneralSystemLineageError(
            f"{kind} must be a bounded list"
        )

    output = []
    seen = set()

    for item in supplied:
        if type(item) is not dict or set(item) != FIELDS[kind]:
            raise GeneralSystemLineageError(
                f"{kind} record fields mismatch"
            )

        record = deepcopy(item)
        identity = _text(record[IDS[kind]], IDS[kind])

        if identity in seen:
            raise GeneralSystemLineageError(
                f"duplicate {kind} identity"
            )

        seen.add(identity)

        if kind == "systems":
            _text(record["domain"], "domain")
            _text(record["label"], "label")

        elif kind == "observations":
            _text(record["system_id"], "system_id")
            _text(record["source_id"], "source_id")
            _text(record["boundary"], "boundary")
            _digest(record["evidence_hash"], "evidence_hash")
            _hash(record["finding"])

        elif kind == "relationships":
            _text(
                record["source_system_id"],
                "source_system_id",
            )
            _text(
                record["target_system_id"],
                "target_system_id",
            )
            _text(
                record["relationship_type"],
                "relationship_type",
            )
            _evidence_ids(
                record["evidence_observation_ids"]
            )

            if (
                type(record["status"]) is not str
                or record["status"] not in STATUS
            ):
                raise GeneralSystemLineageError(
                    "invalid relationship status"
                )

        else:
            _digest(
                record["target_record_hash"],
                "target_record_hash",
            )
            _evidence_ids(
                record["evidence_observation_ids"]
            )
            _text(record["assessment"], "assessment")

        _hash(record)
        output.append(record)

    if kind == "corrections":
        return output

    return sorted(
        output,
        key=lambda record: record[IDS[kind]],
    )


def build_general_system_lineage(
    systems: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    corrections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic report without I/O or source mutation."""

    records = {
        kind: _records(kind, values)
        for kind, values in zip(
            KINDS,
            (
                systems,
                observations,
                relationships,
                corrections,
            ),
        )
    }

    system_ids = {
        item["system_id"]
        for item in records["systems"]
    }
    observation_ids = {
        item["observation_id"]
        for item in records["observations"]
    }

    for item in records["observations"]:
        if item["system_id"] not in system_ids:
            raise GeneralSystemLineageError(
                "observation references missing system"
            )

    for item in records["relationships"]:
        if (
            item["source_system_id"] not in system_ids
            or item["target_system_id"] not in system_ids
        ):
            raise GeneralSystemLineageError(
                "relationship references missing system"
            )

        if not set(
            item["evidence_observation_ids"]
        ) <= observation_ids:
            raise GeneralSystemLineageError(
                "relationship references missing observation"
            )

    for item in records["corrections"]:
        if not set(
            item["evidence_observation_ids"]
        ) <= observation_ids:
            raise GeneralSystemLineageError(
                "correction references missing observation"
            )

    known_hashes = set()

    for kind in (
        "systems",
        "observations",
        "relationships",
    ):
        known_hashes.update(
            _hash(item)
            for item in records[kind]
        )

    for item in records["corrections"]:
        if item["target_record_hash"] not in known_hashes:
            raise GeneralSystemLineageError(
                "correction target is missing or not earlier"
            )

        known_hashes.add(_hash(item))

    body = {
        "type": TYPE,
        "version": VERSION,
        **records,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "lineage_hash": _hash(body),
    }


def validate_general_system_lineage(report: Any) -> bool:
    """Rebuild the report and reject schema or identity tampering."""

    expected_fields = {
        "type",
        "version",
        *KINDS,
        "truth_claimed",
        "accepted",
        "write_authority",
        "lineage_hash",
    }

    if type(report) is not dict or set(report) != expected_fields:
        raise GeneralSystemLineageError(
            "lineage fields mismatch"
        )

    if (
        report["type"] != TYPE
        or type(report["version"]) is not int
        or report["version"] != VERSION
    ):
        raise GeneralSystemLineageError(
            "lineage type/version mismatch"
        )

    if (
        report["truth_claimed"] is not False
        or report["accepted"] is not False
        or report["write_authority"] != "NONE"
    ):
        raise GeneralSystemLineageError(
            "lineage cannot grant authority"
        )

    rebuilt = build_general_system_lineage(
        *(report[kind] for kind in KINDS)
    )

    if rebuilt != report:
        raise GeneralSystemLineageError(
            "lineage identity or contents mismatch"
        )

    return True
