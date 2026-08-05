#!/usr/bin/env python3
"""Build self-hosted woff2 fonts, subset to the exact glyph set this site needs.

Google's own per-subset woff2 files cost ~280 KB for three families because each
"latin" subset carries the full Latin-ext glyph set. We only need basic Latin +
Ukrainian Cyrillic + a handful of typographic marks, so we pull the upstream
variable TTFs and subset them ourselves with fontTools. Result: ~4x smaller,
single file per family, no unicode-range splitting needed.

Two families only:
  Manrope        — display AND body (geometric humanist, full Cyrillic)
  JetBrains Mono — uppercase eyebrow labels only (uppercase + digits subset)
"""
import os
import subprocess
import sys

OUT_DIR = "/agent/workspace/agro/assets/fonts"
CSS_OUT = "/agent/workspace/agro/assets/css/fonts.css"
TMP = "/tmp/fontsrc"

SRC = {
    "manrope": "https://raw.githubusercontent.com/google/fonts/main/ofl/manrope/Manrope%5Bwght%5D.ttf",
    "jbmono": "https://raw.githubusercontent.com/google/fonts/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
}

# --- glyph coverage -------------------------------------------------------
BASIC_LATIN = list(range(0x20, 0x7F))
# Ukrainian Cyrillic: А-я plus the four Ukrainian-specific letter pairs
CYRILLIC = (
    list(range(0x410, 0x450))              # А-я
    + [0x404, 0x454, 0x406, 0x456, 0x407, 0x457, 0x490, 0x491]  # Є є І і Ї ї Ґ ґ
    + [0x401, 0x451]                        # Ё ё (transliteration safety)
)
MARKS = [
    0x00A0,  # nbsp
    0x00AB, 0x00BB,          # « »  — required by ТОВ «ЦЕНТРАГРО ПЛЮС»
    0x00A9,                  # ©
    0x00B0,                  # °
    0x00B7, 0x2022,          # · •
    0x00D7,                  # ×
    0x2013, 0x2014,          # – —
    0x2018, 0x2019, 0x201C, 0x201D, 0x201E,  # curly quotes
    0x2026,                  # …
    0x2116,                  # №
    0x2192, 0x2197,          # → ↗
    0x20B4,                  # ₴
    0x2212,                  # −
    0x02BC,                  # ʼ  Ukrainian apostrophe
]

MANROPE_SET = BASIC_LATIN + CYRILLIC + MARKS
# eyebrows are uppercase-only: A-Z, А-Я, digits, space, and a few marks
JBMONO_SET = (
    list(range(0x41, 0x5B)) + list(range(0x30, 0x3A))
    + [0x20, 0x2E, 0x2C, 0x2D, 0x2F, 0x26, 0x25, 0x2B, 0x28, 0x29, 0x3A]
    + list(range(0x410, 0x430))
    + [0x404, 0x406, 0x407, 0x490, 0x2013, 0x00A0, 0x2116]
)

FAMILIES = [
    ("Manrope", "manrope", MANROPE_SET, "400 800"),
    ("JetBrains Mono", "jbmono", JBMONO_SET, "500 700"),
]


def unicodes_arg(codepoints):
    return ",".join(f"U+{c:04X}" for c in sorted(set(codepoints)))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)

    css = [
        "/* Self-hosted variable fonts, subset to basic Latin + Ukrainian Cyrillic",
        " * + typographic marks. Built by tools/build_fonts.py — do not hand-edit.",
        " * Upstream: Manrope and JetBrains Mono, both SIL Open Font License 1.1. */",
        "",
    ]
    total = 0

    for family, slug, charset, wght in FAMILIES:
        raw = os.path.join(TMP, f"{slug}.ttf")
        if not os.path.exists(raw):
            subprocess.run(["curl", "-sSL", "-m", "90", SRC[slug], "-o", raw], check=True)
        raw_size = os.path.getsize(raw)

        out = os.path.join(OUT_DIR, f"{slug}.woff2")
        subprocess.run([
            sys.executable, "-m", "fontTools.subset", raw,
            f"--unicodes={unicodes_arg(charset)}",
            "--flavor=woff2",
            f"--output-file={out}",
            "--layout-features=kern,liga,calt,ccmp,locl,mark,mkmk,rlig",
            "--name-IDs=1,2,3,4,5,6",
            "--no-hinting",
            "--desubroutinize",
            "--drop-tables+=DSIG",
        ], check=True, capture_output=True)

        size = os.path.getsize(out)
        total += size
        print(f"{family:15s} {raw_size/1024:7.1f} KB ttf -> {size/1024:6.1f} KB woff2 "
              f"({len(set(charset))} codepoints)")

        css.append(
            f"@font-face{{font-family:'{family}';font-style:normal;"
            f"font-weight:{wght};font-display:swap;"
            f"src:url('../fonts/{slug}.woff2') format('woff2')}}"
        )

    with open(CSS_OUT, "w") as fh:
        fh.write("\n".join(css) + "\n")

    print(f"\nTOTAL fonts: {total/1024:.1f} KB (both locales, all weights)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
