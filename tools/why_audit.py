#!/usr/bin/env python3
"""Sweep the #why cards across widths and assert nothing escapes its card.

The failure mode this guards is specific: the tilted plate (.wback) is rotated,
and a rotation's corner excursion scales with the plate's width, so a plate
that sits correctly at one card width can hang out of the card at another.
This walks the viewport across the whole range in small steps and compares
each plate's rendered bounding box against its own card's box.

Also checks that the plate's visible band is actually visible (the headline
figure must not slide behind the white instrument) and that no card scrolls
horizontally.

    python3 tools/why_audit.py [--shot]
"""
from __future__ import annotations

import argparse
import contextlib
import os
import socket
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
# .qa/ is the repo's ignored home for screenshot matrices — see .gitignore.
SHOTS = ROOT / ".qa" / "why-shots"

# card-width regimes: 2-up desktop, 1-up tablet, phone
WIDTHS = list(range(320, 1441, 40)) + [1600, 1920]
PAGES = ["index.html", "v2/index.html", "v3/index.html", "en/index.html"]
SHOT_WIDTHS = [390, 768, 1024, 1440]

TOL = 0.75  # px, sub-pixel rounding in getBoundingClientRect


def free_port() -> int:
    with contextlib.closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PROBE = """
() => {
  const out = [];
  document.querySelectorAll('#why .wcard').forEach((card, i) => {
    const c = card.getBoundingClientRect();
    const back = card.querySelector('.wback');
    const front = card.querySelector('.wfront');
    const fig = card.querySelector('.wback__r');
    const b = back.getBoundingClientRect();
    const f = front.getBoundingClientRect();
    const g = fig.getBoundingClientRect();
    out.push({
      i,
      cls: card.className,
      // how far the plate pokes past each edge of its own card
      outL: c.left - b.left,
      outR: b.right - c.right,
      outT: c.top - b.top,
      // band of plate still showing above the instrument, at the plate's
      // downhill end (the end the figure lives on)
      band: f.top - b.top,
      // is the figure clear of the instrument's top edge?
      figClear: f.top - g.bottom,
      cardW: c.width,
      scrollX: card.scrollWidth - card.clientWidth,
    });
  });
  return out;
}
"""

# Each silo's reading must sit clear of, and above, its own fill. Both parts
# have failed before: --f was once set on the fill itself, which its sibling
# label could not inherit, so every label pinned to the same height; and a
# short track leaves no room above a 79% fill, putting the label on it.
# Nothing a widget draws may spill out of the white instrument that frames it.
# The drought tag is the one that hangs lowest — it sits below the year row by
# design — but this deliberately checks every descendant so a future widget
# cannot quietly poke out either.
SPILL_PROBE = """
() => {
  const out = [];
  document.querySelectorAll('#why .wfront').forEach((front, i) => {
    const f = front.getBoundingClientRect();
    let worst = null;
    front.querySelectorAll('*').forEach(el => {
      if (!el.getClientRects().length) return;
      // .sr is the visually-hidden caption: being outside the box is the
      // whole point of it, so it is not a spill.
      if (el.classList.contains('sr')) return;
      const r = el.getBoundingClientRect();
      const over = Math.max(f.top - r.top, r.bottom - f.bottom,
                            f.left - r.left, r.right - f.right);
      if (worst === null || over > worst.over) {
        worst = { over, cls: el.className.toString().slice(0, 40) };
      }
    });
    if (worst) out.push({ i, over: worst.over, cls: worst.cls });
  });
  return out;
}
"""

# The chart's baseline rule must sit at the bars' feet — above the year row,
# not struck through it. Its offset is counted back from the chart's bottom
# edge, so any change to the chart's bottom padding or the year line-height
# moves it onto the labels.
BASELINE_PROBE = """
() => {
  const g = document.querySelector('#why .cgbars');
  if (!g) return null;
  const gr = g.getBoundingClientRect();
  const ruleY = gr.bottom - parseFloat(getComputedStyle(g, '::after').bottom);
  let through = 0, gapToYear = 9e9, gapToBar = 9e9;
  g.querySelectorAll('.bcol').forEach(c => {
    const yr = c.querySelector('span').getBoundingClientRect();
    const bar = c.querySelector('.btrack i').getBoundingClientRect();
    if (ruleY > yr.top + 0.5 && ruleY < yr.bottom - 0.5) through++;
    gapToYear = Math.min(gapToYear, yr.top - ruleY);
    gapToBar = Math.min(gapToBar, Math.abs(bar.bottom - ruleY));
  });
  return { through, gapToYear, gapToBar };
}
"""

