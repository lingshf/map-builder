# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Plan-view overlap tests between a triangle and a polygon ring or polyline (exact, not sampled)."""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence

from .osm import point_in_ring

Pt = tuple[float, float]
BOUNDARY_CROSS_EPS = 1e-12   # plan-area/collinearity epsilon: points this close to an edge are treated as boundary
OVERLAP_AREA_EPS_M2 = 1e-9   # area this small is treated as boundary-only touch (no positive wet overlap)


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
    """Whether the triangle and the region (``outer`` minus ``holes``) share positive area.

    The overlap is exact in plan area: each ring is clipped against the triangle, then overlap area is
    ``area(clip(outer)) - Σ area(clip(hole))``. Boundary-only touch gives zero area by construction.
    """
    if not _boxes_meet(_box(tri), _box(outer)):
        return False
    wet = _clipped_ring_area(tri, outer) - sum(_clipped_ring_area(tri, h) for h in holes)
    return wet > OVERLAP_AREA_EPS_M2


def _in_region_strict(p: Pt, outer: Sequence[Pt], holes: Sequence[Sequence[Pt]]) -> bool:
    if _on_ring_boundary(p, outer) or any(_on_ring_boundary(p, h) for h in holes):
        return False
    return point_in_ring(*p, outer) and not any(point_in_ring(*p, h) for h in holes)


def _in_triangle_strict(p: Pt, tri: Sequence[Pt]) -> bool:
    return point_in_ring(*p, tri) and not any(_point_on_segment(p, a, b) for a, b in _edges(tri, True))


def _on_ring_boundary(p: Pt, ring: Sequence[Pt]) -> bool:
    return any(_point_on_segment(p, a, b) for a, b in _edges(ring, True))


def _point_on_segment(p: Pt, a: Pt, b: Pt) -> bool:
    dx, dy = b[0] - a[0], b[1] - a[1]
    cross = dx * (p[1] - a[1]) - dy * (p[0] - a[0])
    if abs(cross) > BOUNDARY_CROSS_EPS:
        return False
    dot = (p[0] - a[0]) * dx + (p[1] - a[1]) * dy
    if dot < 0:
        return False
    ll = dx * dx + dy * dy
    return dot <= ll

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


def _box(points: Sequence[Pt]) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _boxes_meet(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _clipped_ring_area(tri: Sequence[Pt], ring: Sequence[Pt]) -> float:
    poly = list(ring)
    if len(poly) < 3:
        return 0.0
    t = list(tri)
    for i in range(3):
        a, b, c = t[i], t[(i + 1) % 3], t[(i + 2) % 3]
        poly = _clip_against_edge(poly, a, b, c)
        if len(poly) < 3:
            return 0.0
    return _polygon_area(poly)


def _clip_against_edge(subject: list[Pt], a: Pt, b: Pt, inside_ref: Pt) -> list[Pt]:
    if not subject:
        return []
    out: list[Pt] = []
    prev = subject[-1]
    prev_in = _inside_half_plane(prev, a, b, inside_ref)
    for curr in subject:
        curr_in = _inside_half_plane(curr, a, b, inside_ref)
        if curr_in:
            if not prev_in:
                out.append(_line_intersection(prev, curr, a, b))
            out.append(curr)
        elif prev_in:
            out.append(_line_intersection(prev, curr, a, b))
        prev, prev_in = curr, curr_in
    return out


def _inside_half_plane(p: Pt, a: Pt, b: Pt, inside_ref: Pt) -> bool:
    edge = _side(a, b, p)
    ref = _side(a, b, inside_ref)
    if abs(ref) <= BOUNDARY_CROSS_EPS:
        return abs(edge) <= BOUNDARY_CROSS_EPS
    return edge * ref >= -BOUNDARY_CROSS_EPS


def _line_intersection(p0: Pt, p1: Pt, a: Pt, b: Pt) -> Pt:
    sx, sy = p1[0] - p0[0], p1[1] - p0[1]
    rx, ry = b[0] - a[0], b[1] - a[1]
    den = sx * ry - sy * rx
    if abs(den) <= BOUNDARY_CROSS_EPS:
        return p1
    qx, qy = a[0] - p0[0], a[1] - p0[1]
    t = (qx * ry - qy * rx) / den
    return p0[0] + t * sx, p0[1] + t * sy


def _polygon_area(poly: Sequence[Pt]) -> float:
    return 0.5 * abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                         for i in range(len(poly))))
