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
from markupsafe import Markup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://xxxquide.github.io/Agro-Site/"
SUBPATH = "/Agro-Site/"
BUILD_YEAR = 2026
BUILD_DATE = "2026-08-05"

CSS_PARTS = [
    "assets/css/fonts.css",
    "src/css/01-tokens.css",
    "src/css/02-base.css",
    "src/css/03-components.css",
    "src/css/04-sections.css",
    "src/css/05-motion.css",
    "src/css/06-responsive.css",
]

LOCALES = [("uk", ""), ("en", "en/")]
GEO_IMGS = ["ops-elevator", "crop-wheat", "crop-corn"]
ORBIT = [
    {"a": 22, "r": "30%", "d": 54},
    {"a": 112, "r": "37%", "d": 64},
    {"a": 203, "r": "31%", "d": 48},
    {"a": 292, "r": "38%", "d": 59},
]

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
            if s["v"] == hi:
                cls += " chart__col--peak"
            elif s["v"] == lo:
                cls += " chart__col--dip"
            label = f'{s["v"]:.1f}'.replace(".", DECIMAL)
            cols.append(
                f'<div class="{cls}" style="--h:{pct:.1f}%">'
                f'<span class="chart__val">{label}</span>'
                f'<span class="chart__fill"></span></div>'
            )
            years.append(f"<span>{s['year']}</span>")
        return Markup(
            '<div class="chart"><div class="chart__plot">' + "".join(cols)
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


def build_jsonld(c, lang, canonical, page_id, seo):
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
                 "blog": "CollectionPage", "contacts": "ContactPage"}[page_id]
    page = {
        "@type": page_type, "@id": canonical + "#page", "url": canonical,
        "name": seo["title"], "description": seo["description"],
        "isPartOf": {"@id": BASE + "#site"}, "about": {"@id": org_id},
        "inLanguage": lang,
        "primaryImageOfPage": {"@type": "ImageObject",
                               "url": BASE + "assets/img/hero-v1-1920.webp"},
    }

    graph = [org, place, site, page]

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


def indexed_urls_alt(loc, lang, all_urls):
    """hreflang pairs for one URL: the same page in the other locale."""
    tail = loc[len(BASE):]
    if tail.startswith("en/"):
        uk_tail, en_tail = tail[3:], tail
    else:
        uk_tail, en_tail = tail, "en/" + tail
    return [("uk", BASE + uk_tail), ("en", BASE + en_tail),
            ("x-default", BASE + en_tail)]


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
                    fan=fan_transforms(len(c["hero"]["cards"])),
                    orbit=ORBIT, geo_imgs=GEO_IMGS,
                    fmt_num=lambda n, _t=thousands: f"{n:,}".replace(",", _t),
                    ha="га" if lang == "uk" else "ha",
                    tel="+" + re.sub(r"\D", "", c["contact"]["phone"]),
                    url_for=url_for,
                    alt_uk=uk_url, alt_en=en_url,
                    alt_uk_rel=(other_rel if lang == "en" else "./"),
                    alt_en_rel=(other_rel if lang == "uk" else "./"),
                    hero_img=(V["hero_img"] if pg["id"] == "home" else None),
                    light_header=(pg["id"] != "home"),
                    variants_url=variants_rel,
                    variant_switch_label=(V["label"] if lang == "uk" else V["label_en"]),
                    jsonld=Markup(build_jsonld(c, lang, canonical, pg["id"], seo)),
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
