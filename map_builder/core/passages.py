"""Building passage stage of ``build_plan`` (D18, D21, D24) and the probe of elevated building parts.

* :func:`split` replaces a building crossed by a ``tunnel=building_passage`` / ``covered=yes`` highway with
  lower parts (footprint minus the corridor, flat-topped at the passage height, ids ``<id>#1..k``) and an upper
  part (the full footprint from the passage height up, id ``<id>#k+1``) built by the ordinary elevated-volume
  code. A building the passage cannot be cut out of is left unchanged and the reason is reported.
* :func:`build` generates the passage road at grade and its ``elevated`` probe; passages that cut no building
  are reported as unsupported.
* :func:`elevated_probe` / :func:`finish`: the probe under an elevated part, and the D21 re-check of all probes
  this module emitted against the finished plan.
"""

import math

from .osm import Feature, Polygon, _subset, point_in_ring, ring_area
from .structures import check_probes, polyline_z_profile
from .triangulate import dedupe_ring

MIN_CLEARANCE_M = 2.5            # lowest passage height (also the lowest maxheight taken as measured)
MAX_CLEARANCE_M = 10.0
DEFAULT_HEIGHT_M = 4.5
EAVE_MARGIN_M = 1.0              # the upper part keeps at least this much wall above the passage
CORRIDOR_MARGIN_M = 0.5
PROBE_MIN_CLEARANCE_M = 2.6      # elevated parts with less free height get no probe
PROBE_LIFT_M = 0.3
PROBE_RUNOUT_M = 3.0
MIN_PIECE_AREA_M2 = 1.0
MAX_PROBE_POINTS = 60
_EPS = 1e-9


class _State:
    def __init__(self):
        self.handled = {}     # passage feature id -> dict(a, b, t0, t1, height)
        self.reasons = {}     # passage feature id -> why no building was cut
        self.probes = []      # ids of the probes this module emitted
        self.boxes = None     # passage feature id -> bbox, computed once
        self.dropped = []     # probes not exported: {id, reason}
        self.prebuilt = {}    # piece id -> build_building result computed while checking the split


def _state(ctx):
    st = getattr(ctx, "passage_state", None)
    if st is None:
        st = ctx.passage_state = _State()
    return st


def _probe_radius(clearance):
    return min(1.0, (clearance - 0.6) / 2.0)


def _gen():
    from . import generate   # generate imports this module
    return generate


# --- geometry -----------------------------------------------------------------------------------------------

def _seg_param(a, b, c, d):
    """Parameter along a->b where it meets segment c->d, or None (parallel or no meeting)."""
    ex, ey = b[0] - a[0], b[1] - a[1]
    fx, fy = d[0] - c[0], d[1] - c[1]
    den = ex * fy - ey * fx
    if abs(den) < _EPS:
        return None
    gx, gy = c[0] - a[0], c[1] - a[1]
    t = (gx * fy - gy * fx) / den
    u = (gx * ey - gy * ex) / den
    if -_EPS <= u <= 1 + _EPS:
        return t
    return None


def _crossings(a, b, ring, lo=0.0, hi=1.0):
    """Sorted, de-duplicated parameters in (lo, hi) where a->b meets the ring."""
    ts = []
    n = len(ring)
    for k in range(n):
        t = _seg_param(a, b, ring[k], ring[(k + 1) % n])
        if t is not None and lo < t < hi:
            ts.append(t)
    ts.sort()
    out = []
    for t in ts:
        if not out or t - out[-1] > 1e-9:
            out.append(t)
    return out


def _clip_side(ring, a, nrm, off):
    """Part of ``ring`` with ``nrm . (p - a) >= off`` (Sutherland-Hodgman against one line)."""
    out = []
    n = len(ring)
    for k in range(n):
        p, q = ring[k], ring[(k + 1) % n]
        dp = nrm[0] * (p[0] - a[0]) + nrm[1] * (p[1] - a[1]) - off
        dq = nrm[0] * (q[0] - a[0]) + nrm[1] * (q[1] - a[1]) - off
        if dp >= 0:
            out.append(p)
        if (dp >= 0) != (dq >= 0):
            f = dp / (dp - dq)
            out.append((p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f))
    return out


