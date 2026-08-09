#!/usr/bin/env python3
"""Sweep the #why cards across widths and assert they stay square with each other.

The cards are now the client's rendered images rather than CSS, so the things
that can go wrong changed. This checks the three that matter:

  1. Nothing is stretched. Every image's rendered aspect ratio must match its
     own intrinsic ratio — the "lock aspect ratio" requirement, enforced rather
     than assumed.
  2. The four line up. They are one normalised canvas with the card body at a
     fixed offset, so equal rendered widths means the bodies align; the text
     column underneath has to share the body's left edge, not the edge of the
     artwork's transparent margin.
  3. Nothing collides or overflows. The tilted plates lean outside their
     bodies, so neighbouring cards must not touch, and the row must not push
     the page sideways.

    python3 tools/why_audit.py [--shot]
"""
from __future__ import annotations

import argparse
import contextlib
import json
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

WIDTHS = list(range(320, 1441, 40)) + [1600, 1920]
PAGES = ["index.html", "v2/index.html", "v3/index.html", "en/index.html"]
SHOT_WIDTHS = [390, 768, 1024, 1440]

TOL = 0.75          # px, sub-pixel rounding in getBoundingClientRect
RATIO_TOL = 0.005   # 0.5% — anything more is a visible stretch

# body geometry baked into the normalised canvas by tools/build_why_cards.py
BODY_LEFT_RATIO = 152 / 1204   # body's left edge, as a fraction of image width

# Where the visible artwork sits inside each canvas, as fractions of it. The
# rest is glow, so neighbouring cards' boxes overlapping is fine and expected;
# their artwork touching is not. Written by tools/build_why_cards.py so this
# tracks the assets instead of restating them.
with open(ROOT / "assets" / "img" / "manifest.json") as _fh:
    ART = {k: v["art"] for k, v in json.load(_fh).items() if "art" in v}

PROBE = """
() => {
  const cards = [...document.querySelectorAll('#why .wcard')];
  const wrap = document.querySelector('#why .wrap').getBoundingClientRect();
  return {
    wrap: { left: wrap.left, right: wrap.right },
    docScroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    cards: cards.map((card, i) => {
      const img = card.querySelector('.wfig img');
      const h3 = card.querySelector('.wcard__h3');
      const r = img.getBoundingClientRect();
      const t = h3.getBoundingClientRect();
      return {
        i,
        w: r.width, h: r.height,
        left: r.left, right: r.right, top: r.top, bottom: r.bottom,
        natW: img.naturalWidth, natH: img.naturalHeight,
        complete: img.complete && img.naturalWidth > 0,
        currentSrc: (img.currentSrc || '').split('/').pop(),
        textLeft: t.left,
      };
    }),
  };
}
"""


def free_port() -> int:
    with contextlib.closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", action="store_true", help="also write screenshots")
    args = ap.parse_args()

    port = free_port()
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", port), partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    )
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    fails: list[str] = []
    worst = {"ratio": 0.0, "align": 0.0, "gap": 9e9, "overflow": -9e9}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.emulate_media(reduced_motion="reduce")

        for rel in PAGES:
            for w in WIDTHS:
                page.set_viewport_size({"width": w, "height": 1000})
                page.goto(f"http://127.0.0.1:{port}/{rel}#why", wait_until="load")
                page.wait_for_timeout(150)
                d = page.evaluate(PROBE)
                cards = d["cards"]
                if len(cards) != 4:
                    fails.append(f"{rel} @{w}: expected 4 cards, got {len(cards)}")
                    continue

                for c in cards:
                    tag = f"{rel} @{w}px card{c['i'] + 1}"
                    if not c["complete"]:
                        fails.append(f"{tag}: image did not load ({c['currentSrc']})")
                        continue

                    # 1. no stretching
                    want = c["natW"] / c["natH"]
                    got = c["w"] / c["h"]
                    err = abs(got - want) / want
                    worst["ratio"] = max(worst["ratio"], err)
                    if err > RATIO_TOL:
                        fails.append(
                            f"{tag}: stretched — rendered {got:.4f} vs intrinsic "
                            f"{want:.4f} ({err * 100:.2f}%)"
                        )

                    # 2b. the text column sits on the card body, not on the
                    #     artwork's transparent margin
                    body_left = c["left"] + c["w"] * BODY_LEFT_RATIO
                    off = abs(body_left - c["textLeft"])
                    worst["align"] = max(worst["align"], off)
                    if off > 1.5:
                        fails.append(
                            f"{tag}: text starts {off:.1f}px off the card's own left edge"
                        )

                # 2a. all four rendered identically
                ws = {round(c["w"], 1) for c in cards}
                if len(ws) > 1:
                    fails.append(f"{rel} @{w}px: cards render at different widths {sorted(ws)}")

                # 3. neighbours must not touch, and the row must stay in the wrap
                rows: dict[float, list[dict]] = {}
                for c in cards:
                    rows.setdefault(round(c["top"] / 5), []).append(c)
                for _, row in rows.items():
                    row.sort(key=lambda c: c["left"])
                    for a, b in zip(row, row[1:]):
                        # artwork edges, not box edges
                        ka = ART.get(a["currentSrc"].rsplit("-", 1)[0])
                        kb = ART.get(b["currentSrc"].rsplit("-", 1)[0])
                        if not ka or not kb:
                            fails.append(f"{rel} @{w}px: no artwork extents for "
                                         f"{a['currentSrc']} / {b['currentSrc']}")
                            continue
                        a_right = a["left"] + a["w"] * ka[2]
                        b_left = b["left"] + b["w"] * kb[0]
                        gap = b_left - a_right
                        worst["gap"] = min(worst["gap"], gap)
                        if gap < -TOL:
                            fails.append(
                                f"{rel} @{w}px: cards {a['i'] + 1} and {b['i'] + 1} "
                                f"overlap by {-gap:.1f}px"
                            )
                for c in cards:
                    k = ART.get(c["currentSrc"].rsplit("-", 1)[0])
                    if not k:
                        continue
                    art_l = c["left"] + c["w"] * k[0]
                    art_r = c["left"] + c["w"] * k[2]
                    over = max(d["wrap"]["left"] - art_l, art_r - d["wrap"]["right"])
                    worst["overflow"] = max(worst["overflow"], over)
                    if over > TOL:
                        fails.append(f"{rel} @{w}px card{c['i'] + 1}: artwork "
                                     f"{over:.1f}px outside the wrap")
                if d["docScroll"] > 1:
                    fails.append(f"{rel} @{w}px: page scrolls sideways by {d['docScroll']}px")

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
        f"worst aspect-ratio error {worst['ratio'] * 100:.3f}%  "
        f"| worst text/card misalignment {worst['align']:.2f}px\n"
        f"tightest gap between neighbours {worst['gap']:.1f}px  "
        f"| furthest past the wrap {worst['overflow']:.1f}px (negative = inside)"
    )
    if fails:
        print(f"\n{len(fails)} FAILURES (first 25):")
        for f in fails[:25]:
            print("  ", f)
        return 1
    print(f"OK — {len(PAGES)} pages x {len(WIDTHS)} widths x 4 cards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
