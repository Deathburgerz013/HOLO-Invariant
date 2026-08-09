"""Verified, non-authoritative cold-start re-entry packets.

The gateway composes an exact reconstructed state with a verified continuity
head check.  It reports whether the supplied evidence is ready for re-entry;
it does not perform continuation or grant truth, acceptance, write, or
execution authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.continuity_current_gate import (
    ContinuityCurrentGateError,
    evaluate_continuity_current_gate,
)
from holosim.reconstructor import (
    ReconstructionError,
    validate_reconstructed_state,
)

PACKET_TYPE = "verified_cold_start_reentry_packet"
PACKET_VERSION = 1


class VerifiedColdStartReentryError(ValueError):
    """Raised when re-entry evidence or a retained packet is invalid."""


def _required_text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise VerifiedColdStartReentryError(
            f"{field} must be a non-empty plain string"
        )
    return value


def _plain_conflicts(conflicts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if type(conflicts) not in {list, tuple}:
        raise VerifiedColdStartReentryError("conflicts must be a list or tuple")
    normalized: list[dict[str, Any]] = []
    for index, conflict in enumerate(conflicts):
        if type(conflict) is not dict:
            raise VerifiedColdStartReentryError(
                f"conflicts[{index}] must be a plain dictionary"
            )
        try:
            stable_hash(conflict)
        except CanonicalValueError as exc:
            raise VerifiedColdStartReentryError(
                f"conflicts[{index}] is outside the canonical JSON contract"
            ) from exc
        normalized.append(deepcopy(conflict))
    return normalized


def _classification(
    *, reconstruction_status: str, head_status: str, conflicts: list[dict[str, Any]]
) -> tuple[str, str, list[str]]:
    if reconstruction_status == "INCOMPLETE":
        return "BLOCKED_INCOMPLETE", "BLOCK", ["reconstruction_incomplete"]
    if reconstruction_status != "COMPLETE":
        raise VerifiedColdStartReentryError(
            "reconstructed state has unsupported status"
        )
    if head_status != "CURRENT":
        return (
            "BLOCKED_HEAD",
            "BLOCK",
            [f"continuity_head_status_{head_status.lower()}"],
        )
    if conflicts:
        return "BLOCKED_CONFLICT", "BLOCK", ["unresolved_conflicts"]
    return "READY_FOR_REENTRY", "ALLOW", []


def build_verified_cold_start_reentry_packet(
    *,
    packet_id: str,
    reconstructed_state: Mapping[str, Any],
    source_items: Sequence[Mapping[str, Any]],
    head_check: Mapping[str, Any],
    conflicts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind reconstruction, head currency, and explicit conflicts into one packet."""
    checked_packet_id = _required_text(packet_id, "packet_id")
    if type(reconstructed_state) is not dict:
        raise VerifiedColdStartReentryError(
            "reconstructed_state must be a plain dictionary"
        )
    try:
        validate_reconstructed_state(reconstructed_state, source_items)
    except ReconstructionError as exc:
        raise VerifiedColdStartReentryError(
            f"reconstructed state is invalid: {exc}"
        ) from exc
    try:
        gate = evaluate_continuity_current_gate(head_check=head_check)
    except ContinuityCurrentGateError as exc:
        raise VerifiedColdStartReentryError(f"head check is invalid: {exc}") from exc

    checked_conflicts = _plain_conflicts(conflicts)
    status, gate_decision, reasons = _classification(
        reconstruction_status=reconstructed_state["status"],
        head_status=gate["head_status"],
        conflicts=checked_conflicts,
    )
    body = {
        "type": PACKET_TYPE,
        "version": PACKET_VERSION,
        "packet_id": checked_packet_id,
        "reconstructed_state": deepcopy(reconstructed_state),
        "reconstructed_state_hash": reconstructed_state["state_hash"],
        "carried_item_ids": list(reconstructed_state["reachable_ids"]),
        "head_check": deepcopy(dict(head_check)),
        "head_check_hash": head_check["check_hash"],
        "head_status": gate["head_status"],
        "conflicts": checked_conflicts,
        "status": status,
        "gate_decision": gate_decision,
        "reasons": reasons,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    try:
        return {**body, "packet_hash": stable_hash(body)}
    except CanonicalValueError as exc:
        raise VerifiedColdStartReentryError(str(exc)) from exc


def validate_verified_cold_start_reentry_packet(
    packet: Mapping[str, Any],
    *,
    source_items: Sequence[Mapping[str, Any]],
) -> bool:
    """Regenerate a packet from its bound evidence and require exact equality."""
    if type(packet) is not dict:
        raise VerifiedColdStartReentryError("packet must be a plain dictionary")
    expected_fields = {
        "type",
        "version",
        "packet_id",
        "reconstructed_state",
        "reconstructed_state_hash",
        "carried_item_ids",
        "head_check",
        "head_check_hash",
        "head_status",
        "conflicts",
        "status",
        "gate_decision",
        "reasons",
        "truth_claimed",
        "accepted",
        "write_authority",
        "execution_authority",
        "packet_hash",
    }
    if set(packet) != expected_fields:
        raise VerifiedColdStartReentryError(
            "packet fields do not match the versioned schema"
        )
    if packet.get("type") != PACKET_TYPE or packet.get("version") != PACKET_VERSION:
        raise VerifiedColdStartReentryError("packet type or version is invalid")
    if (
        packet.get("truth_claimed") is not False
        or packet.get("accepted") is not False
        or packet.get("write_authority") != "NONE"
        or packet.get("execution_authority") != "NONE"
    ):
        raise VerifiedColdStartReentryError("packet cannot grant authority")

    try:
        regenerated = build_verified_cold_start_reentry_packet(
            packet_id=packet["packet_id"],
            reconstructed_state=packet["reconstructed_state"],
            source_items=source_items,
            head_check=packet["head_check"],
            conflicts=packet["conflicts"],
        )
    except VerifiedColdStartReentryError:
        raise
    except (KeyError, TypeError) as exc:
        raise VerifiedColdStartReentryError("packet evidence is malformed") from exc
    if regenerated != packet:
        raise VerifiedColdStartReentryError(
            "packet does not match its reconstructed state and head evidence"
        )
    return True