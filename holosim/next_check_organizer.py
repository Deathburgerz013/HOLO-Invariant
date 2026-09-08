"""Read-only organization of declared next checks from uncertainty records.

This module does not invent checks, decide truth, mutate records, execute work,
or grant authority. It only surfaces resolution conditions that already exist
in supplied records and preserves the record identity that caused each check
candidate to exist.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash


ORGANIZER_TYPE = "holo_next_check_organizer"
ORGANIZER_VERSION = 1

_TERMINAL_STATUSES = frozenset({"resolved"})
_KNOWN_ACTIVE_STATUSES = frozenset(
    {"open", "bounded", "reduced", "contradicted"}
)


class NextCheckOrganizerError(ValueError):
    """Raised when supplied organizer input is structurally invalid."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NextCheckOrganizerError(f"{field} must be a non-empty string")
    return value.strip()


def _text_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise NextCheckOrganizerError(f"{field} must be a sequence of strings")

    result: list[str] = []
    for item in value:
        text = _required_text(item, field)
        result.append(text)
    return result


def _record_identity(record: Mapping[str, Any], position: int) -> dict[str, Any]:
    """Return the source identity preserved on every derived candidate."""
    return {
        "position": position,
        "idx": record.get("idx"),
        "entry_hash": record.get("entry_hash"),
        "claim": _required_text(record.get("claim"), f"records[{position}].claim"),
        "status": _required_text(record.get("status"), f"records[{position}].status"),
        "source_refs": _text_list(
            record.get("source_refs", []),
            f"records[{position}].source_refs",
        ),
    }


def organize_next_checks(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive ordered next-check candidates from declared resolution conditions.

    Record order is preserved. Within each record, declared condition order is
    preserved. Resolved records do not emit candidates. Active records without
    declared resolution conditions are explicitly classified as requiring a
    resolution condition, but no condition is invented.
    """
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise NextCheckOrganizerError("records must be a sequence of mappings")

    candidates: list[dict[str, Any]] = []
    unresolved_without_declared_check: list[dict[str, Any]] = []
    ignored_terminal_records: list[dict[str, Any]] = []

    for position, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise NextCheckOrganizerError(
                f"records[{position}] must be a mapping"
            )

        identity = _record_identity(record, position)
        status = identity["status"].lower()

        conditions = _text_list(
            record.get("resolution_conditions", []),
            f"records[{position}].resolution_conditions",
        )
        residual = _text_list(
            record.get("residual_uncertainty", []),
            f"records[{position}].residual_uncertainty",
        )

        source = {
            **identity,
            "residual_uncertainty": residual,
        }

        if status in _TERMINAL_STATUSES:
            ignored_terminal_records.append(source)
            continue

        if status not in _KNOWN_ACTIVE_STATUSES:
            raise NextCheckOrganizerError(
                f"records[{position}].status is not organizer-recognized: "
                f"{identity['status']}"
            )

        if not conditions:
            unresolved_without_declared_check.append(
                {
                    **source,
                    "routing_status": "RESOLUTION_CONDITION_REQUIRED",
                    "condition_invented": False,
                    "execution_authorized": False,
                    "truth_claimed": False,
                    "accepted": False,
                    "write_authority": "NONE",
                }
            )
            continue

        for condition_index, condition in enumerate(conditions):
            candidate_payload = {
                "condition": condition,
                "condition_index": condition_index,
                "source": source,
                "routing_status": "DECLARED_CHECK_AVAILABLE",
                "invented": False,
                "execution_authorized": False,
                "truth_claimed": False,
                "accepted": False,
                "write_authority": "NONE",
            }
            try:
                candidate_id = stable_hash(candidate_payload)
            except CanonicalValueError as exc:
                raise NextCheckOrganizerError(str(exc)) from exc

            candidates.append(
                {
                    **candidate_payload,
                    "candidate_id": candidate_id,
                }
            )

    payload = {
        "type": ORGANIZER_TYPE,
        "version": ORGANIZER_VERSION,
        "candidate_checks": candidates,
        "unresolved_without_declared_check": unresolved_without_declared_check,
        "ignored_terminal_records": ignored_terminal_records,
        "ordering": "source_record_then_declared_condition",
        "conditions_invented": False,
        "execution_authorized": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }

    try:
        organizer_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise NextCheckOrganizerError(str(exc)) from exc

    return {**payload, "organizer_id": organizer_id}
