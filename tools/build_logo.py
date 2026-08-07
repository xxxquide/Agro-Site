#!/usr/bin/env python3
"""Generate the ЦЕНТРАГРО ПЛЮС identity mark as SVG + raster favicons.

Concept — "field plan from above"
--------------------------------
The mark is a cadastral plan of four parcels seen from the air, split by a cross
of service roads. It encodes all three parts of the name:

  ЦЕНТР  — the crossing point of the two roads is the centre of the estate
  АГРО   — the largest parcel carries tramlines: this is worked land, not a grid
  ПЛЮС   — the roads themselves form the plus, in negative space

Two deliberate decisions keep it from looking like a generic four-square icon:
the road cross sits off-centre (48/56 rather than 50/50), the way a real field
plan does; and the tramlines give the biggest parcel a direction, so the eye
reads cultivated land instead of abstract blocks. It survives 16 px because the
whole form is straight edges and one accent block.

A first pass built the mark from four radiating grain kernels. Rendered, it read
as a four-petal flower — the failure mode that kills most agro marks — so it was
discarded rather than patched.
"""
import os

# See the note in build_fonts.py: this was an absolute path into a directory
# this repository does not have.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "icons")

INK = "#0E2A1B"     # deep field green
LIME = "#C6F24E"    # accent
CREAM = "#F7F6F1"

# --- plan geometry (48 x 48 canvas) ---------------------------------------
ROAD = 2.35         # width of the service roads
VX = 20.4           # vertical road centre  (off-centre: left parcel narrower)
HY = 27.4           # horizontal road centre (off-centre: bottom row shorter)
R_OUT = 11.0        # outer corner radius, matches the template's icon language
R_IN = 0.8          # inner corner radius — near-square: land split by roads,
                    # not four separate tiles

L = VX - ROAD / 2               # left column right edge
Rr = VX + ROAD / 2              # right column left edge
T = HY - ROAD / 2               # top row bottom edge
B = HY + ROAD / 2               # bottom row top edge


def parcel(x, y, w, h, r_tl, r_tr, r_br, r_bl):
    """Rounded rect with independent corner radii."""
    return (
        f"M{x + r_tl:.2f} {y:.2f}"
        f"H{x + w - r_tr:.2f}"
        + (f"A{r_tr:.2f} {r_tr:.2f} 0 0 1 {x + w:.2f} {y + r_tr:.2f}" if r_tr else "")
        + f"V{y + h - r_br:.2f}"
        + (f"A{r_br:.2f} {r_br:.2f} 0 0 1 {x + w - r_br:.2f} {y + h:.2f}" if r_br else "")
        + f"H{x + r_bl:.2f}"
        + (f"A{r_bl:.2f} {r_bl:.2f} 0 0 1 {x:.2f} {y + h - r_bl:.2f}" if r_bl else "")
        + f"V{y + r_tl:.2f}"
        + (f"A{r_tl:.2f} {r_tl:.2f} 0 0 1 {x + r_tl:.2f} {y:.2f}" if r_tl else "")
        + "Z"
    )


# four parcels, clockwise from top-left
P_TL = parcel(0, 0, L, T, R_OUT, R_IN, R_IN, R_IN)
P_TR = parcel(Rr, 0, 48 - Rr, T, R_IN, R_OUT, R_IN, R_IN)
P_BR = parcel(Rr, B, 48 - Rr, 48 - B, R_IN, R_IN, R_OUT, R_IN)
P_BL = parcel(0, B, L, 48 - B, R_IN, R_IN, R_IN, R_OUT)


def tramlines():
    """Diagonal working lines across the largest (top-left) parcel.

    Offsets are picked so both endpoints of every line land on a straight run of
    the parcel outline, never on the rounded outer corner. That removes the need
    for a <clipPath> — which mattered because the mark is inlined twice per page
    and a repeated clip id would be invalid HTML.
    """
    out = []
    for off in (16.0, 24.0, 32.0):
        x1, y1 = max(0.0, off - T), min(T, off)
        x2, y2 = min(L, off), max(0.0, off - L)
        out.append(f"M{x1:.2f} {y1:.2f} L{x2:.2f} {y2:.2f}")
    return " ".join(out)


