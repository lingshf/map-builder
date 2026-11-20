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


def plane_deviation(tris):
    """Largest distance of any vertex of ``tris`` (3D triangles) from the plane of the largest one."""
    best = max(tris, key=lambda t: (round(sum(c * c for c in _cross3(*t)), 9),
                                    tuple(sorted(tuple(round(c, 6) for c in p) for p in t))))
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


def check_building(tris, outer, holes, eave_z, top_z, shape=None):
    """{check name: detail} of the failed checks of one building. ``eave_z``/``top_z`` are absolute map z.
    ``shape`` (the tagged shape) selects the slope model of the planarity check; without it there is none."""
    fails = {}
    planar = check_planar_faces(roof_slopes(tris, shape, outer, top_z, eave_z))
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


def _same(a, b):
    return math.dist(a, b) <= MM


def _distinct(points):
    out = []
    for p in points:
        if not any(_same(p, q) for q in out):
            out.append(p)
    return out


def _chain(tops):
    """The top points ordered along one straight line, or None if they are fewer than two or not collinear."""
    if len(tops) < 2:
        return None
    a = max(tops, key=lambda p: math.dist(tops[0], p))
    b = max(tops, key=lambda p: math.dist(a, p))
    if math.dist(a, b) <= MM or any(
            _dist_to_segment((p[0], p[1]), (a[0], a[1]), (b[0], b[1])) > MM for p in tops):
        return None
    return sorted(tops, key=lambda p: (p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1]))


def _ridge_problem(tops, roof_tris):
    """The ridge is a straight, connected chain of horizontal top edges (collinear vertices are merged into it)."""
    chain = _chain(tops)
    if chain is None:
        return f"no straight ridge line at the top height ({len(tops)} top point(s))"
    if math.dist(chain[0], chain[-1]) < 0.1:
        return "the ridge is shorter than 0.1 m"
    for a, b in zip(chain, chain[1:]):
        if not any(sum(_same(p, a) for p in t) and sum(_same(p, b) for p in t) for t in roof_tris):
            return "the top points are not joined by horizontal roof edges"
    return None

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


def ridge_slopes(tris, top_z):
    """Gabled slopes from topology alone: sloped roof triangles connected across shared edges, except the
    horizontal ridge edges at ``top_z``. No normal-angle cutoff decides membership."""
    items = [t for m, t in tris if m == ROOF and (unit_normal(t) or (0, 0, 1))[2] < 1.0 - 1e-6]
    key = lambda p: tuple(round(c / WELD_M) for c in p)
    by_edge = {}
    for i, t in enumerate(items):
        for k in range(3):
            a, b = t[k], t[(k + 1) % 3]
            if abs(a[2] - top_z) <= MM and abs(b[2] - top_z) <= MM:
                continue
            by_edge.setdefault(frozenset((key(a), key(b))), []).append(i)
    seen, groups = set(), []
    for s in range(len(items)):
        if s in seen:
            continue
        seen.add(s)
        stack, grp = [s], []
        while stack:
            i = stack.pop()
            grp.append(items[i])
            t = items[i]
            for k in range(3):
                for j in by_edge.get(frozenset((key(t[k]), key(t[(k + 1) % 3]))), []):
                    if j not in seen:
                        seen.add(j)
                        stack.append(j)
        groups.append(grp)
    return groups


def _sides(outer):
    """Footprint sides with collinear consecutive edges merged: one hipped/pyramidal slope each."""
    n = len(outer)
    corners = [outer[i] for i in range(n) if _dist_to_segment(outer[i], outer[i - 1], outer[(i + 1) % n]) > MM]
    return [(corners[i], corners[(i + 1) % len(corners)]) for i in range(len(corners))]


