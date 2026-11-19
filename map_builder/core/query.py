"""Bounded geometric queries against a parsed ``.mbcol`` (:class:`collision.Collision`).

Pure Python. Triangles are two-sided for every query here (winding only defines the contact
normal, docs/PACKAGE_FORMAT.md "Winding"). Each query visits objects through a per-object AABB
prefilter (the object table ``aabb``), then triangles through a per-triangle AABB test, and counts
every object and triangle visit as one work unit; exceeding ``max_work`` raises
:class:`errors.LimitError`, so the cost is bounded whatever the input.
"""

import math
import sys
from collections import namedtuple
from fractions import Fraction

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


# A triangle whose |(b - a) x (c - a)| is at most DEGENERATE_SIN times its longest squared edge (a collapsed
# or collinear triangle, width <= DEGENERATE_SIN x its longest edge) is measured through its edges and
# vertices only: its plane is undefined or numerically meaningless. Mirrored by MbmapReader.cs.
DEGENERATE_SIN = 1e-9

# Capsule contact is inclusive: a triangle within radius + CONTACT_TOL_M is a hit, so an exact contact is not
# lost to rounding (a few ulps at map coordinates up to 1e6 m). Mirrored by MbmapReader.cs.
CONTACT_TOL_M = 1e-9
# ray_cast also accepts a tolerant Moller-Trumbore hit (barycentrics down to -RAY_EDGE_TOL), so a ray that only
# touches a silhouette edge (two triangles folded over each other as seen along a grazing ray, where neither
# watertight test reports a crossing) still counts as contact.
RAY_EDGE_TOL = 1e-9


def triangle_is_degenerate(a, b, c):
    """True for a collapsed (two or three equal vertices) or (nearly) collinear triangle, see DEGENERATE_SIN."""
    ab, ac, bc = _sub(b, a), _sub(c, a), _sub(c, b)
    longest = max(_dot(ab, ab), _dot(ac, ac), _dot(bc, bc))
    n = _cross(ab, ac)
    return math.sqrt(_dot(n, n)) <= DEGENERATE_SIN * longest


def _closest_on_edges(p, a, b, c):
    return min((closest_point_segment(p, a, b), closest_point_segment(p, b, c), closest_point_segment(p, c, a)),
               key=lambda q: _dist2(p, q))


def closest_point_triangle(p, a, b, c):
    """Closest point to ``p`` on triangle ``abc``. A degenerate triangle (:func:`triangle_is_degenerate`) is
    measured through its edges. Otherwise ``p`` is projected onto the plane (relative to ``a``, with the
    unnormalised normal, so the error grows with 1/sin of the smallest angle rather than its square, as the
    barycentric-determinant form would); a projection outside the triangle is replaced by the nearest
    point on its edges."""
    if triangle_is_degenerate(a, b, c):
        return _closest_on_edges(p, a, b, c)
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(p, a)
    n = _cross(ab, ac)
    h = _dot(ap, n) / _dot(n, n)
    q = (ap[0] - n[0] * h, ap[1] - n[1] * h, ap[2] - n[2] * h)        # projection, relative to a
    bc = _sub(c, b)
    if (_dot(_cross(ab, q), n) >= 0.0 and _dot(_cross(bc, _sub(q, ab)), n) >= 0.0
            and _dot(_cross(_sub(a, c), _sub(q, ac)), n) >= 0.0):
        return (a[0] + q[0], a[1] + q[1], a[2] + q[2])
    return _closest_on_edges(p, a, b, c)


def closest_point_segment(p, a, b):
    ab = _sub(b, a)
    den = _dot(ab, ab)
    if den == 0.0:
        return a
    t = min(1.0, max(0.0, _dot(_sub(p, a), ab) / den))
    return _lerp(a, ab, t)


def _segment_param(p, a, ab, den):
    return 0.0 if den == 0.0 else min(1.0, max(0.0, _dot(_sub(p, a), ab) / den))


