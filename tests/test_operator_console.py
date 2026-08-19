import json
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from holosim.core import HoloChain
from holosim.operator_console import (
    _OperatorServer,
    build_operator_snapshot,
    serve_operator_console,
)


def _read(url: str) -> tuple[int, str, bytes]:
    try:
        with urlopen(url, timeout=3) as response:
            return response.status, response.headers["Content-Type"], response.read()
    except HTTPError as error:
        return error.code, error.headers["Content-Type"], error.read()


def test_snapshot_reports_verified_local_chain_without_authority(tmp_path):
    chain_path = tmp_path / "operator.jsonl"
    HoloChain(chain_path).append({"event": "operator console test"})

    snapshot = build_operator_snapshot(chain_path)

    assert snapshot["type"] == "holo_operator_snapshot"
    assert snapshot["service"]["verify"]["status"] == "ok"
    assert snapshot["service"]["verify"]["entries"] == 1
    assert snapshot["timeline"][0]["idx"] == 1
    assert snapshot["accepted"] is False
    assert snapshot["truth_claimed"] is False
    assert snapshot["write_authority"] == "NONE"
    assert snapshot["execution_authority"] == "NONE"


def test_console_serves_page_snapshot_and_health_from_loopback(tmp_path):
    chain_path = tmp_path / "operator.jsonl"
    HoloChain(chain_path).append("visible retained event")
    server = _OperatorServer(("127.0.0.1", 0), chain_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        page_status, page_type, page = _read(base + "/")
        api_status, api_type, api_body = _read(base + "/api/snapshot")
        health_status, _, health_body = _read(base + "/healthz")
        missing_status, _, missing_body = _read(base + "/missing")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    snapshot = json.loads(api_body)
    health = json.loads(health_body)
    missing = json.loads(missing_body)
    assert page_status == 200
    assert page_type.startswith("text/html")
    assert b"HOLO / OPERATOR CONSOLE" in page
    assert b'href="/playground"' in page
    assert api_status == 200
    assert api_type.startswith("application/json")
    assert snapshot["service"]["verify"]["entries"] == 1
    assert snapshot["timeline"][0]["preview"] == "visible retained event"
    assert health_status == 200
    assert health == {"status": "ok", "write_authority": "NONE"}
    assert missing_status == 404
    assert missing == {"status": "not_found", "path": "/missing"}


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "example.com"])
def test_console_rejects_non_loopback_hosts(host):
    with pytest.raises(ValueError, match="loopback-only"):
        serve_operator_console(host=host, open_browser=False)


@pytest.mark.parametrize("port", [True, -1, 65536, "8765"])
def test_console_rejects_invalid_ports(port):
    with pytest.raises(ValueError, match="port must be"):
        serve_operator_console(port=port, open_browser=False)
