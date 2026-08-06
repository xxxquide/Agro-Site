# Changelog

## Unreleased — reference-grade completion pass

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
