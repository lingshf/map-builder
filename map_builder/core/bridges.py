"""Bridge stage of ``build_plan`` (D18, D21, D22, D25): highway ways tagged ``bridge=*`` (not ``no``) become
flyable-under deck solids (class ``bridge``) with passage probes over and under the deck.

Pure Python, no bpy. The deck is a rectangle (road width + 2 x 0.5 m, 1.0 m thick) swept along the way; its top
follows a profile that is linear between the at-grade end heights and raised, within an 8 % ramp, where the
ground under the deck needs more clearance.
"""

import math

from .errors import LimitError
from .structures import polyline_z_profile, sweep

DECK_THICKNESS_M = 1.0
DECK_SIDE_MARGIN_M = 0.5
CLEARANCE_PER_LAYER_M = 5.0
MAX_GRADE = 0.08
SAMPLE_STEP_M = 10.0
END_SINK_M = 0.5
MIN_LENGTH_M = 2.0
AT_GRADE_TOL_M = 0.3   # an approach road whose surface is this close under the deck underside (or above) joins it
PROBE_RADIUS_M = 1.0
DECK_PROBE_HEIGHT_M = 1.5
UNDER_PROBE_HEIGHT_M = 1.5
UNDER_PROBE_MIN_CLEARANCE_M = 4.0
UNDER_PROBE_SIDE_M = 3.0
MAX_DECK_PROBE_POINTS = 64
APPROACH_MAX_DEVIATION_DEG = 30.0   # an approach road leaves the deck end within this of straight
APPROACH_TIE_DEG = 5.0   # two candidates this close are ambiguous: none is exempt
SEGMENT_SAMPLE_M = 1.0
PARAPET_HEIGHT_M = 1.0
PARAPET_WIDTH_M = 0.3
PIER_MIN_CLEARANCE_M = 6.0   # piers only where the deck stands more than this above the ground
PIER_SPACING_M = 40.0
PIER_DEPTH_M = 1.5   # along the deck
PIER_SIDE_INSET_M = 1.0   # the pier is this much narrower than the deck
PIER_SINK_M = 1.0   # below the lowest ground under the footprint
PIER_MAX_SHIFT_M = 5.0
PIER_SHIFT_STEP_M = 0.5
PIER_PROBE_GAP_M = 3.0
PIER_ROAD_MARGIN_M = 0.25
PIER_TRIANGLES = 12
PIER_VERTICES = 8


def _layer(tags):
    try:
        return max(1, int(tags.get("layer", "1")))
    except (TypeError, ValueError):
        return 1


def _unit(dx, dy):
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-12 else (1.0, 0.0)


def _directions(pts):
    """Horizontal unit direction of travel at each sample (central difference)."""
    out = []
    for i in range(len(pts)):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        out.append(_unit(b[0] - a[0], b[1] - a[1]))
    return out


def deck_profile(s, lower, z_a, z_b, max_grade=MAX_GRADE):
    """Deck top heights at the arc lengths ``s`` (D22): the straight line between the end heights ``z_a`` and
    ``z_b``, raised where ``lower`` (the wanted minimum top) is higher, so that the deck's own grade never
    exceeds ``max_grade``. It is the smallest such profile: the maximum of the line and the ``max_grade`` cones
    under every reachable wanted height (a wanted height the ends cannot reach within the grade is clamped to
    what they can). The ends stay exactly at ``z_a`` / ``z_b``; if the line itself is steeper than
    ``max_grade`` the profile cannot fix that and keeps it."""
    n = len(s)
    total = s[-1]
    line = [z_a + (z_b - z_a) * si / total for si in s]
    reach = [min(lower[j], z_a + max_grade * s[j], z_b + max_grade * (total - s[j])) for j in range(n)]
    top = list(reach)
    for i in range(1, n):
        top[i] = max(top[i], top[i - 1] - max_grade * (s[i] - s[i - 1]))
    for i in range(n - 2, -1, -1):
        top[i] = max(top[i], top[i + 1] - max_grade * (s[i + 1] - s[i]))
    top = [max(a, b) for a, b in zip(top, line)]
    top[0], top[-1] = z_a, z_b
    return top


def _ground_max(terrain_z, x, y, d, half, step=None):
    """Highest terrain over the section through (x, y) perpendicular to ``d``, between ``-half`` and ``half``
    (centre, both edges and, with ``step``, every ``step`` metres)."""
    nx, ny = -d[1], d[0]
    ts = {-half, 0.0, half}
    if step:
        k = int(math.ceil(2 * half / step))
        ts.update(-half + 2 * half * m / k for m in range(k + 1))
    return max(terrain_z(x + nx * t, y + ny * t) for t in ts)


