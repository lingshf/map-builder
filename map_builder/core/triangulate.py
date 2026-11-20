# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Polygon triangulation with holes (validated rings, hole bridging, ear clipping).

Works on indices into a shared 2-D point list so callers keep vertex identity.
Outer ring must be CCW, holes CW (see :class:`osm.Polygon`). Output triangles
are CCW (normal +Z in the right-handed map frame).

Guarantees (otherwise :class:`TriangulationError` is raised, never a partial result):

* the rings are validated first: >= 3 distinct points, no repeated vertex, no
  self-intersection or self-contact, correct orientation, every hole strictly
  inside the outer ring, holes pairwise disjoint (no contact, no nesting);
* the returned triangles all have strictly positive area, use every original
  ring edge exactly once in ring direction, pair every other edge with its
  reverse, and their total area equals outer area minus hole areas.

Orientation tests are exact (float filter with a ``Fraction`` fallback) and all
geometric work is counted against ``max_work`` so pathological input is bounded.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from fractions import Fraction
from typing import TypeAlias, TypeVar

from .errors import MapBuilderError

Pt: TypeAlias = "Sequence[float]"
# (min x, max x, min y, max y, ring, edge index, ring length, start point, end point)
_EdgeRec: TypeAlias = "tuple[float, float, float, float, int, int, int, Pt, Pt]"
_P = TypeVar("_P", bound=Sequence[float])

DEFAULT_MAX_WORK = 5_000_000
_ERRBOUND = 1e-14


class TriangulationError(MapBuilderError):
    pass


class _Work:
    """Counts primitive geometric tests (orientation/segment/point tests)."""

    def __init__(self, limit: int) -> None:
        self.limit: int = limit
        self.n: int = 0

    def add(self, k: int = 1) -> None:
        self.n += k
        if self.n > self.limit:
            raise TriangulationError(f"triangulation work budget exceeded ({self.limit} geometric tests)")


def orient(a: Pt, b: Pt, c: Pt) -> int:
    """Exact sign of the doubled signed area of (a, b, c): 1 CCW, -1 CW, 0 collinear."""
    left = (b[0] - a[0]) * (c[1] - a[1])
    right = (b[1] - a[1]) * (c[0] - a[0])
    det = left - right
    bound = _ERRBOUND * (abs(left) + abs(right))
    if det > bound:
        return 1
    if det < -bound:
        return -1
    ax, ay = Fraction(a[0]), Fraction(a[1])
    d = (Fraction(b[0]) - ax) * (Fraction(c[1]) - ay) - (Fraction(b[1]) - ay) * (Fraction(c[0]) - ax)
    return (d > 0) - (d < 0)


def _collinear_span(p: Pt, q: Pt, a: Pt, b: Pt) -> tuple[float, float, float, float]:
    """For collinear segments pq and ab: (lo, hi, s0, s1) along the dominant axis of pq."""
    ax = 0 if abs(q[0] - p[0]) >= abs(q[1] - p[1]) else 1
    s0, s1 = sorted((p[ax], q[ax]))
    e0, e1 = sorted((a[ax], b[ax]))
    return max(s0, e0), min(s1, e1), s0, s1


def segments_meet(p: Pt, q: Pt, a: Pt, b: Pt) -> bool:
    """True if the closed segments pq and ab share at least one point."""
    o1, o2 = orient(p, q, a), orient(p, q, b)
    if o1 == 0 and o2 == 0:
        lo, hi, _, _ = _collinear_span(p, q, a, b)
        return lo <= hi
    if o1 * o2 > 0:
        return False
    o3, o4 = orient(a, b, p), orient(a, b, q)
    return o3 * o4 <= 0


def blocks_segment(m: Pt, p: Pt, a: Pt, b: Pt) -> bool:
    """True if closed segment ab meets closed segment mp anywhere except exactly at m or p.

    Covers proper crossings, an edge passing through m-p at one of its own
    endpoints (i.e. m-p runs through a vertex), and collinear overlap.
    """
    o1, o2 = orient(m, p, a), orient(m, p, b)
    if o1 == 0 and o2 == 0:
        lo, hi, s0, s1 = _collinear_span(m, p, a, b)
        if lo > hi:
            return False
        if lo < hi:
            return True
        return s0 < lo < s1
    if o1 * o2 > 0:
        return False
    o3, o4 = orient(a, b, m), orient(a, b, p)
    if o3 * o4 > 0:
        return False
    # Lines are not identical, so the intersection is a single point; it is m (or p) iff m (or p) is on ab.
    return not (o3 == 0 or o4 == 0)


