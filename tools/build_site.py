#!/usr/bin/env python3
"""Build the static site: 3 variations x 5 pages x 2 locales, from one template set.

Everything the browser downloads is produced here and committed, so GitHub Pages
serves the repository directly — no CI step, no server-side build.

URL layout
    /                       variation 1, Ukrainian   (the indexed site)
    /about/ /services/ /blog/ /contacts/
    /v2/ …                  variation 2
    /v3/ …                  variation 3
    /en/ … /en/v2/ … /en/v3/ …
    /variants.html          chooser page, for showing the three side by side

Variations 2 and 3 are marked noindex: they are the same content in a different
layout, and three indexed copies of one company's site would be duplicate
content competing with each other. They stay crawlable (follow) so the chooser
page still passes link equity.

    python3 tools/build_site.py
"""
import datetime
import json
import os
import posixpath
import re
import sys

import rcssmin
import rjsmin
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://xxxquide.github.io/Agro-Site/"
SUBPATH = "/Agro-Site/"
BUILD_YEAR = 2026
BUILD_DATE = "2026-08-06"

CSS_PARTS = [
    "assets/css/fonts.css",
    "src/css/01-tokens.css",
    "src/css/02-base.css",
    "src/css/03-components.css",
    "src/css/04-sections.css",
    "src/css/05-motion.css",
    "src/css/06-responsive.css",
    "src/css/07-variants.css",
]

LOCALES = [("uk", ""), ("en", "en/")]
GEO_IMGS = ["ops-elevator", "crop-wheat", "crop-corn"]
# Dispatch radar (capacity card 03). Positions are authored directly in the
# widget's 400x220 viewBox and mirrored as percentages for the HTML labels, so
# the SVG geometry and the pills cannot drift apart.
#
# The previous widget orbited its labels around a hub, which failed twice over:
# revolving text is unreadable, and the hub was the only in-flow child of a grid
# whose other children were absolutely positioned, so it was placed in an
# implicit second row and sat 59px below the rings it was supposed to centre.
# Here the hub is absolutely centred and every label is static.
RADAR_CX, RADAR_CY = 200.0, 110.0
RADAR = [
    {"x": 120.0, "y": 48.0, "side": "l", "d": 6.5},
    {"x": 280.0, "y": 48.0, "side": "r", "d": 8.0},
    {"x": 296.0, "y": 172.0, "side": "r", "d": 7.2},
    {"x": 104.0, "y": 172.0, "side": "l", "d": 9.0},
]
for _n in RADAR:
    _n["left"] = round(_n["x"] / 4.0, 2)   # 400 wide  -> percent
    _n["top"] = round(_n["y"] / 2.2, 2)    # 220 tall  -> percent

DECIMAL = ","


NBSP = "\u00a0"


