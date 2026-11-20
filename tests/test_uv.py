"""S3-TEX-UV-CORE: world-scaled UVs, textured materials, notices and the textured sample."""

import hashlib
import json
import math
import os
import struct
import tempfile
import unittest
import zipfile
import zlib

from map_builder.core import textures, uv
from map_builder.core.generate import MATERIALS, build_building
from map_builder.core.glb import write_glb
from map_builder.core.mesh import MeshData
from map_builder.core.package import validate_package

from .make_textured_fixture import _load, _write
from .test_scene_generation import building, flat_grid, rect_ccw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "examples", "synthetic_sample.mbmap")
# SHA-256 of visual/map.glb of the committed sample before S3 (v0.3.0 generator, untextured)
PRE_S3_GLB_SHA256 = "1f5b6993f566827bbc60a603608b189728e537590560db16c75912f6e91d259f"
X0 = 2000.0
TOL = 1e-6
CT = {5123: "H", 5125: "I", 5126: "f"}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}


def export(nodes, names):
    mats = dict(MATERIALS)
    for n in names:
        mats[n] = ((0.8, 0.8, 0.8), 0.9, 0.0, textures.load(n))
    return write_glb(nodes, mats)


def decode(glb):
    """(json, [primitives]) of a GLB; a primitive is {material name, mesh, pos, uv or None} with one entry per
    triangle corner (the writer emits unindexed triangles)."""
    jl = struct.unpack_from("<I", glb, 12)[0]
    gl = json.loads(glb[20:20 + jl])
    binc = glb[28 + jl:]

    def acc(i):
        a = gl["accessors"][i]
        v = gl["bufferViews"][a["bufferView"]]
        nc, f = NC[a["type"]], CT[a["componentType"]]
        raw = struct.unpack_from(f"<{a['count'] * nc}{f}", binc, v["byteOffset"] + a.get("byteOffset", 0))
        return [raw[k:k + nc] for k in range(0, len(raw), nc)]
    prims = []
    for mi, m in enumerate(gl["meshes"]):
        for p in m["primitives"]:
            at = p["attributes"]
            prims.append({"material": gl["materials"][p["material"]]["name"], "mesh": mi,
                          "pos": acc(at["POSITION"]), "uv": acc(at["TEXCOORD_0"]) if "TEXCOORD_0" in at else None})
    return gl, prims


def close(test, a, b, msg=""):
    for x, y in zip(a, b):
        test.assertAlmostEqual(x, y, delta=TOL, msg=f"{msg}: {a} != {b}")


def gltf_xyz(p):
    """glTF (x, z, -y) back to map-frame (x, y, z)."""
    return (p[0], -p[2], p[1])


def seams(prims):
    """Number of distinct edges (per mesh and material) whose two sides disagree on the UV."""
    edges = {}
    for pr in prims:
        for t in range(0, len(pr["pos"]), 3):
            for a, b in ((0, 1), (1, 2), (2, 0)):
                pa, pb = tuple(pr["pos"][t + a]), tuple(pr["pos"][t + b])
                ua, ub = tuple(round(x, 6) for x in pr["uv"][t + a]), tuple(round(x, 6) for x in pr["uv"][t + b])
                key = (pr["mesh"], pr["material"], frozenset((pa, pb)))
                edges.setdefault(key, set()).add(frozenset(((pa, ua), (pb, ub))))
    return sum(1 for sides in edges.values() if len(sides) > 1)


def _normal(pts):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = pts[0], pts[1], pts[2]
    u, v = (bx - ax, by - ay, bz - az), (cx - ax, cy - ay, cz - az)
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    m = math.sqrt(sum(c * c for c in n))
    return tuple(c / m for c in n)


def node(name, mesh, loc):
    return {"name": name, "mesh": mesh, "location": loc}


def flat_building(ring, height="6"):
    mesh, _, _ = build_building(building(ring, roof__shape="flat", height=height, roof__height="0"),
                                flat_grid(), 0.0)
    return mesh


