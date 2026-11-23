# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S4-WATER-SURFACE probe and query replays (spec section 7) of a BASE and a HEAD package.

  py -3.12 tools/water_replay.py BASE.mbmap HEAD.mbmap [--seed 20260101] [--rays 2000] [--capsules 100]
        [--allow-drop ID=REASON ...] [--allow-new ID=REASON ...] [--allow-blocked ID=REASON ...] [--no-csharp]

(a) Fixed-query replay. The queries are frozen on BASE (its D98 ray and capsule grid, the centroid rays of its
    degenerate triangles, its passage probe paths) plus one downward ray per water object of HEAD at the pole of
    inaccessibility of its triangles. Rays are compared by their nearest hit (hit/miss, class, object and distance
    to 1 mm) on both packages, in Python (query.ray_cast) and in the C# reader (``--ray-work``); capsules by their
    hit sets (``--probe-work``). Python and C# must agree on every query. Every BASE/HEAD difference is classified
    individually and printed (``--show N``, all in ``--diffs FILE``); each label must match the object, class and
    direction actually hit: new water hit (a water object new on HEAD over a terrain or missed ray), bed moved
    (terrain on both sides within the padded water box, or carved below a deck), road lowered (the same road,
    near water, hit farther down because it is draped on the carved bed), deck raised (same bridge, reported
    in water_decks_raised, lowered by at most the reported rise). Anything else is ``unlisted`` and fails.
(b) Regenerated-passage replay. The sets are compared exactly: every dropped, new or newly blocked id must be
    listed, and every listed id must really be one. Each listed reason must be non-empty and quote the generator's
    own report row (``reason`` or ``blocker``, a blocker being an object of HEAD). Each surviving HEAD id is
    validated passable on its regenerated path, read from HEAD's manifest, in Python and in C#.

Both files are read in full (zip integrity, entry sizes) before anything is compared. Exit 0 only when every group
ran and nothing failed; 1 on any failure; 2 when C# did not run (``--no-csharp`` or no reader), never 0.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from collections.abc import Sequence
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from col_degen_replay import DOWN, build_probes, csharp, names  # noqa: E402
from map_builder.core.collision import Collision, read_collision  # noqa: E402
from map_builder.core.bridges import capsule_polygon  # noqa: E402
from map_builder.core.query import capsule_hits, ray_cast  # noqa: E402
from map_builder.core.water import AREA_EPS, _area2, _clip_poly_tri  # noqa: E402


class Package:
    def __init__(self, path: str) -> None:
        if not os.path.isfile(path):
            raise SystemExit(f"no such package: {path}")
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad is not None:
                raise SystemExit(f"{path}: corrupt zip entry {bad}")
            data = {}
            for info in z.infolist():
                blob = z.read(info.filename)
                if len(blob) != info.file_size:
                    raise SystemExit(f"{path}: truncated entry {info.filename}")
                data[info.filename] = blob
        self.path = path
        self.mbcol = data["collision/map.mbcol"]
        self.manifest = json.loads(data["manifest.json"])
        self.report = json.loads(data["report.json"])
        self.col: Collision = read_collision(self.mbcol)
        self.probes: list[dict[str, Any]] = list(self.manifest.get("passage_probes") or [])
        self.names = {e["name"] for e in self.col.objects}
        self.mbids = {str(o.get("mb_id")) for o in self.manifest.get("objects") or []}
        name_of = {str(o.get("mb_id")): o.get("name") for o in self.manifest.get("objects") or []
                   if o.get("class") == "bridge"}
        self.raised: dict[str, float] = {}
        for r in self.report.get("water_decks_raised") or []:
            nm = name_of.get(str(r.get("id")))
            if nm in self.names and isinstance(r.get("raised_m"), (int, float)):
                self.raised[nm] = float(r["raised_m"])


