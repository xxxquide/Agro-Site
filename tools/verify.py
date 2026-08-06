#!/usr/bin/env python3
"""Static checks on the built output. Exits non-zero on any FAIL.

Covers the things that silently rot in a hand-built static site: dangling asset
references, duplicate ids, images without alt or without intrinsic dimensions,
broken heading order, malformed JSON-LD, and payload budgets.
"""
import glob
import gzip
import html as html_lib
import json
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBPATH = "/Agro-Site/"


def discover_pages():
    """Every built HTML page, so adding a variation cannot bypass the checks."""
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in ("src", "templates", "tools", "content",
                                    "build", "docs", "__pycache__", ".git")]
        for fn in filenames:
            if fn.endswith(".html"):
                out.append(os.path.relpath(os.path.join(dirpath, fn), ROOT))
    return sorted(out)


PAGES = discover_pages()

fails, warns = [], []


def fail(msg):
    fails.append(msg)


def warn(msg):
    warns.append(msg)


class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.dupe_ids = [], []
        self.headings = []
        self.imgs = []
        self.refs = []
        self.jsonld = []
        self.labels, self.inputs, self.forms = [], [], []
        self.in_ld = False
        self.h1 = 0
        self.langs = []
        self.buttons_no_text = 0
        self._tagstack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._tagstack.append(tag)

        if "id" in a:
            if a["id"] in self.ids:
                self.dupe_ids.append(a["id"])
            self.ids.append(a["id"])

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(int(tag[1]))
            if tag == "h1":
                self.h1 += 1

        if tag == "img":
            self.imgs.append(a)
            for key in ("src",):
                if key in a:
                    self.refs.append(a[key])
            for key in ("srcset",):
                if key in a:
                    self.refs += [s.strip().split()[0] for s in a[key].split(",") if s.strip()]

        if tag == "source" and "srcset" in a:
            self.refs += [s.strip().split()[0] for s in a["srcset"].split(",") if s.strip()]

        if tag == "a" and "href" in a:
            self.refs.append(a["href"])

        if tag == "link":
            if "href" in a and a.get("rel") not in ("canonical", "alternate"):
                self.refs.append(a["href"])
            if "imagesrcset" in a:
                self.refs += [s.strip().split()[0] for s in a["imagesrcset"].split(",") if s.strip()]

        if tag == "script" and "src" in a:
            self.refs.append(a["src"])
        if tag == "script" and a.get("type") == "application/ld+json":
            self.in_ld = True

        if tag == "label":
            self.labels.append(a.get("for"))
        if tag in ("input", "select", "textarea"):
            self.inputs.append(a)
        if tag == "form":
            self.forms.append(a)

        if tag == "html" and "lang" in a:
            self.langs.append(a["lang"])

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_ld = False
        if self._tagstack:
            self._tagstack.pop()

    def handle_data(self, data):
        if self.in_ld and data.strip():
            self.jsonld.append(data)


