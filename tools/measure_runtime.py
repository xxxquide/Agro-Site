#!/usr/bin/env python3
"""Collect local browser diagnostics for first view, CLS and animation frames.

These are reproducible local diagnostics, not field Core Web Vitals. Use a live
HTTPS deployment and real devices before making production performance claims.
"""
from __future__ import annotations

import contextlib
import json
import math
import socket
import statistics
import threading
import time
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
OUT = ROOT / ".visual-regression" / "runtime.json"
CASES = [
    ("v1-desktop", "index.html", 1440, 900),
    ("v2-desktop", "v2/index.html", 1440, 900),
    ("v3-desktop", "v3/index.html", 1440, 900),
    ("v1-mobile", "index.html", 390, 844),
    ("v2-mobile", "v2/index.html", 390, 844),
    ("v3-mobile", "v3/index.html", 390, 844),
]


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


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lo, hi = math.floor(index), math.ceil(index)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def rounded(value):
    return None if value is None else round(value, 2)


def main() -> int:
    results = []
    with local_server() as base, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for name, rel, width, height in CASES:
            context = browser.new_context(viewport={"width": width, "height": height})
            context.add_init_script(
                """(() => {
                  window.__vitals = {cls: 0, lcp: 0, longTasks: []};
                  try {
                    new PerformanceObserver(list => {
                      for (const e of list.getEntries()) if (!e.hadRecentInput) window.__vitals.cls += e.value;
                    }).observe({type: 'layout-shift', buffered: true});
                    new PerformanceObserver(list => {
                      const entries = list.getEntries();
                      if (entries.length) window.__vitals.lcp = entries[entries.length - 1].startTime;
                    }).observe({type: 'largest-contentful-paint', buffered: true});
                    new PerformanceObserver(list => {
                      window.__vitals.longTasks.push(...list.getEntries().map(e => e.duration));
                    }).observe({type: 'longtask', buffered: true});
                  } catch (_) {}
                })()"""
            )
            page = context.new_page()
            page.goto(base + rel, wait_until="networkidle")
            page.wait_for_timeout(500)
            page.evaluate(
                """() => {
                  window.__frames = [];
                  let last = performance.now();
                  let end = last + 4200;
                  function frame(now) {
                    window.__frames.push(now - last);
                    last = now;
                    if (now < end) requestAnimationFrame(frame);
                  }
                  requestAnimationFrame(frame);
                }"""
            )
            for _ in range(9):
                page.mouse.wheel(0, height * .72)
                page.wait_for_timeout(380)
            page.wait_for_timeout(900)
            data = page.evaluate(
                """() => {
                  const nav = performance.getEntriesByType('navigation')[0] || {};
                  const resources = performance.getEntriesByType('resource');
                  return {
                    frames: window.__frames || [],
                    vitals: window.__vitals || {},
                    navigation: {
                      domContentLoaded: nav.domContentLoadedEventEnd || 0,
                      load: nav.loadEventEnd || 0
                    },
                    resources: {
                      count: resources.length,
                      transfer: resources.reduce((sum, e) => sum + (e.transferSize || 0), 0),
                      decoded: resources.reduce((sum, e) => sum + (e.decodedBodySize || 0), 0)
                    }
                  };
                }"""
            )
            frames = [v for v in data["frames"] if 0 < v < 1000]
            long_tasks = data["vitals"].get("longTasks", [])
            results.append({
                "case": name,
                "page": rel,
                "viewport": {"width": width, "height": height},
                "navigation_ms": {k: rounded(v) for k, v in data["navigation"].items()},
                "lcp_ms_local": rounded(data["vitals"].get("lcp", 0)),
                "cls_local": round(data["vitals"].get("cls", 0), 4),
                "frame_interval_ms": {
                    "samples": len(frames),
                    "p50": rounded(percentile(frames, .50)),
                    "p95": rounded(percentile(frames, .95)),
                    "p99": rounded(percentile(frames, .99)),
                    "over_25ms": sum(v > 25 for v in frames),
                    "over_50ms": sum(v > 50 for v in frames),
                },
                "long_tasks_ms": {
                    "count": len(long_tasks),
                    "p95": rounded(percentile(long_tasks, .95)),
                    "max": rounded(max(long_tasks) if long_tasks else None),
                },
                "resources": data["resources"],
            })
            context.close()
        browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"note": "Local diagnostics, not field CWV", "results": results}, indent=2), encoding="utf-8")
    print(f"RUNTIME DIAGNOSTICS: {len(results)} cases")
    for item in results:
        f = item["frame_interval_ms"]
        print(f"  {item['case']:10} CLS {item['cls_local']:.4f} | frame p50 {f['p50']} ms p95 {f['p95']} ms p99 {f['p99']} ms | >50 ms {f['over_50ms']}")
    print(f"Report: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
