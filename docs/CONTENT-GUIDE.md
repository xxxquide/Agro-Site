# Content guide

Everything on this site is demonstration data, deliberately. This document is the
map from "a fact about the company" to "the key that holds it", so switching to
real data is editing JSON rather than hunting through HTML.

Two rules before anything else:

- **Never edit the HTML.** Every `.html` file in the repository, plus
  `assets/css/main.css`, `assets/js/app.js`, `sitemap.xml`, `robots.txt` and
  `site.webmanifest`, is generated. Edit `content/*.json`, then run
  `python3 tools/build_site.py`. A hand edit is overwritten on the next build.
- **Edit both locales.** `content/uk.json` and `content/en.json` must have
  identical structure — same keys, same array lengths, everywhere. The build uses
  `StrictUndefined`, so a key present in one and missing in the other fails the
  build immediately; `tools/verify.py` also compares the two shapes. That is a
  feature. Do not work around it by deleting a key.

After any change: `python3 tools/build_site.py && python3 tools/verify.py`.

---

## Where each fact lives

| What | File and key | What to watch for |
|---|---|---|
| Trading name | `brand.name` | Appears in every `<title>` after an em dash. Titles are capped at 70 characters, so a longer name shortens the room every `seo_title` has — `verify.py` warns per page |
| Legal name | `brand.legal` | Used in `<meta name="author">`, the manifest, the footer copyright and `Organization.legalName` |
| Two-part logotype | `brand.word_1`, `brand.word_2` | Rendered as two lines in the header and footer lockup. `word_2` is set at 8px with wide tracking; a long word will not fit |
| Tagline | `brand.tagline`, `footer.tagline` | |
| **ЄДРПОУ code** | `brand.tax_id` | Empty. Fill it and `Organization.taxID` appears in the graph; left empty, the field is omitted rather than published blank |
| **VAT / ІПН** | `brand.vat_id` | Same, `Organization.vatID` |
| **Social profiles** | `brand.same_as` | Empty array. Add full URLs and they become `Organization.sameAs` — the strongest single signal tying this site to a known entity |
| Address | `contact.address`, and the postal fields in `build_jsonld()` in `tools/build_site.py` | The structured address is in the generator, not the content file, because it needs separate street/locality/region/postcode fields. Change both or they disagree |
| Coordinates | `LocalBusiness.geo` in `tools/build_site.py` | 49.0716, 29.3608 — geocoded from the address and **not verified on the ground**. Check before launch |
| Phone | `contact.phone` | The `tel:` href is derived from it by stripping non-digits, so keep the leading `+` and the country code |
| E-mail | `contact.email` | Used in `mailto:` links, the JSON-LD graph and both legal documents |
| Opening hours | `contact.hours` for display; `openingHoursSpecification` in `tools/build_site.py` for the graph | Two places, same caveat as the address |
| Headcount | `numberOfEmployees` in `tools/build_site.py` | 240 |
| Founding year | `foundingDate` in `tools/build_site.py`, and prose in `about.*`, `journey.*` | The site says "18 seasons" and "since 2008" in several places. Change the year and search the prose for both |
| Price band | `seo.price_range` | Empty. Fill it and `LocalBusiness.priceRange` appears |
| Search Console | `seo.google_site_verification` | Empty. Fill it and the meta tag appears. DNS verification is an alternative that costs no request at all |
| Domain | `BASE` and `SUBPATH` in `tools/build_site.py` | Two lines. `BASE` is the absolute origin used by canonicals, hreflang, JSON-LD, OG tags and the sitemap; `SUBPATH` is the domain-absolute prefix `404.html` and the manifest need. Moving to a custom domain is editing these two and rebuilding |

### Production figures

| What | Key | Cross-checks that must stay true |
|---|---|---|
| Land bank, 14 200 ha | `about.stats[0]` | **Must equal the sum of the seven crop areas.** It currently does, exactly |
| Crops in rotation, 7 | `about.stats[1]` | Must equal `len(crops.items)` |
| Storage, 46 000 t | `about.stats[2]` | Own elevator. The capacity card also states 58 000 t including leased capacity, and its split track is drawn at 79% — 46 000 / 58 000 = 79.3%. Change one and the bar lies |
| Shipped per season, 92 000 t | `about.stats[3]` | The seven crops gross 106 710 t; the difference is beet going to a sugar plant plus retained seed. Keep it plausible |
| Years on the market, 18 | `about.stats[4]` | Tied to `foundingDate` 2008 |
| Export countries, 14 | `about.stats[5]` | Also stated in every crop page's commercial-terms section |
| Drying, 1 200 t/day | `seo.description`, `capacity.cards[*]`, and every crop page body | Stated in prose in several places |
| Yield chart | `capacity.cards[0].series` | Bars are scaled between the series min and max, not from zero, so a flat series renders flat. Every exact value is printed above its bar |
| Distances | `geo.distances[]` | Vinnytsia 85, Haisyn 35, Odesa port 380, Kyiv 230 km. The map's four routes are drawn to fixed coordinates in `templates/ukraine-map.svg.j2` and paired to labels by `data-place`, never by document order — renaming a city means editing the SVG too |

### The seven crops

`crops.items[]`, in both locales. Order matters: `related` indexes into this array,
and the footer's product column indexes into it via `footer.columns[1].links[].crop`.

