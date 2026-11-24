# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""Create Blender data from a ScenePlan. Only adds new datablocks; never deletes user content.

Blender world space *is* the map frame (+X east, +Y north, +Z up, metres, z = H - z_offset_m), so plan
geometry and transforms are used as they are. Each generated object carries custom properties
``mb_id``, ``mb_class`` and ``mb_provenance`` (JSON); the map collection carries ``mb_map`` (JSON:
area, z offset, sources, generation report, generated ids). None of them contains credentials: source
entries come from the core, which reduces endpoints to their origin, and :func:`build_scene` checks all of
it with the core credential policy before creating anything.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

import bpy

from ..core import textures as tex
from ..core import uv as core_uv
from ..core import perf_counters
from ..core.errors import MapBuilderError
from ..core.generate import MATERIALS
from ..core.glb import node_scale
from ..core.mesh import UV, MeshData
from .sources import JsonMapping, check_persistable

if TYPE_CHECKING:
    import bpy.types

    from ..core.generate import ScenePlan

COLOR_ATTR = "mb_color"
UV_MAP = "UVMap"
META_KEY = "mb_map"
META_VERSION = 1

# Structure classes (bridge/tunnel/structure) go to their own sub-collections whatever the generator names;
# their materials are added to the generator's table here, so a structure feature needs no change elsewhere.
CLASS_COLLECTIONS: dict[str, str] = {"bridge": "Bridges", "tunnel": "Tunnels", "structure": "Structures"}
STRUCTURE_MATERIALS: dict[str, tuple[tuple[float, float, float], float, float]] = {
    "MB Concrete": ((0.8, 0.8, 0.8), 0.9, 0.0),   # deck sides, piers, headwalls
    "MB Tunnel": ((0.8, 0.8, 0.8), 0.95, 0.0),    # tube walls
}


def _is_generated(mat: bpy.types.Material, name: str, textured: bool) -> bool:
    return mat.get("mb_material") == name and mat.library is None and bool(mat.get("mb_textured")) == textured


def ensure_image(name: str, created_images: list[bpy.types.Image] | None = None,
                 cache: dict[str, bpy.types.Image] | None = None) -> bpy.types.Image:
    """The packed image of the texture of material ``name`` (PNG bytes from core/textures, never a file on
    disk); one datablock per PNG file, shared by materials that use the same file (concrete)."""
    fname = tex.TEXTURES[name][0]
    if cache is not None:
        cached = cache.get(fname)
        if cached is not None and cached.library is None:
            return cached
    img = next((i for i in bpy.data.images if i.get("mb_image") == fname and i.library is None), None)
    if img is not None:
        if cache is not None:
            cache[fname] = img
        return img
    fd, path = tempfile.mkstemp(suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(tex.load(name))
        img = bpy.data.images.load(path)
        if created_images is not None:
            created_images.append(img)
        img.name = f"mb_{fname}"
        img.pack()
        img.filepath = ""
        img["mb_image"] = fname
        if cache is not None:
            cache[fname] = img
    finally:
        os.remove(path)
    return img


def _textured_nodes(nt: bpy.types.NodeTree, bsdf: bpy.types.Node, name: str,
                    created_images: list[bpy.types.Image] | None, image_cache: dict[str, bpy.types.Image] | None) -> None:
    """Principled Base Color <- Mix(Multiply)(Image Texture, Mix(Divide)(Vertex Colour, texture mean albedo)).
    The divide is the viewport twin of the exporter's COLOR_0 compensation (core.uv), clamped to 1 like it."""
    x, y = bsdf.location.x, bsdf.location.y
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = COLOR_ATTR
    attr.location = (x - 900, y - 200)
    comp = nt.nodes.new("ShaderNodeMixRGB")
    comp.blend_type, comp.use_clamp = "DIVIDE", True
    comp.inputs["Fac"].default_value = 1.0
    comp.inputs["Color2"].default_value = (*core_uv.TEXTURE_MEAN_ALBEDO[name], 1.0)
    comp.location = (x - 700, y - 200)
    uvmap = nt.nodes.new("ShaderNodeUVMap")
    uvmap.uv_map = UV_MAP
    uvmap.location = (x - 900, y + 100)
    image = nt.nodes.new("ShaderNodeTexImage")
    image.image = ensure_image(name, created_images, image_cache)
    image.interpolation = "Linear"
    image.extension = "REPEAT"
    image.location = (x - 700, y + 100)
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 1.0
    mix.location = (x - 300, y)
    nt.links.new(uvmap.outputs["UV"], image.inputs["Vector"])
    nt.links.new(attr.outputs["Color"], comp.inputs["Color1"])
    nt.links.new(image.outputs["Color"], mix.inputs["Color1"])
    nt.links.new(comp.outputs["Color"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])


def ensure_material(name: str, created: list[bpy.types.Material] | None = None, textures: bool = False,
                    created_images: list[bpy.types.Image] | None = None,
                    cache: dict[tuple[str, bool], bpy.types.Material] | None = None,
                    image_cache: dict[str, bpy.types.Image] | None = None) -> bpy.types.Material:
    """The generated material ``name``; reuses an existing generated one (tagged ``mb_material``), never
    modifies or adopts a user material that happens to have the same name. ``textures`` builds the textured
    node tree for the materials of ``core.textures`` (the others are unaffected)."""
    textured = bool(textures) and name in tex.TEXTURES
    key = (name, textured)
    if cache is not None:
        cached = cache.get(key)
        if cached is not None and _is_generated(cached, name, textured):
            return cached
    mat = bpy.data.materials.get(name)
    if mat is not None and _is_generated(mat, name, textured):
        if cache is not None:
            cache[key] = mat
        return mat
    mat = next((m for m in bpy.data.materials if _is_generated(m, name, textured)), None)
    if mat is not None:
        if cache is not None:
            cache[key] = mat
        return mat
    if textured:   # the CLI writer's factors, so both paths emit the same material
        base, rough, metal = MATERIALS.get(name, ((0.8, 0.8, 0.8), tex.roughness(name), 0.0))
    else:
        base, rough, metal = STRUCTURE_MATERIALS.get(name) or MATERIALS.get(name, ((0.8, 0.8, 0.8), 0.9, 0.0))
    mat = bpy.data.materials.new(name)
    if created is not None:
        created.append(mat)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) or nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    if textured:
        _textured_nodes(nt, bsdf, name, created_images, image_cache)
        mat["mb_textured"] = True
    else:
        attr = nt.nodes.new("ShaderNodeVertexColor")
        attr.layer_name = COLOR_ATTR
        attr.location = (bsdf.location.x - 300, bsdf.location.y)
        nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    mat["mb_material"] = name
    if cache is not None:
        cache[key] = mat
    return mat


