# UI/UX Pass 2 Defect Matrix

Baseline: feat/reference-grade-redesign at 97a21948b571c7842e8bfdcd4b6bb8b930032786.

Status values: OPEN, VERIFIED, MANUAL.

## Global

| ID | Defect / acceptance | Status |
|---|---|---|
| G01 | Rounded media never exposes square container corners | VERIFIED |
| G02 | No clipped glyphs or overflowing UA/EN text | VERIFIED |
| G03 | Single and double marquees are edge-to-edge, seamless and independent | VERIFIED |
| G04 | Repeated service media uses one ratio and 40–50 percent split | VERIFIED |
| G05 | Shadows remain local and never bleed into the next section | VERIFIED |
| G06 | Capacity accordion opens one panel and smoothly closes the previous one | VERIFIED |
| G07 | News and testimonial cards have accessible hover/focus lift | VERIFIED |
| G08 | Stats, capacity, icon badges, rails and media frames are shared components | VERIFIED |

## V1

| ID | Defect / acceptance | Status |
|---|---|---|
| V1-01 | Partner ecosystem cards do not collide on desktop or mobile | VERIFIED |
| V1-02 | About images fill their masked frames without grey corners | VERIFIED |
| V1-03 | Shared stats cards feel reference-grade | VERIFIED |
| V1-04 | Storage, logistics and laboratory visualizations are detailed and coherent | VERIFIED |
| V1-05 | Geography uses a local Ukraine map, labelled cities and animated route | VERIFIED |
| V1-06 | Partner marks are centred, sharp and not over-zoomed | VERIFIED |
| V1-07 | Team cards link to profile pages | VERIFIED |
| V1-08 | Services hero and media split are consistent; marquee has breathing room | VERIFIED |
| V1-09 | News cards have clean corners, full text and article links | VERIFIED |
| V1-10 | Contact mobile layout and form/media surface match the reference geometry | VERIFIED |

## V2

| ID | Defect / acceptance | Status |
|---|---|---|
| V2-01 | Inline icon heading and crop text do not clip | VERIFIED |
| V2-02 | Partner ecosystem has clear lower spacing | VERIFIED |
| V2-03 | Shared stats and shield badge are correctly sized | VERIFIED |
| V2-04 | Capacity deltas stay legible on dark surfaces | VERIFIED |
| V2-05 | Both marquee rows use full width and never overlap | VERIFIED |
| V2-06 | About headings are white on dark and media corners are clean | VERIFIED |
| V2-07 | Services hero/media and decorative transitions are coherent | VERIFIED |
| V2-08 | Why-to-Crops background transition has adequate breathing room | VERIFIED |
| V2-09 | News hero/title/corners/marquee/CardLift are corrected | VERIFIED |
| V2-10 | Contacts remain regression-free | VERIFIED |

## V3

| ID | Defect / acceptance | Status |
|---|---|---|
| V3-01 | Glass logo bar blur is present at first paint | VERIFIED |
| V3-02 | Animated stats use the shared quiet StatsCard | VERIFIED |
| V3-03 | Crops and Services headings stay centred independently of CTAs | VERIFIED |
| V3-04 | Testimonial rail swipes on mobile on every page | VERIFIED |
| V3-05 | Testimonial buttons, borders, text and shadows are safe | VERIFIED |
| V3-06 | Capacity uses the shared detailed visualization set | VERIFIED |
| V3-07 | About, Services and News hero media fully fill their frames | VERIFIED |

## Detail pages and final QA

| ID | Defect / acceptance | Status |
|---|---|---|
| D01 | Six news articles have UA/EN detail pages in all three variants | VERIFIED |
| D02 | Four team members have UA/EN profile pages in all three variants | VERIFIED |
| D03 | Cards are semantic links with keyboard and focus support | VERIFIED |
| D04 | Canonical, hreflang, sitemap, Article and Person JSON-LD are correct | VERIFIED |
| Q01 | Visual QA passes at 320, 375, 390, 768, 1024, 1440 and 1920 px | VERIFIED |
| Q02 | Interaction QA covers accordion, touch rails, marquees, hover/focus and forms | VERIFIED |
| Q03 | No-JS and reduced-motion fallbacks remain complete | VERIFIED |
| Q04 | Clean checkout build, verify, deployment and live review succeed | OPEN |

## Manual device review

- MANUAL: subjective hover-glow intensity on a colour-calibrated display.
- MANUAL: perceived marquee and route-drawing speed on a physical touch device.
- MANUAL: field LCP and INP after the live HTTPS deployment; local diagnostics are not field Core Web Vitals.