def _clip(subject, clip):
    """Sutherland-Hodgman: the convex polygon ``subject`` clipped to the convex counter-clockwise ``clip``."""
    out = subject
    for k in range(len(clip)):
        if not out:
            break
        a, b = clip[k], clip[(k + 1) % len(clip)]
        ex, ey = b[0] - a[0], b[1] - a[1]
        side = [ex * (p[1] - a[1]) - ey * (p[0] - a[0]) for p in out]
        nxt = []
        for i, p in enumerate(out):
            j = (i + 1) % len(out)
            q = out[j]
            if side[i] >= 0.0:
                nxt.append(p)
            if (side[i] >= 0.0) != (side[j] >= 0.0):
                t = side[i] / (side[i] - side[j])
                nxt.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        out = nxt
    return out


MAX_TRIANGLE_PAIRS = 20000   # plan-overlapping (road, deck) triangle pairs per deck; LimitError past it, before any clipping
ROAD_CELL_M = 16.0


def _poly_area(poly):
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1]))


def _cut(poly, ux, uy, c):
    """``poly`` clipped to the half-plane ``ux * x + uy * y >= c``."""
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        fp, fq = ux * p[0] + uy * p[1] - c, ux * q[0] + uy * q[1] - c
        if fp >= 0.0:
            out.append(p)
        if (fp >= 0.0) != (fq >= 0.0):
            t = fp / (fp - fq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def _bary(p, a, b, c):
    """Barycentric weights of the plan point ``p`` in the triangle ``a, b, c`` (non-degenerate)."""
    d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    l1 = ((p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])) / d
    l2 = ((b[0] - a[0]) * (p[1] - a[1]) - (p[0] - a[0]) * (b[1] - a[1])) / d
    return 1.0 - l1 - l2, l1, l2


def _ccw(a, b, c):
    """``(a, b, c)`` counter-clockwise in plan, or None when degenerate."""
    d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    if abs(d) < 1e-12:
        return None
    return (a, b, c) if d > 0 else (a, c, b)


def _road_triangles(plan, ctx, ids):
    """The exported triangles of the road meshes ``ids`` as ``(CCW vertices (x, y, absolute z), bbox, road id)``,
    cached on ``ctx``."""
    objs = getattr(ctx, "road_objects", None)
    if objs is None:
        objs = ctx.road_objects = {}
        for o in plan.objects:
            if o.mb_class == "road" and o.mesh is not None:
                objs.setdefault(o.mb_id, []).append(o)
        ctx.road_triangles = {}
    out = []
    for rid in ids:
        if rid not in ctx.road_triangles:
            tris = []
            for o in objs.get(rid, ()):
                lx, ly, lz = o.location
                vs = [(x + lx, y + ly, z + lz + ctx.z_offset) for x, y, z in o.mesh.vertices]
                for i, j, k in o.mesh.triangles():
                    tri = _ccw(vs[i], vs[j], vs[k])
                    if tri:
                        xs, ys = [p[0] for p in tri], [p[1] for p in tri]
                        tris.append((tri, (min(xs), min(ys), max(xs), max(ys)), rid))
            ctx.road_triangles[rid] = tris
        out.extend(ctx.road_triangles[rid])
    return out


