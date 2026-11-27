# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Plan-view overlap tests between a triangle and a polygon ring or polyline (exact, not sampled)."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Iterator, Sequence

from .osm import point_in_ring
from . import perf_counters

Pt = tuple[float, float]
Edge = tuple[Pt, Pt]
Box = tuple[float, float, float, float]
BOUNDARY_CROSS_EPS = 1e-12   # plan-area/collinearity epsilon: points this close to an edge are treated as boundary
OVERLAP_AREA_EPS_M2 = 1e-9   # area this small is treated as boundary-only touch (no positive wet overlap)


def point_segment_distance(x: float, y: float, a: Pt, b: Pt) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    ll = dx * dx + dy * dy
    u = 0.0 if ll == 0 else min(1.0, max(0.0, ((x - a[0]) * dx + (y - a[1]) * dy) / ll))
    return math.hypot(x - a[0] - u * dx, y - a[1] - u * dy)


def triangle_touches(tri: Sequence[Pt], path: Sequence[Pt], margin: float, closed: bool) -> bool:
    """Whether the triangle lies within ``margin`` of ``path``: a closed ring (touching it or containing it
    counts) or an open polyline. Nothing is sampled, so a small ring wholly inside the triangle is found.
    Indexes ``path`` on every call: to test many triangles against one path, build a ``PathMask`` once."""
    return PathMask(path, margin, closed).touches(tri)


STRIP_HEIGHT_M = 8.0   # RingIndex / EdgeIndex bucket edges by y strips this tall


def _strip(y: float) -> int:
    return math.floor(y / STRIP_HEIGHT_M)


class EdgeIndex:
    """Edges bucketed by the y strips their own box covers, so a box query reads only the strips it spans.

    Input contract: any edges. Orientation, zero-length edges, repeated edges and self-intersections are fine;
    every query answers from the edges as given. Coordinates must be finite."""

    def __init__(self, edges: Iterable[Edge]) -> None:
        self._strips: dict[int, list[tuple[int, Edge]]] = {}   # strip -> (the edge's first strip, edge)
        for edge in edges:
            (_, ya), (_, yb) = edge
            first = _strip(min(ya, yb))
            for strip in range(first, _strip(max(ya, yb)) + 1):
                self._strips.setdefault(strip, []).append((first, edge))

    def edges_in_box(self, box: Box) -> Iterator[Edge]:
        """Every edge whose own box meets ``box``, once each (an edge spans several strips, so it is yielded
        from the first strip of the query that holds it)."""
        first_strip = _strip(box[1])
        for strip in range(first_strip, _strip(box[3]) + 1):
            for edge_first, edge in self._strips.get(strip, ()):
                if (strip == first_strip or edge_first == strip) and _edge_in_box(*edge, box):
                    yield edge

    def has_edge_in_box(self, box: Box) -> bool:
        return next(self.edges_in_box(box), None) is not None


class RingIndex(EdgeIndex):
    """A closed ring as an ``EdgeIndex`` that also answers point containment with ``point_in_ring``'s crossing
    parity, over only the edges that straddle the query's y. A point outside the ring's box is outside the ring."""

    def __init__(self, ring: Sequence[Pt]) -> None:
        points = list(ring)
        super().__init__(zip(points[-1:] + points[:-1], points))
        self.box = bounding_box(points)

    def contains(self, x: float, y: float) -> bool:
        if not _in_box(x, y, self.box):
            return False
        straddling = self._strips.get(_strip(y), ())
        if perf_counters.ENABLED:
            perf_counters.inc("ring_edge_tests", len(straddling))
        inside = False
        for _, ((xj, yj), (xi, yi)) in straddling:
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        return inside


class PathMask:
    """A footprint ring or a road polyline, indexed once, that plan triangles are tested against with ``margin``.

    Input contract: ``path`` is a ring (``closed``; either winding, the closing edge implied) or a polyline of
    two or more points; repeated or zero-length edges are fine. ``touches`` is true when the triangle is within
    ``margin`` of the path, or (closed) contains or lies inside the ring."""

    def __init__(self, path: Sequence[Pt], margin: float, closed: bool) -> None:
        self.margin = margin
        self.box = _padded_box(path, margin)
        self._contains: Callable[[float, float], bool] | None = None
        if closed:
            ring = RingIndex(path)
            self._index: EdgeIndex = ring
            self._contains = ring.contains
        else:
            self._index = EdgeIndex(_edges(path, False))

    def may_touch(self, tri: Sequence[Pt]) -> bool:
        """False only when the triangle's box misses this mask's padded box, so ``touches`` is False."""
        return boxes_meet(bounding_box(tri), self.box)

    def touches(self, tri: Sequence[Pt]) -> bool:
        if perf_counters.ENABLED:
            perf_counters.inc("overlap_pairs")
        box = _padded_box(tri, self.margin)
        near = list(self._index.edges_in_box(box))
        if any(point_in_ring(x, y, tri) for a, b in near for x, y in (a, b) if _in_box(x, y, box)):
            return True
        if self._contains is not None and any(self._contains(x, y) for x, y in tri):
            return True
        return any(_segment_distance(a, b, c, d) <= self.margin for a, b in near for c, d in _edges(tri, True))


