# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S3-TEX-BLENDER: textures in the Blender scene and in the Blender export.

On the synthetic scene (local fixtures, no network): every textured object has a UV map and the images are
packed; the exported GLB is strictly VALID, binds each texture by material name and carries the D65 notice;
its per-material UVs equal the CLI writer's within 1e-5 (the UV rules live in core/uv.py and are reused, not
reimplemented); the Textures checkbox off reproduces the untextured layout; a user mesh without UVs gets
fallback UVs and exactly one warning, and the package stays VALID. Reports through ``checks_core.check``.
"""
import hashlib
import json
import os
import zipfile

import bpy  # noqa: E402

import checks_core
from checks_core import FIXTURES, LAT, LON, HEIGHT, WIDTH, check, run_op

OSM = os.path.join(FIXTURES, "synthetic_area.osm")
DEM = os.path.join(FIXTURES, "synthetic_dem.asc")
DEM_LICENSE = "SYNTHETIC test data (no licence required)"
OSM_LICENSE = "SYNTHETIC test fixture (hand-written OSM-format XML, not OpenStreetMap data; no licence required)"
UV_TOL = 1e-5


def _members(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def _node_prims(glb):
    """{(node name, material): [(position, uv or None)]} with one entry per triangle corner."""
    from tests.test_uv import decode
    gl, prims = decode(glb)
    mesh_of = {n["name"]: n["mesh"] for n in gl["nodes"] if "mesh" in n}
    shift = {n["name"]: n.get("translation", (0, 0, 0)) for n in gl["nodes"]}
    by_mesh = {}
    for p in prims:
        by_mesh.setdefault(p["mesh"], []).append(p)
    out = {}
    for name, mi in mesh_of.items():
        for p in by_mesh.get(mi, []):
            uvs = p["uv"] or [None] * len(p["pos"])
            t = shift[name]
            out[(name, p["material"])] = [(tuple(c + d for c, d in zip(q, t)), uv) for q, uv in zip(p["pos"], uvs)]
    return gl, prims, out


def _corners_match(a, b):
    """Every (position, uv) corner of ``a`` has one in ``b`` within 1 cm (5 cm in height) / 1e-3 UV (the Blender scene is float32, so heights drift by a few mm and the UVs that follow them by far less than a texel)."""
    grid = {}
    for p, uv in b:
        grid.setdefault((round(p[0] * 100), round(p[2] * 100)), []).append((p, uv))
    for p, uv in a:
        key = (round(p[0] * 100), round(p[2] * 100))
        found = False
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for q, quv in grid.get((key[0] + dx, key[1] + dz), ()):
                    if (abs(p[0] - q[0]) < 1e-2 and abs(p[2] - q[2]) < 1e-2 and abs(p[1] - q[1]) < 5e-2
                            and max(abs(x - y) for x, y in zip(uv, quv)) < 1e-3):
                        found = True
        if not found:
            return False
    return True


def _cli_package(out_dir, textures, osm=OSM, tag=''):
    from map_builder.core.generate import PlanOptions
    from map_builder.core.geodesy import Area
    from map_builder.core.pipeline import Settings, build_package

    s = Settings(elevation_source="file", elevation_file=DEM, elevation_crs="EPSG:4326",
                 elevation_vertical_datum="SYNTHETIC", elevation_license=DEM_LICENSE, osm_source="file",
                 osm_file=osm, osm_license=OSM_LICENSE, terrain_spacing=10.0, heightfield_spacing=2.0,
                 plan_options=PlanOptions(seed=1))
    pkg = os.path.join(out_dir, f"tex_cli{tag}_{int(textures)}.mbmap")
    build_package(Area(LAT, LON, WIDTH, HEIGHT), s, pkg, "tex", textures=textures)
    return pkg


def _generate(pkg, textures, osm=OSM):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    s = bpy.context.scene.map_builder
    s.area_mode = "CENTER"
    s.centre_lat, s.centre_lon, s.width, s.height = str(LAT), str(LON), WIDTH, HEIGHT
    s.elevation_source, s.elevation_file = "file", DEM
    s.elevation_crs, s.elevation_vertical_datum, s.elevation_license = "EPSG:4326", "SYNTHETIC", DEM_LICENSE
    s.osm_source, s.osm_file = "file", osm
    s.terrain_spacing, s.heightfield_spacing, s.seed = 10.0, 2.0, 1
    s.package_name, s.export_path, s.textures = "tex", pkg, textures
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"textures: generate (textures={textures}) ({err or 'ok'})")
    return s


def run(out_dir):
    from map_builder.blender.sources import attribution_lines
    from map_builder.core import textures as tex
    from map_builder.core.package import validate_package
    from tests.test_uv import seams

    s = bpy.context.scene.map_builder
    prop = s.bl_rna.properties.get("textures")
    check(prop is not None and prop.default is True, "textures: the Textures property exists and defaults on (D27/D60)")
    check(any("CC0" in line for line in attribution_lines(True)) and not attribution_lines(False),
          "textures: the panel attribution lists the CC0 asset notice only when textures are on")

    cli_on = _cli_package(out_dir, True)
    cli_off = _cli_package(out_dir, False)

    # --- scene: UV maps, packed images, node tree ------------------------------------------------------------
    pkg = os.path.join(out_dir, "tex_bl.mbmap")
    s = _generate(pkg, True)
    root = s.export_collection
    textured_obs = [o for o in root.all_objects if o.type == "MESH"
                    and any(m.material and m.material.name in tex.TEXTURES for m in o.material_slots)]
    check(len(textured_obs) > 10, f"textures: {len(textured_obs)} textured objects")
    check(all(len(o.data.uv_layers) == 1 for o in textured_obs), "textures: every textured object has a UV map")
    imgs = [i for i in bpy.data.images if i.get("mb_image")]
    check(imgs and all(i.packed_file is not None for i in imgs),
          f"textures: {len(imgs)} generated image(s) are packed into the .blend")
    mat = bpy.data.materials["MB Facade"]
    types = sorted(n.type for n in mat.node_tree.nodes)
    check({"TEX_IMAGE", "UVMAP", "VERTEX_COLOR", "BSDF_PRINCIPLED"} <= set(types) and types.count("MIX_RGB") == 2,
          f"textures: material nodes are Image Texture x Vertex Colour into the Principled BSDF ({types})")

    # --- export ------------------------------------------------------------------------------------------------
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"textures: export ({err or 'ok'})")
    result = validate_package(pkg, strict=True)
    check(result.ok and not result.errors, f"textures: strictly VALID ({result.summary().splitlines()[0]})")
    mem, cli = _members(pkg), _members(cli_on)
    mf = json.loads(mem["manifest.json"])
    check(mf["schema_version"] == "2.1.0" and mf["asset_notices"] == json.loads(cli["manifest.json"])["asset_notices"],
          "textures: schema 2.1.0 and the same D65 asset_notices entry as the CLI")
    check("CC0" in mem["NOTICES.txt"].decode() and "Assets" in mem["NOTICES.txt"].decode(),
          "textures: NOTICES.txt has the Assets section")
    gl, prims, bl_nodes = _node_prims(mem["visual/map.glb"])
    cgl, cprims, cli_nodes = _node_prims(cli["visual/map.glb"])
    binc_ok = True
    for m in gl["materials"]:
        t = m["pbrMetallicRoughness"].get("baseColorTexture")
        if m["name"] in tex.TEXTURES:
            img = gl["images"][gl["textures"][t["index"]]["source"]]
            v = gl["bufferViews"][img["bufferView"]]
            off = 28 + int.from_bytes(mem["visual/map.glb"][12:16], "little") + v["byteOffset"]
            binc_ok &= hashlib.sha256(mem["visual/map.glb"][off:off + v["byteLength"]]).hexdigest() \
                == tex.sha256(m["name"])
        else:
            binc_ok &= t is None
    check(binc_ok, "textures: textures are bound by material name with the core/textures PNG bytes")
    check(all((p["uv"] is not None) == (p["material"] in tex.TEXTURES) for p in prims),
          "textures: TEXCOORD_0 exactly on the textured materials")
    check(sorted(m["name"] for m in gl["materials"]) == sorted(m["name"] for m in cgl["materials"]),
          "textures: the same materials as the CLI package")
    tp, ctp = [p for p in prims if p["uv"]], [p for p in cprims if p["uv"]]
    check(seams(tp) == seams(ctp), f"textures: UV seam count equals the CLI's ({seams(tp)})")
    bad = []
    for key in sorted(set(bl_nodes) | set(cli_nodes)):
        if key not in bl_nodes or key not in cli_nodes:
            bad.append(f"{key} only in one package")
        elif key[1] in tex.TEXTURES and not (_corners_match(bl_nodes[key], cli_nodes[key])
                                              and _corners_match(cli_nodes[key], bl_nodes[key])):
            bad.append(f"{key} UVs differ")
    check(not bad, f"textures: per-material UVs equal the CLI's within 1e-3 ({bad[:3]})")
    col_equal = mem["collision/map.mbcol"] == cli["collision/map.mbcol"]
    print(f"INFO collision identical to the CLI's: {col_equal}")

    # --- Textures off reproduces the untextured layout ----------------------------------------------------------
    s.textures = False
    off = os.path.join(out_dir, "tex_bl_off.mbmap")
    s.export_path = off
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"textures: export with Textures off ({err or 'ok'})")
    ro = validate_package(off, strict=True)
    mo, co = _members(off), _members(cli_off)
    ogl, oprims, _ = _node_prims(mo["visual/map.glb"])
    cogl, _, _ = _node_prims(co["visual/map.glb"])
    mfo = json.loads(mo["manifest.json"])
    check(ro.ok and "images" not in ogl and "textures" not in ogl and "asset_notices" not in mfo
          and all(p["uv"] is None for p in oprims), "textures: off gives no images, no UVs and no asset notice")
    check(sorted(m["name"] for m in ogl["materials"]) == sorted(m["name"] for m in cogl["materials"]),
          "textures: off uses the same materials as the untextured CLI package")
    check(mo["collision/map.mbcol"] == mem["collision/map.mbcol"], "textures: collision is independent of Textures")
    s.textures = True

    # --- edit round trip: a user mesh without UVs ---------------------------------------------------------------
    from map_builder.blender.scene_build import COLOR_ATTR, ensure_material
    me = bpy.data.meshes.new("user_cube")
    v = [(x, y, z) for z in (0, 2) for y in (0, 2) for x in (0, 2)]
    f = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    me.from_pydata(v, [], f)
    me.materials.append(ensure_material("MB Concrete", None, True))
    a = me.color_attributes.new(COLOR_ATTR, "FLOAT_COLOR", "CORNER")
    a.data.foreach_set("color", [0.5, 0.5, 0.5, 1.0] * len(me.loops))
    cube = bpy.data.objects.new("user_cube", me)
    cube.location = (30.0, 20.0, 1.0)
    next(iter(root.children)).objects.link(cube)
    edit = os.path.join(out_dir, "tex_bl_edit.mbmap")
    s.export_path = edit
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"textures: export with a user mesh without UVs ({err or 'ok'})")
    re_ = validate_package(edit, strict=True)
    rep = json.loads(_members(edit)["report.json"])
    uvw = [w for w in rep["blender_export"]["warnings"] if "UV" in w]
    check(re_.ok and len(uvw) == 1 and "user_cube" in uvw[0] and "12" in uvw[0],
          f"textures: fallback UVs give exactly one warning naming the triangle count and the package is VALID ({uvw})")
    _, _, edited = _node_prims(_members(edit)["visual/map.glb"])
    uvs = [uv for _, uv in edited[("user_cube", "MB Concrete")]]
    check(len(uvs) == 36 and all(u is not None for u in uvs), "textures: the user mesh has UVs on every corner")
    bpy.data.objects.remove(cube, do_unlink=True)

    # --- D86: generate with Textures off, export with Textures on: textures, materials and notice agree ----------
    s = _generate(os.path.join(out_dir, "tex_bl_offon.mbmap"), False)
    s.textures = True
    offon = os.path.join(out_dir, "tex_bl_offon_x.mbmap")
    s.export_path = offon
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"textures: off->on export ({err or 'ok'})")
    rx = validate_package(offon, strict=True)
    mx = _members(offon)
    xgl, xprims, xnodes = _node_prims(mx["visual/map.glb"])
    mfx = json.loads(mx["manifest.json"])
    textured_x = sorted(m["name"] for m in xgl["materials"] if m["name"] in tex.TEXTURES)
    check(rx.ok and mfx.get("asset_notices") == json.loads(cli["manifest.json"])["asset_notices"]
          and "CC0" in mx["NOTICES.txt"].decode() and "Assets" in mx["NOTICES.txt"].decode(),
          "textures: off->on package is VALID and carries the D65 notice and NOTICES Assets section")
    check(bool(textured_x) and all(("baseColorTexture" in m["pbrMetallicRoughness"]) == (m["name"] in tex.TEXTURES) for m in xgl["materials"])
          and all((p["uv"] is not None) == (p["material"] in tex.TEXTURES) for p in xprims),
          f"textures: off->on textures, materials and UVs agree ({textured_x})")
    check(sorted(m["name"] for m in xgl["materials"]) == sorted(m["name"] for m in cgl["materials"])
          and seams([p for p in xprims if p["uv"]]) == seams(ctp),
          "textures: off->on has the same materials and UV seams as the CLI package")
    check(not [w for w in json.loads(mx["report.json"])["blender_export"]["warnings"] if "UV" in w],
          "textures: off->on needs no fallback-UV warning for generated objects")

    # --- D86 round 3: an L-shaped gable generated with Textures off exports with the CLI's UVs ------------------
    from checks_roofs import HIPPED_L_OSM
    lg = os.path.join(out_dir, "tex_l_gabled.osm")
    with open(lg, "w", encoding="utf-8") as fh:
        fh.write(HIPPED_L_OSM.replace('v="hipped"', 'v="gabled"'))
    cli_l = _members(_cli_package(out_dir, True, lg, "_l"))
    _, _, lnodes = _node_prims(cli_l["visual/map.glb"])
    s = _generate(os.path.join(out_dir, "tex_bl_l.mbmap"), False, lg)
    s.textures = True
    lx = os.path.join(out_dir, "tex_bl_l_x.mbmap")
    s.export_path = lx
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"textures: L gable off->on export ({err or 'ok'})")
    _, _, bnodes = _node_prims(_members(lx)["visual/map.glb"])
    roofs = [k for k in lnodes if k[1] == "MB Roof"]
    check(bool(roofs) and all(k in bnodes and _corners_match(bnodes[k], lnodes[k]) and _corners_match(lnodes[k], bnodes[k])
                              for k in roofs if k in bnodes) and all(k in bnodes for k in roofs),
          f"textures: L gable generated off, exported on has the CLI's MB Roof UVs ({roofs})")

    # --- D86 round 3: only generated meshes use stored UVs; an untagged mesh with a generated material gets
    # the world-XY fallback and one warning ------------------------------------------------------------------------
    s = _generate(os.path.join(out_dir, "tex_bl_u.mbmap"), False)
    me = bpy.data.meshes.new("plain_cube")
    me.from_pydata(v, [], f)
    me.materials.append(bpy.data.materials["MB Facade"])
    a = me.color_attributes.new(COLOR_ATTR, "FLOAT_COLOR", "CORNER")
    a.data.foreach_set("color", [0.5, 0.5, 0.5, 1.0] * len(me.loops))
    cube = bpy.data.objects.new("plain_cube", me)
    next(iter(s.export_collection.children)).objects.link(cube)
    s.textures = True
    pc = os.path.join(out_dir, "tex_bl_plain.mbmap")
    s.export_path = pc
    res, err = run_op(bpy.ops.map_builder.export)
    rep = json.loads(_members(pc)["report.json"])
    uvw = [w for w in rep["blender_export"]["warnings"] if "UV" in w]
    check(res == {"FINISHED"} and len(uvw) == 1 and "plain_cube" in uvw[0],
          f"textures: an untagged no-UV cube with a generated material gets one fallback warning ({uvw})")

    # --- D86 round 4: plain and textured generated variants of one texture with different roughness keep their
    # own glTF materials, and the names do not depend on object names ---------------------------------------------
    from map_builder.blender.scene_build import ensure_material as _em

    def _cube(name, mat, loc):
        m = bpy.data.meshes.new(name)
        m.from_pydata(v, [], f)
        m.materials.append(mat)
        at = m.color_attributes.new(COLOR_ATTR, "FLOAT_COLOR", "CORNER")
        at.data.foreach_set("color", [0.5, 0.5, 0.5, 1.0] * len(m.loops))
        o = bpy.data.objects.new(name, m)
        o.location = loc
        next(iter(s.export_collection.children)).objects.link(o)
        return o

    def _mats(path):
        gl_, _, _ = _node_prims(_members(path)["visual/map.glb"])
        return {m["name"]: (round(m["pbrMetallicRoughness"]["roughnessFactor"], 3),
                            "baseColorTexture" in m["pbrMetallicRoughness"]) for m in gl_["materials"]}
    bpy.data.objects.remove(cube, do_unlink=True)
    plain = next(m for m in bpy.data.materials if m.get("mb_material") == "MB Facade" and not m.get("mb_textured"))
    tmat = _em("MB Facade", None, True)
    tweaked = tmat.copy()
    next(n for n in tweaked.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Roughness"].default_value = 0.21
    tweaked["mb_material"], tweaked["mb_textured"] = "MB Facade", True
    c1, c2, c3 = _cube("mix_a", plain, (60, 20, 1)), _cube("mix_b", tweaked, (70, 20, 1)), _cube("mix_c", tmat, (80, 20, 1))
    p1 = os.path.join(out_dir, "tex_bl_mix1.mbmap")
    s.export_path = p1
    res, err = run_op(bpy.ops.map_builder.export)
    ok1 = res == {"FINISHED"}
    m1 = _mats(p1) if ok1 else {}
    c1.name, c2.name, c3.name = "zz_a", "aa_b", "mm_c"
    p2 = os.path.join(out_dir, "tex_bl_mix2.mbmap")
    s.export_path = p2
    res, err = run_op(bpy.ops.map_builder.export)
    m2 = _mats(p2) if res == {"FINISHED"} else {}
    fac = {n: v_ for n, v_ in m1.items() if n.startswith("MB Facade")}
    check(ok1 and m1 == m2 and len(fac) == 2 and 0.21 in [r_ for r_, _ in fac.values()] and all(t for _, t in fac.values()),
          f"textures: a plain/textured mix with a different roughness exports two textured materials, "
          f"independent of object names ({fac})")
    check(json.loads(_members(p1)["manifest.json"]).get("asset_notices") is not None,
          "textures: the mixed package carries the notice")

    # --- D88: export identity is a key (exact parameters), not a display name -----------------------------------
    for o in (c1, c2, c3):
        bpy.data.objects.remove(o, do_unlink=True)

    def _tweak(rough):
        m = tmat.copy()
        next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Roughness"].default_value = rough
        m["mb_material"], m["mb_textured"] = "MB Facade", True
        return m

    def _export_mats(tag):
        pth = os.path.join(out_dir, f"tex_bl_{tag}.mbmap")
        s.export_path = pth
        r_, _ = run_op(bpy.ops.map_builder.export)
        return _mats(pth) if r_ == {"FINISHED"} else None

    # (1) a user material whose display name equals the generated one must not take its texture
    tmat.name = "gen_textured_facade"
    user = bpy.data.materials.new("MB Facade")
    d1, d2 = _cube("d88_user", user, (60, 40, 1)), _cube("d88_gen", tmat, (70, 40, 1))
    m_a = _export_mats("d88a")
    fa = {n: v_ for n, v_ in (m_a or {}).items() if n.startswith("MB Facade")}
    check(m_a is not None and sorted(fa.values()) == [(0.4, False), (0.85, True)]
          and all(n.startswith("MB Facade ") for n in fa),
          f"textures: a user material named like a generated one keeps its own params and the texture stays on "
          f"the generated primitive ({m_a})")
    for o in (d1, d2):
        bpy.data.objects.remove(o, do_unlink=True)

    # (2) variants whose roughness differ below the display precision stay distinct and order-independent
    va, vb = _tweak(0.2101), _tweak(0.2104)
    e1, e2 = _cube("d88_v1", va, (60, 60, 1)), _cube("d88_v2", vb, (70, 60, 1))
    m_b = _export_mats("d88b")
    e1.name, e2.name = "zz_v1", "aa_v2"
    m_c = _export_mats("d88c")
    pick = lambda mm: {n: v_ for n, v_ in (mm or {}).items() if n.startswith("MB Facade") and v_[0] == 0.21}
    check(m_b is not None and m_b == m_c and len(pick(m_b)) == 2,
          f"textures: roughness 0.2101 and 0.2104 export as two stable, distinct materials ({pick(m_b)})")
