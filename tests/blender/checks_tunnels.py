"""S1-TUNNEL checks: the fixture road tunnel (way/1072) is generated as a tunnel-class tube in the Tunnels
collection with its bore probe, and a mirrored (negative-scale) tunnel still exports as a valid package."""

import os

import bpy

from checks_core import FIXTURES, HEIGHT, LAT, LON, WIDTH, by_id, check, run_op

TUNNEL_ID = "osm:way/1072"


def run(out_dir):
    from map_builder.core.package import validate_package

    s = bpy.context.scene.map_builder
    pkg = os.path.join(out_dir, "tunnel.mbmap")
    s.area_mode = "CENTER"
    s.lat, s.lon, s.width, s.height = str(LAT), str(LON), WIDTH, HEIGHT
    s.elevation_source, s.elevation_file = "file", os.path.join(FIXTURES, "synthetic_dem.asc")
    s.elevation_crs, s.elevation_vertical_datum = "EPSG:4326", "SYNTHETIC"
    s.elevation_license = "SYNTHETIC test data (no licence required)"
    s.osm_source, s.osm_file = "file", os.path.join(FIXTURES, "synthetic_area.osm")
    s.terrain_spacing = 10.0
    s.package_name = "tunnel"
    s.export_path = pkg
    s.heightfield_spacing = 2.0
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"tunnel: generate ({err or 'ok'})")
    root = s.export_collection
    tube = by_id(root, TUNNEL_ID)
    check(tube.get("mb_class") == "tunnel" and any(c.name.endswith("Tunnels") or "Tunnels" in c.name
                                                   for c in tube.users_collection),
          "tunnel: fixture way/1072 is a tunnel-class object in a Tunnels collection")

    tube.scale = (-1.0, 1.0, 1.0)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"tunnel: export with a mirrored tunnel ({err or 'ok'})")
    r = validate_package(pkg)
    check(r.ok, f"tunnel: mirrored tunnel keeps the tube rule after bake (errors: {r.errors[:2]})")