def _bbox_overlap(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _tag_label(tags):
    return "tunnel=building_passage" if tags.get("tunnel") == "building_passage" else "covered=yes"


# --- the split ----------------------------------------------------------------------------------------------

def _eave(tags, height, eave_based):
    """Estimated eave height: ``height`` minus the roof (source roof:height, else 1 m) of a non-flat roof."""
    if eave_based or tags.get("roof:shape") in (None, "flat"):
        return height
    roof = _gen().parse_length(tags.get("roof:height"))
    return height - (1.0 if roof is None else roof)


def _crossing_of(passage, poly):
    """``("cross", a, b, t0, t1)``, ``("reason", text)`` or None (the passage does not meet the footprint)."""
    pts = passage.geometry
    inside = [i for i, p in enumerate(pts) if poly.contains(p[0], p[1])]
    if inside:
        if 0 in inside or len(pts) - 1 in inside:
            return ("reason", "passage ends inside the building footprint (dead end)")
        return ("reason", "passage bends inside the building footprint")
    found = []
    for i in range(len(pts) - 1):
        ts = _crossings(pts[i], pts[i + 1], poly.outer)
        if ts:
            found.append((i, ts))
    if not found:
        return None
    if len(found) != 1 or len(found[0][1]) != 2:
        return ("reason", "passage meets the building footprint more than once, or only touches it")
    i, (t0, t1) = found[0]
    a, b = pts[i], pts[i + 1]
    mid = (t0 + t1) / 2
    if not poly.contains(a[0] + (b[0] - a[0]) * mid, a[1] + (b[1] - a[1]) * mid):
        return ("reason", "passage only touches the building footprint")
    return ("cross", a, b, t0, t1)


def split(plan, ctx, feature):
    """The footprints to generate for building ``feature``: the building itself, or the lower parts and the upper
    part of a building a passage crosses (see the module docstring)."""
    passages = getattr(ctx.classified, "passages", ())
    if not passages:
        return [feature]
    st = _state(ctx)
    poly = feature.geometry
    box = poly.bbox()
    if st.boxes is None:
        st.boxes = {p.id: (min(q[0] for q in p.geometry), min(q[1] for q in p.geometry),
                           max(q[0] for q in p.geometry), max(q[1] for q in p.geometry)) for p in passages}
    cands = []
    for p in passages:
        if p.id in st.handled:
            continue
        if not _bbox_overlap(box, st.boxes[p.id]):
            continue
        res = _crossing_of(p, poly)
        if res is not None:
            cands.append((p, res))
    if not cands:
        return [feature]
    for p, r in cands:
        if r[0] == "reason":
            st.reasons.setdefault(p.id, r[1])
    crossing = [(p, r) for p, r in cands if r[0] == "cross"]
    if not crossing:
        return [feature]

    def refuse(reason):
        for p, _ in crossing:
            st.reasons.setdefault(p.id, reason)
        return [feature]

    if len(crossing) > 1:
        return refuse(f"{len(crossing)} passages cross the same building")
    passage, (_, a, b, t0, t1) = crossing[0]
    if "building:part" in feature.tags:
        return refuse("building:part outlines are not cut by passages")
    if poly.holes:
        return refuse("courtyard building (footprint with holes) is not cut by passages")
    gen = _gen()
    height, min_h, _, _, eave_based = gen._building_height(feature.tags)
    if min_h > 0:
        return refuse("building with min_height / building:min_level is not cut by passages")
    eave = _eave(feature.tags, height, eave_based)
    measured = gen.parse_length(passage.tags.get("maxheight"))
    if measured is not None and MIN_CLEARANCE_M <= measured <= MAX_CLEARANCE_M:
        clearance, prov = measured, "measured:osm maxheight"
    else:
        clearance = min(DEFAULT_HEIGHT_M, eave - EAVE_MARGIN_M)
        prov = "inferred:min(4.5 m, building eave - 1 m)"
    if clearance < MIN_CLEARANCE_M or clearance > eave - EAVE_MARGIN_M:
        return refuse(f"passage height {clearance:.1f} m does not fit under the building eave ({eave:.1f} m; "
                      f"{EAVE_MARGIN_M:g} m of wall is kept above it)")
    terrain = ctx.terrain
    outer = [tuple(p) for p in dedupe_ring(poly.outer)]
    if any(not gen.inside_terrain(terrain, x, y) for x, y in outer):
        return [feature]   # build_building reports it
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    nrm = ((b[1] - a[1]) / length, -(b[0] - a[0]) / length)
    half = gen.road_width(passage.tags)[0] / 2 + CORRIDOR_MARGIN_M
    pieces = []
    for sign in (1.0, -1.0):
        ring = _clip_side(outer, a, (nrm[0] * sign, nrm[1] * sign), half)
        ring = [tuple(p) for p in dedupe_ring(ring)]
        if len(ring) >= 3 and ring_area(ring) >= MIN_PIECE_AREA_M2:
            pieces.append(ring)
    if not pieces:
        return refuse("the corridor leaves no building footprint beside it")
    for ring in pieces:
        problem = gen.ring_topology_problem(Polygon(ring), ctx.options.max_triangulation_work)
        if problem:
            return refuse(f"the corridor cut produced an invalid lower part ({problem})")
    ground = min(z for _, _, z in gen.footprint_terrain_samples(terrain, [outer]))
    base_tags = {k: v for k, v in feature.tags.items()
                 if k not in ("height", "min_height", "building:levels", "building:min_level")
                 and not k.startswith("roof:")}
    height_prov = f"{prov}; {clearance:.2f} m above the footprint's lowest ground"
    way = passage.id.split("#")[0]
    lows = []
    for k, ring in enumerate(pieces, 1):
        g = min(z for _, _, z in gen.footprint_terrain_samples(terrain, [ring]))
        h_low = clearance + ground - g   # its flat top lands on the passage height measured from the footprint
        if h_low < 1.0:
            return refuse("terrain under the building is too steep to keep the lower parts at the passage height")
        piece = Feature(f"{feature.id}#{k}", feature.kind, dict(base_tags, height=f"{h_low:.6f}"), Polygon(ring))
        piece.extra_prov = {"passage": f"lower part {k} of {len(pieces)}: footprint minus the corridor of "
                                       f"{way}, flat top at the passage height",
                            "passage_height": height_prov}
        lows.append(piece)
    utags = {k: v for k, v in feature.tags.items() if k not in ("min_height", "building:min_level")}
    utags["min_height"] = f"{clearance:.6f}"
    upper = Feature(f"{feature.id}#{len(lows) + 1}", feature.kind, utags, Polygon([tuple(p) for p in poly.outer]))
    upper.passage_upper = True
    upper.extra_prov = {"passage": f"upper part over the corridor of {way}, built as an elevated volume from the "
                                   "passage height",
                        "passage_height": height_prov}
    # The replacement is all-or-nothing: every part must be buildable (terrain humps can make a part fail), else
    # the original building stays and nothing of the passage is staged.
    opts = ctx.options
    built = {}
    for piece in lows + [upper]:
        try:
            built[piece.id] = gen.build_building(piece, terrain, ctx.z_offset, opts.seed,
                                                 max_ring_vertices=opts.max_ring_vertices,
                                                 max_work=opts.max_triangulation_work)
        except (gen.TriangulationError, gen.InvalidFeature) as e:
            return refuse(f"the replacement part {piece.id} cannot be generated ({e})")
    st.prebuilt.update(built)   # build_plan reuses these results instead of building the parts a second time
    st.handled[passage.id] = {"a": a, "b": b, "t0": t0, "t1": t1, "height": clearance, "feature": passage,
                              "note": f"{_tag_label(passage.tags)} way generated at grade under the building cut by it "
                                      f"(passage height {clearance:.2f} m)"}
    plan.count("building_passages")
    return lows + [upper]


# --- the passage road and probes ---------------------------------------------------------------------------

def _probe(ctx, pid, feature_id, points_xy, clearance, base):
    """Probe at ``base(x, y) + r + 0.3`` along ``points_xy``, or None if it leaves the terrain."""
    gen = _gen()
    r = _probe_radius(clearance)
    if any(not gen.inside_terrain(ctx.terrain, x, y, tol=0.0) for x, y in points_xy):
        return None
    length = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(points_xy, points_xy[1:]))
    step = max(ctx.terrain.spacing, length / MAX_PROBE_POINTS)
    prof = polyline_z_profile(points_xy, lambda x, y: base(x, y) + r + PROBE_LIFT_M, max_step=step)
    return {"id": pid, "kind": "elevated", "feature": feature_id,
            "path_map": [[x, y, z] for _, x, y, z in prof], "radius_m": r}


