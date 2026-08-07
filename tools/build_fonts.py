#!/usr/bin/env python3
"""Build the self-hosted typefaces, subset to the exact glyph set the site needs.

Typography decision, and how it was reached
-------------------------------------------
The source template sets Inter (body) + Plus Jakarta Sans (display). Inter can be
used verbatim — its Cyrillic is real. Plus Jakarta Sans cannot:

    google/fonts   PlusJakartaSans[wght].ttf   721 codepoints, 0 Cyrillic
    tokotype/PlusJakartaSans (upstream)        721 codepoints, 0 Cyrillic
    Google CDN, subset "cyrillic-ext"          DECLARES Cyrillic in
                                               unicode-range, but the woff2 it
                                               serves contains only U+0020 and
                                               U+0308 — no Cyrillic glyphs

That last row is a trap: the CSS advertises a Cyrillic range, so a naive check
of the @font-face declaration "proves" support that does not exist. Only reading
the font's cmap tells the truth. Hence the assertion at the bottom of this file:
the build fails loudly if a family ever stops covering Ukrainian.

Display face is therefore Onest — rendered side by side at 52px/700 its Latin is
near-indistinguishable from Plus Jakarta Sans (same geometric skeleton, same
tall x-height), and its Cyrillic is complete.

The template's second family is Geist Mono (buttons, tags, eyebrow labels, set
at letter-spacing .12em). That one carries full Cyrillic, so it is used verbatim.
Net result: one of the two template faces is exact, the other is a visual
near-match forced by the Cyrillic gap. Inter is not needed — the template maps
both body text and headings to the same display family.
"""
import os
import subprocess
import sys

from fontTools.ttLib import TTFont

# Resolved from this file, the way every other tool here does it. These two were
# absolute paths into "/agent/workspace/agro", a directory this repository does
# not have — so the script could not run against the real assets and, when run
# at all, quietly built a parallel tree outside the repo. That is also why two
# orphaned woff2 files survived: main() clears stale woff2 from OUT_DIR first,
# and OUT_DIR was pointing somewhere else.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "fonts")
CSS_OUT = os.path.join(ROOT, "assets", "css", "fonts.css")
TMP = "/tmp/fontsrc"

SRC = {
    "onest": "https://raw.githubusercontent.com/google/fonts/main/ofl/onest/Onest%5Bwght%5D.ttf",
    "geistmono": "https://raw.githubusercontent.com/google/fonts/main/ofl/geistmono/GeistMono%5Bwght%5D.ttf",
}

# --- glyph coverage -------------------------------------------------------
BASIC_LATIN = list(range(0x20, 0x7F))
CYRILLIC = (
    list(range(0x410, 0x450))                                   # А-я
    + [0x404, 0x454, 0x406, 0x456, 0x407, 0x457, 0x490, 0x491]  # Є є І і Ї ї Ґ ґ
    + [0x401, 0x451]                                            # Ё ё
)
MARKS = [
    0x00A0,                                   # nbsp
    0x00AB, 0x00BB,                           # « »  — ТОВ «ЦЕНТРАГРО ПЛЮС»
    0x00A9, 0x00AE,                           # © ®
    0x00B0, 0x00B7, 0x2022,                   # ° · •
    0x00D7, 0x2212, 0x00B1,                   # × − ±
    0x2013, 0x2014,                           # – —
    0x2018, 0x2019, 0x201C, 0x201D, 0x201E,   # curly quotes
    0x2026, 0x2116,                           # … №
    0x2192, 0x2197, 0x2190, 0x2193, 0x2191,   # arrows
    0x20B4, 0x20AC, 0x0024,                   # ₴ € $
    0x2264, 0x2265,                           # ≤ ≥
    0x02BC,                                   # ʼ  Ukrainian apostrophe
    0x2009, 0x202F,                           # thin / narrow nbsp for 14 200
]

CHARSET = BASIC_LATIN + CYRILLIC + MARKS

