#!/usr/bin/env python3
"""Bundle each built page into one self-contained HTML file.

Why this exists: the GitHub integration used to publish this repository cannot
carry binary blobs (verified — content is always re-encoded as UTF-8, so a
base64 payload is double-encoded and the file is corrupt). A single-file build
with CSS, JS, fonts and images inlined as data URIs therefore doubles as the
shareable preview and as proof the page renders correctly before the raster
assets reach the repository.

Only the 1x variant of each image is inlined; srcset is dropped, since a
single-file preview has no need to serve multiple densities.

  python3 tools/build_preview.py
"""
import base64
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# the LCP image is worth its extra weight; everything else uses the 1x variant
PREFERRED = {"hero-field": 1440, "cta-field": 1000}

MIME = {".avif": "image/avif", ".webp": "image/webp",
        ".jpg": "image/jpeg", ".png": "image/png", ".woff2": "font/woff2"}


def data_uri(path):
    ext = os.path.splitext(path)[1]
    with open(path, "rb") as fh:
        blob = fh.read()
    return f"data:{MIME[ext]};base64,{base64.b64encode(blob).decode()}", len(blob)


def inline_css(prefix_stripped=True):
    css = open(os.path.join(ROOT, "assets/css/main.css"), encoding="utf-8").read()
    total = 0
    for slug in ("manrope", "jbmono"):
        uri, n = data_uri(os.path.join(ROOT, "assets/fonts", f"{slug}.woff2"))
        css = css.replace(f"url('../fonts/{slug}.woff2')", f"url({uri})")
        total += n
    return css, total


def build(page, out_name, sibling_href, imgs):
    src = os.path.join(ROOT, page)
    html = open(src, encoding="utf-8").read()
    page_dir = os.path.dirname(src)

    # --- strip things that only make sense on a real origin ---------------
    html = re.sub(r'\n?<link rel="preload"[^>]*>', "", html)
    html = re.sub(r'\n?<link rel="icon"[^>]*>', "", html)
    html = re.sub(r'\n?<link rel="apple-touch-icon"[^>]*>', "", html)
    html = re.sub(r'\n?<link rel="manifest"[^>]*>', "", html)

    # --- collapse every <picture> to one inlined <img> --------------------
    img_bytes = [0]

    def repl_picture(m):
        block = m.group(0)
        img_tag = re.search(r"<img\b[^>]*>", block)
        if not img_tag:
            return block
        tag = img_tag.group(0)

        name_m = re.search(r"assets/img/([a-z\-]+)-\d+\.webp", tag)
        if not name_m:
            return tag
        name = name_m.group(1)
        want = PREFERRED.get(name, imgs[name]["widths"][0])
        if want not in imgs[name]["widths"]:
            want = imgs[name]["widths"][0]

        path = os.path.join(ROOT, "assets/img", f"{name}-{want}.avif")
        uri, n = data_uri(path)
        img_bytes[0] += n

        tag = re.sub(r'\ssrcset="[^"]*"', "", tag)
        tag = re.sub(r'\ssizes="[^"]*"', "", tag)
        tag = re.sub(r'src="[^"]*"', f'src="{uri}"', tag)
        return tag

    html = re.sub(r"<picture\b.*?</picture>", repl_picture, html, flags=re.S)

    # --- inline the stylesheet and the script -----------------------------
    css, font_bytes = inline_css()
    html = re.sub(
        r'<link rel="stylesheet" href="[^"]*">',
        "<style>" + css + "</style>",
        html,
    )

    js = open(os.path.join(ROOT, "assets/js/app.js"), encoding="utf-8").read()
    html = re.sub(
        r'<script src="[^"]*" defer></script>',
        "<script>" + js + "</script>",
        html,
    )

    # --- point the language switch at the sibling preview -----------------
    if sibling_href:
        html = re.sub(r'href="(?:en/|\.\./)"', f'href="{sibling_href}"', html)
    else:
        html = re.sub(r'href="(?:en/|\.\./)"', 'href="#"', html)

    # anchor-only navigation inside a sandboxed iframe
    html = html.replace('<a class="brand" href="./"', '<a class="brand" href="#main"')
    html = html.replace('<a class="brand" href="../"', '<a class="brand" href="#main"')

    out = os.path.join(ROOT, "build", out_name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)

    size = os.path.getsize(out)
    print(f"{out_name:22s} {size/1024:7.1f} KB "
          f"(images {img_bytes[0]/1024:.0f} KB, fonts {font_bytes/1024:.0f} KB)")
    return out


def main():
    with open(os.path.join(ROOT, "assets/img/manifest.json"), encoding="utf-8") as fh:
        imgs = json.load(fh)

    sibling = sys.argv[1] if len(sys.argv) > 1 else ""
    sibling_uk = sys.argv[2] if len(sys.argv) > 2 else ""

    build("index.html", "preview-uk.html", sibling, imgs)
    build("en/index.html", "preview-en.html", sibling_uk, imgs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
