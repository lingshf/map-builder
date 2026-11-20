# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S2-F6 road sliver check: a needle road face that Blender's float32 storage turns over (z <= 0) is removed by
the generator. The minimal face from the headless Blender Pittsburgh build (osm:way/223360727) is put into a real
Blender mesh (float32 local vertices) at its float32 object location with the production scene builder, and baked
with the production export bake (``_bake_mesh_object``); the baked triangles are stored as package collision and
judged by the package validator's orientation rule. Unfiltered, the face is non-degenerate and fails the rule
although it faces up under the core's single rounding; after ``drop_unstorable_slivers`` the object passes."""

import bpy

from checks_core import check

LOC = (-523.3789280347364, 356.9213435776889, 137.46144136630159)
LOCAL = [(-60.29872537158792, 15.750370899771553, -17.523086199304828),
         (-60.29867578193023, 18.19219292867291, -18.14419343554107),
         (-60.29872537158792, 18.192159681263774, -18.144182253643237),
         (-55.0, 15.75, -17.5), (-55.0, 18.19, -18.1)]
TRIS = [(0, 1, 2), (0, 3, 4)]  # the sliver and a wide up-facing neighbour


def bake_road(name, tris):
    """(collision orientation problems, non-degenerate baked triangle count) of a road object built from
    LOCAL/``tris`` at LOC through the production scene builder and export bake."""
    from map_builder.blender import export as mb_export
    from map_builder.blender.scene_build import mesh_from_data
    from map_builder.core.collision import ColObject, is_degenerate, read_collision, write_collision
    from map_builder.core.mesh import MeshData
    from map_builder.core.package import collision_orientation_problems

    md = MeshData(name)
    for v in LOCAL:
        md.add_vertex(*v)
    for t in tris:
        md.add_face(t, "MB Road", (0.12, 0.12, 0.12))
    mats, meshes = [], []
    me = mesh_from_data(md, name, mats, meshes)
    ob = bpy.data.objects.new(name, me)
    ob.location = LOC
    bpy.context.scene.collection.objects.link(ob)
    try:
        deps = bpy.context.evaluated_depsgraph_get()
        baked = mb_export._bake_mesh_object(ob, deps, {}, [], {})
    finally:
        bpy.data.objects.remove(ob)
        for m in meshes:
            bpy.data.meshes.remove(m)
        for m in mats:
            bpy.data.materials.remove(m)
    col = read_collision(write_collision([ColObject(name, "osm:way/223360727", "road", baked.vertices,
                                                    baked.triangles)]))
    live = sum(1 for t in range(col.triangle_count) if not is_degenerate(*col.triangle(t)))
    return collision_orientation_problems(col), live


def run(out_dir):
    from map_builder.core import generate as gen
    from map_builder.core.collision import f32

    (ax, ay), (bx, by), (cx, cy) = ((f32(LOCAL[i][0] + LOC[0]), f32(LOCAL[i][1] + LOC[1])) for i in TRIS[0])
    check((bx - ax) * (cy - ay) - (by - ay) * (cx - ax) > 0, "slivers: the face is up-facing under single rounding")
    problems, live = bake_road("mb_sliver_unfiltered", TRIS)
    check(live == 2 and len(problems) == 1 and "does not point up" in problems[0],
          f"slivers: unfiltered Blender bake keeps the non-degenerate face and fails the road-normal rule ({problems})")
    kept, dropped = gen.drop_unstorable_slivers(LOCAL, TRIS, LOC)
    check(kept == [(0, 3, 4)] and len(dropped or ()) == 1, f"slivers: drop_unstorable_slivers drops it ({kept})")
    problems, live = bake_road("mb_sliver_filtered", kept or [])
    check(live == 1 and not problems, f"slivers: filtered Blender bake passes the road-normal rule ({problems})")
