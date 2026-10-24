import pytest

from holosim.bounded_http_observer import (
    BoundedHTTPObserverError,
    make_loopback_http_observer,
)


def test_rejects_oversized_request_before_connecting():
    adapter = make_loopback_http_observer(
        "http://127.0.0.1:1/"
    )

    with pytest.raises(
        BoundedHTTPObserverError,
        match="oversized request",
    ):
        adapter(b"x" * 65537)


def test_rejects_nonfinite_json():
    from test_bounded_http_observer import server

    with server(body=b'{"value":NaN}') as (url, _):
        with pytest.raises(
            BoundedHTTPObserverError,
            match="non-finite JSON",
        ):
            make_loopback_http_observer(url)(b"{}")


def test_rejects_incomplete_http_body():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers["Content-Length"])
            self.rfile.read(size)

            body = b'{"finding":"OBSERVED"}'

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body) + 100))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            self.close_connection = True

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        adapter = make_loopback_http_observer(
            f"http://127.0.0.1:{httpd.server_port}/observe",
            timeout=1.0,
        )

        with pytest.raises(
            BoundedHTTPObserverError,
            match="HTTP transport failed|incomplete",
        ):
            adapter(b"{}")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def test_rejects_slow_drip_beyond_total_deadline():
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers["Content-Length"])
            self.rfile.read(size)

            body = b'{"finding":"OBSERVED"}'

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()

            for byte in body:
                try:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                except OSError:
                    break
                time.sleep(0.08)

            self.close_connection = True

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        adapter = make_loopback_http_observer(
            f"http://127.0.0.1:{httpd.server_port}/observe",
            timeout=0.2,
        )

        start_time = time.monotonic()

        with pytest.raises(
            BoundedHTTPObserverError,
            match="deadline|timeout|HTTP transport failed",
        ):
            adapter(b"{}")

        elapsed = time.monotonic() - start_time
        assert elapsed < 1.0, (
            f"Total deadline exceeded: {elapsed:.3f}s"
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def test_rejects_delayed_headers_within_deadline():
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers["Content-Length"])
            self.rfile.read(size)

            time.sleep(0.8)

            try:
                body = b'{"finding":"OBSERVED"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        adapter = make_loopback_http_observer(
            f"http://127.0.0.1:{httpd.server_port}/observe",
            timeout=0.2,
        )

        start = time.monotonic()

        with pytest.raises(
            BoundedHTTPObserverError,
            match="deadline|timeout|HTTP transport failed",
        ):
            adapter(b"{}")

        elapsed = time.monotonic() - start
        assert elapsed < 0.6, (
            f"Delayed headers exceeded deadline: {elapsed:.3f}s"
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def test_rejects_slow_drip_headers_within_deadline():
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers["Content-Length"])
            self.rfile.read(size)

            body = b'{"finding":"OBSERVED"}'
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode()
                + b"Connection: close\r\n\r\n"
                + body
            )

            for byte in response:
                try:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                except OSError:
                    break
                time.sleep(0.08)

            self.close_connection = True

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        adapter = make_loopback_http_observer(
            f"http://127.0.0.1:{httpd.server_port}/observe",
            timeout=0.2,
        )

        start = time.monotonic()

        with pytest.raises(
            BoundedHTTPObserverError,
            match="deadline|timeout|HTTP transport failed",
        ):
            adapter(b"{}")

        elapsed = time.monotonic() - start
        assert elapsed < 1.0, (
            f"Slow-drip headers exceeded deadline: {elapsed:.3f}s"
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def test_accepts_json_content_type_with_charset():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers["Content-Length"])
            self.rfile.read(size)

            body = b'{"finding":"OBSERVED"}'
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        adapter = make_loopback_http_observer(
            f"http://127.0.0.1:{httpd.server_port}/observe"
        )
        assert adapter(b"{}") == {"finding": "OBSERVED"}
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def test_large_fast_response_with_short_deadline():
    import time
    from test_bounded_http_observer import server

    body = b'{"d":"' + b"A" * 60000 + b'"}'

    with server(body=body) as (url, _):
        adapter = make_loopback_http_observer(
            url,
            timeout=0.5,
        )

        start = time.monotonic()
        result = adapter(b"{}")
        elapsed = time.monotonic() - start

        assert result == {"d": "A" * 60000}
        assert elapsed < 0.5