def _emit(plan, ctx, probe):
    if probe:
        plan.passage_probes.append(probe)
        _state(ctx).probes.append(probe["id"])


def take_prebuilt(ctx, piece_id):
    """The ``build_building`` result computed for a replacement part while the split was checked, or None."""
    return _state(ctx).prebuilt.pop(piece_id, None)


def handled_roads(ctx):
    """``[(passage feature, provenance note)]``: the passage ways whose building was cut. ``build_plan`` builds
    them with the ordinary roads, so road ownership and the budget treat them like any other road."""
    st = _state(ctx)
    return [(info["feature"], info["note"]) for info in st.handled.values()]


def build(plan, ctx):
    gen = _gen()
    st = _state(ctx)
    unsupported = []
    roads = {o.mb_id for o in plan.objects if o.mb_class == "road"}
    for f in getattr(ctx.classified, "passages", ()):
        info = st.handled.get(f.id)
        if info is None:
            unsupported.append(f)
            continue
        if not ctx.options.roads:
            continue
        if f.id not in roads:
            st.dropped.append({"id": f"{f.id}:passage", "reason": "the passage road was not generated (see "
                                                                  "invalid_features or the covering road)"})
            continue
        a, b = info["a"], info["b"]
        e = PROBE_RUNOUT_M / math.hypot(b[0] - a[0], b[1] - a[1])
        pts = [(a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s)
               for s in (max(0.0, info["t0"] - e), min(1.0, info["t1"] + e))]
        lift = gen.ROAD_LIFT_M - ctx.z_offset
        _emit(plan, ctx, _probe(ctx, f"{f.id}:passage", f.id, pts, info["height"],
                                lambda x, y: gen.terrain_height(ctx.terrain, x, y) + lift))
    seen = set()
    for f in unsupported:
        way = f.id.split("#")[0]
        if way in seen:
            continue
        seen.add(way)
        reason = next((st.reasons[p.id] for p in unsupported if p.id.split("#")[0] == way and p.id in st.reasons),
                      "the way crosses no building footprint")
        pos = getattr(f, "report_pos", (len(ctx.classified.unsupported), 0))
        ctx.pending.append((pos[0], pos[1], {"id": way, "reason": f"{_tag_label(f.tags)}: {reason}; no passage "
                                                                  "generated, building left unchanged",
                                             "tags": _subset(f.tags)}))


