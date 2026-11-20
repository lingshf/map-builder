# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Manual harness (not in CI): CLI path versus Blender path on frozen real acquisitions, Pittsburgh with DSM on.

Needs ``pittsburgh.osm`` and ``pittsburgh.tif`` (Copernicus GLO-30) in a folder, frozen once from Overpass and
the Copernicus tile (D64). The area is 40.437 N, 80.016 W, 1200 x 1000 m, DSM correction on, terrain spacing 10 m,
heightfield 2 m, datum EGM2008. Run, from the repository root:

    blender -b --factory-startup --python-exit-code 1 --python tools/manual/parity_frozen.py -- <acq dir> [<out dir>]

The CLI path is ``core.pipeline.build_package``; the Blender path is the Generate and Export operators with the
default seed. Exits non-zero unless both packages validate and their passage probes are equal.
"""
from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Mapping
from typing import NotRequired, TypedDict, cast

import bpy

sys.path.insert(0, os.getcwd())
import map_builder  # noqa: E402
from map_builder.core.generate import PlanOptions  # noqa: E402
from map_builder.core.geodesy import Area  # noqa: E402
from map_builder.core.package import validate_package  # noqa: E402
from map_builder.core.pipeline import Settings, build_package  # noqa: E402

LAT, LON, WIDTH, HEIGHT = 40.437, -80.016, 1200.0, 1000.0
DATUM, LICENCE = "EGM2008", "Copernicus GLO-30"
OSM_LICENCE = "OpenStreetMap contributors (ODbL), frozen Overpass response"


ProbeRow = tuple[str, str | None, str, tuple[tuple[float, ...], ...], float]


class ManifestProbe(TypedDict):
    id: str
    kind: NotRequired[str]
    feature: str
    path_map: list[list[float]]
    radius_m: float


def probe_set(manifest: Mapping[str, object]) -> list[ProbeRow]:
    probes = cast(list[ManifestProbe], manifest["passage_probes"])
    return sorted((p["id"], p.get("kind"), p["feature"], tuple(tuple(round(c, 3) for c in pt) for pt in p["path_map"]),
                   p["radius_m"]) for p in probes)


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not args:
        sys.exit("usage: ... -- <acq dir containing pittsburgh.osm and pittsburgh.tif> [<out dir>]")
    acq = args[0]
    out = args[1] if len(args) > 1 else tempfile.mkdtemp(prefix="mbparity-")
    os.makedirs(out, exist_ok=True)
    osm, dem = os.path.join(acq, "pittsburgh.osm"), os.path.join(acq, "pittsburgh.tif")
    for f in (osm, dem):
        if not os.path.isfile(f):
            sys.exit(f"missing frozen acquisition: {f}")

    cli_pkg = os.path.join(out, "cli_pittsburgh_dsm_on.mbmap")
    s = Settings(elevation_source="file", elevation_file=dem, elevation_vertical_datum=DATUM,
                 elevation_license=LICENCE, osm_source="file", osm_file=osm, osm_license=OSM_LICENCE,
                 terrain_spacing=10.0, heightfield_spacing=2.0, dsm_correction=True, plan_options=PlanOptions(seed=1))
    cli, cli_result = build_package(Area(LAT, LON, WIDTH, HEIGHT), s, cli_pkg, "pittsburgh")

    map_builder.register()
    m = bpy.context.scene.map_builder
    m.area_mode, m.centre_lat, m.centre_lon, m.width, m.height = "CENTER", repr(LAT), repr(LON), WIDTH, HEIGHT
    m.elevation_source, m.elevation_file = "file", dem
    m.elevation_vertical_datum, m.elevation_license = DATUM, LICENCE
    m.osm_source, m.osm_file = "file", osm
    m.terrain_spacing, m.heightfield_spacing, m.dsm_correction = 10.0, 2.0, "ON"
    bl_pkg = os.path.join(out, "bl_pittsburgh_dsm_on.mbmap")
    m.package_name, m.export_path = "pittsburgh", bl_pkg
    for op in (bpy.ops.map_builder.generate, bpy.ops.map_builder.export):
        if op() != {"FINISHED"}:
            sys.exit("Blender operator failed")
    bl_result = validate_package(bl_pkg)

    want, got = probe_set(cli), probe_set(bl_result.manifest)  # type: ignore[arg-type]  # manifest is set for a validated package
    print(f"CLI probes {len(want)}, Blender probes {len(got)}; packages: {out}")
    print(f"validate: CLI ok={cli_result.ok}, Blender ok={bl_result.ok}")
    if want != got:
        print("MISMATCH only in CLI:", [p[0] for p in want if p not in got])
        print("MISMATCH only in Blender:", [p[0] for p in got if p not in want])
        sys.exit(1)
    if not (cli_result.ok and bl_result.ok):
        sys.exit(1)
    print("OK: probe sets equal")


main()
