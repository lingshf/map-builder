"""S3-PARITY: the CLI path and the Blender path emit the same passage probes from the same input files.

Both paths read the same synthetic acquisition files (OSM + DEM) with the same area and settings. The CLI path is
``core.pipeline.build_package`` (what ``tools/mbmap_cli.py build`` calls); the Blender path is the Generate and
Export operators. The probe sets (id, kind, feature, path, radius) must be equal, in the default (DSM correction
auto = off for a local file) and in the DSM-on mode, where the terrain is lowered under the buildings.

Blender stores the centre as strings (full double precision), so a centre such as 40.437 N is not rounded to
float32 and the area equals the CLI's (S3-PARITY-FIX; Pittsburgh DSM-on is the manual harness
``tools/manual/parity_frozen.py``). The seed is left at the Blender default, which equals the CLI default (1).
Reports through ``checks_core.check``.
"""
import os

import bpy  # noqa: E402

import checks_core
from checks_core import FIXTURES, check, run_op

SEED = 1   # the CLI default; the Blender default is asserted equal to it in run()
OSM = os.path.join(FIXTURES, "synthetic_area.osm")
DEM = os.path.join(FIXTURES, "synthetic_dem.asc")
DEM_LICENSE = "SYNTHETIC test data (no licence required)"
OSM_LICENSE = "SYNTHETIC test fixture (hand-written OSM-format XML, not OpenStreetMap data; no licence required)"


def _probe_set(manifest):
    return sorted((p["id"], p.get("kind"), p["feature"], tuple(tuple(round(c, 3) for c in pt) for pt in p["path_map"]),
                   p["radius_m"]) for p in manifest["passage_probes"])


def _cli_manifest(out_dir, dsm):
    from map_builder.core.geodesy import Area
    from map_builder.core.generate import PlanOptions
    from map_builder.core.pipeline import Settings, build_package

    s = Settings(elevation_source="file", elevation_file=DEM, elevation_crs="EPSG:4326",
                 elevation_vertical_datum="SYNTHETIC", elevation_license=DEM_LICENSE, osm_source="file",
                 osm_file=OSM, osm_license=OSM_LICENSE, terrain_spacing=10.0, heightfield_spacing=10.0,
                 dsm_correction=dsm, plan_options=PlanOptions(seed=SEED))
    pkg = os.path.join(out_dir, f"parity_cli_{dsm}.mbmap")
    manifest, result = build_package(Area(checks_core.LAT, checks_core.LON, checks_core.WIDTH, checks_core.HEIGHT),
                                     s, pkg, "parity")
    return manifest, result


def _blender_manifest(out_dir, mode):
    from map_builder.core.package import validate_package

    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    pkg = os.path.join(out_dir, f"parity_bl_{mode}.mbmap")
    s = bpy.context.scene.map_builder
    s.area_mode = "CENTER"
    s.centre_lat, s.centre_lon, s.width, s.height = (str(checks_core.LAT), str(checks_core.LON), checks_core.WIDTH,
                                                     checks_core.HEIGHT)
    s.elevation_source, s.elevation_file = "file", DEM
    s.elevation_crs, s.elevation_vertical_datum, s.elevation_license = "EPSG:4326", "SYNTHETIC", DEM_LICENSE
    s.osm_source, s.osm_file = "file", OSM
    s.terrain_spacing, s.heightfield_spacing, s.seed = 10.0, 10.0, SEED
    s.dsm_correction = mode
    s.package_name, s.export_path = "parity", pkg
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"parity[{mode}]: Blender generate ({err or 'ok'})")
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"parity[{mode}]: Blender export ({err or 'ok'})")
    result = validate_package(pkg)
    return (result.manifest or {"passage_probes": []}), result


def run(out_dir):
    s = bpy.context.scene.map_builder
    check(s.bl_rna.properties["seed"].default == SEED, "parity: the Blender seed default equals the CLI default (1)")
    from map_builder.blender.operators import make_area
    s.area_mode, s.centre_lat, s.centre_lon = "CENTER", "40.437", "-80.016"
    a = make_area(s)
    check((a.frame.lat0, a.frame.lon0) == (40.437, -80.016),
          f"parity: the centre keeps double precision ({a.frame.lat0}, {a.frame.lon0})")
    for lat, lon in ((40.437, -80.016), (0.0, 0.0), (47.0, 0.0), (0.0, 8.0)):
        for prop in ("lat", "lon", "centre_migrated"):
            s.property_unset(prop)
        s.centre_lat = s.centre_lon = ""
        s.lat, s.lon = lat, lon                                        # a .blend saved with the float centre
        try:
            a = make_area(s)
        except ValueError as e:
            check(False, f"parity: legacy centre ({lat}, {lon}) migrates ({e})")
            continue
        check(abs(a.frame.lat0 - lat) < 1e-5 and abs(a.frame.lon0 - lon) < 1e-5 and s.centre_migrated,
              f"parity: legacy float centre ({lat}, {lon}) migrates ({s.centre_lat!r}, {s.centre_lon!r})")
        s.centre_lat = ""                                              # cleared by the user: never revived
        try:
            make_area(s)
            check(False, "parity: a cleared centre is not revived from the legacy float")
        except ValueError:
            check(True, "parity: a cleared centre is not revived from the legacy float")
    for prop in ("lat", "lon", "centre_migrated"):
        s.property_unset(prop)
    for blender_mode, cli_mode in (("AUTO", None), ("ON", True)):
        cli, cli_result = _cli_manifest(out_dir, cli_mode)
        bl, bl_result = _blender_manifest(out_dir, blender_mode)
        want, got = _probe_set(cli), _probe_set(bl)
        check(len(want) > 0, f"parity[{blender_mode}]: the fixture emits passage probes (CLI {len(want)})")
        check(want == got, f"parity[{blender_mode}]: CLI and Blender probe sets are equal "
                           f"(CLI {[p[0] for p in want]} vs Blender {[p[0] for p in got]})")
        check(cli_result.ok and bl_result.ok, f"parity[{blender_mode}]: both packages validate")