def protect_numbers(html):
    """Bind grouped digits with a no-break space.

    Ukrainian groups thousands with a space, so "14 200" is two tokens and the
    line-breaker will happily split it — which it did, mid-headline. Applied to
    the rendered HTML so every locale and every template benefits, and guarded
    to skip anything inside a tag.
    """
    def fix(chunk):
        prev = None
        while prev != chunk:
            prev = chunk
            chunk = re.sub(r"(\d)\s(\d{3})(?!\d)", r"\1" + NBSP + r"\2", chunk)
        return chunk

    out, last = [], 0
    for m in re.finditer(r"<[^>]+>", html):
        out.append(fix(html[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(fix(html[last:]))
    return "".join(out)


def parse_measure(text, thousands, decimal):
    """Split "4 800 га" into (4800.0, "га", "4 800").

    The crop pages want the area, yield and gross figures as counter-animated
    stat cards, and a counter needs a number. Carrying a second numeric copy of
    each figure in the content would mean the owner updating "4 800 га" and 4800
    in step forever, so the number is read back out of the string the crops
    section already publishes — one source of truth, and locale-aware because uk
    groups thousands with a space and en with a comma.

    Returns None when the string is not a measurement, so a caller can fail
    loudly rather than render a zero.
    """
    # The numeric run has to both start and end on a digit, so a separator counts
    # as part of the number only when digits follow it. A lazier pattern stopped
    # at the first separator and read "6,4 т/га" as 6 with a unit of ",4 т/га" —
    # which is worse than failing, because it renders a plausible wrong figure.
    match = re.match(r"^\s*(\d[\d\s.,\u00a0\u2009\u202f]*\d|\d)\s*(.*)$", text or "")
    if not match:
        return None
    digits = match.group(1).strip()
    unit = match.group(2).strip()
    # Strip every kind of space, not only U+0020: the separator is a plain space
    # in the source, but protect_numbers() rewrites it to U+00A0 on the way to
    # the page, and this helper should read a figure from either side of that.
    normalised = re.sub(r"[\s\u00a0\u2009\u202f]", "", digits)
    if thousands.strip():
        normalised = normalised.replace(thousands, "")
    if decimal != ".":
        normalised = normalised.replace(decimal, ".")
    try:
        value = float(normalised)
    except ValueError:
        return None
    return value, unit, digits


def crop_figures(c, item, thousands, decimal):
    """The three headline numbers of a crop page, as stat_card inputs.

    `display` is set only where the figure is fractional: the shared counter
    rounds as it animates (Math.round on every frame), so 6,4 t/ha would count up
    to 6. Those cards print the authored string instead of animating, which is
    also the honest reading — a yield is a measurement, not a tally.
    """
    labels = c["crops"]["spec_labels"]
    out = []
    for key, label_key in (("area", "area"), ("yield", "yield"), ("volume", "volume")):
        parsed = parse_measure(item[key], thousands, decimal)
        if parsed is None:
            raise SystemExit(f'FATAL: cannot read a number out of crops."{key}" '
                             f'= {item[key]!r} for {item["name"]!r}.')
        value, unit, digits = parsed
        out.append({
            "value": value,
            "suffix": unit,
            "label": labels[label_key],
            "display": None if float(value).is_integer() else digits,
        })
    return out


def rel(*parts):
    return os.path.join(ROOT, *parts)


def read(path):
    with open(rel(path), encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    full = rel(path)
    os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)
    return len(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# assets
# ---------------------------------------------------------------------------

def build_css():
    raw = "\n".join(read(p) for p in CSS_PARTS)
    return len(raw.encode()), write("assets/css/main.css", rcssmin.cssmin(raw))


def build_js():
    raw = read("src/js/app.js")
    return len(raw.encode()), write("assets/js/app.js", rjsmin.jsmin(raw))


# ---------------------------------------------------------------------------
# helpers handed to the templates
# ---------------------------------------------------------------------------

def make_srcset(imgs, prefix):
    def srcset(name, ext):
        m = imgs[name]
        return ", ".join(
            f"{prefix}assets/img/{name}-{w}.{ext} {w}w" for w in m["widths"]
        )
    return srcset


def fan_transforms(n):
    """Per-card 3D placement for the hero fan.

    rotateZ is kept small (max ~1.5deg): at 4deg the small cards read as
    accidentally skewed rather than fanned, which is what "слегка криво" meant.
    The arc now comes from rotateY and depth instead.
    """
    mid = (n - 1) / 2
    out = []
    for i in range(n):
        a = i - mid
        d = abs(a)
        out.append({
            "ry": round(-a * 9.5, 2),
            "rz": round(a * 0.5, 2),
            "ty": round(d * d * 4.0 + d * 4.6, 1),
            "tz": round(-d * 30, 1),
            "sc": round(1 - d * 0.016, 3),
            "z": n - int(d * 2),
        })
    return out


ICON_CHIP = {
    "leaf":      ("lime", "M20 4.5c0 8-4.7 12.4-10 12.4a5 5 0 0 1-5-5C5 6.6 11.6 4.5 20 4.5Z"),
    "grain":     ("sky",  "M8.4 4.8v8.4M15.6 10.8v8.4"),
    "shield":    ("ink",  "M12 3.5 5.5 6v5.4c0 4 2.7 7.4 6.5 9.1 3.8-1.7 6.5-5.1 6.5-9.1V6Z"),
    "handshake": ("lime", "m3.5 12.5 3.4-3.4a2 2 0 0 1 2.8 0l1.1 1.1a1.6 1.6 0 0 0 2.3 0"),
    "route":     ("sky",  "M6 8.4v3.4a3.6 3.6 0 0 0 3.6 3.6h4.8"),
    "drone":     ("sky",  "M9.5 9.5h5v5h-5zM9.5 10.5 6 7m8.5 3.5L18 7m-8.5 6.5L6 17m8.5-3.5L18 17"),
    "sun":       ("lime", "M12 6.8a5.2 5.2 0 1 0 0 10.4 5.2 5.2 0 0 0 0-10.4ZM12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2"),
}


def iconic(text):
    """Render [[icon]] markers inside a heading as inline coloured discs.

    The template drops small coloured chips into the middle of a display line;
    it is one of its most recognisable moves and it breaks up an otherwise long
    heading. Markers live in the content JSON so both locales stay in sync.
    """
    def sub(m):
        tone, path = ICON_CHIP.get(m.group(1), ("lime", ""))
        cls = "ichip icon-badge icon-badge--inline" + ("" if tone == "lime" else f" ichip--{tone}")
        return (f'<span class="{cls}" aria-hidden="true">'
                f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
                f'<path d="{path}"/></svg></span>')
    return Markup(re.sub(r"\[\[([a-z]+)\]\]", sub, escape(text)))


def chart_builder():
    """Bars scale between the series min and max rather than from zero: with a
    0-baseline a 4.9 -> 6.4 t/ha spread is visually flat. Every exact value is
    printed above its bar, so nothing is concealed by the choice."""
    def chart_html(series, big=False):
        vals = [s["v"] for s in series]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1
        cols, years = [], []
        for s in series:
            pct = 42 + 58 * (s["v"] - lo) / span
            cls = "chart__col"
            peak = s["v"] == hi
            dip = s["v"] == lo
            if peak:
                cls += " chart__col--peak"
            elif dip:
                cls += " chart__col--dip"
            label = f'{s["v"]:.1f}'.replace(".", DECIMAL)
            # In the large chart only the record and the bad year are called
            # out; printing all five turns the reference's clean axis into a
            # wall of numbers. The rest surface on hover.
            val = f'<span class="chart__val">{label}</span>'
            if big and not (peak or dip):
                val = f'<span class="chart__val chart__val--quiet">{label}</span>'
            cols.append(
                f'<div class="{cls}" style="--h:{pct:.1f}%">'
                f'{val}<span class="chart__fill"></span></div>'
            )
            years.append(f"<span>{s['year']}</span>")
        grid = '<span class="chart__grid" aria-hidden="true"><i></i><i></i><i></i><i></i></span>'
        return Markup(
            '<div class="chart' + (' chart--big' if big else '')
            + '"><div class="chart__plot">' + grid + "".join(cols)
            + '</div><div class="chart__years">' + "".join(years) + "</div></div>"
        )
    return chart_html


# ---------------------------------------------------------------------------
# per-page SEO copy
# ---------------------------------------------------------------------------

def page_seo(c, page_id, variant):
    brand = c["brand"]["name"]
    if page_id == "home":
        return {
            "title": c["seo"]["title"],
            "description": c["seo"]["description"],
            "keywords": c["seo"]["keywords"],
            "og_title": c["seo"]["og_title"],
            "og_description": c["seo"]["og_description"],
        }
    # A page lead is written for the page, not for a search result, so several
    # are too short to be useful as a description. Extend them from the page's
    # own data rather than authoring a second set of strings per locale.
    joiner = " · "
    src = {
        "about":    (c["about"]["title"], c["about"]["lead"]),
        "services": (c["services"]["title"], c["services"]["lead"] + " "
                     + joiner.join(i["title"] for i in c["services"]["items"][:4])),
        "blog":     (c["blog_page"]["title"], c["blog_page"]["lead"] + " "
                     + joiner.join(pt["tag"] for pt in c["blog_page"]["posts"][:5])),
        "contacts": (c["contact_page"]["title"], c["contact_page"]["lead"]),
    }[page_id]
    title = f"{src[0]} — {brand}"
    desc = " ".join(src[1].split())
    if len(desc) > 165:
        desc = desc[:162].rsplit(" ", 1)[0] + "…"
    return {"title": title, "description": desc, "keywords": None,
            "og_title": src[0], "og_description": desc}


def detail_seo(c, item, kind):
    brand = c["brand"]["name"]
    if kind == "article":
        title = item.get("seo_title", item["title"])
        description = item.get("seo_description", item["excerpt"])
    elif kind == "crop":
        # A crop page is a commercial landing page, so its title and description
        # are authored for the search result and not derived from the page lead.
        title = item["seo_title"]
        description = item["seo_description"]
    else:
        title = f'{item["name"]} — {item["role"]}'
        description = item["intro"]
    description = " ".join(description.split())
    if len(description) > 165:
        description = description[:162].rsplit(" ", 1)[0] + "…"
    return {
        "title": f"{title} — {brand}", "description": description,
        "keywords": None, "og_title": title, "og_description": description,
    }


def build_jsonld(c, lang, canonical, page_id, seo, entity=None, crumbs=None):
    org_id = BASE + "#org"
    addr = {
        "@type": "PostalAddress",
        "streetAddress": "вул. Зарічна, 4" if lang == "uk" else "4 Zarichna St",
        "addressLocality": "Сорока" if lang == "uk" else "Soroka",
        "addressRegion": "Вінницька область" if lang == "uk" else "Vinnytsia region",
        "postalCode": "22731",
        "addressCountry": "UA",
    }

    org = {
        "@type": "Organization", "@id": org_id,
        "name": c["brand"]["name"], "legalName": c["brand"]["legal"],
        "url": BASE,
        "logo": {"@type": "ImageObject", "url": BASE + "assets/icons/logo-lockup.png",
                 "width": 1120, "height": 280},
        "image": BASE + f"assets/img/og-{lang}.jpg",
        "description": c["seo"]["description"],
        "foundingDate": "2008",
        "email": c["contact"]["email"], "telephone": c["contact"]["phone"],
        "address": addr,
        "areaServed": {"@type": "Country", "name": "Ukraine"},
        "knowsLanguage": ["uk", "en"],
        "naics": "111140",
        "numberOfEmployees": {"@type": "QuantitativeValue", "value": 240},
        "hasOfferCatalog": {
            "@type": "OfferCatalog", "name": c["crops"]["title"],
            "itemListElement": [
                {"@type": "Offer",
                 "itemOffered": {"@type": "Product", "name": cr["name"],
                                 "description": cr["text"],
                                 "image": BASE + f'assets/img/{cr["img"]}-1120.webp'},
                 "availability": "https://schema.org/InStock"}
                for cr in c["crops"]["items"]
            ],
        },
        "employee": [
            {"@type": "Person", "name": m["name"], "jobTitle": m["role"]}
            for m in c["team"]["items"]
        ],
    }

    place = {
        "@type": "LocalBusiness", "@id": BASE + "#place",
        "name": c["brand"]["name"], "parentOrganization": {"@id": org_id},
        "image": BASE + f"assets/img/og-{lang}.jpg",
        "address": addr,
        "geo": {"@type": "GeoCoordinates", "latitude": 49.0716, "longitude": 29.3608},
        "telephone": c["contact"]["phone"], "email": c["contact"]["email"],
        "url": BASE,
        "openingHoursSpecification": [{
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "opens": "08:00", "closes": "18:00",
        }],
    }

    site = {"@type": "WebSite", "@id": BASE + "#site", "url": BASE,
            "name": c["brand"]["name"], "publisher": {"@id": org_id},
            "inLanguage": ["uk", "en"]}

    page_type = {"home": "WebPage", "about": "AboutPage", "services": "WebPage",
                 "blog": "CollectionPage", "contacts": "ContactPage",
                 "article": "WebPage", "profile": "ProfilePage",
                 "crop": "ItemPage", "privacy": "WebPage", "terms": "WebPage"}[page_id]
    page = {
        "@type": page_type, "@id": canonical + "#page", "url": canonical,
        "name": seo["title"], "description": seo["description"],
        "isPartOf": {"@id": BASE + "#site"}, "about": {"@id": org_id},
        "inLanguage": lang,
        "primaryImageOfPage": {"@type": "ImageObject",
                               "url": BASE + "assets/img/hero-v1-1920.webp"},
    }

    graph = [org, place, site, page]

    # BreadcrumbList is the one rich result Google still renders for a site like
    # this one — it replaces the bare URL in the result with a navigation path.
    # Every page had zero. The trail is handed in from main(), built from the same
    # page table url_for() uses, so it cannot drift from the real link structure.
    if crumbs:
        graph.append({
            "@type": "BreadcrumbList", "@id": canonical + "#crumbs",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": name,
                 "item": url}
                for i, (name, url) in enumerate(crumbs)
            ],
        })

    if page_id in ("home", "services", "contacts"):
        graph.append({
            "@type": "FAQPage", "@id": canonical + "#faq",
            "isPartOf": {"@id": canonical + "#page"}, "inLanguage": lang,
            "mainEntity": [
                {"@type": "Question", "name": q["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": q["a"]}}
                for q in c["faq"]["items"]
            ],
        })

    if page_id == "blog":
        graph.append({
            "@type": "ItemList", "@id": canonical + "#posts",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "item": {"@type": "BlogPosting", "headline": post["title"],
                          "datePublished": post["iso"],
                          "description": post["excerpt"],
                          "image": BASE + f'assets/img/{post["img"]}-880.webp',
                          "author": {"@id": org_id},
                          "publisher": {"@id": org_id}}}
                for i, post in enumerate(c["blog_page"]["posts"])
            ],
        })

    if page_id == "about":
        graph.append({
            "@type": "ItemList", "@id": canonical + "#milestones",
            "name": c["journey"]["title"],
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "name": f'{m["year"]} — {m["title"]}'}
                for i, m in enumerate(c["journey"]["items"])
            ],
        })

    if page_id == "article" and entity:
        article = {
            "@type": "Article", "@id": canonical + "#article",
            "headline": entity["title"], "description": entity["excerpt"],
            "datePublished": entity["iso"], "dateModified": entity["iso"],
            "mainEntityOfPage": {"@id": canonical + "#page"},
            "image": BASE + f'assets/img/{entity["img"]}-880.webp',
            "author": {"@id": org_id}, "publisher": {"@id": org_id},
            "inLanguage": lang,
        }
        graph.append(article)
        page["mainEntity"] = {"@id": article["@id"]}
        page["primaryImageOfPage"] = {"@type": "ImageObject", "url": article["image"]}

    if page_id == "crop" and entity:
        # additionalProperty is the substance here: moisture, protein, test
        # weight and falling number stop being prose and become machine-readable
        # against the product they describe. No price — the site publishes none,
        # and an Offer without one is still valid in a catalogue.
        product = {
            "@type": "Product", "@id": canonical + "#product",
            "name": entity["name"], "description": entity["seo_description"],
            "image": BASE + f'assets/img/{entity["img"]}-1120.webp',
            "url": canonical,
            "brand": {"@id": org_id},
            "category": c["crops"]["title"],
            "additionalProperty": [
                {"@type": "PropertyValue", "name": spec["k"], "value": spec["v"]}
                for spec in entity["specs"] + entity["specs_extra"]
            ],
            "offers": {
                "@type": "Offer",
                "availability": "https://schema.org/InStock",
                "seller": {"@id": org_id},
                "areaServed": {"@type": "Country", "name": "Ukraine"},
                "url": canonical,
            },
        }
        graph.append(product)
        page["mainEntity"] = {"@id": product["@id"]}
        page["primaryImageOfPage"] = {"@type": "ImageObject", "url": product["image"]}

    if page_id == "profile" and entity:
        person = {
            "@type": "Person", "@id": canonical + "#person",
            "name": entity["name"], "jobTitle": entity["role"],
            "description": entity["intro"],
            "image": BASE + f'assets/img/{entity["img"]}-840.webp',
            "worksFor": {"@id": org_id}, "knowsLanguage": ["uk", "en"],
        }
        graph.append(person)
        page["mainEntity"] = {"@id": person["@id"]}
        page["primaryImageOfPage"] = {"@type": "ImageObject", "url": person["image"]}

    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# side files