def check_page(page):
    path = os.path.join(ROOT, page)
    if not os.path.exists(path):
        return fail(f"{page}: missing")

    html = open(path, encoding="utf-8").read()
    s = Scan()
    s.feed(html)
    tag = page

    # --- ids and dead controls ------------------------------------------
    if 'href="#"' in html:
        fail(f"{tag}: contains dead href=\"#\" control")
    if s.dupe_ids:
        fail(f"{tag}: duplicate id(s) {sorted(set(s.dupe_ids))}")

    # --- headings --------------------------------------------------------
    if s.h1 != 1:
        fail(f"{tag}: expected exactly one <h1>, found {s.h1}")
    prev = 0
    for h in s.headings:
        if prev and h > prev + 1:
            fail(f"{tag}: heading order jumps h{prev} -> h{h}")
            break
        prev = h

    # --- images ----------------------------------------------------------
    for im in s.imgs:
        if "alt" not in im:
            fail(f'{tag}: <img src="{im.get("src", "?")}"> has no alt attribute')
        if not im.get("width") or not im.get("height"):
            fail(f'{tag}: <img src="{im.get("src", "?")}"> missing width/height (CLS risk)')

    # --- dangling references --------------------------------------------
    page_dir = os.path.dirname(path)
    for ref in s.refs:
        if ref.startswith(("http://", "https://", "data:", "#", "mailto:", "tel:")):
            continue
        clean = re.split(r"[?#]", ref, maxsplit=1)[0]
        if not clean:
            continue
        if clean.startswith(SUBPATH):          # domain-absolute, as 404.html needs
            target = os.path.normpath(os.path.join(ROOT, clean[len(SUBPATH):]))
        else:
            target = os.path.normpath(os.path.join(page_dir, clean))
        if not os.path.exists(target):
            fail(f"{tag}: dangling reference -> {ref}")

    # --- labels ----------------------------------------------------------
    for inp in s.inputs:
        iid = inp.get("id")
        if iid and iid not in s.labels:
            fail(f'{tag}: input #{iid} has no <label for>')
        if inp.get("name") in ("email", "contact") and inp.get("type") != "email":
            fail(f'{tag}: email field #{iid or "?"} must use type="email"')
    for form in s.forms:
        if "data-demo-form" in form and "novalidate" in form:
            fail(f"{tag}: demo form disables native validation")

    # --- JSON-LD ---------------------------------------------------------
    if page not in ("404.html", "variants.html"):
        if not s.jsonld:
            fail(f"{tag}: no JSON-LD block")
        for block in s.jsonld:
            try:
                data = json.loads(block)
            except json.JSONDecodeError as e:
                fail(f"{tag}: JSON-LD is not valid JSON — {e}")
                continue
            types = [n.get("@type") for n in data.get("@graph", [])]
            for need in ("Organization", "LocalBusiness", "WebSite"):
                if need not in types:
                    fail(f"{tag}: JSON-LD missing @type {need}")
            page_types = {"WebPage", "AboutPage", "CollectionPage", "ContactPage", "ProfilePage"}
            if not page_types & set(types):
                fail(f"{tag}: JSON-LD has no page-level type {sorted(page_types)}")
            if re.search(r'(^|/)blog/[^/]+/index\.html$', page) and "Article" not in types:
                fail(f"{tag}: article detail page has no Article JSON-LD")
            if "/about/team/" in "/" + page and "Person" not in types:
                fail(f"{tag}: profile detail page has no Person JSON-LD")

        # --- head essentials --------------------------------------------
        for pat, label in [
            (r'<link rel="canonical" href="https://', "canonical"),
            (r'hreflang="uk"', "hreflang uk"),
            (r'hreflang="en"', "hreflang en"),
            (r'hreflang="x-default"', "hreflang x-default"),
            (r'property="og:image"', "og:image"),
            (r'name="twitter:card"', "twitter:card"),
            (r'name="description"', "meta description"),
            (r'rel="manifest"', "manifest"),
        ]:
            if not re.search(pat, html):
                fail(f"{tag}: missing {label}")

        title = re.search(r"<title>(.*?)</title>", html, re.S)
        desc = re.search(r'<meta name="description" content="(.*?)">', html, re.S)
        if title and len(title.group(1)) > 70:
            warn(f"{tag}: <title> is {len(title.group(1))} chars (>70 may be truncated)")
        if desc:
            desc_text = html_lib.unescape(desc.group(1))
            if not (110 <= len(desc_text) <= 165):
                warn(f"{tag}: meta description is {len(desc_text)} chars (aim 110-165)")

    # --- indexability: only variation 1 may be indexed ------------------
    is_variant = page.startswith(("v2/", "v3/", "en/v2/", "en/v3/"))
    robots = re.search(r'<meta name="robots" content="([^"]*)"', html)
    if page not in ("404.html", "variants.html"):
        if is_variant and (not robots or "noindex" not in robots.group(1)):
            fail(f"{tag}: duplicate-layout variation must be noindex")
        if not is_variant and robots and "noindex" in robots.group(1):
            fail(f"{tag}: primary variation must be indexable")

    # --- lazy-loading discipline ----------------------------------------
    eager = [im for im in s.imgs if im.get("loading") != "lazy"]
    if len(eager) > 1:
        warn(f"{tag}: {len(eager)} images are not lazy — only the LCP image should be eager")

    return None


