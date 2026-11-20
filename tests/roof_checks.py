"""Geometry checker for emitted roof triangles (S3-ROOF-CASES; shared by the roof tasks and S3-REVIEW).

It works on the triangles written to ``visual/map.glb`` and ``collision/map.mbcol`` (decoded from the built
package, map frame, material per triangle from the GLB), never on ``MeshData`` faces: the GLB fans faces from
vertex 0, so a non-convex face would be mis-triangulated there. Heights come from the frozen expected file
(``fixtures/munich_roofs_expected.json``), never from the code under test.

``check_building`` returns ``{check name: detail}`` for every failed check:

  closed       walls + roof, welded at 1e-6 m: every edge is used exactly twice
  above_eave   no roof triangle vertex is below the eave z (-1 mm)
  ridge        the maximum roof z is the expected top z +-1 mm (and a vertex or horizontal edge lies there)
  normals      every ``MB Roof`` triangle faces up (n.z > 1e-6); every gable-end triangle (``MB Facade`` with a
               vertex above the eave) is vertical and its base edge lies on the footprint
  no_gap       footprint minus the union of the projected roof triangles <= 1e-6 x footprint area
  no_overlap   the sum of the pairwise intersection areas of the projected roof triangles <= 1e-6 x area
  inside       every projected roof triangle lies inside the footprint

Triangles are planar by construction, so there is no separate planarity check. Gap and overlap are independent:
a union is built by subtracting convex pieces (exact), the overlap by pairwise convex clipping, so an overlap
balanced by a gap fails both.
"""

import json
import math
import zipfile
from collections import Counter

from map_builder.core.collision import read_collision
from map_builder.core.errors import LimitError
from map_builder.core.glb import det3, read_glb
from map_builder.core.triangulate import triangulate

MM = 1e-3
WELD_M = 1e-6
REL_TOL = 1e-6
UP_EPS = 1e-6
PAIR_CAP = 250_000
CLIP_CAP = 2_000_000
ROOF, FACADE = "MB Roof", "MB Facade"


# --- decoding the built package -------------------------------------------------------------------------------

def _accessor(gl, binc, index):
    a = gl["accessors"][index]
    v = gl["bufferViews"][a["bufferView"]]
    fmt = {5121: "B", 5123: "H", 5125: "I", 5126: "f"}[a["componentType"]]
    nc = {"SCALAR": 1, "VEC3": 3}[a["type"]]
    import struct
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    flat = struct.unpack_from(f"<{a['count'] * nc}{fmt}", binc, start)
    return list(flat) if nc == 1 else [tuple(flat[k:k + 3]) for k in range(0, len(flat), 3)]


def _bin_chunk(glb):
    import struct
    o, binc = 12, b""
    while o < len(glb):
        n, t = struct.unpack_from("<II", glb, o)
        if t == 0x004E4942:
            binc = glb[o + 8:o + 8 + n]
        o += 8 + n
    return binc


def decode_package(path):
    """{mb_id: {"visual": [(material, (a, b, c))], "collision": [(a, b, c)]}} in the map frame (x, y, z up)."""
    with zipfile.ZipFile(path) as z:
        glb, col_bytes = z.read("visual/map.glb"), z.read("collision/map.mbcol")
    gl, nodes = read_glb(glb)
    binc = _bin_chunk(glb)
    col = read_collision(col_bytes)
    ents = {e["mb_id"]: e for e in col.objects}
    out = {}
    for n in nodes:
        js = gl["nodes"][n.index]
        if "mesh" not in js:
            continue
        flip = det3(n.matrix) < 0
        m = n.matrix
        tris = []
        for p in gl["meshes"][js["mesh"]]["primitives"]:
            mat = gl["materials"][p["material"]]["name"]
            pos = _accessor(gl, binc, p["attributes"]["POSITION"])
            idx = _accessor(gl, binc, p["indices"])
            for k in range(0, len(idx), 3):
                w = [tuple(m[r][0] * q[0] + m[r][1] * q[1] + m[r][2] * q[2] + m[r][3] for r in range(3))
                     for q in (pos[idx[k]], pos[idx[k + 1]], pos[idx[k + 2]])]
                a, b, c = ((q[0], -q[2], q[1]) for q in w)      # glTF (x, z, -y) -> map frame
                tris.append((mat, (a, c, b) if flip else (a, b, c)))
        mb_id = js.get("extras", {}).get("mb_id", n.name)
        e = ents.get(mb_id)
        out[mb_id] = {"visual": tris, "collision": col.object_triangles(e) if e else []}
    return out


