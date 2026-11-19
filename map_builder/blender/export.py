"""Export the user's FINAL edited map: depsgraph-evaluated meshes + world matrices -> validated package.

How it works (see bake.py for the GLB generation decision):

1. Collect the objects of the map collection (all nested collections), deduplicated by object identity
   (never by name; a linked and a local object sharing a name block the export). Objects reachable only
   through collections that are excluded/hidden in the view layer or disabled for rendering (the map
   collection's ancestors included), hidden/render-disabled objects, and geometry-less helpers (empties,
   lights, cameras...) are excluded and listed; curves, text,
   surfaces, metaballs, point clouds, volumes, grease pencil, instancing and particle systems are
   blocking errors (convert them to meshes first) -- nothing is guessed or silently dropped.
2. For every mesh object read the *evaluated* mesh (modifiers, shape keys and geometry nodes applied,
   via ``Object.evaluated_get(depsgraph).to_mesh()``), its loop triangles and ``matrix_world``.
   ``to_mesh`` creates a temporary mesh owned by the evaluated object, cleared right away; the user's
   objects, meshes, modifiers, selection and active object are never touched.
3. Bake to world space (= map frame) in bake.py, validate, and write GLB + collision from the same
   triangles via the core's atomic ``export_package`` (a failure keeps the previous package).
"""

import json
import math
import os
from array import array

import bpy

from ..core.errors import MapBuilderError
from ..core.geodesy import HARD_MAX_SIDE_M, Area
from ..core.pipeline import filter_passage_probes
from .bake import (DEFAULT_MATERIAL, WHITE, ExportError, bake_object, degenerate_count, export_baked,
                   export_name_clashes, outside_area, principled_omissions)
from .scene_build import META_KEY

UNSUPPORTED_TYPES = {"CURVE", "FONT", "SURFACE", "META", "CURVES", "POINTCLOUD", "VOLUME", "GPENCIL",
                     "GREASEPENCIL"}
IGNORED_TYPES = {"EMPTY", "LIGHT", "CAMERA", "SPEAKER", "LIGHT_PROBE", "LATTICE", "ARMATURE"}
ATTRIBUTE_NODES = {"VERTEX_COLOR", "ATTRIBUTE"}

__all__ = ["ExportError", "collect", "export_map", "find_map_root", "read_meta"]


def map_roots(scene):
    return [c for c in scene.collection.children_recursive if META_KEY in c]


def find_map_root(context, collection=None):
    """The map collection to export: ``collection`` if given, else the map collection containing the
    active collection, else the only map collection in the scene."""
    roots = map_roots(context.scene)
    if collection is not None:
        if META_KEY not in collection:
            raise MapBuilderError(f"collection {collection.name!r} is not a Map Builder map collection")
        return collection
    active = getattr(context, "collection", None)
    if active is not None:
        for r in roots:
            if active == r or active in r.children_recursive:
                return r
    if len(roots) == 1:
        return roots[0]
    if not roots:
        raise MapBuilderError("no Map Builder collection in this scene; generate a map first")
    raise MapBuilderError("several Map Builder collections exist; choose one as the export collection "
                          "(or make it active in the Outliner)")


def read_meta(root):
    try:
        meta = json.loads(root[META_KEY])
        a = meta["area"]
        area = Area(float(a["lat"]), float(a["lon"]), float(a["width_m"]), float(a["height_m"]),
                    max_side_m=HARD_MAX_SIDE_M)
        z = float(meta["z_offset_m"])
        if not math.isfinite(z):
            raise ValueError("z_offset_m is not finite")
        area.frame.z_offset = z
        if not isinstance(meta.get("generated_ids"), list) or not isinstance(meta.get("sources"), list):
            raise ValueError("generated_ids/sources missing")
        return meta, area
    except (KeyError, TypeError, ValueError, MapBuilderError) as e:
        raise MapBuilderError(f"collection {root.name!r} has invalid Map Builder metadata ({e}); "
                              "regenerate the map") from e


# --- materials ------------------------------------------------------------------------------------------

def _linked_from(sock):
    return sock.links[0].from_node if sock.is_linked and sock.links else None