def _in_cone(prev: Pt, v: Pt, nxt: Pt, q: Pt) -> bool:
    """True if direction v->q points strictly into the region left of prev->v->nxt (the polygon interior)."""
    if orient(prev, v, nxt) > 0:
        return orient(prev, v, q) > 0 and orient(v, nxt, q) > 0
    return orient(prev, v, q) > 0 or orient(v, nxt, q) > 0


def ring_area(points: Sequence[Pt]) -> float:
    a = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def _point_in_ring(pt: Pt, ring_pts: Sequence[Pt]) -> bool:
    x, y = pt
    inside = False
    j = len(ring_pts) - 1
    for i in range(len(ring_pts)):
        xi, yi = ring_pts[i]
        xj, yj = ring_pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def dedupe_ring(points: Iterable[_P], tol: float = 1e-6) -> list[_P]:
    """Drop consecutive duplicate points (and a closing duplicate) within ``tol`` metres."""
    out: list[_P] = []
    for p in points:
        if not out or abs(p[0] - out[-1][0]) > tol or abs(p[1] - out[-1][1]) > tol:
            out.append(p)
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) <= tol and abs(out[0][1] - out[-1][1]) <= tol:
        out.pop()
    return out


def _label(r: int) -> str:
    return "outer ring" if r == 0 else f"hole {r}"


def validate_rings(pts: Sequence[Pt], outer: Sequence[int], holes: Sequence[Sequence[int]] = (),
                   max_work: int = DEFAULT_MAX_WORK, _work: _Work | None = None) -> _Work:
    """Raise TriangulationError unless outer/holes describe a valid polygon with holes."""
    work = _work or _Work(max_work)
    rings = [list(outer)] + [list(h) for h in holes]
    for r, ring in enumerate(rings):
        coords = [pts[i] for i in ring]
        if len(set(coords)) < 3:
            raise TriangulationError(f"{_label(r)} has fewer than 3 distinct points")
        if len(set(coords)) != len(coords):
            raise TriangulationError(f"{_label(r)} repeats a vertex (duplicate point or self-contact)")
        area = ring_area(coords)
        if r == 0 and not area > 0:
            raise TriangulationError("outer ring must be counter-clockwise with non-zero area")
        if r > 0 and not area < 0:
            raise TriangulationError(f"{_label(r)} must be clockwise with non-zero area")
    # All edges of all rings; sweep in x so only edges with overlapping x ranges are compared.
    edges: list[_EdgeRec] = []
    for r, ring in enumerate(rings):
        n = len(ring)
        for k in range(n):
            a, b = pts[ring[k]], pts[ring[(k + 1) % n]]
            edges.append((min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]), r, k, n, a, b))
    edges.sort(key=lambda e: e[0])
    active: list[_EdgeRec] = []
    for e in edges:
        x0, _, y0, y1, r, k, n, a, b = e
        active = [f for f in active if f[1] >= x0]
        for f in active:
            work.add()
            if f[3] < y0 or f[2] > y1:
                continue
            fr, fk, fn, fa, fb = f[4], f[5], f[6], f[7], f[8]
            if fr == r and (fk == (k + 1) % n or k == (fk + 1) % n):
                # Adjacent edges share exactly one vertex; they must not fold back over each other.
                if fk == (k + 1) % n:  # a -> b(=fa) -> fb
                    u, shared, w = a, b, fb
                else:  # fa -> fb(=a) -> b
                    u, shared, w = fa, a, b
                if orient(u, shared, w) == 0 and (
                        (u[0] - shared[0]) * (w[0] - shared[0]) + (u[1] - shared[1]) * (w[1] - shared[1])) > 0:
                    raise TriangulationError(f"{_label(r)} folds back on itself (zero-width spike)")
                continue
            if segments_meet(a, b, fa, fb):
                if fr == r:
                    raise TriangulationError(f"{_label(r)} self-intersects or touches itself")
                lo, hi = sorted((r, fr))
                if lo == 0:
                    raise TriangulationError(f"{_label(hi)} touches or crosses the outer ring")
                raise TriangulationError(f"holes {lo} and {hi} touch or cross")
        active.append(e)
    # No contacts remain, so one vertex decides containment for each ring pair.
    ring_pts = [[pts[i] for i in ring] for ring in rings]
    for r in range(1, len(rings)):
        work.add(len(ring_pts[0]))
        if not _point_in_ring(ring_pts[r][0], ring_pts[0]):
            raise TriangulationError(f"{_label(r)} lies outside the outer ring")
        for s in range(1, len(rings)):
            if s != r:
                work.add(len(ring_pts[s]))
                if _point_in_ring(ring_pts[r][0], ring_pts[s]):
                    raise TriangulationError(f"{_label(r)} lies inside hole {s}")
    return work