# --- 2D / 3D helpers ---------------------------------------------------------------------------------------------

def _cross3(a, b, c):
    u, v = (b[0] - a[0], b[1] - a[1], b[2] - a[2]), (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def unit_normal(t):
    n = _cross3(*t)
    ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    return None if ln < 1e-9 else (n[0] / ln, n[1] / ln, n[2] / ln)


def area2d(poly):
    return 0.5 * sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1]
                     for k in range(len(poly)))


def _ccw(poly):
    return poly if area2d(poly) >= 0 else poly[::-1]


def _bbox(poly):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_overlap(a, b, eps=1e-9):
    return a[0] <= b[2] + eps and b[0] <= a[2] + eps and a[1] <= b[3] + eps and b[1] <= a[3] + eps


def _cut(p, q, dp, dq):
    t = dp / (dp - dq)
    return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))


def _split(poly, a, b):
    """(left, right) of the line a->b; both polygons are convex when ``poly`` is."""
    ex, ey = b[0] - a[0], b[1] - a[1]
    left, right = [], []
    prev = poly[-1]
    dprev = ex * (prev[1] - a[1]) - ey * (prev[0] - a[0])
    for p in poly:
        d = ex * (p[1] - a[1]) - ey * (p[0] - a[0])
        if (d > 0 and dprev < 0) or (d < 0 and dprev > 0):
            c = _cut(prev, p, dprev, d)
            left.append(c)
            right.append(c)
        if d >= 0:
            left.append(p)
        if d <= 0:
            right.append(p)
        prev, dprev = p, d
    return left, right


def clip_convex(subject, clip):
    """Intersection of two convex CCW polygons (Sutherland-Hodgman against a convex clip polygon)."""
    out = subject
    for k in range(len(clip)):
        if len(out) < 3:
            return []
        out = _split(out, clip[k], clip[(k + 1) % len(clip)])[0]
    return out if len(out) >= 3 else []


def subtract_convex(poly, clip):
    """Convex pieces partitioning ``poly`` minus the convex ``clip`` (both CCW)."""
    pieces, rest = [], poly
    for k in range(len(clip)):
        if len(rest) < 3:
            break
        inside, outside = _split(rest, clip[k], clip[(k + 1) % len(clip)])
        if len(outside) >= 3 and area2d(outside) > 1e-12:
            pieces.append(outside)
        rest = inside
    return pieces


def footprint_triangles(outer, holes=()):
    rings = [list(outer)] + [list(h) for h in holes]
    pts = [(p[0], p[1]) for r in rings for p in r]
    offs, o = [], 0
    for r in rings:
        offs.append(list(range(o, o + len(r))))
        o += len(r)
    return [_ccw([pts[a], pts[b], pts[c]]) for a, b, c in triangulate(pts, offs[0], offs[1:])]


def projected_roof(tris):
    out = []
    for mat, t in tris:
        if mat == ROOF:
            p = [(q[0], q[1]) for q in t]
            if abs(area2d(p)) > 1e-9:
                out.append(_ccw(p))
    return out


# --- the individual checks ---------------------------------------------------------------------------------------

def check_closed(tris):
    ids, edges = {}, Counter()
    for _, t in tris:
        v = [ids.setdefault(tuple(round(c / WELD_M) for c in p), len(ids)) for p in t]
        if len(set(v)) < 3:
            continue
        for a, b in ((v[0], v[1]), (v[1], v[2]), (v[2], v[0])):
            edges[(a, b) if a < b else (b, a)] += 1
    bad = [e for e, n in edges.items() if n != 2]
    return f"{len(bad)} of {len(edges)} edges are not used exactly twice" if bad else None


def check_above_eave(tris, eave_z):
    low = min((p[2] for m, t in tris if m == ROOF for p in t), default=None)
    if low is not None and low < eave_z - MM:
        return f"a roof vertex is at z={low:.4f}, below the eave {eave_z:.4f}"
    return None


def check_ridge(tris, top_z):
    pts = [p for m, t in tris if m == ROOF for p in t]
    if not pts:
        return "no roof triangles"
    top = max(p[2] for p in pts)
    if abs(top - top_z) > MM:
        return f"maximum roof z {top:.4f} differs from the expected top {top_z:.4f}"
    at_top = [p for p in pts if abs(p[2] - top_z) <= MM]
    if not at_top:
        return "no ridge vertex or edge at the top z"
    return None


