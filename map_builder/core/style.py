# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5 style palette and colour/material rules.

Classic mode preserves pre-S5 colours and materials. Stylized mode applies the
palette sampled from the reference background art and keeps geometry untouched.
"""

from __future__ import annotations

import colorsys
import hashlib
import math
from collections.abc import Mapping, Sequence
from typing import Literal, cast

StyleMode = Literal["classic", "stylized"]
Rgb = tuple[float, float, float]
Vec3 = tuple[float, float, float]
MaterialSpec = tuple[Rgb, float, float]

CLIFF_MIN_SLOPE_DEG = 35.0
BANK_BAND_M = 6.0
SUN_DIRECTION: Vec3 = (-0.5, -0.6, 0.62)    # towards the sun, map frame (+X east, +Y north, +Z up)
FOLIAGE_LIT_MIN = 0.35                      # Lambert term above which a foliage face is lit
FOLIAGE_SHADOW_MAX = 0.0                    # ... and at or below which it is in shadow
SLOPE_RAMP_FULL_TAN = 0.45                  # slope (rise/run) at which the grass ramp reaches its darkest
SLOPE_RAMP_BRIGHTEST, SLOPE_RAMP_DARKEST = 1.08, 0.90
FACADE_MAX_SATURATION, FACADE_VALUE_RANGE = 0.30, (0.78, 0.97)
ROOF_SATURATION_RANGE, ROOF_VALUE_RANGE = (0.35, 0.65), (0.55, 0.80)
HUE_MIN_SATURATION = 0.05                   # below this a colour counts as grey
TREE_TINT_SCALES = (0.92, 1.0, 1.08)


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _hex_linear(code: str) -> Rgb:
    """A ``#rrggbb`` sRGB swatch of the target look as linear glTF colour."""
    r, g, b = (srgb_to_linear(int(code[k:k + 2], 16) / 255.0) for k in (1, 3, 5))
    return (r, g, b)


def _normalized(v: Vec3) -> Vec3:
    n = math.sqrt(sum(c * c for c in v))
    return (v[0] / n, v[1] / n, v[2] / n)


_SUN = _normalized(SUN_DIRECTION)
_CLIFF_MIN_TAN = math.tan(math.radians(CLIFF_MIN_SLOPE_DEG))
_CLIFF_LIT, _CLIFF_SHADOW = _hex_linear("#d4b590"), _hex_linear("#70828b")
_SAND_BANK = _hex_linear("#f2dcae")
# The renderer lifts and desaturates, so these vertex colours are calibrated against rendered pixels, not the
# target swatches: a material factor and the tone curve sit between the stored colour and what is seen.
_STYLIZED_WATER: Rgb = (0.0, 0.2, 0.55)
_SHALLOW_BAND: Rgb = (0.3, 1.0, 1.0)
_FOOTPATH = _hex_linear("#fdeaa2")
_FOLIAGE_LIT, _FOLIAGE_MID, _FOLIAGE_SHADOW = _hex_linear("#6f934e"), _hex_linear("#39864c"), _hex_linear("#3d6e69")

_CLASSIC_MATERIALS: dict[str, MaterialSpec] = {
    "MB Terrain": ((0.8, 0.8, 0.8), 0.95, 0.0),
    "MB Water": ((0.8, 0.8, 0.8), 0.15, 0.0),
    "MB Facade": ((0.8, 0.8, 0.8), 0.85, 0.0),
    "MB Roof": ((0.8, 0.8, 0.8), 0.7, 0.0),
    "MB Road": ((0.8, 0.8, 0.8), 0.9, 0.0),
    "MB Bark": ((0.8, 0.8, 0.8), 0.9, 0.0),
    "MB Foliage": ((0.8, 0.8, 0.8), 0.8, 0.0),
}

_STYLIZED_MATERIALS: dict[str, MaterialSpec] = {
    "MB Terrain": ((0.94, 0.95, 0.89), 0.98, 0.0),
    "MB Water": ((0.69, 0.84, 0.92), 0.94, 0.0),
    "MB Facade": ((0.91, 0.86, 0.75), 0.98, 0.0),
    "MB Roof": ((0.63, 0.55, 0.46), 0.97, 0.0),
    "MB Road": ((0.90, 0.79, 0.67), 0.99, 0.0),
    "MB Bark": ((0.63, 0.52, 0.40), 0.98, 0.0),
    "MB Foliage": ((0.57, 0.72, 0.47), 0.98, 0.0),
}

