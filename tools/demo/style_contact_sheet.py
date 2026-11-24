# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Build a style contact sheet from same-camera reference/base/head renders."""

from __future__ import annotations

import argparse
import os


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        from PIL import Image, ImageDraw  # type: ignore
    except ImportError as e:
        raise SystemExit(f"Pillow is required for contact sheets: {e}") from e

    ref = Image.open(args.reference).convert("RGB")
    base = Image.open(args.base).convert("RGB")
    head = Image.open(args.head).convert("RGB")
    if not (ref.size == base.size == head.size):
        raise SystemExit("all inputs must have the same size")

    w, h = ref.size
    pad = 8
    label_h = 28
    out = Image.new("RGB", (w * 3 + pad * 4, h + label_h + pad * 2), (28, 30, 36))
    d = ImageDraw.Draw(out)
    cols = [("reference", ref), ("base", base), ("head", head)]
    x = pad
    for label, img in cols:
        out.paste(img, (x, pad + label_h))
        d.text((x + 6, pad + 6), label, fill=(220, 230, 240))
        x += w + pad

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    out.save(args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