def _segments(ring):
    return [(ring[k], ring[(k + 1) % len(ring)]) for k in range(len(ring))]


def _dist_to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln2 = dx * dx + dy * dy
    t = 0.0 if ln2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ln2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def _on_boundary(p, segments, tol=MM):
    return any(_dist_to_segment(p, a, b) <= tol for a, b in segments)


def gable_end_triangles(tris, eave_z):
    """Facade triangles that start at the eave and rise above it (a wall triangle starts below the eave)."""
    return [t for m, t in tris if m == FACADE and max(p[2] for p in t) > eave_z + MM
            and min(p[2] for p in t) >= eave_z - MM]


def _base_edge_on_footprint(t, segments):
    a, b, c = sorted(t, key=lambda p: p[2])
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    return all(_on_boundary(p, segments) for p in ((a[0], a[1]), (b[0], b[1]), mid))


def check_normals(tris, eave_z, segments):
    bad_up = bad_end = bad_base = 0
    for m, t in tris:
        n = unit_normal(t)
        if n is None:
            continue
        if m == ROOF and n[2] <= UP_EPS:
            bad_up += 1
    for t in gable_end_triangles(tris, eave_z):
        n = unit_normal(t)
        if n is None:
            continue
        if abs(n[2]) >= UP_EPS:
            bad_end += 1
        elif not _base_edge_on_footprint(t, segments):
            bad_base += 1
    if bad_up or bad_end or bad_base:
        return (f"{bad_up} roof triangle(s) not facing up, {bad_end} non-vertical gable-end triangle(s), "
                f"{bad_base} gable-end base edge(s) off the footprint")
    return None


class _Budget:
    def __init__(self, cap):
        self.left = cap

    def spend(self, n=1):
        self.left -= n
        if self.left < 0:
            raise LimitError("roof check: convex clipping work exceeds the cap")


def roof_coverage(roof, ftris, budget=None):
    """(footprint area, uncovered area, area of the roof outside the footprint, summed pairwise overlap)."""
    budget = budget or _Budget(CLIP_CAP)
    fb = [(f, _bbox(f)) for f in ftris]
    rb = [(r, _bbox(r)) for r in roof]
    total = sum(area2d(f) for f in ftris)
    gap = 0.0
    for f, fbox in fb:
        pieces = [f]
        for r, rbox in rb:
            if not _bbox_overlap(fbox, rbox):
                continue
            nxt = []
            for p in pieces:
                budget.spend()
                nxt.extend(subtract_convex(p, r) if _bbox_overlap(_bbox(p), rbox) else [p])
            pieces = nxt
            if not pieces:
                break
        gap += sum(area2d(p) for p in pieces)
    outside = 0.0
    for r, rbox in rb:
        inside = 0.0
        for f, fbox in fb:
            if _bbox_overlap(fbox, rbox):
                budget.spend()
                inside += abs(area2d(clip_convex(r, f)))
        outside += max(0.0, area2d(r) - inside)
    order = sorted(range(len(rb)), key=lambda i: rb[i][1][0])
    overlap, pairs = 0.0, 0
    for ii, i in enumerate(order):
        for j in order[ii + 1:]:
            if rb[j][1][0] > rb[i][1][2] + 1e-9:
                break
            if _bbox_overlap(rb[i][1], rb[j][1]):
                pairs += 1
                if pairs > PAIR_CAP:
                    raise LimitError("roof check: more than %d bbox-overlapping triangle pairs" % PAIR_CAP)
                overlap += abs(area2d(clip_convex(rb[i][0], rb[j][0])))
    return total, gap, outside, overlap


PLANAR_TOL = MM
SLOPE_ANGLE = 0.02      # rad: adjacent roof triangles tilted less than this apart belong to one slope


def plane_deviation(tris):
    """Largest distance of any vertex of ``tris`` (3D triangles) from the plane of the largest one."""
    best = max(tris, key=lambda t: sum(c * c for c in _cross3(*t)))
    n = _cross3(*best)
    ln = math.sqrt(sum(c * c for c in n))
    if ln == 0:
        return 0.0
    n = tuple(c / ln for c in n)
    o = best[0]
    return max(abs(sum(n[k] * (p[k] - o[k]) for k in range(3))) for t in tris for p in t)


