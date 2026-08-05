#!/usr/bin/env python3
"""Image pipeline: crop to exact ratio, resize to target widths, export AVIF + WebP.

Reads the raw GenerateImage output from /agent/stored_files and writes optimised
derivatives into assets/img/. Deterministic: safe to re-run.
"""
import json
import os
import sys
from PIL import Image

SRC_DIR = "/agent/stored_files"
OUT_DIR = "/agent/workspace/agro/assets/img"

# name, source-id prefix, target aspect (w/h), widths to emit
JOBS = [
    ("hero-field",     "cmsg8o2y90h4w07adyzsbup48", (16, 9),  [960, 1440, 1920]),
    ("cta-field",      "cmsg8ozlp0h0t07adzpwl7mbr", (21, 9),  [1000, 1600]),
    ("about-team",     "cmsg8qjea0hta07adcupcl1mr", (3, 2),   [640, 1280]),

    ("crop-wheat",     "cmsg8o7ob0hhj06adh1tx23oz", (4, 3),   [560, 1120]),
    ("crop-corn",      "cmsg8o9jq0h2v06adus7j7ujk", (4, 3),   [560, 1120]),
    ("crop-sunflower", "cmsg8obos0i1607ad5asax3e7", (4, 3),   [560, 1120]),
    ("crop-soy",       "cmsg8od0f0hm307ad2s1lzcne", (4, 3),   [560, 1120]),
    ("crop-rapeseed",  "cmsg8p1gi0h4n07ad3dz2tjp9", (4, 3),   [560, 1120]),
    ("crop-barley",    "cmsg8p37m0hmu07adp7zc9lg4", (4, 3),   [560, 1120]),
    ("crop-beet",      "cmsg8p5is0heg06adtzsnn8t6", (4, 3),   [560, 1120]),

    ("ops-combine",    "cmsg8p76y0h6g07adxukmithl", (3, 2),   [700, 1400]),
    ("ops-elevator",   "cmsg8p99e0hkd07adgi3ktdkf", (3, 2),   [700, 1400]),
    ("ops-drone",      "cmsg8ptel0h1x07advn1o9yw5", (3, 2),   [700, 1400]),
    ("ops-lab",        "cmsg8pvz20hjp07ada03sy88k", (3, 2),   [700, 1400]),
    ("ops-logistics",  "cmsg8pykj0hl107adbv2zrlb2", (3, 2),   [700, 1400]),
    ("ops-soil",       "cmsg8q0b50hsr07ad5xxao2op", (3, 2),   [632, 1264]),

    ("person-trader",  "cmsg8q2ht0hk707ad7jp7fssw", (1, 1),   [380, 760]),
    ("person-mill",    "cmsg8q4410h7907ad6q1rzhyj", (1, 1),   [380, 760]),
    ("person-feed",    "cmsg8qgv30iq807adt7158gsr", (1, 1),   [380, 760]),

    ("news-drying",    "cmsg8ql9h0hl007adptjboduw", (3, 2),   [440, 880]),
    ("news-harvest",   "cmsg8qnd50i2807ad56swa79h", (3, 2),   [440, 880]),
    ("news-notill",    "cmsg8qp1s0hfw06adbdqheuld", (3, 2),   [440, 880]),
]

# per-family encoder settings — heavier compression where the image is decorative
QUALITY = {
    "hero":   (46, 74),   # (avif, webp)
    "cta":    (44, 72),
    "crop":   (50, 78),
    "ops":    (48, 76),
    "person": (54, 82),
    "news":   (48, 76),
    "about":  (48, 76),
}


def find_src(prefix):
    for f in os.listdir(SRC_DIR):
        if f.startswith(prefix):
            return os.path.join(SRC_DIR, f)
    raise FileNotFoundError(prefix)


def center_crop(im, ratio):
    tw, th = ratio
    target = tw / th
    w, h = im.size
    cur = w / h
    if abs(cur - target) < 0.001:
        return im
    if cur > target:                      # too wide -> trim sides
        new_w = round(h * target)
        left = (w - new_w) // 2
        return im.crop((left, 0, left + new_w, h))
    new_h = round(w / target)             # too tall -> trim top/bottom
    top = (h - new_h) // 2
    return im.crop((0, top, w, top + new_h))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = {}
    total = 0

    for name, prefix, ratio, widths in JOBS:
        family = name.split("-")[0]
        q_avif, q_webp = QUALITY[family]
        im = Image.open(find_src(prefix)).convert("RGB")
        im = center_crop(im, ratio)
        base_w, base_h = im.size

        entry = {"ratio": list(ratio), "widths": [], "files": {}}
        for w in widths:
            if w > base_w:
                print(f"  ! skip {name}@{w} (source only {base_w}px)")
                continue
            h = round(w * ratio[1] / ratio[0])
            resized = im.resize((w, h), Image.LANCZOS)

            for ext, fmt, q in (("avif", "AVIF", q_avif), ("webp", "WEBP", q_webp)):
                path = os.path.join(OUT_DIR, f"{name}-{w}.{ext}")
                if fmt == "AVIF":
                    resized.save(path, format=fmt, quality=q, speed=3)
                else:
                    resized.save(path, format=fmt, quality=q, method=6)
                size = os.path.getsize(path)
                total += size
                entry["files"][f"{w}.{ext}"] = size

            entry["widths"].append(w)
            entry[f"h{w}"] = h

        manifest[name] = entry
        smallest = entry["widths"][0]
        print(f"{name:16s} {base_w}x{base_h} -> {entry['widths']}  "
              f"avif@{smallest}={entry['files'][f'{smallest}.avif']//1024}KB "
              f"webp@{smallest}={entry['files'][f'{smallest}.webp']//1024}KB")

    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    print(f"\nTOTAL image payload: {total/1024/1024:.2f} MB across "
          f"{sum(len(v['files']) for v in manifest.values())} files")


if __name__ == "__main__":
    sys.exit(main())
