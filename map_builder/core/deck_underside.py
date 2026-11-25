# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Shore ramps under bridge decks (D178).

A bank ramp is terrain, so it may run under an elevated deck, but not into an at-grade one or its abutments. The
bridge stage gives a lower bound of each deck's underside and its plan footprint (``bridges.deck_underside``);
:func:`trim_under_decks` cuts out of a ramp triangle every footprint quad whose deck has less than
``RAMP_MIN_CLEARANCE_M`` over the part of the triangle in it. :class:`RampLines` tells the water stage which lines
still mask a ramp whole.

Pure geometry, no I/O.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property

from .overlap import (bounding_box, boxes_meet, convex_difference, convex_intersection, polygon_area,
                      signed_area2)

Pt = tuple[float, float]
Vec3 = tuple[float, float, float]
Tri = tuple[Vec3, Vec3, Vec3]
Box = tuple[float, float, float, float]               # (min x, min y, max x, max y)
Line = tuple[Sequence[Pt], float]                     # (polyline, half width)
WaterMax = Callable[[Pt, Pt], "float | None"]         # the highest water level along a segment, or None

RAMP_MIN_CLEARANCE_M = 2.5   # passages.MIN_CLEARANCE_M: the lowest free height under a deck that is not at-grade
MIN_PIECE_AREA_M2 = 1e-6     # a clipped piece smaller than this is a rounding sliver, not ramp


@dataclass(frozen=True)
class DeckUnderside:
    """A deck seen from below: a lower bound ``z[i]`` of its underside at arc length ``s[i]`` of its path ``xy[i]``
    (linear between), and its plan ``footprint`` as convex quads, sunk ends included."""
    xy: Sequence[Pt]
    s: Sequence[float]
    z: Sequence[float]
    footprint: Sequence[Sequence[Pt]]

    @cached_property
    def _quad_boxes(self) -> list[Box]:
        return [bounding_box(quad) for quad in self.footprint]

    def at_grade_quads(self, tri: Tri) -> Iterator[Sequence[Pt]]:
        """The footprint quads that share area with the triangle and do not clear the part of it they cover."""
        plan = _plan(tri)
        plan_box = bounding_box(plan)
        for quad, quad_box in zip(self.footprint, self._quad_boxes):
            if not boxes_meet(plan_box, quad_box):
                continue
            covered = convex_intersection(plan, quad)
            if polygon_area(covered) > MIN_PIECE_AREA_M2 and not self.clears([_lift(tri, p) for p in covered]):
                yield quad

    def clears(self, piece: Sequence[Vec3], clearance: float = RAMP_MIN_CLEARANCE_M) -> bool:
        """Whether the deck stands at least ``clearance`` above the whole planar piece. A piece reaching past a
        deck end (an abutment) is never cleared."""
        stations = [self._station(v[0], v[1]) for v in piece]
        known = [st for st in stations if st is not None]
        if len(known) < len(stations):
            return False
        return self._lowest_between(min(known), max(known)) - max(v[2] for v in piece) >= clearance

    def _station(self, x: float, y: float) -> float | None:
        """Arc length of the path point nearest to (x, y); None if that is an end of the path or past it."""
        best: tuple[float, float] | None = None   # (squared distance, arc length)
        for i in range(len(self.xy) - 1):
            (ax, ay), (bx, by) = self.xy[i], self.xy[i + 1]
            dx, dy = bx - ax, by - ay
            n2 = dx * dx + dy * dy
            t = 0.0 if n2 == 0.0 else min(max(((x - ax) * dx + (y - ay) * dy) / n2, 0.0), 1.0)
            d2 = (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2
            if best is None or d2 < best[0]:
                best = (d2, self.s[i] + t * (self.s[i + 1] - self.s[i]))
        if best is None or not self.s[0] < best[1] < self.s[-1]:
            return None
        return best[1]

    def _lowest_between(self, s0: float, s1: float) -> float:
        """The lowest underside over an arc-length range: at its ends or a path node inside it (linear between)."""
        inner = [z for si, z in zip(self.s, self.z) if s0 < si < s1]
        return min([self._at(s0), self._at(s1)] + inner)

    def _at(self, st: float) -> float:
        for i in range(len(self.s) - 1):
            if self.s[i] <= st <= self.s[i + 1]:
                span = self.s[i + 1] - self.s[i]
                return self.z[i] if span == 0.0 else self.z[i] + (self.z[i + 1] - self.z[i]) * (st - self.s[i]) / span
        raise ValueError(f"arc length {st} is off the deck path")


def trim_under_decks(tri: Tri, decks: Sequence[DeckUnderside]) -> list[Tri]:
    """The ramp triangle minus every at-grade footprint quad of ``decks``: the triangle itself if there is none,
    else the rest as fans of triangles in the triangle's plane, wound like it."""
    cuts = [quad for deck in decks for quad in deck.at_grade_quads(tri)]
    if not cuts:
        return [tri]
    pieces = [_plan(tri)]
    for quad in cuts:
        pieces = [rest for piece in pieces for rest in convex_difference(piece, quad)]
    counter_clockwise = signed_area2(_plan(tri)) > 0.0
    return [(_lift(tri, a), _lift(tri, b), _lift(tri, c)) for piece in pieces
            for a, b, c in _fan(piece, counter_clockwise) if polygon_area((a, b, c)) > MIN_PIECE_AREA_M2]


def _plan(tri: Sequence[Vec3]) -> list[Pt]:
    return [(v[0], v[1]) for v in tri]


def _fan(piece: Sequence[Pt], counter_clockwise: bool) -> list[tuple[Pt, Pt, Pt]]:
    """A convex polygon as a triangle fan from its first vertex, each wound counter-clockwise or clockwise."""
    ring = list(piece) if (signed_area2(piece) > 0.0) == counter_clockwise else list(reversed(piece))
    return [(ring[0], ring[i], ring[i + 1]) for i in range(1, len(ring) - 1)]


def _lift(tri: Tri, p: Pt) -> Vec3:
    """The point of the triangle's plane over ``p`` (barycentric; ``tri`` is not degenerate in plan)."""
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    wa = ((by - cy) * (p[0] - cx) + (cx - bx) * (p[1] - cy)) / det
    wb = ((cy - ay) * (p[0] - cx) + (ax - cx) * (p[1] - cy)) / det
    return p[0], p[1], wa * az + wb * bz + (1.0 - wa - wb) * cz


@dataclass
class RampLines:
    """How bridge and tunnel lines mask shore ramps. ``always``: lines that mask a whole strip wherever it meets
    them (tunnels, bridges without a deck). ``decks``: ``(bridge id, polyline, half width)`` of the lines of
    highway bridges, which only trim a ramp under their at-grade parts; ``undersides`` gives their decks, by id,
    once the water levels are known. A deck line whose bridge has no underside (no deck) masks like ``always``."""
    always: list[Line] = field(default_factory=list)
    decks: list[tuple[str, Sequence[Pt], float]] = field(default_factory=list)
    undersides: Callable[[WaterMax], Mapping[str, DeckUnderside]] = lambda water_max: {}
