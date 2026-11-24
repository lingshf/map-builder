# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
# CPU-time (D147) single-run headless Blender Generate and Export, textured. One run per Blender process.
import bpy, os, sys, time, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import offline_guard; offline_guard.install()
a = sys.argv[sys.argv.index("--") + 1:]
root, tag, src, out = a[:4]; prof = len(a) > 4 and a[4] == "prof"
key = "munich" if "munich" in src else "pittsburgh"
AREA = {"munich": (48.1395, 11.5764, 400.0, 400.0), "pittsburgh": (40.437, -80.016, 1200.0, 1000.0)}[key]
sys.path.insert(0, root)
import map_builder
map_builder.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
cache = os.path.join(out, f"cache-bl-{tag}-{key}"); shutil.rmtree(cache, ignore_errors=True); shutil.copytree(src, cache)
m = bpy.context.scene.map_builder
lat, lon, w, h = AREA
m.area_mode, m.centre_lat, m.centre_lon, m.width, m.height = "CENTER", repr(lat), repr(lon), w, h
m.elevation_source, m.osm_source, m.cache_dir = "copernicus", "overpass", cache
m.terrain_spacing, m.heightfield_spacing, m.dsm_correction, m.seed, m.textures = 10.0, 2.0, "ON", 1, True
pkg = os.path.join(out, f"bl-{tag}-{key}.mbmap"); m.package_name, m.export_path = key, pkg
if prof:
    import cProfile; pr = cProfile.Profile(); pr.enable()
c0, w0 = time.process_time(), time.perf_counter()
r1 = bpy.ops.map_builder.generate()
c1, w1 = time.process_time(), time.perf_counter()
if prof:
    pr.disable(); pr.dump_stats(os.path.join(out, f"prof-bl-{tag}-{key}.pstats"))
r2 = bpy.ops.map_builder.export()
c2, w2 = time.process_time(), time.perf_counter()
offline_guard.assert_offline()
assert "FINISHED" in r1 and "FINISHED" in r2, (r1, r2)
print("CPU", json.dumps({"tag": tag, "key": key, "cpu_gen": c1 - c0, "cpu_ge": c2 - c0, "wall_gen": w1 - w0, "wall_ge": w2 - w0}), flush=True)
