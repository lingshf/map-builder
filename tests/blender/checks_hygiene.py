# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""S4-BLENDER-HYGIENE (D74, D88): the area bounding box is read in double precision, and the unmodified default
material is exported under its plain name.

* bbox: the panel's bounding box goes through the real ``make_area``; each edge of the resulting area is compared
  with the area ``Area.from_bbox`` builds from the typed doubles. The bbox properties were float32 (0.4 m at 48 N,
  0.6 m at 123 E); the threshold ``MAX_EDGE_ERROR_M`` is set from the pre-change table in the PR and stays below
  ``SMALLEST_FEATURE_M``, the smallest edge feature an area check here uses.
* material: a mesh with the unmodified default material is exported as "MB Default" exactly; a parameter variant
  keeps its digest suffix. Reports through ``checks_core.check``.
"""

import math

import bpy

from checks_core import check

SMALLEST_FEATURE_M = 0.5
MAX_EDGE_ERROR_M = 0.05
M_PER_DEG = 111_320.0
# (name, south, west, north, east) as typed, in degrees
BBOXES = (("munich", 48.13701, 11.57391, 48.14199, 11.57889),
          ("pittsburgh", 40.43401, -80.01901, 40.44099, -80.01299),
          ("48N far from origin", 48.70123, -123.45679, 48.70877, -123.44321))


def set_bbox(s, values):
    """Type the bbox the way the panel does: text, full precision."""
    for edge, v in zip(("south", "west", "north", "east"), values):
        setattr(s, f"bbox_{edge}_deg", repr(v))

def edge_errors_m(values):
    """Per-edge (south, west, north, east) distance in metres between the Blender-derived area and the area built
    from the typed doubles."""
    from map_builder.blender.operators import make_area
    from map_builder.core.geodesy import Area

    s = bpy.context.scene.map_builder
    s.area_mode = "BBOX"
    set_bbox(s, values)
    got = make_area(s).geographic_bbox()
    want = Area.from_bbox(*values).geographic_bbox()
    k = math.cos(math.radians(values[0]))
    return [abs(g - w) * M_PER_DEG * f for g, w, f in zip(got, want, (1, k, 1, k))]


def check_bbox():
    for name, *values in BBOXES:
        errs = edge_errors_m(values)
        print(f"bbox error m (S, W, N, E) {name}: " + ", ".join(f"{e:.4f}" for e in errs))
        check(max(errs) <= MAX_EDGE_ERROR_M < SMALLEST_FEATURE_M,
              f"hygiene: {name} bbox edges within {MAX_EDGE_ERROR_M} m of the double-precision area "
              f"(worst {max(errs):.4f} m)")


def check_bbox_migration():
    """A bbox stored by an older version (float32 properties) fills the empty text fields once, as stored."""
    from map_builder.blender.operators import make_area
    from map_builder.blender.sources import migrate_legacy_bbox

    s = bpy.context.scene.map_builder
    for edge in ("south", "west", "north", "east"):
        setattr(s, f"bbox_{edge}_deg", "")
    s.bbox_migrated = False
    s.area_mode = "BBOX"
    s.bbox_south, s.bbox_west, s.bbox_north, s.bbox_east = 40.434, -80.019, 40.441, -80.013
    got = make_area(s).geographic_bbox()      # make_area migrates on first access
    stored = [float(getattr(s, f"bbox_{e}")) for e in ("south", "west", "north", "east")]
    check([s.bbox_south_deg, s.bbox_east_deg] == [repr(stored[0]), repr(stored[3])] and s.bbox_migrated,
          f"hygiene: legacy float bbox migrates into the text fields as stored ({s.bbox_south_deg!r})")
    check(abs(got[0] - 40.434) < 1e-3 and abs(got[3] + 80.013) < 1e-3, "hygiene: migrated bbox builds the area")
    s.bbox_south_deg = ""
    check(not migrate_legacy_bbox(s) and s.bbox_south_deg == "", "hygiene: a cleared bbox field is not revived")


def check_default_material_name(out_dir):
    from map_builder.blender import export as mb_export

    def names_for(roughness):
        me = bpy.data.meshes.new("mb_hyg")
        me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        ob = bpy.data.objects.new("mb_hyg", me)
        bpy.context.scene.collection.objects.link(ob)
        mat = bpy.data.materials.new("MB Default")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = 0.0
        me.materials.append(mat)
        try:
            registry = {}
            mb_export._bake_mesh_object(ob, bpy.context.evaluated_depsgraph_get(), {}, [], registry)
            return sorted(mb_export._final_names(registry).values())
        finally:
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(me)
            bpy.data.materials.remove(mat)
    default = names_for(0.9)
    variant = names_for(0.5)
    check(default == ["MB Default"], f"hygiene: unmodified default material is exported as 'MB Default' ({default})")
    check(len(variant) == 1 and variant[0].startswith("MB Default ") and len(variant[0]) == len("MB Default ") + 8,
          f"hygiene: a parameter variant keeps the digest suffix ({variant})")


def run(out_dir):
    check_bbox()
    check_bbox_migration()
    check_default_material_name(out_dir)
