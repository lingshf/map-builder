# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5-F3 step 2 evidence: one heightfield finding node, for the AC4 class-E reason.

  py -3.12 hf_node.py <package> <x> <y> --json <out>

Reports the ``.mbhf`` height at the node, every collision triangle within ``NEAR_M`` with the node's signed distance
to each edge (positive inside), and the Python and C# downward rays at the node and on the spec's +-0.5 m grid at
0.1 m spacing.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from map_builder.core.collision import Collision, read_collision, read_heightfield  # noqa: E402
from map_builder.core.query import ray_cast  # noqa: E402
from water_replay import csharp_rays  # noqa: E402

NEAR_M = 3.0
GRID_HALF_M = 0.5
GRID_STEP_M = 0.1
RAY_TOP_Z = 1000.0
RAY_DIST_M = 2000.0
DOWN = (0.0, 0.0, -1.0)
Z_AGREE_M = 1e-4             # float32 error at map coordinates (the spec's shore-step note)

Pt = tuple[float, float]


def edge_distances(tri: Any, p: Pt) -> list[float]:
    """Signed distance of ``p`` to each edge of the triangle in plan; all >= 0 (CCW) means inside."""
    out = []
    for k in range(3):
        (ax, ay, _), (bx, by, _) = tri[k], tri[(k + 1) % 3]
        length = math.hypot(bx - ax, by - ay)
        out.append(((bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)) / length if length else math.inf)
    return out


def near_triangles(col: Collision, p: Pt) -> list[dict[str, Any]]:
    out = []
    for t in range(col.triangle_count):
        tri = col.triangle(t)
        xs, ys = [v[0] for v in tri], [v[1] for v in tri]
        if min(xs) - NEAR_M <= p[0] <= max(xs) + NEAR_M and min(ys) - NEAR_M <= p[1] <= max(ys) + NEAR_M:
            obj = col.objects[col.tri_object[t]]
            out.append({"triangle": t, "mb_id": obj["mb_id"], "class": obj["class"],
                        "xyz": [list(v) for v in tri], "edge_distance_m": edge_distances(tri, p)})
    return out


def grid(p: Pt) -> list[Pt]:
    steps = round(GRID_HALF_M / GRID_STEP_M)
    return [(p[0] + i * GRID_STEP_M, p[1] + j * GRID_STEP_M)
            for j in range(-steps, steps + 1) for i in range(-steps, steps + 1)]


def rays(col_bytes: bytes, col: Collision, points: list[Pt]) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as work:
        cs_hits = csharp_rays(col_bytes, [(x, y, RAY_TOP_Z) for x, y in points], RAY_DIST_M, work)
    out = []
    for (x, y), cs in zip(points, cs_hits):
        py = ray_cast(col, (x, y, RAY_TOP_Z), DOWN, RAY_DIST_M)
        py_hit = None if py is None else [RAY_TOP_Z - py[0], col.objects[py[2]]["mb_id"]]
        cs_hit = None if cs is None else [RAY_TOP_Z - cs[0], col.objects[int(cs[1])]["mb_id"]]
        out.append({"xy": [x, y], "python": py_hit, "csharp": cs_hit, "agree": same_hit(py_hit, cs_hit)})
    return out


def same_hit(a: list[Any] | None, b: list[Any] | None) -> bool:
    if a is None or b is None:
        return a is b
    return bool(a[1] == b[1] and abs(a[0] - b[0]) < Z_AGREE_M)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package", type=Path)
    ap.add_argument("x", type=float)
    ap.add_argument("y", type=float)
    ap.add_argument("--json", type=Path, required=True)
    a = ap.parse_args()
    node = (a.x, a.y)
    with zipfile.ZipFile(a.package) as z:
        col_bytes, hf = z.read("collision/map.mbcol"), read_heightfield(z.read("collision/terrain.mbhf"))
    col = read_collision(col_bytes)
    i, j = round((a.x - hf["x0"]) / hf["spacing"]), round((a.y - hf["y0"]) / hf["spacing"])
    grid_rays = rays(col_bytes, col, grid(node))
    report = {"package": a.package.name, "node": node, "hf_z": hf["z"][j][i],
              "near_triangles": near_triangles(col, node), "rays": grid_rays,
              "misses": [r["xy"] for r in grid_rays if r["python"] is None],
              "readers_agree": all(r["agree"] for r in grid_rays)}
    a.json.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("node", "hf_z", "misses", "readers_agree")}))


if __name__ == "__main__":
    main()
