# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S4-WATER-SURFACE probe and query replays (spec section 7) of a BASE and a HEAD package.

  py -3.12 tools/water_replay.py BASE.mbmap HEAD.mbmap [--seed 20260101] [--rays 2000] [--capsules 100]
        [--allow-drop ID=REASON ...] [--allow-new ID=REASON ...] [--allow-blocked ID=REASON ...] [--no-csharp]

(a) Fixed-query replay. The queries are frozen on BASE (its D98 ray and capsule grid, the centroid rays of its
    degenerate triangles, its passage probe paths) plus one downward ray per water object of HEAD at the pole of
    inaccessibility of its triangles. They run on both packages in Python and in the C# reader (a ray is a
    radius-0 capsule along the ray segment there). Python and C# must agree on every query; every difference
    between BASE and HEAD must fall in a classified change set: new water hit, bed moved, deck raised, pier
    extended, building wall extended. Anything else fails.
(b) Regenerated-passage replay. Every BASE passage id must exist on HEAD unless it is listed with --allow-drop and
    explained by HEAD's own report.json; a listed drop that is present fails; new and newly blocked ids must be
    listed too. Each surviving HEAD id is validated passable on its regenerated path, read from HEAD's manifest,
    in Python and in C#.

Both files are read in full (zip integrity, entry sizes) before anything is compared. Exit 0 only when every group
ran and nothing failed; 1 on any failure; 2 when C# did not run (``--no-csharp`` or no reader), never 0.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import zipfile
from collections import Counter
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from col_degen_replay import DOWN, T_TOL, build_probes, csharp, names, py_ray  # noqa: E402
from map_builder.core.collision import Collision, read_collision  # noqa: E402
from map_builder.core.query import capsule_hits  # noqa: E402


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


def ray_label(b: tuple[float, str] | None, h: tuple[float, str] | None) -> str | None:
    """None when equivalent, else the change-set label, or ``unlisted``."""
    if (b is None) == (h is None) and (b is None or (abs(b[0] - h[0]) <= T_TOL and b[1] == h[1])):  # type: ignore[index]
        return None
    if h is not None and h[1] == "water" and (b is None or b[1] != "water"):
        return "new water hit"
    if b is not None and h is not None:
        if b[1] == "terrain" and h[1] != "water" and h[0] > b[0]:
            return "bed moved"
        if b[1] == h[1] == "bridge" and h[0] < b[0]:
            return "deck raised"
    return "unlisted"


def capsule_labels(b: list[tuple[str, str]], h: list[tuple[str, str]]) -> list[str]:
    out = []
    for cls_, added in [(c, True) for _, c in set(h) - set(b)] + [(c, False) for _, c in set(b) - set(h)]:
        if cls_ == "water" and added:
            out.append("new water hit")
        elif cls_ == "terrain":
            out.append("bed moved")
        elif cls_ == "bridge":
            out.append("pier extended" if added else "deck raised")
        elif cls_ == "building" and added:
            out.append("building wall extended")
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


