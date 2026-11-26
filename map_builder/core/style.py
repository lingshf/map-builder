# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5 style palette and colour/material rules.

Classic mode preserves pre-S5 colours and materials. Stylized mode applies the
palette sampled from the reference background art and keeps geometry untouched.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from typing import Any, Literal, cast

StyleMode = Literal["classic", "stylized"]
Rgb = tuple[float, float, float]
MaterialSpec = tuple[Rgb, float, float]

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

_CLASSIC_FACADE = [
    (0.62, 0.58, 0.52),
    (0.70, 0.66, 0.60),
    (0.55, 0.42, 0.34),
    (0.75, 0.73, 0.70),
    (0.48, 0.47, 0.46),
    (0.66, 0.55, 0.42),
]
_CLASSIC_ROOF = [(0.30, 0.12, 0.08), (0.22, 0.22, 0.24), (0.40, 0.20, 0.12), (0.35, 0.35, 0.36)]

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


def style_uses_textures(style: str | None) -> bool:
    return normalize_style(style) == "classic"


def materials_for_style(style: str | None) -> dict[str, MaterialSpec]:
    return dict(_CLASSIC_MATERIALS if normalize_style(style) == "classic" else _STYLIZED_MATERIALS)


def _choose(values: list[Rgb], key: str) -> Rgb:
    n = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)
    return values[n % len(values)]


def _scaled(c: Rgb, factor: float) -> Rgb:
    return cast("Rgb", tuple(max(0.0, min(1.0, x * factor)) for x in c))


def terrain_color(style: str | None, landcover: str | None, slope: float = 0.0) -> Rgb:
    mode = normalize_style(style)
    base = (_CLASSIC_LANDCOVER if mode == "classic" else _STYLIZED_LANDCOVER).get(landcover, _STYLIZED_LANDCOVER[None])
    if mode == "classic":
        return base
    # Stylized slope ramp: flatter terrain is slightly brighter, steeper terrain slightly darker.
    t = max(0.0, min(1.0, slope / 0.45))
    return _scaled(base, 1.08 - 0.18 * t)


def bank_color(style: str | None) -> Rgb:
    return _CLASSIC_LANDCOVER[None] if normalize_style(style) == "classic" else (0.88, 0.80, 0.67)


def road_color(style: str | None, tags: Mapping[str, str]) -> Rgb:
    if normalize_style(style) == "classic":
        return (0.12, 0.12, 0.12) if tags.get("highway") not in {
            "footway", "path", "cycleway", "steps", "bridleway", "pedestrian", "track"
        } else (0.35, 0.32, 0.28)
    highway = tags.get("highway")
    if highway in {"motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link",
                   "primary_link", "secondary_link"}:
        return (0.87, 0.72, 0.54)
    if highway in {"residential", "unclassified", "living_street", "service"}:
        return (0.85, 0.76, 0.62)
    return (0.80, 0.73, 0.61)


def facade_color(style: str | None, tags: Mapping[str, str], fallback_key: str) -> Rgb:
    palette = _CLASSIC_FACADE if normalize_style(style) == "classic" else _STYLIZED_FACADE
    measured = tags.get("building:colour")
    if measured:
        return _choose(palette, measured + fallback_key)
    return _choose(palette, fallback_key)


def roof_color(style: str | None, tags: Mapping[str, str], fallback_key: str, is_flat: bool) -> Rgb:
    if normalize_style(style) == "classic":
        if is_flat:
            return (0.3, 0.3, 0.31)
        measured = tags.get("roof:colour")
        if measured:
            return _choose(_CLASSIC_ROOF, measured + fallback_key)
        return _choose(_CLASSIC_ROOF, fallback_key)
    if is_flat:
        return (0.68, 0.62, 0.56)
    measured = tags.get("roof:colour")
    if measured:
        return _scaled(_choose(_STYLIZED_ROOF, measured + fallback_key), 1.03)
    return _choose(_STYLIZED_ROOF, fallback_key)


def tree_colours(style: str | None, seed: int) -> tuple[Rgb, Rgb]:
    if normalize_style(style) == "classic":
        return (0.18, 0.11, 0.06), (0.06, 0.20, 0.05)
    tint = (seed % 7) / 20.0
    bark = _scaled((0.53, 0.43, 0.33), 1.0 + tint * 0.1)
    foliage = _scaled((0.37, 0.57, 0.31), 0.95 + tint * 0.08)
    return bark, foliage


def terrain_slope(grid: Any, i: int, j: int) -> float:
    # local finite-difference slope magnitude; caller passes ElevationGrid-like object.
    h = grid.heights
    s = float(grid.spacing)
    dzdx = (h[j][i + 1] - h[j][i] + h[j + 1][i + 1] - h[j + 1][i]) / (2 * s)
    dzdy = (h[j + 1][i] - h[j][i] + h[j + 1][i + 1] - h[j][i + 1]) / (2 * s)
    return math.hypot(dzdx, dzdy)
