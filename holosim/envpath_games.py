"""Dedicated loopback origin for the embedded N64 player and its assets."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import secrets
import shutil
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit


MAX_NATIVE_SAVE_BYTES = 1024 * 1024

ASSET_TYPES = {
    ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
    ".wasm": "application/wasm", ".data": "application/octet-stream",
    ".zip": "application/zip", ".png": "image/png", ".svg": "image/svg+xml",
    ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
}


PLAYER_PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nintendo 64 player</title>
<style nonce="__TOKEN__">
html,body{margin:0;background:#08080c;color:#eee;font:16px system-ui}
main{padding:12px}label{display:block;margin-bottom:8px}#game{width:100%;height:calc(100vh - 24px);min-height:300px}
</style>
<main>
<label for="rom">Open a local Nintendo 64 game</label>
<input id="rom" type="file" accept=".z64,.n64,.v64">
<p id="status" role="status"></p>
<div id="save-actions" hidden>
<button id="save-now" type="button">Save to disk</button>
<button id="import-save" type="button">Import native save</button>
<input id="save-file" type="file" accept=".srm,.sav" hidden>
<p id="save-status" role="status"></p>
</div>
<div id="game" hidden></div>
</main>
<script nonce="__TOKEN__">
const picker = document.getElementById('rom');
const status = document.getElementById('status');
const saveStatus = document.getElementById('save-status');
const saveFile = document.getElementById('save-file');
let gameUrl;
let saveUrl;
let readyToSave = false;
let savedBytes;
let pending = Promise.resolve();
const saveHeaders = {'X-EnvPath-Save-Token': '__TOKEN__'};

async function storeSave(bytes) {
  if (!bytes?.byteLength || bytes.byteLength > 1024 * 1024) throw Error('Invalid native save size.');
  const response = await fetch(saveUrl, {
    method: 'PUT',
    headers: {...saveHeaders, 'Content-Type': 'application/octet-stream'},
    body: bytes
  });
  if (!response.ok) throw Error('Could not write the local save.');
}

function queueSave(bytes) {
  if (!readyToSave) return;
  // The core can reuse its buffer after the callback returns.
  const copy = new Uint8Array(bytes).slice();
  pending = pending.catch(() => {}).then(async () => {
    if (savedBytes?.length === copy.length && copy.every((byte, index) => byte === savedBytes[index])) {
      saveStatus.textContent = 'Native save is on disk.';
      return;
    }
    await storeSave(copy);
    savedBytes = copy;
    saveStatus.textContent = 'Native save written to disk.';
  }).catch(error => { saveStatus.textContent = error.message; });
}

function restoreSave(bytes) {
  const manager = window.EJS_emulator.gameManager;
  const path = manager.getSaveFilePath();
  if (!path || typeof manager.loadSaveFiles !== 'function') {
    throw Error('This emulator core cannot restore a native save.');
  }
  manager.writeFile(path, bytes);
  manager.loadSaveFiles();
}

document.getElementById('save-now').onclick = () => {
  try {
    const bytes = window.EJS_emulator.gameManager.getSaveFile(true);
    if (!bytes?.byteLength) throw Error('Save inside the game first, then try again.');
    queueSave(bytes);
  } catch (error) {
    saveStatus.textContent = error.message;
  }
};
document.getElementById('import-save').onclick = () => saveFile.click();
saveFile.onchange = async () => {
  const file = saveFile.files[0];
  saveFile.value = '';
  if (!file) return;
  if (!file.size || file.size > 1024 * 1024) {
    saveStatus.textContent = 'Choose a native save up to 1 MiB.';
    return;
  }
  if (!confirm('Replace this game’s native save? Use a save from the same ROM and emulator core.')) return;
  readyToSave = false;
  try {
    await pending;
    const imported = new Uint8Array(await file.arrayBuffer());
    const current = savedBytes || window.EJS_emulator.gameManager.getSaveFile(true);
    if (!current?.byteLength || imported.length !== current.byteLength) {
      throw Error('Save size differs from the core’s native format. Import stopped.');
    }
    restoreSave(imported);
    await storeSave(imported);
    savedBytes = imported;
    saveStatus.textContent = 'Native save imported and written to disk.';
  } catch (error) {
    saveStatus.textContent = error.message;
  } finally {
    readyToSave = true;
  }
};
picker.addEventListener('change', async () => {
  const game = picker.files[0];
  if (!game) return;
  picker.disabled = true;
  status.textContent = 'Loading local game…';
  try {
    const formats = {
      '.z64': 0x80371240, '.n64': 0x40123780, '.v64': 0x37804012
    };
    const extension = game.name.slice(-4).toLowerCase();
    if (!formats[extension] || game.size < 64 || game.size > 64 * 1024 * 1024) {
      throw Error('Choose a supported N64 game file up to 64 MiB.');
    }
    const bytes = await game.arrayBuffer();
    if (new DataView(bytes).getUint32(0) !== formats[extension]) {
      throw Error('The file header does not match the selected N64 format.');
    }
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
    const hex = Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('');
    saveUrl = '/save/' + hex;
    const existing = await fetch(saveUrl, {headers: saveHeaders});
    if (existing.ok) savedBytes = new Uint8Array(await existing.arrayBuffer());
    else if (existing.status !== 404) throw Error('Could not read the local save.');
    gameUrl = URL.createObjectURL(game);
    Object.assign(window, {
      EJS_player: '#game',
      EJS_core: 'mupen64plus_next',
      EJS_gameUrl: gameUrl,
      EJS_gameName: 'n64-' + hex + extension,
      EJS_gameID: Number.parseInt(hex.slice(0, 13), 16),
      EJS_pathtodata: '/data/',
      EJS_threads: false,
      EJS_fixedSaveInterval: 5000,
      EJS_onSaveUpdate: event => queueSave(event.save),
      EJS_onGameStart: () => {
        status.textContent = '';
        try {
          if (savedBytes) {
            restoreSave(savedBytes);
            saveStatus.textContent = 'Native save restored from disk.';
          }
          readyToSave = true;
          document.getElementById('save-actions').hidden = false;
        } catch (error) {
          status.textContent = 'Local save could not be restored: ' + error.message;
        }
      }
    });
    document.getElementById('game').hidden = false;
    const loader = document.createElement('script');
    loader.src = '/data/loader.js';
    loader.onerror = () => {
      status.textContent = 'Emulator assets unavailable. Reopen Games after checking the installation.';
    };
    document.head.append(loader);
  } catch (error) {
    status.textContent = error.message;
    picker.value = '';
    picker.disabled = false;
  }
});
window.addEventListener('pagehide', () => {
  if (gameUrl) URL.revokeObjectURL(gameUrl);
});
</script>
</html>
"""