def material_spec(mat):
    """(export name, (rgb, roughness, metallic), colour attribute name or None or "" (= render colour
    attribute), [warnings]) for a Blender material. Supported: a Principled BSDF whose Base Color is a
    constant or comes from a Color Attribute / Attribute node; anything else is approximated and warned,
    and every omitted Principled effect (emission, normal/bump, transmission, coat, sheen, subsurface,
    anisotropy, thin film, other node-driven inputs, volume/displacement) is named in a warning."""
    if mat is None:
        return DEFAULT_MATERIAL, None, None, ["empty material slot (exported with the default grey material)"]
    warnings = []
    name = mat.name if mat.library is None else f"{mat.name} [{os.path.basename(mat.library.filepath)}]"
    if not mat.use_nodes or mat.node_tree is None:
        rgb = tuple(float(c) for c in mat.diffuse_color[:3])
        return name, (rgb, float(mat.roughness), float(mat.metallic)), None, warnings
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
    bsdf = _linked_from(out.inputs["Surface"]) if out is not None else None
    if bsdf is None or bsdf.type != "BSDF_PRINCIPLED":
        kind = "nothing" if bsdf is None else bsdf.bl_label
        warnings.append(f"material {mat.name!r}: surface is {kind}, not a Principled BSDF; exported with its "
                        "viewport colour")
        rgb = tuple(float(c) for c in mat.diffuse_color[:3])
        return name, (rgb, float(mat.roughness), float(mat.metallic)), None, warnings
    base = bsdf.inputs["Base Color"]
    attr = None
    src = _linked_from(base)
    if src is None:
        rgb = tuple(float(c) for c in base.default_value[:3])
    elif (src.type in ATTRIBUTE_NODES and (src.type == "VERTEX_COLOR" or src.attribute_type == "GEOMETRY")
          and base.links[0].from_socket.identifier == "Color"):
        rgb = WHITE
        attr = src.layer_name if src.type == "VERTEX_COLOR" else src.attribute_name
    else:
        rgb = tuple(float(c) for c in base.default_value[:3])
        warnings.append(f"material {mat.name!r}: Base Color comes from a {src.bl_label} node output other than a "
                        "colour attribute's Color (textures, scalar outputs and node networks are not exported); "
                        "exported with the socket's constant colour")
    values = []
    for key in ("Roughness", "Metallic"):
        sock = bsdf.inputs[key]
        if sock.is_linked:
            warnings.append(f"material {mat.name!r}: {key} is driven by nodes; exported with its constant value")
        values.append(float(sock.default_value))
    alpha = bsdf.inputs.get("Alpha")
    if alpha is not None and (alpha.is_linked or alpha.default_value < 1.0):
        warnings.append(f"material {mat.name!r}: transparency is not exported (opaque)")
    sockets = {}
    for sock in bsdf.inputs:
        if getattr(sock, "enabled", True):
            v = getattr(sock, "default_value", None)
            sockets[sock.name] = (sock.is_linked, tuple(v) if hasattr(v, "__len__") else v)
    omitted = principled_omissions(sockets)
    omitted += [f"material output {key} driven by nodes" for key in ("Volume", "Displacement")
                if key in out.inputs and out.inputs[key].is_linked]
    if omitted:
        warnings.append(f"material {mat.name!r}: not exported (omitted): {', '.join(omitted)}")
    if not all(math.isfinite(v) for v in (*rgb, *values)):
        raise ExportError([f"material {mat.name!r}: non-finite colour/roughness/metallic"])
    return name, (rgb, values[0], values[1]), attr, warnings


def _color_reader(me, attr_name):
    """Function(tri_index) -> linear rgb averaged over the triangle's corners, or None if missing."""
    ca = me.color_attributes
    if attr_name:
        layer = ca.get(attr_name)
    else:
        idx = ca.render_color_index
        layer = ca[idx] if 0 <= idx < len(ca) else None
    if layer is None or layer.domain not in {"CORNER", "POINT"}:
        return None
    n = len(layer.data)
    buf = array("f", bytes(4 * 4 * n))
    layer.data.foreach_get("color", buf)
    corner = layer.domain == "CORNER"

    def read(tri_loops, tri_verts):
        idx = tri_loops if corner else tri_verts
        return tuple(sum(buf[4 * i + k] for i in idx) / 3.0 for k in range(3))

    return read


