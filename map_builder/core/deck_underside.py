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

import math
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


QUAD_SPLITS = ((0, 1, 2), (0, 2, 3), (0, 1, 3), (1, 2, 3))   # a quad's triangles across either diagonal


@dataclass(frozen=True)
class DeckUnderside:
    """A deck seen from below, as its sweep makes it. ``footprint``: one convex plan quad
    ``[left start, right start, right end, left end]`` per path segment, quad ``i`` between sections ``i`` and
    ``i + 1``. ``z[i]``: a lower bound of the underside at section ``i``, linear across each quad; ``None`` where
    the section is sunk into an abutment."""
    footprint: Sequence[Sequence[Pt]]
    z: Sequence[float | None]

    @cached_property
    def _quad_boxes(self) -> list[Box]:
        return [bounding_box(quad) for quad in self.footprint]

    def at_grade_quads(self, tri: Tri) -> Iterator[Sequence[Pt]]:
        """The footprint quads that share area with the triangle and do not clear the part of it they cover."""
        plan = _plan(tri)
        plan_box = bounding_box(plan)
        for i, (quad, quad_box) in enumerate(zip(self.footprint, self._quad_boxes)):
            if not boxes_meet(plan_box, quad_box):
                continue
            covered = convex_intersection(plan, quad)
            if polygon_area(covered) > MIN_PIECE_AREA_M2 and not self.clears(i, tri, covered):
                yield quad

    def clears(self, quad: int, tri: Tri, covered: Sequence[Pt], clearance: float = RAMP_MIN_CLEARANCE_M) -> bool:
        """Whether the underside over footprint quad ``quad`` stands at least ``clearance`` above the ramp triangle
        ``tri`` over its plan part ``covered``. The gap is checked on the underside triangles of both diagonals,
        so it holds however the deck mesh splits the quad. A quad at an abutment never clears."""
        underside = self._underside_triangles(quad)
        return underside is not None and all(_lowest_gap(u, tri, covered) >= clearance for u in underside)

    def _underside_triangles(self, quad: int) -> list[Tri] | None:
        z_start, z_end = self.z[quad], self.z[quad + 1]
        if z_start is None or z_end is None:
            return None
        corners = [(x, y, z) for (x, y), z in zip(self.footprint[quad], (z_start, z_start, z_end, z_end))]
        return [(corners[a], corners[b], corners[c]) for a, b, c in QUAD_SPLITS]


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


def _lowest_gap(underside: Tri, ramp: Tri, covered: Sequence[Pt]) -> float:
    """The least height of the ``underside`` triangle above the ``ramp`` triangle over the part of ``covered`` under
    it; infinite where none is. Both are planar there, so their gap is linear and lowest at a vertex of that part."""
    if polygon_area(_plan(underside)) <= MIN_PIECE_AREA_M2:
        return math.inf
    part = convex_intersection(covered, _plan(underside))
    return min((_lift(underside, p)[2] - _lift(ramp, p)[2] for p in part), default=math.inf)


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
