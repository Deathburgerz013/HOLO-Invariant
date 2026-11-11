
"""HTTP boundary tests for the Mechanical Continuity Book."""

import http.client
import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from holosim.general_system_lineage import build_general_system_lineage
from holosim.mechanical_continuity_book import MechanicalContinuityBookError
from holosim.mechanical_continuity_book_server import (
    _BookServer,
    serve_book,
)


def make_report():
    return build_general_system_lineage(
        systems=[
            {"system_id": "alpha", "domain": "test", "label": "Alpha"},
            {"system_id": "beta", "domain": "test", "label": "Beta"},
        ],
        observations=[
            {
                "observation_id": "obs-1",
                "system_id": "alpha",
                "source_id": "fixture",
                "boundary": "local",
                "evidence_hash": "a" * 64,
                "finding": "Observed fixture",
            }
        ],
        relationships=[],
        corrections=[],
    )


@pytest.fixture
def running_book(tmp_path):
    report = make_report()
    path = tmp_path / "lineage.json"
    original = json.dumps(report, sort_keys=True).encode("utf-8")
    path.write_bytes(original)

    server = _BookServer(
        ("127.0.0.1", 0),
        path,
        report["lineage_hash"],
    )
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()

    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        yield base, path, original, report
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def request(url, method="GET", data=None):
    req = Request(url, data=data, method=method)
    try:
        with urlopen(req, timeout=3) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers), error.read()


def test_book_serves_cover_and_contents(running_book):
    base, _, _, report = running_book

    status, headers, body = request(base + "/")
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert b"Holo/Sim" in body
    assert b"MECHANICAL CONTINUITY" in body

    status, headers, body = request(base + "/api/contents")
    data = json.loads(body)

    assert status == 200
    assert headers["Content-Type"].startswith("application/json")
    assert data["lineage_hash"] == report["lineage_hash"]
    assert len(data["contents"]) == 3
    assert data["accepted"] is False
    assert data["truth_claimed"] is False
    assert data["write_authority"] == "NONE"


def test_exact_record_navigation(running_book):
    base, _, _, _ = running_book

    query = urlencode({"kind": "observations", "id": "obs-1"})
    status, _, body = request(base + "/api/page?" + query)
    page = json.loads(body)

    assert status == 200
    assert page["kind"] == "observations"
    assert page["id"] == "obs-1"
    assert page["record"]["finding"] == "Observed fixture"
    assert len(page["record_hash"]) == 64


@pytest.mark.parametrize(
    "query",
    [
        "",
        "kind=observations",
        "id=obs-1",
        "kind=unknown&id=obs-1",
        "kind=observations&id=missing",
        "kind=observations&id=",
        "kind=observations&id=obs-1&id=obs-1",
        "kind=observations&id=obs-1&extra=1",
        "kind=observations&id=obs-1&",
    ],
)
def test_invalid_page_queries_rejected(running_book, query):
    base, _, _, _ = running_book

    status, _, body = request(base + "/api/page?" + query)

    assert status == 400
    assert json.loads(body)["status"] == "REJECTED"


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_mutating_methods_rejected(running_book, method):
    base, path, original, _ = running_book

    status, _, body = request(
        base + "/api/contents",
        method=method,
        data=b'{"change":true}',
    )

    assert status == 405
    assert json.loads(body)["write_authority"] == "NONE"
    assert path.read_bytes() == original


def test_unknown_route_rejected(running_book):
    base, _, _, _ = running_book

    status, _, body = request(base + "/not-a-route")

    assert status == 404
    assert json.loads(body)["status"] == "not_found"


def test_health_has_no_authority(running_book):
    base, _, _, _ = running_book

    status, _, body = request(base + "/healthz")
    data = json.loads(body)

    assert status == 200
    assert data["accepted"] is False
    assert data["truth_claimed"] is False
    assert data["write_authority"] == "NONE"
    assert data["execution_authority"] == "NONE"


def test_security_headers(running_book):
    base, _, _, _ = running_book

    status, headers, _ = request(base + "/")

    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in headers["Content-Security-Policy"]


def test_report_is_not_reloaded_after_startup(running_book):
    base, path, _, report = running_book

    path.write_text('{"tampered":true}', encoding="utf-8")

    status, _, body = request(base + "/api/contents")
    data = json.loads(body)

    assert status == 200
    assert data["lineage_hash"] == report["lineage_hash"]
    assert len(data["contents"]) == 3


def test_wrong_retained_identity_rejected_before_binding(tmp_path):
    report = make_report()
    path = tmp_path / "lineage.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(
        MechanicalContinuityBookError,
        match="identity mismatch",
    ):
        _BookServer(("127.0.0.1", 0), path, "0" * 64)


@pytest.mark.parametrize(
    "host",
    ["0.0.0.0", "192.168.1.20", "example.com", "::1"],
)
def test_non_loopback_or_unsupported_hosts_rejected(host):
    with pytest.raises(ValueError, match="127.0.0.1"):
        serve_book(
            "unused.json",
            "0" * 64,
            host=host,
            open_browser=False,
        )


@pytest.mark.parametrize("port", [True, -1, 65536, "8766"])
def test_invalid_ports_rejected(port):
    with pytest.raises(ValueError, match="port"):
        serve_book(
            "unused.json",
            "0" * 64,
            port=port,
            open_browser=False,
        )


def test_source_remains_unchanged_after_read_requests(running_book):
    base, path, original, _ = running_book

    request(base + "/")
    request(base + "/api/contents")
    request(base + "/api/page?kind=systems&id=alpha")
    request(base + "/healthz")

    assert path.read_bytes() == original