def edge_slopes(tris, outer, top_z, skip=()):
    """Hipped/pyramidal slopes by footprint side, independent of the triangle order. A side's seed plane is the
    plane of its largest eave triangle (the triangles with an edge on that side; one on several sides belongs
    to the lowest-numbered). Every other sloped triangle joins the side, among those whose eave triangles are
    connected to it across non-ridge edges, whose seed plane is nearest (largest vertex distance, ties to the
    lower side index). Triangles with no such side are singleton slopes. No angle cutoff, no first-reach rule.
    The sides in ``skip`` (the footprint sides of the gable ends of a gabled roof) have no slope of their own."""
    sides = _sides(outer)
    items = [t for m, t in tris if m == ROOF and (unit_normal(t) or (0, 0, 1))[2] < 1.0 - 1e-6]
    key = lambda p: tuple(round(c / WELD_M) for c in p)
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    first = {}
    for i, t in enumerate(items):
        for k in range(3):
            a, b = t[k], t[(k + 1) % 3]
            if abs(a[2] - top_z) > MM or abs(b[2] - top_z) > MM:
                j = first.setdefault(frozenset((key(a), key(b))), i)
                parent[find(i)] = find(j)
    eave_of = {}
    for i, t in enumerate(items):
        for s, seg in enumerate(sides):
            if s not in skip and any(_edge_overlap(((t[k][0], t[k][1]), (t[(k + 1) % 3][0], t[(k + 1) % 3][1])), seg) > MM
                   for k in range(3)):
                eave_of[i] = s
                break
    area = lambda t: sum(c * c for c in _cross3(*t))
    canon = lambda t: (round(area(t), 9), tuple(sorted(key(p) for p in t)))
    seed = {}
    for s in range(len(sides)):
        if s in skip:
            continue
        mine = [items[i] for i, v in eave_of.items() if v == s]
        if mine:
            seed[s] = unit_normal(max(mine, key=canon)), max(mine, key=canon)[0]
    comp_sides = {}
    for i, s in eave_of.items():
        comp_sides.setdefault(find(i), set()).add(s)

    def dev(t, s):
        n, o = seed[s]
        return max(abs(sum(n[c] * (p[c] - o[c]) for c in range(3))) for p in t)

    groups = {}
    for i, t in enumerate(items):
        if i in eave_of:
            s = eave_of[i]
        else:
            near = comp_sides.get(find(i), ())
            s = min(near, key=lambda c: (round(dev(t, c), 9), c)) if near else ("lone", i)
        groups.setdefault(s, []).append(t)
    return [groups[s] for s in sorted(groups, key=str)]


def _gable_sides(tris, outer, eave_z):
    """Indices of the footprint sides (:func:`_sides`) that carry a vertical gable-end triangle."""
    sides = _sides(outer)
    ends = [t for t in gable_end_triangles(tris, eave_z) if (unit_normal(t) or (0, 0, 1))[2] < UP_EPS]
    out = set()
    for t in ends:
        a, b, c = sorted(t, key=lambda p: p[2])
        base = ((a[0], a[1]), (b[0], b[1]))
        for s, seg in enumerate(sides):
            if _edge_overlap(base, seg) > MM:
                out.add(s)
    return out


def roof_slopes(tris, shape, outer, top_z, eave_z=None):
    """The slopes of a roof of the tagged ``shape``, from the expected roof topology (none for other shapes).
    A gabled roof on the eave ``eave_z`` has one slope per footprint side without a gable end; without
    ``eave_z`` it is a two-slope ridge roof."""
    if shape == "gabled":
        if eave_z is None:
            return ridge_slopes(tris, top_z)
        return edge_slopes(tris, outer, top_z, _gable_sides(tris, outer, eave_z))
    if shape in ("hipped", "pyramidal"):
        return edge_slopes(tris, outer, top_z)
    if shape == "skillion":
        return [[t for m, t in tris if m == ROOF]]
    return []


def _slope_topology_problems(shape, tris, outer, top_z, eave_z=None):
    expected = len(_sides(outer)) - (len(_gable_sides(tris, outer, eave_z)) if shape == "gabled" else 0)
    slopes = roof_slopes(tris, shape, outer, top_z, eave_z)
    problems = []
    if len(slopes) != expected:
        problems.append(f"{len(slopes)} roof slope(s), a {shape} roof has exactly {expected}")
    bad = check_planar_faces(slopes)
    if bad:
        problems.append(f"{len(bad)} roof slope(s) not coplanar within {PLANAR_TOL * 1000:g} mm")
    return problems

def _nodes(tris, outer, top_z):
    """Roof nodes read from the merged planar slopes, not from raw triangles: the vertices off the footprint where
    three or more slopes meet. Points that only subdivide a hip or ridge edge touch two slopes and are not nodes,
    so the result does not change when the surface is subdivided. -> (nodes, slopes)."""
    segs = _segments(outer)
    key = lambda p: tuple(round(c / WELD_M) for c in p)
    slopes = edge_slopes(tris, outer, top_z)
    touching = {}
    for g, grp in enumerate(slopes):
        for t in grp:
            for p in t:
                if not _on_boundary((p[0], p[1]), segs):
                    touching.setdefault(key(p), (p, set()))[1].add(g)
    return _distinct([p for p, gs in touching.values() if len(gs) >= 3]), slopes


