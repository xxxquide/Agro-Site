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

        page.goto(base + "v3/index.html", wait_until="networkidle")
        blur = page.locator(".logo-bar").evaluate("el => getComputedStyle(el).backdropFilter || getComputedStyle(el).webkitBackdropFilter")
        expect(blur and blur != "none", "V3 logo bar blur is missing at first stable paint")
        for rail_page in ["v3/index.html", "v3/about/index.html", "v3/services/index.html"]:
            page.goto(base + rail_page, wait_until="networkidle")
            rail = page.locator(".rail").first
            expect(rail.count() == 1 and rail.evaluate("el => el.scrollWidth > el.clientWidth"), f"testimonial rail is not scrollable on {rail_page}")
            rail.evaluate("el => { el.scrollLeft = Math.min(180, el.scrollWidth - el.clientWidth); el.dispatchEvent(new Event('scroll')); }")
            page.wait_for_timeout(260)
            expect(rail.evaluate("el => el.scrollLeft > 0"), f"testimonial rail did not accept horizontal scroll on {rail_page}")

        page.goto(base + "v2/index.html", wait_until="networkidle")
        tag_rows = page.locator(".tagband > .marq")
        expect(tag_rows.count() == 2, "V2 double marquee does not contain two independent rows")
        for i in range(tag_rows.count()):
            row = tag_rows.nth(i)
            expect(row.evaluate("el => el.querySelector('.marq__track').scrollWidth >= el.clientWidth * 2"), "marquee track does not cover two viewport widths")
        overlap = tag_rows.evaluate_all("rows => { const r = rows.map(el => el.getBoundingClientRect()); return r.length > 1 && r[1].top < r[0].bottom - 1; }")
        expect(not overlap, "V2 double marquee rows overlap")
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

        page.goto(base + "index.html", wait_until="networkidle")
        details = page.locator(".faq details")
        details.nth(1).locator("summary").evaluate("el => el.click()")
        page.wait_for_timeout(850)
        expect(details.evaluate_all("els => els.filter(el => el.open).length") == 1, "FAQ did not close the previously open item")
        expect(details.nth(1).get_attribute("open") is not None, "requested FAQ item did not open")

        article_links = page.locator(".post[href]")
        expect(article_links.count() >= 3, "news cards are not semantic article links")
        first_post = article_links.first
        first_post.scroll_into_view_if_needed()
        page.wait_for_timeout(700)
        first_post.hover()
        page.wait_for_timeout(180)
        expect(first_post.evaluate("el => getComputedStyle(el).transform !== 'none'"), "news hover lift did not activate")
        expect(first_post.evaluate("el => parseFloat(getComputedStyle(el).borderRadius) > 0"), "news card lost its rounded style")
        response = page.goto(base + "blog/winter-wheat-harvest/index.html", wait_until="networkidle")
        expect(response and response.status == 200, "article detail route failed")
        expect(page.locator("h1").count() == 1 and page.locator(".article-body").count() == 1, "article detail structure is incomplete")
        response = page.goto(base + "about/team/bohdan-hrytsenko/index.html", wait_until="networkidle")
        expect(response and response.status == 200, "profile detail route failed")
        expect(page.locator("h1").count() == 1 and page.locator(".profile-list").count() == 1, "profile detail structure is incomplete")
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
        routes = page.locator(".ukraine-map__route")
        if routes.count():
            expect(routes.first.evaluate("el => parseFloat(getComputedStyle(el).strokeDashoffset) == 0"), "route map stayed hidden in reduced motion")
        marquees = page.locator("[data-marquee]")
        for i in range(marquees.count()):
            row = marquees.nth(i)
            expect(row.evaluate("el => el.scrollWidth >= el.clientWidth"), "marquee row is narrower than its viewport")
        reduced.close()

        nojs = browser.new_context(viewport={"width": 1024, "height": 768}, java_script_enabled=False)
        page = nojs.new_page()
        response = page.goto(base + "blog/winter-wheat-harvest/index.html", wait_until="load")
        expect(response and response.status == 200, "no-JS article route failed")
        expect(page.locator("html").evaluate("el => el.classList.contains('no-js')"), "no-JS document lost its fallback class")
        hidden = page.locator("[data-r], [data-card], [data-split]").evaluate_all(
            "els => els.filter(el => getComputedStyle(el).visibility === 'hidden').length"
        )
        expect(hidden == 0, f"{hidden} elements stayed hidden without JavaScript")
        nojs.close()
        browser.close()

    print("INTERACTION SMOKE: drawer, rails, accordion, details, forms, reduced motion and no-JS passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