def pole(tris: list[tuple[Any, Any, Any]]) -> tuple[float, float]:
    """The triangle centroid farthest from the boundary edges (edges used by one triangle): a deterministic
    pole of inaccessibility of a triangulated surface."""
    edges: Counter = Counter()
    for t in tris:
        for k in range(3):
            a, b = t[k], t[(k + 1) % 3]
            edges[tuple(sorted(((a[0], a[1]), (b[0], b[1]))))] += 1
    boundary = [e for e, n in edges.items() if n == 1]

    def dist(x: float, y: float) -> float:
        best = math.inf
        for (ax, ay), (bx, by) in boundary:
            dx, dy = bx - ax, by - ay
            ll = dx * dx + dy * dy
            u = 0.0 if ll == 0 else min(1.0, max(0.0, ((x - ax) * dx + (y - ay) * dy) / ll))
            best = min(best, math.hypot(x - ax - u * dx, y - ay - u * dy))
        return best
    cands = [((t[0][0] + t[1][0] + t[2][0]) / 3, (t[0][1] + t[1][1] + t[2][1]) / 3) for t in tris]
    return max(cands, key=lambda c: (round(dist(*c), 9), -c[0], -c[1]))


def water_rays(head: Package, top: float) -> list[tuple[float, float, float]]:
    out = []
    for entry in head.col.objects:
        if entry["class"] == "water":
            x, y = pole(head.col.object_triangles(entry))
            out.append((x, y, top))
    return out


DIST_TOL_M = 1e-3     # spec section 7(a): hit distances are compared to 1 mm
BLEND_PAD_M = 65.0    # water bbox padding inside which the terrain bed may have moved (carve + blend, 2 cells)
EDGE_TIE_M = 2e-3     # a ray this close to a road ribbon's edge may report either of two abutting ribbons

Hit = tuple[float, str, str]   # (distance, object name, class)


class Context:
    """What the HEAD package says about its own changes: the water objects new on HEAD (with their plan boxes) and
    the decks it reports as raised (object name -> raised metres)."""

    def __init__(self, base_names: set[str], head: Any, water_tris: list[Any] | None = None,
                 bridges: tuple[dict[str, Any], dict[str, Any]] | None = None) -> None:
        self.new_water = {e["name"]: e["aabb"] for e in head.col.objects
                          if e["class"] == "water" and e["name"] not in base_names}
        self.water_boxes = [e["aabb"] for e in head.col.objects if e["class"] == "water"]
        self.raised = dict(head.raised)
        self.present = set(head.names)
        self.base_bridge, self.head_bridge = bridges if bridges is not None else ({}, {})
        self.water_tris = water_tris if water_tris is not None else [
            [(p[0], p[1]) for p in t] for e in head.col.objects if e["class"] == "water"
            for t in head.col.object_triangles(e)]

    def bridge_ok(self, name: str) -> bool:
        """The bridge's collision geometry changed only as the generator reports: same plan footprint (vertex bbox
        within 1 mm) and top z unchanged, or raised by between 0 and its reported ``raised_m`` (within 1 mm).
        Underside and pier depth may change (piers reach the carved bed). Unknown on either side: not ok."""
        b, h = self.base_bridge.get(name), self.head_bridge.get(name)
        if b is None or h is None:
            return False
        if any(abs(x - y) > DIST_TOL_M for x, y in zip(b[0], h[0])):
            return False
        return -DIST_TOL_M <= h[1] - b[1] <= self.raised.get(name, 0.0) + DIST_TOL_M

    def over_water(self, path: list[Any], radius: float) -> bool:
        """True when the capsule of ``path`` overlaps a water triangle of HEAD in plan (bbox prefilter first)."""
        for a, b in zip(path, path[1:]):
            cap = capsule_polygon((a[0], a[1]), (b[0], b[1]), radius)
            lo_x, hi_x = min(q[0] for q in cap), max(q[0] for q in cap)
            lo_y, hi_y = min(q[1] for q in cap), max(q[1] for q in cap)
            for t in self.water_tris:
                if (max(q[0] for q in t) < lo_x or min(q[0] for q in t) > hi_x
                        or max(q[1] for q in t) < lo_y or min(q[1] for q in t) > hi_y):
                    continue
                clip = _clip_poly_tri(cap, t)
                if len(clip) >= 3 and abs(_area2(clip)) >= AREA_EPS:
                    return True
        return False

    def near_water(self, x: float, y: float) -> bool:
        return _in_padded_box(self.new_water.values(), x, y)

    def near_any_water(self, x: float, y: float) -> bool:
        """Within the carve + blend padding of any water body of HEAD (new or already on BASE)."""
        return _in_padded_box(self.water_boxes, x, y)


