#!/usr/bin/env python3
"""Bundle a built page into one self-contained HTML file.

Why this exists: the GitHub integration used to publish this repository cannot
carry binary blobs (verified — `content` is always re-encoded as UTF-8, so a
base64 payload is double-encoded and the file arrives corrupt). A single-file
build with CSS, JS, fonts and images inlined as data URIs therefore doubles as
the shareable preview and as proof the pages render before the raster assets
reach the repository.

Only the 1x variant of each image is inlined; a single-file preview has no use
for multiple densities.

  python3 tools/build_preview.py [page ...]      default: the three home pages
"""
import base64
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PREFERRED = {"hero-v1": 1440, "hero-v2": 1440, "hero-v3": 1440, "cta-field": 1000}
MIME = {".avif": "image/avif", ".webp": "image/webp", ".jpg": "image/jpeg",
        ".png": "image/png", ".woff2": "font/woff2"}

DEFAULT_PAGES = [
    ("index.html", "preview-v1.html"),
    ("v2/index.html", "preview-v2.html"),
    ("v3/index.html", "preview-v3.html"),
]


def data_uri(path):
    ext = os.path.splitext(path)[1]
    with open(path, "rb") as fh:
        blob = fh.read()
    return f"data:{MIME[ext]};base64,{base64.b64encode(blob).decode()}", len(blob)


def inline_css():
    css = open(os.path.join(ROOT, "assets/css/main.css"), encoding="utf-8").read()
    total = 0
    for slug in ("onest", "geistmono"):
        uri, n = data_uri(os.path.join(ROOT, "assets/fonts", f"{slug}.woff2"))
        css = css.replace(f"url('../fonts/{slug}.woff2')", f"url({uri})")
        total += n
    return css, total


def build(page, out_name, imgs):
    src = os.path.join(ROOT, page)
    html = open(src, encoding="utf-8").read()

    # strip things that only make sense on a real origin
    for pat in (r'\n?<link rel="preload"[^>]*>', r'\n?<link rel="icon"[^>]*>',
                r'\n?<link rel="apple-touch-icon"[^>]*>', r'\n?<link rel="manifest"[^>]*>'):
        html = re.sub(pat, "", html)

    img_bytes = [0]

    def repl_picture(m):
        block = m.group(0)
        tag_m = re.search(r"<img\b[^>]*>", block)
        if not tag_m:
            return block
        tag = tag_m.group(0)
        name_m = re.search(r"assets/img/([a-z0-9\-]+)-\d+\.webp", tag)
        if not name_m:
            return tag
        name = name_m.group(1)
        want = PREFERRED.get(name, imgs[name]["widths"][0])
        if want not in imgs[name]["widths"]:
            want = imgs[name]["widths"][0]
        uri, n = data_uri(os.path.join(ROOT, "assets/img", f"{name}-{want}.avif"))
        img_bytes[0] += n
        tag = re.sub(r'\ssrcset="[^"]*"', "", tag)
        tag = re.sub(r'\ssizes="[^"]*"', "", tag)
        return re.sub(r'src="[^"]*"', f'src="{uri}"', tag)

    html = re.sub(r"<picture\b.*?</picture>", repl_picture, html, flags=re.S)

    css, font_bytes = inline_css()
    html = re.sub(r'<link rel="stylesheet" href="[^"]*">', "<style>" + css + "</style>", html)

    # inline every script, vendor libraries included
    js_bytes = 0
    for rel_js in ["assets/js/vendor/gsap.min.js",
                   "assets/js/vendor/ScrollTrigger.min.js",
                   "assets/js/vendor/lenis.min.js",
                   "assets/js/app.js"]:
        code = open(os.path.join(ROOT, rel_js), encoding="utf-8").read()
        js_bytes += len(code)
        html = re.sub(
            r'<script src="[^"]*' + re.escape(os.path.basename(rel_js)) + r'" defer></script>',
            lambda _m, _c=code: "<script>" + _c + "</script>",
            html)

    # inner-page links cannot resolve inside a single file
    html = re.sub(r'href="(?:\.\./)*(?:about|services|blog|contacts)/"', 'href="#main"', html)
    html = re.sub(r'href="(?:\.\./)*variants\.html"', 'href="#main"', html)
    html = re.sub(r'href="(?:\.\./)*(?:en/)?(?:v2/|v3/)?"', 'href="#main"', html)
    html = html.replace('href="./"', 'href="#main"')

    out = os.path.join(ROOT, "build", out_name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"{out_name:20s} {os.path.getsize(out)/1024:7.1f} KB  "
          f"(img {img_bytes[0]/1024:.0f}K, fonts {font_bytes/1024:.0f}K, js {js_bytes/1024:.0f}K)")
    return out


def main():
    with open(os.path.join(ROOT, "assets/img/manifest.json"), encoding="utf-8") as fh:
        imgs = json.load(fh)

    jobs = DEFAULT_PAGES
    if len(sys.argv) > 1:
        jobs = [(a, "preview-" + a.replace("/", "-").replace(".html", "") + ".html")
                for a in sys.argv[1:]]

    for page, out_name in jobs:
        build(page, out_name, imgs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
