"""Read-only MCP boundary for frozen IDX admission checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from holosim.idx_public_check import check_idx_packet


SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas"
PACKET_SCHEMA_PATH = SCHEMA_ROOT / "idx-spine-packet.schema.json"
RECEIPT_SCHEMA_PATH = SCHEMA_ROOT / "idx-check-receipt.schema.json"

mcp = MCPServer("HOLO Frozen IDX")


@mcp.tool()
def idx_check(
    frozen_idx: str,
    packet: dict[str, Any],
) -> dict[str, Any]:
    """Check a moving Spine packet against a frozen IDX without authority."""
    return check_idx_packet(frozen_idx, packet)


@mcp.resource("holo://schemas/idx-spine-packet")
def idx_spine_packet_schema() -> str:
    """Return the public moving-Spine packet schema."""
    return PACKET_SCHEMA_PATH.read_text(encoding="utf-8")


@mcp.resource("holo://schemas/idx-check-receipt")
def idx_check_receipt_schema() -> str:
    """Return the public IDX-check receipt schema."""
    return RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8")


def main() -> None:
    """Run the read-only MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
