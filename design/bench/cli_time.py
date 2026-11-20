# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
# S4 baseline harness (D91): CLI plan vs package (write + strict validate), median of 3, offline. See design/roadmap.md.
# Usage: MB_ROOT=<dir with cache-munich, cache-pittsburgh> MB_TAG=<tag> PYTHONPATH=<tree root> python cli_time.py munich pittsburgh
import copy, os, statistics, sys, time, json
from pathlib import Path
from map_builder.core.generate import PlanOptions, build_plan
from map_builder.core.geodesy import Area
from map_builder.core.pipeline import Settings, acquire, elevation_correction_note, plan_to_package
AREAS = {"pittsburgh": (Area(40.437, -80.016, 1200, 1000), "pittsburgh"),
         "munich": (Area(48.1395, 11.5764, 400, 400), "munich_altstadt")}
class NoNetwork:
    def fetch(self, url, *a, **k):
        raise RuntimeError("cache miss: " + url.split("?")[0])
root = Path(os.environ["MB_ROOT"]); tag = os.environ["MB_TAG"]
out = {}
for key in sys.argv[1:]:
    area, name = AREAS[key]
    settings = Settings(cache_dir=str(root / f"cache-{key}"), terrain_spacing=10.0, dsm_correction=True)
    grid, classified, sources = acquire(area, settings, client=NoNetwork())
    plan_t, pkg_t, tot = [], [], []
    for run in range(3):
        t = time.perf_counter()
        plan = build_plan(area, copy.deepcopy(grid), copy.deepcopy(classified), PlanOptions(seed=1), dsm_correction=True)
        t1 = time.perf_counter()
        src = copy.deepcopy(sources)
        note = elevation_correction_note(plan.report["terrain_correction"])
        for s in src:
            if note and s.get("kind") == "elevation":
                s["processing"] = note
        _, result = plan_to_package(plan, str(root / f"{tag}-{key}.mbmap"), name, src, textures=True,
                                    heightfield_spacing=2.0, created_utc="2026-11-20T00:00:00Z")
        t2 = time.perf_counter()
        plan_t.append(t1 - t); pkg_t.append(t2 - t1); tot.append(t2 - t)
        assert result.ok, result.summary()
    out[key] = {k: round(statistics.median(v), 3) for k, v in (("plan", plan_t), ("package", pkg_t), ("total", tot))}
    print("CLI", tag, key, out[key], flush=True)
json.dump(out, open(root / f"cli-{tag}.json", "w"))
