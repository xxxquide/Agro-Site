# Changelog

## Unreleased — v6 elements: hero fan, capacity plate, partner orbit, geo link, journey rail

A deliberate redesign of five blocks, from two client mockups whose headings match
the published copy word for word. Content was not rewritten; four keys per capacity
card were added to both locales.

Split out onto its own branch: the preceding pass accepted on pixel-for-pixel
equality of existing pages, and a redesign cannot honour that rule.

Five defects, none of them visible in a screenshot, all found by measuring:

    hero cards jumped into place       GSAP owned .fan__item's transform and handed
                                       it back to CSS in a different composition
                                       order. Split into three layers, one
                                       transform each. Matrix now identical across
                                       all 47 frames of the entrance.
    hover never fired                  transform-style: preserve-3d breaks
                                       hit-testing in Chromium. flat is
                                       pixel-identical (0 px differing >30/channel)
    capacity plate escaped its bench   13px at the one-column breakpoint
    orbit pushed the page sideways     11px on v2 at 320px: place-items:center
                                       lets a grid item outgrow its own track
    capacity card inflated its width   425px card in a 420px viewport: a binding
                                       min-height made aspect-ratio derive width

After the last edit:

    verify.py            ALL CHECKS PASSED, 0 warnings
    geometry_audit.py    parallax 0  glyph 0  shadow 0  centre 0  overflow 0
    interaction_smoke    keyboard, reduced motion, no-JS — passed
    visual_smoke.py      224 screenshots, 0 findings (2 before the fixes)
    measure_runtime.py   CLS 0.0001 on all six cases, frames p50 16.7 ms
    width sweep          17 widths x 3 variants, no horizontal overflow

    JS gzip           55.9 KB -> 55.9 KB   (limit 60, hard fail)
    CSS gzip          20.9 KB -> 22.2 KB
    first view gzip  201.7 KB -> 203.1 KB  (limit 420)
    third-party requests             0     (limit 0, hard fail)

Not verified: real Safari/iOS and touch, field CWV, GitHub Pages after merge.
Known and untouched: a transient sideways scroll on mobile while the map and
about-photo reveals play — pre-existing, and it lives in the reveal layer.

## Unreleased — accessibility, blocking time, crop pages, legal pages

Five phases, each measured against a screenshot matrix captured before the first
edit. Threshold throughout: the share of pixels differing by more than 30 on any
channel stays at or under 0.05% on existing pages. Two repeat captures of the same
build differ by at most 0.02%, so the threshold has real headroom.

    hidden from assistive tech, home, before scroll   74.0% -> 3.0%
    headings in the accessibility tree                 1/23 -> 23/23
    axe serious+critical, 27 pages                      100 -> 0
    contrast failures, whole page revealed              144 -> 0
    TBT mobile                     v1 654 -> 216   v2 678 -> 246   v3 571 -> 221
    CLS v2 desktop                      0.028, spiking to 0.068 -> 0.0000
    HTML files                                           92 -> 146
    sitemap URLs                                         30 -> 48

### Accessibility

- The flash guard and all 46 `autoAlpha` calls moved from `visibility` to
  `opacity`. Both render nothing; `visibility` additionally removes the node from
  the accessibility tree and the tab order, and that selector covers most of the
  page. A screen reader reached 3% of the home page's text and no keyboard could
  reach a link below the first screen.
- 68 `aria-prohibited-attr` violations had the same single cause: `aria-labelledby`
  pointed at headings whose words were hidden, so the name resolved empty, so each
  `<section>` stopped being a `region` and the attribute became invalid on it.
  Stating `role="region"` makes the landmark unconditional. 66 `empty-heading`
  violations resolved from the opacity switch alone.
- Page heroes are no longer landmarks. Each was labelled by the H1 inside it while
  the section below carried the same words as its own heading, so `region`
  appeared twice under one name. `<main>` already delimits the hero.
- Both testimonial rails and the hero fan overflow on narrow viewports and only a
  mouse could scroll them: `tabindex`, `role="group"` and a label. The fan's cards
  stay `aria-hidden` — they restate figures the stats section already gives
  properly.
- `scroll-margin-block` on focusable controls, so focus-scrolling clears both the
  sticky header and the reveal trigger line. Focus had been landing on a link 13px
  short of its own trigger, on a block that stayed transparent.