def budgets():
    def gz(path):
        raw = open(path, "rb").read()
        return len(raw), len(gzip.compress(raw, 9))

    print("\n  asset                     raw      gzip")
    print("  " + "-" * 44)
    rows = []
    for rel_path in ["index.html", "en/index.html", "assets/css/main.css",
                     "assets/js/app.js", "assets/fonts/onest.woff2",
                     "assets/fonts/geistmono.woff2",
                     "assets/js/vendor/gsap.min.js",
                     "assets/js/vendor/ScrollTrigger.min.js",
                     "assets/js/vendor/lenis.min.js"]:
        p = os.path.join(ROOT, rel_path)
        if not os.path.exists(p):
            fail(f"budget: {rel_path} missing")
            continue
        raw, g = gz(p)
        rows.append((rel_path, raw, g))
        print(f"  {rel_path:24s} {raw/1024:6.1f}K  {g/1024:6.1f}K")

    lcp = os.path.join(ROOT, "assets/img/hero-v1-1440.avif")
    lcp_sz = os.path.getsize(lcp) if os.path.exists(lcp) else 0
    print(f"  {'hero-v1-1440.avif':24s} {lcp_sz/1024:6.1f}K       —   (LCP)")

    # first-view weight: uk page + css + js + both fonts + hero avif
    keys = {r[0]: r for r in rows}
    first = (
        keys["index.html"][2] + keys["assets/css/main.css"][2]
        + keys["assets/js/app.js"][2]
        + keys["assets/js/vendor/gsap.min.js"][2]
        + keys["assets/js/vendor/ScrollTrigger.min.js"][2]
        + keys["assets/js/vendor/lenis.min.js"][2]
        + keys["assets/fonts/onest.woff2"][1]
        + keys["assets/fonts/geistmono.woff2"][1]
        + lcp_sz
    )
    print(f"\n  FIRST VIEW (gzip html+css+js, fonts, LCP image): {first/1024:.1f} KB")
    # the budget went up deliberately when GSAP + Lenis replaced the hand-rolled
    # reveal layer, in exchange for scroll-linked motion
    if first > 420 * 1024:
        fail(f"budget: first view {first/1024:.0f} KB exceeds 420 KB")

    js_gz = (keys["assets/js/app.js"][2]
             + keys["assets/js/vendor/gsap.min.js"][2]
             + keys["assets/js/vendor/ScrollTrigger.min.js"][2]
             + keys["assets/js/vendor/lenis.min.js"][2])
    if js_gz > 60 * 1024:
        fail(f"budget: JS {js_gz/1024:.1f} KB gzip exceeds 60 KB")

    total_img = sum(os.path.getsize(f) for f in glob.glob(os.path.join(ROOT, "assets/img/*"))
                    if os.path.isfile(f))
    print(f"  repo image payload: {total_img/1024/1024:.2f} MB")
    return first


def check_parity():
    a = json.load(open(os.path.join(ROOT, "content/uk.json"), encoding="utf-8"))
    b = json.load(open(os.path.join(ROOT, "content/en.json"), encoding="utf-8"))

    def shape(o, p=""):
        if isinstance(o, dict):
            out = []
            for k in o:
                out += [f"{p}.{k}"] + shape(o[k], f"{p}.{k}")
            return out
        if isinstance(o, list):
            out = [f"{p}[{len(o)}]"]
            for i, v in enumerate(o):
                out += shape(v, f"{p}[{i}]")
            return out
        return []

    if shape(a) != shape(b):
        diff = set(shape(a)) ^ set(shape(b))
        fail(f"locale parity: {len(diff)} structural differences, e.g. {sorted(diff)[:4]}")


def check_third_party():
    for page in PAGES:
        html = open(os.path.join(ROOT, page), encoding="utf-8").read()
        ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
        bad = [u for u in ext if "xxxquide.github.io" not in u]
        if bad:
            fail(f"{page}: third-party asset request(s) {bad}")


def main():
    if len(PAGES) != 92:
        fail(f"page count: expected 92 generated HTML pages including 404, found {len(PAGES)}")
    article_pages = [p for p in PAGES if re.search(r'(^|/)blog/[^/]+/index\.html$', p)]
    profile_pages = [p for p in PAGES if "/about/team/" in "/" + p]
    if len(article_pages) != 36:
        fail(f"article detail count: expected 36, found {len(article_pages)}")
    if len(profile_pages) != 24:
        fail(f"profile detail count: expected 24, found {len(profile_pages)}")
    for page in PAGES:
        check_page(page)
    check_parity()
    check_third_party()
    budgets()

    print()
    for w in warns:
        print(f"  WARN  {w}")
    for f in fails:
        print(f"  FAIL  {f}")

    if fails:
        print(f"\n{len(fails)} FAIL / {len(warns)} WARN")
        return 1
    print(f"\nALL CHECKS PASSED ({len(warns)} warnings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
