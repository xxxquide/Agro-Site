# UI/UX Pass 3 Defect Matrix

Baseline: `feat/reference-grade-redesign` at `d3525bf`.

Pass 2 signed every row off by eye. Pass 3 found that several of those rows were
still failing — `G01` (rounded media exposing square corners), `G02` (clipped
glyphs) and `G05` (shadows bleeding into a hard line) among them. Reading a
stylesheet cannot tell you whether a photograph covers its frame at the far end
of a parallax scrub, so this pass measures the rendered page instead.

`tools/geometry_audit.py` drives Chromium over 3 variations x 5 pages x 5
widths, settles the entrance timelines, samples four scroll depths per page and
reports four numeric defect classes. It is committed and exits non-zero, so
these faults cannot come back unnoticed.

## Measured

| Defect class | What it measures | Before | After |
|---|---|---:|---:|
| `parallax` | photograph fails to cover its frame at some scroll depth | 555 | **0** |
| `shadow` | card shadow clipped by an ancestor with less slack than its blur | 186 | **0** |
| `centre` | radial widget's hub off the centre of its own rings | 15 | **0** |
| `glyph` | word-reveal mask narrower than the glyph's ink | 0 | **0** |
| `overflow` | document scrolls horizontally | 0 | **0** |

`python3 tools/verify.py` and `python3 tools/geometry_audit.py` both pass.

## Root causes

| ID | Defect | Root cause | Fix |
|---|---|---|---|
| P3-01 | White/black strip along the edge of many photographs | The drift is `±amount/2` percent of the element's height and nothing grew the element to match | Element rests at `scale(1 + amount/100)`, exactly the travel |
| P3-02 | Same strip, on images that had already been "fixed" | The reveal timeline settled images at `scale: 1`, cancelling the compensation | Both paths share `parallaxCover()`; attribute tagging hoisted ahead of the reveals |
| P3-03 | Testimonial cards pinned 52px low, author line cut off | `gsap.from()` re-recorded its own start state as its destination after a `ScrollTrigger.refresh()` | Every entrance rewritten as `gsap.fromTo()` with both ends stated |
| P3-04 | Side bearings shaved off large headings | `.w` reveal mask inset only the bottom edge | Mask clears the ink on all four sides, with extra room where tracking is tightest |
| P3-05 | Dark triangles at the corners of rounded photographs | Only the outer frame carried the radius | `border-radius: inherit` down the whole `picture > img` chain |
| P3-06 | Opening screen stopped short of the fold; outer fan cards clipped | `.hero` capped at `min(100svh, 54rem)` | Fills the viewport in `svh`/`dvh`; copy centred by auto margins; fan reserves its travel |
| P3-07 | Unit wrapped onto its own line — "46 000" / "т" | Value and unit were one text node in a 9.5rem auto-fit column | Two elements in a nowrap baseline row; four-column grid with two double tiles |
| P3-08 | Logistics hub 59px below its rings | Hub was the only in-flow child of a grid whose siblings were absolutely positioned, so it landed in an implicit second row | Widget rebuilt as a dispatch radar; hub centred by `inset: 0; margin: auto` |
| P3-09 | Rings came to rest 29px off-centre after the rebuild | SVG `transform-origin` resolves against user space, so GSAP's scale compensation did not unwind | `transform-box: fill-box` on the animated SVG shapes |
| P3-10 | Map had no oblasts; Vinnytsia and Haisyn had no route; Kyiv's curve doubled back | One silhouette path and two hand-drawn quadratics, one with a control point outside both endpoints | `tools/build_map.py` generates 27 oblasts and four arcs from one rule |
| P3-11 | Black slab above the v2 news grid | `.v2 .blog-grid` used an ink panel showing through a 1px gap; any unpainted card exposed it | Hairline borders on the cards, no backing plate |
| P3-12 | Tag marquee fused with the block above it | `.tagband` was a full-bleed band with no outer margin | Top margin, rule, edge fades, and the two tracks desynced (40s / 47s) |
| P3-13 | News cards in a row had different heights | The feature card carried a taller `min-height` than its neighbour | `grid-auto-rows: 1fr` with a shared minimum |

## Notes

- Crimea and Sevastopol are drawn as Ukrainian. Natural Earth's default point of
  view files them under Russia; `tools/build_map.py` re-adds them by name. See
  `docs/map-source.md` — this is deliberate and should not be "corrected".
- `geometry_audit.py` skips elements still carrying an entrance transform and
  images that are thumbnails rather than frame-filling covers. Both exclusions
  are there because measuring them produced false positives, not because the
  cases are uninteresting.