def check_planar_faces(faces, tol=PLANAR_TOL):
    """Faces are lists of 3D triangles that must lie in one plane. -> {face index: deviation} of the failures
    (every triangle is planar by construction; a face of several triangles is not)."""
    bad = {}
    for i, f in enumerate(faces):
        f = [t for t in f if unit_normal(t) is not None]
        if f:
            d = plane_deviation(f)
            if d > tol:
                bad[i] = d
    return bad


def roof_slopes(tris):
    """Sloped roof triangles grouped into slopes: edge-adjacent triangles whose normals differ by less than
    SLOPE_ANGLE. A smoothly warped slope stays one group, so check_planar_faces reports it."""
    items = [(t, unit_normal(t)) for m, t in tris if m == ROOF]
    items = [(t, n) for t, n in items if n is not None and n[2] < 1.0 - 1e-9]
    key = lambda p: tuple(round(c / WELD_M) for c in p)
    by_edge = {}
    for i, (t, _) in enumerate(items):
        for k in range(3):
            by_edge.setdefault(frozenset((key(t[k]), key(t[(k + 1) % 3]))), []).append(i)
    seen, groups = set(), []
    for s in range(len(items)):
        if s in seen:
            continue
        seen.add(s)
        stack, grp = [s], []
        while stack:
            i = stack.pop()
            grp.append(items[i][0])
            t = items[i][0]
            for k in range(3):
                for j in by_edge[frozenset((key(t[k]), key(t[(k + 1) % 3])))]:
                    if j not in seen and sum(a * b for a, b in zip(items[i][1], items[j][1])) > math.cos(SLOPE_ANGLE):
                        seen.add(j)
                        stack.append(j)
        groups.append(grp)
    return groups


def skeleton_tiling(sk):
    """Independent tiling checks of a ``Skeleton`` (S3-SKELETON AC7) on its explicitly triangulated faces.
    -> (relative gap, relative overlap, relative area outside the footprint, lifted faces)."""
    roof, lifted = [], []
    for face in sk.faces:
        pts3 = [sk.nodes[k] for k in face]
        pts = [(p[0], p[1]) for p in pts3]
        tri_idx = triangulate(pts, list(range(len(pts))))
        roof += [_ccw([pts[a], pts[b], pts[c]]) for a, b, c in tri_idx]
        lifted.append([(pts3[a], pts3[b], pts3[c]) for a, b, c in tri_idx])
    total, gap, outside, overlap = roof_coverage(roof, footprint_triangles(sk.ring))
    return gap / total, overlap / total, outside / total, lifted


def check_building(tris, outer, holes, eave_z, top_z):
    """{check name: detail} of the failed checks of one building. ``eave_z``/``top_z`` are absolute map z."""
    fails = {}
    planar = check_planar_faces(roof_slopes(tris))
    if planar:
        fails["planar"] = f"{len(planar)} roof slope(s) not coplanar within {PLANAR_TOL * 1000:g} mm (max " \
                          f"{max(planar.values()) * 1000:.3g} mm)"
    segs = [s for r in [outer] + [list(h) for h in holes] for s in _segments(r)]
    for name, detail in (("closed", check_closed(tris)), ("above_eave", check_above_eave(tris, eave_z)),
                         ("ridge", check_ridge(tris, top_z)), ("normals", check_normals(tris, eave_z, segs))):
        if detail:
            fails[name] = detail
    roof = projected_roof(tris)
    total, gap, outside, overlap = roof_coverage(roof, footprint_triangles(outer, holes))
    lim = REL_TOL * total
    if gap > lim:
        fails["no_gap"] = f"uncovered footprint area {gap:.6g} m2 > {lim:.3g}"
    if overlap > lim:
        fails["no_overlap"] = f"overlapping roof area {overlap:.6g} m2 > {lim:.3g}"
    if outside > lim:
        fails["inside"] = f"{outside:.6g} m2 of the roof lies outside the footprint"
    return fails


# --- the tagged-shape signature (D61) ---------------------------------------------------------------------------

def _edge_overlap(e, s, tol=MM):
    """Length of the part of the 3D edge ``e`` (projected) that lies along footprint segment ``s``."""
    (a, b), (p, q) = s, e
    ln = math.hypot(b[0] - a[0], b[1] - a[1])
    if ln < tol or _dist_to_segment(p, a, b) > tol or _dist_to_segment(q, a, b) > tol:
        return 0.0
    ux, uy = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
    t1, t2 = sorted(((p[0] - a[0]) * ux + (p[1] - a[1]) * uy, (q[0] - a[0]) * ux + (q[1] - a[1]) * uy))
    return max(0.0, min(t2, ln) - max(t1, 0.0))