def elevated_probe(plan, ctx, feature):
    """Emit the ``<mb_id>:under`` probe of an elevated building part (clearance >= 2.6 m), if it has one."""
    gen = _gen()
    poly = feature.geometry
    min_h = gen._building_height(feature.tags)[1]
    if min_h <= 0:
        return
    outer = [tuple(p) for p in dedupe_ring(poly.outer)]
    if any(not gen.inside_terrain(ctx.terrain, x, y) for x, y in outer):
        return
    zs = [z for _, _, z in gen.footprint_terrain_samples(ctx.terrain, [outer])]
    clearance = min_h - (max(zs) - min(zs))
    if clearance < PROBE_MIN_CLEARANCE_M:
        return
    n = len(outer)
    k = max(range(n), key=lambda i: math.hypot(outer[(i + 1) % n][0] - outer[i][0],
                                               outer[(i + 1) % n][1] - outer[i][1]))
    p, q = outer[k], outer[(k + 1) % n]
    ln = math.hypot(q[0] - p[0], q[1] - p[1])
    c = poly.centroid()
    if ln < _EPS or not point_in_ring(c[0], c[1], outer):
        return
    d = ((q[0] - p[0]) / ln, (q[1] - p[1]) / ln)
    near = (c[0] - d[0] * 1e4, c[1] - d[1] * 1e4)
    far = (c[0] + d[0] * 1e4, c[1] + d[1] * 1e4)
    # the stretch of the axis through the centroid that lies inside the footprint
    ts = _crossings(near, far, outer)
    lo = max((t for t in ts if t < 0.5 - 1e-12), default=None)
    hi = min((t for t in ts if t > 0.5 + 1e-12), default=None)
    if lo is None or hi is None:
        return
    pts = [(near[0] + (far[0] - near[0]) * t, near[1] + (far[1] - near[1]) * t) for t in (lo, hi)]
    zmax = max(zs) - ctx.z_offset
    _emit(plan, ctx, _probe(ctx, f"{feature.id}:under", feature.id, pts, clearance, lambda x, y: zmax))


