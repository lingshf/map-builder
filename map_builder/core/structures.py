"""Shared helpers for bridge, tunnel and passage generation (pure Python, no bpy).

* :func:`sweep`: a 2D profile swept along a 3D path, closed ends = solid, open ends = tube.
* :func:`polyline_z_profile`: arc-length helpers shared by bridges and tunnels.
* :func:`check_probes`: passage probes against the generated plan meshes (D21).

Also the stage context handed to the stage modules (:class:`StageContext`) and
:func:`report_unsupported`, the stubs' reporting of features that are not generated yet.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from .collision import Collision, ColObject, f32, read_collision, write_collision
from .glb import node_scale
from .mesh import MeshData
from .query import DEFAULT_MAX_WORK, capsule_hits

if TYPE_CHECKING:
    from .dem import ElevationGrid
    from .generate import InvalidFeature, ObjectSpec, PlanOptions, SceneBudget, ScenePlan
    from .geodesy import Area
    from .osm import Classified, Feature

Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]
Color = tuple[float, float, float]
Segment = tuple[Vec2, Vec2, float]
Region = tuple[float, float, float, float]
Probe = dict[str, Any]          # Any: probe entries are free-form manifest dicts ({id, feature, path_map, radius_m, ...})
Frame = tuple[Vec3, Vec3, float]
Tri = tuple[Vec3, Vec3, Vec3]
RoadTri = tuple[Tri, Region, str]     # CCW plan triangle with absolute z, its plan bbox, the road id
Triangles = list[tuple[int, int, int]]
PlacedGeometry = tuple[Sequence[Vec3], Triangles, dict[tuple[int, int], list[int]]]

def _invalid(msg: str) -> InvalidFeature:
    from .generate import InvalidFeature   # generate imports the stage modules, which import this one
    return InvalidFeature(msg)


MAX_TURN_DEG = 60.0
TILE_M = 32.0               # plan tile size of the probe query index
CHUNK_M = 24.0              # probe paths are tested in pieces of about this plan length
_EPS = 1e-9


class StageContext:
    """What the structure stages of ``build_plan`` share: terrain grid, z offset, budget, options, ``add``
    (appends an ObjectSpec to the plan), road segments ``(a, b, radius)`` that block trees (stages append),
    the classified features and the area."""

    # set by the bridge stage on first use (see bridges._road_triangles / bridges.build)
    road_objects: dict[str, list[ObjectSpec]]
    road_triangles: dict[str, list[RoadTri]]
    deck_segments: list[Segment]

    def __init__(self, area: Area, terrain: ElevationGrid, z_offset: float, budget: SceneBudget,
                 options: PlanOptions, add: Callable[[ObjectSpec], None], classified: Classified,
                 road_segments: list[Segment]) -> None:
        self.area = area
        self.terrain = terrain
        self.z_offset = z_offset
        self.budget = budget
        self.options = options
        self.add = add
        self.classified = classified
        self.road_segments = road_segments
        self.probes: list[Probe] = []        # passage probes queued by the stages, checked by finalize_probes
        self.keepout: list[Segment] = []       # (a, b, radius) plan segments where no tree is placed
        self.pending: list[tuple[int, int, dict[str, Any]]] = []

    def flush_unsupported(self, plan: ScenePlan) -> None:
        n = len(self.classified.unsupported)
        entries = plan.report["unsupported_features"]
        keyed = [((i, 0, 0), e) for i, e in enumerate(entries[:n])]
        keyed += [((at, 1, seq), e) for at, seq, e in self.pending]
        keyed.sort(key=lambda t: t[0])
        entries[:n] = [e for _, e in keyed]
        self.pending = []


def report_unsupported(ctx: StageContext, features: Iterable[Feature], reason_of: Callable[[Mapping[str, str]], str | None]) -> None:
    """Queue one ``unsupported_features`` entry per way (parts ``id#k`` share their way's entry) with the
    wording the classifier used before the features were routed; :meth:`StageContext.flush_unsupported` puts
    them back at the position the classifier gave them, so the report order is unchanged."""
    seen = {e[2]["id"] for e in ctx.pending}
    for f in features:
        way = f.id.split("#")[0]
        if way in seen:
            continue
        seen.add(way)
        pos = getattr(f, "report_pos", (len(ctx.classified.unsupported), 0))
        ctx.pending.append((pos[0], pos[1], {"id": way, "reason": reason_of(f.tags), "tags": _subset(f.tags)}))

def _subset(tags: Mapping[str, str]) -> dict[str, str]:
    from .osm import _subset as subset
    return subset(tags)


# --- geometry -----------------------------------------------------------------------------------------------

def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a: Vec3) -> tuple[Vec3, float]:
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    if n < _EPS:
        return (0.0, 0.0, 0.0), 0.0
    return (a[0] / n, a[1] / n, a[2] / n), n


def _frames(path: Sequence[Vec3], half_width: float = 0.0) -> list[Frame]:
    """Per path point (tangent, side, up) with a horizontal side vector (the path never rolls); the tangent at
    a joint is the mitre direction and the returned scale lengthens the side offset to keep the section width."""
    dirs: list[Vec3] = []
    for a, b in zip(path, path[1:]):
        d, n = _norm(_sub(b, a))
        if n < _EPS:
            raise _invalid("structure path has a zero-length segment")
        dirs.append(d)
    out: list[Frame] = []
    shift = [0.0] * len(path)   # how far the inner mitre corner moves along the path at each joint
    for i, p in enumerate(path):
        if i == 0:
            t, miter = dirs[0], 1.0
        elif i == len(path) - 1:
            t, miter = dirs[-1], 1.0
        else:
            d0, d1 = dirs[i - 1], dirs[i]
            h0 = math.hypot(d0[0], d0[1])
            h1 = math.hypot(d1[0], d1[1])
            if h0 < _EPS or h1 < _EPS:
                raise _invalid("structure path is vertical")
            cosang = max(-1.0, min(1.0, (d0[0] * d1[0] + d0[1] * d1[1]) / (h0 * h1)))
            if math.degrees(math.acos(cosang)) > MAX_TURN_DEG:
                raise _invalid(f"structure path turns by more than {MAX_TURN_DEG:g} degrees at point {i}")
            # bisect the turn in plan: averaging 3D tangents skews the side vector when the grades differ
            t, _ = _norm((d0[0] / h0 + d1[0] / h1, d0[1] / h0 + d1[1] / h1, d0[2] / h0 + d1[2] / h1))
            half = math.acos(cosang) / 2
            miter = 1.0 / max(math.cos(half), 0.5)
            shift[i] = half_width * math.tan(half)
        th = math.hypot(t[0], t[1])
        if th < _EPS:
            raise _invalid("structure path is vertical")
        side = (t[1] / th, -t[0] / th, 0.0)          # to the right of the direction of travel
        out.append((t, side, miter))
    for k, (a, b) in enumerate(zip(path, path[1:])):
        if shift[k] + shift[k + 1] >= math.hypot(b[0] - a[0], b[1] - a[1]):
            raise _invalid(f"structure segment {k} is too short for the profile width at its mitred joints "
                           "(the inner corner would fold back)")
    return out


def sweep(profile_2d: Sequence[Vec2], path_3d: Iterable[Sequence[float]], closed_ends: bool, name: str = "sweep",
          material: str = "MB Concrete", color: Color = (0.6, 0.6, 0.6)) -> MeshData:
    """Mesh of ``profile_2d`` ((lateral, up) points, CCW seen along the direction of travel, lateral to the
    right, up +Z) swept along ``path_3d`` with mitred joints.

    ``closed_ends=True``: a solid, end caps added, faces CCW outward (positive volume). ``False``: a tube open
    at both ends, faces CCW seen from the inside (the validator's tube rule: negative volume once the portal
    loops are capped). Raises :class:`InvalidFeature` for fewer than 2 path points, a profile under 3 points,
    a zero-length segment, a turn above ``MAX_TURN_DEG`` degrees (split the path there instead) or a segment
    too short for the profile width at its mitred joints (the inner corner would fold back)."""
    if len(profile_2d) < 3:
        raise _invalid("structure profile needs at least 3 points")
    path: list[Vec3] = [(float(p[0]), float(p[1]), float(p[2])) for p in path_3d]
    if len(path) < 2:
        raise _invalid("structure path needs at least 2 points")
    frames = _frames(path, max(abs(u) for u, _ in profile_2d))
    mesh = MeshData(name)
    n = len(profile_2d)
    rings: list[list[int]] = []
    for p, (t, side, miter) in zip(path, frames):
        rings.append([mesh.add_vertex(p[0] + side[0] * u * miter, p[1] + side[1] * u * miter, p[2] + v)
                      for u, v in profile_2d])
    # Seen along +travel with lateral to the right and up +Z, a CCW profile (right-handed in lateral/up) gives
    # side quads (r0[j], r0[j+1], r1[j+1], r1[j]) facing away from the axis.
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(n):
            k = (j + 1) % n
            quad = (r0[j], r1[j], r1[k], r0[k])
            mesh.add_face(quad if closed_ends else quad[::-1], material, color)
    if closed_ends:
        mesh.add_face(tuple(rings[0]), material, color)
        mesh.add_face(tuple(reversed(rings[-1])), material, color)
    return mesh


def polyline_z_profile(points_xy: Iterable[Sequence[float]], z_func: Callable[[float, float], float],
                       max_step: float | None = None) -> list[tuple[float, float, float, float]]:
    """Samples of a polyline: ``[(s, x, y, z)]`` with ``s`` the arc length from the first point, the original
    vertices kept and, with ``max_step``, extra samples so no step exceeds it; ``z = z_func(x, y)``."""
    pts = [(float(x), float(y)) for x, y in points_xy]
    if len(pts) < 2:
        raise _invalid("polyline needs at least 2 points")
    out: list[tuple[float, float, float, float]] = []
    s = 0.0
    for i, (x, y) in enumerate(pts):
        if i:
            px, py = pts[i - 1]
            seg = math.hypot(x - px, y - py)
            if max_step and seg > max_step:
                m = int(math.ceil(seg / max_step))
                for k in range(1, m):
                    f = k / m
                    ex, ey = px + (x - px) * f, py + (y - py) * f
                    out.append((s + seg * f, ex, ey, z_func(ex, ey)))
            s += seg
        out.append((s, x, y, z_func(x, y)))
    return out


# --- probes ---------------------------------------------------------------------------------------------------

def _world_mesh(spec: ObjectSpec, md: MeshData) -> tuple[Sequence[Vec3], Triangles]:
    """World-space ``(vertices, triangles)`` of a plan object (its transform applied, winding kept)."""
    sx, sy, sz = node_scale(spec.scale)
    c, s_ = math.cos(spec.rotation_z), math.sin(spec.rotation_z)
    loc = spec.location
    if (sx, sy, sz) == (1.0, 1.0, 1.0) and s_ == 0.0 and c == 1.0 and not any(loc):
        verts = md.vertices       # identity placement (terrain)
    else:
        verts = [(c * x * sx - s_ * y * sy + loc[0], s_ * x * sx + c * y * sy + loc[1], z * sz + loc[2])
                 for x, y, z in md.vertices]
    tris = list(md.triangles())
    if sx * sy * sz < 0:   # a mirrored object keeps its winding rule in world space
        tris = [(a, c_, b) for a, b, c_ in tris]
    return verts, tris


def plan_collision(plan: ScenePlan, exclude: Iterable[str] = ()) -> tuple[Collision, list[str]]:
    """Collision of the plan's mesh objects (world transforms applied), as ``(Collision, mb_ids)``; objects
    with ``exclude`` ids are left out."""
    objs: list[ColObject] = []
    ids: list[str] = []
    for spec in plan.objects:
        if spec.mb_id in exclude:
            continue
        md = spec.mesh if spec.mesh is not None else plan.shared_meshes.get(spec.mesh_key)
        if md is None or not md.faces:
            continue
        verts, tris = _world_mesh(spec, md)
        objs.append(ColObject(spec.name, spec.mb_id, spec.mb_class, verts, tris))
        ids.append(spec.mb_id)
    return read_collision(write_collision(objs)), ids


class _CollisionIndex:
    """Plan meshes indexed by ``TILE_M`` plan tiles, so a query for one region builds the collision of just the
    triangles near it (a superset of what a capsule inside the region can touch, so the hits are the same as
    on the whole scene). Objects are placed in world space lazily, the first time a query reaches them."""

    def __init__(self, plan: ScenePlan) -> None:
        self.plan = plan
        self.specs: list[tuple[ObjectSpec, MeshData]] = []
        self.tiles: dict[tuple[int, int], list[int]] = {}
        self.geometry: dict[int, PlacedGeometry] = {}
        radius: dict[int, float] = {}     # local plan radius per mesh (shared meshes are measured once)
        for spec in plan.objects:
            md = spec.mesh if spec.mesh is not None else plan.shared_meshes.get(spec.mesh_key)
            if md is None or not md.faces:
                continue
            r = radius.get(id(md))
            if r is None:
                r = radius[id(md)] = max(math.hypot(x, y) for x, y, _ in md.vertices)
            sx, sy, _sz = node_scale(spec.scale)
            r *= max(abs(sx), abs(sy))
            k = len(self.specs)
            self.specs.append((spec, md))
            x, y = spec.location[0], spec.location[1]
            for key in self._keys(x - r, y - r, x + r, y + r):
                self.tiles.setdefault(key, []).append(k)

    @staticmethod
    def _keys(x0: float, y0: float, x1: float, y1: float) -> list[tuple[int, int]]:
        return [(i, j) for i in range(math.floor(x0 / TILE_M), math.floor(x1 / TILE_M) + 1)
                for j in range(math.floor(y0 / TILE_M), math.floor(y1 / TILE_M) + 1)]

    def _placed(self, k: int) -> PlacedGeometry:
        g = self.geometry.get(k)
        if g is None:
            spec, md = self.specs[k]
            verts, tris = _world_mesh(spec, md)
            by_tile: dict[tuple[int, int], list[int]] = {}
            vi = [math.floor(v[0] / TILE_M) for v in verts]
            vj = [math.floor(v[1] / TILE_M) for v in verts]
            for n, (a, b, c) in enumerate(tris):
                i0, j0 = vi[a], vj[a]
                if i0 == vi[b] == vi[c] and j0 == vj[b] == vj[c]:
                    by_tile.setdefault((i0, j0), []).append(n)
                    continue
                for i in range(min(i0, vi[b], vi[c]), max(i0, vi[b], vi[c]) + 1):
                    for j in range(min(j0, vj[b], vj[c]), max(j0, vj[b], vj[c]) + 1):
                        by_tile.setdefault((i, j), []).append(n)
            g = self.geometry[k] = (verts, tris, by_tile)
        return g

    def collision(self, region: Region) -> Collision:
        """Collision of the triangles whose plan bounding box shares a tile with ``region=(x0, y0, x1, y1)``
        (built directly, with the float32 vertices a serialised collision would hold)."""
        keys = self._keys(*region)
        flat: list[Vec3] = []
        idx: list[int] = []
        tri_obj: list[int] = []
        table: list[dict[str, Any]] = []
        for k in sorted({k for key in keys for k in self.tiles.get(key, ())}):
            verts, tris, by_tile = self._placed(k)
            pick = sorted({n for key in keys for n in by_tile.get(key, ())})
            if not pick:
                continue
            spec = self.specs[k][0]
            remap: dict[int, int] = {}
            start = len(tri_obj)
            lo, hi = [math.inf] * 3, [-math.inf] * 3
            for n in pick:
                for v in tris[n]:
                    if v not in remap:
                        q = (f32(verts[v][0]), f32(verts[v][1]), f32(verts[v][2]))
                        remap[v] = len(flat)
                        flat.append(q)
                        for a in range(3):
                            lo[a] = min(lo[a], q[a])
                            hi[a] = max(hi[a], q[a])
                    idx.append(remap[v])
                tri_obj.append(len(table))
            table.append({"index": len(table), "name": spec.name, "mb_id": spec.mb_id, "class": spec.mb_class,
                          "tri_start": start, "tri_count": len(tri_obj) - start, "aabb": lo + hi})
        return Collision(flat, tuple(idx), tri_obj, bytes(len(tri_obj)), table, None, 1)  # type: ignore[arg-type]  # duck-typed lightweight Collision: list tri_object, no bounds

class WorkBudget:
    """One collision-work allowance shared by every probe check of a finalisation."""

    def __init__(self, left: int = DEFAULT_MAX_WORK) -> None:
        self.left = left


def check_probes(plan: ScenePlan, probes: Sequence[Probe] | None, max_work: int = DEFAULT_MAX_WORK,
                 budget: WorkBudget | None = None) -> tuple[list[Probe], list[dict[str, Any]]]:
    """Passage probes ``{id, feature, path_map, radius_m, ...}`` against the plan meshes (D21).

    Returns ``(kept, blocked)``: ``blocked`` entries are ``{id, blocker}`` (the blocking object's ``mb_id``;
    the probe's own ``feature`` counts like any other mesh, so a probe touching its own tunnel wall is blocked,
    as the package validator does). Each probe is tested against the triangles around its own path only. The
    work budget is shared: when it runs out the remaining probes are returned in ``blocked`` with
    ``blocker=None`` and ``reason="budget_exhausted"``, never silently kept."""
    kept: list[Probe] = []
    blocked: list[dict[str, Any]] = []
    if not probes:
        return kept, blocked
    index = _CollisionIndex(plan)
    rank: dict[str, int] = {}
    for k, (spec, _md) in enumerate(index.specs):
        rank.setdefault(spec.mb_id, k)
    budget = budget if budget is not None else WorkBudget(max_work)
    for i, pr in enumerate(probes):
        if budget.left <= 0:   # an earlier check (any kind) spent the allowance: do not run, do not publish
            blocked.extend({"id": r["id"], "blocker": None, "reason": "budget_exhausted"} for r in probes[i:])
            break
        pts = [tuple(p) for p in pr["path_map"]]
        pad = pr["radius_m"] + 0.5
        # The query's work grows with segments x triangles of every object it reaches, so a long path is tested
        # in chunks of ~CHUNK_M, each against the triangles around it (the union of the hits is the same).
        chunks: list[list[Vec2]] = []
        cur, length = [pts[0]], 0.0
        for a, b in zip(pts, pts[1:]):
            cur.append(b)
            length += math.hypot(b[0] - a[0], b[1] - a[1])
            if length >= CHUNK_M:
                chunks.append(cur)
                cur, length = [b], 0.0
        if len(cur) > 1 or not chunks:
            chunks.append(cur)
        found: set[str] = set()
        try:
            for ch in chunks:
                xs, ys = [p[0] for p in ch], [p[1] for p in ch]
                col = index.collision((min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad))
                res = capsule_hits(col, ch, pr["radius_m"], budget.left, result=True)
                budget.left -= res.work
                found.update(col.objects[k]["mb_id"] for k in res.objects)
        except Exception as exc:   # LimitError: budget exhausted
            if type(exc).__name__ != "LimitError":
                raise
            budget.left = 0   # the failed call spent what was left
            for rest in probes[i:]:
                blocked.append({"id": rest["id"], "blocker": None, "reason": "budget_exhausted"})
            break
        if found:
            blocked.append({"id": pr["id"], "blocker": min(found, key=lambda m: rank[m])})
        else:
            kept.append(pr)
    return kept, blocked


def finalize_probes(plan: ScenePlan, ctx: StageContext) -> None:
    """The single place where passage probes are finished (after the vegetation). Every staged probe is first
    checked on the finished scene by its own kind's check: the elevated / building-passage ones through
    ``passages.finish`` and the ones queued on ``ctx.probes`` (tunnels, later bridges) through ``check_probes``.
    Blocked and unchecked ones go to ``report["passage_probes_blocked"]`` with the blocker's ``mb_id`` or a
    ``reason``. Only then is the one global ``PASSAGE_PROBE_MAX`` cap applied, in plan order, to the survivors:
    the surplus is not exported and is listed in ``report["passage_probes_dropped"]``."""
    from . import passages
    from .package import PASSAGE_PROBE_MAX
    budget = WorkBudget()
    passages.finish(plan, ctx, budget)
    kept, blocked = check_probes(plan, ctx.probes, budget=budget) if ctx.probes else ([], [])
    ctx.probes = []
    plan.passage_probes.extend(kept)
    if blocked:
        plan.report.setdefault("passage_probes_blocked", []).extend(blocked)
    surplus = plan.passage_probes[PASSAGE_PROBE_MAX:]
    if surplus:
        del plan.passage_probes[PASSAGE_PROBE_MAX:]
        plan.report.setdefault("passage_probes_dropped", []).extend(
            {"id": p["id"], "reason": f"the manifest holds at most {PASSAGE_PROBE_MAX} passage probes"}
            for p in surplus)