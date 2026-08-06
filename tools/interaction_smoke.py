#!/usr/bin/env python3
"""Keyboard, drawer, form and reduced-motion smoke tests in a real browser."""
from __future__ import annotations

import contextlib
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    raise SystemExit(
        "Playwright is required. Install with: pip install playwright && "
        "python3 -m playwright install chromium"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


@contextlib.contextmanager
def local_server():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    handler = lambda *a, **kw: QuietHandler(*a, directory=str(ROOT), **kw)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def expect(value, message):
    if not value:
        raise AssertionError(message)


def main() -> int:
    with local_server() as base, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        mobile = browser.new_context(viewport={"width": 390, "height": 844})
        page = mobile.new_page()
        page.goto(base + "index.html", wait_until="networkidle")
        burger = page.locator(".burger")
        burger.click()
        expect(burger.get_attribute("aria-expanded") == "true", "drawer did not open")
        expect(page.locator("#drawer").get_attribute("aria-hidden") == "false", "drawer stayed hidden")
        expect(page.locator("main").evaluate("el => el.inert"), "main is not inert while drawer is open")
        links = page.locator("#drawer a")
        links.last.focus()
        page.keyboard.press("Tab")
        expect(links.first.evaluate("el => el === document.activeElement"), "Tab did not wrap to first drawer link")
        page.keyboard.press("Escape")
        expect(burger.get_attribute("aria-expanded") == "false", "Escape did not close drawer")
        expect(burger.evaluate("el => el === document.activeElement"), "focus was not restored to burger")
        expect(not page.locator("main").evaluate("el => el.inert"), "main stayed inert after drawer close")
        mobile.close()

        forms = browser.new_context(viewport={"width": 1280, "height": 800})
        page = forms.new_page()
        page.goto(base + "contacts/index.html", wait_until="networkidle")
        form = page.locator("#contact [data-demo-form]")
        submit = form.locator('button[type="submit"]')
        submit.click()
        expect(form.locator(":invalid").count() > 0, "empty required fields passed validation")
        expect(not form.locator(".form__ok").evaluate("el => el.classList.contains('is-on')"), "success appeared for invalid form")
        form.locator("#f-name").fill("Тестовий партнер")
        form.locator("#f-mail").fill("partner@example.com")
        submit.click()
        expect(form.locator(".form__ok").evaluate("el => el.classList.contains('is-on')"), "valid demo form did not show notice")
        expect(submit.is_disabled(), "valid demo form submit stayed enabled")
        forms.close()

        reduced = browser.new_context(
            viewport={"width": 1280, "height": 800}, reduced_motion="reduce"
        )
        page = reduced.new_page()
        page.goto(base + "v2/index.html", wait_until="networkidle")
        expect(page.locator("html").evaluate("el => el.classList.contains('no-motion')"), "reduced-motion branch did not activate")
        hidden = page.locator("[data-r], [data-card], [data-split]").evaluate_all(
            "els => els.filter(el => getComputedStyle(el).visibility === 'hidden').length"
        )
        expect(hidden == 0, f"{hidden} animated elements stayed hidden in reduced motion")
        reduced.close()
        browser.close()

    print("INTERACTION SMOKE: drawer, focus trap, form validation and reduced motion passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
