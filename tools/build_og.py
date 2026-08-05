#!/usr/bin/env python3
"""Compose the 1200x630 Open Graph cards, one per locale.

Built from the same hero photograph the page uses, so a shared link and the
landing page read as the same thing. Text is rendered with the real Manrope
variable font rather than a system fallback.
"""
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = "/tmp/fontsrc/manrope.ttf"
TTF_URL = ("https://raw.githubusercontent.com/google/fonts/main/ofl/manrope/"
           "Manrope%5Bwght%5D.ttf")
MONO = "/tmp/fontsrc/jbmono.ttf"
MONO_URL = ("https://raw.githubusercontent.com/google/fonts/main/ofl/jetbrainsmono/"
            "JetBrainsMono%5Bwght%5D.ttf")

W, H = 1200, 630
INK = (14, 42, 27)
LIME = (198, 242, 78)
CREAM = (247, 246, 241)
SOFT = (175, 192, 174)

PAD = 72


def ensure(path, url):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        subprocess.run(["curl", "-sSL", "-m", "90", url, "-o", path], check=True)
    return path


def font(path, size, weight):
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def build(lang, c):
    src = Image.open(os.path.join(ROOT, "assets/img/hero-field-1920.webp")).convert("RGB")

    # cover-crop to the card ratio
    scale = max(W / src.width, H / src.height)
    src = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left = (src.width - W) // 2
    top = int((src.height - H) * 0.42)
    img = src.crop((left, top, left + W, top + H))

    # directional scrim: opaque enough on the left for text, opens up on the right
    scrim = Image.new("L", (W, 1))
    for x in range(W):
        t = x / (W - 1)
        a = 242 - 210 * (t ** 1.35)
        scrim.putpixel((x, 0), max(24, int(a)))
    scrim = scrim.resize((W, H))
    img = Image.composite(Image.new("RGB", (W, H), INK), img, scrim)

    d = ImageDraw.Draw(img)
    ttf, mono = ensure(TTF, TTF_URL), ensure(MONO, MONO_URL)

    f_word = font(ttf, 34, 800)
    f_sub = font(mono, 15, 600)
    f_h = font(ttf, 62, 700)
    f_trust = font(mono, 17, 500)
    f_url = font(mono, 16, 500)

    # --- logo mark, reusing the real favicon tile -------------------------
    import cairosvg
    mark_png = "/tmp/og-mark.png"
    cairosvg.svg2png(url=os.path.join(ROOT, "assets/icons/favicon.svg"),
                     write_to=mark_png, output_width=64, output_height=64)
    mark = Image.open(mark_png).convert("RGBA")
    img.paste(mark, (PAD, PAD), mark)

    d.text((PAD + 82, PAD - 2), c["brand"]["word_1"], font=f_word, fill=CREAM)
    d.text((PAD + 84, PAD + 38), c["brand"]["word_2"], font=f_sub, fill=LIME)

    # --- headline ---------------------------------------------------------
    lines = wrap(d, c["seo"]["og_title"], f_h, W - PAD * 2 - 300)
    y = 232
    for ln in lines[:3]:
        d.text((PAD, y), ln, font=f_h, fill=CREAM)
        y += 74

    # --- lime rule + trust line ------------------------------------------
    y += 18
    d.rectangle([PAD, y, PAD + 54, y + 4], fill=LIME)
    d.text((PAD, y + 26), c["hero"]["trust"], font=f_trust, fill=SOFT)

    # --- url ---------------------------------------------------------------
    url = "xxxquide.github.io/Agro-Site" + ("/en" if lang == "en" else "")
    d.text((PAD, H - PAD - 6), url.upper(), font=f_url, fill=(140, 158, 140))

    out = os.path.join(ROOT, f"assets/img/og-{lang}.jpg")
    img.save(out, "JPEG", quality=86, optimize=True, progressive=True)
    print(f"og-{lang}.jpg  {os.path.getsize(out)/1024:5.1f} KB  ({len(lines)} headline lines)")
    return out


def main():
    for lang in ("uk", "en"):
        with open(os.path.join(ROOT, "content", f"{lang}.json"), encoding="utf-8") as fh:
            build(lang, json.load(fh))


if __name__ == "__main__":
    main()
