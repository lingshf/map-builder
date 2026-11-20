"""Roof shapes of extruded building footprints.

``generate.build_building`` computes the eave and total heights (OSM semantics) and the wall
volume; this module decides which roof shape can be built on the footprint
(:func:`plan_roof`, with ``fallback:`` provenance; a hipped roof on a non-rectangle is planned from the
straight skeleton) and adds the roof faces
(:func:`build_roof`). It depends on nothing in ``generate``.
"""

import math
from dataclasses import dataclass

from .errors import LimitError
from .skeleton import SkeletonError, straight_skeleton
from .triangulate import TriangulationError, triangulate
# Shapes that need a rectangular footprint, and those taking roof:orientation / roof:direction.
RECT_SHAPES = {"gabled", "hipped", "half-hipped", "gambrel", "mansard", "round", "saltbox"}
ORIENTED_SHAPES = {"gabled", "hipped", "half-hipped", "gambrel", "round", "saltbox"}
DIRECTED_SHAPES = {"gabled", "saltbox"}
CONVEX_SHAPES = {"pyramidal", "dome", "onion"}
SUPPORTED_SHAPES = {"flat", "skillion"} | RECT_SHAPES | CONVEX_SHAPES
MAX_ROOF_TRIANGLES = 25000

PLANAR_TOL_M = 1e-6
GABLE_APEX_MIN = 1e-3  # the gable apex lies strictly inside its footprint edge
GABLE_MIN_HEIGHT_RATIO = 0.05  # apex height over the roof's highest point