def _bridge_hole(poly: list[int], hole: list[int], pts: Sequence[Pt], other_edges: list[tuple[Pt, Pt]],
                 work: _Work) -> list[int] | None:
    """Splice ``hole`` into ``poly`` with the shortest valid bridge from its rightmost vertices.

    Hole vertices are tried right to left; for each, polygon vertices in order of
    distance. A bridge is valid if it leaves both endpoints into the polygon
    interior and no edge (of the polygon, this hole or any remaining hole) meets it
    anywhere except at its two endpoints. Returns the new index list or None.
    """
    n, nh = len(poly), len(hole)
    edges = [(pts[poly[k]], pts[poly[(k + 1) % n]]) for k in range(n)]
    edges += [(pts[hole[k]], pts[hole[(k + 1) % nh]]) for k in range(nh)]
    edges += other_edges
    boxes = [(min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]), a, b) for a, b in edges]
    for hk in sorted(range(nh), key=lambda k: (-pts[hole[k]][0], pts[hole[k]][1])):
        m = pts[hole[hk]]
        hp, hn = pts[hole[hk - 1]], pts[hole[(hk + 1) % nh]]
        order = sorted(range(n), key=lambda k: (pts[poly[k]][0] - m[0]) ** 2 + (pts[poly[k]][1] - m[1]) ** 2)
        work.add(n)
        for k in order:
            p = pts[poly[k]]
            work.add()
            if p == m:
                continue
            if not _in_cone(pts[poly[k - 1]], p, pts[poly[(k + 1) % n]], m) or not _in_cone(hp, m, hn, p):
                continue
            x0, x1 = min(m[0], p[0]), max(m[0], p[0])
            y0, y1 = min(m[1], p[1]), max(m[1], p[1])
            ok = True
            for ex0, ex1, ey0, ey1, a, b in boxes:
                work.add()
                if ex1 < x0 or ex0 > x1 or ey1 < y0 or ey0 > y1:
                    continue
                if blocks_segment(m, p, a, b):
                    ok = False
                    break
            if ok:
                rot = hole[hk:] + hole[:hk]
                return poly[:k + 1] + rot + [rot[0], poly[k]] + poly[k + 1:]
    return None


def _ear_blocked(poly: Sequence[int], pts: Sequence[Pt], a: Pt, b: Pt, c: Pt, check_diagonal: bool,
                 work: _Work) -> bool:
    x0, x1 = min(a[0], b[0], c[0]), max(a[0], b[0], c[0])
    y0, y1 = min(a[1], b[1], c[1]), max(a[1], b[1], c[1])
    work.add(len(poly))
    for q in poly:
        pq = pts[q]
        if pq[0] < x0 or pq[0] > x1 or pq[1] < y0 or pq[1] > y1:
            continue
        if pq == a or pq == b or pq == c:
            continue
        if orient(a, b, pq) >= 0 and orient(b, c, pq) >= 0 and orient(c, a, pq) >= 0:
            return True
    if check_diagonal:
        # Coincident (bridge) vertices are skipped above, so also require the new diagonal
        # a-c to be clear of every polygon edge except at its own endpoints.
        dx0, dx1 = min(a[0], c[0]), max(a[0], c[0])
        dy0, dy1 = min(a[1], c[1]), max(a[1], c[1])
        n = len(poly)
        work.add(n)
        for k in range(n):
            u, v = pts[poly[k]], pts[poly[(k + 1) % n]]
            if max(u[0], v[0]) < dx0 or min(u[0], v[0]) > dx1 or max(u[1], v[1]) < dy0 or min(u[1], v[1]) > dy1:
                continue
            if blocks_segment(a, c, u, v):
                return True
    return False