def segment_segment_distance(p1, q1, p2, q2):
    """Closest distance between segments ``p1q1`` and ``p2q2``.

    The minimum is either interior to both segments or has an endpoint of one of them, so it is the
    smaller of the four endpoint-to-segment distances and, whenever the segments are not exactly parallel
    (``d1 x d2`` nonzero), the interior critical point. That point is solved with Lagrange's identity
    (``a e - b^2 = |d1 x d2|^2`` and the numerators as triple products) instead of the cancelling
    ``a e - b^2`` of Ericson 5.1.9, in a frame relative to the start points, then clamped and refined by
    re-projecting each point onto the other segment (each step can only shorten the distance), so nearly
    parallel long segments keep their precision. Every candidate is a real pair of segment points, so a
    poorly conditioned solution can never undercut the true distance; only exactly parallel segments or a
    non-finite solution fall back to the endpoint distances alone."""
    d1, d2 = _sub(q1, p1), _sub(q2, p2)
    a, e = _dot(d1, d1), _dot(d2, d2)
    best = min(_dist2(p1, closest_point_segment(p1, p2, q2)), _dist2(q1, closest_point_segment(q1, p2, q2)),
               _dist2(p2, closest_point_segment(p2, p1, q1)), _dist2(q2, closest_point_segment(q2, p1, q1)))
    if a > 0.0 and e > 0.0:
        n = _cross(d1, d2)
        den = _dot(n, n)
        s = _dot(n, _cross(d2, _sub(p1, p2))) / den if den > 0.0 else math.nan
        if math.isfinite(s):
            s = min(1.0, max(0.0, s))
            t = _segment_param(_lerp(p1, d1, s), p2, d2, e)
            s = _segment_param(_lerp(p2, d2, t), p1, d1, a)
            t = _segment_param(_lerp(p1, d1, s), p2, d2, e)
            best = min(best, _dist2(_lerp(p1, d1, s), _lerp(p2, d2, t)))
    return math.sqrt(best)


def _edge_functions(ax, ay, bx, by, cx, cy):
    return cx * by - cy * bx, ax * cy - ay * cx, bx * ay - by * ax


def _ray_triangle(o, d, a, b, c):
    """Two-sided watertight ray/triangle test (Woop, Benthin and Wald 2013): the parameter ``t`` along
    ``o + t d`` where it meets ``abc``, or None (also None for a ray parallel to the plane). The vertices
    are translated to the ray origin and sheared so the ray runs along +z; the 2D edge functions of a
    shared edge are then computed from identical values in both triangles, and any edge function that
    rounds to zero is recomputed exactly, so a ray can never slip through an edge between two triangles
    (nor through a shared vertex). A non-finite ``t`` is a miss."""
    kz = max(range(3), key=lambda i: abs(d[i]))
    kx, ky = (kz + 1) % 3, (kz + 2) % 3
    if d[kz] == 0.0:
        return None
    sx, sy, sz = d[kx] / d[kz], d[ky] / d[kz], 1.0 / d[kz]
    pa, pb, pc = _sub(a, o), _sub(b, o), _sub(c, o)
    sh = [(p[kx] - sx * p[kz], p[ky] - sy * p[kz]) for p in (pa, pb, pc)]
    u, v, w = _edge_functions(sh[0][0], sh[0][1], sh[1][0], sh[1][1], sh[2][0], sh[2][1])
    if u == 0.0 or v == 0.0 or w == 0.0:
        u, v, w = _edge_functions(*(Fraction(x) for p in sh for x in p))
    if (u < 0 or v < 0 or w < 0) and (u > 0 or v > 0 or w > 0):
        return None
    det = u + v + w
    if det == 0:
        return None
    u, v, w, det = float(u), float(v), float(w), float(det)
    if det == 0.0:
        return None
    t = (u * pa[kz] + v * pb[kz] + w * pc[kz]) * sz / det
    return t if math.isfinite(t) else None


def _ray_triangle_tolerant(o, d, a, b, c, tol):
    """Two-sided Moller-Trumbore with barycentric bounds widened by ``tol``; numerators are divided by the
    determinant directly (a subnormal determinant's reciprocal would overflow). Non-finite values miss."""
    e1, e2 = _sub(b, a), _sub(c, a)
    pv = _cross(d, e2)
    det = _dot(e1, pv)
    if det == 0.0:
        return None
    tv = _sub(o, a)
    u = _dot(tv, pv) / det
    if not (-tol <= u <= 1.0 + tol):
        return None
    qv = _cross(tv, e1)
    v = _dot(d, qv) / det
    if not (v >= -tol and u + v <= 1.0 + tol):
        return None
    t = _dot(e2, qv) / det
    return t if math.isfinite(t) else None


def segment_triangle_distance(p, q, a, b, c):
    """Closest distance between segment ``pq`` and triangle ``abc`` (two-sided; 0 when they intersect).
    Degenerate triangles (:func:`triangle_is_degenerate`) are measured through their edges only."""
    best = math.inf
    if not triangle_is_degenerate(a, b, c):
        t = _ray_triangle(p, _sub(q, p), a, b, c)
        if t is not None and 0.0 <= t <= 1.0:
            return 0.0
        best = math.sqrt(min(_dist2(p, closest_point_triangle(p, a, b, c)),
                             _dist2(q, closest_point_triangle(q, a, b, c))))
    for u, v in ((a, b), (b, c), (c, a)):
        best = min(best, segment_segment_distance(p, q, u, v))
    return best