# --- collection & baking ---------------------------------------------------------------------------------

def _instancing_parents(depsgraph, pointers):
    found = set()
    for inst in depsgraph.object_instances:
        if inst.is_instance and inst.parent is not None:
            parent = inst.parent.original.as_pointer()
            if parent in pointers:
                found.add(parent)
    return found


def _collection_enabled(lc):
    """A layer collection whose content is rendered and visible: not excluded from the view layer, not
    hidden in it, and its collection neither disabled in viewports nor for rendering."""
    c = lc.collection
    return not (lc.exclude or lc.hide_viewport or c.hide_viewport or c.hide_render)


def collection_eligibility(view_layer, root):
    """(pointers of objects reachable through at least one fully enabled collection path from the scene
    collection *through* ``root``, {object pointer: sorted names of disabled collections on its paths},
    whether ``root`` itself is on an enabled path). Every path counts: a collection (and so an object)
    can be linked in several places; ancestors of ``root`` are part of the path."""
    root_ptr = root.as_pointer()
    eligible, blocked, root_enabled = set(), {}, False
    stack = [(view_layer.layer_collection, False)]
    while stack:
        lc, inside = stack.pop()
        here = lc.collection.as_pointer() == root_ptr
        if not _collection_enabled(lc):
            if inside or here or any(c.as_pointer() == root_ptr for c in lc.collection.children_recursive):
                for ob in lc.collection.all_objects:
                    blocked.setdefault(ob.as_pointer(), set()).add(lc.collection.name)
            continue
        inside = inside or here
        root_enabled = root_enabled or here
        if inside:
            eligible.update(ob.as_pointer() for ob in lc.collection.objects)
        stack.extend((child, inside) for child in lc.children)
    return eligible, {k: sorted(v) for k, v in blocked.items()}, root_enabled


def _label(ob):
    """Unambiguous object label for diagnostics (linked objects carry their library: 'Name [lib.blend]')."""
    return ob.name_full


def _export_material_name(mat_names, key, name):
    """Unique, deterministic export name per material datablock (``key``): distinct datablocks whose display
    names coincide (e.g. a linked 'X' from lib.blend and a local 'X [lib.blend]') get ' (2)', ' (3)', ... in
    first-seen order, so one never silently takes the other's factors. The default material's name is
    reserved."""
    if key in mat_names:
        return mat_names[key]
    taken = set(mat_names.values()) | {DEFAULT_MATERIAL}
    unique, k = name, 2
    while unique in taken:
        unique, k = f"{name} ({k})", k + 1
    mat_names[key] = unique
    return unique


