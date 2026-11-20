# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Bridge checks of the headless Blender integration test (S1-BRIDGE).

Run by ``run_integration.py`` after the core checks. Part 1 generates the SYNTHETIC fixture and expects its
free-standing footway bridge as a ``bridge`` object (VALID, ``deck`` probe). Part 2 generates a hand-built
SYNTHETIC valley crossing (a secondary road bridging a 40 m valley) that has an ``under`` probe, exports it and
validates, then moves the deck DOWN onto the valley floor and checks that exactly that ``under`` probe (by its
manifest index) becomes a validator warning, not an error.
"""

import json
import os
import re
import zipfile

import bpy

from checks_core import FIXTURES, LAT, LON, check, run_op


def _valley_height(x):
    return min(15.0, max(0.0, (abs(x) - 20.0) * 0.75))


def _write_valley(out_dir):
    """A SYNTHETIC DEM (valley along y) and OSM (road bridge over it) around the check area centre."""
    from map_builder.core.geodesy import LocalFrame

    frame = LocalFrame(LAT, LON)
    cell = 0.00005
    lat0, lon0 = LAT - 0.0012, LON - 0.0020
    ncols, nrows = 81, 49
    rows = []
    for r in range(nrows):
        lat = lat0 + (nrows - 1 - r) * cell
        rows.append(" ".join(f"{_valley_height(frame.to_local(lat, lon0 + c * cell)[0]):.3f}" for c in range(ncols)))
    dem = os.path.join(out_dir, "valley.asc")
    with open(dem, "w", encoding="utf-8") as f:
        f.write(f"ncols {ncols}\nnrows {nrows}\nxllcenter {lon0}\nyllcenter {lat0}\ncellsize {cell}\n"
                "NODATA_value -9999\n" + "\n".join(rows) + "\n")
    nodes, ways, nid = [], [], 1000

    def way(pts, tags):
        nonlocal nid
        refs = []
        for x, y in pts:
            nid += 1
            lat, lon = frame.to_geographic(x, y)
            nodes.append(f'<node id="{nid}" lat="{lat:.9f}" lon="{lon:.9f}"/>')
            refs.append(nid)
        nid += 1
        ways.append(f'<way id="{nid}">' + "".join(f'<nd ref="{r}"/>' for r in refs)
                    + "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items()) + "</way>")

    way([(-100, 0), (-45, 0)], {"highway": "secondary"})
    way([(45, 0), (100, 0)], {"highway": "secondary"})
    way([(-45, 0), (0, 0), (45, 0)], {"highway": "secondary", "bridge": "yes"})
    osm = os.path.join(out_dir, "valley.osm")
    with open(osm, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="SYNTHETIC test">\n'
                + "\n".join(nodes + ways) + "\n</osm>\n")
    return dem, osm


def run(out_dir):
    from map_builder.core.package import validate_package

    pkg = os.path.join(out_dir, "bridges.mbmap")
    s = bpy.context.scene.map_builder
    s.elevation_source, s.elevation_file = "file", os.path.join(FIXTURES, "synthetic_dem.asc")
    s.osm_source, s.osm_file = "file", os.path.join(FIXTURES, "synthetic_area.osm")
    s.export_path = pkg
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"bridges: generate fixture ({err or 'ok'})")
    decks = [o for o in s.export_collection.all_objects if o.get("mb_class") == "bridge"]
    check(len(decks) >= 1, f"bridges: fixture footway bridge generated as class 'bridge' ({len(decks)})")
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"bridges: export fixture ({err or 'ok'})")
    r = validate_package(pkg)
    check(r.ok and not [w for w in r.warnings if "probe" in w], "bridges: fixture package VALID, no probe warning")

    # valley crossing: has the conditional ``under`` probe (clearance >= 4 m)
    dem, osm = _write_valley(out_dir)
    s.area_mode = "CENTER"
    s.centre_lat, s.centre_lon, s.width, s.height = str(LAT), str(LON), 200.0, 100.0
    s.elevation_source, s.elevation_file = "file", dem
    s.osm_source, s.osm_file = "file", osm
    s.export_path = pkg
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"bridges: generate valley ({err or 'ok'})")
    decks = [o for o in s.export_collection.all_objects if o.get("mb_class") == "bridge"]
    check(len(decks) == 1, f"bridges: valley bridge generated ({len(decks)})")
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"bridges: export valley ({err or 'ok'})")
    r = validate_package(pkg)
    with zipfile.ZipFile(pkg) as z:
        probes = json.loads(z.read("manifest.json")).get("passage_probes", [])
    under = [i for i, p in enumerate(probes) if p["id"].endswith(":under")]
    check(len(under) == 1, f"bridges: valley manifest carries one under probe ({[p['id'] for p in probes]})")
    idx = under[0] if under else -1
    check(r.ok and not [w for w in r.warnings if "probe" in w],
          f"bridges: valley package VALID, no probe warning ({[w for w in r.warnings if 'probe' in w][:1]})")

    # lower the deck onto the valley floor: the under probe's capsule now meets the deck
    for d in decks:
        d.location.z -= 12.0
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"bridges: export after lowering the deck ({err or 'ok'})")
    r = validate_package(pkg)
    named = [w for w in r.warnings if re.search(rf"passage probe {idx}\b", w)]
    check(r.ok, f"bridges: a lowered deck is still VALID (errors {r.errors[:1]})")
    check(len(named) == 1, f"bridges: the lowered deck makes exactly the under probe (index {idx}) a warning "
                           f"({named[:1]}; all {[w for w in r.warnings if 'probe' in w]})")
    for d in decks:
        d.location.z += 12.0
