# Architecture

How this site is generated, and the two contracts that are easy to break by
accident. Read the second half before touching `src/js/app.js` or
`src/css/05-motion.css`.

There is no framework and no build step in CI. `tools/build_site.py` renders
Jinja2 templates to HTML, writes the result into the repository, and the
repository is what GitHub Pages serves. Everything under `assets/` is a build
artefact and is committed on purpose.

## The generator

`main()` runs one triple loop:

```
for V in variants.json["variants"]          # v1, v2, v3
  for lang in (uk, en)
    for page in variants.json["pages"]      -> templates/pages/<id>.html.j2
    for each detail item                    -> article | profile | crop template
```

Detail pages come from one list, and adding a type means adding a row to it:

```python
for kind, items, parent_id, folder, template_name in [
    ("article", c["blog_page"]["posts"], "blog",     "blog",       "article"),
    ("profile", c["team"]["items"],       "about",    "about/team", "profile"),
    ("crop",    c["crops"]["items"],      "services", "services",  "crop"),
]:
```

All three sit exactly one level under their parent, so nothing around the loop
assumes a depth. A page entry may carry an optional `"template"` key when several
pages share a shell — `privacy` and `terms` both render `legal.html.j2`, because
they differ only in which entry of `c.legal` they read.

Counts follow from the content, not from constants: 7 main pages + 6 articles +
4 profiles + 7 crops = 24 per variation per locale, × 3 × 2 = 144, plus
`variants.html` and `404.html` = **146 files**. `tools/verify.py` derives the same
arithmetic from `variants.json` and `uk.json` rather than hardcoding it, so adding
a crop does not require editing the verifier.

### Mechanisms worth knowing before you edit a template

- **`StrictUndefined`.** Any reference to a missing key aborts the build. This is
  an ally: a key added to `uk.json` and forgotten in `en.json` fails immediately
  instead of rendering an empty string in production.
- **`protect_numbers()`** runs over the rendered HTML and binds grouped digits
  with U+00A0, because Ukrainian groups thousands with a space and the line
  breaker was splitting "14 200" across two lines mid-headline. It skips anything
  inside a tag. Every new page goes through it automatically.
- **`DECIMAL`** is a comma for uk and a dot for en. `parse_measure()` respects
  both, which is how the crop pages read a number back out of `"4 800 га"`
  without a second numeric copy of the figure existing anywhere.
- **`noindex = (V["id"] != "v1")`.** Only variation 1 is indexed; three indexed
  copies of one company's site would compete with each other. This applies to new
  page types automatically.
- **`indexed[]`** accumulates the canonical URLs that become `sitemap.xml`.
  `verify.py` asserts that this set is exactly the set of pages that are not
  `noindex` — the sitemap cannot drift from reality without failing the build
  checks.

## How the three variations work

This is the part that decides whether a new page looks like part of the site.

`templates/pages/article.html.j2` does not contain a single reference to `V`.
Neither does `profile.html.j2`, `crop.html.j2`, or `legal.html.j2`. One template
serves all three variations. The difference arrives from two places:

1. `base.html.j2` writes the variation onto the body: `<body class="{{ V.id }}">`.
2. `src/css/07-variants.css` re-skins surfaces, scale and accents through
   selectors like `.v2 .cap__card`, `.v3 .plan`, `.v2 .detail-hero__copy`.

**The consequence that governs every new page:** a page gets each variation's art
direction for free *if it is built from classes `07-variants.css` already knows*,
and stays identical in all three if you invent your own. Identical-in-all-three is
the one outcome a variation-aware page must not have.

So before writing a template, list what is already overridden:

```bash
grep -oE '^\.v[123][^{]*' src/css/07-variants.css | sort -u
```

That output is the palette. `crop.html.j2` was built from it and introduces no new
class at all: `detail-hero`, `detail-hero__copy`, `detail-meta`, `stats-card`,
`card`, `cinfo`, `head`, `head-row`, `plan`, `post`. Measured on one crop page
across the three variations, 4–59% of pixels differ depending on scroll depth.