def _in_padded_box(boxes: Any, x: float, y: float) -> bool:
    return any(b[0] - BLEND_PAD_M <= x <= b[3] + BLEND_PAD_M and b[1] - BLEND_PAD_M <= y <= b[4] + BLEND_PAD_M
               for b in boxes)


def bridge_geometry(col: Collision) -> dict[str, Any]:
    """Bridge object name -> ((xmin, ymin, xmax, ymax), top z) of its collision vertices."""
    out: dict[str, Any] = {}
    for e in col.objects:
        if e["class"] != "bridge":
            continue
        pts = [p for t in col.object_triangles(e) for p in t]
        if pts:
            out[e["name"]] = ((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts),
                               max(p[1] for p in pts)), max(p[2] for p in pts))
    return out


def py_hit(col: Collision, o: tuple[float, float, float], dist: float) -> Hit | None:
    h = ray_cast(col, o, DOWN, dist)
    if h is None:
        return None
    e = col.objects[h.object]
    return (h.t, e["name"], e["class"])


def py_hits(col: Collision, o: tuple[float, float, float], dist: float) -> list[Hit]:
    """Every downward hit of the ray in order, nearest first: the ray is restarted just below each hit."""
    out: list[Hit] = []
    z, travelled = o[2], 0.0
    while len(out) < 64:
        h = ray_cast(col, (o[0], o[1], z), DOWN, dist - travelled)
        if h is None:
            break
        e = col.objects[h.object]
        out.append((travelled + h.t, e["name"], e["class"]))
        z -= h.t + 1e-6
        travelled += h.t + 1e-6
    return out


def csharp_rays(col_bytes: bytes, rays: list[tuple[float, float, float]], dist: float, work: str) -> list[Hit | None]:
    """Nearest downward hits from the C# reader (``--ray-work``): (distance, object index as a string, class)."""
    spec = importlib.util.spec_from_file_location("csharp_build", os.path.join(os.path.dirname(HERE), "tests",
                                                                               "csharp_build.py"))
    assert spec and spec.loader
    cb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cb)
    mbcol, pj = os.path.join(work, "r.mbcol"), os.path.join(work, "r.json")
    with open(mbcol, "wb") as f:
        f.write(col_bytes)
    with open(pj, "w") as f:
        json.dump([{"o": list(o), "dist": dist} for o in rays], f)
    run = subprocess.run([*cb.reader_command(), "--ray-work", mbcol, pj], capture_output=True, text=True)
    if run.returncode:
        raise SystemExit(run.stdout + run.stderr)
    out: list[Hit | None] = []
    for line in run.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "ray":
            if parts[2] == "miss":
                out.append(None)
            else:
                kv = dict(p.split("=", 1) for p in parts[2:])
                out.append((float(kv["t"]), kv["object"], kv["class"]))
    if len(out) != len(rays):
        raise SystemExit(f"C# reader returned {len(out)} ray results for {len(rays)} rays")
    return out


def ray_disagreement(py_h: Hit | None, cs: Hit | None, col: Collision) -> str:
    """Empty when the C# nearest hit equals the Python one in hit/miss, distance (1 mm), class and object. Two
    coincident surfaces of one class (overlapping roads) tie within rounding, so their names may swap."""
    if py_h is None and cs is None:
        return ""
    if py_h is None or cs is None:
        return f"python {py_h}, C# {cs}"
    cs_name = col.objects[int(cs[1])]["name"]
    if abs(py_h[0] - cs[0]) > DIST_TOL_M or py_h[2] != cs[2] or (py_h[1] != cs_name and cs[2] != "road"):
        return f"python {py_h}, C# {(cs[0], cs_name, cs[2])}"
    return ""


def _moved_down(name: str, cls_: str, t: float, h_hits: list[Hit]) -> bool:
    """HEAD hits the same object farther down on this ray (the carve lowered terrain, or a road draped on it)."""
    return any(hn == name and hc == cls_ and ht > t + DIST_TOL_M for ht, hn, hc in h_hits)



def edge_tied_roads(col: Collision, o: tuple[float, float, float], dist: float, on_ray: list[Hit]) -> list[Hit]:
    """Road hits within EDGE_TIE_M of the ray that the ray itself does not report: two abutting road ribbons
    share an edge, and a ray exactly on it reports only one of them."""
    known = {h[1] for h in on_ray}
    tied: list[Hit] = []
    for dx, dy in ((EDGE_TIE_M, 0.0), (-EDGE_TIE_M, 0.0), (0.0, EDGE_TIE_M), (0.0, -EDGE_TIE_M)):
        tied += [h for h in py_hits(col, (o[0] + dx, o[1] + dy, o[2]), dist) if h[2] == "road" and h[1] not in known]
    return tied