def uv_source(md: MeshData, origin: tuple[float, float, float]) -> MeshData | None:
    """``md`` with ``face_uvs`` from core/uv.py (the rule the CLI uses), or None if no face is textured.
    A copy: the plan's mesh is shared with collision and must not change."""
    out = MeshData(md.name)
    out.vertices, out.faces, out.face_materials, out.materials = md.vertices, md.faces, md.face_materials, md.materials
    core_uv.assign_uvs(out, origin)
    return out if out.face_uvs is not None else None


def mesh_from_data(md: MeshData, name: str | None, created_materials: list[bpy.types.Material],
                   created_meshes: list[bpy.types.Mesh], textures: bool = False,
                   origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
                   created_images: list[bpy.types.Image] | None = None,
                   material_cache: dict[tuple[str, bool], bpy.types.Material] | None = None,
                   image_cache: dict[str, bpy.types.Image] | None = None) -> bpy.types.Mesh:
    """Blender mesh with exactly the plan's faces (the generator's closed, CCW-outward shells).

    The new mesh is appended to ``created_meshes`` right after it is allocated (before anything that can
    fail), so the caller's single rollback path owns its removal; likewise new materials go to
    ``created_materials``.     The UV map (core/uv.py, ``origin`` = the object
        location) is always stored, even with Textures off, so a later export with Textures on matches the CLI;
        ``textures`` selects the textured materials."""
    me = bpy.data.meshes.new(name or md.name)
    created_meshes.append(me)
    if perf_counters.ENABLED:
        perf_counters.inc("bpy_mesh_vertices", len(md.vertices))
    me.from_pydata(md.vertices, [], md.faces)
    if me.validate(clean_customdata=False) or len(me.polygons) != len(md.faces):
        raise MapBuilderError(f"generated mesh {md.name!r} was altered by Blender's mesh validation; "
                              "refusing to create a scene that differs from the plan")
    for m in md.materials:
        me.materials.append(ensure_material(m, created_materials, textures, created_images, material_cache, image_cache))
    me.polygons.foreach_set("material_index", md.face_materials)
    uvsrc = uv_source(md, origin) if any(m in tex.TEXTURES for m in md.materials) else None
    if uvsrc is not None:
        flat: list[float] = []
        for face, fuv in zip(uvsrc.faces, cast("list[tuple[UV, ...] | None]", uvsrc.face_uvs)):  # uv_source only returns meshes with face_uvs
            for k in range(len(face)):
                flat.extend(fuv[k] if fuv is not None else (0.0, 0.0))
        if len(flat) != 2 * len(me.loops):
            raise MapBuilderError(f"generated mesh {md.name!r}: UV count does not match Blender's loops")
        layer = me.uv_layers.new(name=UV_MAP)
        layer.data.foreach_set("uv", flat)
    attr = me.color_attributes.new(COLOR_ATTR, "FLOAT_COLOR", "CORNER")
    cols: list[float] = []
    for poly in me.polygons:
        r, g, b = md.face_colors[poly.index]
        cols.extend((r, g, b, 1.0) * poly.loop_total)
    attr.data.foreach_set("color", cols)
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.active_color_index
    me.update()
    return me


