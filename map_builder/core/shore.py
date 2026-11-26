# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Shore ramps (S4-COL-FLOAT-2): no flat water sheet hovers over its bank.

The water carve (``water.py``) lowers the terrain around a body to ``CARVE_DEPTH_M`` below its sheet, so the sheet's
edge hangs over a lower bank, and two bodies at different levels leave an open drop between their sheets. Walls
would close both, but every collision class here is an open +Z surface, so each shore edge gets a ramp instead: a
strip from the sheet's edge that falls away at ``RAMP_SLOPE`` until it meets the surface below.

* over the bank the ramp is terrain (``ShoreRamps.bank``), starting ``FREEBOARD_M`` under the sheet;
* over another water body it is a water cascade (``ShoreRamps.cascade``), starting at the sheet itself.

Pure geometry: the caller supplies the surfaces as functions, so this module knows nothing about the water model.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

Pt = tuple[float, float]
Vec3 = tuple[float, float, float]
Tri = tuple[Vec3, Vec3, Vec3]
Surface = Callable[[float, float], float]
Receiver = tuple[str, float]
Trim = Callable[[Tri], list[Tri]]

RAMP_SLOPE = 0.5          # rise / run: the capped slope of an embankment or cascade
FREEBOARD_M = 0.02        # a bank ramp starts this far under the sheet: terrain never pokes through it, yet no gap shows at grazing angles
MAX_WIDTH_M = 12.0        # a ramp that has not met its surface by then ends there, steeper than RAMP_SLOPE
ALONG_STEP_M = 2.0        # shore edges are cut into ramp segments at most this long
ACROSS_STEP_M = 0.5       # the surface below is probed at this spacing away from the shore
CORNER_TOL_M = 1e-6       # consecutive shore edges share their corner within this
FAN_STEP_RAD = math.radians(15)   # a convex corner is covered by cross-sections turning in steps of this
MIN_PLAN_AREA_M2 = 1e-6   # a ramp triangle thinner than this in plan would not face up
MIN_DROP_M = 0.2         # a bank closer than this to the sheet needs no ramp
MIXED_SPLITS = 3          # a strip whose ends differ in kind is halved at most this many times
LEVEL_TOL_M = 1e-6


@dataclass
class ShoreRamps:
    bank: list[Tri] = field(default_factory=list)
    cascade: list[Tri] = field(default_factory=list)
    blocked_m: float = 0.0      # shore length left open, wholly or in part, because a footprint, road or bridge is in the way


def keep_whole(tri: Tri) -> list[Tri]:
    """The ``trim`` that keeps every ramp triangle."""
    return [tri]


@dataclass
class _Node:
    """A ramp cross-section: the sheet edge point, where the ramp ends and the heights there."""
    top: Vec3
    foot: Vec3
    cascade: bool
    source_piece: int
    receiver: str | None = None

    @property
    def width(self) -> float:
        return math.hypot(self.foot[0] - self.top[0], self.foot[1] - self.top[1])


