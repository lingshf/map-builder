"""S2-ELEV checks: elevated building parts and building passages survive Blender edits (D21, D24).

Generates the synthetic fixture, then checks that (1) the split passage building exports lower parts and an upper
part with distinct ids and passing passage probes, (2) a duplicated upper part keeps distinct ids (the ``~`` rule),
and (3) moving the elevated part down onto the ground turns its probe into a validator warning, which is reported
and never hidden. Reports through ``checks_core.check``.
"""
import os

import bpy  # noqa: E402

import checks_core
from checks_core import FIXTURES, check, by_id, run_op, read_package

BUILDING = "osm:way/1095"
ELEVATED = "osm:way/1048"


def _configure(pkg):
    s = bpy.context.scene.map_builder
    s.area_mode = "CENTER"
    s.lat, s.lon, s.width, s.height = checks_core.LAT, checks_core.LON, checks_core.WIDTH, checks_core.HEIGHT
    s.elevation_source, s.elevation_file = "file", os.path.join(FIXTURES, "synthetic_dem.asc")
    s.elevation_crs, s.elevation_vertical_datum = "EPSG:4326", "SYNTHETIC"
    s.elevation_license = "SYNTHETIC test data (no licence required)"
    s.osm_source, s.osm_file = "file", os.path.join(FIXTURES, "synthetic_area.osm")
    s.terrain_spacing = 10.0
    s.package_name = "passages"
    s.export_path = pkg
    s.heightfield_spacing = 2.0
    return s


def run(out_dir):
    import map_builder
    from map_builder.core.package import validate_package

    map_builder.register()
    pkg = os.path.join(out_dir, "passages.mbmap")
    if os.path.exists(pkg):
        os.remove(pkg)
    s = _configure(pkg)
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"passages: generate ({err or 'ok'})")
    root = s.export_collection

    ids = {o.get("mb_id") for o in root.all_objects}
    parts = [f"{BUILDING}#{i}" for i in (1, 2, 3)]
    check(all(p in ids for p in parts) and BUILDING not in ids,
          "passages: the passage building is split into parts #1..#3")

    # duplicate of the upper part keeps distinct ids
    upper = by_id(root, parts[2])
    dup = upper.copy()
    dup.data = upper.data.copy()
    dup.location.y += 30.0
    upper.users_collection[0].objects.link(dup)
    # the elevated part moved onto the ground blocks its own probe
    elev = by_id(root, ELEVATED)
    elev.location.z -= 6.0
    bpy.context.view_layer.update()

    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"passages: export of the edited map ({err or 'ok'})")
    r = validate_package(pkg)
    check(r.ok, "passages: package validates: " + r.summary().splitlines()[0])
    _, col, _, _ = read_package(pkg)
    ents = {e["mb_id"] for e in col.objects}
    dup_id = f"{parts[2]}~{dup.name}"
    check(dup_id in ents and parts[2] in ents, f"passages: duplicated upper part has the distinct id {dup_id!r}")
    probes = {p["id"] for p in r.manifest["passage_probes"]}
    check(f"osm:way/1098:passage" in probes, "passages: the building passage probe is exported")
    check(any("passage probe" in w and "blocked" in w for w in r.warnings),
          "passages: the elevated part moved down blocks its probe, reported as a validator warning")
