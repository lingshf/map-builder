"""Bounded geometric queries against a parsed ``.mbcol`` (:class:`collision.Collision`).

Pure Python. Triangles are two-sided for every query here (winding only defines the contact
normal, docs/PACKAGE_FORMAT.md "Winding"). Each query visits objects through a per-object AABB
prefilter (the object table ``aabb``), then triangles through a per-triangle AABB test, and counts
every object and triangle visit as one work unit; exceeding ``max_work`` raises
:class:`errors.LimitError`, so the cost is bounded whatever the input.
"""

import math
from collections import namedtuple

from .collision import AABB_TABLE_TOL_M
from .errors import LimitError

DEFAULT_MAX_WORK = 2_000_000

RayHit = namedtuple("RayHit", "t triangle object")
CapsuleResult = namedtuple("CapsuleResult", "objects work")


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _lerp(a, d, t):
    return (a[0] + d[0] * t, a[1] + d[1] * t, a[2] + d[2] * t)


def _dist2(a, b):
    d = _sub(a, b)
    return _dot(d, d)


def closest_point_triangle(p, a, b, c):
    """Closest point to ``p`` on triangle ``abc`` (Ericson, Real-Time Collision Detection 5.1.5)."""
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(p, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a
    bp = _sub(p, b)
    d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        return _lerp(a, ab, d1 / (d1 - d3))
    cp = _sub(p, c)
    d5, d6 = _dot(ab, cp), _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        return _lerp(a, ac, d2 / (d2 - d6))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        return _lerp(b, _sub(c, b), (d4 - d3) / ((d4 - d3) + (d5 - d6)))
    denom = va + vb + vc
    if denom == 0.0:                       # degenerate triangle: fall back to its edges
        return min((closest_point_segment(p, a, b), closest_point_segment(p, b, c), closest_point_segment(p, c, a)),
                   key=lambda q: _dist2(p, q))
    v, w = vb / denom, vc / denom
    return (a[0] + ab[0] * v + ac[0] * w, a[1] + ab[1] * v + ac[1] * w, a[2] + ab[2] * v + ac[2] * w)


def closest_point_segment(p, a, b):
    ab = _sub(b, a)
    den = _dot(ab, ab)
    if den == 0.0:
        return a
    t = min(1.0, max(0.0, _dot(_sub(p, a), ab) / den))
    return _lerp(a, ab, t)


def segment_segment_distance(p1, q1, p2, q2):
    """Closest distance between segments ``p1q1`` and ``p2q2`` (Ericson 5.1.9)."""
    d1, d2, r = _sub(q1, p1), _sub(q2, p2), _sub(p1, p2)
    a, e, f = _dot(d1, d1), _dot(d2, d2), _dot(d2, r)
    if a == 0.0 and e == 0.0:
        return math.sqrt(_dot(r, r))
    if a == 0.0:
        s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = _dot(d1, r)
        if e == 0.0:
            t, s = 0.0, min(1.0, max(0.0, -c / a))
        else:
            b = _dot(d1, d2)
            den = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / den)) if den != 0.0 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1.0:
                t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    return math.sqrt(_dist2(_lerp(p1, d1, s), _lerp(p2, d2, t)))


def _ray_triangle(o, d, a, b, c):
    """Two-sided Moller-Trumbore: the parameter ``t`` along ``o + t d`` where it meets ``abc``, or None
    (also None for a degenerate triangle or a ray parallel to its plane)."""
    e1, e2 = _sub(b, a), _sub(c, a)
    pv = _cross(d, e2)
    det = _dot(e1, pv)
    if det == 0.0:
        return None
    inv = 1.0 / det
    tv = _sub(o, a)
    u = _dot(tv, pv) * inv
    if u < 0.0 or u > 1.0:
        return None
    qv = _cross(tv, e1)
    v = _dot(d, qv) * inv
    if v < 0.0 or u + v > 1.0:
        return None
    return _dot(e2, qv) * inv


def segment_triangle_distance(p, q, a, b, c):
    """Closest distance between segment ``pq`` and triangle ``abc`` (two-sided; 0 when they intersect).
    Degenerate triangles are measured through their edges."""
    t = _ray_triangle(p, _sub(q, p), a, b, c)
    if t is not None and 0.0 <= t <= 1.0:
        return 0.0
    best = min(_dist2(p, closest_point_triangle(p, a, b, c)), _dist2(q, closest_point_triangle(q, a, b, c)))
    best = math.sqrt(best)
    for u, v in ((a, b), (b, c), (c, a)):
        best = min(best, segment_segment_distance(p, q, u, v))
    return best


def _check_points(points, what):
    pts = []
    for p in points:
        if len(p) != 3 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                                  for x in p):
            raise ValueError(f"{what} must be finite 3-vectors")
        pts.append((float(p[0]), float(p[1]), float(p[2])))
    return pts


def _box_overlap(lo, hi, box, pad):
    return (box[0] - pad <= hi[0] and lo[0] <= box[3] + pad and box[1] - pad <= hi[1] and lo[1] <= box[4] + pad
            and box[2] - pad <= hi[2] and lo[2] <= box[5] + pad)


