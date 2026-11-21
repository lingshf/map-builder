# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Roof shapes of extruded building footprints.

``generate.build_building`` computes the eave and total heights (OSM semantics) and the wall
volume; this module decides which roof shape can be built on the footprint
(:func:`plan_roof`, with ``fallback:`` provenance; a hipped roof on a non-rectangle is planned from the
straight skeleton) and adds the roof faces
(:func:`build_roof`). It depends on nothing in ``generate``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from .errors import LimitError
from .skeleton import Node, Pt, Skeleton, SkeletonError, straight_skeleton
from .triangulate import TriangulationError, triangulate

if TYPE_CHECKING:
    from .structures import Prov
    from .mesh import MeshData

Point: TypeAlias = "Sequence[float]"
Ring: TypeAlias = "Sequence[Point]"
Color: TypeAlias = "Sequence[float]"
Tri: TypeAlias = "tuple[int, int, int]"  # vertex or point indices
AddFace: TypeAlias = "Callable[[Sequence[int], str, Color], None]"  # (vertex indices, material, colour)
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


def rect_check(ring: Ring) -> bool:
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


def is_convex(ring: Ring) -> bool:
    n = len(ring)
    for k in range(n):
        a, b, c = ring[k - 1], ring[k], ring[(k + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-9:
            return False
    return True


def add_planar_face(mesh: MeshData, idx: Sequence[int], mat: str, col: Color, tol: float = PLANAR_TOL_M) -> bool:
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


def resolve_shape(shape_tag: str | None, outer: Ring, holes: Sequence[Ring], prov: Prov,
                  skeleton_hipped: bool = False) -> str:
    """The roof shape that can be built for ``roof:shape`` on this footprint; sets
    ``prov["roof_shape"]`` (``measured:``/``inferred:``/``fallback:``). With ``skeleton_hipped`` a hipped or gabled
    roof on a non-rectangular footprint, and a pyramidal one on a concave footprint, is kept (``plan_roof``
    builds it from the straight skeleton)."""
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
    if shape in ("pyramidal", "dome", "onion") and not is_convex(outer) and not (skeleton_hipped and shape == "pyramidal"):
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
    points: list[Node] | None = None
    tris: list[Tri] | None = None
    t_max: float = 0.0
    ends: list[Tri] | None = None  # gable-end triangles (index triples into ``points``), emitted vertical as MB Facade

    @property
    def skeleton(self) -> bool:
        return self.points is not None


def flat_plan() -> RoofPlan:
    return RoofPlan("flat")


class _GableError(Exception):
    """A gable end that cannot be built (the reason is the message); the plan falls back to hipped."""


def plan_roof(shape_tag: str | None, outer: Ring, holes: Sequence[Ring], prov: Prov,
              orientation: str | None = None, direction: float | None = None) -> RoofPlan:
    """Preflight of the roof: the shape that will be built for ``roof:shape`` on this footprint
    (``outer``/``holes`` in the mesh's local frame), with its skeleton for a hipped or gabled roof on a
    non-rectangular footprint. ``orientation`` (``roof:orientation``) and ``direction`` (``roof:direction``
    in degrees) pick the gable ends. Sets ``prov["roof_shape"]``; a gable end that is not representable
    falls back to the hipped skeleton roof and a skeleton failure to the v0.3.0 outcome, with the reason
    appended."""
    shape = resolve_shape(shape_tag, outer, holes, prov, skeleton_hipped=True)
    analytic_gable = shape == "gabled" and rect_check(outer)
    if analytic_gable:
        across = resolve_orientation("gabled", {"roof:orientation": orientation} if orientation else {}, {},
                                     outer, direction)
        analytic_gable = analytic_gable_slope_error(outer, across) is None
    if shape == "pyramidal" and not is_convex(outer):
        return _concave_pyramid_plan(outer, prov)
    if shape not in ("hipped", "gabled") or (rect_check(outer) and (shape == "hipped" or analytic_gable)):
        return RoofPlan(shape)
    near_rect = rect_check(outer)

    def run(merge: bool, p: Prov) -> RoofPlan:
        sk = straight_skeleton(outer)
        if merge:
            _merge_close_nodes(sk.nodes, sk.faces, len(sk.ring), set(), set())
        if shape == "gabled":
            try:
                return _skeleton_plan(outer, sk, _gable_ends(sk, orientation, direction, p))
            except _GableError as exc:
                cut = exc
            try:
                return _walled_plan(outer, sk, orientation, direction, p, merge)
            except _GableError as exc:
                p["roof_shape"] = (f"fallback:hipped (gable end not representable: {cut}; "
                                   f"vertical cut: {exc})")
                p.pop("roof_orientation", None)
        return _skeleton_plan(outer, sk)

    # The plain skeleton is kept when it gives the wanted roof; nodes a hair apart are merged only to repair it.
    errors = (SkeletonError, LimitError, TriangulationError)
    try:
        p1 = dict(prov)
        plan = run(False, p1)
        if plan.ends or shape != "gabled":
            prov.clear()
            prov.update(p1)
            return plan
        first: tuple[RoofPlan, Prov] | None = (plan, p1)
    except errors as exc:
        first = None
        failure = exc
    try:
        p2 = dict(prov)
        plan = run(True, p2)
        if first is None or plan.ends:
            prov.clear()
            prov.update(p2)
            return plan
    except errors as exc:
        if first is None:
            failure = exc
    if first is not None:
        prov.clear()
        prov.update(first[1])
        return first[0]
    if near_rect:
        prov["roof_shape"] = (f"approximate:gabled (the two slopes of a near-rectangular footprint are not "
                              f"coplanar: {analytic_gable_slope_error(outer, across)}; straight skeleton: {failure})")
        return RoofPlan("gabled")
    convex = is_convex(outer)
    shape = "pyramidal" if convex else "flat"
    prov["roof_shape"] = (f"fallback:{shape} (roof:shape={shape_tag} on non-rectangular footprint; "
                          f"straight skeleton: {failure})")
    prov.pop("roof_orientation", None)
    return RoofPlan(shape)


def _concave_pyramid_plan(outer: Ring, prov: Prov) -> RoofPlan:
    """A pyramidal roof on a concave footprint. The straight skeleton gives one sloped face per footprint edge,
    but a reflex corner always splits the apex into a ridge, which the pyramidal roof signature (a single apex)
    does not accept, so the skeleton roof is built only when it does have one apex; otherwise the roof is flat
    and the reason names what the skeleton found (D105: the checker is unchanged)."""
    try:
        sk = straight_skeleton(outer)
        plan = _skeleton_plan(outer, sk)
    except (SkeletonError, LimitError, TriangulationError) as exc:
        prov["roof_shape"] = f"fallback:flat (pyramidal roof on concave footprint; straight skeleton: {exc})"
        return RoofPlan("flat")
    apexes = len(plan.points or ()) - plan.n_ring
    if apexes == 1:
        plan.shape_built = "pyramidal"
        return plan
    prov["roof_shape"] = (f"fallback:flat (pyramidal roof on concave footprint: the straight skeleton has a ridge "
                          f"of {apexes} nodes, not a single apex)")
    return RoofPlan("flat")

def analytic_gable_slope_error(outer: Ring, across: bool, ref_height: float = 10.0,
                               tol: float = 5e-4) -> str | None:
    """None if the two slopes of the analytic gable on the near-rectangle ``outer`` are planar quads, else why not.
    Each slope joins an eave edge to the ridge between the midpoints of the end edges; it is planar only if the
    eave edges are parallel. The deviation is judged for a roof ``ref_height`` high (the real height is not known
    in the preflight) against ``tol`` metres, inside the 1 mm of the roof checker."""
    a, b, c, d = _frame(outer, across)
    ux, uy = _sub(a, b)
    ln = math.hypot(ux, uy)
    ux, uy = ux / ln, uy / ln

    def side(p: Point, q: Point) -> float:
        return (q[0] - p[0]) * uy - (q[1] - p[1]) * ux

    s1 = abs(side(a, ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)))   # distance of the ridge end from the a-b eave
    s2 = abs(side(a, ((d[0] + a[0]) / 2, (d[1] + a[1]) / 2)))
    dev = ref_height * abs(s2 - s1) / max(s1, 1e-9)
    if dev <= tol:
        return None
    return f"the eave edges are {math.degrees(math.asin(min(1.0, abs(_cross2(_sub(a, b), _sub(d, c))) / (math.dist(a, b) * math.dist(d, c))))):.2g} degrees off parallel"


def _cross2(p: Pt, q: Pt) -> float:
    return p[0] * q[1] - p[1] * q[0]


def _min_area_axes(ring: Sequence[Pt]) -> tuple[Pt, Pt]:
    """Unit vectors (long, short) of the minimum-area bounding rectangle of ``ring``."""
    best: tuple[float, Pt, Pt, float, float] | None = None
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
    assert best is not None  # a canonical skeleton ring has a non-degenerate edge
    _, u, v, w, h = best
    return (u, v) if w >= h else (v, u)


def _ridge_axis(ring: Sequence[Pt], orientation: str | None, direction: float | None, prov: Prov) -> Pt:
    """The wanted ridge axis (unit vector), with its ``roof_orientation`` provenance: the long side of the
    minimum-area bounding rectangle, or the short one for ``roof:orientation=across``; without an orientation a
    ``roof:direction`` puts the ridge perpendicular to the way the slope faces (D84)."""
    long_axis, short_axis = _min_area_axes(ring)
    if orientation in ("along", "across"):
        prov["roof_orientation"] = f"measured:osm roof:orientation={orientation}"
        axis = short_axis if orientation == "across" else long_axis
    elif orientation is None and direction is not None:
        d = _bearing(direction)
        axis = (-d[1], d[0])                               # the ridge target: perpendicular to the slope direction
        prov["roof_orientation"] = (f"measured:osm roof:direction={direction:g} "
                                    "(gable ends on the edges whose normal is nearest the ridge bearing)")
    else:
        axis = long_axis
        prov["roof_orientation"] = ("inferred:along (ridge parallel to the longer side of the minimum-area "
                                    "bounding rectangle)" if orientation is None else
                                    f"fallback:along (roof:orientation={orientation} not recognised)")
    return axis


def _is_end(a: Pt, b: Pt, axis: Pt) -> bool:
    """A footprint edge a-b is an end when it is perpendicular to the ridge axis within 45 degrees."""
    return abs((b[0] - a[0]) * axis[0] + (b[1] - a[1]) * axis[1]) / math.dist(a, b) <= math.sqrt(0.5)


def _gable_ends(sk: Skeleton, orientation: str | None, direction: float | None,
                prov: Prov) -> tuple[int, ...]:
    """Faces of the skeleton to turn into gable ends: the triangular faces at a ridge end whose footprint edge is
    perpendicular (within 45 degrees) to the ridge axis (:func:`_ridge_axis`)."""
    axis = _ridge_axis(sk.ring, orientation, direction, prov)
    n = len(sk.ring)
    ridge_ends: list[int] = []
    reasons: list[str] = []
    for i, f in enumerate(sk.faces):
        if len(f) == 3:
            try:
                _gable_node(sk, i)
                ridge_ends.append(i)
            except _GableError as exc:
                reasons.append(str(exc))
    if len(ridge_ends) < 2:
        raise _GableError(reasons[0] if reasons else "the skeleton has fewer than two ridge ends")
    perpendicular: list[int] = []
    for i in ridge_ends:
        if _is_end(sk.ring[i], sk.ring[(i + 1) % n], axis):
            perpendicular.append(i)
    ends = tuple(perpendicular if len(perpendicular) >= 2 else ridge_ends)
    if direction is not None and orientation is None:
        _record_ridge_bearing(sk, ends, direction, prov)
    return ends


def _ridge_bearing(sk: Skeleton, i: int) -> float:
    """Compass bearing in [0, 180) of the emitted ridge that ends in gable end ``i``."""
    N = max(sk.faces[i][2:], key=lambda k: sk.nodes[k][2])
    prev = sk.faces[(i - 1) % len(sk.ring)]
    M = prev[(prev.index(N) + 1) % len(prev)]
    nn, mm = sk.nodes[N], sk.nodes[M]
    return math.degrees(math.atan2(nn[0] - mm[0], nn[1] - mm[1])) % 180.0


def _record_ridge_bearing(sk: Skeleton, ends: Iterable[int], direction: float, prov: Prov,
                          tolerance: float = 10.0) -> None:
    """``prov["roof_ridge_bearing"]`` lists the emitted ridge bearings; ``roof_direction`` is measured only when
    one of them is within ``tolerance`` degrees of perpendicular to the tagged direction, else approximate."""
    want = (direction + 90.0) % 180.0
    bearings = sorted({_ridge_bearing(sk, i) % 180.0 for i in ends})
    def off(b: float) -> float:
        return min(abs(b - want), 180.0 - abs(b - want))

    best = min(bearings, key=off)

    def shown(b: float) -> str:      # the tolerance is judged on the unrounded bearing
        return f"{round(b, 1) % 180.0:g}"
    prov["roof_ridge_bearing"] = ", ".join(shown(b) for b in bearings)
    if off(best) <= tolerance:
        prov["roof_direction"] = f"measured:osm roof:direction={direction:g} (ridge {shown(best)}° perpendicular within {tolerance:g}°)"
    else:
        prov["roof_direction"] = f"approximate: ridge {shown(best)}° vs tagged {direction:g}°"


def drop_ridge_claims(prov: Prov) -> None:
    """Remove the gable ridge/direction provenance when the planned roof is not the one emitted (a flat or
    zero-height downgrade): a roof without a ridge makes no bearing or ``roof:direction`` claim."""
    for key in ("roof_ridge_bearing", "roof_direction", "roof_orientation"):
        prov.pop(key, None)


def _gable_node(sk: Skeleton, i: int) -> tuple[Node, int]:
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

    def dist(a: Pt, b: Pt, p: Pt) -> float:
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


def _skeleton_plan(outer: Ring, sk: Skeleton, ends: Sequence[int] = (), walls: Sequence[int] = ()) -> RoofPlan:
    n = len(outer)
    nodes = list(sk.nodes)
    faces = [list(f) for f in sk.faces]
    gable_apex: dict[int, int] = {}
    wall_set = set(walls)
    for i in ends:
        apex, N = _gable_node(sk, i)
        nodes.append(apex)
        gable_apex[i] = len(nodes) - 1
        for j in ((i - 1) % len(sk.ring), (i + 1) % len(sk.ring)):
            faces[j][faces[j].index(N)] = len(nodes) - 1
    index = {(float(p[0]), float(p[1])): k for k, p in enumerate(outer)}
    node_to_pt: dict[int, int] = {}
    points: list[Node] = [(float(p[0]), float(p[1]), 0.0) for p in outer]
    for k in sorted({k for i, f in enumerate(faces) if i not in gable_apex for k in f}
                    | set(range(len(sk.ring))) | set(gable_apex.values())):
        if k < len(sk.ring):
            node_to_pt[k] = index[sk.ring[k]]
        else:
            node_to_pt[k] = len(points)
            points.append(nodes[k])
    in_skeleton = set(node_to_pt[k] for k in range(len(sk.ring)))
    extra = [k for k in range(n) if k not in in_skeleton]
    tris: list[Tri] = []
    gable_tris: list[Tri] = []
    for i, face in enumerate(faces):
        pts = [(nodes[k][0], nodes[k][1]) for k in face]
        a, b = pts[0], pts[1]
        between = sorted((u, k) for k in extra for u in [_along(outer[k], a, b)] if u is not None)
        fan = [k for _, k in between]
        if i in wall_set:
            # vertical wall: triangulate its outline in (distance along the edge, height); CCW there is outward
            ln = math.dist(a, b)
            ux, uy = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
            poly = [(0.0, 0.0, node_to_pt[face[0]])] + [(u * ln, 0.0, k) for u, k in between]
            poly.append((ln, 0.0, node_to_pt[face[1]]))
            for k in face[2:]:
                poly.append(((nodes[k][0] - a[0]) * ux + (nodes[k][1] - a[1]) * uy, nodes[k][2], node_to_pt[k]))
            for (p, q, r) in triangulate([(x, y) for x, y, _ in poly], list(range(len(poly)))):
                tri = [p, q, r] if _signed(poly[p][:2], poly[q][:2], poly[r][:2]) >= 0 else [p, r, q]
                gable_tris.append((poly[tri[0]][2], poly[tri[1]][2], poly[tri[2]][2]))
            continue
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
            tris.append((ids[0], ids[1], ids[2]))
    t_max = max(p[2] for p in points)
    if t_max <= 0:
        raise SkeletonError("the skeleton has no height")
    if len(tris) + len(gable_tris) > MAX_ROOF_TRIANGLES:
        raise LimitError(f"skeleton roof needs {len(tris) + len(gable_tris)} triangles (limit {MAX_ROOF_TRIANGLES})")
    return RoofPlan("gabled" if ends or walls else "hipped", n, points, tris, t_max, gable_tris)


def _walled_plan(outer: Ring, sk: Skeleton, orientation: str | None, direction: float | None, prov: Prov,
                 merge: bool) -> RoofPlan:
    """Gable ends as vertical walls of a weighted skeleton: every footprint edge that is an end (perpendicular
    to the ridge axis within 45 degrees) becomes a zero-speed wavefront edge, so the slopes run into a vertical
    plane through it and an angled or chamfered end is cut instead of hipped. An end whose wall does not close
    in a single apex (above ``GABLE_APEX_MIN`` and ``GABLE_MIN_HEIGHT_RATIO`` of the roof height) goes back
    to a hip and the skeleton is rebuilt without it; at least two walls must survive (D82)."""
    axis = _ridge_axis(sk.ring, orientation, direction, prov)
    n = len(sk.ring)
    walls = frozenset(frozenset((sk.ring[i], sk.ring[(i + 1) % n])) for i in range(n)
                      if _is_end(sk.ring[i], sk.ring[(i + 1) % n], axis))
    reasons: list[str] = []
    for _ in range(n):
        if len(walls) < 2:
            raise _GableError(reasons[0] if reasons else "fewer than two gable ends perpendicular to the ridge")
        wsk = straight_skeleton(sk.ring, walls)
        if merge:
            _merge_close_nodes(wsk.nodes, wsk.faces, n, set(), set())
        t_max = max(p[2] for p in wsk.nodes)
        bad = set()
        for i in range(n):
            edge = frozenset((wsk.ring[i], wsk.ring[(i + 1) % n]))
            if edge not in walls:
                continue
            adjacent = [frozenset((wsk.ring[j], wsk.ring[(j + 1) % n])) in walls for j in (i - 1, (i + 1) % n)]
            if any(adjacent):
                reasons.append("two gable ends are adjacent (no ridge between slopes reaches the apex)")
                bad.add(edge)
                continue
            tops = [wsk.nodes[k][2] for k in wsk.faces[i][2:] if wsk.nodes[k][2] > GABLE_APEX_MIN]
            if len(tops) != len(wsk.faces[i]) - 2:
                reasons.append("the gable end is not a triangle (a node on its base line)")
                bad.add(edge)
            elif len(tops) != 1:
                reasons.append("the gable end is not a triangle (two tops)" if tops else
                               "the gable end has no height")
                bad.add(edge)
            elif tops[0] < GABLE_MIN_HEIGHT_RATIO * t_max:
                reasons.append("the gable end would be a sliver")
                bad.add(edge)
        if not bad:
            break
        walls -= bad
    else:
        raise _GableError("the gable ends do not settle")
    wall_faces = [i for i in range(n) if frozenset((wsk.ring[i], wsk.ring[(i + 1) % n])) in walls]
    plan = _skeleton_plan(outer, wsk, (), wall_faces)
    if direction is not None and orientation is None:
        _record_ridge_bearing(wsk, wall_faces, direction, prov)
    return plan


MERGE_NODE_M = 5e-4  # inside the 1 mm planarity tolerance of the roof checker


def _merge_close_nodes(nodes: list[Node], faces: list[list[int]], n_ring: int, keep: set[int],
                       keep_faces: set[int]) -> None:
    """Merge interior skeleton nodes closer than ``MERGE_NODE_M`` (two events a hair apart on a nearly regular
    footprint) so no face has a zero-width pinch, which the triangulator rejects. Ring and gable apex nodes are
    kept; a face reduced to a repeated node loses it, and every face sharing the node gets the same one."""
    rep: dict[int, int] = {}
    for k in range(n_ring, len(nodes)):
        if k in keep:
            continue
        for j in range(n_ring, k):
            if j not in rep and j not in keep and math.dist(nodes[k], nodes[j]) <= MERGE_NODE_M:
                rep[k] = j
                break
    if not rep:
        return
    for i, f in enumerate(faces):
        if i in keep_faces:
            continue
        g = [rep.get(k, k) for k in f]
        g = [k for j, k in enumerate(g) if k != g[j - 1]]
        faces[i] = g if len(g) >= 3 else f


def _signed(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _along(p: Point, a: Point, b: Point, tol: float = 1e-5) -> float | None:
    """Parameter of ``p`` along ``a`` -> ``b`` if it lies strictly between them on the segment, else None."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln2 = dx * dx + dy * dy
    u = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ln2
    if 0.0 < u < 1.0 and abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / math.sqrt(ln2) <= tol:
        return u
    return None


# Vertices and triangles (a quad counts as two) the analytic roofs add on a rectangular footprint beyond the wall ring
# and the footprint triangulation (flat, skillion, pyramidal, dome and onion scale with the ring); the geometry of ``build_roof`` is fixed, so these are exact (S4-ROOF-NAMED).
ANALYTIC_ROOF_COUNTS = {"gabled": (2, 6), "hipped": (2, 6), "half-hipped": (6, 14),
                        "gambrel": (6, 14), "mansard": (8, 18), "round": (14, 30), "saltbox": (2, 6)}
RESERVE_MARGIN = 0.0  # the reservation is exact: reserved / emitted == 1 for every roof kind (tests/test_roofs.py)


def roof_budget(plan: RoofPlan, n_ring: int, n_footprint_tris: int) -> tuple[int, int]:
    """Exact ``(vertices, triangles)`` the roof adds on top of the wall ring (2 n vertices, 2 n wall and
    ``n_footprint_tris`` floor triangles): what the plan will emit. A skeleton roof is counted from its plan;
    a flat or skillion roof reuses the wall-top vertices and triangulates the footprint; the other shapes
    add a fixed number of vertices (:data:`ANALYTIC_ROOF_COUNTS`), a dome or onion one ring per profile step."""
    if plan.points is not None and plan.tris is not None:
        return len(plan.points) - plan.n_ring, len(plan.tris) + len(plan.ends or ())
    shape = plan.shape_built
    if shape in ("flat", "skillion"):
        return 0, n_footprint_tris
    if shape in ("dome", "onion"):
        rings = dome_rings(n_ring, DOME_SEGMENTS if shape == "dome" else len(ONION) - 1)
        return n_ring * rings + 1, n_ring * (2 * rings + 1)
    if shape == "pyramidal":
        return 1, n_ring
    return ANALYTIC_ROOF_COUNTS[shape]

def resolve_orientation(shape: str, tags: Mapping[str, str], prov: Prov, outer: Ring | None = None,
                        direction: float | None = None) -> bool:
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


def _bearing(direction: float) -> Pt:
    r = math.radians(direction)
    return math.sin(r), math.cos(r)


def _sub(p: Point, q: Point) -> Pt:
    return q[0] - p[0], q[1] - p[1]


def _frame(ring: Ring, across: bool) -> tuple[Point, Point, Point, Point]:
    """Rectangle corners a, b, c, d (CCW, as ring points) with the ridge parallel to a-b: along
    the longer side, or the shorter one if ``across``."""
    a, b, c, d = ring
    if (math.dist(a[:2], b[:2]) < math.dist(b[:2], c[:2])) != across:
        a, b, c, d = b, c, d, a
    return a, b, c, d

def skillion_surface(shape: str, rings: Iterable[Ring], direction: float | None, top: float, roof_h: float,
                     prov: Prov) -> Callable[[Point], float] | None:
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

    def skillion_z(p: Point) -> float:
        s = p[0] * d[0] + p[1] * d[1]
        return top - roof_h * (s - smin) / span
    return skillion_z


# Cross-section profiles (t across 0..1, z as a fraction of the roof height) of the shapes
# extruded along the ridge; the end walls are vertical.
GAMBREL: list[Pt] = [(0.0, 0.0), (0.18, 0.62), (0.5, 1.0), (0.82, 0.62), (1.0, 0.0)]
SALTBOX_RIDGE_T = 1.0 / 3.0
ROUND_SEGMENTS = 8
DOME_SEGMENTS = 6
# onion: (scale, z fraction) of the rings above the eave, sampled at t = k / 7; the apex follows
ONION: list[Pt] = [(1.0, 0.0), (0.97, 0.10), (0.85, 0.25), (0.62, 0.42), (0.38, 0.60), (0.22, 0.76), (0.10, 0.89),
         (0.0, 1.0)]
MANSARD_LOW_INSET, MANSARD_TOP_INSET, MANSARD_BREAK_Z = 0.15, 0.30, 0.65  # x short side, x short side, x roof_h
HALF_HIP_INSET, HALF_HIP_WALL_Z = 0.25, 0.5  # ridge end inset x short side; gable wall height x roof_h


def dome_rings(n_ring: int, segments: int) -> int:
    """Intermediate rings used for ``segments`` (fewer for a huge footprint so the roof stays
    within MAX_ROOF_TRIANGLES: n x (2 x rings + 1) triangles)."""
    return max(0, min(segments - 1, (MAX_ROOF_TRIANGLES // max(n_ring, 1) - 1) // 2))


def _dome_profile(n_ring: int, shape: str) -> list[Pt]:
    rings = dome_rings(n_ring, DOME_SEGMENTS if shape == "dome" else len(ONION) - 1)
    out: list[Pt] = []
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


def build_roof(mesh: MeshData, ring: Ring, holes: Sequence[Ring], eave_z: float, roof_h: float, plan: RoofPlan,
               tags: Mapping[str, str], prov: Prov, *, top_idx: Sequence[Sequence[int]],
               tris: Sequence[Sequence[int]], add_face: AddFace, roof_col: Color, facade: Color,
               across: bool = False, direction: float | None = None) -> None:
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
    if plan.points is not None and plan.tris is not None:
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
        r1: tuple[float, ...]
        r2: tuple[float, ...]
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


def _rect_roof(mesh: MeshData, rt: Sequence[int], eave_z: float, roof_h: float, shape: str,
               tags: Mapping[str, str], prov: Prov, add_face: AddFace, roof_col: Color, facade: Color,
               across: bool, direction: float | None) -> None:
    """half-hipped / gambrel / round / saltbox / mansard on the rectangle ``rt`` (a, b, c, d CCW)."""
    V = mesh.vertices
    R = "MB Roof"
    a, b, c, d = rt
    if (math.dist(V[a][:2], V[b][:2]) < math.dist(V[b][:2], V[c][:2])) != across:
        a, b, c, d = b, c, d, a
    A, B, C, D = (V[i][:2] for i in (a, b, c, d))
    eave: dict[Pt, int] = {(0.0, 0.0): a, (1.0, 0.0): b, (1.0, 1.0): c, (0.0, 1.0): d}

    def pt(s: float, t: float, zf: float) -> int:
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