def shore_ramps(edges: Sequence[tuple[Pt, Pt]], level_at: Surface, ground_at: Surface,
                blocked_by: Callable[[Sequence[Pt]], bool], other_level_at: Callable[[float, float], Receiver | None],
                wet_by: Callable[[Sequence[Pt], str | None, int], bool],
                edge_sources: Sequence[int] | None = None, trim: Trim = keep_whole) -> ShoreRamps:
    """Ramps along ``edges`` (water on the left of each p->q). ``level_at``: the body's sheet; ``ground_at``: the
    final terrain; ``blocked_by``: whether a plan triangle overlaps a footprint, road or bridge that must not be
    covered; ``other_level_at``: the receiving water body id and its sheet at a point, or None; ``wet_by``:
    whether a plan triangle overlaps disallowed wet area (a cascade may overlap only its receiving body);
    ``trim``: the parts of a ramp triangle to keep (D178: none under an at-grade deck)."""
    out = ShoreRamps()
    normals = [_right_normal(p, q) for p, q in edges]
    sources = list(edge_sources) if edge_sources is not None and len(edge_sources) == len(edges) else [0] * len(edges)

    def section(pt: Pt, normal: Pt, source_piece: int) -> _Node:
        return _node(pt, normal, level_at, ground_at, other_level_at, source_piece)

    for (p, q), normal, source_piece in zip(edges, normals, sources):
        nodes = [section(pt, normal, source_piece) for pt in _cut(p, q)]
        for a, b in zip(nodes, nodes[1:]):
            for part in _split_mixed(a, b, lambda pt: section(pt, normal, source_piece)):
                _place_strip(out, *part, blocked_by, wet_by, trim)
    for i, (_, corner) in enumerate(edges):
        following = (i + 1) % len(edges)
        if _same_point(corner, edges[following][0]) and _turns_towards_water(normals[i], normals[following]):
            fan = [section(corner, n, sources[i]) for n in _fan_normals(normals[i], normals[following])]
            for a, b in zip(fan, fan[1:]):
                _place_strip(out, a, b, blocked_by, wet_by, trim)
    return out


def _split_mixed(a: _Node, b: _Node, section: Callable[[Pt], _Node], depth: int = MIXED_SPLITS,
                 ) -> list[tuple[_Node, _Node]]:
    """Halve a strip whose ends differ in kind (bank / cascade or receiving body) until each part is one kind.
    A part still mixed after ``depth`` halvings is treated as bank."""
    if (a.cascade, a.receiver) == (b.cascade, b.receiver) or depth == 0:
        return [(a, b)]
    middle = section(((a.top[0] + b.top[0]) / 2, (a.top[1] + b.top[1]) / 2))
    return _split_mixed(a, middle, section, depth - 1) + _split_mixed(middle, b, section, depth - 1)


def _place_strip(out: ShoreRamps, a: _Node, b: _Node, blocked_by: Callable[[Sequence[Pt]], bool],
                 wet_by: Callable[[Sequence[Pt], str | None, int], bool], trim: Trim) -> None:
    """Add the strip between two cross-sections as a cascade (both ends cascade) or a bank ramp. A strip that
    overlaps a footprint, road or bridge, or a bank strip that would cover water, is left out; a strip that loses
    a part to ``trim`` is kept without it. Either way its length counts as blocked."""
    tris = _ramp_tris(a, b)
    if not tris:
        return
    cascade = a.cascade and b.cascade and a.receiver is not None and a.receiver == b.receiver
    plan = [[(v[0], v[1]) for v in t] for t in tris]
    source_piece = a.source_piece if a.source_piece == b.source_piece else a.source_piece
    length = math.hypot(b.top[0] - a.top[0], b.top[1] - a.top[1])
    if any(blocked_by(t) or wet_by(t, a.receiver if cascade else None, source_piece) for t in plan):
        out.blocked_m += length
        return
    kept = [part for t in tris for part in trim(t)]
    if kept != tris:
        out.blocked_m += length
    (out.cascade if cascade else out.bank).extend(kept)



def _same_point(a: Pt, b: Pt) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) < CORNER_TOL_M


def _turns_towards_water(n_in: Pt, n_out: Pt) -> bool:
    """Water is on the left, so a left turn is a convex corner, where the strips of the two edges leave a wedge."""
    return n_in[0] * n_out[1] - n_in[1] * n_out[0] > 0.0


def _fan_normals(n_in: Pt, n_out: Pt) -> list[Pt]:
    """Directions turning from ``n_in`` to ``n_out``, at most ``FAN_STEP_RAD`` apart."""
    angle = math.atan2(n_in[0] * n_out[1] - n_in[1] * n_out[0], n_in[0] * n_out[0] + n_in[1] * n_out[1])
    steps = max(1, math.ceil(angle / FAN_STEP_RAD))
    base = math.atan2(n_in[1], n_in[0])
    return [(math.cos(base + angle * k / steps), math.sin(base + angle * k / steps)) for k in range(steps + 1)]