def ray_label(b_hits: list[Hit], h_hits: list[Hit], xy: tuple[float, float], ctx: Context,
              edge_tied: Sequence[Hit] = ()) -> str | None:
    """None when the nearest hits are equivalent, else the change-set label, or ``unlisted``. ``b_hits``/``h_hits``
    are every hit of the ray, nearest first. A difference is accepted only when each BASE object nearer than the
    new nearest hit is explained: terrain near new water that HEAD hits again farther down (the bed moved), or
    nothing else. The new nearest hit must itself be a new water body, an object the base ray also hit, or
    terrain. A deck raise needs the same reported bridge on both sides, near water, lowered by at most the raise."""
    b = b_hits[0] if b_hits else None
    h = h_hits[0] if h_hits else None
    if b is None and h is None:
        return None
    if b is not None and h is not None and b[1] == h[1] and b[2] == h[2] and abs(b[0] - h[0]) <= DIST_TOL_M:
        return None
    if h is None:
        return "unlisted"
    nearer = [x for x in b_hits if x[0] < h[0] - DIST_TOL_M]
    for _t, name, cls_ in [h, *nearer] + ([b] if b else []):
        if cls_ == "bridge" and not ctx.bridge_ok(name):
            return "unlisted"     # the bridge moved sideways or by more than its reported raise
    if b is not None and b[1] == h[1] and b[2] == h[2] == "bridge":
        raise_m = ctx.raised.get(h[1], 0.0)
        if raise_m > 0 and ctx.near_water(*xy) and 0 < b[0] - h[0] <= raise_m + DIST_TOL_M:
            return "deck raised"
        return "unlisted"
    if b is not None and b[2] == h[2] == "road":
        # The head winner must itself be a road already on the base ray that moved down, and the nearest hit
        # must not rise; a road that was not on the base ray is an unexplained replacement.
        base_roads = [x for x in [*b_hits, *edge_tied] if x[2] == "road"]
        winner_was_on_base_ray = any(n == h[1] and h[0] > t + DIST_TOL_M for t, n, _c in base_roads)
        lowered = winner_was_on_base_ray and h[0] >= b[0] - DIST_TOL_M
        return "road lowered" if lowered and ctx.near_any_water(*xy) else "unlisted"
    label = None
    for t, name, cls_ in nearer:
        if cls_ == "road" and h[2] == "water" and _moved_down(name, cls_, t, h_hits):
            label = "road lowered"    # a road that hovered over water now follows the carved bed below it
        elif cls_ == "terrain" and ctx.near_water(*xy) and _moved_down(name, cls_, t, h_hits):
            label = "bed moved"
        else:
            return "unlisted"
    base_names = {x[1] for x in b_hits}
    if h[2] == "water" and h[1] in ctx.new_water:
        return "new water hit"
    if h[2] == "terrain" or h[1] in base_names:
        return label or "unlisted"
    return "unlisted"


def capsule_labels(b: list[tuple[str, str]], h: list[tuple[str, str]], path: list[Any], radius: float,
                   ctx: Context) -> list[str]:
    """One label per object that entered or left the capsule's hit set. Only a water object new on HEAD may
    enter; only terrain near a new water body (bed moved) or a bridge that HEAD reports as raised, still has in
    its collision and whose capsule really overlaps HEAD water may leave. Piers and building walls that extend
    keep their object names, so they do not change a hit set."""
    xy = (path[0][0], path[0][1])
    out = []
    for name, cls_ in sorted(set(h) - set(b)):
        out.append("new water hit" if cls_ == "water" and name in ctx.new_water
                   and not any(c == "bridge" and not ctx.bridge_ok(n) for n, c in set(b) | set(h)) else "unlisted")
    for name, cls_ in sorted(set(b) - set(h)):
        if cls_ == "bridge" and not ctx.bridge_ok(name):
            out.append("unlisted")
        elif cls_ == "terrain" and ctx.near_water(*xy):
            out.append("bed moved")
        elif (cls_ == "bridge" and ctx.raised.get(name, 0.0) > 0 and name in ctx.present
              and ctx.over_water(path, radius)):
            out.append("deck raised")
        else:
            out.append("unlisted")
    return out


