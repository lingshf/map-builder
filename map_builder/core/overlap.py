# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Plan-view overlap tests between a triangle and a polygon ring or polyline (exact, not sampled)."""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence

from .osm import point_in_ring

Pt = tuple[float, float]
WET_SHRINK = 1e-3   # tolerance: a wet overlap thinner than this fraction of the triangle (~1 mm per m) is ignored


def point_segment_distance(x: float, y: float, a: Pt, b: Pt) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    ll = dx * dx + dy * dy
    u = 0.0 if ll == 0 else min(1.0, max(0.0, ((x - a[0]) * dx + (y - a[1]) * dy) / ll))
    return math.hypot(x - a[0] - u * dx, y - a[1] - u * dy)


def triangle_touches(tri: Sequence[Pt], path: Sequence[Pt], margin: float, closed: bool) -> bool:
    """Whether the triangle lies within ``margin`` of ``path``: a closed ring (touching it or containing it
    counts) or an open polyline. Nothing is sampled, so a small ring wholly inside the triangle is found."""
    box = _padded_box(tri, margin)
    if any(point_in_ring(x, y, tri) for x, y in path if _in_box(x, y, box)):
        return True
    if closed and any(point_in_ring(x, y, path) for x, y in tri):
        return True
    return any(_segment_distance(a, b, c, d) <= margin
               for a, b in _edges(path, closed) if _edge_in_box(a, b, box) for c, d in _edges(tri, True))


def triangle_overlaps_region(tri: Sequence[Pt], outer: Sequence[Pt], holes: Sequence[Sequence[Pt]]) -> bool:
    """Whether the triangle and the region (``outer`` minus ``holes``) share area. A triangle whose edge lies on
    the region's boundary does not: it is shrunk a little first, so rounding along that edge is not an overlap."""
    centre = (sum(p[0] for p in tri) / 3, sum(p[1] for p in tri) / 3)
    core = [(centre[0] + (x - centre[0]) * (1 - WET_SHRINK), centre[1] + (y - centre[1]) * (1 - WET_SHRINK)) for x, y in tri]
    rings = [outer, *holes]
    if any(point_in_ring(x, y, core) for ring in rings for x, y in ring):
        return True
    if any(_segments_cross(a, b, c, d) for ring in rings for a, b in _edges(ring, True) for c, d in _edges(core, True)):
        return True
    return point_in_ring(*centre, outer) and not any(point_in_ring(*centre, h) for h in holes)

def _padded_box(points: Sequence[Pt], pad: float) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def _in_box(x: float, y: float, box: tuple[float, float, float, float]) -> bool:
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _edge_in_box(a: Pt, b: Pt, box: tuple[float, float, float, float]) -> bool:
    """Cheap reject: the edge's own box misses ``box``, so no part of it can be within the margin."""
    return not (max(a[0], b[0]) < box[0] or min(a[0], b[0]) > box[2]
                or max(a[1], b[1]) < box[1] or min(a[1], b[1]) > box[3])


def _edges(points: Sequence[Pt], closed: bool) -> Iterator[tuple[Pt, Pt]]:
    count = len(points) if closed else len(points) - 1
    for i in range(count):
        yield points[i], points[(i + 1) % len(points)]


def _segment_distance(a: Pt, b: Pt, c: Pt, d: Pt) -> float:
    if _segments_cross(a, b, c, d):
        return 0.0
    return min(point_segment_distance(*a, c, d), point_segment_distance(*b, c, d),
               point_segment_distance(*c, a, b), point_segment_distance(*d, a, b))


def _segments_cross(a: Pt, b: Pt, c: Pt, d: Pt) -> bool:
    return _side(a, b, c) * _side(a, b, d) < 0 and _side(c, d, a) * _side(c, d, b) < 0


def _side(a: Pt, b: Pt, p: Pt) -> float:
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
