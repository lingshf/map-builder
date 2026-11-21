# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
# Scratch S4-REVIEW measurement: AC4/AC5/AC6 of S4-WATER-SURFACE on the plan (shared by CLI and Blender).
# PYTHONPATH=<tree> py water_ac.py dump|check <cache-dir> <json>
import json, math, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import offline_guard
offline_guard.install()
from map_builder.core import generate as G
from map_builder.core.generate import PlanOptions
from map_builder.core.geodesy import Area
from map_builder.core.pipeline import Settings, generate_plan

mode, cache, js = sys.argv[1], sys.argv[2], sys.argv[3]
cap = {}
if hasattr(G, "_water_stage"):
    orig = G._water_stage
    def wrap(*a, **k):
        m = orig(*a, **k); cap["m"] = m; return m
    G._water_stage = wrap


class NoNet:
    def fetch(self, url, *a, **k):
        raise RuntimeError("cache miss")


settings = Settings(cache_dir=cache, terrain_spacing=10.0, dsm_correction=True, heightfield_spacing=2.0,
                    plan_options=PlanOptions(seed=1))
plan, _ = generate_plan(Area(40.437, -80.016, 1200, 1000), settings, client=NoNet())
offline_guard.assert_offline()


def split(o):
    v = [(x, y, z + o.location[2]) for x, y, z in o.mesh.vertices]
    v = [(x + o.location[0], y + o.location[1], z) for x, y, z in v]
    n = 0
    while len(v) - 8 * (n + 1) >= 0:
        blk = v[len(v) - 8 * (n + 1): len(v) - 8 * n]
        if all(abs(blk[k][0] - blk[k + 4][0]) < 1e-9 and abs(blk[k][1] - blk[k + 4][1]) < 1e-9
               and blk[k][2] < blk[k + 4][2] for k in range(4)):
            n += 1
        else:
            break
    return v[:len(v) - 8 * n], [v[len(v) - 8 * (i + 1): len(v) - 8 * i] for i in range(n)]


bridges = {o.mb_id: split(o) for o in plan.objects if o.mb_class == "bridge" and o.mesh is not None}
if mode == "dump":
    json.dump({k: [d, p] for k, (d, p) in bridges.items()}, open(js, "w"))
    print("dumped", len(bridges), "bridges")
    sys.exit(0)

base = json.load(open(js))
m = cap["m"]
zoff = m.z_offset
out = {}
# AC6 decks
worst, raised, cmp_n, skipped = float("inf"), [], 0, []
for k, (deck, _) in bridges.items():
    if k not in base:
        skipped.append(k + " (new)"); continue
    bd = base[k][0]
    if len(bd) != len(deck):
        skipped.append(f"{k} (vertex count {len(bd)} -> {len(deck)})"); continue
    cmp_n += 1
    d = [h[2] - b[2] for h, b in zip(deck, bd)]
    worst = min(worst, min(d))
    if max(d) > 1e-3:
        raised.append((k, round(max(d), 3)))
out["decks_compared"] = cmp_n
out["deck_min_delta_m"] = round(worst, 6)
out["decks_raised"] = raised
out["decks_skipped"] = skipped
# AC6 piers
piers, wet, worst_gap = 0, 0, -float("inf")
wet_rows = []
for k, (_, ps) in bridges.items():
    for p in ps:
        corners = [(x, y) for x, y, _ in p[:4]]
        bottom = p[0][2] + zoff
        bed = m.carved_min_polygon(corners)
        gap = bottom - bed
        piers += 1
        worst_gap = max(worst_gap, gap)
        if m.touches_water(corners):
            wet += 1
            wet_rows.append((k, round(bottom, 3), round(bed, 3), round(gap, 3)))
out["piers"] = piers
out["pier_max_bottom_minus_carved_min_m"] = round(worst_gap, 3)
out["wet_piers"] = wet_rows
# AC4 / AC5
def a2(r):
    return sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r))) / 2.0
def dseg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
from map_builder.core.water import _inside_pieces
bodies = []
for b in m.bodies:
    row = {"id": b.id, "outcome": b.outcome, "sanity_miss": bool(b.info.get("sanity_miss"))}
    if b.built:
        pa = sum(abs(a2(o)) - sum(abs(a2(h)) for h in hs) for o, hs in b.pieces)
        ta = sum(abs(a2([(t[0][0], t[0][1]), (t[1][0], t[1][1]), (t[2][0], t[2][1])])) for t in b.tris)
        segs = [(r[i - 1], r[i]) for o, hs in b.pieces for r in [o] + hs for i in range(len(r))]
        ec = {}
        for t in b.tris:
            for i in range(3):
                a, c = (t[i][0], t[i][1]), (t[(i + 1) % 3][0], t[(i + 1) % 3][1])
                key = tuple(sorted((a, c)))
                ec[key] = ec.get(key, 0) + 1
        bnd = [e for e, n in ec.items() if n == 1]
        h1 = max(min(dseg(p, a, c) for a, c in segs) for e in bnd for p in e)
        h2 = max(min(dseg(p, a, c) for a, c in bnd) for s in segs for p in s)
        # 2 m raster symmetric difference between polygon and mesh coverage
        xs = [p[0] for o, _ in b.pieces for p in o]; ys = [p[1] for o, _ in b.pieces for p in o]
        def in_tri(t, x, y):
            (x0, y0, _), (x1, y1, _), (x2, y2, _) = t
            d1 = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
            d2 = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
            d3 = (x0 - x2) * (y - y2) - (y0 - y2) * (x - x2)
            return (d1 >= 0 and d2 >= 0 and d3 >= 0) or (d1 <= 0 and d2 <= 0 and d3 <= 0)
        sym = tot = 0
        y = math.floor(min(ys)) + 1.0
        while y < max(ys):
            x = math.floor(min(xs)) + 1.0
            while x < max(xs):
                a_ = _inside_pieces(b, x, y); m_ = any(in_tri(t, x, y) for t in b.tris)
                tot += a_; sym += a_ != m_
                x += 2.0
            y += 2.0
        lv = b.info.get("level_m"); p5 = b.info.get("p5"); p50 = b.info.get("p50")
        zs = [p[2] for t in b.tris for p in t]
        row.update(polygon_area=round(pa, 3), mesh_area=round(ta, 3), hausdorff_mesh_to_poly=h1,
                   hausdorff_poly_to_mesh=h2, raster2m_cells=tot, raster2m_symdiff=sym,
                   level_m=lv, p5=p5, p50=p50, mesh_z=[round(min(zs) - lv, 6) if lv else None,
                                                     round(max(zs) - lv, 6) if lv else None])
    bodies.append(row)
out["bodies"] = bodies
print(json.dumps(out, indent=1))