| Key | Notes |
|---|---|
| `name` | Also appears in `contact.form.crop_options` — keep the two lists in step |
| `img` | Must be a key in `assets/img/manifest.json` |
| `alt` | Real alt text, not the crop name repeated |
| `area` `yield` `volume` | Strings like `4 800 га` / `4,800 ha`. **The numbers on the crop page's three stat cards are parsed out of these strings at build time**, so there is no second copy to keep in sync. Keep the format: digits, locale separator, space, unit. uk uses a space for thousands and a comma for decimals; en a comma and a dot. A malformed string aborts the build with a named error rather than rendering a zero |
| `specs` | Exactly the four pairs the crops accordion shows on the home and services pages. Adding a fifth makes that panel taller — put extra rows in `specs_extra` instead |
| `specs_extra` | The rest of the specification sheet. The crop page renders `specs + specs_extra`, and `Product.additionalProperty` in the JSON-LD covers all of them — this is what makes moisture, protein, test weight and falling number machine-readable |
| `slug` | Latin, identical in both locales, and part of the URL. Changing it changes a live URL: add a redirect or accept the loss |
| `seo_title` | Keep under 53 characters — the brand suffix takes the rest of the 70-character budget |
| `seo_description` | 140–160 characters, with at least one concrete figure |
| `lead` `body` `terms` `related` | Page lead; 4–6 body sections of `{heading, paragraphs[], items?}`; two blocks of `{name, desc, rows[{k,v}]}`; 2–3 indexes of other crops |

Adding an eighth crop is one JSON object per locale and nothing else — the build
produces its 6 pages, the sitemap gains 2 URLs, and `verify.py` recalculates the
expected file count from the content itself.

### People, quotes, news, partners

| What | Key | Notes |
|---|---|---|
| Team | `team.items[]` | `slug` becomes `/about/team/<slug>/`. `img` must be in the image manifest. The three portraits in the `avatars` cluster are the first three entries |
| Testimonials | `testimonials.items[]` | Names, roles and companies are invented. Real quotes need written permission from the person quoted |
| News | `blog_page.posts[]` | `slug` becomes `/blog/<slug>/`. `iso` is the machine date and `date` the displayed one — **keep them consistent**, nothing checks it. `related` indexes into this same array |
| Partner marks | `partners.items[]` | Invented wordmarks, on purpose: putting real companies' trademarks on a site that claims them as partners is both a trademark problem and a false endorsement claim. Replace only with written permission |
| FAQ | `faq.items[]` | Still marked up as `FAQPage`. Google no longer shows FAQ snippets for most sites, so expect no rich result from it — the markup stays because it is valid and helps entity understanding |
| Legal documents | `legal.privacy`, `legal.terms` | Real working documents, but written against the current state of the site: **they say the forms have no backend and transmit nothing.** Connecting a form handler makes that false. Update section 2 of the privacy policy the same day |
| Consent line | `contact.form.note_before`, `note_link`, `note_after` | Three parts that concatenate into one sentence; the middle becomes the link to the privacy policy. Keep the concatenation reading naturally |
| OG images | `assets/img/og-uk.jpg`, `og-en.jpg` | Generated by `tools/build_og.py`, 1200×630. Regenerate after changing the brand name |

---

## What has to be added before launch

Ordered by how much it costs to leave undone.

1. **A form handler.** Both forms are inert. Native validation runs and a valid
   submission shows a notice explaining the demo state; nothing is sent anywhere.
   Until this exists, every enquiry is silently lost. Adding it also obliges the
   privacy-policy update below.
2. **Update the privacy policy.** It currently states truthfully that no data is
   transmitted or stored. The moment a handler exists that is false. Section 2
   needs rewriting, and the retention period and the data controller named.
3. **ЄДРПОУ code and VAT number** into `brand.tax_id` / `brand.vat_id`.
4. **Social profile URLs** into `brand.same_as`.
5. **Search Console verification** into `seo.google_site_verification`, or via
   DNS.
6. **Verify the coordinates** in `LocalBusiness.geo` against the actual site
   entrance, not the settlement centroid.
7. **Certificates**, if any exist — ISO, GMP+, organic. Buyers look for them and
   there is nowhere in the content holding them yet; this needs a new content key
   and a place in the template.
8. **Confirm the delivery bases** on the crop pages. They currently read EXW
   elevator / FCA / CPT port of Odesa. If the company does not in fact sell CPT,
   that is a commercial misstatement rather than a typo.
9. **Real photography.** Every image is generated. Real fields, the real elevator
   and the real team change how the site reads more than any copy edit.

## Known limitations

- **Cache headers.** GitHub Pages serves everything with `Cache-Control:
  max-age=600` and filenames carry no content hash, so returning visitors
  re-validate assets that never change. This cannot be fixed on Pages — it is an
  argument for a host where headers are configurable. Adding hashes to filenames
  would break both the `.nojekyll` layout and existing links and should not be
  done without agreement.
- **`Article.image` is one aspect ratio.** Google recommends 16:9, 4:3 and 1:1 for
  the same article. The news photography exists at 3:2 in two widths, both of
  which are published; the other ratios need new crops out of
  `tools/build_images.py`.
- **The apostrophe.** Ukrainian copy uses U+0027. The font subset also carries
  U+02BC, which is the typographically correct Ukrainian apostrophe. Migrating is
  a whole-content find-and-replace and a deliberate decision, not something to do
  to one string.
- **Counters under reduced motion** print raw digits (`14200`) where everyone else
  reads `14 200`. The locale-correct renderer exists in `src/js/app.js` as
  `renderCounterFinal()` and is deliberately not wired in, because switching it
  changes what those visitors see. It is a one-line change when signed off.
- **`crops.hint`, `contact_quick()` and `[data-secnum]`** exist in the content and
  the CSS but are rendered by no template. Harmless, and worth knowing before
  hunting for where they appear.