def _hip_problems(tris, outer, top_z):
    """A hipped roof from the merged slopes alone: two or more nodes joined by ridge arcs. A single node is a
    pyramid, a hipped roof only when its footprint has an apex equidistant from every side (the straight
    skeleton is a point). The ridge may slope or be at several heights: only the slopes must be planar (checked
    by the caller)."""
    nodes, _ = _nodes(tris, outer, top_z)
    if len(nodes) >= 2:
        return []
    if len(nodes) != 1:
        return ["no roof node where three slopes meet"]
    apex = nodes[0]
    dist = [abs((b[0] - a[0]) * (apex[1] - a[1]) - (b[1] - a[1]) * (apex[0] - a[0])) / math.dist(a, b)
            for a, b in _sides(outer)]
    if max(dist) - min(dist) > max(MM, 1e-3 * max(dist)):
        return ["the roof ends in a single apex on a footprint whose skeleton is not a point (pyramidal, not hipped)"]
    return []

def _apexes_on_two_slopes(ends, slopes):
    """The highest vertex of every group of gable-end triangles (connected through shared vertices, so a
    subdivided end is one group) belongs to at least two merged slopes."""
    key = lambda p: tuple(round(c / WELD_M) for c in p)
    parent = {}

    def find(k):
        while parent.setdefault(k, k) != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for t in ends:
        for p in t[1:]:
            parent[find(key(p))] = find(key(t[0]))
    top = {}
    for t in ends:
        for p in t:
            g = find(key(p))
            if g not in top or p[2] > top[g][2]:
                top[g] = p
    on = [{key(p) for t in g for p in t} for g in slopes]
    return all(sum(key(p) in s_ for s_ in on) >= 2 for p in top.values())


def signature_problems(shape, tris, outer, eave_z, top_z):
    """Why the emitted geometry does not look like ``shape`` (an empty list if it does)."""
    segs = _segments(outer)
    roof_tris = [t for m, t in tris if m == ROOF]
    ends = [t for t in gable_end_triangles(tris, eave_z) if (unit_normal(t) or (0, 0, 1))[2] < UP_EPS]
    ends = [t for t in ends if _base_edge_on_footprint(t, segs)]
    top = [p for t in roof_tris for p in t if abs(p[2] - top_z) <= MM]
    problems = []
    tops = _distinct(top)
    if shape == "hipped":
        problems += _hip_problems(tris, outer, top_z)
        if ends:
            problems.append(f"{len(ends)} gable-end triangle(s) on a hipped roof")
        if _carried(segs, [], roof_tris):
            problems.append("a footprint edge carries no sloped roof triangle")
        problems += _slope_topology_problems(shape, tris, outer, top_z)
    elif shape == "gabled":
        end_sides = _gable_sides([(FACADE, t) for t in ends], outer, eave_z)
        if len(end_sides) < 2:
            problems.append(f"{len(end_sides)} distinct gable end(s) on the footprint sides, need >= 2")
        slopes = roof_slopes(tris, shape, outer, top_z, eave_z)
        if not _apexes_on_two_slopes(ends, slopes):
            problems.append("a gable end does not reach the ridge where two slopes meet")
        if _carried(segs, ends, roof_tris):
            problems.append("a footprint edge outside the gable ends carries no sloped roof triangle")
        problems += _slope_topology_problems(shape, tris, outer, top_z, eave_z)
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
        if len(tops) != 1:
            problems.append("the roof does not end in a single apex")
        if shape == "pyramidal" and ends:
            problems.append(f"{len(ends)} gable-end triangle(s) on a pyramidal roof")
        if shape == "pyramidal" and len(tops) == 1:
            nodes, slopes = _nodes(tris, outer, top_z)
            if len(nodes) != 1 or any(not any(_same(p, tops[0]) for t in g for p in t) for g in slopes):
                problems.append("a slope does not reach the apex (a ridge roof, not a pyramid)")
        if shape == "pyramidal" and _carried(segs, [], roof_tris):
            problems.append("a footprint edge carries no sloped roof triangle")
        if shape == "pyramidal":
            problems += _slope_topology_problems(shape, tris, outer, top_z)
    else:
        zs = [p[2] for t in roof_tris for p in t]
        if not zs or max(zs) - eave_z <= 0.1:
            problems.append("the roof does not rise above the eave")
    return problems


def built_as_tagged(shape, tris, outer, holes, eave_z, top_z):
    """The D61 metric for one building: the geometry checks pass and the signature of ``shape`` holds.
    -> (counted, {check: detail}, [signature problems])."""
    fails = check_building(tris, outer, holes, eave_z, top_z, shape)
    sig = signature_problems(shape, tris, outer, eave_z, top_z)
    return (not fails and not sig), fails, sig


def load_expected(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