### Blocking time

- `boot()` spends its init passes across idle callbacks instead of running 83
  ScrollTriggers and 137 tweens in one 551ms task. TBT counts only what a task
  spends past 50ms, so one 551ms task costs 501ms and ten 55ms tasks cost 50.
  Trigger and tween counts are unchanged; frame intervals on scroll are unchanged
  at p50 16.7ms, p95 33.3ms, zero frames over 50ms.
- `initMarquees` stays synchronous with the hero. Queued, the v2 card rail landed
  on either side of the webfont reflow depending on the run, and v2's desktop CLS
  read 0.028 or 0.068 at random.
- A pass that throws is now caught individually instead of stranding the passes
  behind it, and `motion-ready` is set only once every pass is in place, so a
  3000ms failsafe can detect a boot that died midway and fall back to `no-motion`.
  Verified by breaking `gsap.registerPlugin`: at 1.5s all 44 animated blocks are
  hidden, at 4.5s every one is visible.
- `geistmono.woff2` is preloaded alongside `onest.woff2`. Both are on the first
  screen but only one was requested before the stylesheet was parsed. This removed
  the hero reflow entirely: v2 desktop CLS went from 0.028 with spikes to 0.068 to
  **0.0000 on ten consecutive runs**, at a cost of 12–20ms LCP.
- Two orphaned font files removed. `build_fonts.py`, `build_images.py` and
  `build_logo.py` had absolute output paths into a directory this repository does
  not have, which is why the orphans survived — the stale-file cleanup was
  clearing somewhere else.

### Contrast — the only visible change

Kept as its own commit so it can be reverted alone. `--grey-300` and `--lime-lo`
are colours for dark surfaces and had drifted onto white, at 1.69:1 and 1.37:1
against a 4.5:1 requirement. Two light-surface counterparts join them,
`--muted-on-light` and `--lime-on-light`, with lightness the only channel moved
and both checked against `--grey-100` as well as white — a grey panel costs about
0.4 of a ratio point, which is why #767676 clears white and fails #f4f5f1.
Counted with every block revealed, because axe skips what a scroll trigger is
holding and a plain sweep saw 28 of the 144.

Five of these were pre-existing bugs rather than token drift, all in v2, where a
dark band had never been added to that variation's own on-dark rules.

### Crop pages

- Seven crops had shared one `/services/` page. Each now has its own at
  `/services/<slug>/` — 42 new pages, 14 of them indexed. One row added to the
  detail loop next to articles and profiles.
- `templates/pages/crop.html.j2` never mentions `V` and introduces no new class,
  so the three art directions arrive through `07-variants.css` on their own: 4–59%
  of pixels differ between variations depending on scroll depth.
- ~750–1000 words per crop per locale. The English is written for an international
  buyer rather than translated — DSTU classes alongside the reference a maltster or
  miller actually uses, Incoterms for delivery bases.
- No figure is duplicated. The three headline numbers are parsed back out of the
  strings the crops section already publishes, so area, yield and gross have one
  home in the content.
- `Product` with `additionalProperty` for all eight quality parameters, and an
  `Offer` with availability, seller and areaServed but no price, because the site
  publishes none.

### SEO and legal

- `BreadcrumbList` on every page below the root — 0 of 92 pages had one. Built
  from the same nav labels the header renders and the same page table `url_for()`
  resolves.
- Privacy policy and terms of use at `/privacy/` and `/terms/`, in both locales
  and all three variations. The form had been collecting a name, an e-mail and a
  phone number under a consent line that promised a document which did not exist.
  Both are real working documents, and both state plainly that the forms have no
  backend and transmit nothing — which will need updating the day a handler is
  connected.
- The consent line under the contact form now links to the privacy policy. Its
  middle clause became the link, the sentence is unchanged word for word, and `a`
  inherits colour with no decoration, so the line occupies the same pixels.
- `Organization` gained a `contactPoint`. `sameAs`, `taxID`, `vatID` and
  `priceRange` have content keys and appear the moment they are filled in — an
  invented ЄДРПОУ code in a knowledge graph is worse than a missing one.
- `robots.txt` names GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-Web,
  PerplexityBot, Google-Extended, Applebot-Extended, CCBot and meta-externalagent
  explicitly. `User-agent: *` already allowed them; it allowed them by silence.