def _finite_real(x):
    """A real number (not bool) with a finite float value; integers are bounded before any conversion, so an
    oversized int is rejected instead of raising OverflowError."""
    if isinstance(x, bool):
        return False
    if isinstance(x, int):
        return -sys.float_info.max <= x <= sys.float_info.max
    return isinstance(x, float) and math.isfinite(x)


def _check_points(points, what):
    pts = []
    for p in points:
        if len(p) != 3 or not all(_finite_real(x) for x in p):
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
    with ``radius`` metres: those with a triangle at distance <= ``radius`` (+ CONTACT_TOL_M) from a path segment.

    Returns a sorted list of object indices (into ``col.objects``; names are ``col.objects[k]["name"]``), or a
    :data:`CapsuleResult` ``(objects, work)`` when ``result`` is true. A single point is a sphere. Raises
    LimitError when more than ``max_work`` object/triangle visits would be needed."""
    pts = _check_points(path_points, "path_points")
    if not pts:
        raise ValueError("path_points must hold at least one point")
    if not (_finite_real(radius) and radius >= 0.0):
        raise ValueError("radius must be a finite number >= 0")
    segs = list(zip(pts, pts[1:])) or [(pts[0], pts[0])]
    budget = _Budget(max_work)
    reach = radius + CONTACT_TOL_M                  # the inclusive contact distance, used by every test below
    pad = reach + AABB_TABLE_TOL_M
    bounds = []
    for p, q in segs:
        bounds.append(((min(p[0], q[0]), min(p[1], q[1]), min(p[2], q[2])),
                       (max(p[0], q[0]), max(p[1], q[1]), max(p[2], q[2]))))
    v, idx = col.vertices, col.indices
    whole = (tuple(min(b[0][a] for b in bounds) for a in range(3)), tuple(max(b[1][a] for b in bounds) for a in range(3)))
    hits = []
    for k, e in enumerate(col.objects):
        box = e["aabb"]
        s0, n = e["tri_start"], e["tri_count"]
        if len(segs) > 1 and not _box_overlap(whole[0], whole[1], box, pad):   # whole path misses the object
            budget.spend()
            continue
        hit = False
        grid = _tri_grid(col, k, s0, n) if n > _GRID_MIN_TRIS else None
        boxes = grid[2] if grid is not None else _tri_boxes(col, k, s0, n)
        for (p, q), (lo, hi) in zip(segs, bounds):
            budget.spend()
            if not _box_overlap(lo, hi, box, pad):
                continue
            scan = False
            cand = _grid_candidates(grid, lo, hi, reach) if grid is not None else None
            if cand is not None:
                budget.spend(len(cand))
                tris = ((t, boxes[t - s0]) for t in cand)
            else:
                scan = True
                tris = ((t, boxes[t - s0]) for t in range(s0, s0 + n))
            for t, tb in tris:
                if scan:
                    budget.spend()
                if not _box_overlap(lo, hi, tb, reach):
                    continue
                a, b, c = v[idx[3 * t]], v[idx[3 * t + 1]], v[idx[3 * t + 2]]
                if _plane_clear(p, q, a, b, c, reach):
                    continue
                if segment_triangle_distance(p, q, a, b, c) <= reach:
                    hit = True
                    break
            if hit:
                break
        if hit:
            hits.append(k)
    return CapsuleResult(hits, budget.work) if result else hits


def _tri_boxes(col, k, s0, n):
    """Cached per-triangle boxes of collision object ``k`` (built once, O(triangles))."""
    cache = col.__dict__.setdefault("_tri_box_cache", {})
    boxes = cache.get(k)
    if boxes is None:
        v, idx = col.vertices, col.indices
        boxes = cache[k] = []
        for t in range(s0, s0 + n):
            a, b, c = v[idx[3 * t]], v[idx[3 * t + 1]], v[idx[3 * t + 2]]
            boxes.append((min(a[0], b[0], c[0]), min(a[1], b[1], c[1]), min(a[2], b[2], c[2]),
                          max(a[0], b[0], c[0]), max(a[1], b[1], c[1]), max(a[2], b[2], c[2])))
    return boxes


def _plane_clear(p, q, a, b, c, reach):
    """True when both segment ends lie farther than ``reach`` from the triangle's plane on the same side: no
    contact is possible (the distance to a triangle is at least the distance to its plane)."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    nn = math.sqrt(nx * nx + ny * ny + nz * nz)
    if nn < 1e-12:
        return False
    dp = nx * (p[0] - a[0]) + ny * (p[1] - a[1]) + nz * (p[2] - a[2])
    dq = nx * (q[0] - a[0]) + ny * (q[1] - a[1]) + nz * (q[2] - a[2])
    lim = (reach + 1e-6) * nn
    return (dp > lim and dq > lim) or (dp < -lim and dq < -lim)