def _local_plan(plan, probes, grid=None):
    """A view of ``plan`` holding only what a probe capsule can touch: objects whose bounding box meets a probe's
    padded box, and for the terrain and road surfaces only the faces whose plan-view box meets a probe's box.
    A capsule cannot hit anything else, so the result of the check is the same as on the
    whole scene, at a fraction of the collision-preparation cost. Other objects are kept whole."""
    from types import SimpleNamespace
    gen = _gen()
    boxes = []
    for p in probes:
        pad = p["radius_m"] + 0.05
        xs, ys, zs = [q[0] for q in p["path_map"]], [q[1] for q in p["path_map"]], [q[2] for q in p["path_map"]]
        boxes.append((min(xs) - pad, min(ys) - pad, min(zs) - pad, max(xs) + pad, max(ys) + pad, max(zs) + pad))

    def hit(lo, hi):
        return any(lo[0] <= b[3] and hi[0] >= b[0] and lo[1] <= b[4] and hi[1] >= b[1]
                   and lo[2] <= b[5] and hi[2] >= b[2] for b in boxes)

    shared_r = {}
    objs = []
    for spec in plan.objects:
        if spec.mesh is None:
            md = plan.shared_meshes.get(spec.mesh_key)
            if md is None or not md.vertices:
                continue
            r = shared_r.get(spec.mesh_key)
            if r is None:
                r = shared_r[spec.mesh_key] = (max(math.hypot(x, y) for x, y, _ in md.vertices),
                                               min(z for _, _, z in md.vertices), max(z for _, _, z in md.vertices))
            s = abs(spec.scale) if not isinstance(spec.scale, (tuple, list)) else max(abs(c) for c in spec.scale)
            x, y, z = spec.location
            if hit((x - r[0] * s, y - r[0] * s, z + r[1] * s), (x + r[0] * s, y + r[0] * s, z + r[2] * s)):
                objs.append(spec)
            continue
        md = spec.mesh
        if not md.faces:
            continue
        if spec.rotation_z != 0.0 or spec.scale != 1.0:
            objs.append(spec)
            continue
        x0, y0, z0 = spec.location
        if grid is not None and spec.mb_class == "terrain" and (x0, y0, z0) == (0.0, 0.0, 0.0) \
                and len(md.vertices) == grid.nx * grid.ny and len(md.faces) == 2 * (grid.nx - 1) * (grid.ny - 1):
            # the terrain mesh is the grid (build_terrain: vertex j * nx + i, two faces per cell): pick the cells under
            # the probe boxes by index instead of scanning every vertex, so the cost does not grow with the scene
            cells = set()
            for b in boxes:
                i0 = max(0, int(math.floor((b[0] - grid.x0) / grid.spacing)))
                i1 = min(grid.nx - 2, int(math.floor((b[3] - grid.x0) / grid.spacing)))
                j0 = max(0, int(math.floor((b[1] - grid.y0) / grid.spacing)))
                j1 = min(grid.ny - 2, int(math.floor((b[4] - grid.y0) / grid.spacing)))
                cells.update((j, i) for j in range(j0, j1 + 1) for i in range(i0, i1 + 1))
            keep = [md.faces[2 * (j * (grid.nx - 1) + i) + k] for j, i in sorted(cells) for k in (0, 1)]
            if keep:
                objs.append(_sub_object(gen, spec, md, keep))
            continue
        vx, vy, vz = zip(*md.vertices)
        if not hit((min(vx) + x0, min(vy) + y0, min(vz) + z0), (max(vx) + x0, max(vy) + y0, max(vz) + z0)):
            continue
        if spec.mb_class not in ("terrain", "road"):
            objs.append(spec)    # solids must stay closed; other classes are small or may span the scene
            continue
        # Cohen-Sutherland style: a face is dropped for a box when all its vertices lie beyond the same side of it
        codes = []
        for b in boxes:
            lx, ly, lz, hx, hy, hz = b[0] - x0, b[1] - y0, b[2] - z0, b[3] - x0, b[4] - y0, b[5] - z0
            codes.append([(x < lx) | ((x > hx) << 1) | ((y < ly) << 2) | ((y > hy) << 3) | ((z < lz) << 4)
                          | ((z > hz) << 5) for x, y, z in md.vertices])

        faces = md.faces
        if all(len(f) == 3 for f in faces):
            alive = [False] * len(faces)
            for c in codes:
                for k, ok in enumerate([not (c[a] & c[b] & c[d]) for a, b, d in faces]):
                    if ok:
                        alive[k] = True
            keep = [f for f, ok in zip(faces, alive) if ok]
        else:
            def kept(f):
                for c in codes:
                    acc = 63
                    for i in f:
                        acc &= c[i]
                        if not acc:
                            return True
                return False
            keep = [f for f in faces if kept(f)]
        if len(keep) == len(md.faces):
            objs.append(spec)
        elif keep:
            objs.append(_sub_object(gen, spec, md, keep))
    return SimpleNamespace(objects=objs, shared_meshes=plan.shared_meshes)


