# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""S4-WATER-SURFACE (AC3, AC7) Blender check: the synthetic fixture area is generated and exported through the
operators. The package must carry the water object as class ``water`` with the same triangle count as the CLI
build of the same inputs (examples/synthetic_sample.mbmap), no wet-probe violation, and the section 4 carve
invariant must hold on the triangles Blender baked into the package collision (``tools/water_check.py``)."""

import os
import re
import sys
import zipfile

import bpy

from checks_core import FIXTURES, HEIGHT, LAT, LON, REPO, check, run_op

sys.path.insert(0, os.path.join(REPO, "tools"))


def run(out_dir):
    import water_check
    from map_builder.core.collision import read_collision
    from map_builder.core.package import validate_package

    pkg = os.path.join(out_dir, "water.mbmap")
    s = bpy.context.scene.map_builder
    s.area_mode = "CENTER"
    s.centre_lat, s.centre_lon, s.width, s.height = str(LAT), str(LON), 400.0, HEIGHT
    s.elevation_source, s.elevation_file = "file", os.path.join(FIXTURES, "synthetic_dem.asc")
    s.osm_source, s.osm_file = "file", os.path.join(FIXTURES, "synthetic_area.osm")
    s.export_path = pkg
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"water: generate fixture ({err or 'ok'})")
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"water: export fixture ({err or 'ok'})")
    check(validate_package(pkg).ok, "water: Blender package VALID")

    def water_counts(path):
        with zipfile.ZipFile(path) as z:
            col = read_collision(z.read("collision/map.mbcol"))
        # earlier checks of the same Blender session leave same-named datablocks, so strip ".NNN" suffixes
        return col, {re.sub(r"\.\d{3}$", "", e["name"]): e["tri_count"] for e in col.objects if e["class"] == "water"}

    col, got = water_counts(pkg)
    _, cli = water_counts(os.path.join(REPO, "examples", "synthetic_sample.mbmap"))
    check(len(got) >= 1 and got == cli, f"water: Blender water objects (class water) and triangle counts equal the "
                                        f"CLI build: {got} vs {cli}")
    for name, worst in sorted(water_check.invariant(col).items()):
        check(worst <= 1e-9, f"water: carve invariant on Blender's baked triangles, {name}: max terrain-water "
                             f"{worst:+.6f} m")