def pairs(spec: list[str]) -> dict[str, str]:
    out = {}
    for s in spec:
        k, _, v = s.partition("=")
        if not v:
            raise SystemExit(f"expected ID=REASON, got {s!r}")
        out[k] = v
    return out


def d21_backing(row: dict[str, Any] | None, head: Any) -> tuple[str | None, str]:
    """The generator's own D21 text of a report row (``reason`` of a dropped row, ``blocker`` of a blocked row) and
    a problem string. A blocker must name an object of HEAD (collision name or mb_id); an empty row has no backing."""
    if not row:
        return None, "HEAD's report has no row for it"
    text = row.get("reason") or row.get("blocker")
    if not isinstance(text, str) or not text.strip():
        return None, "HEAD's report row has no non-empty reason or blocker"
    if "blocker" in row and text not in head.names and text not in head.mbids:
        return None, f"blocker {text!r} is not an object of HEAD"
    return text, ""


def passage_check(base: Any, head: Any, drop: dict[str, str], new: dict[str, str],
                  blocked: dict[str, str]) -> list[str]:
    """Exact set differences, each listed id backed by HEAD's own report and quoting the generator's text."""
    problems: list[str] = []
    b = {str(p["id"]) for p in base.probes}
    h = {str(p["id"]) for p in head.probes}
    rows = {}
    for key in ("passage_probes_dropped", "passage_probes_blocked"):
        for e in head.report.get(key) or []:
            rows.setdefault(str(e.get("id")), e)
    base_blocked = {str(e.get("id")) for e in base.report.get("passage_probes_blocked") or []}
    head_blocked = {str(e.get("id")) for e in head.report.get("passage_probes_blocked") or []}

    def check(kind: str, actual: set[str], listed: dict[str, str], backed: bool) -> None:
        for pid in sorted(actual - set(listed)):
            problems.append(f"passage {pid} is {kind} on HEAD and not listed")
        for pid in sorted(set(listed) - actual):
            problems.append(f"passage {pid} is listed as {kind} but is not {kind} on HEAD")
        for pid in sorted(actual & set(listed)):
            if not listed[pid].strip():
                problems.append(f"passage {pid} is listed as {kind} with an empty reason")
            elif backed:
                text, why = d21_backing(rows.get(pid), head)
                if text is None:
                    problems.append(f"passage {pid} is listed as {kind} but {why}")
                elif text.lower() not in listed[pid].lower():
                    problems.append(f"passage {pid}: listed reason {listed[pid]!r} does not quote HEAD's D21 text {text!r}")

    check("dropped", b - h, drop, True)
    check("new", h - b, new, True)
    check("newly blocked", head_blocked - base_blocked, blocked, True)
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base")
    ap.add_argument("head")
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--rays", type=int, default=2000)
    ap.add_argument("--capsules", type=int, default=100)
    ap.add_argument("--allow-drop", action="append", default=[])
    ap.add_argument("--allow-new", action="append", default=[])
    ap.add_argument("--allow-blocked", action="append", default=[])
    ap.add_argument("--no-csharp", action="store_true")
    ap.add_argument("--diffs", help="write every classified difference (query, location, base/head hit, label) as JSON")
    ap.add_argument("--show", type=int, default=12, help="print this many classified differences individually")
    a = ap.parse_args()
    base, head = Package(a.base), Package(a.head)
    fails: list[str] = []

    fails += passage_check(base, head, pairs(a.allow_drop), pairs(a.allow_new), pairs(a.allow_blocked))
    rays, dist, caps, ncent = build_probes(base.col, a.rays, a.capsules, a.seed)
    top = rays[0][2] if rays else max(v[2] for v in base.col.vertices) + 10.0
    wrays = water_rays(head, top)
    all_rays = rays + wrays
    passages_base = [(p["path_map"], float(p["radius_m"])) for p in base.probes]
    queries: list[tuple[list, float]] = caps + passages_base
    head_passages = [(p["path_map"], float(p["radius_m"])) for p in head.probes]
    ctx = Context(base.names, head, bridges=(bridge_geometry(base.col), bridge_geometry(head.col)))

    py = {}
    for key, pkg in (("base", base), ("head", head)):
        py[key] = [names(pkg.col, capsule_hits(pkg.col, path, r)) for path, r in queries]   # type: ignore[arg-type]
    py_rays = {key: [py_hit(pkg.col, o, dist) for o in all_rays] for key, pkg in (("base", base), ("head", head))}
    py_head_passage = [capsule_hits(head.col, p, r) for p, r in head_passages]   # type: ignore[arg-type]
    fails += [f"passage {p['id']} not clear on HEAD (python)" for p, hit in zip(head.probes, py_head_passage) if hit]
    for k, (o, hh) in enumerate(zip(wrays, py_rays["head"][len(rays):])):
        if hh is None or hh[2] != "water":
            fails.append(f"water ray {k} at ({o[0]:.3f}, {o[1]:.3f}) does not hit water on HEAD: {hh}")

    labels: Counter = Counter()
    diffs: list[dict[str, Any]] = []

    def record(kind: str, i: int, xy: tuple[float, float], bv: Any, hv: Any, lab: str) -> None:
        labels[lab] += 1
        diffs.append({"query": kind, "index": i, "xy": [round(xy[0], 3), round(xy[1], 3)], "base": bv, "head": hv,
                      "label": lab})

    for i, o in enumerate(all_rays):
        bh, hh = py_rays["base"][i], py_rays["head"][i]
        if (bh is None and hh is None) or (bh and hh and bh[1] == hh[1] and bh[2] == hh[2]
                                           and abs(bh[0] - hh[0]) <= DIST_TOL_M):
            continue
        base_hits = py_hits(base.col, o, dist)
        lab = ray_label(base_hits, py_hits(head.col, o, dist), (o[0], o[1]), ctx,
                        edge_tied_roads(base.col, o, dist, base_hits))
        if lab:
            record("ray", i, (o[0], o[1]), bh, hh, lab)
    for i, (path, qr) in enumerate(queries):
        kind = "capsule" if i < len(caps) else "base passage"
        for lab in capsule_labels(py["base"][i], py["head"][i], path, qr, ctx):
            record(kind, i, (path[0][0], path[0][1]), py["base"][i], py["head"][i], lab)
    bad = [d for d in diffs if d["label"] == "unlisted"]
    fails += [f"unlisted difference: {d}" for d in bad[:20]]
    if a.diffs:
        with open(a.diffs, "w") as fh:
            json.dump(diffs, fh, indent=1)

    summary = (f"seed {a.seed} | centroid rays {ncent} + grid rays {len(rays) - ncent} + water rays {len(wrays)} | "
               f"capsules {len(caps)} | base passages {len(passages_base)} | head passages {len(head_passages)} | "
               f"change set {dict(labels)}")
    cs_ran = False
    if not a.no_csharp:
        with tempfile.TemporaryDirectory() as w1, tempfile.TemporaryDirectory() as w2:
            cb, ch = csharp(base.mbcol, queries, w1), csharp(head.mbcol, queries, w2)
            cs_head_passage = csharp(head.mbcol, head_passages, w2) if head_passages else []
            rb, rh = csharp_rays(base.mbcol, all_rays, dist, w1), csharp_rays(head.mbcol, all_rays, dist, w2)
        cs_ran = True
        for key, got, pkg in (("base", cb, base), ("head", ch, head)):
            for i, idx in enumerate(got):
                if names(pkg.col, idx) != py[key][i]:
                    fails.append(f"C# and Python disagree on {key} query {i}")
        for key, got, pkg in (("base", rb, base), ("head", rh, head)):
            for i, cs in enumerate(got):
                msg = ray_disagreement(py_rays[key][i], cs, pkg.col)
                if msg:
                    fails.append(f"C# and Python disagree on {key} ray {i}: {msg}")
        fails += [f"passage {p['id']} not clear on HEAD (C#)" for p, hit in zip(head.probes, cs_head_passage) if hit]
    for d in diffs[:a.show]:
        print(f"  diff {d['label']}: {d['query']} {d['index']} at {d['xy']} base {d['base']} head {d['head']}")
    if fails:
        print(f"FAIL {summary}")
        for f in fails[:50]:
            print("  " + f)
        return 1
    if not cs_ran:
        print(f"{summary} | python only, C# SKIPPED")
        return 2
    print(f"OK {summary} | Python and C# agree on every query (ray distance to 1 mm, class and object)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
