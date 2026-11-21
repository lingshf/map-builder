# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""D98 probe-equivalence replay of two packages (S4-COL-DEGEN, AC2).

  py -3.12 tools/col_degen_replay.py BASE.mbmap NEW.mbmap [--seed 20260101] [--rays 2000] [--capsules 100]
                                                         [--allow-passage-id ID ...] [--no-csharp]

Rays and capsules are derived from BASE and replayed on both packages, in the Python query
(map_builder.core.query) and in the C# reader (``--probe-work``, via tests/csharp_build.py):

* one downward ray through the centroid of every validator-degenerate triangle of BASE;
* ``--rays`` seeded downward rays over the BASE bounding box;
* ``--capsules`` seeded capsules (radii 0, 0.3, 0.5 m, two-point horizontal paths).

Python rays are compared on hit/miss, hit distance (1e-6 m) and object class; capsules on the set of (object name, class). C# has no ray query, so a ray is replayed as a radius-0 capsule along the ray
segment and compared per object.

Passage probes are NOT compared against BASE: they are read from the manifest of NEW and each must be clear
(no object touched) in the Python query and in the C# reader. NEW must not lose passage ids or passages
(a count drop is always an error), nor add or change ids unless listed with ``--allow-passage-id``.

Exit 0 only when every group ran and had no difference. Exit 1 on any difference or passage failure, 2 when the C#
comparison did not run (``--no-csharp``); a wrong number of C# results aborts with a message.
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
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from map_builder.core.collision import Collision, is_degenerate, read_collision  # noqa: E402
from map_builder.core.query import capsule_hits, ray_cast  # noqa: E402

DOWN = (0.0, 0.0, -1.0)
T_TOL = 1e-6


def load(path: str) -> tuple[bytes, list[dict[str, Any]]]:
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("manifest.json"))
        return z.read("collision/map.mbcol"), list(manifest.get("passage_probes") or [])


def names(col: Collision, idx: list[int]) -> list[tuple[str, str]]:
    return sorted((col.objects[k]["name"], col.objects[k]["class"]) for k in idx)


Path = tuple[list[tuple[float, float, float]], float]


def build_probes(col: Collision, rays: int, capsules: int, seed: int
                 ) -> tuple[list[tuple[float, float, float]], float, list[Path], int]:
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
    return ray_list, top - lo[2] + 10.0, caps, len(cent)


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
        if line.startswith("probe ") and "hits=" in line:
            hits = line.split("hits=")[1].split(" ")[0]
            out.append([int(x) for x in hits.split(",") if x])
    if len(out) != len(paths):
        raise SystemExit(f"C# reader returned {len(out)} results for {len(paths)} probes")
    return out


def passage_problems(base: list[dict[str, Any]], new: list[dict[str, Any]], allowed: set[str]) -> list[str]:
    b = {str(p.get("id")): p for p in base}
    n = {str(p.get("id")): p for p in new}
    out = []
    if len(new) < len(base):
        out.append(f"passage count dropped {len(base)} -> {len(new)}")
    for pid in sorted(set(b) - set(n)):
        if pid not in allowed:
            out.append(f"passage {pid} missing from NEW")
    for pid in sorted(set(n) - set(b)):
        if pid not in allowed:
            out.append(f"passage {pid} added in NEW")
    for pid in sorted(set(b) & set(n)):
        if b[pid] != n[pid] and pid not in allowed:
            out.append(f"passage {pid} record changed")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--rays", type=int, default=2000)
    ap.add_argument("--capsules", type=int, default=100)
    ap.add_argument("--allow-passage-id", action="append", default=[])
    ap.add_argument("--no-csharp", action="store_true")
    a = ap.parse_args()
    (bb, bprobes), (nb, nprobes) = load(a.base), load(a.new)
    problems = passage_problems(bprobes, nprobes, set(a.allow_passage_id))
    if problems:
        print("FAIL passages: " + "; ".join(problems))
        return 1
    cb, cn = read_collision(bb), read_collision(nb)
    rays, dist, caps, ncent = build_probes(cb, a.rays, a.capsules, a.seed)
    passage: list[Path] = [(p["path_map"], float(p["radius_m"])) for p in nprobes]

    diff = {"py_ray": 0, "py_capsule": 0, "py_passage_not_clear": 0,
            "cs_ray": 0, "cs_capsule": 0, "cs_passage_not_clear": 0}
    hit = 0
    for o in rays:
        x, y = py_ray(cb, o, dist), py_ray(cn, o, dist)
        hit += x is not None
        if (x is None) != (y is None) or (x and y and (abs(x[0] - y[0]) > T_TOL or x[1] != y[1])):
            diff["py_ray"] += 1
    for path, r in caps:
        if names(cb, capsule_hits(cb, path, r)) != names(cn, capsule_hits(cn, path, r)):  # type: ignore[arg-type]
            diff["py_capsule"] += 1
    for path, r in passage:
        if capsule_hits(cn, path, r):
            diff["py_passage_not_clear"] += 1
    summary = (f"seed {a.seed} | centroid rays {ncent} + grid rays {len(rays) - ncent} ({hit} python hits) | "
               f"capsules {len(caps)} | passages checked on NEW {len(passage)}")
    if a.no_csharp:
        print(f"{summary} | python differences {diff} | C# SKIPPED")
        return 2
    ray_caps: list[Path] = [([o, (o[0], o[1], o[2] - dist)], 0.0) for o in rays]
    with tempfile.TemporaryDirectory() as w1, tempfile.TemporaryDirectory() as w2:
        for key, group in (("cs_ray", ray_caps), ("cs_capsule", caps)):
            rb, rn = csharp(bb, group, w1), csharp(nb, group, w2)
            if len(rb) != len(rn):
                raise SystemExit(f"C# result lists differ in length for {key}: {len(rb)} vs {len(rn)}")
            diff[key] = sum(names(cb, x) != names(cn, y) for x, y in zip(rb, rn))
        if passage:
            diff["cs_passage_not_clear"] = sum(1 for h in csharp(nb, passage, w2) if h)
    print(f"{summary} | differences {diff}")
    return 1 if any(diff.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
