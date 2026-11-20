"""Browser regression tests for EnvPath's local presentation controls.

Uses installed Chrome (Playwright channel='chrome'); no downloaded Chromium,
Ollama model, or retained evidence file is needed.
"""
from __future__ import annotations

import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright

from holosim.envpath_ui import PAGE


@pytest.fixture(scope='module')
def ui_url():
    token = 'ui-test-token'

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/':
                self.send_error(404)
                return
            body = PAGE.replace('__TOKEN__', token).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Security-Policy',
                             f"default-src 'none'; script-src 'nonce-{token}'; style-src 'nonce-{token}'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != '/api/status':
                self.send_error(404)
                return
            size = int(self.headers.get('Content-Length', '0'))
            self.rfile.read(size)
            body = json.dumps({'entries': 0, 'model': 'test-model',
                               'chain_file': 'isolated-test', 'head_hash': ''}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.fixture
def page(ui_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(reduced_motion='reduce')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(ui_url)
        page.locator('#appearance-toggle').wait_for()
        yield page
        assert not errors, f'Browser JavaScript errors: {errors}'
        context.close()
        browser.close()


def open_options(page):
    page.locator('#appearance-toggle').click()
    assert page.locator('#appearance-panel').is_visible()


def test_options_open_close_and_escape(page):
    open_options(page)
    assert page.locator('#appearance-toggle').get_attribute('aria-expanded') == 'true'
    page.locator('#appearance-close').click()
    assert page.locator('#appearance-panel').is_hidden()
    open_options(page)
    page.keyboard.press('Escape')
    assert page.locator('#appearance-panel').is_hidden()


def test_theme_accent_persistence_and_reset(page):
    open_options(page)
    page.locator('#appearance-theme').select_option('light')
    page.locator('#appearance-accent').fill('#ff3300')
    assert page.locator('html').get_attribute('data-theme') == 'light'
    page.reload()
    open_options(page)
    assert page.locator('#appearance-theme').input_value() == 'light'
    assert page.locator('#appearance-accent').input_value() == '#ff3300'
    page.locator('#appearance-reset').click()
    assert page.locator('#appearance-theme').input_value() == 'space'
    assert page.evaluate("localStorage.getItem('envpath.appearance.v1')") is None
    page.reload()
    assert page.locator('html').get_attribute('data-theme') == 'space'


@pytest.mark.parametrize('effect', ['off', 'rgb', 'kaleidoscope', 'fractal', 'fractal-kaleidoscope'])
def test_effect_selection_persists(page, effect):
    open_options(page)
    page.locator('#appearance-effect').select_option(effect)
    assert page.locator('#appearance-effect').input_value() == effect
    page.reload()
    open_options(page)
    assert page.locator('#appearance-effect').input_value() == effect


def test_motion_sliders_persist(page):
    open_options(page)
    for name, value in [('speed', '8'), ('brightness', '6'), ('complexity', '7')]:
        page.locator(f'#appearance-{name}').fill(value)
    page.reload()
    open_options(page)
    for name, value in [('speed', '8'), ('brightness', '6'), ('complexity', '7')]:
        assert page.locator(f'#appearance-{name}').input_value() == value


def test_hide_restore_preserves_unsent_draft(page):
    page.locator('#draft-content').fill('unsent draft remains here')
    page.locator('#workspace-hide').click()
    assert page.locator('body').evaluate("e => e.classList.contains('background-view')")
    assert page.locator('#workspace-reveal').is_visible()
    page.locator('#workspace-reveal').click()
    assert not page.locator('body').evaluate("e => e.classList.contains('background-view')")
    assert page.locator('#draft-content').input_value() == 'unsent draft remains here'


def test_h_shortcut_ignores_text_fields(page):
    page.locator('#message').fill('typing')
    page.locator('#message').focus()
    page.keyboard.press('h')
    assert not page.locator('body').evaluate("e => e.classList.contains('background-view')")
    page.locator('#message').evaluate('e => e.blur()')
    page.keyboard.press('h')
    assert page.locator('body').evaluate("e => e.classList.contains('background-view')")
    page.keyboard.press('h')
    assert not page.locator('body').evaluate("e => e.classList.contains('background-view')")


def test_csp_does_not_allow_unsafe_inline(ui_url):
    import urllib.request
    with urllib.request.urlopen(ui_url) as response:
        policy = response.headers['Content-Security-Policy']
    assert 'nonce-' in policy
    assert "'unsafe-inline'" not in policy
    assert "frame-ancestors 'none'" in policy
