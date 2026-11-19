"""Create Blender data from a ScenePlan. Only adds new datablocks; never deletes user content.

Blender world space *is* the map frame (+X east, +Y north, +Z up, metres, z = H - z_offset_m), so plan
geometry and transforms are used as they are. Each generated object carries custom properties
``mb_id``, ``mb_class`` and ``mb_provenance`` (JSON); the map collection carries ``mb_map`` (JSON:
area, z offset, sources, generation report, generated ids). None of them contains credentials: source
entries come from the core, which reduces endpoints to their origin.
"""

import json

import bpy

from ..core.errors import MapBuilderError
from ..core.generate import MATERIALS
from ..core.glb import node_scale

COLOR_ATTR = "mb_color"
META_KEY = "mb_map"
META_VERSION = 1


def ensure_material(name, created=None):
    """The generated material ``name``; reuses an existing generated one (tagged ``mb_material``), never
    modifies or adopts a user material that happens to have the same name."""
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("mb_material") == name and mat.library is None:
        return mat
    mat = next((m for m in bpy.data.materials if m.get("mb_material") == name and m.library is None), None)
    if mat is not None:
        return mat
    base, rough, metal = MATERIALS.get(name, ((0.8, 0.8, 0.8), 0.9, 0.0))
    mat = bpy.data.materials.new(name)
    if created is not None:
        created.append(mat)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) or nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = COLOR_ATTR
    attr.location = (bsdf.location.x - 300, bsdf.location.y)
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    mat["mb_material"] = name
    return mat


def mesh_from_data(md, name=None, created_materials=None):
    """Blender mesh with exactly the plan's faces (the generator's closed, CCW-outward shells)."""
    me = bpy.data.meshes.new(name or md.name)
    me.from_pydata(md.vertices, [], md.faces)
    if me.validate(clean_customdata=False) or len(me.polygons) != len(md.faces):
        bpy.data.meshes.remove(me)
        raise MapBuilderError(f"generated mesh {md.name!r} was altered by Blender's mesh validation; "
                              "refusing to create a scene that differs from the plan")
    for m in md.materials:
        me.materials.append(ensure_material(m, created_materials))
    me.polygons.foreach_set("material_index", md.face_materials)
    attr = me.color_attributes.new(COLOR_ATTR, "FLOAT_COLOR", "CORNER")
    cols = []
    for poly in me.polygons:
        r, g, b = md.face_colors[poly.index]
        cols.extend((r, g, b, 1.0) * poly.loop_total)
    attr.data.foreach_set("color", cols)
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.active_color_index
    me.update()
    return me


def unique_collection_name(base):
    if base not in bpy.data.collections:
        return base
    k = 1
    while f"{base}.{k:03d}" in bpy.data.collections:
        k += 1
    return f"{base}.{k:03d}"


def build_scene(context, plan, sources, map_name):
    """Instantiate ``plan`` in a NEW collection linked to the scene. All datablocks are created first and
    linked last; if anything fails, the datablocks created here (and only those) are removed again, so a
    failed generation leaves the file as it was."""
    created_objects, created_meshes, created_colls, created_mats = [], [], [], []
    try:
        root = bpy.data.collections.new(unique_collection_name(f"MapBuilder {map_name}"))
        created_colls.append(root)
        subs = {}
        shared = {}
        generated = []
        for spec in plan.objects:
            coll = subs.get(spec.collection)
            if coll is None:
                coll = bpy.data.collections.new(f"{root.name} {spec.collection}")
                created_colls.append(coll)
                root.children.link(coll)
                subs[spec.collection] = coll
            if spec.mesh is not None:
                me = mesh_from_data(spec.mesh, spec.name, created_mats)
                created_meshes.append(me)
            else:  # instanced template (trees): one Blender mesh shared by its objects (linked duplicates)
                me = shared.get(spec.mesh_key)
                if me is None:
                    me = shared[spec.mesh_key] = mesh_from_data(plan.shared_meshes[spec.mesh_key], spec.mesh_key,
                                                                created_mats)
                    created_meshes.append(me)
            # Blender may suffix the name (".001") when another map is already in the file; identities
            # live in mb_id, so the object name only has to be unique, which Blender guarantees.
            ob = bpy.data.objects.new(spec.name, me)
            created_objects.append(ob)
            ob.location = tuple(float(c) for c in spec.location)
            ob.rotation_euler = (0.0, 0.0, float(spec.rotation_z))
            ob.scale = node_scale(spec.scale)
            ob["mb_id"] = spec.mb_id
            ob["mb_class"] = spec.mb_class
            ob["mb_provenance"] = json.dumps(spec.provenance, sort_keys=True)
            coll.objects.link(ob)
            generated.append(spec.mb_id)
        area = plan.area
        frame = area.frame
        meta = {
            "version": META_VERSION,
            "map_name": map_name,
            "area": {"lat": frame.lat0, "lon": frame.lon0, "width_m": area.width, "height_m": area.height},
            "z_offset_m": frame.z_offset,
            "sources": sources,
            "report": plan.report,
            "generated_ids": generated,
        }
        root[META_KEY] = json.dumps(meta, sort_keys=True, allow_nan=False)
        context.scene.collection.children.link(root)
    except BaseException:
        for ob in created_objects:
            bpy.data.objects.remove(ob)
        for me in created_meshes:
            bpy.data.meshes.remove(me)
        for c in reversed(created_colls):
            bpy.data.collections.remove(c)
        for m in created_mats:
            bpy.data.materials.remove(m)
        raise
    return root


def write_report_text(name, text):
    """Write the report to a Text block (only our own report Text is reused and overwritten)."""
    t = bpy.data.texts.get(name)
    if t is None or not t.get("mb_report"):
        t = bpy.data.texts.new(name)
        t["mb_report"] = True
    t.clear()
    t.write(text)
    return t
