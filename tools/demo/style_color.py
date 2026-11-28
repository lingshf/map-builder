# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""sRGB to CIELAB conversion and CIEDE2000 (kL=kC=kH=1) for the style palette reports."""

from __future__ import annotations

import math

Rgb = tuple[float, float, float]
Lab = tuple[float, float, float]

_POW25_7 = 25**7


def hex_to_rgb(hex_color: str) -> Rgb:
    c = hex_color.strip().lstrip("#")
    if len(c) != 6:
        raise ValueError(f"invalid hex color: {hex_color}")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def srgb_to_lab(rgb: Rgb) -> Lab:
    def to_linear(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = [to_linear(c / 255.0) for c in rgb]
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    xr, yr, zr = x / 0.95047, y / 1.0, z / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = f(xr), f(yr), f(zr)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _hue_degrees(a: float, b: float) -> float:
    if a == 0 and b == 0:
        return 0.0
    angle = math.degrees(math.atan2(b, a))
    return angle + 360 if angle < 0 else angle


def _hue_difference(h1: float, h2: float, chroma_product: float) -> float:
    if chroma_product == 0:
        return 0.0
    diff = h2 - h1
    if abs(diff) <= 180:
        return diff
    return diff - 360 if diff > 180 else diff + 360


def _mean_hue(h1: float, h2: float, chroma_product: float) -> float:
    if chroma_product == 0:
        return h1 + h2
    if abs(h1 - h2) <= 180:
        return (h1 + h2) / 2
    return (h1 + h2 + (360 if h1 + h2 < 360 else -360)) / 2


def delta_e2000(lab1: Lab, lab2: Lab) -> float:
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_bar**7 / (c_bar**7 + _POW25_7))) if c_bar > 0 else 0.0
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p, h2p = _hue_degrees(a1p, b1), _hue_degrees(a2p, b2)
    chroma_product = c1p * c2p

    dlp = l2 - l1
    dcp = c2p - c1p
    dhp = _hue_difference(h1p, h2p, chroma_product)
    dh_term = 2 * math.sqrt(chroma_product) * math.sin(math.radians(dhp / 2))
    l_bar = (l1 + l2) / 2
    c_bar_p = (c1p + c2p) / 2
    h_bar = _mean_hue(h1p, h2p, chroma_product)
    t = (
        1
        - 0.17 * math.cos(math.radians(h_bar - 30))
        + 0.24 * math.cos(math.radians(2 * h_bar))
        + 0.32 * math.cos(math.radians(3 * h_bar + 6))
        - 0.20 * math.cos(math.radians(4 * h_bar - 63))
    )
    sl = 1 + (0.015 * ((l_bar - 50) ** 2)) / math.sqrt(20 + (l_bar - 50) ** 2)
    sc = 1 + 0.045 * c_bar_p
    sh = 1 + 0.015 * c_bar_p * t
    dtheta = 30 * math.exp(-(((h_bar - 275) / 25) ** 2))
    rc = 2 * math.sqrt(c_bar_p**7 / (c_bar_p**7 + _POW25_7)) if c_bar_p > 0 else 0.0
    rt = -math.sin(math.radians(2 * dtheta)) * rc
    return math.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dh_term / sh) ** 2 + rt * (dcp / sc) * (dh_term / sh))


def delta_e2000_rgb(rgb1: Rgb, rgb2: Rgb) -> float:
    return delta_e2000(srgb_to_lab(rgb1), srgb_to_lab(rgb2))
