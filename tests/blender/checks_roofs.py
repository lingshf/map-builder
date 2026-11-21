# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""S2-F3 roof checks: every roof:shape in the synthetic fixture (gabled, hipped, pyramidal, skillion, dome) is
generated through the Generate operator and compared with the Python pipeline (core generate_plan, same settings):
mb_id, shape provenance, vertex positions within 1 mm, closed manifold mesh, and shape-specific invariants (apex
and ridge counts, height, ridge orientation, outward winding). An unsupported roof:shape (scratch OSM file) falls
back to flat with the same reason as Python. A hipped L-shaped house (scratch OSM file, S3-ROOF-HIPPED) is built from the
straight skeleton: Blender == Python within 1 mm and closed manifold with outward winding. Edited roofs (moved) round-trip through export: collision equals the
evaluated Blender triangles. build_roof stays the single roof entry point of the generator."""

import inspect
import math
import os

import bpy

from checks_core import FIXTURES, HEIGHT, LAT, LON, WIDTH, by_id, check, run_op, signed_volume, world_triangles

MM = 1e-3
ROOFS = {"osm:way/1023": "gabled", "osm:way/1028": "hipped", "osm:way/1033": "pyramidal",
         "osm:way/1038": "skillion", "osm:way/1043": "dome"}
TAG_ROOF_H = {"gabled": 3.0, "skillion": 1.5}  # roof:height tags in the fixture
# (eave, apex) above the mesh base, hard-coded from the fixture tags; the base is 0.3 m below the ground
# (foundation sink): gabled height=8 roof:height=3, pyramidal 2 levels (6 m) + 3 m, skillion height=5 roof:height=1.5,
# dome height=10; hipped has no height tags (defaults for a house)
ABS_HEIGHTS = {"gabled": (5.3, 8.3), "hipped": (3.7, 7.3), "pyramidal": (6.3, 9.3), "skillion": (3.8, 5.3),
              "dome": (6.1, 10.3)}
UNSUPPORTED_OSM = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="mb-test">
<node id="1" lat="47.000500000" lon="8.000000000"/>
<node id="2" lat="47.000500000" lon="8.000200000"/>
<node id="3" lat="47.000650000" lon="8.000200000"/>
<node id="4" lat="47.000650000" lon="8.000000000"/>
<way id="9001"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/><tag k="building" v="house"/><tag k="roof:shape" v="butterfly"/><tag k="height" v="8"/></way>
</osm>
"""


_L = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]      # an L, in steps of 0.0001 deg lon x 0.00008 deg lat
HIPPED_L_OSM = ("<?xml version='1.0' encoding='UTF-8'?>\n<osm version=\"0.6\" generator=\"mb-test\">\n"
                + "".join(f'<node id="{i + 1}" lat="{47.0005 + y * 0.00008:.9f}" lon="{8.0 + x * 0.0001:.9f}"/>\n'
                          for i, (x, y) in enumerate(_L))
                + '<way id="9101">' + "".join(f'<nd ref="{i}"/>' for i in (1, 2, 3, 4, 5, 6, 1))
                + '<tag k="building" v="house"/><tag k="roof:shape" v="hipped"/><tag k="height" v="8"/>'
                + '<tag k="roof:height" v="3"/></way>\n</osm>\n')


# a chamfered pentagon (metres, the footprint that needs the vertical cut) at the fixture's latitude
_CH = [(2, -6), (2, -4.5), (5, 7.5), (-3, 8), (-6, -5)]
CHAMFERED_OSM = ("<?xml version='1.0' encoding='UTF-8'?>\n<osm version=\"0.6\" generator=\"mb-test\">\n"
                 + "".join(f'<node id="{i + 1}" lat="{47.0005 + (y + 10) * 0.00000899:.9f}" lon="{8.0001 + (x + 10) * 0.00001317:.9f}"/>\n'
                           for i, (x, y) in enumerate(_CH))
                 + '<way id="9201">' + "".join(f'<nd ref="{i}"/>' for i in (1, 2, 3, 4, 5, 1))
                 + '<tag k="building" v="house"/><tag k="roof:shape" v="gabled"/><tag k="height" v="8"/>'
                 + '<tag k="roof:height" v="3"/></way>\n</osm>\n')