# ---------------------------------------------------------------------------

def build_side_files(uk, indexed_urls):
    write(".nojekyll", "")
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n")

    urls = []
    for loc, lang in indexed_urls:
        alts = "".join(
            f'\n    <xhtml:link rel="alternate" hreflang="{l}" href="{u}"/>'
            for l, u in indexed_urls_alt(loc, lang, indexed_urls)
        )
        urls.append(
            f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{BUILD_DATE}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{'1.0' if loc == BASE else '0.8'}</priority>{alts}
  </url>"""
        )

    write("sitemap.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
{chr(10).join(urls)}
</urlset>
""")

    write("site.webmanifest", json.dumps({
        "name": uk["brand"]["legal"], "short_name": uk["brand"]["word_1"],
        "description": uk["seo"]["description"],
        "start_url": SUBPATH, "scope": SUBPATH, "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#131313",
        "lang": "uk", "dir": "ltr",
        "icons": [
            {"src": SUBPATH + "assets/icons/favicon-32.png", "sizes": "32x32", "type": "image/png"},
            {"src": SUBPATH + "assets/icons/favicon-96.png", "sizes": "96x96", "type": "image/png"},
            {"src": SUBPATH + "assets/icons/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
            {"src": SUBPATH + "assets/icons/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }, ensure_ascii=False, indent=1))


def section_url(lang_prefix, vslug, page_file):
    """Absolute URL of a page from the same table url_for() reads."""
    tail = posixpath.dirname(f"{lang_prefix}{vslug}{page_file}")
    return BASE + (tail + "/" if tail else "")


def build_crumbs(c, lang_prefix, vslug, page_files, page_id, item=None):
    """Home -> section -> page, as (name, absolute url) pairs.

    Derived, never hardcoded: the section label comes from the same nav table the
    header renders and the URL from the same page table url_for() resolves, so a
    renamed page or a moved file cannot leave a stale trail behind. Returns an
    empty list for the home page, which is the root and has nothing to show.
    """
    if page_id == "home" and item is None:
        return []
    nav_labels = {i["page"]: i["label"] for i in c["nav_pages"]["items"]}
    trail = [(c["detail_labels"]["crumb_home"],
              section_url(lang_prefix, vslug, page_files["home"]))]
    if page_id != "home":
        trail.append((nav_labels.get(page_id, page_id),
                      section_url(lang_prefix, vslug, page_files[page_id])))
    if item is not None:
        trail.append((item.get("name") or item["title"], None))
    return trail


def indexed_urls_alt(loc, lang, all_urls):
    """hreflang pairs for one URL: the same page in the other locale."""
    tail = loc[len(BASE):]
    if tail.startswith("en/"):
        uk_tail, en_tail = tail[3:], tail
    else:
        uk_tail, en_tail = tail, "en/" + tail
    return [("uk", BASE + uk_tail), ("en", BASE + en_tail),
            ("x-default", BASE + uk_tail)]


def build_404(uk):
    mark = read("assets/icons/favicon.svg").split(">", 1)[1].rsplit("</svg>", 1)[0]
    return write("404.html", f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Сторінку не знайдено — {uk["brand"]["name"]}</title>
<meta name="robots" content="noindex, follow">
<link rel="icon" href="{SUBPATH}assets/icons/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{SUBPATH}assets/css/main.css">
<style>
.nf{{min-height:100svh;display:grid;place-items:center;text-align:center;padding:2rem}}
.nf__in{{display:flex;flex-direction:column;align-items:center;gap:1.25rem;max-width:34rem}}
</style>
</head>
<body>
<main class="nf">
  <div class="nf__in">
    <svg width="56" height="56" viewBox="0 0 48 48" aria-hidden="true">{mark}</svg>
    <p class="tag tag--lime">404 — NOT FOUND</p>
    <h1>Такої сторінки немає</h1>
    <p class="lead">Можливо, посилання застаріло. Повернімося на головну — там усе про наші культури, потужності та умови співпраці.</p>
    <a class="btn" href="{SUBPATH}">На головну<span class="btn__badge"><svg viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M2.5 9.5 9.5 2.5M9.5 2.5H4.2M9.5 2.5v5.3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span></a>
  </div>
</main>
</body>
</html>
""")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    global DECIMAL

    with open(rel("assets/img/manifest.json"), encoding="utf-8") as fh:
        imgs = json.load(fh)
    with open(rel("content/variants.json"), encoding="utf-8") as fh:
        vcfg = json.load(fh)
    content = {}
    for lang, _ in LOCALES:
        with open(rel("content", f"{lang}.json"), encoding="utf-8") as fh:
            content[lang] = json.load(fh)

    logo_inner = read("assets/icons/logo-mark.svg").split(">", 1)[1].rsplit("</svg>", 1)[0]

    env = Environment(
        loader=FileSystemLoader(rel("templates")),
        undefined=StrictUndefined, lstrip_blocks=True, autoescape=True,
    )

    css_raw, css_min = build_css()
    js_raw, js_min = build_js()
    chart_html = chart_builder()

    variants = vcfg["variants"]
    pages = vcfg["pages"]
    page_files = {pg["id"]: pg["file"] for pg in pages}

    written = []
    indexed = []

    for V in variants:
        for lang, lang_prefix in LOCALES:
            c = content[lang]
            DECIMAL = "," if lang == "uk" else "."
            thousands = " " if lang == "uk" else ","

            for pg in pages:
                out_path = f"{lang_prefix}{V['slug']}{pg['file']}"
                page_dir = posixpath.dirname(out_path)
                depth = len([s for s in page_dir.split("/") if s])
                prefix = "../" * depth

                def url_for(target, _dir=page_dir, _lp=lang_prefix, _v=V):
                    tgt_dir = posixpath.dirname(f"{_lp}{_v['slug']}{page_files[target]}")
                    r = posixpath.relpath(tgt_dir or ".", _dir or ".")
                    return "./" if r == "." else r + "/"

                def article_url(slug, _dir=page_dir, _lp=lang_prefix, _v=V):
                    target = f'{_lp}{_v["slug"]}blog/{slug}'
                    r = posixpath.relpath(target, _dir or ".")
                    return "./" if r == "." else r + "/"

                def profile_url(slug, _dir=page_dir, _lp=lang_prefix, _v=V):
                    target = f'{_lp}{_v["slug"]}about/team/{slug}'
                    r = posixpath.relpath(target, _dir or ".")
                    return "./" if r == "." else r + "/"

                def crop_url(slug, _dir=page_dir, _lp=lang_prefix, _v=V):
                    target = f'{_lp}{_v["slug"]}services/{slug}'
                    r = posixpath.relpath(target, _dir or ".")
                    return "./" if r == "." else r + "/"

                canonical = BASE + posixpath.dirname(out_path)
                canonical = canonical.rstrip("/") + "/" if posixpath.dirname(out_path) else BASE
                seo = page_seo(c, pg["id"], V)

                # hreflang partners: same variation, same page, other locale
                uk_url = BASE + (posixpath.dirname(f"{V['slug']}{pg['file']}") + "/"
                                 if posixpath.dirname(f"{V['slug']}{pg['file']}") else "")
                en_url = BASE + posixpath.dirname(f"en/{V['slug']}{pg['file']}") + "/"

                other_out = f"{'en/' if lang == 'uk' else ''}{V['slug']}{pg['file']}"
                other_rel = posixpath.relpath(posixpath.dirname(other_out) or ".",
                                              page_dir or ".")
                other_rel = "./" if other_rel == "." else other_rel + "/"

                noindex = (V["id"] != "v1")
                if not noindex:
                    indexed.append((canonical, lang))

                variants_rel = posixpath.relpath("variants.html", page_dir or ".")

                html = env.get_template(f"pages/{pg['id']}.html.j2").render(
                    c=c, V=V, p=prefix, imgs=imgs,
                    base=BASE, canonical=canonical, seo=seo, noindex=noindex,
                    page_id=pg["id"], year=BUILD_YEAR,
                    logo_mark=Markup(logo_inner),
                    srcset=make_srcset(imgs, prefix),
                    chart_html=chart_html,
                    iconic=iconic,
                    fan=fan_transforms(len(c["hero"]["cards"])),
                    radar=RADAR, radar_c=(RADAR_CX, RADAR_CY), geo_imgs=GEO_IMGS,
                    fmt_num=lambda n, _t=thousands: f"{n:,}".replace(",", _t),
                    ha="га" if lang == "uk" else "ha",
                    tel="+" + re.sub(r"\D", "", c["contact"]["phone"]),
                    url_for=url_for, article_url=article_url, profile_url=profile_url,
                    crop_url=crop_url,
                    alt_uk=uk_url, alt_en=en_url,
                    alt_uk_rel=(other_rel if lang == "en" else "./"),
                    alt_en_rel=(other_rel if lang == "uk" else "./"),
                    hero_img=(V["hero_img"] if pg["id"] == "home" else None),
                    light_header=(pg["id"] != "home"),
                    variants_url=variants_rel,
                    variant_switch_label=(V["label"] if lang == "uk" else V["label_en"]),
                    jsonld=Markup(build_jsonld(
                        c, lang, canonical, pg["id"], seo,
                        crumbs=[(n, u or canonical) for n, u in build_crumbs(
                            c, lang_prefix, V["slug"], page_files, pg["id"])])),
                )
                html = protect_numbers(html)
                html = re.sub(r"\n{3,}", "\n\n", html)
                written.append((out_path, write(out_path, html)))

            # Article and team detail pages use the same shared shell and art
            # direction as their parent variation. They are generated from the
            # locale JSON, never copied by hand.
            for kind, items, parent_id, folder, template_name in [
                ("article", c["blog_page"]["posts"], "blog", "blog", "article"),
                ("profile", c["team"]["items"], "about", "about/team", "profile"),
                # Crops sit one level under services, the same depth as an article
                # under blog, so nothing around this loop needs to change.
                ("crop", c["crops"]["items"], "services", "services", "crop"),
            ]:
                for item in items:
                    detail_file = f'{folder}/{item["slug"]}/index.html'
                    out_path = f"{lang_prefix}{V['slug']}{detail_file}"
                    page_dir = posixpath.dirname(out_path)
                    depth = len([s for s in page_dir.split("/") if s])
                    prefix = "../" * depth

                    def detail_url_for(target, _dir=page_dir, _lp=lang_prefix, _v=V):
                        tgt_dir = posixpath.dirname(f"{_lp}{_v['slug']}{page_files[target]}")
                        r = posixpath.relpath(tgt_dir or ".", _dir or ".")
                        return "./" if r == "." else r + "/"

                    def article_url(slug, _dir=page_dir, _lp=lang_prefix, _v=V):
                        target = f'{_lp}{_v["slug"]}blog/{slug}'
                        r = posixpath.relpath(target, _dir or ".")
                        return "./" if r == "." else r + "/"

                    def profile_url(slug, _dir=page_dir, _lp=lang_prefix, _v=V):
                        target = f'{_lp}{_v["slug"]}about/team/{slug}'
                        r = posixpath.relpath(target, _dir or ".")
                        return "./" if r == "." else r + "/"

                    def crop_url(slug, _dir=page_dir, _lp=lang_prefix, _v=V):
                        target = f'{_lp}{_v["slug"]}services/{slug}'
                        r = posixpath.relpath(target, _dir or ".")
                        return "./" if r == "." else r + "/"

                    canonical = BASE + posixpath.dirname(out_path).rstrip("/") + "/"
                    seo = detail_seo(c, item, kind)
                    uk_url = BASE + f'{V["slug"]}{folder}/{item["slug"]}/'
                    en_url = BASE + f'en/{V["slug"]}{folder}/{item["slug"]}/'
                    other_out = f'{"en/" if lang == "uk" else ""}{V["slug"]}{folder}/{item["slug"]}'
                    other_rel = posixpath.relpath(other_out, page_dir or ".")
                    other_rel = "./" if other_rel == "." else other_rel + "/"
                    noindex = (V["id"] != "v1")
                    if not noindex:
                        indexed.append((canonical, lang))

                    if kind == "crop":
                        related = [c["crops"]["items"][i] for i in item["related"]]
                    else:
                        related = [c["blog_page"]["posts"][i] for i in item["related"]]

                    variants_rel = posixpath.relpath("variants.html", page_dir or ".")
                    html = env.get_template(f"pages/{template_name}.html.j2").render(
                        c=c, V=V, p=prefix, imgs=imgs, item=item, related=related,
                        base=BASE, canonical=canonical, seo=seo, noindex=noindex,
                        page_id=parent_id, schema_page_id=kind, year=BUILD_YEAR,
                        logo_mark=Markup(logo_inner), srcset=make_srcset(imgs, prefix),
                        chart_html=chart_html, iconic=iconic,
                        fan=fan_transforms(len(c["hero"]["cards"])),
                        radar=RADAR, radar_c=(RADAR_CX, RADAR_CY), geo_imgs=GEO_IMGS,
                        fmt_num=lambda n, _t=thousands: f"{n:,}".replace(",", _t),
                        ha="га" if lang == "uk" else "ha",
                        tel="+" + re.sub(r"\D", "", c["contact"]["phone"]),
                        url_for=detail_url_for, article_url=article_url,
                        profile_url=profile_url, crop_url=crop_url,
                        figures=(crop_figures(c, item, thousands, DECIMAL)
                                 if kind == "crop" else None),
                        alt_uk=uk_url, alt_en=en_url,
                        alt_uk_rel=(other_rel if lang == "en" else "./"),
                        alt_en_rel=(other_rel if lang == "uk" else "./"),
                        hero_img=None, light_header=True,
                        variants_url=variants_rel,
                        variant_switch_label=(V["label"] if lang == "uk" else V["label_en"]),
                        jsonld=Markup(build_jsonld(
                            c, lang, canonical, kind, seo, item,
                            crumbs=[(n, u or canonical) for n, u in build_crumbs(
                                c, lang_prefix, V["slug"], page_files, parent_id,
                                item)])),
                    )
                    html = protect_numbers(html)
                    html = re.sub(r"\n{3,}", "\n\n", html)
                    written.append((out_path, write(out_path, html)))

    # chooser page
    uk = content["uk"]
    vlist = []
    for V in variants:
        vlist.append({**V, "detail": V["note"], "label": V["label"]})
    chooser = env.get_template("variants.html.j2").render(
        c=uk, variants=vlist, logo_mark=Markup(logo_inner),
        srcset=make_srcset(imgs, ""),
    )
    written.append(("variants.html", write("variants.html", chooser)))

    build_side_files(uk, indexed)
    nf = build_404(uk)

    print("BUILD OK")
    print(f"  css   {css_raw/1024:7.1f} KB -> {css_min/1024:6.1f} KB min")
    print(f"  js    {js_raw/1024:7.1f} KB -> {js_min/1024:6.1f} KB min")
    print(f"  pages {len(written)} html files, {sum(n for _, n in written)/1024:.0f} KB total")
    for path, n in written:
        if path.endswith("index.html") and path.count("/") <= 1 or path == "variants.html":
            print(f"    {path:34s} {n/1024:6.1f} KB")
    print(f"    404.html                           {nf/1024:6.1f} KB")
    print(f"  indexed URLs in sitemap: {len(indexed)} (variations 2 and 3 are noindex)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
