#!/usr/bin/env python3
"""Render the synthetic label images for the benchmark sample set.

The committed labels.json references sample_0N.png files; this script
deterministically generates them with PIL so the benchmark is reproducible
without committing binary images. Run once before benchmarking:

    python tests/benchdata/make_samples.py
"""

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))

SAMPLES = [
    # (filename, lines, skew_degrees)
    ("sample_01.png", [
        "Good Day Biscuits",
        "Net Wt. 100 g",
        "MRP Rs. 25.00 incl. of all taxes",
        "Mfd: 01/2026",
        "Manufactured by ACME Foods Pvt Ltd",
        "FSSAI Lic. No. 10012345678901",
    ], 0.0),
    ("sample_02.png", [
        "Clinic Plus Shampoo",
        "Net Qty. 340 ml",
        "MRP Rs. 195",
        "Mfd: 03/2026",
        "Marketed by Hindustan Consumer Care Ltd",
    ], 0.0),
    ("sample_03.png", [
        "Swiss Dark Chocolate",
        "Net Wt. 50 g",
        "MRP Rs. 99 incl. of all taxes",
        "Mfd: 11/2025",
        "Country of Origin: Switzerland",
        "FSSAI Lic. No. 10012345678902",
    ], 0.0),
    ("sample_04.png", [
        "Bharat Namkeen Mixture",
        "Net Wt. 500 g",
        "MRP Rs. 75 incl. of all taxes",
        "Mfd: 06/2026",
        "Manufactured by Bharat Snacks Ltd",
    ], 5.0),
]


def _render(lines, out_path, skew_deg=0.0):
    img = Image.new("RGB", (900, 600), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    y = 40
    for line in lines:
        d.text((50, y), line, fill=(0, 0, 0))
        y += 60
    if skew_deg:
        # PIL rotates counter-clockwise for positive angles.
        img = img.rotate(-skew_deg, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    img.save(out_path, format="PNG")
    print(f"[OK] wrote {out_path}")


def main():
    for filename, lines, skew in SAMPLES:
        _render(lines, os.path.join(HERE, filename), skew)


if __name__ == "__main__":
    main()
