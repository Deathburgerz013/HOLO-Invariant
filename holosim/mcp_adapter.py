"""Read-only MCP boundary for frozen IDX admission checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from holosim.idx_manager import IDXManager


SCHEMA_ROOT = (
    Path(__file__).resolve().parents[1]
    / "schemas"
)

PACKET_SCHEMA_PATH = (
    SCHEMA_ROOT
    / "idx-spine-packet.schema.json"
)

RECEIPT_SCHEMA_PATH = (
    SCHEMA_ROOT
    / "idx-check-receipt.schema.json"
)


mcp = MCPServer(
    "HOLO Frozen IDX",
)


def _require_packet(
    packet: dict[str, Any],
) -> tuple[
    int,
    str,
    tuple[tuple[str, str], ...],
]:
    if type(packet) is not dict:
        raise TypeError(
            "IDX packet must be an object"
        )

    expected_keys = {
        "version",
        "active_hash",
        "slots",
    }
    observed_keys = set(packet)

    if observed_keys != expected_keys:
        missing = sorted(
            expected_keys - observed_keys
        )
        extra = sorted(
            observed_keys - expected_keys
        )
        raise ValueError(
            "IDX packet keys do not match contract: "
            f"missing={missing}, extra={extra}"
        )

    version = packet["version"]
    if (
        type(version) is not int
        or version < 1
    ):
        raise ValueError(
            "IDX packet version must be an integer "
            "greater than or equal to 1"
        )

    active_hash = packet["active_hash"]
    if (
        type(active_hash) is not str
        or not active_hash
    ):
        raise ValueError(
            "IDX packet active_hash must be a "
            "non-empty string"
        )

    raw_slots = packet["slots"]
    if (
        type(raw_slots) is not list
        or not raw_slots
    ):
        raise ValueError(
            "IDX packet slots must be a "
            "non-empty array"
        )

    slots: list[tuple[str, str]] = []

    for index, raw_slot in enumerate(
        raw_slots,
        start=1,
    ):
        if type(raw_slot) is not dict:
            raise TypeError(
                f"IDX packet slot {index} "
                "must be an object"
            )

        if set(raw_slot) != {
            "name",
            "payload",
        }:
            raise ValueError(
                f"IDX packet slot {index} must "
                "contain only name and payload"
            )

        name = raw_slot["name"]
        payload = raw_slot["payload"]

        if (
            type(name) is not str
            or not name
        ):
            raise ValueError(
                f"IDX packet slot {index} name "
                "must be a non-empty string"
            )

        if type(payload) is not str:
            raise TypeError(
                f"IDX packet slot {index} payload "
                "must be a string"
            )

        slots.append(
            (
                name,
                payload,
            )
        )

    return (
        version,
        active_hash,
        tuple(slots),
    )


@mcp.tool()
def idx_check(
    frozen_idx: str,
    packet: dict[str, Any],
) -> dict[str, Any]:
    """Check a moving Spine packet against a frozen IDX.

    This operation is read-only. It grants no authority,
    performs no rebirth, appends no chain record, and
    modifies no caller state.
    """
    try:
        if (
            type(frozen_idx) is not str
            or not frozen_idx.strip()
        ):
            raise ValueError(
                "Frozen IDX source must be a "
                "non-empty string"
            )

        version, active_hash, slots = (
            _require_packet(packet)
        )

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

    except (
        TypeError,
        ValueError,
    ) as error:
        return {
            "status": "ERROR",
            "code": "IDX_PACKET_INVALID",
            "fused": False,
            "error": str(error),
        }


@mcp.resource(
    "holo://schemas/idx-spine-packet"
)
def idx_spine_packet_schema() -> str:
    """Return the public moving-Spine packet schema."""
    return PACKET_SCHEMA_PATH.read_text(
        encoding="utf-8",
    )


@mcp.resource(
    "holo://schemas/idx-check-receipt"
)
def idx_check_receipt_schema() -> str:
    """Return the public IDX-check receipt schema."""
    return RECEIPT_SCHEMA_PATH.read_text(
        encoding="utf-8",
    )


def main() -> None:
    """Run the read-only MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()