If a new class is genuinely unavoidable, it needs base styles in
`04-sections.css` **and** overrides for all three variations in
`07-variants.css`, following the logic of its neighbours: v1 shadows and radius
24, v2 hairline borders and radius 12, v3 lines only.

### The trap that scoping fixes

A rule like `.v2 .detail-meta { color: var(--on-dark-2) }` reads as "in variation
2 this row is on a dark surface". That was true while the only page with a
`.detail-meta` was an article, where the row sits inside the ink copy panel. The
crop page puts a breadcrumb in the same class *outside* that panel, on white — and
on-dark grey on white measures 1.69:1. Three separate contrast failures in this
project came from exactly this shape of selector. Scope a variation's on-dark
rules to the surface, not to the variation.

## The motion contract

Two rules. Both were violated by the original implementation in ways that were
invisible until measured.

### 1. Hide with `opacity`, never with `visibility`

`src/css/05-motion.css` has a flash guard that hides animated blocks before GSAP
takes over. It sets `opacity: 0`. It must keep setting `opacity: 0`.

`visibility: hidden` renders identically and additionally removes the node from
the accessibility tree and from the tab order. Because the guard's selector covers
`[data-r]`, `[data-card]`, `[data-split]` and `[data-stagger] > *`, that meant most
of the page. Measured before the change:

| State | Text hidden from assistive tech | Headings in the accessibility tree |
|---|---|---|
| No JS | 5.3% | 23 / 23 |
| Rendered, not scrolled | **74.0%** | **1 / 23** |
| After scrolling | 5.5% | 23 / 23 |

It also produced a second-order failure. `aria-labelledby` on a `<section>`
pointed at a heading whose words were hidden; the accessible name resolved empty;
the section therefore stopped being a `region` landmark; and `aria-labelledby` is
prohibited on a generic element. One CSS declaration was generating 68
`aria-prohibited-attr` violations and 66 `empty-heading` violations as well.

Consequently `src/js/app.js` contains no `autoAlpha`. GSAP's `autoAlpha` is
opacity *plus* visibility, and the visibility half is the whole problem. Every
entrance animates plain `opacity`.

An opaque-zero node stays focusable, which is the point: focus enters it, the
browser scrolls it into view, its own trigger fires, the block reveals. Focusable
controls carry `scroll-margin-block` so the browser scrolls far enough to cross
the trigger line — without it, focus landed on a link whose top sat at 823px in a
900px viewport, 13px short of the 810px line, and the block stayed transparent.

The safety branches — `html.no-motion` and `@media (prefers-reduced-motion)` —
force full visibility with `!important` and should be left alone.

Verify with `python3 .qa/a11y.py` (census plus axe) and `python3 .qa/keyboard.py`
(walks the whole tab order and reports any stop whose reveal never resolved).

### 2. Chunked init must preserve order

`boot()` no longer runs its init passes back to back. It ran 83 ScrollTriggers and
137 tweens in a single 551ms task on a throttled phone, and Total Blocking Time
counts only what a task spends past 50ms — so one 551ms task costs 501ms while ten
55ms tasks cost 50. The passes are now drained one at a time through
`requestIdleCallback`, with `setTimeout(0)` where that does not exist.

Three properties the queue must keep:

1. **Order.** `tagParallaxTargets()` must tag every image before any reveal
   timeline reads `data-parallax` off it. When that tagging lived inside
   `initParallax()`, an already-decoded image built its reveal first, settled at
   scale 1, and the drift then slid it off the edge of its frame. The queue is
   drained front to back and is never reordered to fill a gap.
2. **The first screen stays synchronous.** `initSmoothScroll`,
   `tagParallaxTargets`, `initHero`, `initPageHero` and `initMarquees` run inline.
   The last of those is there for a measured reason: v2's card rail and v3's logo
   bar are inside the hero, building a marquee changes its track's height, and the
   webfont swap reflows the hero at ~340ms. Queued, the rail landed on either side
   of that reflow depending on the run and v2's desktop CLS read 0.028 or 0.068 at
   random.
