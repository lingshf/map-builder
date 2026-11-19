"""Core checks of the headless Blender integration test for the Map Builder add-on (Blender 4.2 LTS).

Run through ``run_integration.py`` (which also runs the optional ``checks_*.py`` feature modules):

    blender --background --factory-startup --python tests/blender/run_integration.py -- <out_dir>

Uses only the local SYNTHETIC fixtures (tests/fixtures; no network). Registers the add-on from this
repository, generates through the Generate operator, edits the scene like a user (move/rotate/
non-uniform scale, delete, duplicate, Array modifier, negative-scale mirror, user cube with Bevel,
terrain vertex edit), exports through the Export operator and checks the validated package against
the evaluated scene. Then checks that inherited collection restrictions (render-disabled parents,
view-layer exclude/hide) exclude and list objects, that a linked library object sharing a name with a
local one blocks the export, that omitted Principled effects are named, that invalid scenes (curve
object, zero scale, non-closed building) fail without touching the previous package or the report
Text, that failed generations (forced mid-build failure, credential-like inputs) roll back completely,
that offline network sources fail clearly, and that no
credential reaches the .blend file. Exit code 0 = pass; non-zero with a FAIL list otherwise.

The file name deliberately does not match unittest's ``test*.py`` pattern (and tests/blender has no
__init__.py), so ``python -m unittest discover -s tests`` never imports bpy.
"""

import hashlib
import json
import math
import os
import sys
import tempfile
import traceback
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

import bpy  # noqa: E402

FIXTURES = os.path.join(REPO, "tests", "fixtures")
LAT, LON, WIDTH, HEIGHT = 47.0, 8.0, 400.0, 300.0
FAILURES = []
TOL = 1e-4


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILURES.append(msg)


def run_op(op):
    """Operator result; in background mode an operator that reports ERROR raises RuntimeError."""
    try:
        return op(), None
    except RuntimeError as e:
        return {"CANCELLED"}, str(e)


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def by_id(root, mb_id):
    return next(o for o in root.all_objects if o.get("mb_id") == mb_id)


def world_triangles(ob):
    """Evaluated (modifiers applied) world-space triangles, CCW outward (flipped for mirrored matrices)."""
    deps = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        me.calc_loop_triangles()
        mw = ev.matrix_world.copy()
        pts = [mw @ v.co for v in me.vertices]
        tris = [tuple(t.vertices) for t in me.loop_triangles]
    finally:
        ev.to_mesh_clear()
    if mw.determinant() < 0:
        tris = [(a, c, b) for a, b, c in tris]
    return [tuple(tuple(pts[i]) for i in t) for t in tris]


def signed_volume(tris):
    v = 0.0
    for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in tris:
        v += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return v / 6.0


def scene_state():
    """Everything export must leave untouched."""
    vl = bpy.context.view_layer
    state = {"objects": sorted(o.name for o in bpy.data.objects), "meshes": len(bpy.data.meshes),
             "materials": len(bpy.data.materials), "collections": len(bpy.data.collections),
             "selected": sorted(o.name for o in vl.objects if o.select_get()),
             "active": vl.objects.active.name if vl.objects.active else None, "per_object": {}}
    for o in bpy.data.objects:
        h = hashlib.sha256()
        if o.type == "MESH":
            for v in o.data.vertices:
                h.update(repr(tuple(round(c, 7) for c in v.co)).encode())
            h.update(repr([tuple(p.vertices) for p in o.data.polygons]).encode())
        state["per_object"][o.name] = (o.data.name if o.data else None, h.hexdigest(),
                                       [(m.name, m.type, m.show_viewport) for m in o.modifiers],
                                       [tuple(round(c, 7) for c in row) for row in o.matrix_world],
                                       o.hide_get(), o.get("mb_id"))
    return state


