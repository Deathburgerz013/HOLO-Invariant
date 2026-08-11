"""Local read-only operator console for Holo/Sim."""

from __future__ import annotations

import json
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from holosim.config import DEFAULT_CHAIN_FILE
from holosim.service import get_service


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

INDEX_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>HOLO — Local Continuity</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #050608;
      --panel: rgba(15, 18, 25, .82);
      --line: rgba(148, 173, 255, .17);
      --text: #f3f6ff;
      --muted: #8992a8;
      --cyan: #58e7ff;
      --violet: #9a7cff;
      --green: #59f2ad;
      --red: #ff6b82;
      --amber: #ffc766;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      background:
        radial-gradient(circle at 18% 6%, rgba(88,231,255,.12), transparent 28rem),
        radial-gradient(circle at 88% 12%, rgba(154,124,255,.13), transparent 30rem),
        linear-gradient(145deg, #030406, #090b12 55%, #050608);
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: .18;
      background-image:
        linear-gradient(var(--line) 1px, transparent 1px),
        linear-gradient(90deg, var(--line) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: linear-gradient(to bottom, black, transparent 70%);
    }
    main { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 72px; }
    header { display: flex; justify-content: space-between; gap: 24px; align-items: end; margin-bottom: 24px; }
    .eyebrow { color: var(--cyan); font: 700 11px/1.2 ui-monospace, monospace; letter-spacing: .22em; }
    h1 { margin: 8px 0 5px; font-size: clamp(34px, 6vw, 72px); line-height: .92; letter-spacing: -.055em; }
    .subtitle { color: var(--muted); margin: 0; max-width: 650px; }
    button {
      border: 1px solid rgba(88,231,255,.35);
      border-radius: 999px;
      padding: 10px 16px;
      color: var(--text);
      background: rgba(88,231,255,.08);
      cursor: pointer;
      font: 700 12px ui-monospace, monospace;
      letter-spacing: .08em;
    }
    button:hover { background: rgba(88,231,255,.16); }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
    .panel {
      position: relative;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--panel);
      box-shadow: 0 18px 70px rgba(0,0,0,.28);
      backdrop-filter: blur(18px);
    }
    .metric { grid-column: span 3; padding: 18px; min-height: 128px; }
    .metric::after {
      content: ""; position: absolute; inset: auto -20% -70% 20%; height: 100px;
      background: radial-gradient(circle, rgba(88,231,255,.16), transparent 65%);
    }
    .label { color: var(--muted); font: 700 10px ui-monospace, monospace; letter-spacing: .14em; text-transform: uppercase; }
    .value { margin-top: 14px; font-size: clamp(24px, 4vw, 40px); font-weight: 750; letter-spacing: -.04em; }
    .value.small { font: 600 15px/1.5 ui-monospace, monospace; overflow-wrap: anywhere; }
    .good { color: var(--green); }
    .bad { color: var(--red); }
    .wide { grid-column: span 8; }
    .side { grid-column: span 4; }
    .section-head { display: flex; justify-content: space-between; align-items: center; padding: 18px 20px; border-bottom: 1px solid var(--line); }
    h2 { margin: 0; font-size: 15px; letter-spacing: -.01em; }
    .count { color: var(--muted); font: 11px ui-monospace, monospace; }
    .timeline { max-height: 520px; overflow: auto; }
    .event { display: grid; grid-template-columns: 52px 160px 1fr; gap: 12px; padding: 15px 20px; border-bottom: 1px solid rgba(148,173,255,.09); }
    .event:last-child { border-bottom: 0; }
    .idx { color: var(--cyan); font: 700 12px ui-monospace, monospace; }
    .time { color: var(--muted); font: 11px/1.45 ui-monospace, monospace; }
    .preview { min-width: 0; font: 12px/1.5 ui-monospace, monospace; color: #d9dff0; overflow-wrap: anywhere; }
    .empty { padding: 52px 20px; text-align: center; color: var(--muted); }
    .details { padding: 18px 20px; display: grid; gap: 16px; }
    .detail { display: grid; gap: 6px; }
    .detail code { color: #dbe3ff; font: 11px/1.5 ui-monospace, monospace; overflow-wrap: anywhere; }
    .authority { border: 1px solid rgba(154,124,255,.24); border-radius: 14px; padding: 14px; background: rgba(154,124,255,.07); }
    .authority strong { color: var(--violet); font-size: 12px; }
    .authority p { margin: 8px 0 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
    .error { display: none; margin-bottom: 14px; border: 1px solid rgba(255,107,130,.35); background: rgba(255,107,130,.09); color: #ffbcc7; padding: 12px 15px; border-radius: 12px; }
    footer { color: #596174; font: 10px ui-monospace, monospace; margin-top: 18px; text-align: right; }
    @media (max-width: 860px) {
      header { align-items: flex-start; flex-direction: column; }
      .metric { grid-column: span 6; }
      .wide, .side { grid-column: span 12; }
    }
    @media (max-width: 560px) {
      main { width: min(100% - 20px, 1180px); padding-top: 20px; }
      .metric { grid-column: span 12; }
      .event { grid-template-columns: 44px 1fr; }
      .event .preview { grid-column: 1 / -1; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <div class="eyebrow">HOLO / OPERATOR CONSOLE</div>
        <h1>Local continuity.</h1>
        <p class="subtitle">Verified chain state from the selected local evidence file. Read-only by design.</p>
      </div>
      <button id="refresh">REFRESH STATE</button>
    </header>
    <div id="error" class="error"></div>
    <section class="grid">
      <article class="panel metric"><div class="label">Chain status</div><div id="chainStatus" class="value">—</div></article>
      <article class="panel metric"><div class="label">Verified entries</div><div id="entries" class="value">0</div></article>
      <article class="panel metric"><div class="label">Latest index</div><div id="latestIndex" class="value">—</div></article>
      <article class="panel metric"><div class="label">Compression ratio</div><div id="compression" class="value">—</div></article>

      <article class="panel wide">
        <div class="section-head"><h2>Verified timeline</h2><span id="eventCount" class="count">0 EVENTS</span></div>
        <div id="timeline" class="timeline"><div class="empty">No retained entries yet.</div></div>
      </article>

      <aside class="panel side">
        <div class="section-head"><h2>Current head</h2><span class="count">SHA-256</span></div>
        <div class="details">
          <div class="detail"><span class="label">Head hash</span><code id="headHash">GENESIS</code></div>
          <div class="detail"><span class="label">Chain file</span><code id="chainFile">—</code></div>
          <div class="detail"><span class="label">Anchor</span><code id="anchor">—</code></div>
          <div class="detail"><span class="label">Active hash</span><code id="activeHash">—</code></div>
          <div class="authority"><strong>OBSERVATIONAL SURFACE</strong><p>This console verifies and displays retained state. It grants no write, execution, acceptance, or truth authority.</p></div>
        </div>
      </aside>
    </section>
    <footer id="generated">WAITING FOR LOCAL STATE</footer>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
    const compactTime = (value) => value ? String(value).replace('T', ' ').replace('+00:00Z', 'Z') : '—';

    function render(data) {
      const status = data.service || {};
      const verify = status.verify || {};
      const health = status.health || {};
      const identity = status.identity || {};
      const timeline = Array.isArray(data.timeline) ? data.timeline : [];
      $('chainStatus').textContent = verify.status === 'ok' ? 'VERIFIED' : 'ERROR';
      $('chainStatus').className = 'value ' + (verify.status === 'ok' ? 'good' : 'bad');
      $('entries').textContent = verify.entries ?? 0;
      $('latestIndex').textContent = verify.latest_idx ?? '—';
      $('compression').textContent = health.compression_ratio == null ? '—' : String(health.compression_ratio);
      $('headHash').textContent = verify.latest_hash || 'GENESIS';
      $('chainFile').textContent = verify.chain_file || identity.chain_file || '—';
      $('anchor').textContent = identity.anchor || '—';
      $('activeHash').textContent = identity.active_hash || '—';
      $('eventCount').textContent = `${timeline.length} EVENT${timeline.length === 1 ? '' : 'S'}`;
      $('generated').textContent = `LOCAL SNAPSHOT ${data.generated_at || ''}`;
      $('timeline').innerHTML = timeline.length ? timeline.slice().reverse().map(item => `
        <div class="event">
          <div class="idx">#${escapeHtml(item.idx)}</div>
          <div class="time">${escapeHtml(compactTime(item.timestamp))}<br>${escapeHtml(item.type || 'plain')}</div>
          <div class="preview">${escapeHtml(item.preview || '')}</div>
        </div>`).join('') : '<div class="empty">No retained entries yet.</div>';
    }

    async function refresh() {
      $('error').style.display = 'none';
      try {
        const response = await fetch('/api/snapshot', {cache: 'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        render(data);
      } catch (error) {
        $('error').textContent = `Unable to verify local state: ${error.message}`;
        $('error').style.display = 'block';
        $('chainStatus').textContent = 'UNAVAILABLE';
        $('chainStatus').className = 'value bad';
      }
    }

    $('refresh').addEventListener('click', refresh);
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>'''


def build_operator_snapshot(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    *,
    timeline_limit: int = 100,
) -> dict[str, Any]:
    """Build one verified, read-only snapshot for the browser console."""
    if type(timeline_limit) is not int or isinstance(timeline_limit, bool):
        raise TypeError("timeline_limit must be a plain integer")
    if not 1 <= timeline_limit <= 1000:
        raise ValueError("timeline_limit must be between 1 and 1000")

    service = get_service(chain_path)
    status = service.status()
    timeline = service.replay_timeline()[-timeline_limit:]

    return {
        "type": "holo_operator_snapshot",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service": status,
        "timeline": timeline,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


class _OperatorServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], chain_path: str | Path):
        self.chain_path = Path(chain_path)
        super().__init__(address, _OperatorHandler)


class _OperatorHandler(BaseHTTPRequestHandler):
    server: _OperatorServer

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(
            status,
            "application/json; charset=utf-8",
            json.dumps(value, ensure_ascii=False).encode("utf-8"),
        )

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlsplit(self.path).path
        if path == "/":
            self._send(200, "text/html; charset=utf-8", INDEX_HTML.encode("utf-8"))
            return
        if path == "/healthz":
            self._json(200, {"status": "ok", "write_authority": "NONE"})
            return
        if path == "/api/snapshot":
            try:
                self._json(200, build_operator_snapshot(self.server.chain_path))
            except Exception as error:
                self._json(
                    500,
                    {
                        "status": "error",
                        "error": str(error),
                        "accepted": False,
                        "write_authority": "NONE",
                        "execution_authority": "NONE",
                    },
                )
            return
        self._json(404, {"status": "not_found", "path": path})

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve_operator_console(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> int:
    """Serve the local read-only console until interrupted."""
    if host not in LOOPBACK_HOSTS:
        raise ValueError("operator console host must be loopback-only")
    if type(port) is not int or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be an integer between 0 and 65535")

    server = _OperatorServer((host, port), chain_path)
    actual_port = server.server_address[1]
    url_host = "127.0.0.1" if host in {"localhost", "::1"} else host
    url = f"http://{url_host}:{actual_port}"
    print(f"HOLO operator console: {url}")
    print(f"Verified chain: {Path(chain_path)}")
    print("Read-only local surface. Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.15, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nHOLO operator console stopped.")
    finally:
        server.server_close()
    return 0