class RegionMask:
    """A region (``outer`` minus ``holes``), indexed once: ``overlaps`` answers as ``triangle_overlaps_region``.

    Input contract: rings in either winding, holes inside ``outer``; degenerate (under 3 point) rings never
    overlap, exactly as in ``triangle_overlaps_region``."""

    def __init__(self, outer: Sequence[Pt], holes: Sequence[Sequence[Pt]]) -> None:
        self.outer, self.holes = outer, holes
        self._outer_index = RingIndex(outer)
        self._hole_indexes = [RingIndex(h) for h in holes]

    def contains(self, x: float, y: float) -> bool:
        return self._outer_index.contains(x, y) and not any(h.contains(x, y) for h in self._hole_indexes)

    def overlaps(self, tri: Sequence[Pt]) -> bool:
        return not self._clear_of_outer(tri) and triangle_overlaps_region(tri, self.outer, self.holes)

    def _clear_of_outer(self, tri: Sequence[Pt]) -> bool:
        """Whether the triangle is wholly outside ``outer`` and so shares no area with the region: its box misses the
        ring's box, or meets no ring edge (so it is wholly inside or wholly outside) and a vertex is outside."""
        box = bounding_box(tri)
        if not boxes_meet(box, self._outer_index.box):
            return True
        return not self._outer_index.has_edge_in_box(box) and not self._outer_index.contains(*tri[0])

def triangle_overlaps_region(tri: Sequence[Pt], outer: Sequence[Pt], holes: Sequence[Sequence[Pt]]) -> bool:
    """Whether the triangle and the region (``outer`` minus ``holes``) share positive area.

    The overlap is exact in plan area: each ring is clipped against the triangle, then overlap area is
    ``area(clip(outer)) - Σ area(clip(hole))``. Boundary-only touch gives zero area by construction.
    """
    if perf_counters.ENABLED:
        perf_counters.inc("overlap_pairs")
    if not boxes_meet(bounding_box(tri), bounding_box(outer)):
        return False
    origin = tri[0]
    tri_local = [_sub_xy(p, origin) for p in tri]
    outer_local = [_sub_xy(p, origin) for p in outer]
    holes_local = [[_sub_xy(p, origin) for p in h] for h in holes]
    wet = _clipped_ring_area(tri_local, outer_local) - sum(_clipped_ring_area(tri_local, h) for h in holes_local)
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
    if perf_counters.ENABLED:
        perf_counters.inc("overlap_edge_tests")
    if _segments_cross(a, b, c, d):
        return 0.0
    return min(point_segment_distance(*a, c, d), point_segment_distance(*b, c, d),
               point_segment_distance(*c, a, b), point_segment_distance(*d, a, b))


def _segments_cross(a: Pt, b: Pt, c: Pt, d: Pt) -> bool:
    return _side(a, b, c) * _side(a, b, d) < 0 and _side(c, d, a) * _side(c, d, b) < 0


def _side(a: Pt, b: Pt, p: Pt) -> float:
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def bounding_box(points: Sequence[Pt]) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def boxes_meet(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _clipped_ring_area(tri: Sequence[Pt], ring: Sequence[Pt]) -> float:
    poly = list(ring)
    if len(poly) < 3:
        return 0.0
    t = list(tri)
    if signed_area2(t) < 0.0:
        t[1], t[2] = t[2], t[1]
    for i in range(3):
        a, b = t[i], t[(i + 1) % 3]
        poly = _clip_against_edge(poly, a, b)
        if len(poly) < 3:
            return 0.0
    return polygon_area(poly)

def convex_intersection(subject: Sequence[Pt], clip: Sequence[Pt]) -> list[Pt]:
    """The convex polygon ``subject`` cut to the convex polygon ``clip`` (either winding); [] if they share no area."""
    poly = list(subject)
    for a, b in _edges(_counter_clockwise(clip), True):
        poly = _clip_against_edge(poly, a, b)
        if len(poly) < 3:
            return []
    return poly


def convex_difference(subject: Sequence[Pt], clip: Sequence[Pt]) -> list[list[Pt]]:
    """The convex polygon ``subject`` minus the convex polygon ``clip`` (either winding), as convex pieces: the part
    outside each edge of ``clip`` of what the previous edges left inside."""
    pieces: list[list[Pt]] = []
    rest = list(subject)
    for a, b in _edges(_counter_clockwise(clip), True):
        outside = _clip_against_edge(rest, b, a)
        if len(outside) >= 3 and polygon_area(outside) > 0.0:
            pieces.append(outside)
        rest = _clip_against_edge(rest, a, b)
        if len(rest) < 3:
            break
    return pieces


def _counter_clockwise(ring: Sequence[Pt]) -> list[Pt]:
    return list(ring) if signed_area2(ring) >= 0.0 else list(reversed(ring))


def _clip_against_edge(subject: list[Pt], a: Pt, b: Pt) -> list[Pt]:
    if not subject:
        return []
    if perf_counters.ENABLED:
        perf_counters.inc("clip_steps", len(subject))
        perf_counters.inc("overlap_edge_tests", len(subject))
    out: list[Pt] = []
    prev = subject[-1]
    prev_side = _side(a, b, prev)
    prev_in = prev_side >= 0.0
    for curr in subject:
        curr_side = _side(a, b, curr)
        curr_in = curr_side >= 0.0
        if curr_in:
            if not prev_in:
                out.append(_line_intersection_by_side(prev, curr, prev_side, curr_side))
            out.append(curr)
        elif prev_in:
            out.append(_line_intersection_by_side(prev, curr, prev_side, curr_side))
        prev, prev_in, prev_side = curr, curr_in, curr_side
    return out


def _line_intersection_by_side(a: Pt, b: Pt, side_a: float, side_b: float) -> Pt:
    den = side_a - side_b
    if den == 0.0:
        return b
    t = side_a / den
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def polygon_area(poly: Sequence[Pt]) -> float:
    return 0.5 * abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                         for i in range(len(poly))))


def signed_area2(poly: Sequence[Pt]) -> float:
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly)))


def _sub_xy(a: Pt, b: Pt) -> Pt:
    return a[0] - b[0], a[1] - b[1]
