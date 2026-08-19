"""Model-independent reconstruction from verified, presently usable state."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from holosim.guarantee_environment_binding import (
    GuaranteeEnvironmentBindingError,
    verify_guarantee_environment_binding,
)


PACKET_TYPE = "holo_situated_reconstruction_packet"
PACKET_VERSION = 1


class SituatedReconstructionPacketError(ValueError):
    """Raised when situated reconstruction evidence is invalid."""


def _canonical_json(value: Any, *, label: str) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise SituatedReconstructionPacketError(
            f"{label} must contain only JSON values"
        ) from exc


def _closed_copy(value: Any, *, label: str) -> Any:
    return json.loads(_canonical_json(value, label=label))


def _canonical_hash(value: Any, *, label: str) -> str:
    return hashlib.sha256(
        _canonical_json(value, label=label).encode("utf-8")
    ).hexdigest()


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SituatedReconstructionPacketError(
            f"{label} must be a non-empty string"
        )
    return value


def _text_list(value: Any, *, label: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SituatedReconstructionPacketError(
            f"{label} must be a sequence"
        )
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _required_text(item, label=f"{label}[{index}]")
        if text in seen:
            raise SituatedReconstructionPacketError(
                f"{label} must not contain duplicates"
            )
        seen.add(text)
        result.append(text)
    return result


def _verify_projection(projection: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(projection, Mapping):
        raise SituatedReconstructionPacketError(
            "projection must be a mapping"
        )
    closed = _closed_copy(dict(projection), label="projection")
    required_fields = {
        "type",
        "version",
        "current_environment_fingerprint",
        "event_count",
        "history_hash",
        "active_claims",
        "excluded_claims",
        "accepted",
        "truth_claimed",
        "write_authority",
        "execution_authority",
        "canonical_mutation",
        "projection_hash",
    }
    if set(closed) != required_fields:
        raise SituatedReconstructionPacketError(
            "projection fields are invalid"
        )
    supplied_hash = closed.pop("projection_hash")
    if (
        not isinstance(supplied_hash, str)
        or not supplied_hash
        or _canonical_hash(closed, label="projection") != supplied_hash
    ):
        raise SituatedReconstructionPacketError(
            "projection hash mismatch"
        )
    if closed["type"] != "holo_active_invariant_projection":
        raise SituatedReconstructionPacketError(
            "projection type mismatch"
        )
    if closed["version"] != 1:
        raise SituatedReconstructionPacketError(
            "projection version mismatch"
        )
    _required_text(
        closed["current_environment_fingerprint"],
        label="current_environment_fingerprint",
    )
    _required_text(closed["history_hash"], label="history_hash")
    if type(closed["event_count"]) is not int or closed["event_count"] < 0:
        raise SituatedReconstructionPacketError(
            "projection event_count is invalid"
        )
    if not isinstance(closed["active_claims"], list):
        raise SituatedReconstructionPacketError(
            "active_claims must be a list"
        )
    if not isinstance(closed["excluded_claims"], list):
        raise SituatedReconstructionPacketError(
            "excluded_claims must be a list"
        )
    active_ids: list[str] = []
    for claim in closed["active_claims"]:
        if not isinstance(claim, dict) or set(claim) != {
            "claim_id", "status", "event_hash"
        }:
            raise SituatedReconstructionPacketError(
                "active claim fields are invalid"
            )
        claim_id = _required_text(claim["claim_id"], label="claim_id")
        if claim["status"] not in {
            "INVARIANT", "ESTABLISHED", "CONTINGENT"
        }:
            raise SituatedReconstructionPacketError(
                "active claim status is invalid"
            )
        _required_text(claim["event_hash"], label="event_hash")
        active_ids.append(claim_id)
    if active_ids != sorted(set(active_ids)):
        raise SituatedReconstructionPacketError(
            "active claims are not canonical"
        )
    excluded_ids: list[str] = []
    for claim in closed["excluded_claims"]:
        if not isinstance(claim, dict) or set(claim) != {
            "claim_id", "status", "event_hash", "exclusion_reason"
        }:
            raise SituatedReconstructionPacketError(
                "excluded claim fields are invalid"
            )
        excluded_ids.append(
            _required_text(claim["claim_id"], label="claim_id")
        )
        _required_text(claim["status"], label="status")
        _required_text(claim["event_hash"], label="event_hash")
        _required_text(
            claim["exclusion_reason"],
            label="exclusion_reason",
        )
    if excluded_ids != sorted(set(excluded_ids)):
        raise SituatedReconstructionPacketError(
            "excluded claims are not canonical"
        )
    if set(active_ids) & set(excluded_ids):
        raise SituatedReconstructionPacketError(
            "claim cannot be both active and excluded"
        )
    bounded = {
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    for field, expected in bounded.items():
        if closed[field] != expected:
            raise SituatedReconstructionPacketError(
                f"invalid projection bounded field {field}"
            )
    return {**closed, "projection_hash": supplied_hash}


def _verified_binding_map(
    bindings: Sequence[Mapping[str, Any]],
    *,
    environment_fingerprint: str,
) -> dict[str, dict[str, Any]]:
    if isinstance(bindings, (str, bytes)) or not isinstance(bindings, Sequence):
        raise SituatedReconstructionPacketError(
            "bindings must be a sequence"
        )
    result: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        if not isinstance(binding, Mapping):
            raise SituatedReconstructionPacketError(
                "binding is invalid: binding must be a mapping"
            )
        closed = _closed_copy(dict(binding), label="binding")
        try:
            verify_guarantee_environment_binding(closed)
        except GuaranteeEnvironmentBindingError as exc:
            raise SituatedReconstructionPacketError(
                f"binding is invalid: {exc}"
            ) from exc
        claim_id = closed["guarantee_id"]
        if claim_id in result:
            raise SituatedReconstructionPacketError(
                "duplicate binding for active claim"
            )
        if closed["status"] != "BOUND":
            raise SituatedReconstructionPacketError(
                "binding is invalid: active claim binding is not BOUND"
            )
        if closed["environment_fingerprint"] != environment_fingerprint:
            raise SituatedReconstructionPacketError(
                "binding is invalid: environment fingerprint mismatch"
            )
        result[claim_id] = closed
    return result


def build_situated_reconstruction_packet(
    *,
    projection: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
    objective: str,
    unresolved: Sequence[str],
    required_checks: Sequence[str],
) -> dict[str, Any]:
    """Assemble the minimum verified state needed for situated re-entry."""
    verified_projection = _verify_projection(projection)
    environment = verified_projection[
        "current_environment_fingerprint"
    ]
    binding_map = _verified_binding_map(
        bindings,
        environment_fingerprint=environment,
    )
    active_ids = {
        claim["claim_id"]
        for claim in verified_projection["active_claims"]
    }
    extra = set(binding_map) - active_ids
    if extra:
        raise SituatedReconstructionPacketError(
            "binding supplied for nonactive claim"
        )
    active: list[dict[str, Any]] = []
    for claim in verified_projection["active_claims"]:
        binding = binding_map.get(claim["claim_id"])
        if binding is None:
            raise SituatedReconstructionPacketError(
                f"missing binding for active claim {claim['claim_id']}"
            )
        active.append(
            {
                **claim,
                "binding_hash": binding["binding_hash"],
            }
        )
    body: dict[str, Any] = {
        "type": PACKET_TYPE,
        "version": PACKET_VERSION,
        "environment_fingerprint": environment,
        "projection_hash": verified_projection["projection_hash"],
        "history_hash": verified_projection["history_hash"],
        "objective": _required_text(objective, label="objective"),
        "active_claims": active,
        "excluded_claims": deepcopy(
            verified_projection["excluded_claims"]
        ),
        "unresolved": _text_list(unresolved, label="unresolved"),
        "required_checks": _text_list(
            required_checks,
            label="required_checks",
        ),
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    return {
        **body,
        "packet_hash": _canonical_hash(body, label="packet"),
    }


def verify_situated_reconstruction_packet(
    packet: Mapping[str, Any],
) -> bool:
    """Verify packet identity, schema, ordering, and bounded authority."""
    if not isinstance(packet, Mapping):
        raise SituatedReconstructionPacketError(
            "packet must be a mapping"
        )
    closed = _closed_copy(dict(packet), label="packet")
    required_fields = {
        "type",
        "version",
        "environment_fingerprint",
        "projection_hash",
        "history_hash",
        "objective",
        "active_claims",
        "excluded_claims",
        "unresolved",
        "required_checks",
        "accepted",
        "truth_claimed",
        "write_authority",
        "execution_authority",
        "canonical_mutation",
        "packet_hash",
    }
    if set(closed) != required_fields:
        raise SituatedReconstructionPacketError(
            "packet fields are invalid"
        )
    supplied_hash = closed.pop("packet_hash")
    if (
        not isinstance(supplied_hash, str)
        or not supplied_hash
        or _canonical_hash(closed, label="packet") != supplied_hash
    ):
        raise SituatedReconstructionPacketError(
            "packet hash mismatch"
        )
    if closed["type"] != PACKET_TYPE:
        raise SituatedReconstructionPacketError("packet type mismatch")
    if closed["version"] != PACKET_VERSION:
        raise SituatedReconstructionPacketError("packet version mismatch")
    for field in (
        "environment_fingerprint",
        "projection_hash",
        "history_hash",
        "objective",
    ):
        _required_text(closed[field], label=field)
    active_ids: list[str] = []
    if not isinstance(closed["active_claims"], list):
        raise SituatedReconstructionPacketError(
            "active_claims must be a list"
        )
    for claim in closed["active_claims"]:
        if not isinstance(claim, dict) or set(claim) != {
            "claim_id", "status", "event_hash", "binding_hash"
        }:
            raise SituatedReconstructionPacketError(
                "active claim fields are invalid"
            )
        active_ids.append(
            _required_text(claim["claim_id"], label="claim_id")
        )
        if claim["status"] not in {
            "INVARIANT", "ESTABLISHED", "CONTINGENT"
        }:
            raise SituatedReconstructionPacketError(
                "active claim status is invalid"
            )
        _required_text(claim["event_hash"], label="event_hash")
        _required_text(claim["binding_hash"], label="binding_hash")
    if active_ids != sorted(set(active_ids)):
        raise SituatedReconstructionPacketError(
            "active claims are not canonical"
        )
    if not isinstance(closed["excluded_claims"], list):
        raise SituatedReconstructionPacketError(
            "excluded_claims must be a list"
        )
    excluded_ids: list[str] = []
    for claim in closed["excluded_claims"]:
        if not isinstance(claim, dict) or set(claim) != {
            "claim_id", "status", "event_hash", "exclusion_reason"
        }:
            raise SituatedReconstructionPacketError(
                "excluded claim fields are invalid"
            )
        excluded_ids.append(
            _required_text(claim["claim_id"], label="claim_id")
        )
        _required_text(claim["status"], label="status")
        _required_text(claim["event_hash"], label="event_hash")
        _required_text(
            claim["exclusion_reason"],
            label="exclusion_reason",
        )
    if excluded_ids != sorted(set(excluded_ids)):
        raise SituatedReconstructionPacketError(
            "excluded claims are not canonical"
        )
    if set(active_ids) & set(excluded_ids):
        raise SituatedReconstructionPacketError(
            "claim cannot be both active and excluded"
        )
    _text_list(closed["unresolved"], label="unresolved")
    _text_list(closed["required_checks"], label="required_checks")
    bounded = {
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    for field, expected in bounded.items():
        if closed[field] != expected:
            raise SituatedReconstructionPacketError(
                f"invalid bounded field {field}"
            )
    return True


def consume_situated_reconstruction_packet(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the minimal verified frame presented to any capable model."""
    verify_situated_reconstruction_packet(packet)
    return {
        "status": "SITUATED_RECONSTRUCTION_READY",
        "packet_hash": packet["packet_hash"],
        "environment_fingerprint": packet["environment_fingerprint"],
        "objective": packet["objective"],
        "active_claims": deepcopy(packet["active_claims"]),
        "excluded_claims": deepcopy(packet["excluded_claims"]),
        "unresolved": list(packet["unresolved"]),
        "required_checks": list(packet["required_checks"]),
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }