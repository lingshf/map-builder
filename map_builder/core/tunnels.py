"""Tunnel stage of ``build_plan`` (D18, D21, D23): highway ways tagged ``tunnel=*`` become flyable tubes.

* The floor profile is linear in arc length between the road z at the two ends (terrain + ``ROAD_LIFT_M``).
* The tube (class ``tunnel``) is :func:`structures.sweep` of a closed cross-section with open ends; the floor
  faces use ``MB Road``, the walls and the arch ``MB Tunnel``.
* The terrain is cut only inside the bore volume (:func:`cut_terrain`): within the tube footprint, terrain
  between the floor (less ``CUT_BELOW_FLOOR_M``) and the roof is removed. Terrain outside the footprint, above
  the roof or below the floor stays, so the cut is exact and nothing leaks (a vertical ray hits terrain or the
  tube roof). The removed part is exactly the heightfield NaN region. The edit is local: only the cut cells are
  touched, never the whole grid.
* Where the terrain first rises above the roof, walking in from a portal, a headwall (class ``structure``,
  a 1 m slab with a through-hole matching the tube) closes the cutting.
* One passage probe (kind ``tunnel``, id ``<mb_id>:bore``) per tube, queued on ``ctx.probes`` and checked on the
  finished scene by :func:`structures.finalize_probes` (D21), after the vegetation.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING

from .mesh import MeshData
from .osm import _unsupported_reason
from .structures import Probe, Segment, Vec2, Vec3, polyline_z_profile, report_unsupported, sweep

if TYPE_CHECKING:
    from .dem import ElevationGrid
    from .generate import ObjectSpec, ScenePlan
    from .geodesy import Area
    from .osm import Feature
    from .structures import StageContext

Plane = tuple[float, float, float]      # z = A x + B y + C, or a half-plane a x + b y + c >= 0
Bounds = tuple[float, float, float, float]      # (min x, max x, min y, max y)
# (xy polygon CCW, roof plane, floor plane, bbox, edges, fz, rz)
Tile = tuple[list[Vec2], Plane, Plane | None, Bounds, list[Plane], float, float]
Poly = list[Vec2]

FLOOR_MARGIN_M = 1.0        # floor width = road width + 2 x this
WALL_HEIGHT_M = 4.5
ARCH_RISE_M = 1.0
ARCH_SEGMENTS = 5
DEFAULT_CLEARANCE_M = WALL_HEIGHT_M + ARCH_RISE_M
CLEARANCE_RANGE_M = (2.5, 10.0)
MAX_STEP_M = 10.0
HEADWALL_THICKNESS_M = 1.0
HEADWALL_BELOW_FLOOR_M = 1.0
HEADWALL_ABOVE_TERRAIN_M = 1.0
COVER_WARN_M = 0.5
PORTAL_PROBE_MARGIN_M = 3.0
PORTAL_KEEPOUT_M = 5.0      # no tree within this distance of a portal (the bore probe extends 3 m beyond it)
PROBE_MAX_RADIUS_M = 1.5
CUT_BELOW_FLOOR_M = 0.1     # the cross-section is grown by this at the floor
HEADWALL_TRIANGLE_RESERVE = 200
MAX_SAMPLES = 400           # cap of the cover / headwall walks along a very long tunnel

TUBE_COLOR = (0.55, 0.55, 0.55)
FLOOR_COLOR = (0.12, 0.12, 0.12)
HEADWALL_COLOR = (0.62, 0.62, 0.60)
_EPS_AREA2 = 1e-9
# Vertices closer than this (in plan, and in z up to the local slope) are one vertex: about three times the
# float32 spacing at 1 km, so the welded boundary survives the collision file's storage precision.
_WELD_M = 1e-4
FLOOR_EDGE = 0


def cross_section(width: float, clearance: float) -> list[Vec2]:
    """Closed tube cross-section ``[(lateral, up)]`` (CCW, floor at up = 0): edge 0 is the floor, 1 the right
    wall, 2..6 the arch panels (the roof) and 7 the left wall. The arch rises ``ARCH_RISE_M`` above the wall
    top; its highest vertices reach exactly ``clearance``."""
    a = width / 2.0
    wall = clearance - ARCH_RISE_M
    pts = [(-a, 0.0), (a, 0.0)]
    peak = 1.0 - (1.0 - 2.0 * (ARCH_SEGMENTS // 2) / ARCH_SEGMENTS) ** 2
    for k in range(ARCH_SEGMENTS + 1):
        u = a * (1.0 - 2.0 * k / ARCH_SEGMENTS)
        pts.append((u, wall + ARCH_RISE_M * (1.0 - (u / a) ** 2) / peak))
    return pts


def clearance_of(tags: Mapping[str, str]) -> tuple[float, str]:
    """``(clearance_m, provenance)``: ``maxheight`` within 2.5-10 m (measured), else the 5.5 m default."""
    from .generate import parse_length
    h = parse_length(tags.get("maxheight"))
    if h is not None and CLEARANCE_RANGE_M[0] <= h <= CLEARANCE_RANGE_M[1]:
        return h, "measured:osm maxheight"
    return DEFAULT_CLEARANCE_M, f"inferred:default {DEFAULT_CLEARANCE_M:g} m"


def _simplify(pts: Sequence[Vec2], tol: float) -> list[Vec2]:
    """Douglas-Peucker in plan."""
    if len(pts) < 3:
        return list(pts)
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    L = math.hypot(x1 - x0, y1 - y0)
    best, at = -1.0, 0
    for i in range(1, len(pts) - 1):
        x, y = pts[i]
        d = (math.hypot(x - x0, y - y0) if L < 1e-12
             else abs((x1 - x0) * (y0 - y) - (x0 - x) * (y1 - y0)) / L)
        if d > best:
            best, at = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return _simplify(pts[:at + 1], tol)[:-1] + _simplify(pts[at:], tol)


class _Tube:
    """One generated tube; ``path`` is one world point per ring (z already minus ``z_offset``)."""

    def __init__(self, feature: Feature, mesh: MeshData, origin: Vec3, profile: Sequence[Vec2], path: Sequence[Vec3],
                 spec: ObjectSpec, clearance: float, half: float) -> None:
        self.feature = feature
        self.mesh = mesh
        self.origin = origin
        self.profile = profile
        self.path = path
        self.arc = _Arc(path)
        self.spec = spec
        self.clearance = clearance
        self.half = half

    def ring(self, k: int) -> list[Vec3]:
        n = len(self.profile)
        ox, oy, oz = self.origin
        return [(x + ox, y + oy, z + oz) for x, y, z in self.mesh.vertices[k * n:(k + 1) * n]]


def _tube_mesh(profile: Sequence[Vec2], path: Sequence[Vec3], name: str) -> MeshData:
    mesh = sweep(profile, path, False, name, "MB Tunnel", TUBE_COLOR)
    n = len(profile)
    floor = mesh.material_index("MB Road")
    for k in range(len(path) - 1):
        mesh.face_materials[k * n + FLOOR_EDGE] = floor
        mesh.face_colors[k * n + FLOOR_EDGE] = FLOOR_COLOR
    return mesh


class _Arc:
    """Plan arc-length lookup on ``path`` in O(log n) per query (cumulative lengths are built once)."""

    def __init__(self, path: Sequence[Vec3]) -> None:
        self.path = path
        self.start: list[float] = [0.0]
        for a, b in zip(path, path[1:]):
            self.start.append(self.start[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.length = self.start[-1]

    def at(self, s: float) -> tuple[float, float, float, Vec2, int, float]:
        """``(x, y, z, direction_xy, segment_index, segment_start_s)`` at plan arc length ``s``."""
        k = min(max(bisect.bisect_left(self.start, s) - 1, 0), len(self.path) - 2)
        a, b = self.path[k], self.path[k + 1]
        seg = self.start[k + 1] - self.start[k]
        f = 0.0 if seg == 0 else min(max((s - self.start[k]) / seg, 0.0), 1.0)
        d = ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)
        return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, d, k, self.start[k])


def _plan_length(path: Sequence[Sequence[float]]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


# --- headwall -------------------------------------------------------------------------------------------------

def _annulus(outer: Sequence[Sequence[float]], inner: Sequence[Sequence[float]]) -> list[tuple[int, int, int]]:
    """Triangles ``(kind, i, j)`` filling the ring between nested convex CCW polygons, merging the vertices by
    angle around the inner centroid; kind 0 = outer edge i->i+1 with inner vertex j, kind 1 = inner edge
    j->j+1 with outer vertex i."""
    cx = sum(p[0] for p in inner) / len(inner)
    cy = sum(p[1] for p in inner) / len(inner)

    def order(poly: Sequence[Sequence[float]]) -> tuple[int, list[float]]:
        ang = [math.atan2(p[1] - cy, p[0] - cx) for p in poly]
        start = min(range(len(poly)), key=lambda i: ang[i])
        return start, [(ang[(start + k) % len(poly)] - ang[start]) % (2 * math.pi) for k in range(len(poly))]

    so, ao = order(outer)
    si, ai = order(inner)
    no, ni = len(outer), len(inner)
    i = j = 0
    out: list[tuple[int, int, int]] = []
    while i < no or j < ni:
        o_next = ao[i + 1] if i + 1 < no else 2 * math.pi
        i_next = ai[j + 1] if j + 1 < ni else 2 * math.pi
        if i < no and (j >= ni or o_next <= i_next):
            out.append((0, (so + i) % no, (si + j) % ni))
            i += 1
        else:
            out.append((1, (so + i) % no, (si + j) % ni))
            j += 1
    return out


def headwall_mesh(name: str, c0: Vec3, c1: Vec3, side: Vec2, profile: Sequence[Vec2], half_width: float,
                  z_top: float) -> MeshData:
    """Genus-1 closed solid (outward faces): a vertical slab from ``c0`` to ``c1`` (3D tube centreline points,
    ``side`` the horizontal unit vector to the right), ``half_width`` wide from ``HEADWALL_BELOW_FLOOR_M``
    below the floor to ``z_top``, with a through-hole equal to ``profile``."""
    mesh = MeshData(name)
    n = len(profile)
    rings: list[tuple[list[int], list[int], list[Vec2], list[Vec2]]] = []
    for c in (c0, c1):
        outer = [(-half_width, c[2] - HEADWALL_BELOW_FLOOR_M), (half_width, c[2] - HEADWALL_BELOW_FLOOR_M),
                 (half_width, z_top), (-half_width, z_top)]
        o_ids = [mesh.add_vertex(c[0] + side[0] * u, c[1] + side[1] * u, z) for u, z in outer]
        h_ids = [mesh.add_vertex(c[0] + side[0] * u, c[1] + side[1] * u, c[2] + v) for u, v in profile]
        rings.append((o_ids, h_ids, list(outer), [(u, c[2] + v) for u, v in profile]))
    mat, col = "MB Concrete", HEADWALL_COLOR
    (o0, h0, op0, hp0), (o1, h1, _a, _b) = rings
    for j in range(4):
        k = (j + 1) % 4
        mesh.add_face((o0[j], o1[j], o1[k], o0[k]), mat, col)
    for j in range(n):
        k = (j + 1) % n
        mesh.add_face((h0[j], h1[j], h1[k], h0[k])[::-1], mat, col)
    for kind, i, j in _annulus(op0, hp0):
        if kind == 0:
            front = (o0[i], o0[(i + 1) % 4], h0[j])
            back = (o1[i], o1[(i + 1) % 4], h1[j])
        else:
            front = (o0[i], h0[(j + 1) % n], h0[j])
            back = (o1[i], h1[(j + 1) % n], h1[j])
        mesh.add_face(front, mat, col)
        mesh.add_face(back[::-1], mat, col)
    return mesh


# --- terrain cut ------------------------------------------------------------------------------------------------

def _clip_linear(poly: Sequence[Vec2], a: float, b: float, c: float) -> list[Vec2]:
    """Part of convex ``poly`` with ``a x + b y + c >= 0``."""
    out: list[Vec2] = []
    n = len(poly)
    for k in range(n):
        p, q = poly[k], poly[(k + 1) % n]
        sp = a * p[0] + b * p[1] + c
        sq = a * q[0] + b * q[1] + c
        if sp >= 0:
            out.append(p)
        if (sp > 0 > sq) or (sp < 0 < sq):
            t = sp / (sp - sq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def _plane(p: Sequence[float], q: Sequence[float], r: Sequence[float]) -> Plane | None:
    """``(A, B, C)`` with ``z = A x + B y + C`` through three points, or None if vertical."""
    det = (q[0] - p[0]) * (r[1] - p[1]) - (r[0] - p[0]) * (q[1] - p[1])
    if abs(det) < 1e-12:
        return None
    A = ((q[2] - p[2]) * (r[1] - p[1]) - (r[2] - p[2]) * (q[1] - p[1])) / det
    B = ((r[2] - p[2]) * (q[0] - p[0]) - (q[2] - p[2]) * (r[0] - p[0])) / det
    return A, B, p[2] - A * p[0] - B * p[1]


def _poly_area2(poly: Sequence[Sequence[float]]) -> float:
    a = 0.0
    n = len(poly)
    for k in range(n):
        a += poly[k][0] * poly[(k + 1) % n][1] - poly[(k + 1) % n][0] * poly[k][1]
    return a


def _hull(points: Iterable[Vec2]) -> list[Vec2]:
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts
    cr: Callable[[Vec2, Vec2, Vec2], float] = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])   # noqa: E731
    half: list[Vec2] = []
    for seq in (pts, pts[::-1]):
        h: list[Vec2] = []
        for p in seq:
            while len(h) >= 2 and cr(h[-2], h[-1], p) <= 0:
                h.pop()
            h.append(p)
        half.extend(h[:-1])
    return half


class _Group:
    """One ring segment's arch panels. ``hull`` (CCW, with its half-planes ``edges``) is set only when the tiles
    tile it exactly (area equal), so a terrain face can be clipped to the segment once. ``rmin`` is the lowest roof
    and ``fmax`` the highest floor-band bound, ``rz`` / ``fz`` the highest roof and lowest floor-band bound (all
    over the tile vertices); a terrain between ``fmax`` and ``rmin`` is cut whole. The tiles are built on demand."""
    __slots__ = ("r0", "r1", "floor", "tiles", "hull", "edges", "bbox", "fz", "rz", "rmin", "fmax")
    r0: list[tuple[float, ...]]
    r1: list[tuple[float, ...]]
    floor: Plane | None
    tiles: list[Tile] | None
    hull: list[Vec2] | None
    edges: list[Plane] | None
    bbox: Bounds
    fz: float
    rz: float
    rmin: float
    fmax: float


def _tiles_of(g: _Group) -> list[Tile]:
    """Tiles ``(xy polygon CCW, roof plane, floor plane, bbox, edges, fz, rz)`` of a group: the arch panels, split
    exactly as the collision fan splits the (reversed) quads, so their plan projections tile the tube footprint."""
    if g.tiles is not None:
        return g.tiles
    seg: list[Tile] = []
    r0, r1, floor = g.r0, g.r1, g.floor
    for j in range(len(r0) - 1):
        nxt = j + 1
        for tri in ((r0[nxt], r1[nxt], r1[j]), (r0[nxt], r1[j], r0[j])):
            poly = [(p[0], p[1]) for p in tri]
            area2 = _poly_area2(poly)
            plane = _plane(*tri)
            if abs(area2) < _EPS_AREA2 or plane is None:
                continue
            if area2 < 0:
                poly.reverse()
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            edges: list[Plane] = []      # inside-positive half-planes of the (CCW) tile, for a quick disjointness test
            for e in range(3):
                p0, p1 = poly[e], poly[(e + 1) % 3]
                ea, eb = p0[1] - p1[1], p1[0] - p0[0]
                edges.append((ea, eb, -(ea * p0[0] + eb * p0[1])))
            rz = max(plane[0] * x + plane[1] * y + plane[2] for x, y in poly)
            fz = (min(floor[0] * x + floor[1] * y + floor[2] for x, y in poly) - CUT_BELOW_FLOOR_M
                  if floor is not None else -math.inf)
            seg.append((poly, plane, floor, (min(xs), max(xs), min(ys), max(ys)), edges, fz, rz))
    g.tiles = seg
    return seg


def _roof_triangles(tubes: Iterable[_Tube]) -> list[_Group]:
    """The cut groups, one per ring segment of every tube, in the terrain frame (see ``_tiles_of``). The floor
    plane of a segment is that of its floor ring edge (None if degenerate)."""
    out: list[_Group] = []
    q: Callable[[Sequence[float]], tuple[float, ...]] = lambda p: tuple(round(c, 6) for c in p)   # noqa: E731  (stable across libm differences)
    for t in tubes:
        n = len(t.profile)
        for k in range(len(t.path) - 1):
            ring0, ring1 = t.ring(k), t.ring(k + 1)
            floor = _plane(q(ring0[0]), q(ring0[1]), q(ring1[0]))
            r0 = [q(p) for p in ring0[2:n]]
            r1 = [q(p) for p in ring1[2:n]]
            g = _Group()
            g.r0, g.r1, g.floor, g.tiles = r0, r1, floor, None
            pts = r0 + r1
            xs, ys, zs = [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
            g.bbox = (min(xs), max(xs), min(ys), max(ys))
            g.rz, g.rmin = max(zs), min(zs)
            if floor is None:
                g.fz = g.fmax = -math.inf
            else:
                fl = [floor[0] * p[0] + floor[1] * p[1] + floor[2] for p in pts]
                g.fz, g.fmax = min(fl) - CUT_BELOW_FLOOR_M, max(fl) - CUT_BELOW_FLOOR_M
            g.hull = g.edges = None
            hull = _hull([(p[0], p[1]) for p in pts])
            if len(hull) >= 3:
                h2 = _poly_area2(hull)
                tiles2 = 0.0
                for j in range(len(r0) - 1):
                    nxt = j + 1
                    for tri in ((r0[nxt], r1[nxt], r1[j]), (r0[nxt], r1[j], r0[j])):
                        a2 = abs((tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1])
                                 - (tri[2][0] - tri[0][0]) * (tri[1][1] - tri[0][1]))
                        if a2 >= _EPS_AREA2 and _plane(*tri) is not None:
                            tiles2 += a2
                if h2 > 0 and abs(h2 - tiles2) <= 1e-9 * max(1.0, h2):
                    g.hull = hull
                    g.edges = []
                    for e in range(len(hull)):
                        p0, p1 = hull[e], hull[(e + 1) % len(hull)]
                        ea, eb = p0[1] - p1[1], p1[0] - p0[0]
                        g.edges.append((ea, eb, -(ea * p0[0] + eb * p0[1])))
            out.append(g)
    return out


def _altitude2(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> tuple[float, float]:
    """``(2 x signed plan area, shortest altitude)`` of the plan triangle ``abc``."""
    area2 = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    longest = max(math.hypot(b[0] - a[0], b[1] - a[1]), math.hypot(c[0] - b[0], c[1] - b[1]),
                  math.hypot(a[0] - c[0], a[1] - c[1]))
    return area2, (area2 / longest if longest else 0.0)


def cut_terrain(mesh: MeshData, grid: ElevationGrid, tubes: Iterable[_Tube]) -> tuple[int, list[Poly]]:
    """Remove from the terrain ``mesh`` the part inside the bore volume: within a tube's footprint, the terrain
    between ``CUT_BELOW_FLOOR_M`` under the floor and the roof.

    Returns ``(cut_cells, regions)``: the number of terrain cells touched and the removed convex plan polygons.
    Only the cells overlapping a tube's tiles are visited and edited in place: a cut face is replaced by the
    triangles of what is left of it (same plane, material and colour), new vertices are welded to the
    vertices of the touched cells only (same plan position within ``_WELD_M`` and the same height up to the
    local slope), and the vertices that no face uses any more are reused. A leftover triangle thinner than
    ``2 * _WELD_M`` is a collapsed sliver and dropped; a larger one that turned over is a defect and raises."""
    from .generate import _MIN_AREA2, _cell_range, _clip_convex, _clip_halfplane, _convex_difference
    groups = _roof_triangles(tubes)
    if not groups:
        return 0, []
    per_cell: dict[tuple[int, int], list[_Group]] = {}
    for g in groups:
        x0, x1, y0, y1 = g.bbox
        i0, i1, j0, j1 = _cell_range(grid, x0, x1, y0, y1)
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                per_cell.setdefault((i, j), []).append(g)
    nx = grid.nx
    if len(mesh.faces) != 2 * (nx - 1) * (grid.ny - 1):
        raise AssertionError("terrain mesh is not the plain grid triangulation")
    V, F = mesh.vertices, mesh.faces
    removed: dict[int, tuple[Plane, list[Poly]]] = {}
    regions: list[Poly] = []
    cells = 0
    for (i, j) in sorted(per_cell, key=lambda c: (c[1], c[0])):
        touched = False
        for upper in (0, 1):
            fi = 2 * (j * (nx - 1) + i) + upper
            tri = [V[v] for v in F[fi]]
            plane = _plane(*tri)
            if plane is None:
                continue
            poly = [(p[0], p[1]) for p in tri]
            tx0, tx1 = min(p[0] for p in poly), max(p[0] for p in poly)
            ty0, ty1 = min(p[1] for p in poly), max(p[1] for p in poly)
            cuts: list[Poly] = []
            tzlo, tzhi = min(p[2] for p in tri), max(p[2] for p in tri)
            sgn = 1.0 if _poly_area2(poly) > 0 else -1.0
            tedges: list[Plane] = []
            for e in range(3):
                p0, p1 = poly[e], poly[(e + 1) % 3]
                ea, eb = (p0[1] - p1[1]) * sgn, (p1[0] - p0[0]) * sgn
                tedges.append((ea, eb, -(ea * p0[0] + eb * p0[1])))
            for g in per_cell[(i, j)]:
                bb = g.bbox
                if bb[0] > tx1 or bb[1] < tx0 or bb[2] > ty1 or bb[3] < ty0:
                    continue
                if tzlo > g.rz + 1e-9 or tzhi < g.fz - 1e-9:
                    continue
                frag: Poly | None = None
                if g.hull is not None:
                    if any(all(ea * x + eb * y + ec < 0 for x, y in poly)
                           for ea, eb, ec in g.edges):  # type: ignore[union-attr]  # edges is set whenever hull is
                        continue
                    if any(all(ea * x + eb * y + ec < 0 for x, y in g.hull) for ea, eb, ec in tedges):
                        continue
                    frag = poly
                    for k in range(0 if all(ea * x + eb * y + ec >= 0 for ea, eb, ec in g.edges  # type: ignore[union-attr]
                                            for x, y in poly)
                                   else len(g.hull)):
                        frag = _clip_halfplane(frag, g.hull[k], g.hull[(k + 1) % len(g.hull)])
                        if len(frag) < 3:
                            break
                    if len(frag) < 3:
                        continue
                    if tzhi <= g.rmin - 1e-9 and tzlo >= g.fmax + 1e-9:
                        if _poly_area2(frag) > _MIN_AREA2:
                            cuts.append(frag)       # the whole piece is inside the bore: one cut, not one per tile
                        continue
                gcuts: list[Poly] = []
                for rpoly, rplane, fplane, bb, edges, fz, rz in _tiles_of(g):
                    if bb[0] > tx1 or bb[1] < tx0 or bb[2] > ty1 or bb[3] < ty0:
                        continue
                    if tzlo > rz + 1e-9 or tzhi < fz - 1e-9:
                        continue        # the terrain here is above the roof or under the floor band
                    if any(all(ea * x + eb * y + ec < 0 for x, y in poly) for ea, eb, ec in edges):
                        continue        # the cell triangle lies outside one edge of the tile
                    if any(all(ea * x + eb * y + ec < 0 for x, y in rpoly) for ea, eb, ec in tedges):
                        continue        # and the tile outside one edge of the cell triangle
                    q = _clip_convex(poly, rpoly)
                    if len(q) < 3:
                        continue
                    q = _clip_linear(q, rplane[0] - plane[0], rplane[1] - plane[1], rplane[2] - plane[2])
                    if len(q) >= 3 and fplane is not None:
                        q = _clip_linear(q, plane[0] - fplane[0], plane[1] - fplane[1],
                                         plane[2] - fplane[2] + CUT_BELOW_FLOOR_M)
                    if len(q) >= 3 and _poly_area2(q) > _MIN_AREA2:
                        gcuts.append(q)
                if (frag is not None and len(gcuts) > 1
                        and abs(sum(_poly_area2(q) for q in gcuts) - _poly_area2(frag))
                        <= 1e-9 * max(1.0, abs(_poly_area2(frag)))):
                    gcuts = [frag]          # the tiles cut all of the segment's piece: merge them
                cuts.extend(gcuts)
            if not cuts:
                continue
            touched = True
            regions.extend(cuts)
            pieces = [poly]
            for c in cuts:
                cx0, cx1 = min(p[0] for p in c), max(p[0] for p in c)
                cy0, cy1 = min(p[1] for p in c), max(p[1] for p in c)
                nxt = []
                for p in pieces:
                    if (min(r[0] for r in p) >= cx1 or max(r[0] for r in p) <= cx0
                            or min(r[1] for r in p) >= cy1 or max(r[1] for r in p) <= cy0):
                        nxt.append(p)       # disjoint from this cut
                    else:
                        nxt.extend(_convex_difference(p, c))
                pieces = nxt
            removed[fi] = (plane, pieces)
        cells += touched
    if not removed:
        return 0, []

    candidates = sorted({v for fi in removed for v in F[fi]})
    buckets: dict[tuple[int, int], list[int]] = {}

    def bucket(x: float, y: float) -> tuple[int, int]:
        return (math.floor(x / _WELD_M), math.floor(y / _WELD_M))

    for v in candidates:
        buckets.setdefault(bucket(V[v][0], V[v][1]), []).append(v)
    base = len(V)
    fresh: list[Vec3] = []          # new vertices, provisional ids base + k
    used_old: set[int] = set()

    def weld(x: float, y: float, z: float, slope: float) -> int:
        bx, by = bucket(x, y)
        tol_z = _WELD_M * (1.0 + slope)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in buckets.get((bx + dx, by + dy), ()):
                    p = V[k] if k < base else fresh[k - base]
                    if abs(p[0] - x) <= _WELD_M and abs(p[1] - y) <= _WELD_M and abs(p[2] - z) <= tol_z:
                        if k < base:
                            used_old.add(k)
                        return k
        fresh.append((x, y, z))
        buckets.setdefault((bx, by), []).append(base + len(fresh) - 1)
        return base + len(fresh) - 1

    new_tris: list[tuple[tuple[int, int, int], int, tuple[float, ...]]] = []       # (ids, material, colour)
    for fi in sorted(removed):
        plane, pieces = removed[fi]
        slope = math.hypot(plane[0], plane[1])
        for p in pieces:
            ids = [weld(x, y, plane[0] * x + plane[1] * y + plane[2], slope) for x, y in p]
            for k in range(1, len(ids) - 1):
                corner = (ids[0], ids[k], ids[k + 1])
                if len(set(corner)) < 3:
                    continue
                pts = [(V[v] if v < base else fresh[v - base]) for v in corner]
                area2, altitude = _altitude2(*pts)
                if abs(altitude) <= 2.0 * _WELD_M:
                    continue
                if area2 < 0:
                    raise AssertionError("terrain cut produced an inverted face")
                new_tris.append((corner, mesh.face_materials[fi], mesh.face_colors[fi]))

    # Vertices of the cut cells that no face uses any more (ids are j * nx + i, see generate.build_terrain).
    kept_new = {v for tri, _m, _c in new_tris for v in tri}
    dead: list[int] = []
    for v in candidates:
        if v in kept_new:
            continue
        i, j = v % nx, v // nx
        if any(v in F[2 * (jj * (nx - 1) + ii) + u] and (2 * (jj * (nx - 1) + ii) + u) not in removed
               for jj in (j - 1, j) if 0 <= jj < grid.ny - 1
               for ii in (i - 1, i) if 0 <= ii < nx - 1 for u in (0, 1)):
            continue
        dead.append(v)
    remap: dict[int, int] = {}
    spare = list(dead)
    for k, fv in enumerate(fresh):
        if base + k not in kept_new:
            continue
        if spare:
            slot = spare.pop(0)
            V[slot] = fv
            remap[base + k] = slot
        else:
            V.append(fv)
            remap[base + k] = len(V) - 1
    leftover = spare
    slots = sorted(removed)
    for n, fi in enumerate(slots):
        if n < len(new_tris):
            ntri, mat, col = new_tris[n]
            F[fi] = tuple(remap.get(v, v) for v in ntri)
            mesh.face_materials[fi] = mat
            mesh.face_colors[fi] = col
    for ntri, mat, col in new_tris[len(slots):]:
        F.append(tuple(remap.get(v, v) for v in ntri))
        mesh.face_materials.append(mat)
        mesh.face_colors.append(col)
    for fi in sorted(slots[len(new_tris):], reverse=True):
        last = len(F) - 1
        if fi != last:
            F[fi], mesh.face_materials[fi], mesh.face_colors[fi] = F[last], mesh.face_materials[last], \
                mesh.face_colors[last]
        F.pop()
        mesh.face_materials.pop()
        mesh.face_colors.pop()
    if leftover:    # more vertices freed than created: compact once (rare)
        used = sorted({v for f in F for v in f})
        index = {v: k for k, v in enumerate(used)}
        mesh.vertices = [V[v] for v in used]
        mesh.faces = [tuple(index[v] for v in f) for f in F]
    return cells, regions


# --- the stage --------------------------------------------------------------------------------------------------

def build(plan: ScenePlan, ctx: StageContext) -> None:
    from .generate import InvalidFeature
    features: list[Feature] = list(getattr(ctx.classified, "tunnels", ()))
    if not ctx.options.roads:
        report_unsupported(ctx, features, _unsupported_reason)
        return
    invalid = plan.report["invalid_features"]
    tubes: list[_Tube] = []
    walls: list[ObjectSpec] = []
    for f in features:
        try:
            tube = _build_tube(ctx, f)
        except InvalidFeature as e:
            ctx.budget.release()
            invalid.append({"id": f.id, "reason": str(e)})
            continue
        tubes.append(tube)
        ctx.add(tube.spec)
        plan.count("tunnels")
        if tube.spec.provenance["width"].startswith("inferred"):
            plan.inferred("tunnel.width")
        if tube.spec.provenance["clearance"].startswith("inferred"):
            plan.inferred("tunnel.clearance")
        _cover(plan, ctx, tube)
        walls.extend(_build_headwalls(plan, ctx, tube))
        ctx.probes.append(_make_probe(tube, ctx.area))
    if not tubes:
        return
    terrain = next(s for s in plan.objects if s.mb_id == "terrain:grid")
    # The terrain is the plain grid triangulation, so its triangle count is its face count.
    before = (len(terrain.mesh.vertices), len(terrain.mesh.faces))
    cells, _ = cut_terrain(terrain.mesh, ctx.terrain, tubes)
    if cells:
        terrain.provenance["tunnel_cut"] = "terrain inside the tunnel bores (floor to roof) removed"
        ctx.budget.charge("terrain:grid", max(0, len(terrain.mesh.vertices) - before[0]),
                          max(0, len(terrain.mesh.faces) - before[1]))
    plan.count("terrain_cut_cells", cells)
    for w in walls:
        ctx.add(w)
        plan.count("tunnel_headwalls")


def _build_tube(ctx: StageContext, f: Feature) -> _Tube:
    from .generate import (InvalidFeature, ObjectSpec, ROAD_LIFT_M, _dedupe_polyline, inside_terrain,
                           mesh_triangle_count, road_width, short_name, terrain_height)
    grid, z_off = ctx.terrain, ctx.z_offset
    width, wprov = road_width(f.tags)
    floor_w = width + 2.0 * FLOOR_MARGIN_M
    clearance, cprov = clearance_of(f.tags)
    profile = cross_section(floor_w, clearance)
    pts = _dedupe_polyline(list(f.geometry))
    if len(pts) < 2:
        raise InvalidFeature("tunnel collapses to fewer than 2 distinct points; not generated")
    if not all(inside_terrain(grid, x, y) for x, y in pts):
        raise InvalidFeature("tunnel lies outside the terrain extent; not generated")

    def path_of(points: Sequence[Vec2]) -> list[Vec3]:
        z0 = terrain_height(grid, *points[0]) + ROAD_LIFT_M
        z1 = terrain_height(grid, *points[-1]) + ROAD_LIFT_M
        samples = polyline_z_profile(points, lambda x, y: 0.0, MAX_STEP_M)
        total = samples[-1][0]
        return [(x, y, z0 + (z1 - z0) * (s / total) - z_off) for s, x, y, _ in samples]

    def mesh_of(path: Sequence[Vec3], origin: Vec3) -> MeshData:
        # Reserve the upper bound (quads as 2 triangles, plus the headwalls) before allocating the mesh.
        n = len(profile)
        ctx.budget.reserve(f.id, n * len(path) + 2 * HEADWALL_TRIANGLE_RESERVE,
                           2 * n * (len(path) - 1) + 2 * HEADWALL_TRIANGLE_RESERVE)
        return _tube_mesh(profile, [(x - origin[0], y - origin[1], z - origin[2]) for x, y, z in path],
                          f"tunnel_{short_name(f.id)}")

    path = path_of(pts)
    origin = (sum(p[0] for p in path) / len(path), sum(p[1] for p in path) / len(path), path[0][2])
    try:
        mesh = mesh_of(path, origin)
    except InvalidFeature:
        simple = _simplify(pts, 0.5)
        if len(simple) == len(pts):
            raise
        path = path_of(simple)
        mesh = mesh_of(path, origin)
    ctx.budget.charge(f.id, len(mesh.vertices), mesh_triangle_count(mesh))
    prov = {"width": wprov, "floor_width_m": round(floor_w, 2), "clearance": cprov,
            "clearance_m": round(clearance, 2),
            "profile": f"inferred:floor = road width + 2 x {FLOOR_MARGIN_M:g} m, walls {clearance - ARCH_RISE_M:g} m, "
                       f"{ARCH_SEGMENTS}-segment arch rising {ARCH_RISE_M:g} m",
            "vertical": f"inferred:linear in arc length between the portal road heights (terrain +{ROAD_LIFT_M:g} m)"}
    spec = ObjectSpec(mesh.name, f.id, "tunnel", "Tunnels", mesh=mesh, location=origin, provenance=prov)
    return _Tube(f, mesh, origin, profile, path, spec, clearance, floor_w / 2.0)


def _cover(plan: ScenePlan, ctx: StageContext, tube: _Tube) -> None:
    """Cover warning and tree blocking along the tube."""
    from .generate import terrain_height
    grid, z_off = ctx.terrain, ctx.z_offset
    path = tube.path
    arc = tube.arc

    def cover(x: float, y: float, z: float) -> float:
        return terrain_height(grid, x, y) - z_off - (z + tube.clearance)

    L = arc.length
    n = max(2, min(int(math.ceil(L)) + 1, MAX_SAMPLES))
    covers: list[float] = []
    for k in range(n):
        x, y, z, *_ = arc.at(L * k / (n - 1))
        covers.append(cover(x, y, z))
    if sum(1 for c in covers if c < COVER_WARN_M) > 0.5 * len(covers):
        plan.report["warnings"].append(
            f"{tube.feature.id}: terrain above the tunnel roof is under {COVER_WARN_M:g} m for more than half of "
            "its length (likely cut-and-cover or an underpass); the tube is generated as is")
    for a, b in zip(path, path[1:]):
        if min(cover(*a), cover(*b)) < 2.0:
            ctx.road_segments.append(((a[0], a[1]), (b[0], b[1]), tube.half + 1.0))
            ctx.keepout.append(((a[0], a[1]), (b[0], b[1]), tube.half + 1.0))
    for p, q in ((path[0], path[1]), (path[-1], path[-2])):
        ctx.keepout.append(((p[0], p[1]), (p[0], p[1]), PORTAL_KEEPOUT_M))


def _build_headwalls(plan: ScenePlan, ctx: StageContext, tube: _Tube) -> list[ObjectSpec]:
    from .generate import ObjectSpec, mesh_triangle_count, terrain_height
    grid, z_off = ctx.terrain, ctx.z_offset
    path = tube.path
    arc = tube.arc
    L = arc.length
    T = HEADWALL_THICKNESS_M
    step = max(1.0, L / MAX_SAMPLES)
    out: list[ObjectSpec] = []
    taken: list[float] = []
    for end in (0, 1):
        s_h: float | None = None
        k = 0
        while k * step <= L - T:
            s = k * step if end == 0 else L - k * step
            x, y, z, *_ = arc.at(s)
            if terrain_height(grid, x, y) - z_off > z + tube.clearance:
                s_h = s
                break
            k += 1
        if s_h is None:
            continue
        s0 = s_h if end == 0 else s_h - T
        _x, _y, _z, d, seg, seg_s = arc.at(s0 + T / 2.0)
        a, b = path[seg], path[seg + 1]
        seg_len = math.hypot(b[0] - a[0], b[1] - a[1])
        if seg_len < T:
            plan.report["warnings"].append(
                f"{tube.feature.id}: portal headwall skipped (path segment shorter than {T:g} m where the "
                "terrain covers the tube)")
            continue
        t0 = min(max(s0 - seg_s, 0.0), seg_len - T)
        if any(abs((seg_s + t0) - o) < T for o in taken):
            continue
        taken.append(seg_s + t0)
        c: list[Vec3] = []
        for t in (t0, t0 + T):
            f = t / seg_len
            c.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f))
        side = (d[1], -d[0])
        w = tube.half + grid.spacing
        top = _terrain_max(grid, c, side, w, d) - z_off + HEADWALL_ABOVE_TERRAIN_M
        top = max(top, max(p[2] for p in c) + tube.clearance + HEADWALL_ABOVE_TERRAIN_M)
        ox, oy, oz = (c[0][0] + c[1][0]) / 2, (c[0][1] + c[1][1]) / 2, c[0][2]
        rel = [(p[0] - ox, p[1] - oy, p[2] - oz) for p in c]
        mesh = headwall_mesh(f"headwall{end}_{tube.mesh.name}", rel[0], rel[1], side, tube.profile, w, top - oz)
        ctx.budget.charge(tube.feature.id, len(mesh.vertices), mesh_triangle_count(mesh))
        out.append(ObjectSpec(mesh.name, f"{tube.feature.id}:headwall{end}", "structure", "Structures", mesh=mesh,
                              location=(ox, oy, oz),
                              provenance={"role": f"portal headwall of {tube.feature.id}",
                                          "geometry": "inferred:1 m slab where the terrain first rises above the "
                                                      "tube roof, through-hole equal to the tube profile"}))
    return out


def _terrain_max(grid: ElevationGrid, c: Sequence[Vec3], side: Vec2, w: float, d: Vec2) -> float:
    """Highest terrain (map z) over the slab footprint: edges sampled every 0.5 m plus the grid vertices inside."""
    from .generate import terrain_height
    corners = [(c[0][0] - side[0] * w, c[0][1] - side[1] * w), (c[0][0] + side[0] * w, c[0][1] + side[1] * w),
               (c[1][0] + side[0] * w, c[1][1] + side[1] * w), (c[1][0] - side[0] * w, c[1][1] - side[1] * w)]
    best = -math.inf
    for p, q in zip(corners, corners[1:] + corners[:1]):
        m = max(1, int(math.ceil(math.hypot(q[0] - p[0], q[1] - p[1]) / 0.5)))
        for k in range(m + 1):
            f = k / m
            best = max(best, terrain_height(grid, p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f))
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    i0 = max(0, int(math.ceil((min(xs) - grid.x0) / grid.spacing)))
    i1 = min(grid.nx - 1, int(math.floor((max(xs) - grid.x0) / grid.spacing)))
    j0 = max(0, int(math.ceil((min(ys) - grid.y0) / grid.spacing)))
    j1 = min(grid.ny - 1, int(math.floor((max(ys) - grid.y0) / grid.spacing)))
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            x, y = grid.x0 + i * grid.spacing, grid.y0 + j * grid.spacing
            u = (x - c[0][0]) * side[0] + (y - c[0][1]) * side[1]
            s = (x - c[0][0]) * d[0] + (y - c[0][1]) * d[1]
            if abs(u) <= w and 0.0 <= s <= HEADWALL_THICKNESS_M:
                best = max(best, grid.heights[j][i])
    return best


def _make_probe(tube: _Tube, area: Area) -> Probe:
    """Probe through the tube, extended 3 m beyond a portal unless that would leave the area."""
    r = min(PROBE_MAX_RADIUS_M, (tube.clearance - 1.0) / 2.0, tube.half - 0.2)
    pts = _thin([(x, y, z + r + 0.5) for x, y, z in tube.path], 62)
    for end in (0, 1):
        a, b = (pts[0], pts[1]) if end == 0 else (pts[-1], pts[-2])
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        if d < 1e-9:
            continue
        x = a[0] + (a[0] - b[0]) / d * PORTAL_PROBE_MARGIN_M
        y = a[1] + (a[1] - b[1]) / d * PORTAL_PROBE_MARGIN_M
        if not area.contains(x, y):
            continue
        if end == 0:
            pts.insert(0, (x, y, a[2]))
        else:
            pts.append((x, y, a[2]))
    return {"id": f"{tube.feature.id}:bore", "kind": "tunnel", "feature": tube.feature.id,
            "path_map": [[round(v, 4) for v in p] for p in pts], "radius_m": round(r, 4)}


def _thin(pts: list[Vec3], limit: int) -> list[Vec3]:
    """At most ``limit`` points keeping the ends: 3D Douglas-Peucker with a growing tolerance."""
    tol = 0.01
    while len(pts) > limit:
        pts = _dp3(pts, tol)
        tol *= 2.0
    return pts


def _dp3(pts: Sequence[Vec3], tol: float) -> list[Vec3]:
    a, b = pts[0], pts[-1]
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    L2 = sum(v * v for v in ab)
    best, at = -1.0, 0
    for i in range(1, len(pts) - 1):
        p = pts[i]
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, sum((p[k] - a[k]) * ab[k] for k in range(3)) / L2))
        dd = math.dist(p, (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t))
        if dd > best:
            best, at = dd, i
    if best <= tol:
        return [a, b]
    return _dp3(pts[:at + 1], tol)[:-1] + _dp3(pts[at:], tol)