def _sub_object(gen, spec, md, keep):
    """``spec`` reduced to the faces ``keep`` (vertex indices compacted) for the probe check."""
    used = sorted({i for f in keep for i in f})
    remap = {v: k for k, v in enumerate(used)}
    sub = gen.MeshData(md.name)
    sub.vertices = [md.vertices[i] for i in used]
    sub.faces = [tuple(remap[i] for i in f) for f in keep]
    sub.face_materials = [0] * len(keep)
    sub.face_colors = [(0.5, 0.5, 0.5)] * len(keep)
    sub.materials = ["MB Probe Check"]
    return gen.ObjectSpec(spec.name, spec.mb_id, spec.mb_class, spec.collection, mesh=sub, location=spec.location)


def finish(plan, ctx):
    """D21: probes this module emitted are checked against the finished plan; a blocked one is not exported and
    is listed in ``report['passage_probes_blocked']`` with the blocking object's ``mb_id``. The manifest holds at
    most ``PASSAGE_PROBE_MAX`` probes: surplus probes of this module are not exported and are listed in
    ``report['passage_probes_dropped']``."""
    from .package import PASSAGE_PROBE_MAX
    st = _state(ctx)
    mine = [p for p in plan.passage_probes if p["id"] in st.probes]
    dropped = list(st.dropped)
    if mine:
        others = len(plan.passage_probes) - len(mine)
        room = max(0, PASSAGE_PROBE_MAX - others)
        _, blocked = check_probes(_local_plan(plan, mine[:PASSAGE_PROBE_MAX], ctx.terrain),
                                  mine[:PASSAGE_PROBE_MAX])
        gone = {b["id"] for b in blocked}
        survivors = [p for p in mine[:PASSAGE_PROBE_MAX] if p["id"] not in gone]
        for p in survivors[room:]:
            dropped.append({"id": p["id"], "reason": f"the manifest holds at most {PASSAGE_PROBE_MAX} passage probes"})
            gone.add(p["id"])
        for p in mine[PASSAGE_PROBE_MAX:]:
            dropped.append({"id": p["id"], "reason": f"the manifest holds at most {PASSAGE_PROBE_MAX} passage probes"})
            gone.add(p["id"])
        if gone:
            plan.passage_probes[:] = [p for p in plan.passage_probes if p["id"] not in gone]
        if blocked:
            plan.report.setdefault("passage_probes_blocked", []).extend(blocked)
    if dropped:
        plan.report.setdefault("passage_probes_dropped", []).extend(dropped)
