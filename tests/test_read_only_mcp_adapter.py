import asyncio
import copy
import hashlib
import json
from pathlib import Path

from mcp import Client

from holosim.mcp_adapter import idx_check, mcp


PACKET_RESOURCE = (
    "holo://schemas/idx-spine-packet"
)

RECEIPT_RESOURCE = (
    "holo://schemas/idx-check-receipt"
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def frozen_idx() -> str:
    return (
        "IDX:v=1;n=1\n"
        f"S1=CORE@{digest('original')}\n"
        "ACTIVE_HASH=frozen-head\n"
    )


def moving_packet(
    payload: str = "original",
) -> dict:
    return {
        "version": 1,
        "active_hash": "frozen-head",
        "slots": [
            {
                "name": "CORE",
                "payload": payload,
            }
        ],
    }


def test_idx_check_is_read_only_and_returns_pass():
    idx_source = frozen_idx()
    packet = moving_packet()
    packet_before = copy.deepcopy(packet)

    result = idx_check(
        frozen_idx=idx_source,
        packet=packet,
    )

    assert result == {
        "status": "PASS",
        "code": "IDX_MATCH",
        "fused": False,
        "slot": None,
        "expected": None,
        "observed": None,
    }
    assert idx_source == frozen_idx()
    assert packet == packet_before


def test_idx_check_returns_abort_without_authority():
    result = idx_check(
        frozen_idx=frozen_idx(),
        packet=moving_packet("changed"),
    )

    assert result["status"] == "ABORT"
    assert result["code"] == "SLOT_HASH_MISMATCH"
    assert result["fused"] is False
    assert result["slot"] == "CORE"
    assert "authority" not in result


def test_idx_check_returns_closed_input_error():
    result = idx_check(
        frozen_idx=frozen_idx(),
        packet={
            "version": 1,
        },
    )

    assert result["status"] == "ERROR"
    assert result["code"] == "IDX_PACKET_INVALID"
    assert result["fused"] is False
    assert result["error"]


async def inspect_server():
    async with Client(
        mcp,
        raise_exceptions=True,
    ) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()

        packet_schema = await client.read_resource(
            PACKET_RESOURCE
        )
        receipt_schema = await client.read_resource(
            RECEIPT_RESOURCE
        )

        tool_result = await client.call_tool(
            "idx_check",
            {
                "frozen_idx": frozen_idx(),
                "packet": moving_packet(),
            },
        )

        return {
            "tools": tools,
            "resources": resources,
            "packet_schema": packet_schema,
            "receipt_schema": receipt_schema,
            "tool_result": tool_result,
        }


def test_mcp_server_exposes_only_declared_read_boundaries():
    result = asyncio.run(inspect_server())

    tool_names = [
        tool.name
        for tool in result["tools"].tools
    ]
    resource_uris = [
        str(resource.uri)
        for resource in result["resources"].resources
    ]

    assert tool_names == [
        "idx_check",
    ]
    assert sorted(resource_uris) == sorted(
        [
            PACKET_RESOURCE,
            RECEIPT_RESOURCE,
        ]
    )

    assert result["tool_result"].structured_content == {
        "status": "PASS",
        "code": "IDX_MATCH",
        "fused": False,
        "slot": None,
        "expected": None,
        "observed": None,
    }


def test_mcp_resources_match_public_schema_files():
    result = asyncio.run(inspect_server())

    packet_text = (
        result["packet_schema"]
        .contents[0]
        .text
    )
    receipt_text = (
        result["receipt_schema"]
        .contents[0]
        .text
    )

    assert json.loads(packet_text) == json.loads(
        Path(
            "schemas/idx-spine-packet.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert json.loads(receipt_text) == json.loads(
        Path(
            "schemas/idx-check-receipt.schema.json"
        ).read_text(encoding="utf-8")
    )