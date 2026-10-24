import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from holosim.bounded_http_observer import (
    BoundedHTTPObserverError,
    make_loopback_http_observer,
)
from holosim.canonical import stable_hash
from holosim.provider_neutral_observer_transport import (
    transport_situated_reconstruction_packet,
    verify_provider_neutral_observer_receipt,
)


def packet():
    body = {
        "type": "holo_situated_reconstruction_packet",
        "version": 1,
        "environment_fingerprint": "environment:test",
        "projection_hash": "projection:test",
        "history_hash": "history:test",
        "objective": "Test bounded network observation.",
        "active_claims": [],
        "excluded_claims": [],
        "unresolved": ["Remote observer identity is unverified."],
        "required_checks": ["Verify the returned receipt."],
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    return {**body, "packet_hash": stable_hash(body)}


@contextmanager
def server(body=b'{"finding":"OBSERVED"}', status=200):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers["Content-Length"])
            received.append(self.rfile.read(size))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{httpd.server_port}/observe", received
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def test_two_local_observers_receive_identical_packet():
    with server() as (url_a, received_a):
        with server(b'{"finding":"DISPUTED"}') as (url_b, received_b):
            source = packet()
            receipts = transport_situated_reconstruction_packet(
                packet=source,
                observers=[
                    ("local:a", make_loopback_http_observer(url_a)),
                    ("local:b", make_loopback_http_observer(url_b)),
                ],
            )

            assert received_a == received_b
            assert len(receipts) == 2
            assert receipts[0]["response"] != receipts[1]["response"]

            for receipt in receipts:
                assert verify_provider_neutral_observer_receipt(
                    receipt, packet=source
                )
                assert receipt["accepted"] is False
                assert receipt["truth_claimed"] is False
                assert receipt["write_authority"] == "NONE"
                assert receipt["execution_authority"] == "NONE"


@pytest.mark.parametrize("url", [
    "https://127.0.0.1:8000/observe",
    "http://localhost:8000/observe",
    "http://8.8.8.8:8000/observe",
    "http://127.0.0.1:8000@evil.example/",
    "http://user:pass@127.0.0.1:8000/",
    "http://127.0.0.1:8000/#fragment",
])
def test_rejects_disallowed_endpoints(url):
    with pytest.raises(BoundedHTTPObserverError):
        make_loopback_http_observer(url)


def test_redirect_rejected():
    with server(status=302) as (url, _):
        with pytest.raises(
            BoundedHTTPObserverError, match="unexpected HTTP status"
        ):
            make_loopback_http_observer(url)(b"{}")


def test_oversized_response_rejected():
    with server(body=b"x" * 100) as (url, _):
        with pytest.raises(
            BoundedHTTPObserverError, match="oversized"
        ):
            make_loopback_http_observer(
                url, max_response_bytes=16
            )(b"{}")


def test_duplicate_json_keys_rejected():
    with server(body=b'{"finding":1,"finding":2}') as (url, _):
        with pytest.raises(
            BoundedHTTPObserverError, match="duplicate JSON key"
        ):
            make_loopback_http_observer(url)(b"{}")


def test_non_object_response_rejected():
    with server(body=b'["OBSERVED"]') as (url, _):
        with pytest.raises(
            BoundedHTTPObserverError, match="JSON object"
        ):
            make_loopback_http_observer(url)(b"{}")


def test_invalid_timeout_and_limits_rejected():
    for timeout in (0, -1, float("nan"), float("inf"), True):
        with pytest.raises(BoundedHTTPObserverError):
            make_loopback_http_observer(
                "http://127.0.0.1:8000/", timeout=timeout
            )

    for limit in (0, -1, True, 65537):
        with pytest.raises(BoundedHTTPObserverError):
            make_loopback_http_observer(
                "http://127.0.0.1:8000/",
                max_response_bytes=limit,
            )