class WallUvTest(unittest.TestCase):
    RING = [(0, 0), (10, 0), (10, 3), (4, 3), (4, 6), (0, 6)]   # a 10 x 6 m L, CCW
    CUM = [0, 10, 13, 19, 22, 26, 32]

    def test_l_footprint_walls(self):
        mesh = uv.textured_copy(flat_building(self.RING), (X0, 0, 0))
        _, prims = decode(export([node("b", mesh, (X0, 0, 0))], ["MB Facade", "MB Roof"]))
        facade = next(p for p in prims if p["material"] == "MB Facade")
        base = min(gltf_xyz(p)[2] for p in facade["pos"])
        tile = textures.tile_size("MB Facade")
        for q in range(6):   # the six wall quads come first, two triangles each
            corners = [facade["uv"][6 * q + k] for k in (0, 1, 2, 5)]
            want = [(self.CUM[q], -0.3), (self.CUM[q + 1], -0.3), (self.CUM[q + 1], 6), (self.CUM[q], 6)]
            for got, (u, v) in zip(corners, want):
                close(self, got, (u / tile, v / tile), f"quad {q}")
        zs = [gltf_xyz(p)[2] for p in facade["pos"]]
        self.assertAlmostEqual(max(v for _, v in facade["uv"]), 2.0, delta=TOL)   # V reaches 6 m / tile
        self.assertAlmostEqual(max(zs), 6.0, delta=TOL)
        self.assertTrue(all(abs(c) <= 40 / tile + 1 for p in prims for c in sum(p["uv"], ())))
        # ring vertex 0 seam + six ring bottom edges against the foundation cap
        self.assertEqual(seams(prims), 7)

    def test_gabled_roof_u_runs_along_the_eave_and_gables_continue_the_wall(self):
        ring = rect_ccw(-10, -6, 10, 6)
        mesh, _, _ = build_building(building(ring, roof__shape="gabled", height="10", roof__height="3"),
                                    flat_grid(), 0.0)
        mesh = uv.textured_copy(mesh, (X0, 0, 0))
        _, prims = decode(export([node("b", mesh, (X0, 0, 0))], ["MB Facade", "MB Roof"]))
        roof = next(p for p in prims if p["material"] == "MB Roof")
        slope, tile = math.hypot(6, 3), textures.tile_size("MB Roof")
        for t in range(0, len(roof["pos"]), 3):
            south = sum(gltf_xyz(p)[1] for p in roof["pos"][t:t + 3]) < 0   # the plane facing -y runs +x
            for p, uvc in zip(roof["pos"][t:t + 3], roof["uv"][t:t + 3]):
                x, y, _ = gltf_xyz(p)
                u = (x + 10) if south else (10 - x)
                close(self, uvc, (u / tile, (slope - abs(y) * slope / 6) / tile), "roof")
        facade = next(p for p in prims if p["material"] == "MB Facade")
        ft, cum = textures.tile_size("MB Facade"), {(10, -6): 20, (10, 6): 32, (-10, 6): 52, (-10, -6): 72}
        gables = 0
        for p, uvc in zip(facade["pos"], facade["uv"]):
            x, y, z = gltf_xyz(p)
            if abs(abs(x) - 10) < 1e-6 and z > 7 + 1e-6:   # above the eave: a gable apex
                gables += 1
                u = (26 if x > 0 else 58)
                close(self, uvc, (u / ft, (z - 0) / ft), "gable apex")
        self.assertEqual(gables, 2)
        self.assertEqual(seams(prims), 6)   # ring start, 4 bottom edges, 1 ridge