- No `llms.txt`. Ahrefs surveyed 137 000 domains and 97% of those files received
  no request in a month, and Google has said it ignores them.
- `FAQPage` markup kept and documented as producing no rich result.

### Quality assurance

- `tools/verify.py` derives its expected page counts from the content files
  instead of three hardcoded literals, and gained the cross-page checks no
  per-page pass can make: the sitemap set against the indexable set, duplicate
  titles and descriptions, self-canonical, hreflang reciprocity, `Product` with
  `additionalProperty` on crop pages, `BreadcrumbList` below the root, and
  Cyrillic leaking onto an English page. All zero.
- `docs/ARCHITECTURE.md` and `docs/CONTENT-GUIDE.md` added. The first documents
  the motion contract, so the next person does not restore `visibility: hidden`
  believing `opacity` to be sloppiness. The second maps every fact on the site to
  the key that holds it.
- README's weight table re-measured. It had promised 97.0 KB for `index.html`
  against an actual 155.2 KB — a 59% gap, snapped eight commits earlier.

## Unreleased — UI/UX pass 3: measured geometry

Pass 2 signed its defect matrix off by eye and several rows were still failing.
This pass measures the rendered page instead: `tools/geometry_audit.py` drives
Chromium over 3 variations x 5 pages x 5 widths and reports four numeric defect
classes. It is committed and exits non-zero.

    parallax 555 -> 0    shadow 186 -> 0    centre 15 -> 0    glyph 0    overflow 0

### Fixed

- Photographs no longer uncover their frame at either end of a parallax scrub.
  The drift is +/-amount/2 percent of the element's height and nothing had grown
  the element to match; it now rests at `scale(1 + amount/100)`.
- Every entrance animation rewritten from `gsap.from()` to `gsap.fromTo()`. A
  from-tween records the element's current value as its destination, and the
  refresh this page fires on image load could make it re-record its own start
  state — which pinned all three testimonial cards 52px low, permanently.
- The word-reveal mask clears the glyph's ink on all four sides. It inset only
  the bottom, so round and tall letters lost their side bearings in every large
  heading.
- Rounded media inherits its radius down the whole `picture > img` chain, so no
  square corner shows through as a dark triangle.
- Rails, the mobile fan and the v2 hero marquee reserve room for their cards'
  shadows instead of slicing them into a hard line.

### Changed

- The opening screen fills the viewport on all three variations. It was capped
  at 54rem, so on a tall window it stopped short of the fold and clipped the
  outer fan cards.
- Stats rebuilt: value and unit are separate elements in a nowrap baseline row
  (the unit used to wrap onto its own line at full display size), on a
  four-column grid where the land bank and season tonnage take a double tile.
- The logistics widget is now a dispatch radar. Its hub had been placed in an
  implicit second grid row and sat 59px below its own rings; revolving labels
  were unreadable besides.
- The Ukraine map is generated by `tools/build_map.py` from Natural Earth
  admin-1: 27 oblasts with Vinnytsia highlighted, and four arcs — Kyiv, Odesa,
  Vinnytsia, Haisyn — from a single rule. Two of the four had no line at all and
  Kyiv's curve doubled back on itself.
- v2's news grid uses hairline borders instead of an ink backing plate, which
  had been showing through as a black slab above the grid.
- The tag marquee has room above it and its two tracks run at different speeds.

## Unreleased — client-ready UI/UX pass 2

### Shared system

- Added reusable MediaFrame, StatsCard, IconBadge, CardLift, seamless marquee, exclusive accordion and touch-rail primitives.
- Replaced repeated one-off stats, media, capacity, news and team markup with shared Jinja macros and data-driven variants.
- Added strict visual checks for clipped text, media coverage inside rounded masks and marquee overlap.

### Visual and interaction polish

- Rebuilt V1 partner ecosystem mobile layout, shared stats and four agricultural capacity visualizations.
- Added a local animated Ukraine route map with Vinnytsia, Haisyn, Kyiv and the Port of Odesa.
- Fixed V2 dark-surface labels, team media masks, article treatment, double marquee coverage and the incomplete News grid.
- Removed the V3 glass-bar first-paint flash and improved quiet stats, centred headings and testimonial surfaces.
- Added exclusive animated FAQ closing, lifecycle-managed capacity motion and verified horizontal testimonial swipe on every V3 page that contains the rail.
- Added accessible hover/focus lift to news, testimonial and team cards.

