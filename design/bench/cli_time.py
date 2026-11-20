# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
# S4 baseline harness (D91): CLI whole Generate = acquire (frozen cache, offline) + plan + package (write +
# strict validate), median of 3. Every run starts from a fresh copy of the frozen cache. See design/roadmap.md.
# Usage: MB_CACHES=<dir with cache-munich, cache-pittsburgh> MB_OUT=<scratch dir> MB_TAG=<tag>
#        PYTHONPATH=<tree root> python cli_time.py munich pittsburgh
import os, shutil, statistics, sys, time, json
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import offline_guard
offline_guard.install()
from map_builder.core.generate import PlanOptions
from map_builder.core.geodesy import Area
from map_builder.core.pipeline import Settings, generate_plan, plan_to_package

AREAS = {"pittsburgh": (Area(40.437, -80.016, 1200, 1000), "pittsburgh"),
         "munich": (Area(48.1395, 11.5764, 400, 400), "munich_altstadt")}


class NoNetwork:
    def fetch(self, url, *a, **k):
        raise RuntimeError("cache miss: " + url.split("?")[0])


caches, out, tag = Path(os.environ["MB_CACHES"]), Path(os.environ["MB_OUT"]), os.environ["MB_TAG"]
res = {}
for key in sys.argv[1:]:
    area, name = AREAS[key]
    acq_plan, pkg, tot = [], [], []
    for run in range(3):
        cache = out / f"cli-cache-{tag}-{key}-{run}"
        shutil.rmtree(cache, ignore_errors=True)
        shutil.copytree(caches / f"cache-{key}", cache)
        settings = Settings(cache_dir=str(cache), terrain_spacing=10.0, dsm_correction=True,
                            heightfield_spacing=2.0, plan_options=PlanOptions(seed=1))
        t0 = time.perf_counter()
        plan, sources = generate_plan(area, settings, client=NoNetwork())
        t1 = time.perf_counter()
        _, result = plan_to_package(plan, str(out / f"cli-{tag}-{key}.mbmap"), name, sources, textures=True,
                                    heightfield_spacing=2.0, created_utc="2026-11-20T00:00:00Z")
        t2 = time.perf_counter()
        assert result.ok, result.summary()
        acq_plan.append(t1 - t0); pkg.append(t2 - t1); tot.append(t2 - t0)
    offline_guard.assert_offline()
    res[key] = {k: round(statistics.median(v), 3) for k, v in
                (("acquire_plan", acq_plan), ("package", pkg), ("total", tot))}
    print("CLI", tag, key, res[key], "network_attempts=0", flush=True)
json.dump(res, open(out / f"cli-{tag}.json", "w"))