def configure(s, osm, name, pkg):
    s.area_mode = "CENTER"
    s.centre_lat, s.centre_lon, s.width, s.height = str(LAT), str(LON), WIDTH, HEIGHT
    s.elevation_source, s.elevation_file = "file", os.path.join(FIXTURES, "synthetic_dem.asc")
    s.elevation_crs, s.elevation_vertical_datum = "EPSG:4326", "SYNTHETIC"
    s.elevation_license = "SYNTHETIC test data (no licence required)"
    s.osm_source, s.osm_file = "file", osm
    s.terrain_spacing = 10.0
    s.package_name = name
    s.export_path = pkg
    s.heightfield_spacing = 2.0


def welded_edge_faces(ob):
    """Edge -> face count over vertices welded at 0.1 mm (the generator may split vertices for flat shading)."""
    me = ob.data
    key = {v.index: tuple(round(c * 1e4) for c in v.co) for v in me.vertices}
    edges = {}
    for p in me.polygons:
        vs = [key[i] for i in p.vertices]
        for a, b in zip(vs, vs[1:] + vs[:1]):
            e = (a, b) if a <= b else (b, a)
            edges[e] = edges.get(e, 0) + 1
    return edges


def world_verts(ob):
    mw = ob.matrix_world
    return [tuple(mw @ v.co) for v in ob.data.vertices]


def near(a, b):
    return max(abs(x - y) for x, y in zip(a, b)) <= MM


def matches(got, want):
    return all(any(near(w, g) for g in got) for w in want) and all(any(near(g, w) for w in want) for g in got)


def eave_from_walls(ob):
    """Wall top measured on the mesh: the lowest top edge of the vertical quads (roof faces are not walls)."""
    mw, tops = ob.matrix_world, []
    for p in ob.data.polygons:
        if len(p.vertices) == 4 and abs(p.normal.z) < 1e-3:
            tops.append(max((mw @ ob.data.vertices[i].co).z for i in p.vertices))
    return min(tops) if tops else float("nan")


def apex(pts):
    top = max(p[2] for p in pts)
    out = []
    for p in pts:
        if abs(p[2] - top) <= MM and not any(near(p, q) for q in out):
            out.append(p)
    return top, out


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def shape_invariants(shape, pts, eave_top, ob):
    top, ap = apex(pts)
    n = len(ap)
    low = min(p[2] for p in pts)
    base = []
    for p in pts:
        if abs(p[2] - low) <= MM and not any(near(p, q) for q in base):
            base.append(p)
    if shape in ("pyramidal", "dome"):
        check(n == 1, f"roofs: {shape} has a single apex ({n})")
    elif shape == "gabled":
        check(n == 2, f"roofs: gabled has a two-point ridge ({n})")
        # ridge parallel to the footprint's long side (the fixture footprint is a rotated rectangle)
        sides = sorted(dist(base[0], q) for q in base[1:])
        r = dist(ap[0], ap[1]) if n == 2 else -1.0
        check(any(abs(r - d) <= MM for d in sides[:2]), f"roofs: gabled ridge {r:.3f} m spans a footprint side {sides[:2]}")
    elif shape == "hipped":
        sides = sorted(dist(base[0], q) for q in base[1:])
        want = abs(sides[1] - sides[0])
        got = dist(ap[0], ap[1]) if n == 2 else -1.0
        check(abs(got - want) <= 0.01, f"roofs: hipped ridge {got:.3f} m = long side - short side ({want:.3f} m)")
    elif shape == "skillion":
        check(n >= 2, f"roofs: skillion high edge has >= 2 points ({n})")
        check(any(abs(p[2] - top) > 1.0 for p in pts), "roofs: skillion slopes (not flat)")
    if shape in TAG_ROOF_H:
        check(abs(top - eave_top - TAG_ROOF_H[shape]) <= MM, f"roofs: {shape} rises exactly roof:height {TAG_ROOF_H[shape]} m above the eave")
    check(top > eave_top + 0.1, f"roofs: {shape} apex {top:.3f} rises above the eave {eave_top:.3f}")


