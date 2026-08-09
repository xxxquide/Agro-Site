#!/usr/bin/env python3
"""Normalise the client's four #why card exports and emit AVIF + WebP.

The exports are Figma renders at 4x, one per card, each a complete card: the
white instrument body with a dark plate behind it (tilted on two of them) and
a soft white glow around the whole thing.

They cannot be dropped into a grid as they are. Figma sizes each export to its
own content, so the transparent margin around the card differs per file — the
white body sits 34, 35, 93 and 9 Figma px from the left edge respectively, and
the plates lean out different amounts on different sides. Placed side by side
at their own sizes, the four bodies would not line up, which is exactly the
thing that has to look right here.

So the four are re-cropped onto ONE canvas, anchored on the body rather than
on the file edge. The body is the same 218.96 x 236.934 on every card (it is
the one element the reference does not vary), so once each crop puts it at the
same offset, the four images are interchangeable boxes: same dimensions, body
in the same place, alignment guaranteed by construction instead of by nudging
CSS per card.

Margins are the widest each side needs across all four, measured at the alpha
where the glow stops being perceptible (>= 8/255 — below that it is at most
RGB 8,8,8 over black, invisible even on v2's dark band). Glow fainter than
that is dropped rather than padding every card out to the widest file.

Body detection does not look for "white": the body is full of widgets, so its
fill is not uniform. It keys off the opaque region instead — the card is
opaque, the glow is not — and the body's known height, which reaches the
bottom of every export.

Deterministic: safe to re-run.

    python3 tools/build_why_cards.py [--src DIR] [--measure]

--src points at the folder holding the four Figma exports (default is the
same /agent/stored_files build_images.py reads). --measure reports the margin
each export needs without writing anything, which is how the constants below
were derived and how to re-derive them if the artwork is ever re-exported.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

SRC_DIR = "/agent/stored_files"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "img")

S = 4                       # the exports are 4x
BODY_W = 218.96             # Figma units, identical on all four cards
BODY_H = 236.934
BW, BH = round(BODY_W * S), round(BODY_H * S)      # 876 x 948

# Union of what each side needs, at alpha >= 8, rounded up to a multiple of 4
# so every output width divides cleanly at 1x/2x/3x. Recompute with --measure
# if the exports are ever replaced.
M_L, M_R, M_T, M_B = 152, 176, 308, 16

CANVAS_W = M_L + BW + M_R   # 1204  -> 301 at 1x
CANVAS_H = M_T + BH + M_B   # 1272  -> 318 at 1x

# name, source-id prefix, and the Figma frame size Figma puts in the exported
# filename. The size tag is the fallback matcher so the exports can be rebuilt
# from a local folder of the original files, whose names are otherwise
# Cyrillic and normalise differently between systems.
JOBS = [
    ("why-chart", "cmslxruly1ahf06adl5x4rb0n", "218.96x281.6"),    # динаміка за 5 сезонів
    ("why-silos", "cmsm02rvb1b1o07ad9v0i2bxr", "218.96x287.26"),   # зайнято під роздільне зберігання
    # ^ re-export: the first one read "5 800 т" on the plate while its own rows
    #   said 46 000 + 12 000. Same frame and geometry, so it drops straight in.
    ("why-lab",   "cmslxrurs1bvo07ad04hhnvn9", "254.46x309.94"),   # протокол до відвантаження
    ("why-route", "cmslxruml1aa706adp7pzxvo0", "239.98x308.74"),   # куди їде зерно
]

WIDTHS = [301, 602, 903]    # 1x, 2x, 3x of the normalised canvas
Q_AVIF, Q_WEBP = 60, 82


def source_for(prefix, size_tag):
    """The export for one card: by upload id, else by its Figma frame size."""
    names = sorted(os.listdir(SRC_DIR))
    for f in names:
        if f.startswith(prefix):
            return os.path.join(SRC_DIR, f)
    for f in names:
        if size_tag in f and f.lower().endswith(".png"):
            return os.path.join(SRC_DIR, f)
    raise SystemExit(
        f"no source image for {prefix} / {size_tag} in {SRC_DIR}. Point --src "
        f"at the folder holding the four Figma exports."
    )


def body_rect(im):
    """(x0, y0) of the card's white instrument body, in source pixels.

    Opaque pixels are the card (plate + body); the glow is semi-transparent.
    The body reaches the bottom of the export on every card and is a known
    height, which fixes y. For x, look only at a band well inside the body so
    the plate above it and the body's own rounded corners cannot pull the
    edges in or out.
    """
    opaque = np.array(im)[..., 3] > 250
    rows = np.where(opaque.any(1))[0]
    y1 = rows.max() + 1
    y0 = y1 - BH
    band = opaque[y0 + 40:y1 - 40]
    cols = np.where(band.mean(0) > 0.97)[0]
    return int(cols.min()), int(y0), int(cols.max()) + 1, int(y1)


def measure():
    """Report the margin each card needs, so the constants can be re-derived."""
    print(f"body target {BW}x{BH}px @{S}x\n")
    need = [0, 0, 0, 0]
    for name, prefix, size_tag in JOBS:
        im = Image.open(source_for(prefix, size_tag)).convert("RGBA")
        x0, y0, x1, y1 = body_rect(im)
        a = np.array(im)[..., 3]
        g = a >= 8
        gr, gc = np.where(g.any(1))[0], np.where(g.any(0))[0]
        m = [x0 - gc.min(), gc.max() + 1 - x1, y0 - gr.min(), gr.max() + 1 - y1]
        need = [max(n, v) for n, v in zip(need, m)]
        print(f"  {name:10} body={x1 - x0}x{y1 - y0}  needs L={m[0]} R={m[1]} T={m[2]} B={m[3]}")
    print(f"\n  union L={need[0]} R={need[1]} T={need[2]} B={need[3]}")
    print(f"  in use L={M_L} R={M_R} T={M_T} B={M_B}"
          f"  {'OK' if all(u <= v for u, v in zip(need, (M_L, M_R, M_T, M_B))) else 'TOO SMALL'}")


def main():
    global SRC_DIR
    if "--src" in sys.argv:
        SRC_DIR = sys.argv[sys.argv.index("--src") + 1]
    if "--measure" in sys.argv:
        measure()
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    manifest_path = os.path.join(OUT_DIR, "manifest.json")
    # Merge rather than replace: build_images.py owns the photographic entries
    # in this same file, and either script may be run on its own.
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as fh:
            manifest = json.load(fh)

    placed = []
    for name, prefix, size_tag in JOBS:
        im = Image.open(source_for(prefix, size_tag)).convert("RGBA")
        x0, y0, x1, y1 = body_rect(im)

        got = x1 - x0
        if abs(got - BW) > 4:
            raise SystemExit(
                f"{name}: body measured {got}px wide, expected ~{BW}px. The "
                f"exports are no longer 4x or no longer share a body size; "
                f"re-run with --measure before trusting the crop."
            )

        # Crop relative to the body. Coordinates outside the source are fine:
        # PIL pads them transparent, which is what a card with less glow than
        # the union margin should get.
        box = (x0 - M_L, y0 - M_T, x0 - M_L + CANVAS_W, y0 - M_T + CANVAS_H)
        card = im.crop(box)
        assert card.size == (CANVAS_W, CANVAS_H), card.size

        # the body must now sit at the same place in every output
        bx, by, _, _ = body_rect(card)
        placed.append((name, bx, by))

        # Where the visible artwork actually sits inside the canvas, as
        # fractions of it. The rest of the canvas is glow and transparency, so
        # neighbouring cards' *boxes* are expected to overlap in a tight grid
        # while their artwork must not — tools/why_audit.py checks that using
        # these numbers rather than a hardcoded guess.
        op = np.array(card)[..., 3] > 250
        orows, ocols = np.where(op.any(1))[0], np.where(op.any(0))[0]
        art = [
            round(int(ocols.min()) / CANVAS_W, 6),
            round(int(orows.min()) / CANVAS_H, 6),
            round((int(ocols.max()) + 1) / CANVAS_W, 6),
            round((int(orows.max()) + 1) / CANVAS_H, 6),
        ]

        entry = {"ratio": [CANVAS_W, CANVAS_H], "widths": list(WIDTHS),
                 "art": art, "files": {}}
        for w in WIDTHS:
            h = round(w * CANVAS_H / CANVAS_W)
            r = card.resize((w, h), Image.LANCZOS)
            entry[f"h{w}"] = h
            for ext, fmt, q in (("avif", "AVIF", Q_AVIF), ("webp", "WEBP", Q_WEBP)):
                path = os.path.join(OUT_DIR, f"{name}-{w}.{ext}")
                if fmt == "AVIF":
                    r.save(path, format=fmt, quality=q, speed=3)
                else:
                    r.save(path, format=fmt, quality=q, method=6, lossless=False)
                entry["files"][f"{w}.{ext}"] = os.path.getsize(path)
        manifest[name] = entry
        sizes = " ".join(
            f"{w}:{os.path.getsize(os.path.join(OUT_DIR, f'{name}-{w}.avif')) // 1024}"
            f"/{os.path.getsize(os.path.join(OUT_DIR, f'{name}-{w}.webp')) // 1024}KB"
            for w in WIDTHS
        )
        print(f"  {name:10} body@({bx},{by})  {sizes}")

    # The whole point of this script: identical body placement everywhere.
    xs = {p[1] for p in placed}
    ys = {p[2] for p in placed}
    if len(xs) > 1 or len(ys) > 1:
        raise SystemExit(f"body placement drifted between cards: {placed}")

    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=1)

    print(f"\n  canvas {CANVAS_W}x{CANVAS_H} @{S}x -> {CANVAS_W // S}x{CANVAS_H // S} at 1x")
    print(f"  body at ({placed[0][1] // S}, {placed[0][2] // S}) in 1x units, "
          f"identical on all four")
    return 0


if __name__ == "__main__":
    sys.exit(main())