_CLASSIC_LANDCOVER: dict[str | None, Rgb] = {
    None: (0.28, 0.26, 0.20),
    "grass": (0.16, 0.32, 0.08),
    "forest": (0.07, 0.20, 0.05),
    "water": (0.05, 0.14, 0.24),
    "sand": (0.62, 0.55, 0.38),
}

_STYLIZED_LANDCOVER: dict[str | None, Rgb] = {
    None: (0.75, 0.70, 0.62),
    "grass": (0.67, 0.79, 0.42),
    "forest": (0.43, 0.58, 0.37),
    "water": (0.45, 0.77, 0.92),
    "sand": (0.91, 0.85, 0.65),
}

_CLASSIC_BARK, _CLASSIC_LEAF = (0.18, 0.11, 0.06), (0.06, 0.20, 0.05)
_STYLIZED_BARK = (0.53, 0.43, 0.33)
_FLAT_ROOF = (0.68, 0.62, 0.56)
_MAJOR_ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link",
                "primary_link", "secondary_link"}
_MINOR_ROADS = {"residential", "unclassified", "living_street", "service"}
_CLASSIC_FOOT_WAYS = {"footway", "path", "cycleway", "steps", "bridleway", "pedestrian", "track"}

_STYLIZED_FACADE = [
    (0.93, 0.84, 0.72),
    (0.90, 0.80, 0.67),
    (0.83, 0.73, 0.61),
    (0.95, 0.88, 0.78),
    (0.86, 0.80, 0.73),
    (0.88, 0.76, 0.64),
]
_STYLIZED_ROOF = [(0.74, 0.56, 0.45), (0.66, 0.57, 0.52), (0.56, 0.49, 0.45), (0.69, 0.61, 0.53)]


def normalize_style(style: str | None) -> StyleMode:
    if style == "classic":
        return "classic"
    return "stylized"


def is_stylized(style: str | None) -> bool:
    return normalize_style(style) == "stylized"


def style_uses_textures(style: str | None) -> bool:
    return normalize_style(style) == "classic"


def materials_for_style(style: str | None) -> dict[str, MaterialSpec]:
    return dict(_CLASSIC_MATERIALS if normalize_style(style) == "classic" else _STYLIZED_MATERIALS)


def _stable_hash(key: str) -> int:
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)


def _choose(values: Sequence[Rgb], key: str) -> Rgb:
    return values[_stable_hash(key) % len(values)]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _scaled(c: Rgb, factor: float) -> Rgb:
    return cast("Rgb", tuple(_clamp(x * factor, 0.0, 1.0) for x in c))


def _pull_into_palette(rgb: Sequence[float], saturation: tuple[float, float], value: tuple[float, float]) -> Rgb:
    """Keep the hue of a tagged colour; clamp its saturation and brightness (sRGB HSV) to the palette."""
    h, s, v = colorsys.rgb_to_hsv(*(linear_to_srgb(c) for c in rgb))
    if s >= HUE_MIN_SATURATION:     # a grey has no hue to keep, so it stays grey
        s = _clamp(s, *saturation)
    r, g, b = colorsys.hsv_to_rgb(h, s, _clamp(v, *value))
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b))


def face_cross(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    """Normal of the counter-clockwise triangle ``a, b, c``, scaled by twice its area."""
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    w = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])


def face_normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    """Unit normal of the counter-clockwise triangle ``a, b, c``."""
    return _normalized(face_cross(a, b, c))


def _lambert(normal: Vec3) -> float:
    return normal[0] * _SUN[0] + normal[1] * _SUN[1] + normal[2] * _SUN[2]


def terrain_color(style: str | None, landcover: str | None, slope: float = 0.0) -> Rgb:
    """Landcover colour; stylized terrain gets a brightness ramp by ``slope`` (rise over run)."""
    mode = normalize_style(style)
    palette = _CLASSIC_LANDCOVER if mode == "classic" else _STYLIZED_LANDCOVER
    base = palette.get(landcover, palette[None])
    if mode == "classic":
        return base
    t = slope / SLOPE_RAMP_FULL_TAN
    factor = SLOPE_RAMP_BRIGHTEST + (SLOPE_RAMP_DARKEST - SLOPE_RAMP_BRIGHTEST) * (t if t < 1.0 else 1.0)
    r, g, b = base      # inline arithmetic: this runs once per terrain triangle
    return (r * factor if r * factor < 1.0 else 1.0,
            g * factor if g * factor < 1.0 else 1.0,
            b * factor if b * factor < 1.0 else 1.0)