def run(out_dir):
    import map_builder
    from map_builder.blender.operators import make_area, make_settings
    from map_builder.core import generate as gen
    from map_builder.core import pipeline, roofs
    from map_builder.core.package import validate_package
    from checks_core import read_package

    s = bpy.context.scene.map_builder
    osm = os.path.join(FIXTURES, "synthetic_area.osm")
    pkg = os.path.join(out_dir, "roofs.mbmap")
    configure(s, osm, "roofs", pkg)
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"roofs: generate ({err or 'ok'})")
    root = s.export_collection
    plan, _ = pipeline.generate_plan(make_area(s), make_settings(s))
    ref = {sp.mb_id: sp for sp in plan.objects}

    check(len(roofs.SUPPORTED_SHAPES) >= len(ROOFS) and all(r in roofs.SUPPORTED_SHAPES for r in ROOFS.values()),
          "roofs: every fixture roof shape is supported by the generator")
    check(len(inspect.getsource(gen).split("roofs.build_roof(")) == 2
          and "def build_roof" not in inspect.getsource(gen), "roofs: build_roof has a single call site in generate")

    for mb_id, shape in ROOFS.items():
        ob = by_id(root, mb_id)
        sp = ref[mb_id]
        prov = ob.get("mb_provenance", "")
        check(ob.get("mb_class") == "building" and f'"roof_shape_built": "{shape}"' in prov,
              f"roofs: {mb_id} exists as a {shape} building (built {shape})")
        got = world_verts(ob)
        want = [tuple(c + o for c, o in zip(v, sp.location)) for v in sp.mesh.vertices]
        check(len(got) == len(want) and matches(got, want),
              f"roofs: {shape} vertices equal the Python pipeline within 1 mm ({len(got)} verts)")
        top_b, top_p = max(p[2] for p in got), max(p[2] for p in want)
        check(abs(top_b - top_p) <= MM, f"roofs: {shape} apex height {top_b:.4f} vs Python {top_p:.4f}")
        bad = [e for e, c in welded_edge_faces(ob).items() if c != 2]
        check(not bad, f"roofs: {shape} roof+walls are closed manifold ({len(bad)} bad edges)")
        check(signed_volume(world_triangles(ob)) > 0, f"roofs: {shape} is outward-wound (positive volume)")
        eave = eave_from_walls(ob)
        rise = top_b - eave
        base_z = min(p[2] for p in got)
        want_eave, want_apex = ABS_HEIGHTS[shape]
        check(abs(eave - base_z - want_eave) <= 0.005 and abs(top_b - base_z - want_apex) <= 0.005,
              f"roofs: {shape} eave {eave - base_z:.3f} m / apex {top_b - base_z:.3f} m above the mesh base = "
              f"fixture {want_eave} / {want_apex} m")
        want_rise = sp.provenance["roof_height_m"]
        check(abs(rise - want_rise) <= 0.01, f"roofs: {shape} measured rise {rise:.3f} m (apex - wall top) = declared roof height {want_rise} m")
        shape_invariants(shape, got, eave, ob)

    gab, hip = world_verts(by_id(root, "osm:way/1023")), world_verts(by_id(root, "osm:way/1028"))
    ridge_g, ridge_h = apex(gab)[1], apex(hip)[1]
    check(len(ridge_g) == 2 and len(ridge_h) == 2, "roofs: gabled and hipped ridges are both two-point")
    check(len(ridge_g) == 2 and len(ridge_h) == 2 and dist(*ridge_h) < dist(*ridge_g),
          "roofs: the hipped ridge is shorter than the gabled ridge (hips cut ends)")

    # --- edits round-trip through export ------------------------------------------------------------------
    moved = by_id(root, "osm:way/1043")
    moved.location.z += 2.0
    bpy.context.view_layer.update()
    if os.path.exists(pkg):
        os.remove(pkg)
    res, err = run_op(bpy.ops.map_builder.export)
    check(res == {"FINISHED"}, f"roofs: export after moving a roof ({err or 'ok'})")
    r = validate_package(pkg) if os.path.exists(pkg) else None
    check(r is not None and r.ok, "roofs: exported package exists and validates")
    if r is not None and r.ok:
        _, col, _, _ = read_package(pkg)
        ents = {e["mb_id"]: e for e in col.objects}
        for mb_id, shape in ROOFS.items():
            want = world_triangles(by_id(root, mb_id))
            got = col.object_triangles(ents[mb_id])
            err_max = max((abs(a - b) for tw, tg in zip(want, got) for pw, pg in zip(tw, tg) for a, b in zip(pw, pg)),
                          default=math.inf)
            check(len(want) == len(got) and err_max <= 1e-4,
                  f"roofs: {shape}{' (moved +2 m)' if mb_id == 'osm:way/1043' else ''} collision == Blender "
                  f"triangles (max err {err_max:.1e} m)")
        top_c = max(p[2] for t in col.object_triangles(ents["osm:way/1043"]) for p in t)
        check(abs(top_c - (apex(world_verts(by_id(root, "osm:way/1043")))[0])) <= MM and top_c > top_p_dome(plan) + 1.9,
              "roofs: moved dome apex is 2 m higher in the exported collision")

    # --- unsupported roof:shape falls back to flat with the Python reason ----------------------------------
    scratch = os.path.join(out_dir, "roof_unsupported.osm")
    with open(scratch, "w", encoding="utf-8") as f:
        f.write(UNSUPPORTED_OSM)
    s2 = bpy.context.scene.map_builder
    configure(s2, scratch, "roofs_flat", os.path.join(out_dir, "roofs_flat.mbmap"))
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"roofs: generate with an unsupported roof:shape ({err or 'ok'})")
    root2 = s2.export_collection
    ob = by_id(root2, "osm:way/9001")
    plan2, _ = pipeline.generate_plan(make_area(s2), make_settings(s2))
    py = next(sp for sp in plan2.objects if sp.mb_id == "osm:way/9001").provenance
    import json
    bl = json.loads(ob["mb_provenance"])
    check(py["roof_shape"] == "fallback:flat (roof:shape=butterfly not modelled)",
          f"roofs: Python reason for the unsupported shape ({py['roof_shape']})")
    check(bl["roof_shape"] == py["roof_shape"] and bl["roof_shape_built"] == "flat",
          "roofs: Blender falls back to flat with the same reason as Python")
    top, ap = apex(world_verts(ob))
    check(len(ap) >= 4 and not [e for e, c in welded_edge_faces(ob).items() if c != 2],
          "roofs: fallback roof is a flat closed box top")

    # --- a hipped L-shaped house is built from the straight skeleton ---------------------------------------
    scratch = os.path.join(out_dir, "roof_hipped_l.osm")
    with open(scratch, "w", encoding="utf-8") as f:
        f.write(HIPPED_L_OSM)
    s3 = bpy.context.scene.map_builder
    configure(s3, scratch, "roofs_l", os.path.join(out_dir, "roofs_l.mbmap"))
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"roofs: generate an L-shaped hipped house ({err or 'ok'})")
    ob = by_id(s3.export_collection, "osm:way/9101")
    plan3, _ = pipeline.generate_plan(make_area(s3), make_settings(s3))
    sp = next(o for o in plan3.objects if o.mb_id == "osm:way/9101")
    got = world_verts(ob)
    want = [tuple(c + o for c, o in zip(v, sp.location)) for v in sp.mesh.vertices]
    check(sp.provenance["roof_shape_built"] == "hipped" and "straight skeleton" in sp.provenance["roof_construction"],
          "roofs: the L-shaped hipped house is built hipped from the straight skeleton")
    check(len(got) == len(want) and matches(got, want), f"roofs: L-shaped hipped vertices equal Python within 1 mm ({len(got)} verts)")
    check(not [e for e, c in welded_edge_faces(ob).items() if c != 2], "roofs: L-shaped hipped house is closed manifold")
    check(signed_volume(world_triangles(ob)) > 0, "roofs: L-shaped hipped house is outward-wound")
    check(sp.provenance["roof_height_m"] == 3.0, "roofs: L-shaped hipped house has the tagged roof height")

    # --- a gabled L-shaped house: the ridge-end hips become vertical MB Facade gable walls -----------------
    scratch = os.path.join(out_dir, "roof_gabled_l.osm")
    with open(scratch, "w", encoding="utf-8") as f:
        f.write(HIPPED_L_OSM.replace('v="hipped"', 'v="gabled"'))
    s4 = bpy.context.scene.map_builder
    configure(s4, scratch, "roofs_gl", os.path.join(out_dir, "roofs_gl.mbmap"))
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"roofs: generate an L-shaped gabled house ({err or 'ok'})")
    ob = by_id(s4.export_collection, "osm:way/9101")
    plan4, _ = pipeline.generate_plan(make_area(s4), make_settings(s4))
    sp = next(o for o in plan4.objects if o.mb_id == "osm:way/9101")
    got = world_verts(ob)
    want = [tuple(c + o for c, o in zip(v, sp.location)) for v in sp.mesh.vertices]
    check(sp.provenance["roof_shape_built"] == "gabled" and "vertical gable wall" in sp.provenance["roof_construction"],
          f"roofs: the L-shaped gabled house is built gabled ({sp.provenance['roof_shape']})")
    check(len(got) == len(want) and matches(got, want), f"roofs: L-shaped gabled vertices equal Python within 1 mm ({len(got)} verts)")
    check(not [e for e, c in welded_edge_faces(ob).items() if c != 2], "roofs: L-shaped gabled house is closed manifold")
    check(signed_volume(world_triangles(ob)) > 0, "roofs: L-shaped gabled house is outward-wound")
    zmin = min(v[2] for v in got)
    ends = 0
    for tri in world_triangles(ob):
        zs = sorted(v[2] for v in tri)
        u = [tri[1][k] - tri[0][k] for k in range(3)]
        w = [tri[2][k] - tri[0][k] for k in range(3)]
        nrm = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        nl = math.sqrt(sum(c * c for c in nrm))
        if nl > 1e-9 and abs(nrm[2]) / nl < 1e-3 and zs[0] - zmin > 4.0 and abs(zs[0] - zs[1]) < 1e-3 and zs[2] - zs[1] > 0.1:
            ends += 1
    check(ends >= 2, f"roofs: the L-shaped gabled house has vertical gable-end walls ({ends} triangles)")

    # --- a chamfered gabled house needs the vertical cut (S4-ROOF-ENDS): Blender == Python, closed, outward ---
    scratch = os.path.join(out_dir, "roof_chamfered.osm")
    with open(scratch, "w", encoding="utf-8") as f:
        f.write(CHAMFERED_OSM)
    s5 = bpy.context.scene.map_builder
    configure(s5, scratch, "roofs_ch", os.path.join(out_dir, "roofs_ch.mbmap"))
    res, err = run_op(bpy.ops.map_builder.generate)
    check(res == {"FINISHED"}, f"roofs: generate a chamfered gabled house ({err or 'ok'})")
    ob = by_id(s5.export_collection, "osm:way/9201")
    plan5, _ = pipeline.generate_plan(make_area(s5), make_settings(s5))
    sp = next(o for o in plan5.objects if o.mb_id == "osm:way/9201")
    got = world_verts(ob)
    want = [tuple(c + o for c, o in zip(v, sp.location)) for v in sp.mesh.vertices]
    check(sp.provenance["roof_shape_built"] == "gabled" and "vertical gable wall" in sp.provenance["roof_construction"],
          f"roofs: the chamfered house is built gabled by the vertical cut ({sp.provenance['roof_shape']})")
    check(len(got) == len(want) and matches(got, want), f"roofs: chamfered gabled vertices equal Python within 1 mm ({len(got)} verts)")
    check(not [e for e, c in welded_edge_faces(ob).items() if c != 2], "roofs: chamfered gabled house is closed manifold")
    check(signed_volume(world_triangles(ob)) > 0, "roofs: chamfered gabled house is outward-wound")


def top_p_dome(plan):
    sp = next(o for o in plan.objects if o.mb_id == "osm:way/1043")
    return max(v[2] for v in sp.mesh.vertices) + sp.location[2]
