import hashlib
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from holosim.core import HoloChain
from holosim.operator_console import (
    PLAYGROUND_HTML,
    _OperatorServer,
    build_idx_playground_receipt,
)


def digest(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def frozen_idx() -> str:
    return (
        "IDX:v=1;n=1\n"
        f"S1=CORE@{digest('original')}\n"
        "ACTIVE_HASH=frozen-head\n"
    )


def packet(
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


def post_json(
    url: str,
    value: dict,
) -> tuple[int, str, bytes]:
    request = Request(
        url,
        data=json.dumps(value).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=3,
        ) as response:
            return (
                response.status,
                response.headers["Content-Type"],
                response.read(),
            )
    except HTTPError as error:
        return (
            error.code,
            error.headers["Content-Type"],
            error.read(),
        )


def test_playground_receipt_passes_without_authority():
    result = build_idx_playground_receipt(
        frozen_idx(),
        packet(),
    )

    assert result == {
        "status": "PASS",
        "code": "IDX_MATCH",
        "fused": False,
        "slot": None,
        "expected": None,
        "observed": None,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


def test_playground_receipt_exposes_exact_mismatch():
    result = build_idx_playground_receipt(
        frozen_idx(),
        packet("changed"),
    )

    assert result["status"] == "ABORT"
    assert result["code"] == (
        "SLOT_HASH_MISMATCH"
    )
    assert result["slot"] == "CORE"
    assert result["expected"] == digest(
        "original"
    )
    assert result["observed"] == digest(
        "changed"
    )
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert (
        result["execution_authority"]
        == "NONE"
    )


def test_playground_page_contains_visible_relations():
    encoded = PLAYGROUND_HTML.encode("utf-8")

    assert b"HOLO / CONTINUITY PLAYGROUND" in encoded
    assert b"FROZEN IDX" in encoded
    assert b"MOVING SPINE" in encoded
    assert b"CHECK RELATION" in encoded
    assert b'id="continuityGraph"' in encoded
    assert b'id="frozenInput"' in encoded
    assert b'id="packetInput"' in encoded
    assert b'id="receipt"' in encoded


def test_playground_endpoint_is_read_only(
    tmp_path: Path,
):
    chain_path = tmp_path / "operator.jsonl"
    HoloChain(chain_path).append(
        "preserved chain state"
    )
    before = chain_path.read_bytes()

    server = _OperatorServer(
        ("127.0.0.1", 0),
        chain_path,
    )
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()

    try:
        base = (
            "http://127.0.0.1:"
            f"{server.server_address[1]}"
        )

        with urlopen(
            base + "/playground",
            timeout=3,
        ) as response:
            page_status = response.status
            page_type = response.headers[
                "Content-Type"
            ]
            page = response.read()

        api_status, api_type, api_body = (
            post_json(
                base + "/api/idx-check",
                {
                    "frozen_idx": frozen_idx(),
                    "packet": packet(),
                },
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    result = json.loads(api_body)

    assert page_status == 200
    assert page_type.startswith("text/html")
    assert (
        b"HOLO / CONTINUITY PLAYGROUND"
        in page
    )

    assert api_status == 200
    assert api_type.startswith(
        "application/json"
    )
    assert result["status"] == "PASS"
    assert result["code"] == "IDX_MATCH"
    assert result["write_authority"] == "NONE"

    assert chain_path.read_bytes() == before


def test_playground_endpoint_rejects_bad_envelope(
    tmp_path: Path,
):
    chain_path = tmp_path / "operator.jsonl"

    server = _OperatorServer(
        ("127.0.0.1", 0),
        chain_path,
    )
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()

    try:
        base = (
            "http://127.0.0.1:"
            f"{server.server_address[1]}"
        )
        status, content_type, body = post_json(
            base + "/api/idx-check",
            {
                "packet": packet(),
                "authority": "GRANTED",
            },
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    result = json.loads(body)

    assert status == 400
    assert content_type.startswith(
        "application/json"
    )
    assert result["status"] == "ERROR"
    assert result["code"] == (
        "IDX_REQUEST_INVALID"
    )
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert (
        result["execution_authority"]
        == "NONE"
    )