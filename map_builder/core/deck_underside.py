# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Shore ramps under bridge decks (D178).

A bank ramp is terrain, so it may run under an elevated deck, but not into an at-grade one or its abutments. The
bridge stage gives a lower bound of each deck's underside and its plan footprint (``bridges.deck_underside``);
:func:`trim_under_decks` cuts out of a ramp triangle every piece that lies in a footprint where that deck has less
than ``RAMP_MIN_CLEARANCE_M`` over it. :class:`RampLines` tells the water stage which lines still mask a ramp whole.

Pure geometry, no I/O.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from .overlap import triangle_touches

Pt = tuple[float, float]
Vec3 = tuple[float, float, float]
Tri = tuple[Vec3, Vec3, Vec3]
Line = tuple[Sequence[Pt], float]                     # (polyline, half width)
WaterMax = Callable[[Pt, Pt], "float | None"]         # the highest water level along a segment, or None

RAMP_MIN_CLEARANCE_M = 2.5   # passages.MIN_CLEARANCE_M: the lowest free height under a deck that is not at-grade
TRIM_DEPTH = 5               # a ramp triangle is quartered at most this often: 12 m ramps are cut to under 0.4 m


@dataclass(frozen=True)
class DeckUnderside:
    """A deck seen from below: a lower bound ``z[i]`` of its underside at arc length ``s[i]`` of its path ``xy[i]``
    (linear between), and its plan ``footprint`` as convex quads, sunk ends included."""
    xy: Sequence[Pt]
    s: Sequence[float]
    z: Sequence[float]
    footprint: Sequence[Sequence[Pt]]

    def at_grade_over(self, tri: Sequence[Vec3]) -> bool:
        """Whether the triangle meets the footprint somewhere the deck does not clear it."""
        plan = [(v[0], v[1]) for v in tri]
        return any(triangle_touches(plan, quad, 0.0, closed=True) for quad in self.footprint) \
            and not self.clears(tri)

    def clears(self, tri: Sequence[Vec3], clearance: float = RAMP_MIN_CLEARANCE_M) -> bool:
        """Whether the deck stands at least ``clearance`` above the whole triangle. A triangle reaching past a deck
        end (an abutment) is never cleared."""
        stations = [self._station(v[0], v[1]) for v in tri]
        known = [st for st in stations if st is not None]
        if len(known) < len(stations):
            return False
        return self._lowest_between(min(known), max(known)) - max(v[2] for v in tri) >= clearance

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


def trim_under_decks(tri: Tri, decks: Sequence[DeckUnderside], depth: int = TRIM_DEPTH) -> list[Tri]:
    """The pieces of a ramp triangle that no deck in ``decks`` stands at-grade over: the triangle itself if none
    does, else its midpoint quarters, trimmed in turn; a piece still under an at-grade deck after ``depth``
    quarterings is left out."""
    near = [d for d in decks if d.at_grade_over(tri)]
    if not near:
        return [tri]
    if depth == 0:
        return []
    return [piece for quarter in _quarters(tri) for piece in trim_under_decks(quarter, near, depth - 1)]


def _quarters(tri: Tri) -> list[Tri]:
    """The four midpoint sub-triangles, each wound like ``tri``."""
    a, b, c = tri
    ab, bc, ca = _mid(a, b), _mid(b, c), _mid(c, a)
    return [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]


def _mid(p: Vec3, q: Vec3) -> Vec3:
    return ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, (p[2] + q[2]) / 2)


@dataclass
class RampLines:
    """How bridge and tunnel lines mask shore ramps. ``always``: lines that mask a whole strip wherever it meets
    them (tunnels, bridges without a deck). ``decks``: ``(bridge id, polyline, half width)`` of the lines of
    highway bridges, which only trim a ramp under their at-grade parts; ``undersides`` gives their decks, by id,
    once the water levels are known. A deck line whose bridge has no underside (no deck) masks like ``always``."""
    always: list[Line] = field(default_factory=list)
    decks: list[tuple[str, Sequence[Pt], float]] = field(default_factory=list)
    undersides: Callable[[WaterMax], Mapping[str, DeckUnderside]] = lambda water_max: {}
