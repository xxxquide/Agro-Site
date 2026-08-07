#!/usr/bin/env python3
"""Render deterministic visual-regression screenshots and run browser smoke checks.

Requires Playwright only for this QA tool:
    pip install playwright
    python3 -m playwright install chromium

The production site itself remains dependency-free in the browser beyond the
self-hosted files committed under assets/js/vendor.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover - environment guidance
    raise SystemExit(
        "Playwright is required for visual QA. Install with: "
        "pip install playwright && python3 -m playwright install chromium"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAGES = [
    "index.html",
    "about/index.html",
    "services/index.html",
    "blog/index.html",
    "contacts/index.html",
    "v2/index.html",
    "v2/about/index.html",
    "v2/services/index.html",
    "v2/blog/index.html",
    "v2/contacts/index.html",
    "v3/index.html",
    "v3/about/index.html",
    "v3/services/index.html",
    "v3/blog/index.html",
    "v3/contacts/index.html",
    "blog/winter-wheat-harvest/index.html",
    "about/team/bohdan-hrytsenko/index.html",
    "v2/blog/third-drying-complex/index.html",
    "v2/about/team/nataliia-bondar/index.html",
    "v3/blog/soil-mapping-results/index.html",
    "v3/about/team/taras-lozovyi/index.html",
    "en/index.html",
    "en/blog/no-till-first-season/index.html",
    "en/about/team/serhii-kushnir/index.html",
    # Crop and legal pages, one per variation. They are new templates rather than
    # restatements of an audited layout, so leaving them out of a hand-picked list
    # is a coverage gap rather than a saving.
    "services/winter-wheat/index.html",
    "v2/services/corn/index.html",
    "v3/services/sugar-beet/index.html",
    "en/services/winter-wheat/index.html",
    "privacy/index.html",
    "terms/index.html",
    "v2/privacy/index.html",
    "en/terms/index.html",
]
VIEWPORTS = {
    "compact": (320, 568),
    "phone": (375, 812),
    "mobile": (390, 844),
    "tablet": (768, 1024),
    "laptop": (1024, 768),
    "desktop": (1440, 900),
    "wide": (1920, 1080),
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextlib.contextmanager
def local_server():
    port = free_port()
    handler = lambda *a, **kw: QuietHandler(*a, directory=str(ROOT), **kw)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def slug(path: str) -> str:
    clean = path.replace("/index.html", "").replace("index.html", "home")
    return clean.strip("/").replace("/", "-") or "home"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".visual-regression", help="Screenshot directory")
    parser.add_argument("--viewport", choices=["all", *VIEWPORTS], default="all")
    parser.add_argument("--page", action="append", help="Relative page path; repeat as needed")
    args = parser.parse_args()

    pages = args.page or DEFAULT_PAGES
    viewports = VIEWPORTS if args.viewport == "all" else {args.viewport: VIEWPORTS[args.viewport]}
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    findings = []

    with local_server() as base, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for view_name, (width, height) in viewports.items():
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
                reduced_motion="reduce",
                color_scheme="light",
            )
            for rel in pages:
                errors = []
                page = context.new_page()
                page.on("console", lambda msg, bucket=errors: bucket.append(f"console:{msg.type}:{msg.text}") if msg.type == "error" else None)
                page.on("pageerror", lambda exc, bucket=errors: bucket.append(f"pageerror:{exc}"))
                response = page.goto(base + rel, wait_until="networkidle")
                page.evaluate("document.documentElement.classList.add('no-motion')")
                page.add_style_tag(content=".hdr{position:absolute!important}.sentinel{display:none!important}")
                page.evaluate(
                    """async () => {
                      const step = Math.max(320, Math.floor(window.innerHeight * .8));
                      for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
                        window.scrollTo(0, y);
                        await new Promise(resolve => setTimeout(resolve, 35));
                      }
                      window.scrollTo(0, 0);
                    }"""
                )
                page.wait_for_timeout(250)

                metrics = page.evaluate(
                    """() => ({
                      scrollWidth: document.documentElement.scrollWidth,
                      clientWidth: document.documentElement.clientWidth,
                      h1: document.querySelectorAll('h1').length,
                      hiddenAnimated: [...document.querySelectorAll('[data-r],[data-card],[data-split]')]
                        .filter(el => getComputedStyle(el).visibility === 'hidden').length,
                      // Broken means the browser tried and failed: complete with no
                      // intrinsic size. `!complete` only means still in flight, and on a
                      // page with 20 lazy images below the fold that is the normal state
                      // rather than a defect — it was reporting a finding on every home
                      // page at every narrow viewport, which is noise that hides real ones.
                      invalidImages: [...document.images].filter(img => img.getClientRects().length && img.complete && img.naturalWidth === 0).length,
                      clippedText: [...document.querySelectorAll('h1,h2,h3,p,.stat__v,.post__title,.quote__txt,.member__n,.svc__body')]
                        .filter(el => !el.classList.contains('sr') && el.getClientRects().length && ((el.scrollHeight > el.clientHeight + 1) || (el.scrollWidth > el.clientWidth + 1)) && ['hidden','clip'].includes(getComputedStyle(el).overflow)).length,
                      mediaLeaks: [...document.querySelectorAll('.media-frame')].filter(frame => {
                        const img = frame.querySelector('img');
                        if (!img || !frame.getClientRects().length || !img.getClientRects().length) return false;
                        const f = frame.getBoundingClientRect(), r = img.getBoundingClientRect();
                        return r.width + 1 < f.width || r.height + 1 < f.height || getComputedStyle(frame).overflow === 'visible';
                      }).length,
                      marqueeOverlap: [...document.querySelectorAll('.tagband')].filter(band => {
                        const rows = [...band.querySelectorAll(':scope > .marq')].map(el => el.getBoundingClientRect());
                        return rows.length > 1 && rows.some((r,i) => i && r.top < rows[i-1].bottom - 1);
                      }).length
                    })"""
                )
                if not response or response.status >= 400:
                    errors.append(f"http:{response.status if response else 'no-response'}")
                if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
                    errors.append(f"horizontal-overflow:{metrics['scrollWidth'] - metrics['clientWidth']}px")
                if metrics["h1"] != 1:
                    errors.append(f"h1-count:{metrics['h1']}")
                if metrics["hiddenAnimated"]:
                    errors.append(f"hidden-animated:{metrics['hiddenAnimated']}")
                if metrics["invalidImages"]:
                    errors.append(f"invalid-images:{metrics['invalidImages']}")
                if metrics["clippedText"]:
                    errors.append(f"clipped-text:{metrics['clippedText']}")
                if metrics["mediaLeaks"]:
                    errors.append(f"media-leaks:{metrics['mediaLeaks']}")
                if metrics["marqueeOverlap"]:
                    errors.append(f"marquee-overlap:{metrics['marqueeOverlap']}")

                filename = f"{slug(rel)}--{view_name}.png"
                page.screenshot(path=str(out / filename), full_page=True, animations="disabled")
                findings.append({"page": rel, "viewport": view_name, "screenshot": filename, "metrics": metrics, "errors": errors})
                page.close()
            context.close()
        browser.close()

    report = {"root": str(ROOT), "screenshots": len(findings), "findings": findings}
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    failures = [item for item in findings if item["errors"]]
    print(f"VISUAL SMOKE: {len(findings)} screenshots, {len(failures)} pages with findings")
    for item in failures:
        print(f"  {item['viewport']:7} {item['page']}: {', '.join(item['errors'])}")
    print(f"Report: {out / 'report.json'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
