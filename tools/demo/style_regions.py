# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""Preset-scoped palette regions: loading, validation and pairing (no Pillow, no bpy)."""

from __future__ import annotations

import json
from dataclasses import dataclass

import style_color


@dataclass(frozen=True)
class Region:
    """A rectangle in image fractions. Swatch regions carry ``target_hex``; contrast regions do not."""

    camera: str
    label: str
    x: float
    y: float
    w: float
    h: float
    target_hex: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.camera, self.label)

    @property
    def pair_id(self) -> str:
        """Contrast regions ``<kind>-<n>`` pair up by their shared ``<n>``."""
        return self.label.rsplit("-", 1)[-1]


def _parse_region(raw: dict) -> Region:
    region = Region(
        camera=str(raw["camera"]),
        label=str(raw["label"]),
        x=float(raw["x"]),
        y=float(raw["y"]),
        w=float(raw["w"]),
        h=float(raw["h"]),
        target_hex=raw.get("target_hex"),
    )
    if region.target_hex is not None:
        style_color.hex_to_rgb(region.target_hex)
    inside = region.w > 0 and region.h > 0 and 0 <= region.x and 0 <= region.y
    if not inside or region.x + region.w > 1 or region.y + region.h > 1:
        raise ValueError(f"region {region.key} is not inside the image")
    return region


def parse_regions(raw: dict) -> list[Region]:
    regions = [_parse_region(r) for r in raw.get("regions", [])]
    keys = [r.key for r in regions]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise ValueError(f"duplicate (camera, label) keys: {duplicates}")
    return regions


def load_regions(path: str) -> list[Region]:
    with open(path, "r", encoding="utf-8") as f:
        return parse_regions(json.load(f))


def regions_for_camera(regions: list[Region], camera: str) -> list[Region]:
    return [r for r in regions if r.camera == camera]


def swatch_regions(regions: list[Region]) -> list[Region]:
    return [r for r in regions if r.target_hex is not None]


def contrast_pairs(regions: list[Region]) -> list[tuple[Region, Region]]:
    """Pair the targetless regions that share a suffix, in file order (``roof-1`` with ``wall-1``)."""
    groups: dict[str, list[Region]] = {}
    for region in regions:
        if region.target_hex is None:
            groups.setdefault(region.pair_id, []).append(region)
    for pair_id, members in groups.items():
        if len(members) != 2:
            raise ValueError(f"contrast regions with suffix '-{pair_id}' must come in twos: {[m.key for m in members]}")
    return [(members[0], members[1]) for members in groups.values()]