SILO_PROBE = """
() => {
  const out = [];
  document.querySelectorAll('#why .silo').forEach((s, i) => {
    const v = s.querySelector('.silo__v').getBoundingClientRect();
    const f = s.querySelector('.silo__f').getBoundingClientRect();
    const c = s.querySelector('.silo__cap').getBoundingClientRect();
    out.push({
      i,
      gap: f.top - c.bottom,          // label clear of its fill
      inside: Math.min(c.top - v.top, v.bottom - c.bottom),  // inside track
      aspect: v.width / v.height,     // dome must stay portrait-ish
    });
  });
  return out;
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", action="store_true", help="also write screenshots")
    args = ap.parse_args()

    port = free_port()
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    fails: list[str] = []
    worst = {"outL": -9e9, "outR": -9e9, "outT": -9e9, "band": 9e9, "figClear": 9e9}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # the reveal animation starts cards translated/faded; land them
        page.emulate_media(reduced_motion="reduce")

        for rel in PAGES:
            for w in WIDTHS:
                page.set_viewport_size({"width": w, "height": 1000})
                page.goto(f"http://127.0.0.1:{port}/{rel}#why", wait_until="load")
                page.wait_for_timeout(120)
                try:
                    rows = page.evaluate(PROBE)
                except Exception as exc:  # pragma: no cover
                    fails.append(f"{rel} @{w}: probe failed: {exc}")
                    continue
                if len(rows) != 4:
                    fails.append(f"{rel} @{w}: expected 4 cards, got {len(rows)}")
                for r in rows:
                    tag = f"{rel} @{w}px card{r['i'] + 1}"
                    for edge in ("outL", "outR", "outT"):
                        worst[edge] = max(worst[edge], r[edge])
                        if r[edge] > TOL:
                            fails.append(
                                f"{tag}: plate escapes {edge} by {r[edge]:.1f}px "
                                f"(cardW {r['cardW']:.0f})"
                            )
                    worst["band"] = min(worst["band"], r["band"])
                    if r["band"] < 8:
                        fails.append(
                            f"{tag}: plate band only {r['band']:.1f}px "
                            f"(cardW {r['cardW']:.0f})"
                        )
                    # v3 flattens the plate into a static header: the figure
                    # sits in normal flow there, so the clearance test does
                    # not apply.
                    if "/v3/" not in rel:
                        worst["figClear"] = min(worst["figClear"], r["figClear"])
                        if r["figClear"] < 0:
                            fails.append(
                                f"{tag}: headline figure overlapped by instrument "
                                f"by {-r['figClear']:.1f}px"
                            )
                    if r["scrollX"] > 1:
                        fails.append(f"{tag}: card scrolls horizontally by {r['scrollX']}px")

                bl = page.evaluate(BASELINE_PROBE)
                if bl:
                    worst["ruleToBar"] = max(worst.get("ruleToBar", 0), bl["gapToBar"])
                    if bl["through"]:
                        fails.append(
                            f"{rel} @{w}px: baseline rule strikes through "
                            f"{bl['through']} year label(s)"
                        )
                    if bl["gapToBar"] > 2:
                        fails.append(
                            f"{rel} @{w}px: baseline rule {bl['gapToBar']:.1f}px "
                            f"off the bars' feet"
                        )

                for s in page.evaluate(SPILL_PROBE):
                    worst["spill"] = max(worst.get("spill", -9e9), s["over"])
                    if s["over"] > TOL:
                        fails.append(
                            f"{rel} @{w}px card{s['i'] + 1}: .{s['cls']} spills "
                            f"{s['over']:.1f}px out of its instrument"
                        )

                # v3 keeps the silos but drops the card chrome; the readings
                # still have to clear their fills there too.
                for s in page.evaluate(SILO_PROBE):
                    tag = f"{rel} @{w}px silo{s['i'] + 1}"
                    worst["siloGap"] = min(worst.get("siloGap", 9e9), s["gap"])
                    worst["siloAspect"] = max(worst.get("siloAspect", 0), s["aspect"])
                    if s["gap"] < 1:
                        fails.append(f"{tag}: reading overlaps its fill by {-s['gap']:.1f}px")
                    if s["inside"] < -TOL:
                        fails.append(f"{tag}: reading outside its track by {-s['inside']:.1f}px")
                    if s["aspect"] > 1.6:
                        fails.append(f"{tag}: dome too wide, aspect {s['aspect']:.2f}")

        if args.shot:
            SHOTS.mkdir(parents=True, exist_ok=True)
            for rel in PAGES:
                for w in SHOT_WIDTHS:
                    page.set_viewport_size({"width": w, "height": 1400})
                    page.goto(f"http://127.0.0.1:{port}/{rel}", wait_until="load")
                    page.wait_for_timeout(400)
                    el = page.query_selector("#why")
                    el.scroll_into_view_if_needed()
                    page.wait_for_timeout(900)
                    name = rel.replace("/", "-").replace(".html", "")
                    el.screenshot(path=str(SHOTS / f"{name}-{w}.png"))

        browser.close()
    httpd.shutdown()

    print(
        "worst margins — plate past card: "
        f"L {worst['outL']:.1f}px  R {worst['outR']:.1f}px  T {worst['outT']:.1f}px  "
        f"| min band {worst['band']:.1f}px  | min figure clearance {worst['figClear']:.1f}px\n"
        f"silos — min reading gap {worst.get('siloGap', 0):.1f}px  "
        f"| widest dome aspect {worst.get('siloAspect', 0):.2f}\n"
        f"widget spill past instrument: {worst.get('spill', 0):.1f}px "
        f"(negative = clear)"
    )
    if fails:
        print(f"\n{len(fails)} FAILURES (first 25):")
        for f in fails[:25]:
            print("  ", f)
        return 1
    print(f"OK — {len(PAGES)} pages x {len(WIDTHS)} widths x 4 cards, nothing escapes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
