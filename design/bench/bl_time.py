# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
# S4 baseline harness (D91): headless Blender Generate vs Export, median of 3, with offline_guard (any DNS or
# connect raises and fails the run). See design/roadmap.md, sprint 4 baselines.
# Usage: blender --background --factory-startup --online-mode --python-exit-code 1 --python bl_time.py -- <tree root> <tag> <frozen cache dir> <out dir>
import bpy, os, sys, time, shutil, json, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import offline_guard
offline_guard.install()
a = sys.argv[sys.argv.index("--") + 1:]
root, tag, src_cache, out = a[0], a[1], a[2], a[3]
key = "munich" if "munich" in src_cache else "pittsburgh"
AREA = {"munich": (48.1395, 11.5764, 400.0, 400.0), "pittsburgh": (40.437, -80.016, 1200.0, 1000.0)}[key]
sys.path.insert(0, root)
import map_builder
from map_builder.core.package import validate_package
map_builder.register()
res = []
for i in range(3):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cache = os.path.join(out, f"cache-{tag}-{key}-{i}")
    shutil.rmtree(cache, ignore_errors=True); shutil.copytree(src_cache, cache)
    n0 = sum(len(f) for _, _, f in os.walk(cache))
    m = bpy.context.scene.map_builder
    lat, lon, w, h = AREA
    m.area_mode, m.centre_lat, m.centre_lon, m.width, m.height = "CENTER", repr(lat), repr(lon), w, h
    m.elevation_source, m.osm_source, m.cache_dir = "copernicus", "overpass", cache
    m.terrain_spacing, m.heightfield_spacing, m.dsm_correction, m.seed, m.textures = 10.0, 2.0, "ON", 1, True
    pkg = os.path.join(out, f"{tag}-{key}-{i}.mbmap"); m.package_name, m.export_path = key, pkg
    t0 = time.perf_counter(); r1 = bpy.ops.map_builder.generate(); t1 = time.perf_counter()
    r2 = bpy.ops.map_builder.export(); t2 = time.perf_counter()
    n1 = sum(len(f) for _, _, f in os.walk(cache))
    ok = validate_package(pkg).ok
    res.append({"gen": t1 - t0, "exp": t2 - t1, "total": t2 - t0, "ok": ok, "ops": [list(r1), list(r2)], "new_cache_files": n1 - n0})
    print("RUN", tag, key, i, res[-1], flush=True)
offline_guard.assert_offline()
med = {k: statistics.median(r[k] for r in res) for k in ("gen", "exp", "total")}
print("MEDIAN", tag, key, json.dumps(med), "network_attempts=0", flush=True)
with open(os.path.join(out, f"res-{tag}-{key}.json"), "w") as f: json.dump({"runs": res, "median": med}, f)