def rect_check(ring):
    """Return True if ring is a near-rectangle (4 vertices, ~90 deg corners)."""
    if len(ring) != 4:
        return False
    for k in range(4):
        a, b, c = ring[k - 1], ring[k], ring[(k + 1) % 4]
        v1 = (a[0] - b[0], a[1] - b[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 < 0.5 or n2 < 0.5:
            return False
        if abs((v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)) > math.sin(math.radians(15)):
            return False
    return True


def is_convex(ring):
    n = len(ring)
    for k in range(n):
        a, b, c = ring[k - 1], ring[k], ring[(k + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-9:
            return False
    return True


def add_planar_face(mesh, idx, mat, col, tol=PLANAR_TOL_M):
    """Add face ``idx``; a polygon with > 3 vertices that is not planar within ``tol`` metres
    is added as explicit triangles instead (a quad along its shorter diagonal, otherwise a
    fan), keeping the winding. Returns True if the face was split."""
    if len(idx) > 3:
        V = [mesh.vertices[i] for i in idx]
        n = len(V)
        nx_ = sum((V[k][1] - V[(k + 1) % n][1]) * (V[k][2] + V[(k + 1) % n][2]) for k in range(n))
        ny_ = sum((V[k][2] - V[(k + 1) % n][2]) * (V[k][0] + V[(k + 1) % n][0]) for k in range(n))
        nz_ = sum((V[k][0] - V[(k + 1) % n][0]) * (V[k][1] + V[(k + 1) % n][1]) for k in range(n))
        ln = math.sqrt(nx_ * nx_ + ny_ * ny_ + nz_ * nz_)
        c = [sum(v[d] for v in V) / n for d in range(3)]
        if ln <= 1e-12 or max(abs((v[0] - c[0]) * nx_ + (v[1] - c[1]) * ny_ + (v[2] - c[2]) * nz_) / ln
                              for v in V) > tol:
            if n == 4 and math.dist(V[1], V[3]) < math.dist(V[0], V[2]):
                tris = [(idx[1], idx[2], idx[3]), (idx[1], idx[3], idx[0])]
            else:
                tris = [(idx[0], idx[k], idx[k + 1]) for k in range(1, n - 1)]
            for t in tris:
                mesh.add_face(t, mat, col)
            return True
    mesh.add_face(idx, mat, col)
    return False


def resolve_shape(shape_tag, outer, holes, prov, skeleton_hipped=False):
    """The roof shape that can be built for ``roof:shape`` on this footprint; sets
    ``prov["roof_shape"]`` (``measured:``/``inferred:``/``fallback:``). With ``skeleton_hipped`` a hipped
    roof on a non-rectangular footprint is kept (``plan_roof`` builds it from the straight skeleton)."""
    shape = shape_tag or "flat"
    prov["roof_shape"] = "measured:osm roof:shape" if shape_tag else "inferred:flat"
    if shape not in SUPPORTED_SHAPES:
        prov["roof_shape"] = f"fallback:flat (roof:shape={shape} not modelled)"
        shape = "flat"
    if holes and shape not in ("flat", "skillion"):
        prov["roof_shape"] = f"fallback:flat (roof:shape={shape} with courtyard)"
        shape = "flat"
    if shape in RECT_SHAPES and not rect_check(outer) and not (skeleton_hipped and shape in ("hipped", "gabled")):
        if is_convex(outer):
            prov["roof_shape"] = f"fallback:pyramidal (roof:shape={shape} on non-rectangular footprint)"
            shape = "pyramidal"
        else:
            prov["roof_shape"] = f"fallback:flat (roof:shape={shape} on non-rectangular footprint)"
            shape = "flat"
    if shape in ("pyramidal", "dome", "onion") and not is_convex(outer):
        prov["roof_shape"] = f"fallback:flat ({shape} roof on concave footprint)"
        shape = "flat"
    return shape


@dataclass
class RoofPlan:
    """The roof decided before any mesh is allocated (``plan_roof``).

    ``shape_built`` is the shape that will be emitted. A skeleton roof additionally carries
    ``points`` (``(x, y, t)`` in the mesh's local frame; the first ``n_ring`` are the footprint
    vertices at t = 0, the rest new roof vertices) and ``tris`` (index triples into ``points``,
    counter-clockwise seen from above), so its exact vertex and triangle counts are known."""
    shape_built: str
    n_ring: int = 0
    points: list = None
    tris: list = None
    t_max: float = 0.0
    ends: list = None  # gable-end triangles (index triples into ``points``), emitted vertical as MB Facade

    @property
    def skeleton(self):
        return self.points is not None


def flat_plan():
    return RoofPlan("flat")


class _GableError(Exception):
    """A gable end that cannot be built (the reason is the message); the plan falls back to hipped."""


def plan_roof(shape_tag, outer, holes, prov, orientation=None, direction=None):
    """Preflight of the roof: the shape that will be built for ``roof:shape`` on this footprint
    (``outer``/``holes`` in the mesh's local frame), with its skeleton for a hipped or gabled roof on a
    non-rectangular footprint. ``orientation`` (``roof:orientation``) and ``direction`` (``roof:direction``
    in degrees) pick the gable ends. Sets ``prov["roof_shape"]``; a gable end that is not representable
    falls back to the hipped skeleton roof and a skeleton failure to the v0.3.0 outcome, with the reason
    appended."""
    shape = resolve_shape(shape_tag, outer, holes, prov, skeleton_hipped=True)
    if shape not in ("hipped", "gabled") or rect_check(outer):
        return RoofPlan(shape)
    try:
        sk = straight_skeleton(outer)
        if shape == "gabled":
            try:
                return _skeleton_plan(outer, sk, _gable_ends(sk, orientation, direction, prov))
            except _GableError as exc:
                prov["roof_shape"] = f"fallback:hipped (gable end not representable: {exc})"
                prov.pop("roof_orientation", None)
        return _skeleton_plan(outer, sk)
    except (SkeletonError, LimitError, TriangulationError) as exc:
        convex = is_convex(outer)
        shape = "pyramidal" if convex else "flat"
        prov["roof_shape"] = (f"fallback:{shape} (roof:shape={shape_tag} on non-rectangular footprint; "
                              f"straight skeleton: {exc})")
        prov.pop("roof_orientation", None)
        return RoofPlan(shape)


def _min_area_axes(ring):
    """Unit vectors (long, short) of the minimum-area bounding rectangle of ``ring``."""
    best = None
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        ln = math.dist(a, b)
        if ln <= 1e-9:
            continue
        u = ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln)
        v = (-u[1], u[0])
        pu = [p[0] * u[0] + p[1] * u[1] for p in ring]
        pv = [p[0] * v[0] + p[1] * v[1] for p in ring]
        w, h = max(pu) - min(pu), max(pv) - min(pv)
        if best is None or w * h < best[0] - 1e-9:
            best = (w * h, u, v, w, h)
    _, u, v, w, h = best
    return (u, v) if w >= h else (v, u)


def _gable_ends(sk, orientation, direction, prov):
    """Faces of the skeleton to turn into gable ends: the triangular faces at a ridge end whose footprint edge is
    perpendicular (within 45 degrees) to the ridge axis. The ridge axis is the long side of the minimum-area
    bounding rectangle, or the short one for ``roof:orientation=across``; without an orientation a
    ``roof:direction`` puts the ridge perpendicular to the way the slope faces."""
    long_axis, short_axis = _min_area_axes(sk.ring)
    if orientation in ("along", "across"):
        prov["roof_orientation"] = f"measured:osm roof:orientation={orientation}"
        across = orientation == "across"
    elif orientation is None and direction is not None:
        d = _bearing(direction)
        across = abs(d[0] * long_axis[0] + d[1] * long_axis[1]) > math.sqrt(0.5)
        prov["roof_orientation"] = (f"measured:osm roof:direction={direction:g} "
                                    "(ridge perpendicular to the slope direction)")
    else:
        across = False
        prov["roof_orientation"] = ("inferred:along (ridge parallel to the longer side of the minimum-area "
                                    "bounding rectangle)" if orientation is None else
                                    f"fallback:along (roof:orientation={orientation} not recognised)")
    axis = short_axis if across else long_axis
    n = len(sk.ring)
    ridge_ends = []
    reasons = []
    for i, f in enumerate(sk.faces):
        if len(f) == 3:
            try:
                _gable_node(sk, i)
                ridge_ends.append(i)
            except _GableError as exc:
                reasons.append(str(exc))
    if len(ridge_ends) < 2:
        raise _GableError(reasons[0] if reasons else "the skeleton has fewer than two ridge ends")
    ends = []
    for i in ridge_ends:
        a, b = sk.ring[i], sk.ring[(i + 1) % n]
        if abs((b[0] - a[0]) * axis[0] + (b[1] - a[1]) * axis[1]) / math.dist(a, b) <= math.sqrt(0.5):
            ends.append(i)
    return tuple(ends if len(ends) >= 2 else ridge_ends)


def _gable_node(sk, i):
    """The gable apex of triangular face ``i`` (A, B, N) as ``((x, y, t), N)``: where the ridge through N meets
    the footprint edge A-B. The faces beside the end keep their planes, N becomes this point."""
    n = len(sk.ring)
    A, B = sk.ring[i], sk.ring[(i + 1) % n]
    N = sk.faces[i][2]
    prev, nxt = sk.faces[(i - 1) % n], sk.faces[(i + 1) % n]
    if sum(N in f for f in sk.faces) != 3 or N not in prev or N not in nxt:
        raise _GableError("the ridge end is a node of more than three faces")
    k, m = prev.index(N), nxt.index(N)
    M = prev[(k + 1) % len(prev)]
    if prev[k - 1] != sk.faces[i][0] or nxt[(m + 1) % len(nxt)] != sk.faces[i][1] or nxt[m - 1] != M:
        raise _GableError("the faces beside the gable end do not meet in a ridge")
    if M < n:
        raise _GableError("the ridge ends on a footprint corner")
    p0, p1 = sk.ring[(i - 1) % n], sk.ring[(i + 2) % n]

    def dist(a, b, p):
        return ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / math.dist(a, b)

    fa, fb = dist(p0, A, A) - dist(B, p1, A), dist(p0, A, B) - dist(B, p1, B)
    if abs(fa - fb) <= 1e-9:
        raise _GableError("the ridge runs along the gable edge")
    u = fa / (fa - fb)
    if not GABLE_APEX_MIN < u < 1 - GABLE_APEX_MIN:
        raise _GableError("the ridge meets the gable edge outside it")
    p = (A[0] + u * (B[0] - A[0]), A[1] + u * (B[1] - A[1]))
    t = dist(p0, A, p)
    nn, mm = sk.nodes[N], sk.nodes[M]
    if (t <= 1e-6 or abs(t - dist(B, p1, p)) > 1e-6
            or (p[0] - nn[0]) * (nn[0] - mm[0]) + (p[1] - nn[1]) * (nn[1] - mm[1]) <= 0):
        raise _GableError("the ridge does not reach the gable edge")
    if t < GABLE_MIN_HEIGHT_RATIO * max(q[2] for q in sk.nodes):
        raise _GableError("the gable end would be a sliver")
    return (p[0], p[1], t), N


def _skeleton_plan(outer, sk, ends=()):
    n = len(outer)
    nodes = list(sk.nodes)
    faces = [list(f) for f in sk.faces]
    gable_apex = {}
    for i in ends:
        apex, N = _gable_node(sk, i)
        nodes.append(apex)
        gable_apex[i] = len(nodes) - 1
        for j in ((i - 1) % len(sk.ring), (i + 1) % len(sk.ring)):
            faces[j][faces[j].index(N)] = len(nodes) - 1
    index = {(float(p[0]), float(p[1])): k for k, p in enumerate(outer)}
    node_to_pt = {}
    points = [(float(p[0]), float(p[1]), 0.0) for p in outer]
    for k in sorted({k for i, f in enumerate(faces) if i not in gable_apex for k in f}
                    | set(range(len(sk.ring))) | set(gable_apex.values())):
        if k < len(sk.ring):
            node_to_pt[k] = index[sk.ring[k]]
        else:
            node_to_pt[k] = len(points)
            points.append(nodes[k])
    in_skeleton = set(node_to_pt[k] for k in range(len(sk.ring)))
    extra = [k for k in range(n) if k not in in_skeleton]
    tris, gable_tris = [], []
    for i, face in enumerate(faces):
        pts = [(nodes[k][0], nodes[k][1]) for k in face]
        a, b = pts[0], pts[1]
        between = sorted((u, k) for k in extra for u in [_along(outer[k], a, b)] if u is not None)
        fan = [k for _, k in between]
        if i in gable_apex:
            chain = [node_to_pt[face[0]]] + fan + [node_to_pt[face[1]]]
            top = node_to_pt[gable_apex[i]]
            gable_tris += [(chain[j], chain[j + 1], top) for j in range(len(chain) - 1)]
            continue
        local = triangulate(pts, list(range(len(pts))))
        for (p, q, r) in local:
            tri = [p, q, r]
            if _signed(pts[p], pts[q], pts[r]) < 0:
                tri = [p, r, q]
            ids = [node_to_pt[face[v]] for v in tri]
            if fan:
                at = next((j for j in range(3) if tri[j] == 0 and tri[(j + 1) % 3] == 1), None)
                if at is not None:
                    c = ids[(at + 2) % 3]
                    chain = [ids[at]] + fan + [ids[(at + 1) % 3]]
                    tris += [(chain[j], chain[j + 1], c) for j in range(len(chain) - 1)]
                    continue
            tris.append(tuple(ids))
    t_max = max(p[2] for p in points)
    if t_max <= 0:
        raise SkeletonError("the skeleton has no height")
    if len(tris) + len(gable_tris) > MAX_ROOF_TRIANGLES:
        raise LimitError(f"skeleton roof needs {len(tris) + len(gable_tris)} triangles (limit {MAX_ROOF_TRIANGLES})")
    return RoofPlan("gabled" if ends else "hipped", n, points, tris, t_max, gable_tris)


def _signed(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _along(p, a, b, tol=1e-5):
    """Parameter of ``p`` along ``a`` -> ``b`` if it lies strictly between them on the segment, else None."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln2 = dx * dx + dy * dy
    u = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ln2
    if 0.0 < u < 1.0 and abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / math.sqrt(ln2) <= tol:
        return u
    return None


def roof_budget(plan, n_ring, n_footprint_tris):
    """Exact ``(vertices, triangles)`` the roof adds on top of the wall ring (2 n vertices, 2 n wall and
    ``n_footprint_tris`` floor triangles): for a skeleton roof what the plan will emit, otherwise the
    per-shape upper bound of :func:`shape_budget` plus the fixed apex/ridge and flat-top allowance."""
    if plan.skeleton:
        return len(plan.points) - plan.n_ring, len(plan.tris) + len(plan.ends or ())
    extra_v, extra_t = shape_budget(plan.shape_built, n_ring)
    return 2 + extra_v, n_footprint_tris + 4 + extra_t


def resolve_orientation(shape, tags, prov, outer=None, direction=None):
    """True if the ridge runs across (parallel to the shorter side); sets
    ``prov["roof_orientation"]``. Without ``roof:orientation``, a ``roof:direction``
    (``direction`` in degrees, the way the slope faces) puts the ridge perpendicular to it."""
    across = False
    orient_tag = tags.get("roof:orientation")
    if shape in ORIENTED_SHAPES:
        if orient_tag in ("along", "across"):
            prov["roof_orientation"] = f"measured:osm roof:orientation={orient_tag}"
            across = orient_tag == "across"
        elif orient_tag is None and direction is not None and shape in DIRECTED_SHAPES and outer is not None:
            frame = _frame(outer, False)
            d = _bearing(direction)
            ridge_axis = _sub(frame[1], frame[0])  # along the longer side
            across = abs(d[0] * ridge_axis[0] + d[1] * ridge_axis[1]) > math.sqrt(0.5) * math.hypot(*ridge_axis)
            prov["roof_orientation"] = (f"measured:osm roof:direction={direction:g} "
                                        "(ridge perpendicular to the slope direction)")
        elif orient_tag is None:
            prov["roof_orientation"] = "inferred:along (ridge parallel to the longer side)"
        else:
            prov["roof_orientation"] = f"fallback:along (roof:orientation={orient_tag} not recognised)"
    elif orient_tag is not None:
        prov["roof_orientation"] = f"ignored:roof:orientation={orient_tag} (roof built {shape})"
    return across


def _bearing(direction):
    r = math.radians(direction)
    return math.sin(r), math.cos(r)


def _sub(p, q):
    return q[0] - p[0], q[1] - p[1]


def _frame(ring, across):
    """Rectangle corners a, b, c, d (CCW, as ring points) with the ridge parallel to a-b: along
    the longer side, or the shorter one if ``across``."""
    a, b, c, d = ring
    if (math.dist(a[:2], b[:2]) < math.dist(b[:2], c[:2])) != across:
        a, b, c, d = b, c, d, a
    return a, b, c, d

def skillion_surface(shape, rings, direction, top, roof_h, prov):
    """For a skillion roof, a function (x, y) -> roof underside z; else None. ``direction`` is the parsed\n    ``roof:direction`` in degrees (None if absent)."""
    if shape != "skillion":
        return None
    if direction is None:
        prov["roof_direction"] = "inferred:0 (north-facing slope)"
        direction = 0.0
    direction %= 360.0
    d = (math.sin(math.radians(direction)), math.cos(math.radians(direction)))
    proj = [p[0] * d[0] + p[1] * d[1] for r in rings for p in r]
    smin, smax = min(proj), max(proj)
    span = max(smax - smin, 1e-6)

    def skillion_z(p):
        s = p[0] * d[0] + p[1] * d[1]
        return top - roof_h * (s - smin) / span
    return skillion_z


# Cross-section profiles (t across 0..1, z as a fraction of the roof height) of the shapes
# extruded along the ridge; the end walls are vertical.
GAMBREL = [(0.0, 0.0), (0.18, 0.62), (0.5, 1.0), (0.82, 0.62), (1.0, 0.0)]
SALTBOX_RIDGE_T = 1.0 / 3.0
ROUND_SEGMENTS = 8
DOME_SEGMENTS = 6
# onion: (scale, z fraction) of the rings above the eave, sampled at t = k / 7; the apex follows
ONION = [(1.0, 0.0), (0.97, 0.10), (0.85, 0.25), (0.62, 0.42), (0.38, 0.60), (0.22, 0.76), (0.10, 0.89),
         (0.0, 1.0)]
MANSARD_LOW_INSET, MANSARD_TOP_INSET, MANSARD_BREAK_Z = 0.15, 0.30, 0.65  # x short side, x short side, x roof_h
HALF_HIP_INSET, HALF_HIP_WALL_Z = 0.25, 0.5  # ridge end inset x short side; gable wall height x roof_h


def dome_rings(n_ring, segments):
    """Intermediate rings used for ``segments`` (fewer for a huge footprint so the roof stays
    within MAX_ROOF_TRIANGLES: n x (2 x rings + 1) triangles)."""
    return max(0, min(segments - 1, (MAX_ROOF_TRIANGLES // max(n_ring, 1) - 1) // 2))


def shape_budget(shape, n_ring):
    """(vertices, triangles) a roof of ``shape`` adds beyond what ``build_building`` reserves
    for the wall ring, the footprint and the apex (2 n + 2 vertices, 2 n + 2 tris + 4)."""
    if shape in ("dome", "onion"):
        rings = dome_rings(n_ring, DOME_SEGMENTS if shape == "dome" else len(ONION) - 1)
        return n_ring * rings, n_ring * 2 * rings
    if shape in RECT_SHAPES and shape not in ("gabled", "hipped"):
        return 24, 40
    return 0, 0


def _dome_profile(n_ring, shape):
    rings = dome_rings(n_ring, DOME_SEGMENTS if shape == "dome" else len(ONION) - 1)
    out = []
    for k in range(1, rings + 1):
        if shape == "dome":
            th = (math.pi / 2) * k / (rings + 1)
            out.append((math.cos(th), math.sin(th)))
        else:
            f = k * (len(ONION) - 1) / (rings + 1)
            i = min(int(f), len(ONION) - 2)
            u = f - i
            out.append((ONION[i][0] + (ONION[i + 1][0] - ONION[i][0]) * u,
                        ONION[i][1] + (ONION[i + 1][1] - ONION[i][1]) * u))
    return out


def build_roof(mesh, ring, holes, eave_z, roof_h, plan, tags, prov, *, top_idx, tris, add_face,
               roof_col, facade, across=False, direction=None):
    """Emit the ``plan`` (``plan_roof``) on the wall-top vertices ``top_idx`` (one index list
    per ring, outer first, in the mesh's local frame). ``ring``/``holes`` are the local
    footprint rings, the wall tops are at ``eave_z`` (sloped for a skillion), the highest
    point is ``eave_z + roof_h``. ``tris`` triangulates the footprint over the flattened
    ``top_idx``; ``add_face(idx, material, colour)`` adds (and counts split) faces.
    ``across`` swaps the ridge axis of rectangular shapes; ``direction`` (degrees, the way
    the long slope of a saltbox faces) is the parsed ``roof:direction``. The plan fixes the shape."""
    shape = plan.shape_built
    top = eave_z + roof_h
    flat_top = [i for rt in top_idx for i in rt]
    R = "MB Roof"
    if plan.skeleton:
        scale = roof_h / plan.t_max
        ids = list(top_idx[0])
        for x, y, t in plan.points[plan.n_ring:]:
            ids.append(mesh.add_vertex(x, y, top if t >= plan.t_max else eave_z + t * scale))
        for (a, b, c) in plan.tris:
            mesh.add_face((ids[a], ids[b], ids[c]), R, roof_col)
        for (a, b, c) in plan.ends or ():
            mesh.add_face((ids[a], ids[b], ids[c]), "MB Facade", facade)
        return
    if shape in ("flat", "skillion"):
        for (a, b, c) in tris:
            add_face((flat_top[a], flat_top[b], flat_top[c]), R, roof_col)
    elif shape == "pyramidal":
        apex = mesh.add_vertex(0.0, 0.0, top)
        rt = top_idx[0]
        for k in range(len(rt)):
            add_face((rt[k], rt[(k + 1) % len(rt)], apex), R, roof_col)
    elif shape in ("dome", "onion"):
        rt = top_idx[0]
        n = len(rt)
        prev = rt
        for s, zf in _dome_profile(n, shape):
            cur = [mesh.add_vertex(ring[k][0] * s, ring[k][1] * s, eave_z + roof_h * zf) for k in range(n)]
            for k in range(n):
                j = (k + 1) % n
                add_face((prev[k], prev[j], cur[j], cur[k]), R, roof_col)
            prev = cur
        apex = mesh.add_vertex(0.0, 0.0, top)
        for k in range(n):
            add_face((prev[k], prev[(k + 1) % n], apex), R, roof_col)
    elif shape in ("gabled", "hipped"):  # on rectangle a,b,c,d (CCW); ridge runs parallel to a-b
        rt = top_idx[0]
        V = mesh.vertices
        a, b, c, d = rt
        # along: a-b is a long side (ridge along the long axis); across: a-b is a short side.
        if (math.dist(V[a][:2], V[b][:2]) < math.dist(V[b][:2], V[c][:2])) != across:
            a, b, c, d = b, c, d, a
        m1 = tuple((V[b][i] + V[c][i]) / 2 for i in range(2))
        m2 = tuple((V[d][i] + V[a][i]) / 2 for i in range(2))
        if shape == "hipped":
            end = math.dist(V[b][:2], V[c][:2])
            ridge_span = math.dist(m1, m2)
            t = min(0.5 * end / max(ridge_span, 1e-6), 0.49)
            r1 = (m1[0] + (m2[0] - m1[0]) * t, m1[1] + (m2[1] - m1[1]) * t)
            r2 = (m2[0] + (m1[0] - m2[0]) * t, m2[1] + (m1[1] - m2[1]) * t)
        else:
            r1, r2 = m1, m2
        R1 = mesh.add_vertex(r1[0], r1[1], top)
        R2 = mesh.add_vertex(r2[0], r2[1], top)
        add_face((a, b, R1, R2), R, roof_col)
        add_face((c, d, R2, R1), R, roof_col)
        end_mat, end_col = (R, roof_col) if shape == "hipped" else ("MB Facade", facade)
        add_face((b, c, R1), end_mat, end_col)
        add_face((d, a, R2), end_mat, end_col)
    else:
        _rect_roof(mesh, top_idx[0], eave_z, roof_h, shape, tags, prov, add_face, roof_col, facade, across,
                   direction)


def _rect_roof(mesh, rt, eave_z, roof_h, shape, tags, prov, add_face, roof_col, facade, across, direction):
    """half-hipped / gambrel / round / saltbox / mansard on the rectangle ``rt`` (a, b, c, d CCW)."""
    V = mesh.vertices
    R = "MB Roof"
    a, b, c, d = rt
    if (math.dist(V[a][:2], V[b][:2]) < math.dist(V[b][:2], V[c][:2])) != across:
        a, b, c, d = b, c, d, a
    A, B, C, D = (V[i][:2] for i in (a, b, c, d))
    eave = {(0.0, 0.0): a, (1.0, 0.0): b, (1.0, 1.0): c, (0.0, 1.0): d}

    def pt(s, t, zf):
        """Vertex at fraction s along a-b and t along a-d (bilinear over the corners), z = eave + zf x roof_h;
        the eave corners reuse the wall-top vertices."""
        if zf == 0.0 and (s, t) in eave:
            return eave[(s, t)]
        x = A[0] * (1 - s) * (1 - t) + B[0] * s * (1 - t) + C[0] * s * t + D[0] * (1 - s) * t
        y = A[1] * (1 - s) * (1 - t) + B[1] * s * (1 - t) + C[1] * s * t + D[1] * (1 - s) * t
        return mesh.add_vertex(x, y, eave_z + roof_h * zf)

    len_s, len_t = math.dist(A, B), math.dist(A, D)
    short = min(len_s, len_t)

    if shape == "mansard":
        e1, e2 = MANSARD_LOW_INSET * short, MANSARD_TOP_INSET * short
        rings = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]]
        for e, zf in ((e1, MANSARD_BREAK_Z), (e2, 1.0)):
            si, ti = e / len_s, e / len_t
            rings.append([(si, ti), (1 - si, ti), (1 - si, 1 - ti), (si, 1 - ti)])
        zs = [0.0, MANSARD_BREAK_Z, 1.0]
        idx = [[pt(s, t, z) for (s, t) in r] for r, z in zip(rings, zs)]
        for lo, hi in zip(idx, idx[1:]):
            for k in range(4):
                j = (k + 1) % 4
                add_face((lo[k], lo[j], hi[j], hi[k]), R, roof_col)
        add_face(tuple(idx[2]), R, roof_col)  # flat top
        return

    if shape == "half-hipped":
        e = min(HALF_HIP_INSET * short / len_s, 0.25)
        zw = HALF_HIP_WALL_Z
        r1, r2 = pt(e, 0.5, 1.0), pt(1 - e, 0.5, 1.0)
        q1a, q2a = pt(0.0, 0.5 * zw, zw), pt(0.0, 1 - 0.5 * zw, zw)
        q1b, q2b = pt(1.0, 0.5 * zw, zw), pt(1.0, 1 - 0.5 * zw, zw)
        add_face((a, b, q1b, r2, r1, q1a), R, roof_col)
        add_face((c, d, q2a, r1, r2, q2b), R, roof_col)
        add_face((d, a, q1a, q2a), "MB Facade", facade)
        add_face((b, c, q2b, q1b), "MB Facade", facade)
        add_face((q1a, r1, q2a), R, roof_col)
        add_face((q2b, r2, q1b), R, roof_col)
        return

    # shapes extruded along the ridge: the profile runs from the a-b eave (t = 0) to the d-c eave
    if shape == "gambrel":
        prof = GAMBREL
    elif shape == "round":
        prof = [((1 - math.cos(math.pi * i / ROUND_SEGMENTS)) / 2, math.sin(math.pi * i / ROUND_SEGMENTS))
                for i in range(ROUND_SEGMENTS + 1)]
        prof[0], prof[-1] = (0.0, 0.0), (1.0, 0.0)
    else:  # saltbox: the long slope faces ``direction``; default to the side of d
        n_t = (D[0] - A[0], D[1] - A[1])
        if direction is None:
            long_on_t = True
            prov["roof_direction"] = "inferred:long slope on the side of the second ridge-parallel eave"
        else:
            dv = _bearing(direction)
            long_on_t = dv[0] * n_t[0] + dv[1] * n_t[1] >= 0
            prov["roof_direction"] = f"measured:osm roof:direction={direction:g}"
        rt_ = SALTBOX_RIDGE_T if long_on_t else 1.0 - SALTBOX_RIDGE_T
        prof = [(0.0, 0.0), (rt_, 1.0), (1.0, 0.0)]
    row0 = [pt(0.0, t, z) for t, z in prof]
    row1 = [pt(1.0, t, z) for t, z in prof]
    for i in range(len(prof) - 1):
        add_face((row0[i], row1[i], row1[i + 1], row0[i + 1]), R, roof_col)
    add_face((row0[-1], row0[0]) + tuple(row0[1:-1]), "MB Facade", facade)
    add_face((row1[0], row1[-1]) + tuple(row1[-2:0:-1]), "MB Facade", facade)