TRAM = tramlines()


def mark(fill_main, fill_soft, fill_accent, tram_stroke, detail=True):
    """Assemble the mark. `detail` off = no tramlines (for 16 px use)."""
    svg = [
        f'<path d="{P_TL}" fill="{fill_main}"/>',
        f'<path d="{P_TR}" fill="{fill_accent}"/>',
        f'<path d="{P_BL}" fill="{fill_soft}"/>',
        f'<path d="{P_BR}" fill="{fill_main}"/>',
    ]
    if detail:
        svg.insert(1,
            f'<path d="{TRAM}" stroke="{tram_stroke}" stroke-width="1.5" '
            f'stroke-linecap="round" opacity=".5" fill="none"/>')
    return "".join(svg)


def write(name, svg):
    path = os.path.join(OUT, name)
    with open(path, "w") as fh:
        fh.write(svg)
    print(f"{name:26s} {len(svg):5d} B")
    return path


def main():
    os.makedirs(OUT, exist_ok=True)

    # 1. Nav mark — parcels inherit page colour, one parcel stays lime.
    write("logo-mark.svg",
          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" '
          'role="img" aria-label="ЦЕНТРАГРО ПЛЮС">'
          + mark("currentColor", "currentColor", LIME, CREAM)
          .replace(f'<path d="{P_BL}" fill="currentColor"/>',
                   f'<path d="{P_BL}" fill="currentColor" opacity=".55"/>')
          + "</svg>")

    # 2. Single-colour mark for monochrome contexts (print, stamps, watermark).
    write("logo-mark-flat.svg",
          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
          + mark("currentColor", "currentColor", "currentColor", "none", detail=False)
          + "</svg>")

    # 3. Favicon tile — mark inset on ink, tramlines kept at 96 px+ only.
    tile_body = mark(CREAM, "#7E9E6A", LIME, INK)
    favicon = write("favicon.svg",
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
                    f'<rect width="48" height="48" rx="{R_OUT}" fill="{INK}"/>'
                    '<g transform="translate(24 24) scale(.72) translate(-24 -24)">'
                    + tile_body + "</g></svg>")

    # 4. Raster icons for platforms that still need PNG.
    import cairosvg
    small = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
             f'<rect width="48" height="48" rx="{R_OUT}" fill="{INK}"/>'
             '<g transform="translate(24 24) scale(.74) translate(-24 -24)">'
             + mark(CREAM, "#7E9E6A", LIME, INK, detail=False) + "</g></svg>")
    small_path = os.path.join(OUT, "_favicon-small.svg")
    with open(small_path, "w") as fh:
        fh.write(small)

    for out_name, size, src in (("favicon-32.png", 32, small_path),
                                ("favicon-96.png", 96, favicon),
                                ("apple-touch-icon.png", 180, favicon)):
        dest = os.path.join(OUT, out_name)
        cairosvg.svg2png(url=src, write_to=dest, output_width=size, output_height=size)
        print(f"{out_name:26s} {os.path.getsize(dest)/1024:5.1f} KB  ({size}px)")
    os.remove(small_path)

    # 5. Horizontal lockup for README / social cards.
    lockup = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 140">'
        f'<rect width="560" height="140" fill="{INK}"/>'
        '<g transform="translate(44 34) scale(1.5)">' + tile_body + "</g>"
        f'<text x="150" y="63" font-family="Manrope,Arial,sans-serif" font-size="36" '
        f'font-weight="800" letter-spacing="-1.6" fill="{CREAM}">ЦЕНТРАГРО</text>'
        f'<text x="151" y="99" font-family="Manrope,Arial,sans-serif" font-size="26" '
        f'font-weight="500" letter-spacing="9.5" fill="{LIME}">ПЛЮС</text>'
        "</svg>"
    )
    lock_path = write("logo-lockup.svg", lockup)
    cairosvg.svg2png(url=lock_path,
                     write_to=os.path.join(OUT, "logo-lockup.png"), output_width=1120)
    print(f"{'logo-lockup.png':26s} "
          f"{os.path.getsize(os.path.join(OUT, 'logo-lockup.png'))/1024:5.1f} KB")


if __name__ == "__main__":
    main()
