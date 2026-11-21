# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
# S4-REVIEW R2: AC4/AC5/AC6 of S4-WATER-SURFACE measured on an EMITTED package (Blender path), plus Blender/CLI parity.
# PYTHONPATH=<head tree> py water_ac_pkg.py CACHE HEAD_BLENDER.mbmap BASE_BLENDER.mbmap HEAD_CLI.mbmap
import json, math, sys, os, zipfile, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import offline_guard
offline_guard.install()
from map_builder.core import generate as G
from map_builder.core.generate import PlanOptions
from map_builder.core.geodesy import Area
from map_builder.core.pipeline import Settings, generate_plan
from map_builder.core.collision import read_collision
from map_builder.core.water import _inside_pieces, _clip_poly_tri, _area2, _Plane, AREA_EPS

cache, hb, bb, hc = sys.argv[1:5]
cap = {}
orig = G._water_stage
def wrap(*a, **k):
    m = orig(*a, **k); cap["m"] = m; return m
G._water_stage = wrap
class NoNet:
    def fetch(self, url, *a, **k):
        raise RuntimeError("cache miss")
plan, _ = generate_plan(Area(40.437, -80.016, 1200, 1000), Settings(cache_dir=cache, terrain_spacing=10.0,
                        dsm_correction=True, heightfield_spacing=2.0, plan_options=PlanOptions(seed=1)), client=NoNet())
offline_guard.assert_offline()
m = cap["m"]

def load(p):
    z = zipfile.ZipFile(p)
    col = read_collision(z.read("collision/map.mbcol"))
    rep = json.loads(z.read("report.json"))
    objs = {e["name"]: (e["class"], col.object_triangles(e)) for e in col.objects}
    sha = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
    return objs, rep, sha
H, HR, HS = load(hb); B, BR, BS = load(bb); C, CR, CS = load(hc)
zoff = HR["z_offset_m"]
out = {"packages": {"head_blender": hb, "base_blender": bb, "head_cli": hc},
       "z_offset_m": {"head_blender": zoff, "base_blender": BR["z_offset_m"], "head_cli": CR["z_offset_m"]}}

def a2(r):
    return sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r))) / 2.0
def dseg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
def in_tri(t, x, y):
    (x0, y0, _), (x1, y1, _), (x2, y2, _) = t
    d1 = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
    d2 = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
    d3 = (x0 - x2) * (y - y2) - (y0 - y2) * (x - x2)
    return (d1 >= 0 and d2 >= 0 and d3 >= 0) or (d1 <= 0 and d2 <= 0 and d3 <= 0)

# AC4 / AC5 on the Blender-emitted water objects and the Blender report
rb = {r["id"]: r for r in HR["water_bodies"]}
bodies = []
for b in m.bodies:
    r = rb[b.id]
    row = {"id": b.id, "outcome_blender": r["outcome"], "sanity_miss_blender": bool(r.get("sanity_miss"))}
    name = "water:" + b.id
    if b.built:
        tris = H[name][1]
        pa = sum(abs(a2(o)) - sum(abs(a2(h)) for h in hs) for o, hs in b.pieces)
        ta = sum(abs(a2([(p[0], p[1]) for p in t])) for t in tris)
        segs = [(rr[i - 1], rr[i]) for o, hs in b.pieces for rr in [o] + hs for i in range(len(rr))]
        ec = collections.Counter()
        for t in tris:
            for i in range(3):
                ec[tuple(sorted(((t[i][0], t[i][1]), (t[(i + 1) % 3][0], t[(i + 1) % 3][1]))))] += 1
        bnd = [e for e, n in ec.items() if n == 1]
        h1 = max(min(dseg(p, a, c) for a, c in segs) for e in bnd for p in e)
        h2 = max(min(dseg(p, a, c) for a, c in bnd) for s in segs for p in s)
        xs = [p[0] for o, _ in b.pieces for p in o]; ys = [p[1] for o, _ in b.pieces for p in o]
        gx0, gy0 = math.floor(min(xs)) + 1.0, math.floor(min(ys)) + 1.0
        covered = set()
        for t in tris:
            tx0, tx1 = min(p[0] for p in t), max(p[0] for p in t); ty0, ty1 = min(p[1] for p in t), max(p[1] for p in t)
            for i in range(max(0, math.ceil((tx0 - gx0) / 2)), math.floor((tx1 - gx0) / 2) + 1):
                for j in range(max(0, math.ceil((ty0 - gy0) / 2)), math.floor((ty1 - gy0) / 2) + 1):
                    if in_tri(t, gx0 + 2 * i, gy0 + 2 * j):
                        covered.add((i, j))
        sym = tot = 0
        j = 0
        while gy0 + 2 * j < max(ys):
            i = 0
            while gx0 + 2 * i < max(xs):
                a_ = _inside_pieces(b, gx0 + 2 * i, gy0 + 2 * j); m_ = (i, j) in covered
                tot += a_; sym += a_ != m_
                i += 1
            j += 1
        zs = [p[2] + zoff for t in tris for p in t]
        lv = r["level_m"]
        row.update(triangles=len(tris), polygon_area=round(pa, 3), mesh_area=round(ta, 3),
                   hausdorff_mesh_to_poly_m=round(h1, 6), hausdorff_poly_to_mesh_m=round(h2, 6),
                   raster2m_cells=tot, raster2m_symdiff=sym, 
                   level_m=lv, p5=r.get("p5"), p50=r.get("p50"), level_in_p5_p50=r.get("p5") <= lv <= r.get("p50"),
                   mesh_z_minus_level_m=[round(min(zs) - lv, 6), round(max(zs) - lv, 6)],
                   level_equal_cli=lv == {x["id"]: x for x in CR["water_bodies"]}[b.id]["level_m"])
    bodies.append(row)
