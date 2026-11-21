# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S4-WATER-SURFACE checks on an EMITTED package (spec AC3, AC6, AC7); works the same on a CLI or a Blender build.

  py -3.12 tools/water_check.py PACKAGE.mbmap [--min-clearance 0.62]

* Carve invariant (spec section 4) on the emitted ``.mbcol`` triangles: for every pair of a terrain triangle and a
  water triangle whose xy projections overlap, the terrain must not rise above the water over the overlap. The
  maximum (terrain - water, metres; negative = terrain below water) is printed per water body.
* Wet-probe clearance (AC6): every emitted ``:under`` probe whose capsule footprint touches an emitted water
  triangle must clear the highest emitted water and terrain surface over the whole footprint by at least
  ``--min-clearance`` (ROAD_LIFT_M + 0.5). The terrain here is the emitted (carved) one, which is never above the
  pre-carve ground the generator measures; the pre-carve term is covered by tests/test_water.py.

Exit 0 when nothing is violated, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from map_builder.core.bridges import PROBE_RADIUS_M, capsule_polygon  # noqa: E402
from map_builder.core.collision import read_collision  # noqa: E402
from map_builder.core.water import AREA_EPS, VIOLATION_TOL_M, _area2, _clip_poly_tri, _Plane  # noqa: E402

CELL = 32.0


def _box(t):
    xs, ys = [p[0] for p in t], [p[1] for p in t]
    return min(xs), min(ys), max(xs), max(ys)


def _cells(b, pad=0.0):
    for i in range(int((b[0] - pad) // CELL), int((b[2] + pad) // CELL) + 1):
        for j in range(int((b[1] - pad) // CELL), int((b[3] + pad) // CELL) + 1):
            yield i, j


def _index(tris):
    idx: dict = {}
    for k, t in enumerate(tris):
        for c in _cells(_box(t)):
            idx.setdefault(c, []).append(k)
    return idx


def _near(idx, tris, b, pad=0.0):
    seen: set[int] = set()
    for c in _cells(b, pad):
        for k in idx.get(c, ()):
            if k not in seen:
                seen.add(k)
                yield tris[k]


def invariant(col) -> dict[str, float]:
    terrain = [t for e in col.objects if e["class"] == "terrain" for t in col.object_triangles(e)]
    tidx = _index(terrain)
    out: dict[str, float] = {}
    for e in col.objects:
        if e["class"] != "water":
            continue
        worst = -math.inf
        for w in col.object_triangles(e):
            w2 = [(p[0], p[1]) for p in w]
            wp = _Plane(w)
            for t in _near(tidx, terrain, _box(w)):
                clip = _clip_poly_tri(w2, [(p[0], p[1]) for p in t])
                if len(clip) < 3 or abs(_area2(clip)) < AREA_EPS:
                    continue
                tp = _Plane(t)
                worst = max(worst, max(tp.at(x, y) - wp.at(x, y) for x, y in clip))
        out[e["name"]] = worst
    return out


def wet_clearance(col, probes, min_clear: float) -> list[tuple[str, float, bool]]:
    surf = [(t, "water" if e["class"] == "water" else "terrain") for e in col.objects
            if e["class"] in ("water", "terrain") for t in col.object_triangles(e)]
    tris = [s[0] for s in surf]
    idx = _index(tris)
    kind = {id(s[0]): s[1] for s in surf}
    rows = []
    for p in probes:
        if not str(p["id"]).endswith(":under"):
            continue
        (ax, ay, z), (bx, by, _) = p["path_map"]
        cap = capsule_polygon((ax, ay), (bx, by), p.get("radius_m", PROBE_RADIUS_M))
        box = (min(q[0] for q in cap), min(q[1] for q in cap), max(q[0] for q in cap), max(q[1] for q in cap))
        wet, top = False, -math.inf
        for t in _near(idx, tris, box):
            clip = _clip_poly_tri(cap, [(q[0], q[1]) for q in t])
            if len(clip) < 3 or abs(_area2(clip)) < AREA_EPS:
                continue
            pl = _Plane(t)
            m = max(pl.at(x, y) for x, y in clip)
            top = max(top, m)
            wet = wet or kind[id(t)] == "water"
        if wet:
            clear = z - p.get("radius_m", PROBE_RADIUS_M) - top
            rows.append((p["id"], clear, clear >= min_clear - 1e-4))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package")
    ap.add_argument("--min-clearance", type=float, default=0.62)
    a = ap.parse_args()
    with zipfile.ZipFile(a.package) as z:
        if z.testzip() is not None:
            raise SystemExit("corrupt zip")
        col = read_collision(z.read("collision/map.mbcol"))
        probes = json.loads(z.read("manifest.json")).get("passage_probes") or []
    bad = 0
    inv = invariant(col)
    for name, worst in sorted(inv.items()):
        ok = worst <= VIOLATION_TOL_M
        bad += not ok
        print(f"invariant {name}: max terrain-water {worst:+.6f} m {'OK' if ok else 'VIOLATION'}")
    if not inv:
        print("invariant: no water objects")
    rows = wet_clearance(col, probes, a.min_clearance)
    for pid, clear, ok in rows:
        bad += not ok
        print(f"wet probe {pid}: clearance {clear:.4f} m {'OK' if ok else 'BELOW ' + str(a.min_clearance)}")
    print(f"{len(inv)} water bodies, {len(rows)} wet under-probes, {'FAIL' if bad else 'PASS'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
