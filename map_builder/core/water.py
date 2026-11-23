# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Flat water surfaces on carved beds (S4-WATER-SURFACE, D113-D118).

Every water body (``natural=water`` and the other area families, plus closed ``waterway=riverbank`` ways) gets its own
mesh, clipped to the area, at a level taken from the pre-carve DEM along its shore (p20 of the 0-2 cell band). A
river of at least 300 m with one consistent ``waterway`` centreline gets an isotonic (non-increasing downstream)
profile instead of one level. The terrain mesh is then carved ``CARVE_DEPTH_M`` below the water wherever it overlaps
a body and blended into the banks, so no terrain triangle is above a water triangle (checked exactly, bounded
remedy, then fallback to today's painted cells). Roads follow the carved terrain mesh, so none hovers over a bed;
buildings, bridges and probes keep using the pre-carve grid.

Pure Python, no I/O. ``generate.py`` calls :func:`build_water` and passes the callbacks that would otherwise make
this module import it.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from .dem import ElevationGrid
from .errors import LimitError, MapBuilderError
from .mesh import MeshData
from .osm import Feature, Polygon, point_in_ring
from .triangulate import TriangulationError, clean_ring, dedupe_ring, triangulate

Pt = tuple[float, float]
Tri = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

N_MIN = 8                      # minimum shore samples
CARVE_DEPTH_M = 1.5            # D: the bed lies at least this far below the water
BAND_CELLS = (0.5, 1.0, 1.5, 2.0)
WIDE_BAND_CELLS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0)
SAMPLE_STEP_M = 5.0
PERCENTILE = 20.0
PROFILE_MIN_LENGTH_M = 300.0
STATION_LENGTH_M = 100.0
SLOPE_CAP = 0.01
BLEND_CELLS = 1
REMEDY_ROUNDS = 2
REMEDY_MARGIN_M = 0.01
VIOLATION_TOL_M = 1e-9
AREA_EPS = 1e-9
WATER_COLOR = (0.05, 0.14, 0.24)
MATERIAL = "MB Water"
SAMPLE_MASK_BUFFER_M = 15.0   # dsm.BUILDING_BUFFER_M / BRIDGE_BUFFER_M: the DSM mask the samples avoid


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile (the numpy default)."""
    v = sorted(values)
    if not v:
        raise ValueError("no values")
    pos = (len(v) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


# --- 2D helpers -----------------------------------------------------------------------------------------------

def _area2(poly: Sequence[Pt]) -> float:
    return sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1]
               for k in range(len(poly))) / 2.0


def _lerp_canon(a: Pt, b: Pt, t: float) -> Pt:
    """Point at ``t`` along a->b, computed from the endpoints in sorted order so that the two triangles sharing an
    edge produce the identical point (no T-junctions, welded vertices)."""
    if b < a:
        a, b, t = b, a, 1.0 - t
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _clip_half(poly: Sequence[Pt], nx: float, ny: float, c: float, keep_ge: bool) -> list[Pt]:
    """Keep the part of convex ``poly`` where nx*x + ny*y >= c (or <= c). Intersections are canonical."""
    out: list[Pt] = []
    sgn = 1.0 if keep_ge else -1.0
    n = len(poly)
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        da = sgn * (nx * a[0] + ny * a[1] - c)
        db = sgn * (nx * b[0] + ny * b[1] - c)
        if da >= 0:
            out.append(a)
        if (da > 0 and db < 0) or (da < 0 and db > 0):
            out.append(_lerp_canon(a, b, da / (da - db)))
    return out


def _clip_poly_tri(poly: Sequence[Pt], tri: Sequence[Pt]) -> list[Pt]:
    """Convex ``poly`` clipped to the CCW triangle ``tri``."""
    for k in range(3):
        a, b = tri[k], tri[(k + 1) % 3]
        # left of a->b: cross >= 0  <=>  -(dy)*x + dx*y >= -dy*ax + dx*ay
        dx, dy = b[0] - a[0], b[1] - a[1]
        poly = _clip_half(poly, -dy, dx, -dy * a[0] + dx * a[1], True)
        if len(poly) < 3:
            return []
    return list(poly)


def _clip_rect_poly(poly: Sequence[Pt], x0: float, y0: float, x1: float, y1: float) -> list[Pt]:
    p = _clip_half(poly, 1.0, 0.0, x0, True)
    if len(p) >= 3:
        p = _clip_half(p, 1.0, 0.0, x1, False)
    if len(p) >= 3:
        p = _clip_half(p, 0.0, 1.0, y0, True)
    if len(p) >= 3:
        p = _clip_half(p, 0.0, 1.0, y1, False)
    return p if len(p) >= 3 else []


class _Plane:
    """z = a*x + b*y + c through three points (a CCW triangle)."""
    __slots__ = ("a", "b", "c")

    def __init__(self, tri: Tri) -> None:
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri
        d = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if d == 0:
            self.a = self.b = 0.0
            self.c = (z0 + z1 + z2) / 3.0
            return
        self.a = ((z1 - z0) * (y2 - y0) - (z2 - z0) * (y1 - y0)) / d
        self.b = ((x1 - x0) * (z2 - z0) - (x2 - x0) * (z1 - z0)) / d
        self.c = z0 - self.a * x0 - self.b * y0

    def at(self, x: float, y: float) -> float:
        return self.a * x + self.b * y + self.c


def _in_tri(tri: Sequence[Pt], x: float, y: float) -> bool:
    for k in range(3):
        a, b = tri[k], tri[(k + 1) % 3]
        if (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]) < 0:
            return False
    return True


class _Index:
    """Uniform-grid index of bboxes (cell size ``cell`` m)."""

    def __init__(self, cell: float = 40.0) -> None:
        self.cell = cell
        self.map: dict[tuple[int, int], list[int]] = {}

    def add(self, key: int, box: tuple[float, float, float, float]) -> None:
        c = self.cell
        for i in range(int(math.floor(box[0] / c)), int(math.floor(box[2] / c)) + 1):
            for j in range(int(math.floor(box[1] / c)), int(math.floor(box[3] / c)) + 1):
                self.map.setdefault((i, j), []).append(key)

    def at(self, x: float, y: float) -> Sequence[int]:
        return self.map.get((int(math.floor(x / self.cell)), int(math.floor(y / self.cell))), ())


# --- Clipping a polygon with holes to the terrain rectangle ---------------------------------------------------------

Rect = tuple[float, float, float, float]


def _lb(a: Pt, b: Pt, r: Rect) -> tuple[float, float] | None:
    """Liang-Barsky: parameter interval of segment a->b inside the closed rectangle, or None."""
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - r[0]), (dx, r[2] - a[0]), (-dy, a[1] - r[1]), (dy, r[3] - a[1])):
        if p == 0:
            if q < 0:
                return None
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return None
                t0 = max(t0, t)
            else:
                if t < t0:
                    return None
                t1 = min(t1, t)
    return (t0, t1) if t0 <= t1 else None


def _snap(p: Pt, r: Rect) -> Pt:
    x, y = p
    for v in (r[0], r[2]):
        if abs(x - v) < 1e-7:
            x = v
    for v in (r[1], r[3]):
        if abs(y - v) < 1e-7:
            y = v
    return (x, y)


def _u(p: Pt, r: Rect) -> float:
    """Perimeter coordinate of a boundary point, CCW from the lower-left corner."""
    w, h = r[2] - r[0], r[3] - r[1]
    x, y = p
    if y == r[1] and x < r[2]:
        return x - r[0]
    if x == r[2] and y < r[3]:
        return w + (y - r[1])
    if y == r[3] and x > r[0]:
        return w + h + (r[2] - x)
    return 2 * w + h + (r[3] - y)


def _ring_chains(ring: Sequence[Pt], r: Rect) -> tuple[list[list[Pt]], bool]:
    """(chains, inside): the parts of ``ring`` inside ``r`` as entry..exit polylines (the ring's own direction), or,
    if the ring has no part crossing the boundary, ``inside`` = True when it lies entirely inside."""
    n = len(ring)

    def outside(p: Pt) -> bool:
        return not (r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3])

    start = next((k for k in range(n) if outside(ring[k])), None)
    if start is None:
        return [], True
    chains: list[list[Pt]] = []
    cur: list[Pt] | None = None
    for m in range(n):
        k = (start + m) % n
        a, b = ring[k], ring[(k + 1) % n]
        iv = _lb(a, b, r)
        if iv is None or iv[1] - iv[0] < 1e-12:
            continue
        t0, t1 = iv
        dx, dy = b[0] - a[0], b[1] - a[1]
        if t0 > 1e-12 or cur is None:
            cur = [_snap((a[0] + t0 * dx, a[1] + t0 * dy), r)]
        if t1 < 1.0 - 1e-12:
            cur.append(_snap((a[0] + t1 * dx, a[1] + t1 * dy), r))
            chains.append(cur)
            cur = None
        else:
            cur.append(b)
    return chains, False


def clip_polygon(poly: Polygon, r: Rect) -> list[tuple[list[Pt], list[list[Pt]]]] | None:
    """``poly`` (outer CCW, holes CW) clipped to rectangle ``r`` as (outer, holes) pieces, each CCW / CW with
    exactly the polygon's boundary inside ``r`` plus the rectangle edges. None if the clip is not
    well-formed (degenerate contacts), so the caller can report it. Empty list: nothing inside."""
    rings = [list(dedupe_ring(poly.outer))] + [list(dedupe_ring(h)) for h in poly.holes]
    chains: list[list[Pt]] = []
    inside_rings: list[list[Pt]] = []
    for ring in rings:
        ch, inside = _ring_chains(ring, r)
        if inside:
            inside_rings.append(ring)
        chains.extend(ch)
    loops: list[list[Pt]] = []
    if chains:
        w, h = r[2] - r[0], r[3] - r[1]
        per = 2 * (w + h)
        corners = [(r[0], r[1], 0.0), (r[2], r[1], w), (r[2], r[3], w + h), (r[0], r[3], 2 * w + h)]
        ents = sorted(range(len(chains)), key=lambda i: (_u(chains[i][0], r), i))
        eu = [_u(chains[i][0], r) for i in ents]
        nxt: dict[int, int] = {}
        for i, c in enumerate(chains):
            ux = _u(c[-1], r)
            best = min(range(len(ents)), key=lambda k: ((eu[k] - ux) % per, ents[k]))
            nxt[i] = ents[best]
        if sorted(nxt.values()) != list(range(len(chains))):
            return None
        seen: set[int] = set()
        for i0 in range(len(chains)):
            if i0 in seen:
                continue
            loop: list[Pt] = []
            i = i0
            while i not in seen:
                seen.add(i)
                loop.extend(chains[i])
                j = nxt[i]
                u0, u1 = _u(chains[i][-1], r), _u(chains[j][0], r)
                span = (u1 - u0) % per
                for cx, cy, cu in sorted(corners, key=lambda c: (c[2] - u0) % per):
                    if 0.0 < (cu - u0) % per < span:
                        loop.append((cx, cy))
                i = j
            loops.append(loop)
    elif poly.contains(r[0], r[1]):
        loops.append([(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])])
    loops.extend(inside_rings)
    outers: list[list[Pt]] = []
    holes: list[list[Pt]] = []
    for lp in loops:
        lp = clean_ring(dedupe_ring(lp), 1e-9)
        if len(lp) < 3:
            continue
        a = _area2(lp)
        if abs(a) < AREA_EPS:
            continue
        (outers if a > 0 else holes).append(lp)
    out: list[tuple[list[Pt], list[list[Pt]]]] = [(o, []) for o in outers]
    for hl in holes:
        for o, hs in out:
            if point_in_ring(hl[0][0], hl[0][1], o):
                hs.append(hl)
                break
        else:
            return None
    return out


# --- Level model ---------------------------------------------------------------------------------------------

@dataclass
class Level:
    """Water surface z(x, y): constant, or piecewise linear in the arc length t of the projection on ``chain``."""
    flat: float | None = None
    chain: list[Pt] = field(default_factory=list)
    cum: list[float] = field(default_factory=list)
    st_t: list[float] = field(default_factory=list)       # station centres (arc length)
    st_z: list[float] = field(default_factory=list)       # station levels, non-increasing

    def param(self, x: float, y: float) -> float:
        best, bt = float("inf"), 0.0
        for k in range(len(self.chain) - 1):
            a, b = self.chain[k], self.chain[k + 1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ll = dx * dx + dy * dy
            u = 0.0 if ll == 0 else min(1.0, max(0.0, ((x - a[0]) * dx + (y - a[1]) * dy) / ll))
            d = (x - a[0] - u * dx) ** 2 + (y - a[1] - u * dy) ** 2
            if d < best:
                best, bt = d, self.cum[k] + u * math.sqrt(ll)
        return bt

    def at(self, x: float, y: float) -> float:
        if self.flat is not None:
            return self.flat
        t = self.param(x, y)
        ts, zs = self.st_t, self.st_z
        if t <= ts[0]:
            return zs[0]
        if t >= ts[-1]:
            return zs[-1]
        for k in range(len(ts) - 1):
            if t <= ts[k + 1]:
                f = (t - ts[k]) / (ts[k + 1] - ts[k])
                return zs[k] + f * (zs[k + 1] - zs[k])
        return zs[-1]

    def cut_lines(self) -> list[tuple[float, float, float]]:
        """(nx, ny, c) half-plane lines nx*x+ny*y = c perpendicular to the chain at each interior station centre."""
        out = []
        if self.flat is not None:
            return out
        for t in self.st_t:
            k = next((i for i in range(len(self.cum) - 1) if t <= self.cum[i + 1]), len(self.chain) - 2)
            a, b = self.chain[k], self.chain[k + 1]
            ll = math.hypot(b[0] - a[0], b[1] - a[1])
            ux, uy = (b[0] - a[0]) / ll, (b[1] - a[1]) / ll
            f = t - self.cum[k]
            px, py = a[0] + ux * f, a[1] + uy * f
            out.append((ux, uy, ux * px + uy * py))
        return out

    def min_over(self, pts: Iterable[Pt]) -> float:
        return min(self.at(x, y) for x, y in pts)


def _segment_inside(a: Pt, b: Pt, pieces: Sequence[tuple[list[Pt], list[list[Pt]]]]) -> list[tuple[float, float]]:
    """Parameter intervals of segment a->b inside the clipped pieces (exact crossings with the ring edges)."""
    ts = [0.0, 1.0]
    dx, dy = b[0] - a[0], b[1] - a[1]
    for outer, holes in pieces:
        for ring in [outer] + holes:
            n = len(ring)
            for k in range(n):
                c, d = ring[k], ring[(k + 1) % n]
                ex, ey = d[0] - c[0], d[1] - c[1]
                den = dx * ey - dy * ex
                if den == 0:
                    continue
                t = ((c[0] - a[0]) * ey - (c[1] - a[1]) * ex) / den
                s = ((c[0] - a[0]) * dy - (c[1] - a[1]) * dx) / den
                if 0.0 < t < 1.0 and 0.0 <= s <= 1.0:
                    ts.append(t)
    ts.sort()
    out: list[tuple[float, float]] = []
    for t0, t1 in zip(ts, ts[1:]):
        if t1 - t0 < 1e-12:
            continue
        m = (t0 + t1) / 2
        x, y = a[0] + dx * m, a[1] + dy * m
        if any(point_in_ring(x, y, o) and not any(point_in_ring(x, y, h) for h in hs) for o, hs in pieces):
            if out and abs(out[-1][1] - t0) < 1e-12:
                out[-1] = (out[-1][0], t1)
            else:
                out.append((t0, t1))
    return out


# --- Bodies ----------------------------------------------------------------------------------------------

@dataclass
class Body:
    id: str
    polygon: Polygon
    kind: str                                   # "area" | "riverbank"
    pieces: list[tuple[list[Pt], list[list[Pt]]]] = field(default_factory=list)
    outcome: str = ""
    notes: list[str] = field(default_factory=list)
    level: Level | None = None
    tris: list[Tri] = field(default_factory=list)          # absolute z
    shore: list[tuple[Pt, Pt]] = field(default_factory=list)   # clipped-ring edges that are polygon edges
    carve: dict[int, float] = field(default_factory=dict)
    blend: dict[int, float] = field(default_factory=dict)
    info: dict[str, object] = field(default_factory=dict)
    mesh_counts: tuple[int, int] = (0, 0)

    @property
    def built(self) -> bool:
        return self.outcome.startswith("built")


def _body_box(b: Body) -> tuple[float, float, float, float]:
    xs = [p[0] for o, _ in b.pieces for p in o]
    ys = [p[1] for o, _ in b.pieces for p in o]
    return min(xs), min(ys), max(xs), max(ys)


def _inside_pieces(b: Body, x: float, y: float) -> bool:
    for o, hs in b.pieces:
        if point_in_ring(x, y, o) and not any(point_in_ring(x, y, h) for h in hs):
            return True
    return False


@dataclass
class WaterModel:
    """Result of :func:`build_water`: the carved grid, per-body outcomes and the emitted triangles."""
    grid: ElevationGrid                 # pre-carve ground (unchanged)
    carved: ElevationGrid               # terrain mesh heights
    bodies: list[Body]
    z_offset: float = 0.0
    _tri_index: dict[tuple[int, int], list[tuple[int, int]]] = field(default_factory=dict)

    def active(self) -> list[Body]:
        return [b for b in self.bodies if b.built]

    def _build_index(self) -> None:
        g = self.grid
        self._tri_index = {}
        for bi, b in enumerate(self.bodies):
            if not b.built:
                continue
            for ti, t in enumerate(b.tris):
                xs, ys = [p[0] for p in t], [p[1] for p in t]
                i0, i1, j0, j1 = _cells(g, min(xs), max(xs), min(ys), max(ys))
                for i in range(i0, i1 + 1):
                    for j in range(j0, j1 + 1):
                        self._tri_index.setdefault((i, j), []).append((bi, ti))

    def _tris_near(self, x0: float, x1: float, y0: float, y1: float) -> Iterable[Tri]:
        g = self.grid
        i0, i1, j0, j1 = _cells(g, x0, x1, y0, y1)
        seen: set[tuple[int, int]] = set()
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                for key in self._tri_index.get((i, j), ()):
                    if key not in seen:
                        seen.add(key)
                        yield self.bodies[key[0]].tris[key[1]]

    def touches_water(self, poly: Sequence[Pt]) -> bool:
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        for t in self._tris_near(min(xs), max(xs), min(ys), max(ys)):
            if len(_clip_poly_tri(poly, [(t[0][0], t[0][1]), (t[1][0], t[1][1]), (t[2][0], t[2][1])])) >= 3:
                return True
        return False

    def wmax_polygon(self, poly: Sequence[Pt]) -> float | None:
        """Exact maximum water level over convex CCW ``poly`` (None if no water under it)."""
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        best: float | None = None
        for t in self._tris_near(min(xs), max(xs), min(ys), max(ys)):
            clip = _clip_poly_tri(poly, [(t[0][0], t[0][1]), (t[1][0], t[1][1]), (t[2][0], t[2][1])])
            if len(clip) < 3 or abs(_area2(clip)) < AREA_EPS:
                continue
            pl = _Plane(t)
            m = max(pl.at(x, y) for x, y in clip)
            if best is None or m > best:
                best = m
        return best

    def wmax_segment(self, a: Pt, b: Pt) -> float | None:
        """Exact maximum water level along segment a-b: the maximum over its intersections with the water
        triangles (its endpoints inside water and its crossings of triangle edges are the interval ends)."""
        best: float | None = None
        for t in self._tris_near(min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])):
            tri = [(t[0][0], t[0][1]), (t[1][0], t[1][1]), (t[2][0], t[2][1])]
            t0, t1 = 0.0, 1.0
            dx, dy = b[0] - a[0], b[1] - a[1]
            for k in range(3):
                p, q = tri[k], tri[(k + 1) % 3]
                ex, ey = q[0] - p[0], q[1] - p[1]
                f0 = ex * (a[1] - p[1]) - ey * (a[0] - p[0])       # >= 0 inside
                fd = ex * dy - ey * dx
                if fd == 0:
                    if f0 < 0:
                        t0, t1 = 1.0, 0.0
                        break
                    continue
                s = -f0 / fd
                if fd > 0:
                    t0 = max(t0, s)
                else:
                    t1 = min(t1, s)
                if t0 > t1:
                    break
            if t0 > t1:
                continue
            pl = _Plane(t)
            m = max(pl.at(a[0] + dx * t0, a[1] + dy * t0), pl.at(a[0] + dx * t1, a[1] + dy * t1))
            if best is None or m > best:
                best = m
        return best

    def ground_max_polygon(self, poly: Sequence[Pt]) -> float:
        """Exact maximum of the pre-carve ground over convex CCW ``poly``."""
        g = self.grid
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        i0, i1, j0, j1 = _cells(g, min(xs), max(xs), min(ys), max(ys))
        best = -float("inf")
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                for tri in _cell_tris(g, i, j, g.heights):
                    clip = _clip_poly_tri(poly, [(p[0], p[1]) for p in tri])
                    if len(clip) < 3:
                        continue
                    pl = _Plane(tri)
                    best = max(best, max(pl.at(x, y) for x, y in clip))
        return best

    def carved_min_polygon(self, poly: Sequence[Pt]) -> float:
        """Lowest carved terrain (mesh vertices and triangle clips) under convex ``poly``."""
        g = self.carved
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        i0, i1, j0, j1 = _cells(g, min(xs), max(xs), min(ys), max(ys))
        best = float("inf")
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                for tri in _cell_tris(g, i, j, g.heights):
                    clip = _clip_poly_tri(poly, [(p[0], p[1]) for p in tri])
                    if len(clip) < 3:
                        continue
                    pl = _Plane(tri)
                    best = min(best, min(pl.at(x, y) for x, y in clip))
        return best

    def mesh(self, body: Body) -> MeshData:
        """The body's ``MB Water`` mesh (local z = absolute - z_offset; welded vertices; normals +Z)."""
        m = MeshData(f"water:{body.id}")
        idx: dict[tuple[float, float, float], int] = {}  # welded to 1 um: platform libm differences must not change the vertex set
        for t in body.tris:
            ids = []
            for x, y, z in t:
                key = (round(x, 6), round(y, 6), round(z, 6))
                if key not in idx:
                    idx[key] = m.add_vertex(x, y, z - self.z_offset)
                ids.append(idx[key])
            m.add_face(tuple(ids), MATERIAL, WATER_COLOR)
        return m


def _cells(g: ElevationGrid, x0: float, x1: float, y0: float, y1: float) -> tuple[int, int, int, int]:
    s = g.spacing
    return (max(0, int(math.floor((x0 - g.x0) / s))), min(g.nx - 2, int(math.floor((x1 - g.x0) / s))),
            max(0, int(math.floor((y0 - g.y0) / s))), min(g.ny - 2, int(math.floor((y1 - g.y0) / s))))


def _cell_tris(g: ElevationGrid, i: int, j: int, h: list[list[float]]) -> list[Tri]:
    s = g.spacing
    x0, y0 = g.x0 + i * s, g.y0 + j * s
    x1, y1 = x0 + s, y0 + s
    a, b, c, d = (x0, y0, h[j][i]), (x1, y0, h[j][i + 1]), (x1, y1, h[j + 1][i + 1]), (x0, y1, h[j + 1][i])
    return [(a, b, c), (a, c, d)]


# --- Shore samples --------------------------------------------------------------------------------------------

def _edge_samples(ring: Sequence[Pt], r: Rect, step: float) -> list[tuple[Pt, Pt]]:
    """(point, outward normal) every ``step`` m of ring arc length from the ring's first vertex, only on the parts
    inside ``r`` (clipped edges are not shoreline). Outward = the right of the direction (outer rings and holes)."""
    out: list[tuple[Pt, Pt]] = []
    n = len(ring)
    s0 = 0.0
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln == 0:
            continue
        iv = _lb(a, b, r)
        if iv is not None:
            nxv, nyv = dy / ln, -dx / ln
            m = int(math.ceil(s0 / step - 1e-12))
            while m * step < s0 + ln:
                t = (m * step - s0) / ln
                if iv[0] <= t <= iv[1]:
                    out.append(((a[0] + t * dx, a[1] + t * dy), (nxv, nyv)))
                m += 1
        s0 += ln
    return out


@dataclass
class _Masks:
    """Things the shore samples avoid and the bank blend must not undercut."""
    footprints: list[Polygon]
    lines: list[tuple[list[Pt], float]]          # (polyline, half width + margin)
    foot_idx: _Index = field(default_factory=_Index)
    line_idx: _Index = field(default_factory=_Index)

    def build(self) -> None:
        for i, p in enumerate(self.footprints):
            b = p.bbox()
            self.foot_idx.add(i, (b[0] - SAMPLE_MASK_BUFFER_M, b[1] - SAMPLE_MASK_BUFFER_M,
                                  b[2] + SAMPLE_MASK_BUFFER_M, b[3] + SAMPLE_MASK_BUFFER_M))
        for i, (pl, hw) in enumerate(self.lines):
            xs, ys = [p[0] for p in pl], [p[1] for p in pl]
            self.line_idx.add(i, (min(xs) - hw, min(ys) - hw, max(xs) + hw, max(ys) + hw))

    def hit_footprint(self, x: float, y: float, buffer: float) -> bool:
        for i in self.foot_idx.at(x, y):
            p = self.footprints[i]
            if p.contains(x, y):
                return True
            if buffer > 0 and _dist_ring(x, y, p.outer) <= buffer:
                return True
        return False

    def hit_line(self, x: float, y: float, extra: float) -> bool:
        for i in self.line_idx.at(x, y):
            pl, hw = self.lines[i]
            for k in range(len(pl) - 1):
                if _dist_seg(x, y, pl[k], pl[k + 1]) <= hw + extra:
                    return True
        return False


def _dist_seg(x: float, y: float, a: Pt, b: Pt) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    ll = dx * dx + dy * dy
    u = 0.0 if ll == 0 else min(1.0, max(0.0, ((x - a[0]) * dx + (y - a[1]) * dy) / ll))
    return math.hypot(x - a[0] - u * dx, y - a[1] - u * dy)


def _dist_ring(x: float, y: float, ring: Sequence[Pt]) -> float:
    return min(_dist_seg(x, y, ring[k], ring[(k + 1) % len(ring)]) for k in range(len(ring)))


# --- The builder ----------------------------------------------------------------------------------------------

def build_water(grid: ElevationGrid, z_offset: float, areas: Sequence[Feature], riverbanks: Sequence[Feature],
                waterways: Sequence[Feature], footprints: Sequence[Polygon], lines: Sequence[tuple[Sequence[Pt], float]],
                road_lines: Sequence[tuple[Sequence[Pt], float]], extent: Rect,
                ring_problem: Callable[[Polygon], str | None],
                charge: Callable[[str, int, int], None] | None = None,
                refund: Callable[[int, int], None] | None = None,
                carve_depth: float = CARVE_DEPTH_M) -> WaterModel:
    """Build the water bodies and the carved terrain grid.

    ``areas``: validated water landcover features. ``riverbanks``/``waterways``: ``ClassifiedOSM`` lists.
    ``footprints``: building polygons and ``lines``: (polyline, half width) of bridges and tunnels, both used to
    discard shore samples. ``road_lines``: roads (and the lines above) the bank blend must not undercut.
    ``extent``: terrain extent (x0, y0, x1, y1). ``charge``/``refund``: triangle-budget callbacks (LimitError means
    refusal). ``carve_depth`` exists for tests."""
    s = grid.spacing
    bodies: list[Body] = []
    for f in areas:
        if f.tags.get("_class") == "water":
            bodies.append(Body(f.id, f.geometry, "area"))
    taken = {b.id for b in bodies}
    for f in riverbanks:
        if f.id in taken:
            continue
        taken.add(f.id)
        problem = ring_problem(f.geometry)
        if problem is None:
            bodies.append(Body(f.id, f.geometry, "riverbank"))
    bodies.sort(key=lambda b: b.id)
    model = WaterModel(grid, grid, bodies, z_offset)
    if not bodies:
        return model

    masks = _Masks(list(footprints), [(list(pl), hw + SAMPLE_MASK_BUFFER_M) for pl, hw in lines])
    masks.build()
    blend_masks = _Masks(list(footprints), [(list(pl), hw + 1.0) for pl, hw in list(road_lines) + list(lines)])
    blend_masks.build()

    # 1. clip to the terrain rectangle
    for b in bodies:
        try:
            pieces = clip_polygon(b.polygon, extent)
        except (ValueError, ArithmeticError):
            pieces = None
        if pieces is None:
            b.outcome = "fallback(no shore samples)"
            b.notes.append("clip to the terrain extent failed")
            continue
        b.pieces = pieces
        if not pieces:
            b.outcome = "fallback(no shore samples)"
            b.notes.append("no part inside the terrain extent")

    # 2. shore samples, level, triangles
    for b in bodies:
        if b.outcome:
            continue
        _make_level(b, grid, extent, bodies, masks, waterways, s)
        if not b.built:
            continue
        try:
            _triangulate_body(b)
        except TriangulationError as e:
            b.outcome = "fallback(no shore samples)"
            b.notes.append(f"clipped polygon could not be triangulated: {e}")
            b.level = None
            continue

    # 3. budget: ascending id, exact counts
    for b in bodies:
        if not b.built:
            continue
        nv = len({(round(x, 6), round(y, 6), round(z, 6)) for t in b.tris for x, y, z in t})
        b.mesh_counts = (nv, len(b.tris))
        if charge is not None:
            try:
                charge(f"water:{b.id}", nv, len(b.tris))
            except LimitError as e:
                b.outcome = "fallback(budget)"
                b.notes.append(str(e))
                b.tris = []
                continue
    model._build_index()

    # 4. carve, invariant, fallbacks (always recomputed from the pre-carve ground)
    cut = _CarveContext(model, blend_masks, carve_depth)
    cut.prepare()
    cut.settle(refund)
    model._build_index()
    return model


def _make_level(b: Body, grid: ElevationGrid, extent: Rect, all_bodies: Sequence[Body], masks: _Masks,
                waterways: Sequence[Feature], s: float) -> None:
    # shore edges and samples
    rings = [dedupe_ring(b.polygon.outer)] + [dedupe_ring(h) for h in b.polygon.holes]
    for o, hs in b.pieces:
        for ring in [o] + hs:
            n = len(ring)
            for k in range(n):
                p, q = ring[k], ring[(k + 1) % n]
                on_edge = ((p[0] == q[0] and p[0] in (extent[0], extent[2]))
                           or (p[1] == q[1] and p[1] in (extent[1], extent[3])))
                if not on_edge:
                    b.shore.append((p, q))

    def collect(cells: Sequence[float]) -> list[tuple[float, float, float]]:
        out: list[tuple[float, float, float]] = []
        for ring in rings:
            for (px, py), (nx, ny) in _edge_samples(ring, extent, SAMPLE_STEP_M):
                for c in cells:
                    x, y = px + nx * c * s, py + ny * c * s
                    if not (extent[0] <= x <= extent[2] and extent[1] <= y <= extent[3]):
                        continue
                    if masks.hit_footprint(x, y, SAMPLE_MASK_BUFFER_M) or masks.hit_line(x, y, 0.0):
                        continue
                    if any(_inside_pieces(o, x, y) for o in all_bodies if o.pieces):
                        continue
                    out.append((x, y, _ground(grid, x, y)))
        return out

    samples = collect(BAND_CELLS)
    wide = False

    def flat_level(smp: list[tuple[float, float, float]]) -> bool:
        nonlocal samples, wide
        if len(smp) < N_MIN and not wide:
            wide = True
            samples = collect(WIDE_BAND_CELLS)
            smp = samples
        if len(smp) < N_MIN:
            b.outcome = "fallback(no shore samples)"
            b.notes.append(f"{len(smp)} shore samples (< {N_MIN})")
            return False
        zs = [z for _, _, z in smp]
        lv = percentile(zs, PERCENTILE)
        p5, p50 = percentile(zs, 5.0), percentile(zs, 50.0)
        b.level = Level(flat=lv)
        b.outcome = "built(flat)"
        b.info.update(samples=len(smp), level_m=round(lv, 4), p5=round(p5, 3), p50=round(p50, 3),
                      band_cells=4 if wide else 2,
                      shore_percentiles={q: round(percentile(zs, q), 3) for q in (5, 10, 20, 30, 50)})
        if not (p5 - 1e-9 <= lv <= p50 + 1e-9):
            b.info["sanity_miss"] = True
            b.notes.append("sanity window miss")
        return True

    chain, why = _centreline(b, waterways)
    if chain is None:
        if why:
            b.notes.append(why)
        flat_level(samples)
        return
    pts, cum, s_in, s_out, inside_len = chain
    if inside_len < PROFILE_MIN_LENGTH_M:
        flat_level(samples)
        return
    lvl = Level(chain=pts, cum=cum)
    # stations
    span = s_out - s_in
    n = max(1, int(span // STATION_LENGTH_M))
    if span - n * STATION_LENGTH_M >= STATION_LENGTH_M / 2:
        n += 1
    bounds = [s_in + k * STATION_LENGTH_M for k in range(n)] + [s_out]
    groups: list[list[tuple[float, float, float]]] = [[] for _ in range(n)]
    for smp in samples:
        t = lvl.param(smp[0], smp[1])
        k = min(n - 1, max(0, int(math.ceil((t - s_in) / STATION_LENGTH_M)) - 1))
        groups[k].append(smp)
    ranges = [[bounds[k], bounds[k + 1]] for k in range(n)]
    while len(groups) > 1:
        small = next((k for k, g in enumerate(groups) if len(g) < N_MIN), None)
        if small is None:
            break
        tgt = small + 1 if small + 1 < len(groups) else small - 1
        lo, hi = min(small, tgt), max(small, tgt)
        groups[lo] = groups[lo] + groups[hi]
        ranges[lo] = [ranges[lo][0], ranges[hi][1]]
        del groups[hi], ranges[hi]
    if len(groups) == 1:
        flat_level(samples)
        return
    zs = [[z for _, _, z in g] for g in groups]
    lv = [percentile(z, PERCENTILE) for z in zs]
    wt = [float(len(z)) for z in zs]
    blocks = _pav(lv, wt)
    centres = [(r[0] + r[1]) / 2 for r in ranges]
    final = [lv[k] for k in range(len(lv))]
    for lo, hi, val in blocks:
        for k in range(lo, hi + 1):
            final[k] = val
    for k in range(len(final) - 1):
        if abs(final[k + 1] - final[k]) / (centres[k + 1] - centres[k]) > SLOPE_CAP + 1e-12:
            b.notes.append("profile slope > 1 %")
            flat_level(samples)
            return
    miss = False
    for lo, hi, val in blocks:
        lo_b = min(percentile(zs[k], 5.0) for k in range(lo, hi + 1))
        hi_b = max(percentile(zs[k], 50.0) for k in range(lo, hi + 1))
        if not (lo_b - 1e-9 <= val <= hi_b + 1e-9):
            miss = True
    lvl.st_t, lvl.st_z = centres, final
    b.level = lvl
    b.outcome = f"built(profile, {len(groups)} stations)"
    b.info.update(samples=len(samples), stations=len(groups), levels_m=[round(z, 4) for z in final],
                  station_samples=[len(g) for g in groups], chain_length_m=round(inside_len, 2),
                  band_cells=2)
    if miss:
        b.info["sanity_miss"] = True
        b.notes.append("sanity window miss")


def _ground(grid: ElevationGrid, x: float, y: float) -> float:
    s = grid.spacing
    fx = min(max((x - grid.x0) / s, 0.0), grid.nx - 1.000001)
    fy = min(max((y - grid.y0) / s, 0.0), grid.ny - 1.000001)
    i, j = int(fx), int(fy)
    tx, ty = fx - i, fy - j
    h = grid.heights
    if ty > tx:   # upper triangle (v00, v11, v01)
        return h[j][i] + (h[j + 1][i + 1] - h[j + 1][i]) * tx + (h[j + 1][i] - h[j][i]) * ty
    return h[j][i] + (h[j][i + 1] - h[j][i]) * tx + (h[j + 1][i + 1] - h[j][i + 1]) * ty


def _pav(vals: Sequence[float], wts: Sequence[float]) -> list[tuple[int, int, float]]:
    """Pool-adjacent-violators for a non-increasing sequence: [(first, last, value)] blocks, weighted means."""
    blocks: list[list[float]] = []   # [lo, hi, weight*value, weight]
    for k, (v, w) in enumerate(zip(vals, wts)):
        blocks.append([k, k, v * w, w])
        while len(blocks) > 1 and blocks[-2][2] / blocks[-2][3] < blocks[-1][2] / blocks[-1][3]:
            last = blocks.pop()
            blocks[-1] = [blocks[-1][0], last[1], blocks[-1][2] + last[2], blocks[-1][3] + last[3]]
    return [(int(b[0]), int(b[1]), b[2] / b[3]) for b in blocks]


def _centreline(b: Body, waterways: Sequence[Feature]):
    """((points, cumulative length, s_in, s_out, length inside), note) of the single consistent chain of
    waterway parts with >= 50 % of their length inside the body, or (None, note|None) for a flat body."""
    parts: list[Feature] = []
    for f in sorted(waterways, key=lambda w: w.id):
        pts = f.geometry
        tot = ins = 0.0
        for a, c in zip(pts, pts[1:]):
            ln = math.hypot(c[0] - a[0], c[1] - a[1])
            tot += ln
            ins += ln * sum(t1 - t0 for t0, t1 in _segment_inside(a, c, b.pieces))
        if tot > 0 and ins >= 0.5 * tot:
            parts.append(f)
    if not parts:
        return None, None
    if any(p.node_ids is None or p.node_ids[0] is None or p.node_ids[-1] is None for p in parts) and len(parts) > 1:
        return None, "ambiguous centreline"
    chain = _chain_parts(parts)
    if chain is None:
        return None, "ambiguous centreline"
    pts = chain
    cum = [0.0]
    for a, c in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(c[0] - a[0], c[1] - a[1]))
    s_in = s_out = None
    inside = 0.0
    for k, (a, c) in enumerate(zip(pts, pts[1:])):
        ln = cum[k + 1] - cum[k]
        for t0, t1 in _segment_inside(a, c, b.pieces):
            if s_in is None:
                s_in = cum[k] + t0 * ln
            s_out = cum[k] + t1 * ln
            inside += (t1 - t0) * ln
    if s_in is None or s_out is None:
        return None, None
    return (pts, cum, s_in, s_out, inside), None


def _chain_parts(parts: Sequence[Feature]) -> list[Pt] | None:
    """Concatenate parts end to start by node id; None if more than one chain or a part is reversed."""
    if len(parts) == 1:
        return list(parts[0].geometry)
    starts = {p.node_ids[0]: p for p in parts if p.node_ids}
    ends = {p.node_ids[-1]: p for p in parts if p.node_ids}
    if len(starts) != len(parts) or len(ends) != len(parts):
        return None
    heads = [p for p in parts if p.node_ids[0] not in ends]
    if len(heads) != 1:
        return None
    out = list(heads[0].geometry)
    cur = heads[0]
    used = 1
    while cur.node_ids[-1] in starts and used < len(parts):
        cur = starts[cur.node_ids[-1]]
        out.extend(cur.geometry[1:])
        used += 1
    return out if used == len(parts) else None


def _triangulate_body(b: Body) -> None:
    cuts = b.level.cut_lines() if b.level is not None else []
    tris: list[Tri] = []
    for outer, holes in b.pieces:
        rings = [dedupe_ring(outer)] + [dedupe_ring(h) for h in holes]
        pts = [p for r in rings for p in r]
        offs, o = [], 0
        for r in rings:
            offs.append(list(range(o, o + len(r))))
            o += len(r)
        for i, j, k in triangulate(pts, offs[0], offs[1:], 10 ** 9):
            polys: list[list[Pt]] = [[pts[i], pts[j], pts[k]]]
            for nx, ny, c in cuts:
                nxt: list[list[Pt]] = []
                for p in polys:
                    for keep in (False, True):
                        q = _clip_half(p, nx, ny, c, keep)
                        if len(q) >= 3 and abs(_area2(q)) > AREA_EPS:
                            nxt.append(q)
                polys = nxt
            for p in polys:
                p = clean_ring(dedupe_ring(p, 1e-9), 1e-12)
                for m in range(1, len(p) - 1):
                    tri = (p[0], p[m], p[m + 1])
                    if _area2(tri) > AREA_EPS:
                        tris.append(tuple((x, y, b.level.at(x, y)) for x, y in tri))   # type: ignore[arg-type]
    b.tris = tris


# --- Carve, blend, invariant ----------------------------------------------------------------------------------

class _CarveContext:
    def __init__(self, model: WaterModel, masks: _Masks, depth: float) -> None:
        self.m = model
        self.masks = masks
        self.depth = depth
        self.g = model.grid

    def prepare(self) -> None:
        for b in self.m.bodies:
            if b.built:
                self._carve_body(b)
                self._blend_body(b)

    def _carve_body(self, b: Body) -> None:
        g = self.g
        s = g.spacing
        cell_min: dict[tuple[int, int], float] = {}
        for t in b.tris:
            xs, ys = [p[0] for p in t], [p[1] for p in t]
            i0, i1, j0, j1 = _cells(g, min(xs), max(xs), min(ys), max(ys))
            pl = _Plane(t)
            tri = [(p[0], p[1]) for p in t]
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    x0, y0 = g.x0 + i * s, g.y0 + j * s
                    corners = [(x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s)]
                    if all(_in_tri(tri, x, y) for x, y in corners):
                        clip = corners
                    else:
                        clip = _clip_poly_tri(corners, tri)
                        if len(clip) < 3 or abs(_area2(clip)) < AREA_EPS:
                            continue
                    lo = min(pl.at(x, y) for x, y in clip)
                    key = (i, j)
                    if key not in cell_min or lo < cell_min[key]:
                        cell_min[key] = lo
        carve: dict[int, float] = {}
        for (i, j), lmin in cell_min.items():
            z = lmin - self.depth
            for vj in (j, j + 1):
                for vi in (i, i + 1):
                    v = vj * g.nx + vi
                    if v not in carve or z < carve[v]:
                        carve[v] = z
        b.carve = {v: z for v, z in carve.items() if z < g.heights[v // g.nx][v % g.nx]}
        b.info["cells"] = len(cell_min)

    def _blend_body(self, b: Body) -> None:
        g = self.g
        s = g.spacing
        k = BLEND_CELLS
        reach = k * s
        bx0, by0, bx1, by1 = _body_box(b)
        i0, i1, j0, j1 = (max(0, int(math.floor((bx0 - reach - g.x0) / s))),
                          min(g.nx - 1, int(math.ceil((bx1 + reach - g.x0) / s))),
                          max(0, int(math.floor((by0 - reach - g.y0) / s))),
                          min(g.ny - 1, int(math.ceil((by1 + reach - g.y0) / s))))
        edges = b.shore
        blend: dict[int, float] = {}
        for j in range(j0, j1 + 1):
            y = g.y0 + j * s
            for i in range(i0, i1 + 1):
                v = j * g.nx + i
                if v in b.carve:
                    continue
                x = g.x0 + i * s
                best, bp = reach, None
                for p, q in edges:
                    if (min(p[0], q[0]) - reach > x or max(p[0], q[0]) + reach < x
                            or min(p[1], q[1]) - reach > y or max(p[1], q[1]) + reach < y):
                        continue
                    d = _dist_seg(x, y, p, q)
                    if d < best:
                        best, bp = d, (p, q)
                if bp is None:
                    continue
                if any(_inside_pieces(o, x, y) for o in self.m.bodies if o.built):
                    continue
                if self.masks.hit_footprint(x, y, 0.0) or self.masks.hit_line(x, y, 0.0):
                    continue
                p, q = bp
                dx, dy = q[0] - p[0], q[1] - p[1]
                ll = dx * dx + dy * dy
                u = 0.0 if ll == 0 else min(1.0, max(0.0, ((x - p[0]) * dx + (y - p[1]) * dy) / ll))
                level = b.level.at(p[0] + u * dx, p[1] + u * dy)     # type: ignore[union-attr]
                z = g.heights[j][i]
                z2 = level + (best / reach) * (z - level)
                if z2 < z:
                    blend[v] = z2
        b.blend = blend

    def heights(self, active: Sequence[Body]) -> list[list[float]]:
        g = self.g
        h = [row[:] for row in g.heights]
        for b in active:
            for src in (b.carve, b.blend):
                for v, z in src.items():
                    j, i = divmod(v, g.nx)
                    if z < h[j][i]:
                        h[j][i] = z
        return h

    def check(self, active: Sequence[Body], h: list[list[float]]) -> dict[tuple[int, int, int], tuple[float, str]]:
        """Exact invariant: {(i, j, half): (max terrain - water over the overlap, body id)} for violations;
        ``self.max_by_body`` receives each body's maximum."""
        g = self.g
        by_cell: dict[tuple[int, int], list[tuple[Body, Tri, _Plane]]] = {}
        self.max_by_body = {b.id: -float("inf") for b in active}
        for b in active:
            for t in b.tris:
                xs, ys = [p[0] for p in t], [p[1] for p in t]
                i0, i1, j0, j1 = _cells(g, min(xs), max(xs), min(ys), max(ys))
                pl = _Plane(t)
                for i in range(i0, i1 + 1):
                    for j in range(j0, j1 + 1):
                        by_cell.setdefault((i, j), []).append((b, t, pl))
        bad: dict[tuple[int, int, int], tuple[float, str]] = {}
        for (i, j), wl in by_cell.items():
            wmin = min(min(p[2] for p in t) for _, t, _ in wl)
            for half, tt in enumerate(_cell_tris(g, i, j, h)):
                tmax = max(p[2] for p in tt)
                if tmax <= wmin - 1e-6:
                    for b, _, _ in wl:
                        self.max_by_body[b.id] = max(self.max_by_body[b.id], tmax - wmin)
                    continue
                tri2 = [(p[0], p[1]) for p in tt]
                tp = _Plane(tt)
                for b, t, wp in wl:
                    clip = _clip_poly_tri([(p[0], p[1]) for p in t], tri2)
                    if len(clip) < 3 or abs(_area2(clip)) < AREA_EPS:
                        continue
                    worst = max(tp.at(x, y) - wp.at(x, y) for x, y in clip)
                    if worst > self.max_by_body[b.id]:
                        self.max_by_body[b.id] = worst
                    if worst > VIOLATION_TOL_M:
                        key = (i, j, half)
                        if key not in bad or worst > bad[key][0]:
                            bad[key] = (worst, b.id)
        return bad

    def settle(self, refund: Callable[[int, int], None] | None) -> None:
        g = self.g
        while True:
            active = self.m.active()
            h = self.heights(active)
            bad = self.check(active, h)
            rounds = 0
            while bad and rounds < REMEDY_ROUNDS:
                lower: dict[tuple[int, int], float] = {}
                for (i, j, half), (viol, _) in bad.items():
                    vs = ((i, j), (i + 1, j), (i + 1, j + 1)) if half == 0 else ((i, j), (i + 1, j + 1), (i, j + 1))
                    for vi, vj in vs:
                        lower[(vi, vj)] = max(lower.get((vi, vj), 0.0), viol + REMEDY_MARGIN_M)
                for (vi, vj), dz in lower.items():
                    h[vj][vi] -= dz
                rounds += 1
                bad = self.check(active, h)
            if not bad:
                for b in active:
                    b.info["max_terrain_above_water_m"] = round(self.max_by_body[b.id], 6)
                    b.info["remedy_rounds"] = rounds
                self.m.carved = ElevationGrid(g.x0, g.y0, g.spacing, g.nx, g.ny, h, g.provenance)
                return
            first = min(v[1] for v in bad.values())
            victim = next(b for b in active if b.id == first)
            victim.outcome = "fallback(carve invariant)"
            victim.notes.append("terrain above water after the bounded remedy")
            if refund is not None:
                refund(*victim.mesh_counts)
            victim.tris, victim.carve, victim.blend, victim.level = [], {}, {}, None


def at_grade_roads(model: WaterModel, roads: Iterable[tuple[str, Sequence[Pt]]], lift: float,
                   step: float = 2.0) -> dict[str, list[str]]:
    """Per built body, ``at-grade road over water: <id>, <n> m inside, <m> m below L`` for every at-grade road
    (not a bridge or tunnel) whose centreline runs inside it. The road follows the carved bed at ``lift``; this
    only reports it, as an OSM data issue (ford, untagged causeway)."""
    out: dict[str, list[str]] = {}
    for b in model.active():
        if b.level is None:
            continue
        x0, y0, x1, y1 = _body_box(b)
        rows: list[str] = []
        for rid, pts in sorted(roads, key=lambda r: r[0]):
            if len(pts) < 2 or max(p[0] for p in pts) < x0 or min(p[0] for p in pts) > x1 \
                    or max(p[1] for p in pts) < y0 or min(p[1] for p in pts) > y1:
                continue
            inside = below = 0.0
            for a, c in zip(pts, pts[1:]):
                seg = math.hypot(c[0] - a[0], c[1] - a[1])
                for t0, t1 in _segment_inside(a, c, b.pieces):
                    n = max(1, math.ceil((t1 - t0) * seg / step))
                    for k in range(n):
                        t = t0 + (t1 - t0) * (k + 0.5) / n
                        x, y = a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t
                        part = (t1 - t0) * seg / n
                        inside += part
                        if _ground(model.grid, x, y) + lift < b.level.at(x, y):
                            below += part
            if inside > 0.0:
                rows.append(f"at-grade road over water: {rid}, {inside:.1f} m inside, {below:.1f} m below L")
        if rows:
            out[b.id] = rows
    return out


class WaterError(MapBuilderError):
    """Internal inconsistency in the water stage."""