out["ac4_ac5_bodies"] = bodies

# AC6 on Blender head vs Blender base: decks by vertex xy key, piers from the plan's pier corners
def split(o):
    v = [(x + o.location[0], y + o.location[1], z + o.location[2]) for x, y, z in o.mesh.vertices]
    n = 0
    while len(v) - 8 * (n + 1) >= 0:
        blk = v[len(v) - 8 * (n + 1): len(v) - 8 * n]
        if all(abs(blk[k][0] - blk[k + 4][0]) < 1e-9 and abs(blk[k][1] - blk[k + 4][1]) < 1e-9
               and blk[k][2] < blk[k + 4][2] for k in range(4)):
            n += 1
        else:
            break
    return [v[len(v) - 8 * (i + 1): len(v) - 8 * i] for i in range(n)]
piers_by_name = {}
for o in plan.objects:
    if o.mb_class == "bridge" and o.mesh is not None:
        piers_by_name[o.name] = split(o)
K = lambda x, y: (round(x * 200), round(y * 200))     # 5 mm xy key
def zmap(tris):
    d = collections.defaultdict(set)
    for t in tris:
        for p in t:
            d[K(p[0], p[1])].add(round(p[2], 4))
    return d
terrain = [t for n, (c, ts) in H.items() if c == "terrain" for t in ts]
water = [t for n, (c, ts) in H.items() if c == "water" for t in ts]
worst, raised, compared, skipped, pier_rows = math.inf, [], 0, [], []
for name, (cls, ts) in sorted(H.items()):
    if cls != "bridge":
        continue
    pier_keys = {(k[0] + a, k[1] + c) for k in (K(p[0], p[1]) for pr in piers_by_name.get(name, []) for p in pr)
                 for a in (-1, 0, 1) for c in (-1, 0, 1)}
    if name not in B:
        skipped.append(name + " (new)"); continue
    hz, bz = zmap(ts), zmap(B[name][1])
    moved = set(bz) - set(hz)                        # base pier corners that moved in xy at head
    dk = [k for k in hz if k not in pier_keys]
    if not (set(hz) - set(bz)) <= pier_keys or set(dk) != {k for k in bz if k not in pier_keys | moved}:
        skipped.append((name, "deck xy set differs", sorted((set(hz) - set(bz)) - pier_keys)[:6], sorted(set(dk) ^ {k for k in bz if k not in pier_keys | moved})[:6], len(pier_keys), len(moved))); continue
    if moved:
        out.setdefault("piers_moved_xy", []).append((name, len(moved) // 4))
    compared += 1
    dmin, dmax = math.inf, -math.inf
    for k in dk:
        h, b_ = sorted(hz[k]), sorted(bz[k])
        if len(h) != len(b_):
            skipped.append(f"{name} (z count at a vertex)"); break
        for x, y in zip(h, b_):
            dmin, dmax = min(dmin, x - y), max(dmax, x - y)
    worst = min(worst, dmin)
    if dmax > 1e-3:
        raised.append((name, round(dmax, 3)))
    for pr in piers_by_name.get(name, []):
        corners = [(p[0], p[1]) for p in pr[:4]]
        bottom = min(min(min(hz.get((K(x, y)[0] + a, K(x, y)[1] + c), {math.inf})) for a in (-1, 0, 1) for c in (-1, 0, 1)) for x, y in corners)
        bed, wet = math.inf, False
        for t in terrain:
            if max(p[0] for p in t) < min(c[0] for c in corners) or min(p[0] for p in t) > max(c[0] for c in corners) \
               or max(p[1] for p in t) < min(c[1] for c in corners) or min(p[1] for p in t) > max(c[1] for c in corners):
                continue
            clip = _clip_poly_tri(corners, [(p[0], p[1]) for p in t])
            if len(clip) < 3 or abs(_area2(clip)) < AREA_EPS:
                continue
            pl = _Plane(t); bed = min(bed, min(pl.at(x, y) for x, y in clip))
        for t in water:
            clip = _clip_poly_tri(corners, [(p[0], p[1]) for p in t])
            if len(clip) >= 3 and abs(_area2(clip)) >= AREA_EPS:
                wet = True; break
        pier_rows.append((name, wet, round(bottom - bed, 3)))
out["ac6_decks"] = {"compared": compared, "min_delta_head_minus_base_m": round(worst, 4), "raised": raised,
                    "skipped": skipped, "water_decks_raised_report": HR.get("water_decks_raised")}
out["ac6_piers"] = {"piers": len(pier_rows), "wet": sum(r[1] for r in pier_rows),
                    "max_bottom_minus_emitted_bed_m": max(r[2] for r in pier_rows), "rows": pier_rows}

# Parity of emitted surfaces: Blender head vs CLI head
def tset(ts):
    return collections.Counter(tuple(sorted(tuple(round(c, 4) for c in p) for p in t)) for t in ts)
par = {}
for name, (cls, ts) in H.items():
    if cls in ("water", "terrain", "bridge"):
        a, c = tset(ts), tset(C[name][1]) if name in C else collections.Counter()
        par[name] = {"class": cls, "blender_tris": len(ts), "cli_tris": sum(c.values()),
                     "only_blender": sum((a - c).values()), "only_cli": sum((c - a).values())}
out["parity_blender_vs_cli"] = {"objects": len(par), "identical_sets": sum(1 for v in par.values() if not v["only_blender"] and not v["only_cli"]),
                                "differing": {k: v for k, v in par.items() if v["only_blender"] or v["only_cli"]},
                                "terrain_mbhf_sha256": {"blender": HS["collision/terrain.mbhf"], "cli": CS["collision/terrain.mbhf"]}}
print(json.dumps(out, indent=1))
