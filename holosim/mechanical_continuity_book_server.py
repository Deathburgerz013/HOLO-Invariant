
"""Loopback-only, read-only HTTP interface for the Mechanical Continuity Book."""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from holosim.mechanical_continuity_book import (
    MechanicalContinuityBookError,
    contents,
    open_book,
    read_page,
)


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Holo/Sim | Mechanical Continuity</title>
<style>
:root {
  color-scheme: dark;
  font-family: Georgia, "Times New Roman", serif;
  background: #11100f;
  color: #e8dfcf;
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; }
main {
  max-width: 1100px;
  margin: 40px auto;
  padding: 20px;
}
.book {
  min-height: 650px;
  display: grid;
  grid-template-columns: 280px 1fr;
  background: #211c19;
  border: 1px solid #66513b;
  border-radius: 5px 14px 14px 5px;
  box-shadow: 16px 18px 45px #0009;
  overflow: hidden;
}
.cover {
  background: linear-gradient(125deg,#34271f,#171310);
  border-right: 5px double #786348;
  padding: 48px 25px;
  text-align: center;
}
.cover h1 { font-size: 35px; margin-top: 100px; }
.cover h2 { font-size: 21px; font-weight: normal; }
.cover p { letter-spacing: 2px; font-size: 13px; }
.page {
  padding: 38px;
  background: #e7dcc7;
  color: #30271f;
  overflow-wrap: anywhere;
}
.page h2 { border-bottom: 1px solid #9e8c73; padding-bottom: 12px; }
button {
  display: block;
  width: 100%;
  margin: 8px 0;
  padding: 11px;
  text-align: left;
  border: 1px solid #aa967a;
  background: #f4ecdc;
  color: #30271f;
  cursor: pointer;
}
button:hover { background: #d8c8ad; }
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 13px/1.6 Consolas, monospace;
}
small { color: #665846; }
@media(max-width:720px) {
  .book { grid-template-columns: 1fr; }
  .cover { padding: 15px; border-right: 0; border-bottom: 4px double #786348; }
  .cover h1 { margin-top: 5px; }
}
</style>
</head>
<body>
<main>
<div class="book">
  <aside class="cover">
    <h1>Holo/Sim</h1>
    <h2>Invariants</h2>
    <p>MECHANICAL CONTINUITY</p>
  </aside>
  <section class="page">
    <h2 id="heading">Contents</h2>
    <div id="content">Loading verified records...</div>
  </section>
</div>
</main>
<script>
const heading = document.getElementById("heading");
const content = document.getElementById("content");

async function getJSON(url) {
  const response = await fetch(url, {cache: "no-store"});
  const value = await response.json();
  if (!response.ok) throw new Error(value.reason || value.status);
  return value;
}

function clear() {
  content.replaceChildren();
}

function addButton(label, callback) {
  const button = document.createElement("button");
  button.textContent = label;
  button.addEventListener("click", callback);
  content.appendChild(button);
}

async function showContents() {
  heading.textContent = "Contents";
  clear();
  try {
    const data = await getJSON("/api/contents");
    const note = document.createElement("small");
    note.textContent = "Retained identity: " + data.lineage_hash;
    content.appendChild(note);
    for (const entry of data.contents) {
      addButton(entry.kind + " / " + entry.id,
        () => showPage(entry.kind, entry.id));
    }
  } catch (error) {
    content.textContent = "Cannot load book: " + error.message;
  }
}

async function showPage(kind, id) {
  heading.textContent = kind + " / " + id;
  clear();
  addButton("Back to contents", showContents);
  try {
    const query = new URLSearchParams({kind, id});
    const page = await getJSON("/api/page?" + query.toString());
    const note = document.createElement("small");
    note.textContent = "Record hash: " + page.record_hash;
    content.appendChild(note);
    const body = document.createElement("pre");
    body.textContent = JSON.stringify(page.record, null, 2);
    content.appendChild(body);
  } catch (error) {
    const message = document.createElement("p");
    message.textContent = "Cannot open page: " + error.message;
    content.appendChild(message);
  }
}

showContents();
</script>
</body>
</html>
"""


class _BookServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        report_path: str | Path,
        expected_hash: str,
    ):
        if address[0] != "127.0.0.1":
            raise ValueError("book server must bind to 127.0.0.1")
        port = address[1]
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("invalid book server port")

        # Verification occurs before any socket is opened.
        self.report = open_book(report_path, expected_hash)
        super().__init__(address, _BookHandler)


class _BookHandler(BaseHTTPRequestHandler):
    server: _BookServer

    def _send(
        self, status: int, content_type: str, body: bytes
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; "
            "style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'; "
            "connect-src 'self'; "
            "base-uri 'none'; form-action 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: dict[str, Any]) -> None:
        self._send(
            status,
            "application/json; charset=utf-8",
            json.dumps(value, ensure_ascii=False).encode("utf-8"),
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)

        if parsed.path == "/":
            self._send(
                200,
                "text/html; charset=utf-8",
                INDEX_HTML.encode("utf-8"),
            )
            return

        if parsed.path == "/healthz":
            self._json(200, {
                "status": "ok",
                "accepted": False,
                "truth_claimed": False,
                "write_authority": "NONE",
                "execution_authority": "NONE",
            })
            return

        if parsed.path == "/api/contents":
            self._json(200, {
                "lineage_hash": self.server.report["lineage_hash"],
                "contents": contents(self.server.report),
                "accepted": False,
                "truth_claimed": False,
                "write_authority": "NONE",
            })
            return

        if parsed.path == "/api/page":
            try:
                query = parse_qs(
                    parsed.query,
                    keep_blank_values=True,
                    strict_parsing=True,
                )
                if set(query) != {"kind", "id"}:
                    raise ValueError("kind and id are required")
                if any(len(values) != 1 for values in query.values()):
                    raise ValueError("duplicate query parameters")
                page = read_page(
                    self.server.report,
                    query["kind"][0],
                    query["id"][0],
                )
            except (ValueError, MechanicalContinuityBookError):
                self._json(400, {
                    "status": "REJECTED",
                    "reason": "invalid or unknown record identity",
                })
                return

            self._json(200, page)
            return

        self._json(404, {"status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_PUT(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_DELETE(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_PATCH(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def _method_not_allowed(self) -> None:
        self._json(405, {
            "status": "method_not_allowed",
            "write_authority": "NONE",
        })

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve_book(
    report_path: str | Path,
    expected_hash: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8766,
    open_browser: bool = True,
) -> int:
    """Serve a previously verified, read-only lineage snapshot."""
    server = _BookServer((host, port), report_path, expected_hash)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"

    print(f"Holo/Sim Mechanical Continuity: {url}")
    print("Read-only verified snapshot. Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.15, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Holo/Sim Mechanical Continuity Book"
    )
    parser.add_argument("report_path")
    parser.add_argument("--expected-hash", required=True)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    try:
        return serve_book(
            args.report_path,
            args.expected_hash,
            port=args.port,
            open_browser=not args.no_browser,
        )
    except (MechanicalContinuityBookError, ValueError, OSError) as error:
        parser.exit(1, f"Book rejected: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