def unique_collection_name(base: str) -> str:
    if base not in bpy.data.collections:
        return base
    k = 1
    while f"{base}.{k:03d}" in bpy.data.collections:
        k += 1
    return f"{base}.{k:03d}"


def build_scene(context: bpy.types.Context, plan: ScenePlan, sources: Sequence[JsonMapping],
                map_name: str, textures: bool = False) -> bpy.types.Collection:
    """Instantiate ``plan`` in a NEW collection linked to the scene. Everything that will be saved in the
    .blend (collection metadata, object names and provenance) is first checked with the core credential
    policy; then all datablocks are created and linked last. If anything fails, the datablocks created here
    (and only those) are removed again by one rollback path, so a failed generation leaves the file as it
    was."""
    area = plan.area
    frame = area.frame
    meta: dict[str, object] = {
        "version": META_VERSION,
        "map_name": map_name,
        "area": {"lat": frame.lat0, "lon": frame.lon0, "width_m": area.width, "height_m": area.height},
        "z_offset_m": frame.z_offset,
        "sources": sources,
        "report": plan.report,
        "generated_ids": [spec.mb_id for spec in plan.objects],
        "passage_probes": list(getattr(plan, "passage_probes", [])),
    }
    check_persistable({"collection_metadata": meta,
                       "objects": [{"name": spec.name, "mb_id": spec.mb_id, "mb_class": spec.mb_class,
                                    "collection": spec.collection, "provenance": spec.provenance}
                                   for spec in plan.objects]})
    meta_json = json.dumps(meta, sort_keys=True, allow_nan=False)
    created_objects: list[bpy.types.Object] = []
    created_meshes: list[bpy.types.Mesh] = []
    created_colls: list[bpy.types.Collection] = []
    created_mats: list[bpy.types.Material] = []
    created_images: list[bpy.types.Image] = []
    material_cache: dict[tuple[str, bool], bpy.types.Material] = {}
    image_cache: dict[str, bpy.types.Image] = {}
    try:
        root = bpy.data.collections.new(unique_collection_name(f"MapBuilder {map_name}"))
        created_colls.append(root)
        subs: dict[str, bpy.types.Collection] = {}
        shared: dict[str, bpy.types.Mesh] = {}
        for spec in plan.objects:
            coll_name = CLASS_COLLECTIONS.get(spec.mb_class, spec.collection)
            coll = subs.get(coll_name)
            if coll is None:
                coll = bpy.data.collections.new(f"{root.name} {coll_name}")
                created_colls.append(coll)
                root.children.link(coll)
                subs[coll_name] = coll
            if spec.mesh is not None:
                me = mesh_from_data(spec.mesh, spec.name, created_mats, created_meshes, textures, spec.location,
                                    created_images, material_cache, image_cache)
            else:  # instanced template (trees): one Blender mesh shared by its objects (linked duplicates)
                key = spec.mesh_key
                if key is None:
                    raise KeyError(key)
                me = shared.get(key)
                if me is None:
                    me = shared[key] = mesh_from_data(plan.shared_meshes[key], key, created_mats, created_meshes,
                                                      material_cache=material_cache, image_cache=image_cache)
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
        root[META_KEY] = meta_json
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
        for img in created_images:
            bpy.data.images.remove(img)
        raise
    return root


def write_report_text(name: str, text: str) -> bpy.types.Text:
    """Write the report to a Text block (only our own report Text is reused and overwritten)."""
    t = bpy.data.texts.get(name)
    if t is None or not t.get("mb_report"):
        t = bpy.data.texts.new(name)
        t["mb_report"] = True
    t.clear()
    t.write(text)
    return t