def _ear_clip(poly: list[int], pts: Sequence[Pt], work: _Work) -> list[tuple[int, int, int]]:
    poly = list(poly)
    check_diagonal = len({pts[i] for i in poly}) < len(poly)
    tris: list[tuple[int, int, int]] = []
    start = 0
    while len(poly) > 3:
        n = len(poly)
        ear: int | None = None
        for t in range(n):
            k = (start + t) % n
            ia, ib, ic = poly[k - 1], poly[k], poly[(k + 1) % n]
            a, b, c = pts[ia], pts[ib], pts[ic]
            work.add()
            if orient(a, b, c) <= 0:
                continue
            if _ear_blocked(poly, pts, a, b, c, check_diagonal, work):
                continue
            ear = k
            break
        if ear is None:
            raise TriangulationError("no valid ear found (degenerate or non-simple polygon)")
        tris.append((poly[ear - 1], poly[ear], poly[(ear + 1) % n]))
        poly.pop(ear)
        start = max(ear - 1, 0)
    if orient(*(pts[i] for i in poly)) <= 0:
        raise TriangulationError("final triangle is degenerate")
    tris.append(tuple(poly))  # type: ignore[arg-type]  # exactly three vertices remain
    return tris


def verify_triangulation(tris: Iterable[tuple[int, int, int]], pts: Sequence[Pt], outer: Sequence[int],
                         holes: Sequence[Sequence[int]] = ()) -> None:
    """Raise TriangulationError unless ``tris`` exactly tiles the polygon (see module docstring)."""
    directed: Counter[tuple[int, int]] = Counter()
    area = 0.0
    for i, j, k in tris:
        a, b, c = pts[i], pts[j], pts[k]
        if orient(a, b, c) <= 0:
            raise TriangulationError("triangulation produced a degenerate or flipped triangle")
        area += ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0
        directed[(i, j)] += 1
        directed[(j, k)] += 1
        directed[(k, i)] += 1
    ring_edges: set[tuple[int, int]] = set()
    for ring in [list(outer)] + [list(h) for h in holes]:
        n = len(ring)
        for k in range(n):
            ring_edges.add((ring[k], ring[(k + 1) % n]))
    for e in ring_edges:
        if directed.get(e) != 1:
            raise TriangulationError(f"triangulation does not cover ring edge {e[0]}->{e[1]} exactly once")
    for (u, v), cnt in directed.items():
        if cnt != 1:
            raise TriangulationError(f"edge {u}->{v} used {cnt} times (overlapping triangles)")
        if (u, v) in ring_edges:
            if (v, u) in directed:
                raise TriangulationError(f"triangle outside ring edge {u}->{v}")
        elif (v, u) not in directed:
            raise TriangulationError(f"interior edge {u}->{v} has no twin (gap or T-junction)")
    expected = ring_area([pts[i] for i in outer]) + sum(ring_area([pts[i] for i in h]) for h in holes)
    if abs(area - expected) > 1e-7 * max(1.0, abs(expected)):
        raise TriangulationError(f"triangulated area {area:.6f} differs from polygon area {expected:.6f}")


def triangulate(pts: Sequence[Pt], outer: Sequence[int], holes: Sequence[Sequence[int]] = (),
                max_work: int = DEFAULT_MAX_WORK) -> list[tuple[int, int, int]]:
    """pts: list of (x, y); outer/holes: lists of indices. Returns [(i, j, k)] (CCW).

    Raises TriangulationError for invalid rings, when the geometric work exceeds
    ``max_work`` tests, or if the result fails verification.
    """
    pts = [(float(p[0]), float(p[1])) for p in pts]
    outer = list(outer)
    hole_lists = [list(h) for h in holes]
    work = validate_rings(pts, outer, hole_lists, max_work)
    poly = list(outer)
    pending = sorted(hole_lists, key=lambda h: -max(pts[i][0] for i in h))
    while pending:
        for idx, hole in enumerate(pending):
            other: list[tuple[Pt, Pt]] = []
            for o, h in enumerate(pending):
                if o != idx:
                    other += [(pts[h[k]], pts[h[(k + 1) % len(h)]]) for k in range(len(h))]
            spliced = _bridge_hole(poly, hole, pts, other, work)
            if spliced is not None:
                poly = spliced
                pending.pop(idx)
                break
        else:
            raise TriangulationError("could not find a valid bridge from a hole to the outer ring")
    tris = _ear_clip(poly, pts, work)
    verify_triangulation(tris, pts, outer, hole_lists)
    return tris