class _Budget:
    def __init__(self, max_work):
        self.max_work = max_work
        self.work = 0

    def spend(self, n=1):
        self.work += n
        if self.work > self.max_work:
            raise LimitError(f"collision query exceeded its work budget of {self.max_work} unit(s)")


def capsule_hits(col, path_points, radius, max_work=DEFAULT_MAX_WORK, *, result=False):
    """Collision objects touched by the capsule swept along the polyline ``path_points`` (map frame, metres)
    with ``radius`` metres: those with a triangle at distance <= ``radius`` from a path segment.

    Returns a sorted list of object indices (into ``col.objects``; names are ``col.objects[k]["name"]``), or a
    :data:`CapsuleResult` ``(objects, work)`` when ``result`` is true. A single point is a sphere. Raises
    LimitError when more than ``max_work`` object/triangle visits would be needed."""
    pts = _check_points(path_points, "path_points")
    if not pts:
        raise ValueError("path_points must hold at least one point")
    if not (isinstance(radius, (int, float)) and math.isfinite(radius) and radius >= 0.0):
        raise ValueError("radius must be a finite number >= 0")
    segs = list(zip(pts, pts[1:])) or [(pts[0], pts[0])]
    budget = _Budget(max_work)
    pad = radius + AABB_TABLE_TOL_M
    bounds = []
    for p, q in segs:
        bounds.append(((min(p[0], q[0]), min(p[1], q[1]), min(p[2], q[2])),
                       (max(p[0], q[0]), max(p[1], q[1]), max(p[2], q[2]))))
    v, idx = col.vertices, col.indices
    hits = []
    for k, e in enumerate(col.objects):
        box = e["aabb"]
        s0, n = e["tri_start"], e["tri_count"]
        hit = False
        for (p, q), (lo, hi) in zip(segs, bounds):
            budget.spend()
            if not _box_overlap(lo, hi, box, pad):
                continue
            for t in range(s0, s0 + n):
                budget.spend()
                a, b, c = v[idx[3 * t]], v[idx[3 * t + 1]], v[idx[3 * t + 2]]
                tb = (min(a[0], b[0], c[0]), min(a[1], b[1], c[1]), min(a[2], b[2], c[2]),
                      max(a[0], b[0], c[0]), max(a[1], b[1], c[1]), max(a[2], b[2], c[2]))
                if not _box_overlap(lo, hi, tb, radius):
                    continue
                if segment_triangle_distance(p, q, a, b, c) <= radius:
                    hit = True
                    break
            if hit:
                break
        if hit:
            hits.append(k)
    return CapsuleResult(hits, budget.work) if result else hits


def _ray_box(o, inv, box, tmax):
    t0, t1 = 0.0, tmax
    for a in range(3):
        lo, hi = box[a] - AABB_TABLE_TOL_M, box[a + 3] + AABB_TABLE_TOL_M
        if inv[a] is None:
            if o[a] < lo or o[a] > hi:
                return False
            continue
        ta, tb = (lo - o[a]) * inv[a], (hi - o[a]) * inv[a]
        if ta > tb:
            ta, tb = tb, ta
        t0, t1 = max(t0, ta), min(t1, tb)
        if t0 > t1:
            return False
    return True


def ray_cast(col, origin, direction, max_dist, max_work=DEFAULT_MAX_WORK):
    """Nearest triangle hit by the ray ``origin + t * direction`` for ``0 <= t <= max_dist`` (``t`` in metres;
    ``direction`` is normalised). Returns :data:`RayHit` ``(t, triangle, object)`` or None; ties go to the lower
    triangle index. Raises ValueError for a zero direction and LimitError when over ``max_work``."""
    (o,) = _check_points([origin], "origin")
    (d,) = _check_points([direction], "direction")
    n = math.sqrt(_dot(d, d))
    if n == 0.0:
        raise ValueError("direction must not be zero")
    if not (isinstance(max_dist, (int, float)) and math.isfinite(max_dist) and max_dist >= 0.0):
        raise ValueError("max_dist must be a finite number >= 0")
    d = (d[0] / n, d[1] / n, d[2] / n)
    inv = tuple(1.0 / x if x != 0.0 else None for x in d)
    budget = _Budget(max_work)
    v, idx = col.vertices, col.indices
    best = None
    for k, e in enumerate(col.objects):
        budget.spend()
        limit = best.t if best is not None else max_dist
        if not _ray_box(o, inv, e["aabb"], limit):
            continue
        s0 = e["tri_start"]
        for t in range(s0, s0 + e["tri_count"]):
            budget.spend()
            hit = _ray_triangle(o, d, v[idx[3 * t]], v[idx[3 * t + 1]], v[idx[3 * t + 2]])
            if hit is None or hit < 0.0 or hit > max_dist:
                continue
            if best is None or hit < best.t or (hit == best.t and t < best.triangle):
                best = RayHit(hit, t, k)
    return best