def _deck_triangles(mesh, count, n):
    """The underside triangles of the swept deck: ``(path segment, ((x, y, path node) x 3) CCW in plan)``. The
    underside quad of segment ``i`` is face ``n i`` of the sweep (``n`` profile points), split as the collision
    split it."""
    out = []
    for i in range(count):
        q = [(mesh.vertices[v][0], mesh.vertices[v][1], v // n) for v in mesh.faces[n * i]]
        for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
            tri = _ccw(*tri)
            if tri:
                out.append((i, tri))
    return out


def _end_nodes(node_ids):
    """The OSM ids of a way's own first and last node as they reach clearance (None where clipping made the end)."""
    return (node_ids[0], node_ids[-1]) if node_ids else (None, None)


def _approach_segments(roads, ids, ends, g):
    """Per road id, the ``(a, b, half width)`` segment that is the approach road at each deck end. ``ends`` is
    ``[(OSM node id or None, end point, next point of the swept path)]``: the directions are those of the
    deduplicated path the sweep uses. Among all the segments leaving the end's OSM node (a node shared with the
    deck, never a nearby one), the single outward continuation closest to straight is exempt, if within
    ``APPROACH_MAX_DEVIATION_DEG``; when the two best are within ``APPROACH_TIE_DEG`` of each other it is
    ambiguous and nothing is exempt. Every other segment still counts."""
    wanted, out = set(ids), {}
    for en, e, i in ends:
        if en is None or math.dist(e, i) <= g.POLYLINE_DEDUP_TOL_M:
            continue
        straight = math.atan2(e[1] - i[1], e[0] - i[0])   # the direction continuing outward from the deck
        cands, seen = [], set()
        for r in roads:
            if r.id not in wanted or not r.node_ids:
                continue
            for k, nid in enumerate(r.node_ids):
                if nid != en or k not in (0, len(r.node_ids) - 1):   # only a road's own end node
                    continue
                for step in (-1, 1):
                    o = k + step
                    while 0 <= o < len(r.geometry) and math.dist(r.geometry[o], e) <= g.POLYLINE_DEDUP_TOL_M:
                        o += step   # skip duplicated vertices
                    if 0 <= o < len(r.geometry) and (r.id, o) not in seen:
                        seen.add((r.id, o))
                        dx, dy = r.geometry[o][0] - e[0], r.geometry[o][1] - e[1]
                        dev = abs((math.atan2(dy, dx) - straight + math.pi) % (2 * math.pi) - math.pi)
                        cands.append((math.degrees(dev), r.id, k, o, r))
        cands.sort(key=lambda c: c[0])
        if not cands or cands[0][0] > APPROACH_MAX_DEVIATION_DEG:
            continue
        if len(cands) > 1 and cands[1][0] - cands[0][0] <= APPROACH_TIE_DEG:
            continue
        _, rid, k, o, r = cands[0]
        out.setdefault(rid, []).append((r.geometry[k], r.geometry[o], g.road_width(r.tags)[0] / 2.0))
    return out


def _in_approach(tri, segs):
    """The triangle's centroid lies on one of the segments' ribbons."""
    cx = sum(p[0] for p in tri[0]) / 3.0
    cy = sum(p[1] for p in tri[0]) / 3.0
    for a, b, hw in segs:
        dx, dy = b[0] - a[0], b[1] - a[1]
        n2 = dx * dx + dy * dy
        u = 0.0 if n2 == 0 else max(0.0, min(1.0, ((cx - a[0]) * dx + (cy - a[1]) * dy) / n2))
        if math.hypot(cx - a[0] - u * dx, cy - a[1] - u * dy) <= hw + 0.5:
            return True
    return False


def _triangle_pairs(deck_tris, road_tris):
    """Index pairs ``(deck, road)`` of the triangles whose plan bounding boxes overlap, found through a grid over
    the deck triangles. Counted as they are found: more than ``MAX_TRIANGLE_PAIRS`` pairs (or grid cells visited)
    raises LimitError, so at most ``MAX_TRIANGLE_PAIRS + 1`` are ever held and nothing is clipped before."""
    cap, cell = MAX_TRIANGLE_PAIRS, ROAD_CELL_M
    grid, boxes = {}, []
    for di, (_, tri) in enumerate(deck_tris):
        xs, ys = [p[0] for p in tri], [p[1] for p in tri]
        box = (min(xs), min(ys), max(xs), max(ys))
        boxes.append(box)
        for cx in range(math.floor(box[0] / cell), math.floor(box[2] / cell) + 1):
            for cy in range(math.floor(box[1] / cell), math.floor(box[3] / cell) + 1):
                grid.setdefault((cx, cy), []).append(di)
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    pairs, visits = [], 0
    for ri, (_, rb, _rid) in enumerate(road_tris):
        if rb[2] < x0 or rb[0] > x1 or rb[3] < y0 or rb[1] > y1:
            continue
        seen = set()
        for cx in range(math.floor(max(rb[0], x0) / cell), math.floor(min(rb[2], x1) / cell) + 1):
            for cy in range(math.floor(max(rb[1], y0) / cell), math.floor(min(rb[3], y1) / cell) + 1):
                visits += 1
                if visits > cap:
                    raise LimitError(f"bridge clearance needs more than {cap} grid cells")
                for di in grid.get((cx, cy), ()):
                    b = boxes[di]
                    if di not in seen and b[0] <= rb[2] and rb[0] <= b[2] and b[1] <= rb[3] and rb[1] <= b[3]:
                        seen.add(di)
                        pairs.append((di, ri))
                        if len(pairs) > cap:
                            raise LimitError(f"bridge clearance needs more than {cap} road/deck triangle pairs (stopped at {len(pairs)})")
    return pairs


def _crossing_points(pairs, deck_tris, road_tris):
    """For each overlapping (deck, road) triangle pair, the vertices of the convex intersection of the two
    triangles in plan: ``(deck nodes, deck weights, road z, road id)``. Both surfaces are planar on a triangle,
    so their difference is linear on the intersection and its minimum is at one of these vertices."""
    out = []
    for di, ri in pairs:
        i, dtri = deck_tris[di]
        rtri, _, rid = road_tris[ri]
        poly = _clip([(p[0], p[1]) for p in rtri], [(p[0], p[1]) for p in dtri])
        if len(poly) < 3 or _poly_area(poly) < 1e-9:
            continue
        for p in poly:
            wd, wr = _bary(p, *dtri), _bary(p, *[q[:2] for q in rtri])
            out.append(([q[2] for q in dtri], wd, sum(w * q[2] for w, q in zip(wr, rtri)), rid))
    return out


def _road_nodes(roads):
    """OSM node id -> ids of the roads that END at it (a road's own first or last node)."""
    table = {}
    for f in roads:
        for nid in _end_nodes(f.node_ids):
            if nid is not None:
                table.setdefault(nid, []).append(f.id)
    return table


def _deck_profile_2d(half, parapets):
    """The deck section (lateral right, up), CCW. Without ``parapets`` the slab; with them one outline in which
    each outer side is one wall from the underside to the parapet top, so a parapet adds only its top and inner
    faces (4 triangles per sweep interval). Returns ``(points, index of the first deck-surface point)``; the
    surface edge is from that point to the next one."""
    if not parapets:
        return [(-half, -DECK_THICKNESS_M), (half, -DECK_THICKNESS_M), (half, 0.0), (-half, 0.0)], 2
    inner = half - PARAPET_WIDTH_M
    return [(-half, -DECK_THICKNESS_M), (half, -DECK_THICKNESS_M), (half, PARAPET_HEIGHT_M),
            (inner, PARAPET_HEIGHT_M), (inner, 0.0), (-inner, 0.0), (-inner, PARAPET_HEIGHT_M),
            (-half, PARAPET_HEIGHT_M)], 4


def _split_caps(mesh):
    """Replace the two end caps of a parapeted deck (one concave polygon each: a fan triangulation would cover the
    notch between the parapets) by three convex quads: the slab and one parapet on each side."""
    pieces = ((0, 1, 4, 5), (1, 2, 3, 4), (5, 6, 7, 0))
    caps = [mesh.faces.pop(), mesh.faces.pop()]   # the end cap, then the start cap
    mat, col = mesh.face_materials[-2:], mesh.face_colors[-2:]
    del mesh.face_materials[-2:], mesh.face_colors[-2:]
    for cap, m, c in zip(caps, mat[::-1], col[::-1]):
        order = cap if cap == tuple(sorted(cap)) else tuple(reversed(cap))   # ring order, ascending
        for piece in pieces:
            face = tuple(order[i] for i in piece)
            if cap != order:   # the end cap faces the other way
                face = (face[0],) + face[:0:-1]
            mesh.faces.append(face)
            mesh.face_materials.append(m)
            mesh.face_colors.append(c)

def _assign_materials(mesh, road_color, n, surface):
    """The deck surface faces (the sweep quads on the profile edge ``surface`` -> ``surface + 1``) get the road
    material."""
    top = mesh.material_index("MB Road")
    for k in range(len(mesh.faces)):
        quad = mesh.faces[k]
        if len(quad) == 4 and k % n == surface and {v % n for v in quad} == {surface, (surface + 1) % n}:
            mesh.face_materials[k] = top
            mesh.face_colors[k] = road_color


def build(plan, ctx):
    from . import generate as g
    features = list(getattr(ctx.classified, "structure_bridges", ()))
    if not features or not ctx.options.roads:
        return
    invalid = plan.report["invalid_features"]
    tz = lambda x, y: g.terrain_height(ctx.terrain, x, y)   # noqa: E731
    roads = _road_nodes(ctx.classified.roads)
    road_boxes = _road_boxes(ctx.classified.roads)
    ctx.deck_segments = []
    results = []   # (length, probes)
    for f in features:
        try:
            pts = g._dedupe_polyline(list(f.geometry))
            if len(pts) < 2 or sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])) < MIN_LENGTH_M:
                raise g.InvalidFeature(f"shorter than {MIN_LENGTH_M:g} m; not generated")
            if not all(g.inside_terrain(ctx.terrain, x, y) for x, y in pts):
                raise g.InvalidFeature("lies outside the terrain extent; not generated")
            results.append(_build_deck(plan, ctx, f, pts, tz, roads, g, road_boxes))
        except g.InvalidFeature as e:
            ctx.budget.release()
            invalid.append({"id": f.id, "reason": f"bridge: {e}"})
    for _, probes in results:   # checked, budgeted and capped with every other kind by finalize_probes, in plan order
        ctx.probes.extend(probes)


