"""Derive a small probe-bearing demo package from the committed synthetic sample (viewer smoke test).

    py -3.12 tools/demo/make_probe_sample.py out/probe_sample.mbmap

The result is the synthetic sample plus three passage probes: one clear (PASS), one through a building
(BLOCKED) and one whose id contains markup, to show that the viewer lists ids as plain text.
"""

import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demo_bundle as db  # noqa: E402,F401  (sets up sys.path for map_builder)

from map_builder.core.collision import read_collision  # noqa: E402
from map_builder.core.geodesy import Area  # noqa: E402
from map_builder.core.package import assemble, validate_package, write_package  # noqa: E402

SAMPLE = os.path.join(db.REPO, "examples", "synthetic_sample.mbmap")


def main(out):
    with zipfile.ZipFile(SAMPLE) as z:
        m = json.loads(z.read("manifest.json"))
        glb, col_bytes = z.read("visual/map.glb"), z.read("collision/map.mbcol")
        hf = (z.read("collision/terrain.mbhf"), {k: v for k, v in m["heightfield"].items()
                                                   if k not in ("path", "format", "version", "authority")})
        report = json.loads(z.read("report.json"))
    col = read_collision(col_bytes)
    b = next(e for e in col.objects if e["name"] == "bld_way_1007")
    lo, hi = b["aabb"][:3], b["aabb"][3:]
    cx, cy, cz = [(lo[i] + hi[i]) / 2 for i in range(3)]
    ids = {o["name"]: o["mb_id"] for o in m["objects"]}
    feat = ids["bld_way_1007"]
    probes = [
        {"id": "clear-overhead", "kind": "bridge", "feature": feat, "radius_m": 1.0,
         "path_map": [[-60, 0, 60], [60, 0, 60]]},
        {"id": "through-building", "kind": "tunnel", "feature": feat, "radius_m": 1.5,
         "path_map": [[cx - 20, cy, cz], [cx + 20, cy, cz]]},
        {"id": "<img src=x onerror=alert(1)> & co", "kind": "elevated", "feature": feat, "radius_m": 1.0,
         "path_map": [[0, -80, 50], [0, 80, 50]]},
    ]
    area = Area(m["georeference"]["origin"]["lat_deg"], m["georeference"]["origin"]["lon_deg"],
                m["area"]["width_m"], m["area"]["height_m"])
    members, manifest, _ = assemble("probe_sample", area, m["sources"], glb, col_bytes, m["objects"], heightfield=hf,
                                    report=report, created_utc="2026-01-01T00:00:00Z", passage_probes=probes)
    write_package(out, members, manifest)
    r = validate_package(out)
    print(r.summary())
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
