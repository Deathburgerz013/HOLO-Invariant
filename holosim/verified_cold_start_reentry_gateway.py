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
COMPARISON_TYPE = "cross_observer_reentry_comparison"
COMPARISON_VERSION = 1


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


def compare_observer_reentry_packets(
    *,
    left: Mapping[str, Any],
    left_source_items: Sequence[Mapping[str, Any]],
    right: Mapping[str, Any],
    right_source_items: Sequence[Mapping[str, Any]],
    left_observer_id: str,
    right_observer_id: str,
) -> dict[str, Any]:
    """Compare two independently validated packets at the same verified head.

    Observer IDs are caller-supplied labels, not authenticated identities. A match
    establishes byte-level agreement in the bounded reconstruction, not truth or
    permission to update a lineage. Disagreement is an explicit gateway conflict.
    """
    left_id = _required_text(left_observer_id, "left_observer_id")
    right_id = _required_text(right_observer_id, "right_observer_id")
    if left_id == right_id:
        raise VerifiedColdStartReentryError("observer labels must differ")
    validate_verified_cold_start_reentry_packet(left, source_items=left_source_items)
    validate_verified_cold_start_reentry_packet(right, source_items=right_source_items)

    left_state = left["reconstructed_state"]
    right_state = right["reconstructed_state"]
    left_head = left["head_check"]
    right_head = right["head_check"]
    same_scope = (
        left_state["reference"] == right_state["reference"]
        and left_state["target_ids"] == right_state["target_ids"]
        and left_head["current_head_hash"] == right_head["current_head_hash"]
        and left_head["current_head_idx"] == right_head["current_head_idx"]
    )
    reasons: list[str] = []
    conflicts: list[dict[str, Any]] = []
    if left["status"] != "READY_FOR_REENTRY" or right["status"] != "READY_FOR_REENTRY":
        status = "BLOCKED_INPUT"
        reasons.append("input_packet_not_ready")
    elif not same_scope:
        status = "BLOCKED_SCOPE"
        reasons.append("reconstruction_scope_or_head_differs")
    elif left["reconstructed_state_hash"] != right["reconstructed_state_hash"]:
        status = "BLOCKED_CONFLICT"
        reasons.append("reconstructed_states_disagree")
        conflicts.append({
            "id": "cross-observer-reconstruction-conflict",
            "left_observer_id": left_id,
            "right_observer_id": right_id,
            "left_state_hash": left["reconstructed_state_hash"],
            "right_state_hash": right["reconstructed_state_hash"],
        })
    else:
        status = "MATCHED"

    body = {
        "type": COMPARISON_TYPE,
        "version": COMPARISON_VERSION,
        "left_observer_id": left_id,
        "right_observer_id": right_id,
        "left_packet_hash": left["packet_hash"],
        "right_packet_hash": right["packet_hash"],
        "left_state_hash": left["reconstructed_state_hash"],
        "right_state_hash": right["reconstructed_state_hash"],
        "status": status,
        "reasons": reasons,
        "conflicts": conflicts,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "comparison_hash": stable_hash(body)}


def validate_observer_reentry_comparison(
    comparison: Mapping[str, Any],
    *,
    left: Mapping[str, Any],
    left_source_items: Sequence[Mapping[str, Any]],
    right: Mapping[str, Any],
    right_source_items: Sequence[Mapping[str, Any]],
) -> bool:
    """Regenerate the comparison from both original packets and source items."""
    if type(comparison) is not dict:
        raise VerifiedColdStartReentryError("comparison must be a plain dictionary")
    expected = compare_observer_reentry_packets(
        left=left,
        left_source_items=left_source_items,
        right=right,
        right_source_items=right_source_items,
        left_observer_id=comparison.get("left_observer_id"),
        right_observer_id=comparison.get("right_observer_id"),
    )
    if comparison != expected:
        raise VerifiedColdStartReentryError("comparison does not match its evidence")
    return True
