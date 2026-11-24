# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
# CPU-time (D147) single-run CLI whole Generate: acquire+plan, package (write + strict validate). One run per process.
import os, sys, shutil, time, json
tree, tag, src, out, key = sys.argv[1:6]
prof = len(sys.argv) > 6 and sys.argv[6] == "prof"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, tree)
import offline_guard; offline_guard.install()
from map_builder.core.generate import PlanOptions
from map_builder.core.geodesy import Area
from map_builder.core.pipeline import Settings, generate_plan, plan_to_package
AREAS = {"pittsburgh": (Area(40.437, -80.016, 1200, 1000), "pittsburgh"), "munich": (Area(48.1395, 11.5764, 400, 400), "munich_altstadt")}
class NoNetwork:
    def fetch(self, url, *a, **k): raise RuntimeError("cache miss: " + url.split("?")[0])
area, name = AREAS[key]
cache = os.path.join(out, f"cache-cli-{tag}-{key}"); shutil.rmtree(cache, ignore_errors=True); shutil.copytree(src, cache)
settings = Settings(cache_dir=cache, terrain_spacing=10.0, dsm_correction=True, heightfield_spacing=2.0, plan_options=PlanOptions(seed=1))
if prof:
    import cProfile; pr = cProfile.Profile(); pr.enable()
c0, w0 = time.process_time(), time.perf_counter()
plan, sources = generate_plan(area, settings, client=NoNetwork())
c1, w1 = time.process_time(), time.perf_counter()
_, result = plan_to_package(plan, os.path.join(out, f"cli-{tag}-{key}.mbmap"), name, sources, textures=True, heightfield_spacing=2.0, created_utc="2026-11-20T00:00:00Z")
c2, w2 = time.process_time(), time.perf_counter()
if prof:
    pr.disable(); pr.dump_stats(os.path.join(out, f"prof-cli-{tag}-{key}.pstats"))
assert result.ok, result.summary()
offline_guard.assert_offline()
print("CPU", json.dumps({"tag": tag, "key": key, "cpu_plan": c1 - c0, "cpu_pkg": c2 - c1, "cpu_total": c2 - c0, "wall_total": w2 - w0}), flush=True)