def make_player_server(data_dir: Path, *, port: int, workspace_port: int,
                       save_dir: Path | None = None) -> ThreadingHTTPServer:
    root = data_dir.resolve(strict=True)
    if not (root / "loader.js").is_file() or not (root / "cores").is_dir():
        raise ValueError("Select the EmulatorJS data directory containing loader.js and cores.")
    if save_dir is None:
        save_dir = Path.home() / "EnvPath Saves"
    save_dir.mkdir(parents=True, exist_ok=True)
    saves = save_dir.resolve(strict=True)
    if saves.is_relative_to(root) or root.is_relative_to(saves):
        raise ValueError("Use separate emulator asset and save directories.")
    nonce = secrets.token_urlsafe(24)
    page = PLAYER_PAGE.replace("__TOKEN__", nonce).encode()
    # EmulatorJS 4.2.3 uses dynamic JavaScript in its decompression worker.
    policy = (
        "default-src 'none'; "
        f"script-src 'nonce-{nonce}' 'self' blob: 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' blob:; img-src 'self' blob: data:; "
        "font-src 'self' data: blob:; media-src 'self' blob: data:; "
        "connect-src 'self' blob: data:; worker-src 'self' blob:; "
        "base-uri 'none'; form-action 'none'; "
        f"frame-ancestors http://127.0.0.1:{workspace_port} http://localhost:{workspace_port}"
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def save_path(self):
            if (self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}"
                    or self.headers.get("X-EnvPath-Save-Token") != nonce):
                self.send_error(403)
                return None
            match = re.fullmatch(r"/save/([0-9a-f]{64})", self.path)
            if match is None:
                self.send_error(404)
                return None
            path = saves / (match[1] + ".srm")
            if path.is_symlink() or path.resolve() != path:
                self.send_error(403)
                return None
            return path

        def do_PUT(self):
            path = self.save_path()
            if path is None:
                return
            if (self.headers.get("Origin") != f"http://127.0.0.1:{self.server.server_port}"
                    or self.headers.get("Content-Type") != "application/octet-stream"
                    or self.headers.get("Transfer-Encoding")):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if not 0 < length <= MAX_NATIVE_SAVE_BYTES:
                self.send_error(400)
                return
            temporary = None
            try:
                self.connection.settimeout(10)
                payload = self.rfile.read(length)
                if len(payload) != length:
                    self.send_error(400)
                    return
                with NamedTemporaryFile(dir=saves, delete=False) as output:
                    temporary = Path(output.name)
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
                temporary.replace(path)
            except OSError:
                self.send_error(500)
                return
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            self.send_headers("application/octet-stream", 0)

        def do_GET(self):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_error(403)
                return
            if self.path == "/":
                self.send_headers("text/html; charset=utf-8", len(page))
                self.wfile.write(page)
                return
            if self.path.startswith("/save/"):
                path = self.save_path()
                if path is None:
                    return
                try:
                    with path.open("rb") as source:
                        payload = source.read(MAX_NATIVE_SAVE_BYTES + 1)
                except FileNotFoundError:
                    self.send_error(404)
                    return
                except OSError:
                    self.send_error(500)
                    return
                if not 0 < len(payload) <= MAX_NATIVE_SAVE_BYTES:
                    self.send_error(500)
                    return
                self.send_headers("application/octet-stream", len(payload))
                self.wfile.write(payload)
                return
            request_path = urlsplit(self.path).path
            relative = request_path.removeprefix("/data/")
            if (relative == request_path or not re.fullmatch(r"[A-Za-z0-9_./@-]+", relative)
                    or any(part in {"", ".", ".."} for part in relative.split("/"))):
                self.send_error(404)
                return
            mime = ASSET_TYPES.get(Path(relative).suffix.lower())
            if mime is None:
                self.send_error(404)
                return
            try:
                path = (root / relative).resolve(strict=True)
                if not path.is_relative_to(root) or not path.is_file():
                    self.send_error(404)
                    return
                source = path.open("rb")
            except (OSError, RuntimeError):
                self.send_error(404)
                return
            with source:
                source.seek(0, 2)
                length = source.tell()
                source.seek(0)
                self.send_headers(mime, length)
                shutil.copyfileobj(source, self.wfile)

        def send_headers(self, mime, length):
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(length))
            self.send_header("Content-Security-Policy", policy)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