def tree_blocker(ctx):
    """``blocked(x, y)``: a point within a bridge deck's footprint (half width + 1 m), where no mapped tree is
    placed."""
    from . import generate as g
    segs = getattr(ctx, "deck_segments", ())
    if not segs:
        return lambda x, y: False
    a = ctx.area
    buckets = g._Buckets([((p, q, r), (min(p[0], q[0]) - r, min(p[1], q[1]) - r, max(p[0], q[0]) + r,
                                       max(p[1], q[1]) + r)) for p, q, r in segs],
                         cell=25.0, bounds=(-a.width / 2, -a.height / 2, a.width / 2, a.height / 2))

    def blocked(x, y):
        for p, q, r in buckets.query(x, y):
            dx, dy = q[0] - p[0], q[1] - p[1]
            n2 = dx * dx + dy * dy
            t = 0.0 if n2 == 0 else max(0.0, min(1.0, ((x - p[0]) * dx + (y - p[1]) * dy) / n2))
            if math.hypot(x - p[0] - t * dx, y - p[1] - t * dy) < r:
                return True
        return False
    return blocked


def _road_boxes(roads):
    out = []
    for r in roads:
        g_ = r.geometry
        if len(g_) >= 2:
            xs, ys = [p[0] for p in g_], [p[1] for p in g_]
            out.append(((min(xs), min(ys), max(xs), max(ys)), r))
    return out