### Detail routes

- Added six full UA/EN articles and four UA/EN team profiles for every variation.
- Added Article and ProfilePage templates based on the supplied reading-blog reference.
- Added 36 Article and 24 Person detail routes with semantic card links, canonical, hreflang, Article/Person JSON-LD and related content.
- Clean build now produces 91 content/chooser pages plus 404, for 92 HTML files total; only the 30 V1 UA/EN routes are indexed.

### Quality assurance

- Visual smoke covers 24 representative main/detail pages at 320, 375, 390, 768, 1024, 1440 and 1920 px.
- Interaction smoke covers drawer focus, all V3 testimonial rails, V2 double marquee, exclusive accordion, hover lift, article/profile routes, forms, reduced motion and no-JS.
- Static verify checks 92-page output, 36 Article routes, 24 Person routes, locale parity, internal links, SEO and asset budgets with zero warnings.

### Measured checkpoint

- First-view budget: 181.5 KB including gzipped HTML/CSS/JS, vendor JS, fonts and V1 LCP AVIF.
- Local repeated diagnostics: CLS approximately 0–0.0274; mobile frame interval p95 16.7–16.8 ms; desktop p95 around 33 ms in the stable run.
- These remain local diagnostics, not field Core Web Vitals.

## Previous — reference-grade completion pass

### Art direction

- Strengthened the separation between the three site directions beyond section order.
- Rebuilt V2 Services as a full-bleed editorial-industrial dark band with indexed service rows, hairline separators and signal graphics.
- Rebuilt V3 Services as a quiet gallery of indexed image-and-copy rows without card containers.
- Rebuilt V3 Blog as one large photographic feature beside a compact editorial story index.
- Tightened the V2 portrait hero so the navigation, headline and moving card rail no longer compete at the top edge.
- Repositioned the V3 portrait crop so the display heading no longer sits directly across the subject's face.
- Gave each About intro a different operational photograph instead of repeating the inner-page hero image.
- Added compact service signal graphics and animated them with the shared motion grammar.

### Motion and interaction

- Activated the existing inner-page hero timeline; it had been defined but was never called during boot.
- Added viewport and tab-visibility control for the V1 partner orbit.
- Added pause behavior for orbit motion on hover and focus.
- Added a safe reload when the operating-system reduced-motion preference changes while the page is open.
- Kept every animated element visible when motion is reduced or GSAP is unavailable.
- Added a real mobile navigation focus trap, inert background content, dynamic open/close labels and focus restoration.

### Forms and accessibility

- Restored native constraint validation on contact and newsletter forms.
- Changed the contact field to a semantic e-mail input and corrected the name autocomplete token.
- Kept demo submissions honest: valid forms show the local demo notice and never imply that data was transmitted.
- Added live status semantics, invalid-field styling and disabled-submit styling.
- Fixed the V1 contact form being clipped below the photograph on mobile.
- Removed an unused legacy template that duplicated obsolete page markup.

### Quality assurance

- Added tools/visual_smoke.py for deterministic screenshots and overflow/image/heading checks at 320, 375, 390, 768, 1024, 1440 and 1920 px.
- Added tools/interaction_smoke.py for drawer, focus, form and reduced-motion checks.
- Added tools/measure_runtime.py for clearly labelled local CLS, LCP, long-task and frame-interval diagnostics.
- Extended tools/verify.py to reject disabled native validation and non-semantic e-mail fields.
- Verified 31 generated pages, UA/EN parity, zero static warnings, browser smoke checks and mobile/desktop responsive coverage.

### Measured checkpoint

- First-view budget: 174.0 KB for gzipped HTML/CSS/JS, self-hosted vendor JS, both fonts and the V1 LCP AVIF.
- Local six-case diagnostics: CLS 0–0.0090; mobile frame interval p95 16.7–16.8 ms; desktop p95 about 33 ms under the scripted scroll workload.
- These are local diagnostics, not field Core Web Vitals; production LCP/INP still require the deployed HTTPS site and real devices.
