"""Headless Blender integration test for the Map Builder add-on (Blender 4.2 LTS).

    blender --background --factory-startup --python tests/blender/run_integration.py -- <out_dir>

Uses only the local SYNTHETIC fixtures (tests/fixtures; no network). Registers the add-on from this
repository, generates through the Generate operator, edits the scene like a user (move/rotate/
non-uniform scale, delete, duplicate, Array modifier, negative-scale mirror, user cube with Bevel,
terrain vertex edit), exports through the Export operator and checks the validated package against
the evaluated scene. Then checks that invalid scenes (curve object, zero scale, non-closed building)
fail without touching the previous package, that offline network sources fail clearly, and that no
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


def main(out_dir):
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

    # --- invalid scenes fail and keep the previous package --------------------------------------------
    good = sha256(pkg)
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
    check("previous package" in bpy.data.texts["MapBuilder Report"].as_string(), "failure written to report Text")
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
    check(secret.encode() not in data and b"overpass.invalid" not in data, "no credential/endpoint in the .blend")
    with zipfile.ZipFile(pkg) as z:
        check(all(secret.encode() not in z.read(n) for n in z.namelist()), "no credential in the package")
    del os.environ["MAP_BUILDER_OVERPASS_URL"]
    print(f"package: {pkg} ({os.path.getsize(pkg)} bytes, sha256 {good[:16]}...), "
          f"{len(col.objects)} objects, {col.triangle_count} collision triangles")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0]) if argv else tempfile.mkdtemp(prefix="mb_it_")
    os.makedirs(out, exist_ok=True)
    try:
        main(out)
    except Exception:
        traceback.print_exc()
        FAILURES.append("exception")
    print(f"\n{'FAILED' if FAILURES else 'OK'}: {len(FAILURES)} failure(s); output in {out}")
    for f in FAILURES:
        print("  FAIL", f)
    sys.stdout.flush()
    sys.exit(1 if FAILURES else 0)