class PlaneUvTest(unittest.TestCase):
    def test_hipped_plane(self):
        m = MeshData("hip")
        pts = [(0, 0, 6), (10, 0, 6), (7, 4, 8), (3, 4, 8)]
        m.add_face([m.add_vertex(*p) for p in pts], "MB Roof", (0.4, 0.2, 0.1))
        uv.assign_uvs(m, (X0, 0, 0))
        s = math.hypot(4, 2)
        for p, got in zip(pts, m.face_uvs[0]):
            close(self, got, (p[0] / 2.0, (p[1] * 4 / s + (p[2] - 6) * 2 / s) / 2.0), "hip")

    def test_skeleton_hipped_roof_on_an_l_footprint(self):
        ring = [(0, 0), (20, 0), (20, 8), (8, 8), (8, 20), (0, 20)]
        mesh, _, _ = build_building(building(ring, roof__shape="hipped", height="9", roof__height="4"),
                                    flat_grid(), 0.0)
        roof = mesh.materials.index("MB Roof")
        roof_faces = [i for i, m in enumerate(mesh.face_materials) if m == roof]
        self.assertGreater(len(roof_faces), 4)
        uv.assign_uvs(mesh, (X0, 0, 0))
        tile = textures.tile_size("MB Roof")
        planes = {}
        for i in roof_faces:
            pts = [mesh.vertices[v] for v in mesh.faces[i]]
            n = _normal(pts)
            key = tuple(round(c, 4) for c in n) + (round(sum(a * b for a, b in zip(n, pts[0])), 3),)
            planes.setdefault(key, []).append((pts, mesh.face_uvs[i]))
        for faces in planes.values():
            # per plane the UV is one isometric map: edge lengths in UV (metres) equal the 3D lengths
            for pts, uvs in faces:
                for a in range(len(pts)):
                    b = (a + 1) % len(pts)
                    d3 = math.dist(pts[a], pts[b])
                    d2 = math.dist(uvs[a], uvs[b]) * tile
                    self.assertAlmostEqual(d3, d2, delta=1e-4)
        self.assertGreaterEqual(len(planes), 4)
        self.assertTrue(all(abs(c) < 100 / tile for f in planes.values() for _, u in f for p in u for c in p))

    def test_terrain_and_road_use_world_xy_minus_the_mesh_offset(self):
        for mat, tile in (("MB Terrain", 8.0), ("MB Road", 4.0)):
            m = MeshData(mat)
            vs = [m.add_vertex(x, y, 1.0) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            m.add_face(vs[:3], mat, (0.5, 0.5, 0.5))
            m.add_face((vs[0], vs[2], vs[3]), mat, (0.5, 0.5, 0.5))
            origin = (X0 + 3.0, 1003.5, 0.0)
            _, prims = decode(export([node("t", uv.textured_copy(m, origin), origin)], [mat]))
            ox, oy = tile * math.floor(origin[0] / tile), tile * math.floor(origin[1] / tile)
            for p, got in zip(prims[0]["pos"], prims[0]["uv"]):
                x, y, _ = gltf_xyz(p)
                close(self, got, ((x + origin[0] - ox) / tile, (y + origin[1] - oy) / tile), mat)
            self.assertLessEqual(max(abs(c) for u in prims[0]["uv"] for c in u), 1 + 2 / tile)

    def test_box_projection_and_untextured_materials(self):
        m = MeshData("box")
        a = [m.add_vertex(*p) for p in ((0, 0, 0), (2, 0, 0), (2, 0, 3), (0, 0, 3))]   # faces -y: (x, z)
        m.add_face(a, "MB Concrete", (0.5,) * 3)
        t = [m.add_vertex(*p) for p in ((0, 0, 3), (2, 0, 3), (2, 2, 3))]               # faces +z: (x, y)
        m.add_face(t, "MB Tunnel", (0.5,) * 3)
        m.add_face([m.add_vertex(0, 0, 0), m.add_vertex(1, 0, 0), m.add_vertex(0, 1, 0)], "MB Probe", (1, 1, 1))
        uv.assign_uvs(m, (X0 + 1.0, 0.0, 0.0))
        o = 4.0 * math.floor((X0 + 1) / 4)
        close(self, m.face_uvs[0][3], ((0 + X0 + 1 - o) / 4.0, 3 / 4.0), "concrete: dominant axis y -> (x, z)")
        close(self, m.face_uvs[0][1], ((2 + X0 + 1 - o) / 4.0, 0.0), "concrete x")
        close(self, m.face_uvs[1][2], ((2 + X0 + 1 - o) / 4.0, 2 / 4.0), "tunnel: dominant axis z -> (x, y)")
        self.assertIsNone(m.face_uvs[2])


class TexturedExportTest(unittest.TestCase):
    def test_mean_albedo_table_matches_the_png(self):
        for name, (png, _, _) in textures.TEXTURES.items():
            got = _mean_linear(textures.load(name))
            for g, w in zip(got, uv.TEXTURE_MEAN_ALBEDO[name]):
                self.assertAlmostEqual(g, w, delta=2e-3, msg=name)

    def test_color_compensation_is_clamped_and_leaves_untextured_alone(self):
        self.assertEqual(uv.compensated_color("MB Terrain", (0.0, 0.0, 0.0)), (0.0, 0.0, 0.0))
        self.assertTrue(all(0 <= c <= 1 for c in uv.compensated_color("MB Roof", (0.9, 0.9, 0.9))))
        m = MeshData("t")
        m.add_face([m.add_vertex(0, 0, 0), m.add_vertex(1, 0, 0), m.add_vertex(0, 1, 0)], "MB Probe", (0.3, 0.3, 0.3))
        self.assertEqual(uv.textured_copy(m).face_colors, [(0.3, 0.3, 0.3)])

    def test_bindings_and_notice(self):
        from .synthetic import synthetic_inputs
        from map_builder.core.generate import PlanOptions, build_plan
        from map_builder.core.pipeline import plan_to_package
        with tempfile.TemporaryDirectory() as tmp:
            area, grid, cl, _ids, sources = synthetic_inputs(os.path.join(tmp, "src"))
            plan = build_plan(area, grid, cl, PlanOptions(seed=1))
            path = os.path.join(tmp, "t.mbmap")
            manifest, result = plan_to_package(plan, path, "t", sources, heightfield_spacing=5,
                                               created_utc="2026-01-01T00:00:00Z", textures=True)
            self.assertTrue(result.ok, result.summary())
            members, mf = _load(path)
            self.assertEqual(mf["schema_version"], "2.1.0")
            gl, prims = decode(members["visual/map.glb"])
            binc = members["visual/map.glb"][28 + struct.unpack_from("<I", members["visual/map.glb"], 12)[0]:]
            used = set()
            for m in gl["materials"]:
                tex = m["pbrMetallicRoughness"].get("baseColorTexture")
                if m["name"] in textures.TEXTURES:
                    img = gl["images"][gl["textures"][tex["index"]]["source"]]
                    v = gl["bufferViews"][img["bufferView"]]
                    png = binc[v["byteOffset"]:v["byteOffset"] + v["byteLength"]]
                    self.assertEqual(hashlib.sha256(png).hexdigest(), textures.sha256(m["name"]))
                    used.add(m["name"])
                else:
                    self.assertIsNone(tex, m["name"])
            for p in prims:
                self.assertEqual(p["uv"] is not None, p["material"] in textures.TEXTURES, p["material"])
            self.assertTrue({"MB Facade", "MB Roof", "MB Terrain", "MB Road"} <= used, used)
            self.assertEqual(mf["asset_notices"], [textures.asset_notice(used)])
            self.assertIn("CC0", members["NOTICES.txt"].decode())
            # without provenance the 2.1 validator rejects the textured package
            del mf["asset_notices"]
            bad = os.path.join(tmp, "bad.mbmap")
            _write(bad, members, mf)
            self.assertFalse(validate_package(bad).ok)
            # untextured export: schema 2.1.0, no images, no UVs, no notices
            plain = os.path.join(tmp, "p.mbmap")
            plan_to_package(plan, plain, "t", sources, heightfield_spacing=5, created_utc="2026-01-01T00:00:00Z")
            pm, pmf = _load(plain)
            pgl, pprims = decode(pm["visual/map.glb"])
            self.assertEqual((pmf["schema_version"], "images" in pgl, "asset_notices" in pmf), ("2.1.0", False, False))
            self.assertTrue(all(p["uv"] is None for p in pprims))
            self.assertEqual(pm["collision/map.mbcol"], members["collision/map.mbcol"])

    def test_committed_sample_is_textured_and_valid(self):
        r = validate_package(SAMPLE)
        self.assertTrue(r.ok, r.summary())
        self.assertEqual(r.warnings, ["collision has 2 degenerate (zero-area) triangles"])
        members, mf = _load(SAMPLE)
        self.assertEqual(mf["schema_version"], "2.1.0")
        self.assertEqual(mf["asset_notices"][0]["name"], textures.NOTICE_NAME)
        self.assertNotEqual(hashlib.sha256(members["visual/map.glb"]).hexdigest(), PRE_S3_GLB_SHA256)
        self.assertIn("CC0-1.0", members["NOTICES.txt"].decode())


def _mean_linear(png):
    """Mean linear (gamma 2.2) RGB of an 8-bit RGB PNG (test-only decoder)."""
    pos, idat = 8, b""
    while pos < len(png):
        n = struct.unpack(">I", png[pos:pos + 4])[0]
        tag, data = png[pos + 4:pos + 8], png[pos + 8:pos + 8 + n]
        pos += 12 + n
        if tag == b"IHDR":
            w, h = struct.unpack(">II", data[:8])
        elif tag == b"IDAT":
            idat += data
    raw, stride, prev, total = zlib.decompress(idat), w * 3 + 1, bytearray(w * 3), [0.0] * 3
    for y in range(h):
        ft, line = raw[y * stride], bytearray(raw[y * stride + 1:(y + 1) * stride])
        for i in range(len(line)):
            a, b = (line[i - 3] if i >= 3 else 0), prev[i]
            c = prev[i - 3] if i >= 3 else 0
            if ft == 1:
                line[i] = (line[i] + a) & 255
            elif ft == 2:
                line[i] = (line[i] + b) & 255
            elif ft == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        for i in range(w * 3):
            total[i % 3] += (line[i] / 255) ** 2.2
        prev = line
    return [t / (w * h) for t in total]


if __name__ == "__main__":
    unittest.main()
