"""Shared helpers for bridge, tunnel and passage generation (pure Python, no bpy).

* :func:`sweep`: a 2D profile swept along a 3D path, closed ends = solid, open ends = tube.
* :func:`polyline_z_profile`: arc-length helpers shared by bridges and tunnels.
* :func:`check_probes`: passage probes against the generated plan meshes (D21).

Also the stage context handed to the stage modules (:class:`StageContext`) and
:func:`report_unsupported`, the stubs' reporting of features that are not generated yet.
"""

import math

from .collision import ColObject, read_collision, write_collision
from .glb import node_scale
from .mesh import MeshData
from .query import DEFAULT_MAX_WORK, capsule_hits

def _invalid(msg):
    from .generate import InvalidFeature   # generate imports the stage modules, which import this one
    return InvalidFeature(msg)


MAX_TURN_DEG = 60.0
_EPS = 1e-9


class StageContext:
    """What the structure stages of ``build_plan`` share: terrain grid, z offset, budget, options, ``add``
    (appends an ObjectSpec to the plan), road segments ``(a, b, radius)`` that block trees (stages append),
    the classified features and the area."""

    def __init__(self, area, terrain, z_offset, budget, options, add, classified, road_segments):
        self.area = area
        self.terrain = terrain
        self.z_offset = z_offset
        self.budget = budget
        self.options = options
        self.add = add
        self.classified = classified
        self.road_segments = road_segments
        self.pending = []

    def flush_unsupported(self, plan):
        n = len(self.classified.unsupported)
        entries = plan.report["unsupported_features"]
        keyed = [((i, 0, 0), e) for i, e in enumerate(entries[:n])]
        keyed += [((at, 1, seq), e) for at, seq, e in self.pending]
        keyed.sort(key=lambda t: t[0])
        entries[:n] = [e for _, e in keyed]
        self.pending = []


def report_unsupported(ctx, features, reason_of):
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

def _subset(tags):
    from .osm import _subset as subset
    return subset(tags)


# --- geometry -----------------------------------------------------------------------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    if n < _EPS:
        return (0.0, 0.0, 0.0), 0.0
    return (a[0] / n, a[1] / n, a[2] / n), n


def _frames(path):
    """Per path point (tangent, side, up) with a horizontal side vector (the path never rolls); the tangent at
    a joint is the mitre direction and the returned scale lengthens the side offset to keep the section width."""
    dirs = []
    for a, b in zip(path, path[1:]):
        d, n = _norm(_sub(b, a))
        if n < _EPS:
            raise _invalid("structure path has a zero-length segment")
        dirs.append(d)
    out = []
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
            t, _ = _norm((d0[0] + d1[0], d0[1] + d1[1], d0[2] + d1[2]))
            half = math.acos(cosang) / 2
            miter = 1.0 / max(math.cos(half), 0.5)
        th = math.hypot(t[0], t[1])
        if th < _EPS:
            raise _invalid("structure path is vertical")
        side = (t[1] / th, -t[0] / th, 0.0)          # to the right of the direction of travel
        out.append((t, side, miter))
    return out


def sweep(profile_2d, path_3d, closed_ends, name="sweep", material="MB Concrete", color=(0.6, 0.6, 0.6)):
    """Mesh of ``profile_2d`` ((lateral, up) points, CCW seen along the direction of travel, lateral to the
    right, up +Z) swept along ``path_3d`` with mitred joints.

    ``closed_ends=True``: a solid, end caps added, faces CCW outward (positive volume). ``False``: a tube open
    at both ends, faces CCW seen from the inside (the validator's tube rule: negative volume once the portal
    loops are capped). Raises :class:`InvalidFeature` for fewer than 2 path points, a profile under 3 points,
    a zero-length segment, or a turn above ``MAX_TURN_DEG`` degrees (split the path there instead)."""
    if len(profile_2d) < 3:
        raise _invalid("structure profile needs at least 3 points")
    path = [tuple(float(c) for c in p) for p in path_3d]
    if len(path) < 2:
        raise _invalid("structure path needs at least 2 points")
    frames = _frames(path)
    mesh = MeshData(name)
    n = len(profile_2d)
    rings = []
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


def polyline_z_profile(points_xy, z_func, max_step=None):
    """Samples of a polyline: ``[(s, x, y, z)]`` with ``s`` the arc length from the first point, the original
    vertices kept and, with ``max_step``, extra samples so no step exceeds it; ``z = z_func(x, y)``."""
    pts = [(float(x), float(y)) for x, y in points_xy]
    if len(pts) < 2:
        raise _invalid("polyline needs at least 2 points")
    out, s = [], 0.0
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

def plan_collision(plan, exclude=()):
    """Collision of the plan's mesh objects (world transforms applied), as ``(Collision, mb_ids)``; objects
    with ``exclude`` ids are left out."""
    objs, ids = [], []
    for spec in plan.objects:
        if spec.mb_id in exclude:
            continue
        md = spec.mesh if spec.mesh is not None else plan.shared_meshes.get(spec.mesh_key)
        if md is None or not md.faces:
            continue
        sx, sy, sz = node_scale(spec.scale)
        c, s_ = math.cos(spec.rotation_z), math.sin(spec.rotation_z)
        loc = spec.location
        verts = [(c * x * sx - s_ * y * sy + loc[0], s_ * x * sx + c * y * sy + loc[1], z * sz + loc[2])
                 for x, y, z in md.vertices]
        tris = list(md.triangles())
        if sx * sy * sz < 0:   # a mirrored object keeps its winding rule in world space
            tris = [(a, c_, b) for a, b, c_ in tris]
        objs.append(ColObject(spec.name, spec.mb_id, spec.mb_class, verts, tris))
        ids.append(spec.mb_id)
    return read_collision(write_collision(objs)), ids


def check_probes(plan, probes, max_work=DEFAULT_MAX_WORK):
    """Passage probes ``{id, feature, path_map, radius_m, ...}`` against the plan meshes (D21).

    Returns ``(kept, blocked)``: ``blocked`` entries are ``{id, blocker}`` (the blocking object's ``mb_id``;
    the probe's own ``feature`` is not a blocker). The work budget is shared: when it runs out the remaining
    probes are returned in ``blocked`` with ``blocker=None`` and ``reason="work budget exhausted"``, never
    silently kept."""
    kept, blocked = [], []
    if not probes:
        return kept, blocked
    col, _ = plan_collision(plan)
    left = max_work
    for i, pr in enumerate(probes):
        own = pr.get("feature")
        try:
            res = capsule_hits(col, [tuple(p) for p in pr["path_map"]], pr["radius_m"], left, result=True)
        except Exception as exc:   # LimitError: budget exhausted
            if type(exc).__name__ != "LimitError":
                raise
            for rest in probes[i:]:
                blocked.append({"id": rest["id"], "blocker": None, "reason": "work budget exhausted"})
            break
        left -= res.work
        hits = [col.objects[k]["mb_id"] for k in res.objects if col.objects[k]["mb_id"] != own]
        if hits:
            blocked.append({"id": pr["id"], "blocker": hits[0]})
        else:
            kept.append(pr)
    return kept, blocked