def _carried(segs, ends, roof_tris):
    """Footprint segments (longer than 1 mm) not covered by a gable end, that carry no sloped roof triangle."""
    sloped_edges = []
    for t in roof_tris:
        n = unit_normal(t)
        if n is not None and n[2] < 1.0 - 1e-6:
            sloped_edges.extend(((t[k][0], t[k][1]), (t[(k + 1) % 3][0], t[(k + 1) % 3][1])) for k in range(3))
    end_edges = [((t[0][0], t[0][1]), (t[1][0], t[1][1])) for t in ends]
    end_edges += [((t[1][0], t[1][1]), (t[2][0], t[2][1])) for t in ends]
    end_edges += [((t[2][0], t[2][1]), (t[0][0], t[0][1])) for t in ends]
    missing = []
    for s in segs:
        if math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]) <= MM:
            continue
        if any(_edge_overlap(e, s) > MM for e in end_edges):
            continue
        if not any(_edge_overlap(e, s) > MM for e in sloped_edges):
            missing.append(s)
    return missing


def _is_square(ring, tol=0.01):
    """A 4-vertex ring with equal sides and right angles (the only footprint whose hipped roof is a pyramid)."""
    if len(ring) != 4:
        return False
    sides = [(ring[(i + 1) % 4][0] - ring[i][0], ring[(i + 1) % 4][1] - ring[i][1]) for i in range(4)]
    ln = [math.hypot(*s) for s in sides]
    if max(ln) - min(ln) > tol * max(ln):
        return False
    return all(abs(sides[i][0] * sides[(i + 1) % 4][0] + sides[i][1] * sides[(i + 1) % 4][1]) <= tol * ln[0] ** 2
               for i in range(4))


def signature_problems(shape, tris, outer, eave_z, top_z):
    """Why the emitted geometry does not look like ``shape`` (an empty list if it does)."""
    segs = _segments(outer)
    roof_tris = [t for m, t in tris if m == ROOF]
    ends = [t for t in gable_end_triangles(tris, eave_z) if (unit_normal(t) or (0, 0, 1))[2] < UP_EPS]
    ends = [t for t in ends if _base_edge_on_footprint(t, segs)]
    top = [p for t in roof_tris for p in t if abs(p[2] - top_z) <= MM]
    problems = []
    if shape == "hipped":
        if len({(round(p[0] / MM), round(p[1] / MM)) for p in top}) == 1 and not _is_square(outer):
            problems.append("the roof ends in a single apex on a non-square footprint (pyramidal, not hipped)")
        if ends:
            problems.append(f"{len(ends)} gable-end triangle(s) on a hipped roof")
        if _carried(segs, [], roof_tris):
            problems.append("a footprint edge carries no sloped roof triangle")
    elif shape == "gabled":
        if len(ends) < 2:
            problems.append(f"{len(ends)} vertical gable-end triangle(s), need >= 2")
        if _carried(segs, ends, roof_tris):
            problems.append("a footprint edge outside the gable ends carries no sloped roof triangle")
    elif shape == "skillion":
        if not top:
            problems.append("no roof point reaches the top")
        normals = [n for n in (unit_normal(t) for t in roof_tris) if n is not None]
        if any(max(abs(a - b) for a, b in zip(n, normals[0])) > 1e-4 for n in normals):
            problems.append("the roof is not a single plane")
        zs = [p[2] for t in roof_tris for p in t]
        if not zs or max(zs) - min(zs) <= 0.1:
            problems.append("the roof does not slope")
    elif shape in ("pyramidal", "dome", "onion"):
        if len({(round(p[0] / MM), round(p[1] / MM)) for p in top}) != 1:
            problems.append("the roof does not end in a single apex")
    else:
        zs = [p[2] for t in roof_tris for p in t]
        if not zs or max(zs) - eave_z <= 0.1:
            problems.append("the roof does not rise above the eave")
    return problems


def built_as_tagged(shape, tris, outer, holes, eave_z, top_z):
    """The D61 metric for one building: the geometry checks pass and the signature of ``shape`` holds.
    -> (counted, {check: detail}, [signature problems])."""
    fails = check_building(tris, outer, holes, eave_z, top_z)
    sig = signature_problems(shape, tris, outer, eave_z, top_z)
    return (not fails and not sig), fails, sig


def load_expected(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