def _right_normal(p: Pt, q: Pt) -> Pt:
    length = math.hypot(q[0] - p[0], q[1] - p[1])
    return (q[1] - p[1]) / length, -(q[0] - p[0]) / length


def _cut(p: Pt, q: Pt) -> list[Pt]:
    n = max(1, math.ceil(math.hypot(q[0] - p[0], q[1] - p[1]) / ALONG_STEP_M))
    return [(p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n) for k in range(n + 1)]


def _node(pt: Pt, normal: Pt, level_at: Surface, ground_at: Surface,
          other_level_at: Callable[[float, float], Receiver | None], source_piece: int) -> _Node:
    """A bank ramp, or a cascade down to another body where the sheet's edge touches one."""
    sheet = level_at(*pt)
    probe = (pt[0] + normal[0] * ACROSS_STEP_M, pt[1] + normal[1] * ACROSS_STEP_M)
    receiver = other_level_at(*probe)
    if receiver is None or receiver[1] >= sheet - LEVEL_TOL_M:
        return _cross_section(pt, normal, sheet - FREEBOARD_M, ground_at, other_level_at, source_piece, cascade=False)
    return _cross_section(pt, normal, sheet, ground_at, other_level_at, source_piece, cascade=True, receiver=receiver[0])


def _cross_section(pt: Pt, normal: Pt, start: float, ground_at: Surface,
                   other_level_at: Callable[[float, float], Receiver | None], source_piece: int, cascade: bool,
                   receiver: str | None = None) -> _Node:
    """The ramp leaving ``pt`` along ``normal`` from height ``start``, down to the ground. It also ends where it
    reaches another body: a cascade lands on that sheet, so the two sheets meet without a gap; a bank ramp stops."""
    top = (pt[0], pt[1], start)
    if start - ground_at(*pt) < MIN_DROP_M:
        return _Node(top, top, False, source_piece, None)
    if cascade and receiver is not None:
        for k in range(1, round(MAX_WIDTH_M / ACROSS_STEP_M) + 1):
            run = k * ACROSS_STEP_M
            x, y = pt[0] + normal[0] * run, pt[1] + normal[1] * run
            other = other_level_at(x, y)
            if other is not None and other[0] == receiver and other[1] < start - LEVEL_TOL_M:
                return _Node(top, (x, y, other[1]), True, source_piece, receiver)
        return _Node(top, top, False, source_piece, None)
    foot = top
    for k in range(1, round(MAX_WIDTH_M / ACROSS_STEP_M) + 1):
        run = k * ACROSS_STEP_M
        x, y = pt[0] + normal[0] * run, pt[1] + normal[1] * run
        if other_level_at(x, y) is not None:
            return _Node(top, foot, False, source_piece, None)
        surface = ground_at(x, y)
        if start - RAMP_SLOPE * run <= surface or run >= MAX_WIDTH_M:
            return _Node(top, (x, y, surface), False, source_piece, None)
        foot = (x, y, start - RAMP_SLOPE * run)
    raise AssertionError("unreachable")


def _ramp_tris(a: _Node, b: _Node) -> list[Tri]:
    """The strip between two cross-sections as upward-facing triangles; a zero-width end collapses one of them."""
    quad = [(a.top, b.top, b.foot), (a.top, b.foot, a.foot)]
    return [_facing_up(t) for t in quad if abs(_plan_area2(t)) > MIN_PLAN_AREA_M2]


def _plan_area2(t: Tri) -> float:
    (ax, ay, _), (bx, by, _), (cx, cy, _) = t
    return (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)


def _facing_up(t: Tri) -> Tri:
    return t if _plan_area2(t) > 0 else (t[0], t[2], t[1])