_GRID_MIN_TRIS = 256
_GRID_CELL_M = 8.0
_GRID_MAX_TRI_CELLS = 64        # a triangle spanning more cells is kept in a short "big" list instead
_GRID_MAX_QUERY_CELLS = 1024    # a query spanning more cells falls back to the (budgeted) triangle scan


def _tri_grid(col, k, s0, n):
    """Cached ``(cell dict, cell size, per-triangle boxes, big triangle ids)`` of collision object ``k``: map
    cells -> triangle ids. Cells per triangle are capped, so the build is O(triangles)."""
    cache = col.__dict__.setdefault("_tri_grids", {})
    if k in cache:
        return cache[k]
    v, idx = col.vertices, col.indices
    cells, boxes, big, cs = {}, [], [], _GRID_CELL_M
    inserted, limit = 0, _GRID_MAX_TRI_CELLS * n     # enumeration guard: the per-triangle cap keeps it below
    for t in range(s0, s0 + n):
        a, b, c = v[idx[3 * t]], v[idx[3 * t + 1]], v[idx[3 * t + 2]]
        tb = (min(a[0], b[0], c[0]), min(a[1], b[1], c[1]), min(a[2], b[2], c[2]),
              max(a[0], b[0], c[0]), max(a[1], b[1], c[1]), max(a[2], b[2], c[2]))
        boxes.append(tb)
        i0, i1 = math.floor(tb[0] / cs), math.floor(tb[3] / cs)
        j0, j1 = math.floor(tb[1] / cs), math.floor(tb[4] / cs)
        if (i1 - i0 + 1) * (j1 - j0 + 1) > _GRID_MAX_TRI_CELLS:
            big.append(t)
            continue
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                inserted += 1
                if inserted > limit:
                    raise LimitError("triangle grid cell enumeration exceeded its bound")
                cells.setdefault((i, j), []).append(t)
    cache[k] = (cells, cs, boxes, big)
    return cache[k]


def _grid_candidates(grid, lo, hi, reach):
    """Triangle ids near the box, or None when it spans too many cells (the caller scans instead)."""
    cells, cs, _, big = grid
    i0, i1 = math.floor((lo[0] - reach) / cs), math.floor((hi[0] + reach) / cs)
    j0, j1 = math.floor((lo[1] - reach) / cs), math.floor((hi[1] + reach) / cs)
    if (i1 - i0 + 1) * (j1 - j0 + 1) > _GRID_MAX_QUERY_CELLS:
        return None
    out = set(big)
    seen = 0
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            seen += 1
            if seen > _GRID_MAX_QUERY_CELLS:   # enumeration guard: the cap above keeps it from firing
                raise LimitError("triangle grid query cell enumeration exceeded its bound")
            out.update(cells.get((i, j), ()))
    return sorted(out)


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
    ``direction`` is normalised, after scaling by its largest component so huge or tiny directions neither
    overflow nor underflow). Returns :data:`RayHit` ``(t, triangle, object)`` or None; ties go to the lower
    triangle index; degenerate triangles (:func:`triangle_is_degenerate`) are never hit. Raises ValueError
    for a zero direction and LimitError when over ``max_work``."""
    (o,) = _check_points([origin], "origin")
    (d,) = _check_points([direction], "direction")
    m = max(abs(d[0]), abs(d[1]), abs(d[2]))
    if m == 0.0:
        raise ValueError("direction must not be zero")
    d = (d[0] / m, d[1] / m, d[2] / m)
    n = math.sqrt(_dot(d, d))
    if not (_finite_real(max_dist) and max_dist >= 0.0):
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
            a, b, c = v[idx[3 * t]], v[idx[3 * t + 1]], v[idx[3 * t + 2]]
            if triangle_is_degenerate(a, b, c):
                continue
            hit = _ray_triangle(o, d, a, b, c)
            if hit is None or hit < 0.0 or hit > max_dist:     # (either test's hit counts; see RAY_EDGE_TOL)
                hit = _ray_triangle_tolerant(o, d, a, b, c, RAY_EDGE_TOL)
            if hit is None or hit < 0.0 or hit > max_dist:
                continue
            if best is None or hit < best.t or (hit == best.t and t < best.triangle):
                best = RayHit(hit, t, k)
    return best
