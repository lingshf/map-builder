# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""D98 probe-equivalence replay of two packages (S4-COL-DEGEN, AC2).

  py -3.12 tools/col_degen_replay.py BASE.mbmap NEW.mbmap [--seed 20260101] [--rays 2000] [--capsules 100]
                                                         [--no-csharp]

Probes are derived from BASE and replayed on both packages, in the Python query (map_builder.core.query) and in
the C# reader (``--probe-work``, via tests/csharp_build.py):

* one downward ray through the centroid of every validator-degenerate triangle of BASE;
* ``--rays`` seeded downward rays over the BASE bounding box;
* ``--capsules`` seeded capsules (radii 0, 0.3, 0.5 m, two-point horizontal paths);
* every passage probe in the BASE manifest (``path_map``, ``radius_m``).

Python rays are compared on hit/miss, hit distance (1e-6 m) and object class; capsules and passage probes on the
set of (object name, class). C# has no ray query, so a ray is replayed as a radius-0 capsule along the ray
segment and compared per object. Prints one summary line and exits 1 on any difference.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from map_builder.core.collision import Collision, is_degenerate, read_collision  # noqa: E402
from map_builder.core.query import capsule_hits, ray_cast  # noqa: E402

DOWN = (0.0, 0.0, -1.0)
T_TOL = 1e-6


def load(path: str) -> tuple[bytes, list[dict]]:
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("manifest.json"))
        return z.read("collision/map.mbcol"), list(manifest.get("passage_probes") or [])


def names(col: Collision, idx: list[int]) -> list[tuple[str, str]]:
    return sorted((col.objects[k]["name"], col.objects[k]["class"]) for k in idx)


Path = tuple[list[tuple[float, float, float]], float]


def build_probes(col: Collision, probes: list[dict], rays: int, capsules: int, seed: int
                 ) -> tuple[list[tuple[float, float, float]], float, list[Path], list[Path], int]:
    cent = []
    for t in range(col.triangle_count):
        a, b, c = col.triangle(t)
        if is_degenerate(a, b, c):
            cent.append(tuple((a[i] + b[i] + c[i]) / 3 for i in range(3)))
    lo = [min(v[i] for v in col.vertices) for i in range(3)]
    hi = [max(v[i] for v in col.vertices) for i in range(3)]
    rng = random.Random(seed)
    top = hi[2] + 10.0
    grid = [(rng.uniform(lo[0], hi[0]), rng.uniform(lo[1], hi[1])) for _ in range(rays)]
    caps = []
    for _ in range(capsules):
        x, y, z = rng.uniform(lo[0], hi[0]), rng.uniform(lo[1], hi[1]), rng.uniform(lo[2], hi[2] + 3.0)
        caps.append(([(x, y, z), (x + rng.uniform(-5, 5), y + rng.uniform(-5, 5), z)], rng.choice((0.0, 0.3, 0.5))))
    ray_list = [(p[0], p[1], top) for p in cent] + [(x, y, top) for x, y in grid]
    passage = [(p["path_map"], float(p["radius_m"])) for p in probes]
    return ray_list, top - lo[2] + 10.0, caps, passage, len(cent)


def py_ray(col: Collision, o: tuple[float, float, float], dist: float) -> tuple[float, str] | None:
    h = ray_cast(col, o, DOWN, dist)
    return None if h is None else (h.t, col.objects[h.object]["class"])


def csharp(col_bytes: bytes, paths: list[tuple[list, float]], work: str) -> list[list[int]]:
    sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location("csharp_build", os.path.join(ROOT, "tests", "csharp_build.py"))
    assert spec and spec.loader
    csharp_build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(csharp_build)
    mbcol, pj = os.path.join(work, "c.mbcol"), os.path.join(work, "p.json")
    with open(mbcol, "wb") as f:
        f.write(col_bytes)
    with open(pj, "w") as f:
        json.dump([{"path": p, "radius": r} for p, r in paths], f)
    run = subprocess.run([*csharp_build.reader_command(), "--probe-work", mbcol, pj], capture_output=True, text=True)
    if run.returncode:
        raise SystemExit(run.stdout + run.stderr)
    out = []
    for line in run.stdout.splitlines():
        hits = line.split("hits=")[1].split(" ")[0]
        out.append([int(x) for x in hits.split(",") if x])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--rays", type=int, default=2000)
    ap.add_argument("--capsules", type=int, default=100)
    ap.add_argument("--no-csharp", action="store_true")
    a = ap.parse_args()
    (bb, probes), (nb, _) = load(a.base), load(a.new)
    cb, cn = read_collision(bb), read_collision(nb)
    rays, dist, caps, passage, ncent = build_probes(cb, probes, a.rays, a.capsules, a.seed)

    diff = {"py_ray": 0, "py_capsule": 0, "py_passage": 0, "cs_ray": 0, "cs_capsule": 0, "cs_passage": 0}
    hit = 0
    for o in rays:
        x, y = py_ray(cb, o, dist), py_ray(cn, o, dist)
        hit += x is not None
        if (x is None) != (y is None) or (x and y and (abs(x[0] - y[0]) > T_TOL or x[1] != y[1])):
            diff["py_ray"] += 1
    for key, group in (("py_capsule", caps), ("py_passage", passage)):
        for path, r in group:
            if names(cb, capsule_hits(cb, path, r)) != names(cn, capsule_hits(cn, path, r)):  # type: ignore[arg-type]
                diff[key] += 1
    if not a.no_csharp:
        ray_caps = [([o, (o[0], o[1], o[2] - dist)], 0.0) for o in rays]
        with tempfile.TemporaryDirectory() as w1, tempfile.TemporaryDirectory() as w2:
            for key, group in (("cs_ray", ray_caps), ("cs_capsule", caps), ("cs_passage", passage)):
                rb, rn = csharp(bb, group, w1), csharp(nb, group, w2)
                diff[key] = sum(names(cb, x) != names(cn, y) for x, y in zip(rb, rn))
    print(f"seed {a.seed} | centroid rays {ncent} + grid rays {len(rays) - ncent} ({hit} python hits) | "
          f"capsules {len(caps)} | passage probes {len(passage)} | differences {diff}")
    return 1 if any(diff.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