3. **One refresh at the end.** `ScrollTrigger.refresh()` is expensive and runs
   once, after the last pass.

Two failure modes are handled explicitly. A pass that throws is caught
individually, so it cannot strand the passes behind it. And `motion-ready` is set
only *after* every pass is in place, which makes it a real health signal — a
3000ms timer falls back to `no-motion` if it never appears, so a boot that dies
midway cannot leave the flash guard's `opacity: 0` in place forever. The queue's
own synchronous cutoff is at 2500ms, deliberately below that timer, so on a
healthy page the queue always finishes first and the failsafe never fires.

Nothing styles on `motion-ready`. It exists for the failsafe.

## What not to change without measuring first

- **Lenis.** `syncTouch: false` means it stays out of the scroll path on touch
  devices; removing it noticeably changes desktop feel.
- **`scrub: 0.8`** on the hero depth timeline. Changing it to `true` changes the
  feel, not just the implementation.
- **The `clip-path` wipe in `initImageReveal`.** It is the site's most
  characteristic effect.
- **Reveal on CSS + IntersectionObserver instead of GSAP.** The previous
  implementation did this and could only animate on enter/exit, so nothing could
  be tied to scroll *progress*; parallax, marquees and the hero fan all read as
  snapping into place.

## Verification

The project's own tools, all committed and all exiting non-zero on failure:

| Tool | What it does |
|---|---|
| `tools/verify.py` | static sweep of every built page: references, ids, headings, alt and dimensions, JSON-LD shape, head essentials, indexability, cross-page invariants (sitemap set, duplicate titles, self-canonical, hreflang reciprocity, Cyrillic on English pages), locale parity, weight budgets |
| `tools/geometry_audit.py` | drives Chromium over 3 variations × 5 pages × 5 widths × 4 scroll depths and reports parallax coverage, clipped glyphs, clipped shadows, hub centring, horizontal overflow |
| `tools/interaction_smoke.py` | drawer focus trap, rails, accordion, forms, reduced motion, no-JS |
| `tools/visual_smoke.py` | 24 pages × 7 viewports: overflow, single h1, stuck-hidden animated elements, broken images, clipped text, media leaks |
| `tools/measure_runtime.py` | CLS, LCP, long tasks and frame-interval percentiles; diagnostic, no thresholds |

`tools/build_fonts.py`, `build_images.py` and `build_logo.py` had absolute output
paths pointing at a directory this repository does not have, so they could not run
against the real assets. They now resolve `ROOT` from `__file__` like every other
tool. That is also why two orphaned `woff2` files survived for so long:
`build_fonts.py` clears stale output before rebuilding, and it was clearing a
different directory.

### Regression harness

`.qa/` is not committed (see `.gitignore`) and holds the pixel-comparison harness
used for the accessibility and performance pass: `shots.py` captures a matrix of
pages × variations × viewports × scroll depths, `compare.py` reports the share of
pixels differing by more than 30 on any channel, `a11y.py` and `contrast.py` run
axe, `keyboard.py` walks the tab order, `metrics.py` measures LCP/CLS/TBT under
Lighthouse-shaped throttling, `cls.py` samples one figure many times.

Two things had to be pinned before that comparison meant anything, and they are
worth knowing if you rebuild it. Scroll position is reached with wheel deltas,
never `window.scrollTo` — Lenis owns the scroll and writes its own target back on
the next frame, so a programmatic scroll silently ends up somewhere else. And
before each shot the harness resets infinite animations to their first frame and
drops `will-change`, because `.w__i` carries a compositing hint that flips word
antialiasing between grayscale and subpixel depending on whether the layer has
collapsed yet. Without both, two captures of the *same build* differed by up to
1.36%; with them, by at most 0.02%.