def read_package(path):
    from map_builder.core.collision import read_collision
    from map_builder.core.glb import read_glb
    with zipfile.ZipFile(path) as z:
        report = json.loads(z.read("report.json"))
        col = read_collision(z.read("collision/map.mbcol"))
        _, nodes = read_glb(z.read("visual/map.glb"))
        names = z.namelist()
    return report, col, nodes, names


def run(out_dir):
    import map_builder
    from map_builder.core.collision import CLASSES
    from map_builder.core.geodesy import gltf_to_map
    from map_builder.core.package import validate_package

    map_builder.register()
    pkg = os.path.join(out_dir, "it.mbmap")
    for stale in (pkg,):
        if os.path.exists(stale):
            os.remove(stale)
    s = bpy.context.scene.map_builder
    s.area_mode = "CENTER"
    s.lat, s.lon, s.width, s.height = LAT, LON, WIDTH, HEIGHT
    s.elevation_source, s.elevation_file = "file", os.path.join(FIXTURES, "synthetic_dem.asc")
    s.elevation_crs, s.elevation_vertical_datum = "EPSG:4326", "SYNTHETIC"
    s.elevation_license = "SYNTHETIC test data (no licence required)"
    s.osm_source, s.osm_file = "file", os.path.join(FIXTURES, "synthetic_area.osm")
    s.terrain_spacing = 10.0
    s.package_name = "it"
    s.export_path = pkg
    s.heightfield_spacing = 2.0

    # a user object that exists before generation must survive it untouched
    pre = bpy.data.objects.new("pre_existing_empty", None)
    bpy.context.scene.collection.objects.link(pre)
    n_colls = len(bpy.context.scene.collection.children)

    # --- generate ----------------------------------------------------------------------------------
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"generate from local fixtures ({err or 'ok'})")
    root = s.export_collection
    check(root is not None and "mb_map" in root, "generate created a map collection and selected it for export")
    check(len(bpy.context.scene.collection.children) == n_colls + 1, "generate added exactly one new collection")
    check("pre_existing_empty" in bpy.data.objects, "pre-existing user content kept")
    meta = json.loads(root["mb_map"])
    gen = [o for o in root.all_objects if o.type == "MESH"]
    check(len(gen) > 10 and all(isinstance(o.get("mb_id"), str) and o.get("mb_class") in CLASSES for o in gen),
          f"all {len(gen)} generated objects carry mb_id and a valid mb_class")
    check(sorted(meta["generated_ids"]) == sorted(o["mb_id"] for o in gen), "generated ids stored in the collection")
    txt = bpy.data.texts.get("MapBuilder Report")
    body = txt.as_string() if txt else ""
    for needle in ("SOURCES, LICENCES AND ATTRIBUTION", "OpenStreetMap", "SYNTHETIC", "UNSUPPORTED FEATURES",
                   "INVALID FEATURES", "WARNINGS", "resampled_spacing_m"):
        check(needle in body, f"report Text mentions {needle!r}")

    # --- failed generations leave the file (datablocks and the report Text) exactly as it was ----------
    from map_builder.blender import operators as mb_ops
    from map_builder.blender import scene_build
    from map_builder.core.errors import MapBuilderError

    def counts():
        return (len(bpy.data.meshes), len(bpy.data.objects), len(bpy.data.materials), len(bpy.data.collections),
                len(bpy.data.texts))

    def forced_failure(*args, **kwargs):
        raise MapBuilderError("forced material failure (test)")

    before = counts()
    real_ensure = scene_build.ensure_material
    scene_build.ensure_material = forced_failure     # fails right after the first mesh is allocated
    try:
        res, err = run_op(bpy.ops.map_builder.generate)
    finally:
        scene_build.ensure_material = real_ensure
    check(res == {"CANCELLED"} and "forced material failure" in (err or ""), "forced mid-build failure cancels")
    check(counts() == before, f"failed generation rolled back its meshes/objects/materials/collections "
                              f"{before} -> {counts()}")
    check(bpy.data.texts["MapBuilder Report"].as_string() == body, "failed generation left the report Text untouched")

    dummy = "DUMMY-TOKEN-0000"
    leak = f"SYNTHETIC, terms https://user:{dummy}@licence.invalid/terms"
    good_lic = s.elevation_license
    s.elevation_license = leak
    check(s.elevation_license == "" and s.credential_notice.startswith("Licence:")
          and dummy not in s.credential_notice, "credential typed into Licence is cleared before it can be saved")
    s.elevation_license = good_lic
    check(s.credential_notice == "", "notice cleared by a clean value")
    s["elevation_license"] = leak                    # raw custom property: bypasses the update callback
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"CANCELLED"} and "Licence" in (err or "") and dummy not in (err or "")
          and "licence.invalid" not in (err or ""), "credential in Licence rejects generation, naming the field only")
    check(counts() == before and bpy.data.texts["MapBuilder Report"].as_string() == body,
          "credential rejection created nothing and left the report Text untouched")
    s.elevation_license = good_lic

    real_plan = mb_ops.generate_plan

    def leaky_plan(area, settings, progress=None):
        plan, sources = real_plan(area, settings, progress=progress)
        return plan, sources + [{"kind": "features", "attribution": f"see x?api_key={dummy}"}]

    mb_ops.generate_plan = leaky_plan
    try:
        res, err = run_op(bpy.ops.map_builder.generate)
    finally:
        mb_ops.generate_plan = real_plan
    check(res == {"CANCELLED"} and "generated scene data" in (err or "") and dummy not in (err or ""),
          "credential-like source data is rejected before anything is persisted")
    check(counts() == before and bpy.data.texts["MapBuilder Report"].as_string() == body,
          "rejected source data created nothing and left the report Text untouched")

    # --- user edits ----------------------------------------------------------------------------------
    moved = by_id(root, "osm:way/1007")
    moved.location.x += 20.0
    moved.location.y -= 5.0
    moved.rotation_euler = (0.05, -0.03, moved.rotation_euler.z + 0.4)
    moved.scale = (1.3, 0.8, 1.5)
    deleted_id = "osm:way/1023"
    bpy.data.objects.remove(by_id(root, deleted_id))
    src = by_id(root, "osm:way/1028")
    dup = src.copy()
    dup.data = src.data.copy()
    dup.location.y += 25.0
    src.users_collection[0].objects.link(dup)
    arr = by_id(root, "osm:way/1033")
    arr_tris_before = len(world_triangles(arr))
    mod = arr.modifiers.new("array", "ARRAY")
    mod.count = 2
    mod.relative_offset_displace = (1.5, 0.0, 0.0)
    mirrored = by_id(root, "osm:way/1038")
    mirrored.scale = (-1.0, 1.0, 1.0)
    me = bpy.data.meshes.new("user_box")
    me.from_pydata([(0, 0, 0), (3, 0, 0), (3, 2, 0), (0, 2, 0), (0, 0, 5), (3, 0, 5), (3, 2, 5), (0, 2, 5)], [],
                   [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
    user = bpy.data.objects.new("user_box", me)
    user.location = (-150.0, 120.0, 30.0)
    bev = user.modifiers.new("bevel", "BEVEL")
    bev.width = 0.2
    bev.segments = 2
    root.objects.link(user)
    terrain = next(o for o in root.all_objects if o.get("mb_class") == "terrain")
    terrain.data.vertices[len(terrain.data.vertices) // 2].co.z += 15.0
    terrain.data.update()
    # selection / active state the export must not change
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    moved.select_set(True)
    user.select_set(True)
    vl.objects.active = mirrored
    vl.update()

    # --- export ---------------------------------------------------------------------------------------
    before = scene_state()
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"export of the edited map ({err or 'ok'})")
    check(scene_state() == before, "export left the scene unchanged (objects, meshes, modifiers, matrices, "
                                   "selection, active object)")
    r = validate_package(pkg)
    check(r.ok, "validate_package: " + r.summary().splitlines()[0])
    report, col, nodes, names = read_package(pkg)
    m = r.manifest
    ents = {e["mb_id"]: e for e in col.objects}
    by_name = {e["name"]: e for e in col.objects}

    want = world_triangles(moved)
    got = col.object_triangles(ents["osm:way/1007"])
    err_max = max((abs(a - b) for tw, tg in zip(want, got) for pw, pg in zip(tw, tg) for a, b in zip(pw, pg)),
                  default=math.inf)
    check(len(want) == len(got) and err_max <= TOL,
          f"moved/rotated/scaled building: collision == evaluated world triangles ({len(got)} tris, "
          f"max err {err_max:.2e} m)")
    check(deleted_id not in ents and deleted_id in report["edits"]["removed"] and m["edits"]["removed"] == 1,
          "deleted building reported in edits.removed and absent from collision")
    dup_id = f"osm:way/1028~{dup.name}"
    check(dup_id in ents and "osm:way/1028" in ents and ents[dup_id]["name"] == dup.name,
          f"duplicate has the distinct derived id {dup_id!r}, original keeps its id")
    check(any(d["object"] == dup.name for d in report["edits"]["duplicated"]), "duplicate reported in edits")
    ue = ents.get(f"user:{user.name}")
    check(ue is not None and ue["class"] == "user" and user.name in report["edits"]["user_added"],
          "user cube exported as user:<name> with class 'user'")
    check(ue is not None and ue["tri_count"] > 12, f"Bevel modifier geometry exported ({ue and ue['tri_count']} tris)")
    ae = ents["osm:way/1033"]
    check(ae["tri_count"] == 2 * arr_tris_before, f"Array modifier doubles the building's collision triangles "
                                                  f"({arr_tris_before} -> {ae['tri_count']})")
    me_ = ents["osm:way/1038"]
    vol_c = signed_volume(col.object_triangles(me_))
    node = next(n for n in nodes if n.name == mirrored.name)
    vol_v = signed_volume([tuple(gltf_to_map(p) for p in t) for t in node.triangles])
    check(vol_c > 0 and abs(vol_v - vol_c) <= 1e-3 * abs(vol_c),
          f"mirrored building is outward-wound in collision ({vol_c:.2f}) and visuals ({vol_v:.2f})")
    check(mirrored.name in report["blender_export"]["mirrored_objects"], "mirrored object listed in the report")
    te = next(e for e in col.objects if e["class"] == "terrain")
    zmax = max((terrain.matrix_world @ v.co).z for v in terrain.data.vertices)
    check(abs(te["aabb"][5] - zmax) <= 1e-3, "terrain vertex edit exported")
    check(m["generator"].get("blender") == bpy.app.version_string, "Blender version recorded")
    check("collision/terrain.mbhf" in names and m.get("heightfield"), "heightfield exported and validated")
    check(set(by_name) == {n.name for n in nodes if n.triangles}, "every collision object has its glTF node")
    check(all(o.name in by_name for o in root.all_objects if o.type == "MESH"), "every mesh object exported")

    # --- collection paths (inherited render/view-layer restrictions), linked objects, materials ----------
    box_faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    box_verts = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0), (0, 0, 2), (2, 0, 2), (2, 2, 2), (0, 2, 2)]

    def box(name, colls, loc):
        bme = bpy.data.meshes.new(name)
        bme.from_pydata(box_verts, [], box_faces)
        ob = bpy.data.objects.new(name, bme)
        ob.location = loc
        for c in colls:
            c.objects.link(ob)
        return ob

    def layer_coll(coll, lc=None):
        lc = lc or bpy.context.view_layer.layer_collection
        if lc.collection == coll:
            return lc
        return next((x for x in (layer_coll(coll, ch) for ch in lc.children) if x is not None), None)

    scene_coll = bpy.context.scene.collection
    parent = bpy.data.collections.new("it parent (render off)")
    scene_coll.children.link(parent)
    parent.children.link(root)
    parent.hide_render = True
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"map collection with one enabled path (scene root) still exports ({err or 'ok'})")
    scene_coll.children.unlink(root)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"CANCELLED"} and "not enabled" in (err or "") and parent.name in (err or ""),
          f"map collection only under a render-disabled parent blocks export ({(err or '')[:90]!r})")
    scene_coll.children.link(root)
    parent.children.unlink(root)
    bpy.data.collections.remove(parent)

    c_off = bpy.data.collections.new("it render off")
    c_excl = bpy.data.collections.new("it excluded")
    c_hide = bpy.data.collections.new("it hidden in layer")
    for c in (c_off, c_excl, c_hide):
        root.children.link(c)
    c_off.hide_render = True
    bpy.context.view_layer.update()
    layer_coll(c_excl).exclude = True
    layer_coll(c_hide).hide_viewport = True
    box_a = box("it_box_render_off", [c_off], (-100.0, -100.0, 40.0))
    box_b = box("it_box_excluded", [c_excl], (-90.0, -100.0, 40.0))
    box_h = box("it_box_hidden", [c_hide], (-85.0, -100.0, 40.0))
    box_c = box("it_box_two_paths", [c_off, root], (-80.0, -100.0, 40.0))
    fancy = bpy.data.materials.new("it fancy")
    fancy.use_nodes = True
    bsdf = next(n for n in fancy.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Emission Strength"].default_value = 2.0
    bsdf.inputs["Coat Weight"].default_value = 0.5
    bsdf.inputs["Transmission Weight"].default_value = 0.3
    bump = fancy.node_tree.nodes.new("ShaderNodeBump")
    fancy.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    box_c.data.materials.append(fancy)

    lib_path = os.path.join(out_dir, "it_lib.blend")
    lob = box("it_twin", [], (60.0, -60.0, 40.0))
    lme = lob.data
    bpy.data.libraries.write(lib_path, {lob}, fake_user=True)
    bpy.data.objects.remove(lob)
    bpy.data.meshes.remove(lme)
    with bpy.data.libraries.load(lib_path, link=True) as (src_data, dst_data):
        dst_data.objects = ["it_twin"]
    linked = dst_data.objects[0]
    root.objects.link(linked)
    c_on = bpy.data.collections.new("it enabled")
    root.children.link(c_on)
    c_on.objects.link(linked)                        # same object in two map collections: exported once
    twin = box("it_twin", [root], (70.0, -60.0, 40.0))
    check(linked.library is not None and twin.library is None and twin.name == linked.name,
          f"local and linked objects share the name {twin.name!r} ({linked.name_full!r})")
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"CANCELLED"} and "'it_twin'" in (err or "") and "it_lib.blend" in (err or ""),
          f"linked and local objects sharing a name block export, naming both ({(err or '')[:120]!r})")
    bpy.data.objects.remove(twin)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"export with a linked object and restricted collections ({err or 'ok'})")
    report2, col2, _, _ = read_package(pkg)
    ids2 = [e["mb_id"] for e in col2.objects]
    excl = {e["object"]: e["reason"] for e in report2["blender_export"]["excluded_objects"]}
    for ob, coll in ((box_a, c_off), (box_b, c_excl), (box_h, c_hide)):
        check(f"user:{ob.name}" not in ids2 and coll.name in excl.get(ob.name, ""),
              f"{ob.name} (in {coll.name!r}) excluded and listed in the report")
    check(f"user:{box_c.name}" in ids2, "object with one enabled collection path is exported")
    check(ids2.count("user:it_twin") == 1, "linked library object exported exactly once (identity dedupe)")
    warns = [w for w in report2["blender_export"]["warnings"] if "it fancy" in w]
    for effect in ("emission", "coat", "transmission", "normal/bump"):
        check(any(effect in w for w in warns), f"omitted material effect {effect!r} named in the export warnings")
    for ob in (box_a, box_b, box_h, box_c):
        bpy.data.objects.remove(ob)
    root.objects.unlink(linked)
    for c in (c_off, c_excl, c_hide, c_on):
        bpy.data.collections.remove(c)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"export after restoring the scene ({err or 'ok'})")

    # --- material identity, attribute-socket handling and credential-like names (review round 2) -------
    mlib_path = os.path.join(out_dir, "it_mlib.blend")

    def principled(name, rgb):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1.0)
        return m

    lm = principled("it_dup", (1.0, 0.0, 0.0))
    bpy.data.libraries.write(mlib_path, {lm}, fake_user=True)
    bpy.data.materials.remove(lm)
    with bpy.data.libraries.load(mlib_path, link=True) as (src_data, dst_data):
        dst_data.materials = ["it_dup"]
    linked_mat = dst_data.materials[0]
    local_mat = principled("it_dup [it_mlib.blend]", (0.0, 0.0, 1.0))
    alpha_mat = principled("it_alpha", (0.0, 1.0, 0.0))
    ca = alpha_mat.node_tree.nodes.new("ShaderNodeVertexColor")
    alpha_mat.node_tree.links.new(ca.outputs["Alpha"],
                                  alpha_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    mat_boxes = []
    for i, m in enumerate((linked_mat, local_mat, alpha_mat)):
        ob = box(f"it_mat_{i}", [root], (-60.0 - 5 * i, 60.0, 40.0))
        ob.data.materials.append(m)
        mat_boxes.append(ob)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"export with same-named material datablocks ({err or 'ok'})")
    with zipfile.ZipFile(pkg) as z:
        gltf, _ = __import__("map_builder.core.glb", fromlist=["read_glb"]).read_glb(z.read("visual/map.glb"))
        rep3 = json.loads(z.read("report.json"))
    gmats = {m["name"]: m["pbrMetallicRoughness"]["baseColorFactor"][:3] for m in gltf.get("materials", [])}
    dup = {n: c for n, c in gmats.items() if n.startswith("it_dup [it_mlib.blend]")}
    check(len(dup) == 2 and sorted(tuple(round(x, 3) for x in c) for c in dup.values())
          == [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0)],
          f"distinct material datablocks with the same display name keep their own colours ({sorted(dup)})")
    check([round(x, 3) for x in gmats.get("it_alpha", [])] == [0.0, 1.0, 0.0]
          and any("it_alpha" in w and "Color" in w for w in rep3["blender_export"]["warnings"]),
          "Color Attribute Alpha output into Base Color is not treated as RGB (constant colour + warning)")
    secret = bpy.data.objects.new("it token=FAKE_REVIEW_ONLY", bpy.data.curves.new("it_secret", "CURVE"))
    root.objects.link(secret)
    good = sha256(pkg)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"CANCELLED"} and "FAKE_REVIEW_ONLY" not in (err or "") and "withheld" in (err or ""),
          f"credential-like object name is not echoed in the export error ({(err or '')[:100]!r})")
    check(sha256(pkg) == good, "previous package unchanged after the credential-named failure")
    bpy.data.objects.remove(secret)
    c_secret = bpy.data.collections.new("token=FAKE_REVIEW_ONLY")
    root.children.link(c_secret)
    c_secret.hide_render = True
    c_secret.objects.link(box("it_in_secret_coll", [], (-90.0, 60.0, 40.0)))
    res, err = run_op(bpy.ops.map_builder.export)
    check("FAKE_REVIEW_ONLY" not in (err or "") and sha256(pkg) == good
          and "FAKE_REVIEW_ONLY" not in bpy.data.texts["MapBuilder Report"].as_string(),
          f"credential-like collection name is never echoed or packaged ({res}, {(err or '')[:100]!r})")
    for ob in list(c_secret.objects):
        bpy.data.objects.remove(ob)
    bpy.data.collections.remove(c_secret)
    for ob in mat_boxes:
        bpy.data.objects.remove(ob)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"export after removing the material test objects ({err or 'ok'})")

    # --- invalid scenes fail and keep the previous package --------------------------------------------
    good = sha256(pkg)
    report_text = bpy.data.texts["MapBuilder Report"].as_string()
    curve = bpy.data.objects.new("bad_curve", bpy.data.curves.new("bad_curve", "CURVE"))
    root.objects.link(curve)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"CANCELLED"} and "bad_curve" in (err or ""), "curve object blocks export with a clear error")
    check(sha256(pkg) == good, "previous package unchanged after the curve failure")
    bpy.data.objects.remove(curve)

    user.scale = (1.0, 1.0, 0.0)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"CANCELLED"} and "zero scale" in (err or ""), "zero-scale object blocks export")
    check(sha256(pkg) == good, "previous package unchanged after the zero-scale failure")
    user.scale = (1.0, 1.0, 1.0)

    import bmesh
    touched = {"osm:way/1007", "osm:way/1028", "osm:way/1033", "osm:way/1038"}
    holed = next(o for o in sorted(root.all_objects, key=lambda o: o.name)
                 if o.get("mb_class") == "building" and o.get("mb_id") not in touched and o.data.users == 1)
    bm = bmesh.new()
    bm.from_mesh(holed.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context="FACES_ONLY")
    bm.to_mesh(holed.data)
    bm.free()
    holed.data.update()
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"CANCELLED"}, f"non-closed building blocks export ({(err or '').splitlines()[0:1]})")
    check(sha256(pkg) == good, "previous package unchanged after the non-closed-building failure")
    check(bpy.data.texts["MapBuilder Report"].as_string() == report_text,
          "failed exports left the last good report Text untouched")
    bogus = os.path.join(out_dir, "bogus.mbmap")
    with open(bogus, "wb") as f:
        f.write(b"not a package")
    s.export_path = bogus
    res, err = run_op(bpy.ops.map_builder.validate)
    s.export_path = pkg
    check(res == {"CANCELLED"} and bpy.data.texts["MapBuilder Report"].as_string() == report_text,
          f"failed validation reports without touching the report Text ({(err or '')[:60]!r})")
    check(validate_package(pkg).ok, "previous package still validates")

    # --- offline network sources fail clearly; credentials never reach the .blend --------------------
    secret = "S3CRET-token-123"
    os.environ["MAP_BUILDER_OVERPASS_URL"] = f"https://user:{secret}@overpass.invalid/api/{secret}/interpreter"
    s.osm_source, s.overpass_endpoint = "overpass", "env"
    n_colls = len(bpy.data.collections)
    res, err = run_op(bpy.ops.map_builder.generate)
    if not bpy.app.online_access:
        check(res == {"CANCELLED"} and "Online access is disabled" in (err or ""),
              "offline: Overpass generation fails clearly")
    else:
        check(res == {"CANCELLED"}, "unreachable Overpass endpoint fails (online)")
    check(len(bpy.data.collections) == n_colls, "failed generation created nothing")
    blend = os.path.join(out_dir, "it.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=False, copy=True)
    with open(blend, "rb") as f:
        data = f.read()
    check(secret.encode() not in data and b"overpass.invalid" not in data and dummy.encode() not in data,
          "no credential/endpoint in the .blend")
    with zipfile.ZipFile(pkg) as z:
        check(all(secret.encode() not in z.read(n) for n in z.namelist()), "no credential in the package")
    del os.environ["MAP_BUILDER_OVERPASS_URL"]
    print(f"package: {pkg} ({os.path.getsize(pkg)} bytes, sha256 {good[:16]}...), "
          f"{len(col.objects)} objects, {col.triangle_count} collision triangles")