def _bake_mesh_object(ob, depsgraph, materials, warnings, mat_names):
    ev = ob.evaluated_get(depsgraph)
    me = ev.to_mesh()
    try:
        me.calc_loop_triangles()
        nv, nt = len(me.vertices), len(me.loop_triangles)
        co = array("f", bytes(4 * 3 * nv))
        me.vertices.foreach_get("co", co)
        tv = array("i", bytes(4 * 3 * nt))
        me.loop_triangles.foreach_get("vertices", tv)
        tl = array("i", bytes(4 * 3 * nt))
        me.loop_triangles.foreach_get("loops", tl)
        tm = array("i", bytes(4 * nt))
        me.loop_triangles.foreach_get("material_index", tm)
        verts = [(co[3 * i], co[3 * i + 1], co[3 * i + 2]) for i in range(nv)]
        tris = [(tv[3 * t], tv[3 * t + 1], tv[3 * t + 2]) for t in range(nt)]
        slot_specs = []
        if not len(ev.material_slots):
            warnings.append(f"{ob.name}: no material (exported with the default grey material)")
            slot_specs.append((DEFAULT_MATERIAL, None))
        for slot in ev.material_slots:
            mname, spec, attr, mwarn = material_spec(slot.material)
            if spec is not None:
                mname = _export_material_name(mat_names, slot.material.as_pointer(), mname)
                materials.setdefault(mname, spec)
            reader = None
            if attr is not None:
                reader = _color_reader(me, attr)
                if reader is None:
                    mwarn = mwarn + [f"material {mname!r} reads colour attribute {attr or '(render)'!r}, which "
                                     "this mesh lacks; exported white"]
            for w in mwarn:
                warnings.append(f"{ob.name}: {w}")
            slot_specs.append((mname, reader))
        tri_mats, tri_cols = [], []
        last = len(slot_specs) - 1
        for t in range(nt):
            mname, reader = slot_specs[min(max(tm[t], 0), last)]
            tri_mats.append(mname)
            tri_cols.append(reader(tl[3 * t:3 * t + 3], tv[3 * t:3 * t + 3]) if reader else WHITE)
        matrix = [list(row) for row in ev.matrix_world]
        loose_edges = sum(1 for e in me.edges if e.is_loose) if nt else 0
    finally:
        ev.to_mesh_clear()
    prov_raw = ob.get("mb_provenance")
    try:
        prov = json.loads(prov_raw) if isinstance(prov_raw, str) and prov_raw else {}
        if not isinstance(prov, dict):
            raise ValueError
    except ValueError:
        prov = {}
        warnings.append(f"{ob.name}: unreadable mb_provenance property (ignored)")
    mb_id, mb_class = ob.get("mb_id"), ob.get("mb_class")
    baked = bake_object(ob.name, verts, tris, matrix, tri_mats, tri_cols,
                        mb_id=mb_id if isinstance(mb_id, str) else None,
                        mb_class=mb_class if isinstance(mb_class, str) else None, provenance=prov)
    if baked.unused_vertices or loose_edges:
        warnings.append(f"{ob.name}: {baked.unused_vertices} loose vertex(es) / {loose_edges} loose edge(s) "
                        "without faces are not exported")
    return baked


def collect(context, root, depsgraph, area=None, generated_ids=()):
    """Bake the map collection. Returns (baked objects, materials, export report). Raises ExportError
    listing every blocking problem (nothing is written in that case).

    Objects are deduplicated by identity (an object linked in several collections is exported once), never
    by name: a linked library object and a local object may share a name, which blocks the export (see
    :func:`export_name_clashes`). An object is exported only if at least one collection path from the
    scene collection through the map collection is enabled in the view layer (not excluded, hidden or
    disabled for rendering, ancestors included) and the object itself is visible and render-enabled;
    excluded objects are listed in the report."""
    errors, warnings, excluded = [], [], []
    view_layer = context.view_layer
    generated = set(generated_ids)
    unique = {}
    for ob in root.all_objects:
        unique.setdefault(ob.as_pointer(), ob)
    objects = sorted(unique.values(), key=lambda o: (o.name, o.name_full))
    eligible, blocked, root_enabled = collection_eligibility(view_layer, root)
    if not root_enabled:
        why = (f"it or a parent collection ({', '.join(sorted(set(n for v in blocked.values() for n in v)))}) is "
               "excluded from the view layer, hidden, or disabled for rendering") if blocked else \
            "it is not linked into this scene"
        raise ExportError([f"map collection {root.name!r} is not enabled in view layer {view_layer.name!r}: {why}"])
    instancers = _instancing_parents(depsgraph, set(unique))
    baked, materials, names = [], {}, []
    mat_names = {}                              # material datablock pointer -> unique export name
    for ob in objects:
        ptr = ob.as_pointer()
        reason = None
        if ptr not in eligible:
            reason = (f"only in collection(s) excluded, hidden or disabled for rendering "
                      f"({', '.join(blocked.get(ptr, [])) or 'outside the enabled map collections'})")
        elif not ob.visible_get(view_layer=view_layer) or ob.hide_render:
            reason = "hidden in the viewport or disabled for rendering"
        if reason:
            excluded.append({"object": _label(ob), "reason": reason})
            if ob.get("mb_id") in generated:
                warnings.append(f"{_label(ob)}: hidden generated object is not exported and counts as removed")
            continue
        if ob.type in UNSUPPORTED_TYPES:
            errors.append(f"{_label(ob)}: {ob.type} objects cannot be exported; convert to a mesh "
                          "(Object > Convert > Mesh), or hide or delete it")
            continue
        if ob.type in IGNORED_TYPES:
            if ptr in instancers or ob.instance_type != "NONE":
                errors.append(f"{_label(ob)}: instancing ({ob.instance_type}) is not supported; use "
                              "Object > Apply > Make Instances Real")
            else:
                excluded.append({"object": _label(ob), "reason": f"{ob.type} has no geometry"})
            continue
        if ob.type != "MESH":
            errors.append(f"{_label(ob)}: unsupported object type {ob.type}")
            continue
        if len(ob.particle_systems):
            errors.append(f"{_label(ob)}: particle systems are not supported; convert them "
                          "(Object > Apply > Make Instances Real / Convert) or remove them")
            continue
        if ptr in instancers or ob.instance_type != "NONE":
            errors.append(f"{_label(ob)}: instancing (instance type {ob.instance_type} or geometry-node "
                          "instances) is not supported; use Object > Apply > Make Instances Real or "
                          "add a Realize Instances node")
            continue
        try:
            b = _bake_mesh_object(ob, depsgraph, materials, warnings, mat_names)
        except ExportError as e:
            errors.extend(e.errors)
            continue
        if not b.triangles:
            excluded.append({"object": _label(ob), "reason": "evaluated mesh has no faces"})
            warnings.append(f"{_label(ob)}: evaluated mesh has no faces; not exported")
            continue
        d = degenerate_count(b)
        if d:
            warnings.append(f"{ob.name}: {d} degenerate (zero-area) triangle(s)")
        if area is not None and outside_area(b, area):
            warnings.append(f"{ob.name}: extends outside the map area")
        baked.append(b)
        names.append((ob.name, _label(ob)))
    errors.extend(export_name_clashes(names))
    if not baked and not errors:
        errors.append("nothing to export: no visible mesh objects with faces in the map collection"
                      + (f" ({len(excluded)} object(s) excluded: "
                         + "; ".join(f"{e['object']}: {e['reason']}" for e in excluded[:5])
                         + (" ..." if len(excluded) > 5 else "") + ")" if excluded else ""))
    if errors:
        raise ExportError(errors)
    report = {"warnings": warnings, "excluded_objects": excluded,
              "mirrored_objects": [b.name for b in baked if b.mirrored],
              "objects": len(baked), "triangles": sum(len(b.triangles) for b in baked),
              "geometry": "depsgraph-evaluated meshes (modifiers applied) in world space; GLB and collision "
                          "share the same triangles"}
    return baked, materials, report