# (display name, slug, declared weight range, axes to pin before subsetting)
# `pin` fixes a variable axis before subsetting, for a font shipping axes this
# site never varies. Empty dict = keep the font as published.
FAMILIES = [
    ("Onest", "onest", "300 900", {}),
    ("Geist Mono", "geistmono", "400 600", {}),
]

# a family that fails this check would silently fall back to a system font
REQUIRED_UK = {0x0404: "Є", 0x0454: "є", 0x0406: "І", 0x0456: "і",
               0x0407: "Ї", 0x0457: "ї", 0x0490: "Ґ", 0x0491: "ґ",
               0x0410: "А", 0x044F: "я", 0x0449: "щ", 0x044E: "ю"}


def ensure(slug):
    os.makedirs(TMP, exist_ok=True)
    path = os.path.join(TMP, f"{slug}.ttf")
    if not os.path.exists(path) or os.path.getsize(path) < 20000:
        subprocess.run(["curl", "-sSL", "-m", "120", SRC[slug], "-o", path], check=True)
    return path


def assert_covers(path, family):
    """Read the cmap — never trust a declared unicode-range."""
    cmap = TTFont(path).getBestCmap()
    missing = [ch for cp, ch in REQUIRED_UK.items() if cp not in cmap]
    if missing:
        raise SystemExit(
            f"FATAL: {family} is missing Ukrainian glyphs {''.join(missing)}. "
            f"Refusing to build a page that would silently fall back to a system font."
        )
    return len(cmap)


def unicodes_arg(codepoints):
    return ",".join(f"U+{c:04X}" for c in sorted(set(codepoints)))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for stale in os.listdir(OUT_DIR):
        if stale.endswith(".woff2"):
            os.remove(os.path.join(OUT_DIR, stale))

    css = [
        "/* Self-hosted variable fonts, subset to basic Latin + Ukrainian Cyrillic",
        " * + typographic marks. Built by tools/build_fonts.py — do not hand-edit.",
        " *",
        " * Onest stands in for the template's Plus Jakarta Sans, which ships no",
        " * Cyrillic glyphs in any distribution (see the module docstring).",
        " * Both families: SIL Open Font License 1.1. */",
        "",
    ]
    total = 0

    for family, slug, wght, pin in FAMILIES:
        raw = ensure(slug)
        n_cp = assert_covers(raw, family)

        if pin:
            pinned = os.path.join(TMP, f"{slug}-pinned.ttf")
            subprocess.run(
                [sys.executable, "-m", "fontTools.varLib.instancer", raw]
                + [f"{a}={v}" for a, v in pin.items()]
                + ["--output", pinned],
                check=True, capture_output=True)
            raw = pinned

        out = os.path.join(OUT_DIR, f"{slug}.woff2")

        subprocess.run([
            sys.executable, "-m", "fontTools.subset", raw,
            f"--unicodes={unicodes_arg(CHARSET)}",
            "--flavor=woff2",
            f"--output-file={out}",
            "--layout-features=kern,liga,calt,ccmp,locl,mark,mkmk,rlig,tnum",
            "--name-IDs=1,2,3,4,5,6",
            "--no-hinting",
            "--desubroutinize",
            "--drop-tables+=DSIG",
        ], check=True, capture_output=True)

        # the subset must still cover Ukrainian
        assert_covers(out, f"{family} (subset)")

        size = os.path.getsize(out)
        total += size
        print(f"{family:8s} {os.path.getsize(raw)/1024:7.1f} KB ttf "
              f"({n_cp} cp) -> {size/1024:6.1f} KB woff2")

        css.append(
            f"@font-face{{font-family:'{family}';font-style:normal;"
            f"font-weight:{wght};font-display:swap;"
            f"src:url('../fonts/{slug}.woff2') format('woff2')}}"
        )

    with open(CSS_OUT, "w") as fh:
        fh.write("\n".join(css) + "\n")

    print(f"\nTOTAL fonts: {total/1024:.1f} KB — both locales, all weights")
    print("Ukrainian coverage asserted against the cmap of every output file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
