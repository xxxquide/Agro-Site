#!/usr/bin/env python3
"""Measure the rendered page and fail on the defect classes that keep coming back.

`verify.py` reads the HTML; this reads the *layout*. Four families of bug were
found by eye in pass 3, and each of them has a numeric signature that a browser
can check far more reliably than a person scrolling:

    parallax-gap   a photograph that no longer covers its frame at either end
                   of its scroll travel, leaving a hairline of card background
    glyph-clip     a word wrapper whose scrollWidth exceeds its clientWidth, i.e.
                   the reveal mask is shaving the side bearing off a letter
    shadow-clip    a shadowed card sitting inside a clipping ancestor with less
                   slack than the shadow's blur radius, so the shadow reads as a
                   dark line instead of a soft edge
    off-centre     a widget whose centre drifts from the centre of the rings it
                   is supposed to sit inside

    python3 tools/geometry_audit.py                 # audit, exits non-zero on FAIL
    python3 tools/geometry_audit.py --shots out/    # also write screenshots
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
from contextlib import closing
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Playwright is required: pip install playwright && "
        "python3 -m playwright install chromium"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]

# One page per layout family, times every variation. Detail pages reuse the same
# components, so auditing them too would triple the runtime for no new coverage.
PAGES = [
    ("home", ""),
    ("about", "about/"),
    ("services", "services/"),
    ("blog", "blog/"),
    ("contacts", "contacts/"),
]
VARIANTS = [("v1", ""), ("v2", "v2/"), ("v3", "v3/")]
WIDTHS = [(1920, 1080), (1440, 900), (1280, 800), (768, 1024), (390, 844)]

# Sub-pixel noise: browsers round layout to 1/64px, and a fractional gap smaller
# than this is invisible and unfixable. Anything above it is a real defect.
EPS = 0.75


def free_port() -> int:
    with closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def serve() -> tuple[ThreadingHTTPServer, str]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT), **kw)

        def log_message(self, *a):  # keep the audit output readable
            pass

    port = free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}"


# Entrance tweens are still running when a scroll lands, and a card measured at
# 52 of its 60px travel looks exactly like a card clipped by its container. Jump
# every non-scrubbed tween to its end state first, so what gets measured is the
# resting layout. Scrubbed tweens (the parallax) are left alone on purpose —
# their whole point is to be sampled at several scroll depths.
SETTLE = r"""
() => {
  const ST = window.ScrollTrigger;
  if (ST) {
    // A ScrollTrigger'd tween is parked outside the global timeline until it
    // fires, so reaching it through the trigger is the only reliable route.
    ST.getAll().forEach((st) => {
      if (st.vars && st.vars.scrub) return;
      if (st.animation) { try { st.animation.progress(1, false); } catch (e) {} }
    });
  }
  const g = window.gsap;
  if (g) {
    g.globalTimeline.getChildren(true, true, true).forEach((t) => {
      const st = t.scrollTrigger;
      if (st && st.vars && st.vars.scrub) return;
      try { t.progress(1, false); } catch (e) {}
    });
  }
}
"""

# The probe runs inside the page. It is deliberately defensive: a missing widget
# is not a failure, it just means this page does not use that component.
PROBE = r"""
() => {
  const out = { parallax: [], glyph: [], shadow: [], centre: [], overflow: [] };
  const rect = (el) => el.getBoundingClientRect();
  const label = (el) => {
    const cls = (el.className && el.className.baseVal !== undefined)
      ? el.className.baseVal : (el.className || '');
    return el.tagName.toLowerCase() + (cls ? '.' + String(cls).trim().split(/\s+/).join('.') : '');
  };

  /* 1. frame coverage ----------------------------------------------------
     The only thing that matters visually is whether, at the scroll position
     being sampled, the photograph still covers every edge of its frame. A
     drifting image is sampled at both ends of its travel by the caller, so a
     pass here at both ends means the frame is covered throughout. Checking
     "slack >= travel" instead was wrong: mid-scrub the slack is legitimately
     lopsided, which produced hundreds of false positives. */
  document.querySelectorAll('img').forEach((img) => {
    const frame = img.closest('.media-frame, .post, .quote__ph, .svc__ph, .parcel, .about__ph, .phero__ph, .contact-photo');
    if (!frame) return;
    const cs = getComputedStyle(img);
    if (cs.objectFit !== 'cover') return;
    const f = rect(frame), i = rect(img);
    if (f.width < 4 || f.height < 4) return;
    // Only judge what the visitor can actually see. Cards parked off-screen in
    // a horizontal rail report rects thousands of pixels away, which says
    // nothing about whether the photograph covers its frame.
    if (f.bottom < -40 || f.top > innerHeight + 40) return;
    if (f.right < -40 || f.left > innerWidth + 40) return;
    // A thumbnail inside a wide row is not "a photograph covering its frame" —
    // the nearest .post ancestor is simply the wrong box to measure against.
    // Only judge images that are actually filling the frame they sit in.
    if (i.width < f.width * 0.6 || i.height < f.height * 0.6) return;
    const gapTop = f.top - i.top;
    const gapBottom = i.bottom - f.bottom;
    const gapLeft = f.left - i.left;
    const gapRight = i.right - f.right;
    const worst = Math.min(gapTop, gapBottom, gapLeft, gapRight);
    if (worst < -0.75) {
      out.parallax.push({
        el: label(img), src: (img.currentSrc || img.src).split('/').pop(),
        uncovered: +(-worst).toFixed(2),
        top: +gapTop.toFixed(2), bottom: +gapBottom.toFixed(2),
        left: +gapLeft.toFixed(2), right: +gapRight.toFixed(2),
      });
    }
  });

  /* 2. glyph clipping ----------------------------------------------------
     The reveal mask is an overflow:hidden box around each word. If the glyph
     is wider than the box, a side bearing is being shaved off. */
  document.querySelectorAll('.w').forEach((w) => {
    const dx = w.scrollWidth - w.clientWidth;
    const dy = w.scrollHeight - w.clientHeight;
    if (dx > 1 || dy > 1) {
      out.glyph.push({ text: w.textContent.trim().slice(0, 24), dx, dy });
    }
  });

  /* 3. shadow clipped by an ancestor -------------------------------------
     Measured on the resting layout only. A card still carrying an entrance
     transform is mid-reveal, not mis-laid-out, and reading its live rect would
     report the remaining travel as a clipped shadow. */
  const identity = (t) => !t || t === 'none' ||
    /^matrix\(1,\s*0,\s*0,\s*1,\s*0,\s*0\)$/.test(t);
  document.querySelectorAll('.card, .stat, .stats-card, .quote, .cap__card, .fcard, .post, .member').forEach((card) => {
    const cs = getComputedStyle(card);
    if (!identity(cs.transform)) return;
    const sh = cs.boxShadow;
    if (!sh || sh === 'none') return;
    const nums = sh.match(/-?\d+(\.\d+)?px/g) || [];
    const blur = nums.length >= 3 ? Math.abs(parseFloat(nums[2])) : 0;
    if (blur < 2) return;
    let p = card.parentElement;
    while (p && p !== document.body) {
      const pcs = getComputedStyle(p);
      if (/hidden|clip|auto|scroll/.test(pcs.overflow + pcs.overflowY)) {
        const c = rect(card), q = rect(p);
        const slack = Math.min(c.top - q.top, q.bottom - c.bottom);
        if (slack < blur * 0.6) {
          out.shadow.push({
            el: label(card), clipper: label(p),
            blur: +blur.toFixed(1), slack: +slack.toFixed(1),
          });
        }
        break;
      }
      p = p.parentElement;
    }
  });

  /* 4. widget centring ---------------------------------------------------
     The hub of a radial widget must share a centre with its rings. */
  document.querySelectorAll('.orbit, .radar').forEach((box) => {
    const hub = box.querySelector('.orbit__hub, .radar__hub');
    const ring = box.querySelector('.orbit__ring, .radar__ring');
    if (!hub || !ring) return;
    const h = rect(hub), r = rect(ring);
    const dx = (h.left + h.width / 2) - (r.left + r.width / 2);
    const dy = (h.top + h.height / 2) - (r.top + r.height / 2);
    if (Math.abs(dx) > 1.5 || Math.abs(dy) > 1.5) {
      out.centre.push({ el: label(box), dx: +dx.toFixed(1), dy: +dy.toFixed(1) });
    }
  });

  /* 5. horizontal document overflow -------------------------------------- */
  const de = document.documentElement;
  if (de.scrollWidth - de.clientWidth > 1) {
    out.overflow.push({ scrollWidth: de.scrollWidth, clientWidth: de.clientWidth });
  }
  return out;
}
"""


def audit(shots: Path | None, only: str | None) -> int:
    httpd, base = serve()
    findings: list[str] = []
    counts = {"parallax": 0, "glyph": 0, "shadow": 0, "centre": 0, "overflow": 0}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for vname, vpath in VARIANTS:
                for pname, ppath in PAGES:
                    if only and only not in (f"{vname}-{pname}", vname, pname):
                        continue
                    for w, h in WIDTHS:
                        ctx = browser.new_context(
                            viewport={"width": w, "height": h},
                            device_scale_factor=1,
                            reduced_motion="no-preference",
                        )
                        page = ctx.new_page()
                        page.goto(f"{base}/{vpath}{ppath}", wait_until="load")
                        # let the entrance timelines settle so measurements are
                        # taken on the resting layout, not mid-tween
                        page.wait_for_timeout(1400)
                        page.evaluate(
                            "() => window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(900)

                        tag = f"{vname}/{pname}@{w}"
                        seen = set()
                        # Sample the page at several scroll depths: a parallax
                        # image only uncovers its frame at one end of its
                        # travel, so a single sample would miss half the bugs.
                        for frac in (1.0, 0.66, 0.33, 0.0):
                            page.evaluate(
                                "(f) => window.scrollTo(0, (document.body.scrollHeight"
                                " - window.innerHeight) * f)", frac)
                            page.wait_for_timeout(320)
                            page.evaluate(SETTLE)
                            page.wait_for_timeout(120)
                            res = page.evaluate(PROBE)
                            for kind, rows in res.items():
                                for row in rows:
                                    key = (kind, json.dumps(row, sort_keys=True))
                                    if key in seen:
                                        continue
                                    seen.add(key)
                                    counts[kind] += 1
                                    findings.append(f"  {kind:9s} {tag:22s} {json.dumps(row, ensure_ascii=False)}")

                        if shots:
                            shots.mkdir(parents=True, exist_ok=True)
                            page.screenshot(
                                path=str(shots / f"{vname}-{pname}-{w}.jpg"),
                                full_page=True, type="jpeg", quality=72)
                        ctx.close()
            browser.close()
    finally:
        httpd.shutdown()

    total = sum(counts.values())
    if findings:
        print("\n".join(findings[:120]))
        if len(findings) > 120:
            print(f"  … {len(findings) - 120} more")
    print("\nGEOMETRY AUDIT " + " ".join(f"{k}={v}" for k, v in counts.items()))
    print("FAIL" if total else "PASS")
    return 1 if total else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", type=Path, default=None,
                    help="directory for full-page screenshots")
    ap.add_argument("--only", default=None,
                    help="restrict to a variant (v2), a page (blog) or v2-blog")
    args = ap.parse_args()
    return audit(args.shots, args.only)


if __name__ == "__main__":
    sys.exit(main())