def resolve_path(path):
    if not path:
        raise MapBuilderError("no export path set")
    if path.startswith("//") and not bpy.data.filepath:
        raise MapBuilderError("the export path is relative to the .blend file ('//...'), but the file has not "
                              "been saved; save the .blend or choose an absolute path")
    out = os.path.abspath(bpy.path.abspath(path))
    if os.path.isdir(out):
        raise MapBuilderError(f"export path {out!r} is a directory; choose a .mbmap file name")
    return out


def export_map(context, path, name, heightfield_spacing=0.0, root=None):
    """Export the map collection to ``path``. Returns (manifest, ValidationResult, report, edits) where
    ``report`` is the package report (generation report + ``blender_export`` diagnostics + ``edits``).
    Raises ExportError / MapBuilderError (incl. PackageError); the previous package then stays as it was."""
    out = resolve_path(path)
    root = root or find_map_root(context)
    meta, area = read_meta(root)
    depsgraph = context.evaluated_depsgraph_get()
    baked, materials, export_report = collect(context, root, depsgraph, area, meta["generated_ids"])
    report = json.loads(json.dumps(meta.get("report", {})))   # deep copy; never mutate the stored metadata
    report["warnings"] = list(report.get("warnings", [])) + export_report["warnings"]
    report["blender_export"] = export_report
    parent = os.path.dirname(out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    probes = meta.get("passage_probes", [])
    manifest, result, edits = export_baked(out, name, area, meta["sources"], baked, meta["generated_ids"],
                                           materials, report, blender_version=bpy.app.version_string,
                                           heightfield_spacing=heightfield_spacing or None,
                                           passage_probes=probes)
    report["edits"] = edits
    report["passage_probes_dropped"] = filter_passage_probes(probes, (o["mb_id"] for o in manifest["objects"]))[1]
    return manifest, result, report, edits