def terrain_face_color(landcover: str | None, normal: Vec3, in_bank_band: bool) -> Rgb:
    """Stylized colour of one terrain triangle: cliff colours from 35 degrees, else sand inside the bank band,
    else the landcover ramp. ``normal`` points up and need not be unit length."""
    nx, ny, nz = normal
    horizontal_sq = nx * nx + ny * ny
    if nz <= 0.0 or horizontal_sq >= (nz * _CLIFF_MIN_TAN) ** 2:
        return _CLIFF_LIT if nx * _SUN[0] + ny * _SUN[1] > 0.0 else _CLIFF_SHADOW
    if in_bank_band and landcover != "water":
        return _SAND_BANK
    return terrain_color("stylized", landcover, math.sqrt(horizontal_sq) / nz)


def water_color(style: str | None) -> Rgb:
    """Vertex colour of a built water surface; stylized is calibrated so the render reads as ``#6dc0e7``."""
    return _CLASSIC_LANDCOVER["water"] if normalize_style(style) == "classic" else _STYLIZED_WATER


def bank_color(style: str | None) -> Rgb:
    """Colour of a ``bank:`` shore ramp. The ramp is the first land from the sheet's edge, so stylized it is the
    shallow band: water, shallow band and sand then follow each other without a gap."""
    return _CLASSIC_LANDCOVER[None] if normalize_style(style) == "classic" else _SHALLOW_BAND


def road_color(style: str | None, tags: Mapping[str, str]) -> Rgb:
    highway = tags.get("highway")
    if normalize_style(style) == "classic":
        return (0.35, 0.32, 0.28) if highway in _CLASSIC_FOOT_WAYS else (0.12, 0.12, 0.12)
    if highway in _CLASSIC_FOOT_WAYS:
        return _FOOTPATH
    if highway in _MAJOR_ROADS:
        return (0.87, 0.72, 0.54)
    if highway in _MINOR_ROADS:
        return (0.85, 0.76, 0.62)
    return (0.80, 0.73, 0.61)


def facade_color(measured: Sequence[float] | None, fallback_key: str) -> Rgb:
    """Stylized wall colour: a tagged colour keeps its hue as a pastel, else a palette pick."""
    if measured is not None:
        return _pull_into_palette(measured, (0.0, FACADE_MAX_SATURATION), FACADE_VALUE_RANGE)
    return _choose(_STYLIZED_FACADE, fallback_key)


def roof_color(measured: Sequence[float] | None, fallback_key: str, is_flat: bool) -> Rgb:
    """Stylized roof colour: a tagged colour keeps its hue, saturated into the palette range."""
    if measured is not None:
        return _pull_into_palette(measured, ROOF_SATURATION_RANGE, ROOF_VALUE_RANGE)
    return _FLAT_ROOF if is_flat else _choose(_STYLIZED_ROOF, fallback_key)


def tree_tint_variant(style: str | None, key: str) -> int:
    """Deterministic tint variant of a tree, from its OSM id or scatter id; classic trees have one look."""
    return 0 if normalize_style(style) == "classic" else _stable_hash(key) % len(TREE_TINT_SCALES)


def bark_color(style: str | None, variant: int) -> Rgb:
    if normalize_style(style) == "classic":
        return _CLASSIC_BARK
    return _scaled(_STYLIZED_BARK, TREE_TINT_SCALES[variant])


def foliage_color(style: str | None, variant: int, normal: Vec3) -> Rgb:
    """Foliage colour of one crown face: lit, mid or shadow side by its facing, tinted by the variant."""
    if normalize_style(style) == "classic":
        return _CLASSIC_LEAF
    lambert = _lambert(normal)
    if lambert > FOLIAGE_LIT_MIN:
        base = _FOLIAGE_LIT
    elif lambert > FOLIAGE_SHADOW_MAX:
        base = _FOLIAGE_MID
    else:
        base = _FOLIAGE_SHADOW
    return _scaled(base, TREE_TINT_SCALES[variant])
