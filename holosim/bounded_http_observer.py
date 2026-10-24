"""Bounded loopback HTTP adapter for untrusted observer responses.

No remote authority, persistence, redirects, or external network access.
This is a local transport experiment, not a general web client.
"""

from __future__ import annotations

import http.client
import io
import json
import math
import socket
import time
from urllib.parse import urlsplit


class BoundedHTTPObserverError(ValueError):
    """The HTTP observation could not be safely completed."""


class _DeadlineSocket:
    """Apply one monotonic deadline to socket receive operations."""

    def __init__(self, sock, deadline):
        self._sock = sock
        self._deadline = deadline
        self._io_refs = 0
        self._close_requested = False

    def _remaining(self):
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise BoundedHTTPObserverError(
                "HTTP total deadline exceeded"
            )
        return remaining

    def recv(self, size, flags=0):
        self._sock.settimeout(self._remaining())
        data = self._sock.recv(size, flags)
        self._remaining()
        return data

    def recv_into(self, buffer, nbytes=0, flags=0):
        self._sock.settimeout(self._remaining())
        count = self._sock.recv_into(buffer, nbytes, flags)
        self._remaining()
        return count

    def sendall(self, data, flags=0):
        self._sock.settimeout(self._remaining())
        result = self._sock.sendall(data, flags)
        self._remaining()
        return result

    def makefile(self, mode="r", buffering=None, *, encoding=None,
                 errors=None, newline=None):
        if mode != "rb":
            raise BoundedHTTPObserverError(
                "unsupported socket reader mode"
            )

        self._io_refs += 1
        try:
            return io.BufferedReader(socket.SocketIO(self, "rb"))
        except BaseException:
            self._io_refs -= 1
            raise

    def _decref_socketios(self):
        self._io_refs -= 1
        if self._io_refs == 0 and self._close_requested:
            self._sock.close()

    def fileno(self):
        return self._sock.fileno()

    def close(self):
        self._close_requested = True
        if self._io_refs == 0:
            self._sock.close()

    def __getattr__(self, name):
        return getattr(self._sock, name)


MAX_REQUEST_BYTES = 65536
MAX_RESPONSE_BYTES = 65536
MAX_TIMEOUT_SECONDS = 10.0


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BoundedHTTPObserverError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise BoundedHTTPObserverError("non-finite JSON value")


def make_loopback_http_observer(
    url: str,
    *,
    timeout: float = 2.0,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
):
    """Return a callable compatible with HOLO's observer transport."""

    if not isinstance(url, str):
        raise BoundedHTTPObserverError("URL must be text")

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise BoundedHTTPObserverError("invalid URL") from exc

    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or not port
        or not (1 <= port <= 65535)
        or not parsed.path.startswith("/")
        or parsed.netloc != f"127.0.0.1:{port}"
    ):
        raise BoundedHTTPObserverError(
            "only explicit 127.0.0.1 HTTP endpoints are allowed"
        )

    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or not 0 < timeout <= MAX_TIMEOUT_SECONDS
    ):
        raise BoundedHTTPObserverError("invalid timeout")

    if (
        type(max_response_bytes) is not int
        or not 1 <= max_response_bytes <= MAX_RESPONSE_BYTES
    ):
        raise BoundedHTTPObserverError("invalid response limit")

    target = parsed.path
    if parsed.query:
        target += "?" + parsed.query

    def observe(payload: bytes) -> dict:
        if (
            not isinstance(payload, bytes)
            or len(payload) > MAX_REQUEST_BYTES
        ):
            raise BoundedHTTPObserverError("invalid or oversized request")

        deadline = time.monotonic() + timeout
        connection = http.client.HTTPConnection(
            "127.0.0.1", port, timeout=timeout
        )

        def remaining_time():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BoundedHTTPObserverError(
                    "HTTP total deadline exceeded"
                )
            return remaining

        try:
            connection.timeout = remaining_time()
            connection.request(
                "POST",
                target,
                body=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Connection": "close",
                },
            )
            if connection.sock is not None:
                connection.sock = _DeadlineSocket(
                    connection.sock, deadline
                )

            response = connection.getresponse()

            if response.status != 200:
                raise BoundedHTTPObserverError(
                    f"unexpected HTTP status: {response.status}"
                )

            content_type = response.getheader("Content-Type", "")
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                raise BoundedHTTPObserverError(
                    "unexpected response content type"
                )

            content_length = response.getheader("Content-Length")
            declared = None

            if content_length is not None:
                try:
                    declared = int(content_length)
                except ValueError as exc:
                    raise BoundedHTTPObserverError(
                        "invalid content length"
                    ) from exc

                if declared < 0 or declared > max_response_bytes:
                    raise BoundedHTTPObserverError(
                        "oversized declared response"
                    )

            # Read through the response's HTTP framing while
            # enforcing one monotonic deadline for the exchange.
            # Use a bounded amount per read.
            chunks = []
            total = 0

            while total <= max_response_bytes:
                remaining = remaining_time()

                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                elif response.fp is not None:
                    raw_socket = getattr(
                        response.fp, "raw", None
                    )
                    socket_obj = getattr(
                        raw_socket, "_sock", None
                    )
                    if socket_obj is not None:
                        socket_obj.settimeout(remaining)

                chunk = response.read1(
                    min(4096, max_response_bytes - total + 1)
                )

                remaining_time()

                if not chunk:
                    break

                chunks.append(chunk)
                total += len(chunk)

            raw = b"".join(chunks)

            if len(raw) > max_response_bytes:
                raise BoundedHTTPObserverError(
                    "oversized response"
                )

            if declared is not None and len(raw) != declared:
                raise BoundedHTTPObserverError(
                    "incomplete HTTP response body"
                )

            try:
                result = json.loads(
                    raw.decode("utf-8"),
                    object_pairs_hook=_reject_duplicate_keys,
                    parse_constant=_reject_constant,
                )
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise BoundedHTTPObserverError(
                    "invalid response JSON"
                ) from exc

            if not isinstance(result, dict):
                raise BoundedHTTPObserverError(
                    "observer response must be a JSON object"
                )

            return result

        except (OSError, http.client.HTTPException) as exc:
            raise BoundedHTTPObserverError(
                "HTTP transport failed"
            ) from exc
        finally:
            connection.close()

    return observe