def _build_deck(plan, ctx, f, pts, tz, roads, g, road_boxes):
    kept = g._dedupe_indices(f.geometry)   # ``pts`` is the deduplicated path: the node ids follow its indices
    deck_nodes = _end_nodes(f.node_ids)
    terrain, z_off, budget = ctx.terrain, ctx.z_offset, ctx.budget
    width, wprov = g.road_width(f.tags)
    deck_w = width + 2 * DECK_SIDE_MARGIN_M
    half = deck_w / 2.0
    clearance = _layer(f.tags) * CLEARANCE_PER_LAYER_M
    samples = polyline_z_profile(pts, tz, SAMPLE_STEP_M)
    xy = [(x, y) for _, x, y, _ in samples]
    s = [t[0] for t in samples]
    total = s[-1]
    dirs = _directions(xy)
    z_a, z_b = samples[0][3] + g.ROAD_LIFT_M, samples[-1][3] + g.ROAD_LIFT_M
    line = [z_a + (z_b - z_a) * si / total for si in s]
    ground = [_ground_max(tz, x, y, d, half) + g.ROAD_LIFT_M for (x, y), d in zip(xy, dirs)]
    lower = [gr + clearance + DECK_THICKNESS_M for gr in ground]

    # the ends sink into the abutting ground/road (not past the terrain edge)
    path_xy = list(xy)
    front = 0
    for first, (end, nbr) in enumerate(((xy[0], xy[1]), (xy[-1], xy[-2]))):
        dx, dy = _unit(end[0] - nbr[0], end[1] - nbr[1])
        ext = (end[0] + dx * END_SINK_M, end[1] + dy * END_SINK_M)
        if g.inside_terrain(terrain, ext[0], ext[1], 0.0):
            if first == 0:
                path_xy.insert(0, ext)
                front = 1
            else:
                path_xy.append(ext)
    n_path = len(path_xy)
    parapets = half - PARAPET_WIDTH_M >= PROBE_RADIUS_M + 0.05   # the deck probe runs between the parapets
    prof, surface = _deck_profile_2d(half, parapets)
    np_ = len(prof)
    piers_max = max(0, math.ceil(total / PIER_SPACING_M) - 1) if ctx.options.bridge_piers else 0
    tris = 16 * (n_path - 1) + 12 if parapets else 8 * (n_path - 1) + 4   # side quads + end caps
    budget.reserve(f.id, np_ * n_path + PIER_VERTICES * piers_max, tris + PIER_TRIANGLES * piers_max)
    mesh = sweep(prof, [(x, y, 0.0) for x, y in path_xy], True, name=f"bridge_{g.short_name(f.id)}")
    if parapets:
        _split_caps(mesh)
    node = lambda m: min(max(m - front, 0), len(s) - 1)   # noqa: E731  path node -> deck sample

    # clearance over the crossing roads is judged on the exported triangles: the road meshes as built and the
    # deck underside, clipped pairwise; the difference is linear on each clipped polygon
    pts_box = (min(p[0] for p in path_xy) - half, min(p[1] for p in path_xy) - half,
               max(p[0] for p in path_xy) + half, max(p[1] for p in path_xy) + half)
    ids = []
    for (bx0, by0, bx1, by1), r in road_boxes:
        m = 3.0 * g.road_width(r.tags)[0] + 2.0
        if r.id != f.id and bx1 + m >= pts_box[0] and bx0 - m <= pts_box[2] \
                and by1 + m >= pts_box[1] and by0 - m <= pts_box[3]:
            ids.append(r.id)
    road_tris = _road_triangles(plan, ctx, ids) if ids else []
    ends = [(deck_nodes[0], pts[0], pts[1]), (deck_nodes[1], pts[-1], pts[-2])]
    approach = _approach_segments(ctx.classified.roads, ids, ends, g)
    if approach:
        road_tris = [t for t in road_tris if not _in_approach(t, approach.get(t[2], ()))]
    records = []
    if road_tris:
        deck_tris = _deck_triangles(mesh, n_path - 1, np_)
        pairs = _triangle_pairs(deck_tris, road_tris)
        records = _crossing_points(pairs, deck_tris, road_tris)
    # an unsplit approach (S1-F1): the end runs where the straight deck line stays below the clearance over the
    # terrain are ramp, not deck. A crossing there is exempt only where the road surface is at the deck's own
    # surface: its gap to the deck underside (ground-only profile) is at most ``AT_GRADE_TOL_M`` (a road at or
    # above the underside joins the deck). Every positive gap above that is a real under-crossing and is measured
    # on the exported geometry (D39), wherever it lies and whichever nodes the roads share. A way whose line never
    # clears the terrain has no real span, so nothing is exempt.
    lo, hi = _approach_runs(line, ground, clearance)
    if lo > 0 or hi < len(s) - 1:
        top0 = deck_profile(s, lower, z_a, z_b)
        records = [r for r in records
                   if not all((node(m) < lo or node(m) > hi) for m, w in zip(r[0], r[1]) if w > 1e-9)
                   or sum(w * (top0[node(m)] - DECK_THICKNESS_M) for m, w in zip(r[0], r[1])) - r[2]
                   > AT_GRADE_TOL_M]
    for nodes, wd, rz, _rid in records:
        need = rz + clearance + DECK_THICKNESS_M
        for m, w in zip(nodes, wd):
            if w > 1e-9:
                lower[node(m)] = max(lower[node(m)], need)
    top = deck_profile(s, lower, z_a, z_b)
    max_raise = max(t - ln for t, ln in zip(top, line))
    grade = max(abs(top[i + 1] - top[i]) / (s[i + 1] - s[i]) for i in range(len(s) - 1))

    checked, where = None, ""
    for nodes, wd, rz, rid in records:
        c = sum(w * (top[node(m)] - DECK_THICKNESS_M) for m, w in zip(nodes, wd)) - rz
        if checked is None or c < checked:
            checked, where = c, f" over the crossing road {rid}"
    # clearance: the lowest over the crossing roads; else the best interior sample over the ground (unreachable
    # near the abutments); no sample = unverified
    if checked is None and len(s) > 2:
        checked = max(top[i] - DECK_THICKNESS_M - ground[i] for i in range(1, len(s) - 1))
        where = " under the deck"
    clear_met = None if checked is None else checked >= clearance - 1e-6
    warns = []
    if clear_met is False:
        warns.append(f"{f.id}: bridge clearance{where} is at most {checked:.2f} m, below "
                     f"the {clearance:g} m wanted: the span is too short to rise that high at a "
                     f"deck grade of {MAX_GRADE * 100:g} %")
    elif clear_met is None:
        warns.append(f"{f.id}: bridge clearance could not be verified: the span is too short to sample")
    if grade > MAX_GRADE + 1e-6:
        warns.append(f"{f.id}: bridge deck grade is {grade * 100:.1f} %, above {MAX_GRADE * 100:g} %: "
                     "the end heights (the adjoining road heights) differ too much for its length")

    cx = sum(p[0] for p in xy) / len(xy)
    cy = sum(p[1] for p in xy) / len(xy)
    oz = top[0] - z_off
    vz = [v for _, v in prof]
    mesh.vertices = [(x - cx, y - cy, top[node(v // np_)] - z_off + vz[v % np_] - oz)
                     for v, (x, y, _) in enumerate(mesh.vertices)]
    road_color = (0.12, 0.12, 0.12) if f.tags.get("highway") not in g.FOOT else (0.35, 0.32, 0.28)
    _assign_materials(mesh, road_color, np_, surface)
    under = _under_probe(f, xy, s, dirs, top, half, tz, g, z_off, (lo, hi))
    n_piers = 0
    if piers_max:
        piers = _piers(xy, s, dirs, top, deck_w, tz, g, ctx, f, under, road_boxes)
        for corners, zs, zb in piers:
            _add_pier(mesh, corners, zs, zb, z_off, oz, cx, cy)
        n_piers = len(piers)
    budget.commit(mesh)
    plan.report["warnings"].extend(warns)

    measured = wprov.startswith("measured")
    raised = max_raise > 1e-6
    prov = {"width": f"{'measured:osm width' if measured else 'inferred:road width'} + 2 x "
                     f"{DECK_SIDE_MARGIN_M:g} m",
            "width_m": round(deck_w, 2), "thickness": f"inferred:{DECK_THICKNESS_M:g} m",
            "profile": ("inferred:linear between the end heights (road z at the ends), " +
                        (f"raised up to {max_raise:.2f} m toward {clearance:g} m clearance under the deck "
                         if raised else "not raised ") +
                        f"(D22, deck grade <= {MAX_GRADE * 100:g} %)" +
                        ("; clearance not verified (span too short to sample)" if clear_met is None else
                         f"; clearance NOT met: at most {checked:.2f} m" if not clear_met else "")),
            "max_raise_m": round(max_raise, 3), "max_grade_pct": round(grade * 100, 2),
            "clearance_wanted_m": clearance, "clearance_met": clear_met,
            "length_m": round(total, 2)}
    if checked is not None:
        prov["clearance_m"] = round(checked, 2)
    for key, nid in (("start", deck_nodes[0]), ("end", deck_nodes[1])):
        rid = next((r for r in roads.get(nid, ()) if r != f.id), None) if nid is not None else None
        prov[f"{key}_joint"] = f"joins at-grade road {rid}" if rid else "free end: terrain + road lift"
    if not measured:
        plan.inferred("bridge.width")
    plan.inferred("bridge.thickness")
    if raised:
        plan.inferred("bridge.profile")
    ctx.add(g.ObjectSpec(mesh.name, f.id, "bridge", "Bridges", mesh=mesh, location=(cx, cy, oz), provenance=prov))
    for a, b in zip(pts, pts[1:]):
        ctx.road_segments.append((a, b, half + 1.0))
        ctx.deck_segments.append((a, b, half + 1.0))
    plan.count("bridges")

    idx = list(range(len(xy)))
    if len(idx) > MAX_DECK_PROBE_POINTS:
        k = MAX_DECK_PROBE_POINTS - 1
        idx = sorted({round(m * (len(xy) - 1) / k) for m in range(k + 1)})
    deck = {"id": f"{f.id}:deck", "kind": "bridge", "feature": f.id, "radius_m": PROBE_RADIUS_M,
            "path_map": [[round(xy[i][0], 4), round(xy[i][1], 4),
                          round(top[i] + DECK_PROBE_HEIGHT_M - z_off, 4)] for i in idx]}
    return total, [deck] + ([under] if under else [])


def _interp(s, vals, t):
    """Linear interpolation of ``vals`` at arc length ``t`` (clamped) over the sorted arc lengths ``s``."""
    if t <= s[0]:
        return vals[0]
    for i in range(1, len(s)):
        if t <= s[i]:
            w = (t - s[i - 1]) / (s[i] - s[i - 1])
            return vals[i - 1] + (vals[i] - vals[i - 1]) * w
    return vals[-1]


def _on_road(x, y, roads_near):
    for a, b, hw in roads_near:
        dx, dy = b[0] - a[0], b[1] - a[1]
        n2 = dx * dx + dy * dy
        u = 0.0 if n2 == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / n2))
        if math.hypot(x - a[0] - u * dx, y - a[1] - u * dy) <= hw + PIER_ROAD_MARGIN_M:
            return True
    return False


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    u = 0.0 if n2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


def _piers(xy, s, dirs, top, deck_w, tz, g, ctx, f, under_probe, road_boxes):
    """Pier shells ``(plan corners CCW, underside z at the two ends along the deck, bottom z)`` for the deck
    sampled at ``xy`` / arc length ``s`` with top heights ``top``. Evenly spaced at most ``PIER_SPACING_M``
    apart; each is shifted along the deck by at most ``PIER_MAX_SHIFT_M`` (else skipped) until it stands where the
    deck is more than ``PIER_MIN_CLEARANCE_M`` above the ground, is at least ``PIER_PROBE_GAP_M`` from the
    ``under`` probe segment, is clear of every at-grade road ribbon (other than bridges) and of the deck's own
    kinks, so its top follows the underside."""
    total = s[-1]
    count = math.ceil(total / PIER_SPACING_M) - 1
    if count < 1:
        return []
    a, b = PIER_DEPTH_M / 2.0, (deck_w - PIER_SIDE_INSET_M) / 2.0
    xs = [p[0] for p in xy]
    ys = [p[1] for p in xy]
    pad = deck_w + a + PIER_MAX_SHIFT_M
    near = [(r.geometry[i], r.geometry[i + 1], g.road_width(r.tags)[0] / 2.0)
            for (bx0, by0, bx1, by1), r in road_boxes
            if r.id != f.id and bx1 + pad >= min(xs) and bx0 - pad <= max(xs)
            and by1 + pad >= min(ys) and by0 - pad <= max(ys)
            for i in range(len(r.geometry) - 1)]
    probe = None
    if under_probe:   # back to plan metres: the probe path is in map frame, the same frame as xy
        probe = tuple((p[0], p[1]) for p in under_probe["path_map"])
    shifts = [0.0]
    for k in range(1, int(PIER_MAX_SHIFT_M / PIER_SHIFT_STEP_M) + 1):
        shifts += [k * PIER_SHIFT_STEP_M, -k * PIER_SHIFT_STEP_M]
    out, last = [], None
    for k in range(1, count + 1):
        for sh in shifts:
            t = total * k / (count + 1) + sh
            if t - a < 0.0 or t + a > total or (last is not None and not 2 * a <= t - last <= PIER_SPACING_M):
                continue
            # the underside is linear over the pier only if no sample kink lies within it
            z_lo = _interp(s, top, t - a) - DECK_THICKNESS_M
            z_hi = _interp(s, top, t + a) - DECK_THICKNESS_M
            if abs(_interp(s, top, t) - DECK_THICKNESS_M - (z_lo + z_hi) / 2.0) > 0.001:
                continue
            i = min(range(len(s)), key=lambda m: abs(s[m] - t))
            d = dirs[i]
            cx, cy = _interp(s, xs, t), _interp(s, ys, t)
            nx, ny = -d[1], d[0]
            corners = [(cx + d[0] * u + nx * v, cy + d[1] * u + ny * v) for u, v in ((-a, -b), (a, -b), (a, b), (-a, b))]
            pts = []
            for ui in range(5):
                for vi in range(int(2 * b / 0.5) + 2):
                    u = -a + 2 * a * ui / 4
                    v = -b + 2 * b * vi / (int(2 * b / 0.5) + 1)
                    pts.append((cx + d[0] * u + nx * v, cy + d[1] * u + ny * v))
            ground = [tz(*p) for p in pts]
            if min(z_lo, z_hi) - max(ground) - g.ROAD_LIFT_M <= PIER_MIN_CLEARANCE_M:
                continue
            if probe and any(_seg_dist(p, *probe) < PIER_PROBE_GAP_M for p in pts):
                continue
            if near and any(_on_road(p[0], p[1], near) for p in pts):
                continue
            out.append((corners, (z_lo, z_hi), min(ground) - PIER_SINK_M))
            last = t
            break
    return out


def _add_pier(mesh, corners, zs, z_bottom, z_off, oz, cx, cy):
    """Append a closed box shell (8 vertices, 6 quads = 12 triangles) to ``mesh`` in its local frame: bottom at
    ``z_bottom``, top at the deck underside ``zs`` = (z at the first pair of corners, z at the second); corners
    CCW in plan, the first and last at the low end of the deck."""
    zt = (zs[0], zs[1], zs[1], zs[0])
    lo = [mesh.add_vertex(x - cx, y - cy, z_bottom - z_off - oz) for x, y in corners]
    hi = [mesh.add_vertex(x - cx, y - cy, z - z_off - oz) for (x, y), z in zip(corners, zt)]
    color = (0.6, 0.6, 0.6)
    mesh.add_face(tuple(reversed(lo)), "MB Concrete", color)
    mesh.add_face(tuple(hi), "MB Concrete", color)
    for i in range(4):
        j = (i + 1) % 4
        mesh.add_face((lo[i], lo[j], hi[j], hi[i]), "MB Concrete", color)


def _approach_runs(top, ground, clearance):
    """(first, last) deck sample whose clearance over the ground reaches ``clearance``; samples outside are the
    approach end runs. No such sample: (0, last), i.e. no approach (a low bridge is not an approach)."""
    ok = [i for i in range(len(top)) if top[i] - DECK_THICKNESS_M - ground[i] >= clearance - 1e-6]
    return (ok[0], ok[-1]) if ok else (0, len(top) - 1)


def _under_probe(f, xy, s, dirs, top, half, tz, g, z_off, span=None):
    """The straight segment across the span at the interior sample with the most clearance under the deck
    (None below ``UNDER_PROBE_MIN_CLEARANCE_M``), level at the highest ground along it + 1.5 m."""
    reach = half + 3.0
    best = None
    lo, hi = span or (1, len(xy) - 2)
    for i in range(max(lo, 1), min(hi, len(xy) - 2) + 1):
        g_max = _ground_max(tz, xy[i][0], xy[i][1], dirs[i], reach, SEGMENT_SAMPLE_M) + g.ROAD_LIFT_M
        clear = top[i] - DECK_THICKNESS_M - g_max
        # the most clearance; among equals (a raised plateau) the sample nearest the middle of the span
        key = (round(clear, 4), -abs(s[i] - s[-1] / 2.0))
        if best is None or key > best[0]:
            best = (key, i, g_max, clear)
    if best is None or best[3] < UNDER_PROBE_MIN_CLEARANCE_M:
        return None
    _, i, g_max, _ = best
    x, y = xy[i]
    nx, ny = -dirs[i][1], dirs[i][0]
    z = round(g_max + UNDER_PROBE_HEIGHT_M - z_off, 4)
    return {"id": f"{f.id}:under", "kind": "bridge", "feature": f.id, "radius_m": PROBE_RADIUS_M,
            "path_map": [[round(x - nx * reach, 4), round(y - ny * reach, 4), z],
                         [round(x + nx * reach, 4), round(y + ny * reach, 4), z]]}
