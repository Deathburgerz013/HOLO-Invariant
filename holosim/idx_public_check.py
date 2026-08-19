"""Dependency-free public frozen IDX comparison boundary."""

from __future__ import annotations

from typing import Any

from holosim.idx_manager import IDXManager


def require_idx_packet(
    packet: dict[str, Any],
) -> tuple[int, str, tuple[tuple[str, str], ...]]:
    if type(packet) is not dict:
        raise TypeError("IDX packet must be an object")

    expected_keys = {"version", "active_hash", "slots"}
    observed_keys = set(packet)
    if observed_keys != expected_keys:
        missing = sorted(expected_keys - observed_keys)
        extra = sorted(observed_keys - expected_keys)
        raise ValueError(
            "IDX packet keys do not match contract: "
            f"missing={missing}, extra={extra}"
        )

    version = packet["version"]
    if type(version) is not int or version < 1:
        raise ValueError(
            "IDX packet version must be an integer greater than or equal to 1"
        )

    active_hash = packet["active_hash"]
    if type(active_hash) is not str or not active_hash:
        raise ValueError("IDX packet active_hash must be a non-empty string")

    raw_slots = packet["slots"]
    if type(raw_slots) is not list or not raw_slots:
        raise ValueError("IDX packet slots must be a non-empty array")

    slots: list[tuple[str, str]] = []
    for index, raw_slot in enumerate(raw_slots, start=1):
        if type(raw_slot) is not dict:
            raise TypeError(f"IDX packet slot {index} must be an object")
        if set(raw_slot) != {"name", "payload"}:
            raise ValueError(
                f"IDX packet slot {index} must contain only name and payload"
            )

        name = raw_slot["name"]
        payload = raw_slot["payload"]
        if type(name) is not str or not name:
            raise ValueError(
                f"IDX packet slot {index} name must be a non-empty string"
            )
        if type(payload) is not str:
            raise TypeError(f"IDX packet slot {index} payload must be a string")
        slots.append((name, payload))

    return version, active_hash, tuple(slots)


def check_idx_packet(
    frozen_idx: str,
    packet: dict[str, Any],
) -> dict[str, Any]:
    """Compare supplied values without granting authority or retaining state."""
    try:
        if type(frozen_idx) is not str or not frozen_idx.strip():
            raise ValueError("Frozen IDX source must be a non-empty string")

        version, active_hash, slots = require_idx_packet(packet)
        manager = IDXManager()
        manager.parse_spine(frozen_idx)
        gate = manager.build_frozen_gate()
        admission = gate.check(
            version=version,
            active_hash=active_hash,
            slots=slots,
        )
        return {
            "status": admission.status,
            "code": admission.code,
            "fused": admission.fused,
            "slot": admission.slot,
            "expected": admission.expected,
            "observed": admission.observed,
        }
    except (TypeError, ValueError) as error:
        return {
            "status": "ERROR",
            "code": "IDX_PACKET_INVALID",
            "fused": False,
            "error": str(error),
        }