def passage_check(base: Package, head: Package, drop: dict[str, str], new: dict[str, str],
                  blocked: dict[str, str]) -> list[str]:
    problems: list[str] = []
    b = {str(p["id"]) for p in base.probes}
    h = {str(p["id"]) for p in head.probes}
    explained = {str(e.get("id")): e for key in ("passage_probes_dropped", "passage_probes_blocked")
                 for e in head.report.get(key) or []}
    for pid in sorted(b - h):
        if pid not in drop:
            problems.append(f"passage {pid} missing from HEAD and not listed")
        elif pid not in explained:
            problems.append(f"passage {pid} is listed as dropped but HEAD's report gives no D21 reason")
    for pid in sorted(set(drop) & h):
        problems.append(f"passage {pid} is listed as dropped but present on HEAD")
    for pid in sorted(h - b):
        if pid not in new:
            problems.append(f"passage {pid} is new on HEAD and not listed")
    for pid in sorted(set(new) - h):
        problems.append(f"passage {pid} is listed as new but absent from HEAD")
    base_blocked = {str(e.get("id")) for e in base.report.get("passage_probes_blocked") or []}
    head_blocked = {str(e.get("id")) for e in head.report.get("passage_probes_blocked") or []}
    for pid in sorted(head_blocked - base_blocked):
        if pid not in blocked:
            problems.append(f"passage {pid} is newly blocked on HEAD and not listed")
    for pid in sorted(set(blocked) - head_blocked):
        problems.append(f"passage {pid} is listed as blocked but is not blocked on HEAD")
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
    a = ap.parse_args()
    base, head = Package(a.base), Package(a.head)
    fails: list[str] = []

    fails += passage_check(base, head, pairs(a.allow_drop), pairs(a.allow_new), pairs(a.allow_blocked))
    rays, dist, caps, ncent = build_probes(base.col, a.rays, a.capsules, a.seed)
    top = rays[0][2] if rays else max(v[2] for v in base.col.vertices) + 10.0
    wrays = water_rays(head, top)
    all_rays = rays + wrays
    passages_base = [(p["path_map"], float(p["radius_m"])) for p in base.probes]
    queries: list[tuple[list, float]] = [([o, (o[0], o[1], o[2] - dist)], 0.0) for o in all_rays] + caps \
        + passages_base
    head_passages = [(p["path_map"], float(p["radius_m"])) for p in head.probes]

    py = {}
    for key, pkg in (("base", base), ("head", head)):
        py[key] = [names(pkg.col, capsule_hits(pkg.col, path, r)) for path, r in queries]   # type: ignore[arg-type]
    py_head_passage = [capsule_hits(head.col, p, r) for p, r in head_passages]   # type: ignore[arg-type]
    fails += [f"passage {p['id']} not clear on HEAD (python)" for p, hit in zip(head.probes, py_head_passage) if hit]

    labels: Counter = Counter()
    unlisted: list[str] = []
    for i, o in enumerate(all_rays):
        lab = ray_label(py_ray(base.col, o, dist), py_ray(head.col, o, dist))
        if lab:
            labels[lab] += 1
            if lab == "unlisted":
                unlisted.append(f"ray {o}")
    for i in range(len(all_rays), len(queries)):
        kind = "capsule" if i < len(all_rays) + len(caps) else "base passage"
        for lab in capsule_labels(py["base"][i], py["head"][i]):
            labels[lab] += 1
            if lab == "unlisted":
                unlisted.append(f"{kind} {i}")
    fails += [f"unlisted difference: {u}" for u in unlisted[:20]]

    summary = (f"seed {a.seed} | centroid rays {ncent} + grid rays {len(rays) - ncent} + water rays {len(wrays)} | "
               f"capsules {len(caps)} | base passages {len(passages_base)} | head passages {len(head_passages)} | "
               f"change set {dict(labels)}")
    cs_ran = False
    if not a.no_csharp:
        with tempfile.TemporaryDirectory() as w1, tempfile.TemporaryDirectory() as w2:
            cb, ch = csharp(base.mbcol, queries, w1), csharp(head.mbcol, queries, w2)
            cs_head_passage = csharp(head.mbcol, head_passages, w2) if head_passages else []
        cs_ran = True
        for key, got, pkg in (("base", cb, base), ("head", ch, head)):
            for i, idx in enumerate(got):
                if names(pkg.col, idx) != py[key][i]:
                    fails.append(f"C# and Python disagree on {key} query {i}")
        fails += [f"passage {p['id']} not clear on HEAD (C#)" for p, hit in zip(head.probes, cs_head_passage) if hit]
    if fails:
        print(f"FAIL {summary}")
        for f in fails[:50]:
            print("  " + f)
        return 1
    if not cs_ran:
        print(f"{summary} | python only, C# SKIPPED")
        return 2
    print(f"OK {summary} | Python and C# agree on every query")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
