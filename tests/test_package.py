"""Package contract tests (docs/PACKAGE_FORMAT.md): mbcol/mbhf/GLB formats, axes and handedness,
orientation probes, per-triangle winding, identity, validator robustness, atomic writes, pipeline."""

import contextlib
import copy
import importlib.util
import io
import json
import math
import os
import random
import shutil
import struct
import tempfile
import unittest
import zipfile
from unittest import mock

from map_builder.core import package as pkg
from map_builder.core.collision import (CLASSES, COL_HEADER, HF_HEADER, ColObject, collision_size, read_collision,
                                        read_heightfield, rasterize_heightfield, write_collision, write_heightfield)
from map_builder.core.errors import CoverageError, LimitError, MapBuilderError, NetworkError, PackageError
from map_builder.core.generate import MATERIALS, PlanOptions, build_plan
from map_builder.core.geodesy import Area, gltf_to_map, map_to_gltf, map_to_unity_x_negated
from map_builder.core.glb import read_glb, write_glb
from map_builder.core.mesh import MeshData
from map_builder.core.package import (MAP_FROM_GLTF, MAP_FROM_UNITY, PROBES_UNAVAILABLE, assemble, file_entry,
                                      manifest_bytes, match_winding, package_id_of, safe_member_name,
                                      select_orientation_probes, unity_import, validate_package,
                                      verify_probe_in_unity)
from map_builder.core.pipeline import (Settings, build_package, collision_object, heightfield_from_collision,
                                       object_transform, plan_to_package, resolve_identities)

from .synthetic import (AREA_H, AREA_W, ORIGIN, build_synthetic_osm, chiral_mesh, grid_terrain_mesh,
                        synthetic_inputs, synthetic_sources, write_synthetic_fixtures)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AREA = Area(ORIGIN[0], ORIGIN[1], AREA_W, AREA_H)
UTC = "2024-01-01T00:00:00Z"


# --- helpers ---------------------------------------------------------------------------

def cross(a, b, c):
    u = [b[k] - a[k] for k in range(3)]
    v = [c[k] - a[k] for k in range(3)]
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def mat_vec(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def signed_volume(tris):
    return sum(dot(a, cross((0, 0, 0), b, c)) for a, b, c in tris) / 6.0


def box_mesh(x0, y0, x1, y1, z0, z1, name="box"):
    m = MeshData(name)
    for z in (z0, z1):
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            m.add_vertex(x, y, z)
    for f in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        m.add_face(f, "MB Wall", (0.7, 0.7, 0.7))
    return m


def obj(name, mb_id, cls, mesh, location=(0.0, 0.0, 0.0), rotation_z=0.0, scale=1.0):
    return {"name": name, "mb_id": mb_id, "cls": cls, "mesh": mesh, "location": location, "rotation_z": rotation_z,
            "scale": scale}


def scene(extra=(), terrain_fn=None):
    return [obj("terrain", "terrain:grid", "terrain", grid_terrain_mesh(AREA_W, AREA_H, 20.0, terrain_fn)),
            obj("chiral", "osm:way/1", "building", chiral_mesh(), (30.0, 40.0, 5.0), 0.3),
            obj("box", "osm:way/2", "building", box_mesh(-55, -65, -45, -50, 2, 12))] + list(extra)


def node_of(o, mesh=None, **override):
    n = {"name": o["name"], "mesh": mesh or o["mesh"], "location": o["location"], "rotation_z": o["rotation_z"],
         "scale": o["scale"], "extras": {"mb_id": o["mb_id"], "mb_class": o["cls"]}}
    n.update(override)
    return n


def col_of(o):
    return collision_object(o["name"], o["mb_id"], o["cls"], o["mesh"], o["location"], o["rotation_z"], o["scale"])


def world_mesh(o, mirror_cx=None, reverse=False):
    """The object's mesh in world space (identity node transform), optionally mirrored about x = mirror_cx
    (faces reversed so it stays outward-facing) and/or with its winding flipped."""
    apply, mirrored = object_transform(o["location"], o["rotation_z"], o["scale"])
    src = o["mesh"]
    m = MeshData(o["name"])
    for v in src.vertices:
        p = apply(v)
        if mirror_cx is not None:
            p = (2 * mirror_cx - p[0], p[1], p[2])
        m.add_vertex(*p)
    flip = mirrored ^ (mirror_cx is not None) ^ reverse
    for f, mi, c in zip(src.faces, src.face_materials, src.face_colors):
        m.add_face(tuple(reversed(f)) if flip else tuple(f), src.materials[mi], c)
    return m


def world_node(o, **kw):
    return {"name": o["name"], "mesh": world_mesh(o, **kw), "location": (0.0, 0.0, 0.0), "rotation_z": 0.0,
            "scale": 1.0, "extras": {"mb_id": o["mb_id"]}}


def scene_members(objs, visual_nodes=None, heightfield_spacing=None, report=None, sources=None):
    col_bytes = write_collision([col_of(o) for o in objs])
    glb = write_glb(visual_nodes if visual_nodes is not None else [node_of(o) for o in objs], MATERIALS)
    hf = heightfield_from_collision(read_collision(col_bytes), AREA, heightfield_spacing) if heightfield_spacing \
        else None
    objects = [{"name": o["name"], "mb_id": o["mb_id"], "class": o["cls"], "collision": True, "provenance": {}}
               for o in objs]
    return assemble("test", AREA, sources or synthetic_sources(), glb, col_bytes, objects, heightfield=hf,
                    report=report or {}, created_utc=UTC)


def raw_write(path, members, manifest, manifest_raw=None):
    """Write a package WITHOUT validation (to produce deliberately broken packages)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", manifest_raw if manifest_raw is not None else manifest_bytes(manifest))
        for name in sorted(members):
            z.writestr(name, members[name])


def load(path):
    with zipfile.ZipFile(path) as z:
        members = {n: z.read(n) for n in z.namelist() if n != "manifest.json"}
        manifest = json.loads(z.read("manifest.json"))
    return members, manifest


def rehash(members, manifest):
    manifest["files"] = [file_entry(p, members[p]) for p in sorted(members)]
    return manifest


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def patch_glb(glb, fn):
    jl = struct.unpack_from("<I", glb, 12)[0]
    gl = json.loads(glb[20:20 + jl])
    fn(gl)
    rest = glb[20 + jl:]
    js = json.dumps(gl).encode()
    js += b" " * (-len(js) % 4)
    return (struct.pack("<III", 0x46546C67, 2, 20 + len(js) + len(rest)) + struct.pack("<II", len(js), 0x4E4F534A)
            + js + rest)


class TempDirCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def p(self, name):
        return os.path.join(self.tmp, name)

    def assertInvalid(self, path, fragment):
        r = validate_package(path)
        self.assertFalse(r.ok, r.summary())
        self.assertTrue(any(fragment in e for e in r.errors), r.errors)
        return r


# --- formats -------------------------------------------------------------------------

def two_objects():
    a = ColObject("a", "osm:way/1", "building", [(0, 0, 0), (1, 0, 0), (0, 1, 0), (9, 9, 9)], [(0, 1, 2)])
    b = ColObject("b", "terrain:grid", "terrain", [(5, 5, 1), (6, 5, 1), (5, 7, 2), (6, 7, 2)], [(0, 1, 2), (1, 3, 2)])
    return [a, b]


def replace_table(data, table_bytes):
    """Swap the mbcol object table (fixing J and the padding)."""
    _, _, _, nv, nt, _, _, *_ = COL_HEADER.unpack_from(data, 0)
    off = collision_size(nv, nt, 0)
    table_bytes += b"\0" * (-len(table_bytes) % 4)
    out = bytearray(data[:off] + table_bytes)
    struct.pack_into("<I", out, 28, len(table_bytes))
    return bytes(out)


class CollisionFormatTest(unittest.TestCase):
    def test_header_and_layout_offsets(self):
        data = write_collision(two_objects())
        self.assertEqual(COL_HEADER.size, 64)
        magic, ver, flags, nv, nt, no, tlen, *rest = COL_HEADER.unpack_from(data, 0)
        self.assertEqual((magic, ver, flags, nv, nt, no), (b"MBCOL\0\0\0", 1, 1, 7, 3, 2))  # unused vertex dropped
        self.assertEqual(tuple(rest[:6]), (0, 0, 0, 6, 7, 2))
        self.assertEqual(tuple(rest[6:]), (0, 0))
        self.assertEqual(tlen % 4, 0)
        o = 64
        verts = struct.unpack_from(f"<{3 * nv}f", data, o)
        self.assertEqual(verts[:9], (0, 0, 0, 1, 0, 0, 0, 1, 0))
        o += 12 * nv
        self.assertEqual(struct.unpack_from("<9I", data, o), (0, 1, 2, 3, 4, 5, 4, 6, 5))
        o += 12 * nt
        self.assertEqual(struct.unpack_from("<3I", data, o), (0, 1, 1))
        o += 4 * nt
        self.assertEqual(data[o:o + 4], bytes([2, 1, 1, 0]))  # class ids + zero padding to 4
        o += 4
        table = json.loads(data[o:].rstrip(b"\0"))
        self.assertEqual(len(data), o + tlen)
        self.assertEqual([(e["index"], e["name"], e["class"], e["tri_start"], e["tri_count"]) for e in table],
                         [(0, "a", "building", 0, 1), (1, "b", "terrain", 1, 2)])
        self.assertEqual(table[1]["aabb"], [5, 5, 1, 6, 7, 2])

    def test_round_trip(self):
        col = read_collision(write_collision(two_objects()))
        self.assertEqual(col.triangle_count, 3)
        self.assertEqual(col.triangle(2), ((6, 5, 1), (6, 7, 2), (5, 7, 2)))
        self.assertEqual(col.tri_class, bytes([2, 1, 1]))
        self.assertEqual(col.bounds, ((0, 0, 0), (6, 7, 2)))
        self.assertEqual(len(col.class_triangles("terrain")), 2)

    def test_class_mapping_is_contract(self):
        self.assertEqual(CLASSES, {"user": 0, "terrain": 1, "building": 2, "road": 3, "vegetation": 4, "water": 5,
                                   "prop": 6})

    def test_reader_rejects_corruption(self):
        good = write_collision(two_objects())
        _, _, _, nv, nt, no, tlen, *_ = COL_HEADER.unpack_from(good, 0)
        o_idx = 64 + 12 * nv
        o_obj = o_idx + 12 * nt
        o_cls = o_obj + 4 * nt

        def patched(fmt, offset, *values):
            b = bytearray(good)
            struct.pack_into(fmt, b, offset, *values)
            return bytes(b)
        cases = {
            "magic": patched("<8s", 0, b"MBCOX\0\0\0"),
            "version": patched("<I", 8, 2),
            "flag bit0 unset": patched("<I", 12, 0),
            "unknown flag": patched("<I", 12, 3),
            "reserved": patched("<I", 56, 1),
            "bounds": patched("<f", 32, -1.0),
            "nan vertex": patched("<f", 64, math.nan),
            "inf bound": patched("<f", 40, math.inf),
            "vertex index": patched("<I", o_idx, nv),
            "object index": patched("<I", o_obj, 5),
            "class mismatch": patched("<B", o_cls, 3),
            "unknown class": patched("<B", o_cls, 9),
            "class padding": patched("<B", o_cls + 3, 1),
            "non-contiguous": patched("<3I", o_obj, 1, 0, 1),
            "table length not /4": patched("<I", 28, tlen - 1),
            "more objects than triangles": patched("<I", 24, nt + 1),
            "truncated": good[:-1],
            "extended": good + b"\0\0\0\0",
            "short": good[:40],
        }
        table = json.loads(good[o_cls + 4:].rstrip(b"\0"))
        dup = json.dumps(table).replace('"name": "a"', '"name": "a", "name": "x"', 1).encode()
        cases["duplicate key"] = replace_table(good, dup)
        cases["nan in table"] = replace_table(good, json.dumps(table).replace("[0", "[NaN", 1).encode())
        t2 = copy.deepcopy(table)
        t2[1]["name"] = "a"
        cases["duplicate name"] = replace_table(good, json.dumps(t2).encode())
        t3 = copy.deepcopy(table)
        t3[0]["aabb"][3] += 1
        cases["aabb"] = replace_table(good, json.dumps(t3).encode())
        t4 = copy.deepcopy(table)
        t4[1]["tri_count"] = 1
        cases["coverage"] = replace_table(good, json.dumps(t4).encode())
        cases["table count"] = replace_table(good, json.dumps(table[:1]).encode())
        cases["nul in table"] = replace_table(good, json.dumps(table).encode()[:-1] + b"\0]")
        for what, data in cases.items():
            with self.subTest(what), self.assertRaises(PackageError):
                read_collision(data)
        read_collision(replace_table(good, json.dumps(table).encode()))  # the helper itself keeps it valid

    def test_writer_rejects_bad_objects(self):
        tri = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        cases = {
            "duplicate names": [ColObject("a", "i", "user", tri, [(0, 1, 2)]), ColObject("a", "j", "user", tri,
                                                                                         [(0, 1, 2)])],
            "empty name": [ColObject("", "i", "user", tri, [(0, 1, 2)])],
            "no mb_id": [ColObject("a", "", "user", tri, [(0, 1, 2)])],
            "unknown class": [ColObject("a", "i", "bridge", tri, [(0, 1, 2)])],
            "no triangles": [ColObject("a", "i", "user", tri, [])],
            "bad index": [ColObject("a", "i", "user", tri, [(0, 1, 3)])],
            "nan": [ColObject("a", "i", "user", [(math.nan, 0, 0)] + tri, [(0, 1, 2)])],
            "far": [ColObject("a", "i", "user", [(2e6, 0, 0)] + tri, [(0, 1, 2)])],
        }
        for what, objs in cases.items():
            with self.subTest(what), self.assertRaises(PackageError):
                write_collision(objs)


class HeightfieldFormatTest(unittest.TestCase):
    def test_layout_is_row_major_south_to_north(self):
        nx, ny, x0, y0, s = 4, 3, -15.0, -10.0, 10.0
        z = [[1.0 + 2 * (x0 + i * s) + 3 * (y0 + j * s) for i in range(nx)] for j in range(ny)]
        z[0][0] = math.nan
        data = write_heightfield(z, x0, y0, s)
        self.assertEqual(HF_HEADER.size, 48)
        self.assertEqual(HF_HEADER.unpack_from(data, 0), (b"MBHF\0\0\0\0", 1, nx, ny, 0, x0, y0, s))
        self.assertEqual(len(data), 48 + 4 * nx * ny)
        j, i = 2, 1  # y = y0 + 2s (north), x = x0 + s
        self.assertEqual(struct.unpack_from("<f", data, 48 + 4 * (j * nx + i))[0], 1 + 2 * (-5.0) + 3 * 10.0)
        hf = read_heightfield(data)
        self.assertTrue(math.isnan(hf["z"][0][0]))
        self.assertEqual(hf["z"][2][1], 21.0)

    def test_rasterize_takes_maximum(self):
        tris = [((0, 0, 0), (10, 0, 10), (10, 10, 10)), ((0, 0, 0), (10, 10, 10), (0, 10, 0)),
                ((0, 0, 50), (10, 0, 50), (0, 10, 50))]
        z = rasterize_heightfield(tris, 0, 0, 5, 3, 3)
        self.assertEqual(z[0][0], 50)
        self.assertAlmostEqual(z[2][2], 10)

    def test_reader_and_writer_reject_bad_input(self):
        good = write_heightfield([[0.0, 1.0], [2.0, 3.0]], 0, 0, 1)
        b = bytearray(good)
        struct.pack_into("<I", b, 20, 1)
        for bad in (bytes(b), good[:-1], good + b"\0" * 4, good[:47],
                    good[:48] + struct.pack("<f", math.inf) + good[52:]):
            with self.assertRaises(PackageError):
                read_heightfield(bad)
        for z in ([[0.0]], [[0.0, 1.0], [2.0]], [[0.0, math.inf], [1.0, 2.0]]):
            with self.assertRaises(PackageError):
                write_heightfield(z, 0, 0, 1)


# --- GLB ---------------------------------------------------------------------------------

class GlbTest(unittest.TestCase):
    def glb(self, **kw):
        n = {"name": "chiral", "mesh": chiral_mesh(), "location": (10.0, -5.0, 2.0), "rotation_z": 0.7,
             "scale": 1.0, "extras": {"mb_id": "x"}}
        n.update(kw)
        return write_glb([n], MATERIALS), n

    def test_round_trip_matches_object_transform(self):
        for scale in (1.3, (2.0, 3.0, 0.5), (-1.0, 1.0, 1.0), -1.0):
            glb, n = self.glb(scale=scale)
            _, nodes = read_glb(glb)
            apply, mirrored = object_transform(n["location"], n["rotation_z"], scale)
            got = [tuple(gltf_to_map(q) for q in t) for t in nodes[0].triangles]
            want = [tuple(apply(n["mesh"].vertices[i]) for i in t) for t in n["mesh"].triangles()]
            if mirrored:
                want = [(a, c, b) for a, b, c in want]
            self.assertEqual(len(got), len(want))
            for g, w in zip(got, want):
                for gp, wp in zip(g, w):
                    for a, b in zip(gp, wp):
                        self.assertAlmostEqual(a, b, places=4)
            # outward-facing in both cases: positive signed volume for the closed chiral tetrahedron
            self.assertGreater(signed_volume(got), 0, scale)

    def test_specific_rejections(self):
        glb, _ = self.glb()
        read_glb(patch_glb(glb, lambda gl: None))

        def setter(path, value):
            def fn(gl):
                d = gl
                for k in path[:-1]:
                    d = d[k]
                d[path[-1]] = value
            return fn
        cases = {
            "buffer uri": setter(["buffers", 0, "uri"], "x.bin"),
            "extensionsRequired": setter(["extensionsRequired"], ["KHR_draco_mesh_compression"]),
            "triangle strip": setter(["meshes", 0, "primitives", 0, "mode"], 5),
            "matrix and TRS": setter(["nodes", 0, "matrix"], [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]),
            "cycle": setter(["nodes", 0, "children"], [0]),
            "image uri": setter(["images"], [{"uri": "tex.png"}]),
            "version": setter(["asset", "version"], "1.0"),
            "skin": setter(["nodes", 0, "skin"], 0),
            "quaternion": setter(["nodes", 0, "rotation"], [0, 0.5, 0, 0.5]),
            "accessor overrun": setter(["accessors", 0, "count"], 10 ** 6),
            "index type": setter(["accessors", 3, "componentType"], 5126),
            "two buffers": lambda gl: gl["buffers"].append({"byteLength": 4}),
        }
        for what, fn in cases.items():
            with self.subTest(what), self.assertRaises(PackageError):
                read_glb(patch_glb(glb, fn))

    def test_fuzzed_glb_raises_only_package_error(self):
        glb, _ = self.glb()
        rnd = random.Random(1234)
        for _ in range(400):
            b = bytearray(glb)
            k = rnd.randrange(3)
            if k == 0:
                for _ in range(rnd.randint(1, 4)):
                    b[rnd.randrange(len(b))] = rnd.randrange(256)
            elif k == 1:
                b = b[:rnd.randrange(len(b))]
            else:
                pos = rnd.randrange(len(b) - 4)
                b[pos:pos + 4] = struct.pack("<I", rnd.choice([0, 1, 3, 0xFFFFFFFF, 0x7FFFFFFF, len(b)]))
            try:
                read_glb(bytes(b))
            except PackageError:
                pass


# --- axes and handedness ------------------------------------------------------------------

class AxesTest(unittest.TestCase):
    def test_mappings_are_exact(self):
        p = (3.0, -7.0, 2.0)  # east 3, south 7, up 2
        self.assertEqual(map_to_gltf(p), (3.0, 2.0, 7.0))
        self.assertEqual(map_to_unity_x_negated(p), (-3.0, 2.0, 7.0))
        self.assertEqual(gltf_to_map(map_to_gltf(p)), p)
        self.assertEqual(mat_vec(MAP_FROM_GLTF, map_to_gltf(p)), p)
        self.assertEqual(mat_vec(MAP_FROM_UNITY, map_to_unity_x_negated(p)), p)
        self.assertEqual(det3(MAP_FROM_GLTF), 1)    # rotation: winding preserved
        self.assertEqual(det3(MAP_FROM_UNITY), -1)  # reflection: the importer must reverse winding
        self.assertEqual(pkg.AXES["map_from_gltf"], MAP_FROM_GLTF)
        self.assertEqual(pkg.AXES["map_from_unity"], MAP_FROM_UNITY)

    def test_chiral_scene_through_glb_and_unity_import(self):
        m = chiral_mesh()
        loc = (12.0, 34.0, 5.0)
        glb = write_glb([{"name": "c", "mesh": m, "location": loc, "rotation_z": 0.4, "scale": 1.0}], MATERIALS)
        _, nodes = read_glb(glb)
        apply, _ = object_transform(loc, 0.4, 1.0)
        map_tris = [tuple(apply(m.vertices[i]) for i in t) for t in m.triangles()]
        gltf_tris = nodes[0].triangles
        good, naive = unity_import(gltf_tris), [tuple((-p[0], p[1], p[2]) for p in t) for t in gltf_tris]
        for mt, gt, ut, nt in zip(map_tris, gltf_tris, good, naive):
            n_map = unit(cross(*mt))
            self.assertGreater(dot(unit(cross(*gt)), map_to_gltf(n_map)), 0.99)            # rotation keeps CCW
            self.assertGreater(dot(unit(cross(*ut)), map_to_unity_x_negated(n_map)), 0.99)  # importer reverses
            self.assertLess(dot(unit(cross(*nt)), map_to_unity_x_negated(n_map)), -0.99)    # forgot to reverse
            for q, u in zip(mt, (ut[0], ut[2], ut[1])):
                for a, b in zip(map_to_unity_x_negated(q), u):
                    self.assertAlmostEqual(a, b, places=4)
        self.assertGreater(signed_volume(map_tris), 0)


# --- orientation probes ---------------------------------------------------------------------

class ProbeTest(unittest.TestCase):
    def collision(self, objs):
        return read_collision(write_collision([col_of(o) for o in objs]))

    def test_probe_fields_follow_the_contract(self):
        col = self.collision(scene())
        probes = select_orientation_probes(col)
        self.assertEqual([p["node"] for p in probes], ["chiral", "box", "terrain"])
        for p in probes:
            self.assertEqual(set(p), {"node", "point_map", "point_gltf", "point_unity_x_negated", "triangle_map",
                                      "normal_map", "normal_unity_x_negated"})
            pm, nm, tri = p["point_map"], p["normal_map"], p["triangle_map"]
            self.assertEqual(p["point_gltf"], list(map_to_gltf(pm)))
            self.assertEqual(p["point_unity_x_negated"], list(map_to_unity_x_negated(pm)))
            self.assertEqual(p["normal_unity_x_negated"], list(map_to_unity_x_negated(nm)))
            self.assertGreaterEqual(abs(pm[0]), 1.0)
            self.assertGreaterEqual(abs(pm[1]), 1.0)
            self.assertEqual(tri[0], pm)
            self.assertGreater(dot(unit(cross(*tri)), nm), 0.9999)
            entry = next(e for e in col.objects if e["name"] == p["node"])
            verts = {v for t in col.object_triangles(entry) for v in t}
            self.assertTrue(all(math.dist(v, (-pm[0], pm[1], pm[2])) > 0.5 for v in verts))
            self.assertIn(tuple(tuple(q) for q in tri), {tuple(t) for t in col.object_triangles(entry)})

    def test_at_most_three_and_non_terrain_first(self):
        extra = [obj(f"b{k}", f"osm:way/{10 + k}", "building", chiral_mesh(f"b{k}"), (60.0 + 20 * k, 70.0, 3.0))
                 for k in range(4)]
        probes = select_orientation_probes(self.collision(scene(extra)))
        self.assertEqual(len(probes), 3)
        self.assertEqual(len({p["node"] for p in probes}), 3)
        self.assertNotIn("terrain", [p["node"] for p in probes])

    def test_terrain_used_when_no_other_node_qualifies(self):
        objs = [obj("terrain", "terrain:grid", "terrain", grid_terrain_mesh(AREA_W, AREA_H, 20.0)),
                obj("box", "osm:way/2", "building", box_mesh(-5, 10, 5, 20, 0, 6))]  # X-symmetric about x = 0
        self.assertEqual([p["node"] for p in select_orientation_probes(self.collision(objs))], ["terrain"])

    def test_symmetric_scene_has_no_probes(self):
        sym = scene_symmetric()
        self.assertEqual(select_orientation_probes(self.collision(sym)), [])

    def test_simulated_importers(self):
        objs = scene()
        col = self.collision(objs)
        _, nodes = read_glb(write_glb([node_of(o) for o in objs], MATERIALS))
        by_name = {n.name: n for n in nodes}
        for probe in select_orientation_probes(col):
            tris = by_name[probe["node"]].triangles
            self.assertIsNone(verify_probe_in_unity(probe, unity_import(tris)))
            no_reversal = [tuple((-p[0], p[1], p[2]) for p in t) for t in tris]
            self.assertIn("winding", verify_probe_in_unity(probe, no_reversal))
            no_negation = [(a, c, b) for a, b, c in tris]
            self.assertIn("no vertex", verify_probe_in_unity(probe, no_negation))
            gltf_as_is = list(tris)
            self.assertIsNotNone(verify_probe_in_unity(probe, gltf_as_is))


def scene_symmetric():
    return [obj("terrain", "terrain:grid", "terrain",
                grid_terrain_mesh(AREA_W, AREA_H, 20.0, lambda x, y: 2.0 + 0.01 * y + 0.001 * x * x)),
            obj("box", "osm:way/2", "building", box_mesh(-6, 10, 6, 20, 3, 9))]


# --- winding -------------------------------------------------------------------------------

def tri_grid(n, s=1.0):
    out = []
    for j in range(n):
        for i in range(n):
            a, b, c, d = (i * s, j * s, 0.0), ((i + 1) * s, j * s, 0.1), ((i + 1) * s, (j + 1) * s, 0.2), \
                (i * s, (j + 1) * s, 0.0)
            out += [(a, b, c), (a, c, d)]
    return out


class WindingTest(unittest.TestCase):
    def test_same_reversed_rotated(self):
        tris = tri_grid(5)
        self.assertEqual(match_winding(tris, tris)["same"], len(tris))
        self.assertEqual(match_winding(tris, [(b, c, a) for a, b, c in tris])["same"], len(tris))
        st = match_winding(tris, [(a, c, b) for a, b, c in tris])
        self.assertEqual((st["reversed"], st["same"]), (len(tris), 0))
        self.assertEqual(len(st["reversed_examples"]), 3)

    def test_tolerance_ambiguity_unmatched_degenerate(self):
        tris = tri_grid(3)
        shift = lambda d: [tuple((p[0] + d, p[1], p[2]) for p in t) for t in tris]  # noqa: E731
        self.assertEqual(match_winding(tris, shift(0.003))["same"], len(tris))       # within 5 mm
        self.assertEqual(match_winding(tris, shift(0.006))["unmatched"], len(tris))  # beyond 5 mm
        double = tris + [(a, c, b) for a, b, c in tris]                               # double-sided visual
        self.assertEqual(match_winding(tris, double)["ambiguous"], len(tris))
        st = match_winding([((0, 0, 0), (1, 0, 0), (2, 0, 0))] + tris, tris)
        self.assertEqual((st["degenerate"], st["considered"]), (1, len(tris)))

    def test_lowest_total_distance_decides(self):
        # an almost-equilateral triangle whose visual copy is slightly rotated: both orientations fit within
        # 5 mm for a tiny triangle, the lowest total distance must win
        t = ((0, 0, 0), (0.004, 0, 0), (0.002, 0.0035, 0))
        v = ((0.0001, 0, 0), (0.0041, 0, 0), (0.0021, 0.0035, 0))
        self.assertEqual(match_winding([t], [v])["same"], 1)
        self.assertEqual(match_winding([t], [(v[0], v[2], v[1])])["reversed"], 1)

    def test_bounded_on_large_grid(self):
        tris = tri_grid(150)  # 45k triangles
        st = match_winding(tris, list(reversed(tris)))
        self.assertEqual(st["same"], len(tris))
        self.assertLessEqual(st["comparisons"], 3 * len(tris))

    def test_candidate_cap_counts_as_ambiguous(self):
        t = tri_grid(1)[:1]
        st = match_winding(t, t * (pkg.MAX_WINDING_CANDIDATES + 1))
        self.assertEqual(st["ambiguous"], 1)
        self.assertLessEqual(st["comparisons"], pkg.MAX_WINDING_CANDIDATES)


# --- package binding / negatives -----------------------------------------------------------

class BindingTest(TempDirCase):
    def write(self, name, objs=None, visual_nodes=None, **kw):
        members, manifest, probes = scene_members(objs or scene(), visual_nodes, **kw)
        raw_write(self.p(name), members, manifest)
        return self.p(name), manifest

    def test_valid_small_scene(self):
        path, m = self.write("ok.mbmap", heightfield_spacing=10.0)
        r = validate_package(path)
        self.assertTrue(r.ok, r.summary())
        self.assertEqual(len(m["orientation_probes"]), 3)
        self.assertTrue(all(st["same"] == st["considered"] and not st["reversed"] for st in r.winding.values()))

    def test_flipped_visual_winding_rejected(self):
        objs = scene()
        nodes = [world_node(o, reverse=True) if o["name"] == "chiral" else node_of(o) for o in objs]
        r = self.assertInvalid(self.write("flip.mbmap", objs, nodes)[0], "winding mismatch")
        self.assertTrue(any("orientation probe 0 (collision object #1)" in e for e in r.errors), r.errors)

    def test_whole_scene_x_mirror_rejected(self):
        objs = scene()
        for reverse in (False, True):  # mirrored with or without winding repair
            nodes = [world_node(o, mirror_cx=0.0, reverse=reverse) for o in objs]
            self.assertInvalid(self.write(f"mirror{reverse}.mbmap", objs, nodes)[0], "AABB mismatch")

    def test_probe_node_mirrored_in_place_rejected(self):
        objs = scene()
        o = objs[1]
        apply, _ = object_transform(o["location"], o["rotation_z"], o["scale"])
        xs = [apply(v)[0] for v in o["mesh"].vertices]
        cx = (min(xs) + max(xs)) / 2
        nodes = [world_node(x, mirror_cx=cx) if x is o else node_of(x) for x in objs]
        r = validate_package(self.write("selfmirror.mbmap", objs, nodes)[0])
        self.assertFalse(any("AABB" in e for e in r.errors), r.errors)  # same box: only probes/winding catch it
        self.assertTrue(any("orientation probe 0 (collision object #1)" in e for e in r.errors), r.errors)
        self.assertTrue(any("unambiguous visual match" in w for w in r.warnings), r.warnings)

    def test_moved_visual_and_visual_only_node_rejected(self):
        objs = scene()
        nodes = [node_of(o, location=(31.0, 40.0, 5.0)) if o["name"] == "chiral" else node_of(o) for o in objs]
        self.assertInvalid(self.write("moved.mbmap", objs, nodes)[0], "AABB mismatch")
        nodes = [node_of(o) for o in objs] + [node_of(objs[2], name="ghost")]
        self.assertInvalid(self.write("ghost.mbmap", objs, nodes)[0], "has triangles but no collision object")
        nodes = [node_of(o) for o in objs if o["name"] != "box"]
        self.assertInvalid(self.write("nobox.mbmap", objs, nodes)[0], "no glTF node")

    def test_mirrored_object_transform_accepted(self):
        objs = scene([obj("mir", "osm:way/9", "building", chiral_mesh("mir"), (-80.0, 60.0, 4.0), 1.1,
                          (-1.0, 1.0, 1.0)),
                      obj("pt", "osm:way/8", "building", chiral_mesh("pt"), (90.0, -70.0, 4.0), 0.0, -1.5)])
        path, m = self.write("mirok.mbmap", objs)
        r = validate_package(path)
        self.assertTrue(r.ok, r.summary())
        self.assertEqual(r.winding["mir"]["same"], 4)
        e = next(e for e in r.collision.objects if e["name"] == "mir")
        self.assertGreater(signed_volume(r.collision.object_triangles(e)), 0)  # still outward after the mirror

    def test_symmetric_scene_valid_with_unavailable_warning(self):
        members, manifest, probes = scene_members(scene_symmetric())
        self.assertEqual(probes, [])
        self.assertEqual(manifest["orientation_probes"], [])
        self.assertIn(PROBES_UNAVAILABLE, json.loads(members["report.json"])["warnings"])
        raw_write(self.p("sym.mbmap"), members, manifest)
        r = validate_package(self.p("sym.mbmap"))
        self.assertTrue(r.ok, r.summary())
        self.assertIn(PROBES_UNAVAILABLE, r.warnings)

    def test_tampered_probes_rejected(self):
        members, manifest, _ = scene_members(scene())

        def bad(name, change, fragment):
            m = copy.deepcopy(manifest)
            change(m)
            raw_write(self.p(name), members, m)
            self.assertInvalid(self.p(name), fragment)
        bad("p0.mbmap", lambda m: m.update(orientation_probes=[]), "orientation_probes is empty")
        bad("p1.mbmap", lambda m: m["orientation_probes"].pop(), "orientation_probes has 2")

        def flip_normal(m):
            p = m["orientation_probes"][0]
            p["normal_map"] = [-c for c in p["normal_map"]]
            p["normal_unity_x_negated"] = list(map_to_unity_x_negated(p["normal_map"]))
        bad("p2.mbmap", flip_normal, "orientation probe")

        def unity_unnegated(m):
            p = m["orientation_probes"][0]
            p["point_unity_x_negated"] = p["point_gltf"]
        bad("p3.mbmap", unity_unnegated, "documented mappings")

        def reorder(m):
            p = m["orientation_probes"][0]
            t = p["triangle_map"]
            p["triangle_map"] = [t[0], t[2], t[1]]
            p["normal_map"] = [-c for c in p["normal_map"]]
            p["normal_unity_x_negated"] = list(map_to_unity_x_negated(p["normal_map"]))
        bad("p4.mbmap", reorder, "not a collision triangle")

    def test_wrong_axes_rejected(self):
        members, manifest, _ = scene_members(scene())
        manifest["axes"]["map_from_unity"] = MAP_FROM_GLTF
        raw_write(self.p("axes.mbmap"), members, manifest)
        self.assertInvalid(self.p("axes.mbmap"), "axes.map_from_gltf")


# --- identity ------------------------------------------------------------------------------

class IdentityTest(unittest.TestCase):
    def test_duplicates_deletions_and_user_objects(self):
        entries = [("b", "osm:way/2", "building"), ("b.001", "osm:way/2", "building"), ("cube", None, None),
                   ("t", "terrain:grid", "terrain"), ("z", "osm:way/77", "bogus")]
        resolved, edits = resolve_identities(entries, ["osm:way/1", "osm:way/2", "terrain:grid"])
        self.assertEqual([r[1] for r in resolved], ["osm:way/2", "osm:way/2~b.001", "user:cube", "terrain:grid",
                                                    "user:z"])
        self.assertEqual(edits, {"duplicated": [{"object": "b.001", "source_id": "osm:way/2"}],
                                 "user_added": ["cube", "z"], "removed": ["osm:way/1"]})
        self.assertEqual(resolved[2][2], "user")
        self.assertEqual(resolved[4][2], "user")

    def test_name_order_decides_the_original(self):
        resolved, edits = resolve_identities([("b.001", "osm:way/2", "building"), ("a", "osm:way/2", "building")])
        self.assertEqual(resolved[0], ("a", "osm:way/2", "building"))
        self.assertEqual(resolved[1][1], "osm:way/2~b.001")
        self.assertEqual(edits["removed"], [])

    def test_duplicate_names_rejected(self):
        with self.assertRaises(PackageError):
            resolve_identities([("a", "x", "user"), ("a", "y", "user")])


# --- full plan export ---------------------------------------------------------------------

class PlanPackageTest(TempDirCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.area, grid, cl, cls.ids, cls.sources = synthetic_inputs(os.path.join(cls.tmp, "src"))
        cls.plan = build_plan(cls.area, grid, cl, PlanOptions(seed=1))
        cls.path = os.path.join(cls.tmp, "good.mbmap")
        cls.manifest, cls.result = plan_to_package(cls.plan, cls.path, "synthetic", cls.sources,
                                                   heightfield_spacing=5, created_utc=UTC)

    def test_valid_package_and_report_flow(self):
        r = validate_package(self.path)
        self.assertTrue(r.ok, r.summary())
        m = r.manifest
        with zipfile.ZipFile(self.path) as z:
            self.assertEqual(r.package_id, package_id_of(z.read("manifest.json")))
            report = json.loads(z.read("report.json"))
            notices = z.read("NOTICES.txt").decode()
            hf = read_heightfield(z.read("collision/terrain.mbhf"))
        self.assertTrue(r.package_id.startswith("sha256:"))
        self.assertNotIn("package_id", m)
        self.assertEqual(m["georeference"]["vertical_datum"], "SYNTHETIC")
        self.assertEqual(m["georeference"]["z_offset_m"], self.plan.area.frame.z_offset)
        self.assertEqual({f["role"] for f in m["files"]}, {"visual", "collision", "notices", "report", "heightfield"})
        self.assertEqual(len(m["objects"]), len(self.plan.objects))
        self.assertEqual(len(m["orientation_probes"]), 3)
        self.assertTrue(all(p["node"] != "terrain" for p in m["orientation_probes"][:1]))
        self.assertIn("OpenStreetMap", notices)
        for key in ("invalid_features", "unsupported_features", "budget", "z_offset_m", "counts",
                    "building_overlaps", "inferred"):
            if key in self.plan.report:
                self.assertEqual(report[key], json.loads(json.dumps(self.plan.report[key])), key)
        self.assertIn("budget", report)
        self.assertTrue(any("bridge" in u["reason"] for u in report["unsupported_features"]))
        self.assertEqual(m["warnings_count"], len(report["warnings"]))
        self.assertEqual(report["export"]["objects"], len(self.plan.objects))
        self.assertEqual(report["edits"], {"duplicated": [], "user_added": [], "removed": []})
        self.assertEqual(m["edits"], {"duplicated": 0, "user_added": 0, "removed": 0})
        self.assertEqual(sum(math.isnan(v) for row in hf["z"] for v in row), 0)

    def test_reproducible_identity(self):
        m2, r2 = plan_to_package(self.plan, self.p("again.mbmap"), "synthetic", self.sources, heightfield_spacing=5,
                                 created_utc=UTC)
        self.assertEqual(m2, self.manifest)
        self.assertEqual(r2.package_id, self.result.package_id)

    def test_collision_comes_from_final_meshes_and_transforms(self):
        col = self.result.collision
        for o in self.plan.objects:
            md = o.mesh if o.mesh is not None else self.plan.shared_meshes[o.mesh_key]
            apply, _ = object_transform(o.location, o.rotation_z, o.scale)
            used = {i for t in md.triangles() for i in t}
            pts = [apply(md.vertices[i]) for i in used]
            e = next(e for e in col.objects if e["name"] == o.name)
            self.assertEqual(e["class"], o.mb_class)
            want = [min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts),
                    max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts)]
            for a, b in zip(e["aabb"], want):
                self.assertAlmostEqual(a, b, delta=1e-3)
            self.assertTrue(all(col.tri_class[t] == CLASSES[o.mb_class]
                                for t in range(e["tri_start"], e["tri_start"] + e["tri_count"])))

    def test_edits_flow_into_manifest_and_report(self):
        plan = copy.deepcopy(self.plan)
        generated = [o.mb_id for o in plan.objects]
        src = next(o for o in plan.objects if o.mb_id == f"osm:way/{self.ids['L']}")
        dup = copy.copy(src)
        dup.name = src.name + ".001"
        dup.location = (src.location[0] + 1.0, src.location[1], src.location[2])
        user = copy.copy(src)
        user.name, user.mb_id, user.mb_class = "my_cube", None, "prop"
        user.location = (src.location[0] - 30.0, src.location[1] + 10.0, src.location[2])
        gone = f"osm:way/{self.ids['gabled']}"
        plan.objects = [o for o in plan.objects if o.mb_id != gone] + [dup, user]
        m, r = plan_to_package(plan, self.p("edited.mbmap"), "synthetic", self.sources, generated_ids=generated)
        self.assertTrue(r.ok, r.summary())
        self.assertEqual(m["edits"], {"duplicated": 1, "user_added": 1, "removed": 1})
        ids = {e["name"]: (e["mb_id"], e["class"]) for e in r.collision.objects}
        self.assertEqual(ids[dup.name], (f"{src.mb_id}~{dup.name}", src.mb_class))
        self.assertEqual(ids["my_cube"], ("user:my_cube", "prop"))
        self.assertNotIn(gone, {v[0] for v in ids.values()})
        with zipfile.ZipFile(self.p("edited.mbmap")) as z:
            rep = json.loads(z.read("report.json"))
        self.assertEqual(rep["edits"]["removed"], [gone])

    def test_edited_transform_is_what_collides(self):
        plan = copy.deepcopy(self.plan)
        o = next(x for x in plan.objects if x.mb_id == f"osm:way/{self.ids['L']}")
        o.location = (o.location[0] + 25.0, o.location[1] - 5.0, o.location[2] + 1.0)
        o.rotation_z = 0.5
        _, r = plan_to_package(plan, self.p("moved.mbmap"), "synthetic", self.sources)
        self.assertTrue(r.ok, r.summary())
        entry = next(e for e in r.collision.objects if e["mb_id"] == o.mb_id)
        apply, _ = object_transform(o.location, 0.5, 1.0)
        xs, ys, zs = zip(*[apply(v) for v in o.mesh.vertices])
        for a, b in zip(entry["aabb"], [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]):
            self.assertAlmostEqual(a, b, places=3)

    def test_failed_export_keeps_previous_package(self):
        from map_builder.core import pipeline
        target = self.p("keep.mbmap")
        plan_to_package(self.plan, target, "synthetic", self.sources)
        before = read_bytes(target)
        with mock.patch.object(pipeline, "write_glb", lambda *a, **k: b"garbage"):
            with self.assertRaises(PackageError):
                plan_to_package(self.plan, target, "synthetic", self.sources)
        self.assertEqual(read_bytes(target), before)
        self.assertFalse([f for f in os.listdir(self.tmp) if f.endswith(".tmp")])
        with self.assertRaises(PackageError):
            plan_to_package(self.plan, self.p("x.zip"), "synthetic", self.sources)
        self.assertFalse(os.path.exists(self.p("x.zip")))

    def test_inconsistent_visual_is_never_written(self):
        from map_builder.core import pipeline
        orig = pipeline.write_glb
        target = next(o.name for o in self.plan.objects if o.mb_class == "building")

        def flipped(nodes, materials, generator=None, extras=None):
            out = []
            for n in nodes:
                if n["name"] == target:
                    md = copy.deepcopy(n["mesh"])
                    md.faces = [tuple(reversed(f)) for f in md.faces]
                    n = dict(n, mesh=md)
                out.append(n)
            return orig(out, materials, generator=generator)
        with mock.patch.object(pipeline, "write_glb", flipped):
            with self.assertRaises(PackageError) as cm:
                plan_to_package(self.plan, self.p("bad.mbmap"), "synthetic", self.sources)
        self.assertIn("winding mismatch", str(cm.exception))
        self.assertFalse(os.path.exists(self.p("bad.mbmap")))


# --- validator robustness ---------------------------------------------------------------------

class ValidatorTest(TempDirCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.members, cls.manifest, _ = scene_members(scene(), heightfield_spacing=10.0)
        cls.path = os.path.join(cls.tmp, "base.mbmap")
        raw_write(cls.path, cls.members, cls.manifest)
        assert validate_package(cls.path).ok

    def variant(self, name, change_members=None, change_manifest=None):
        members, manifest = copy.deepcopy(self.members), copy.deepcopy(self.manifest)
        if change_members:
            change_members(members)
        rehash(members, manifest)
        if change_manifest:
            change_manifest(manifest)
        raw_write(self.p(name), members, manifest)
        return self.p(name)

    def with_extra(self, name, entries, patch=None):
        """Valid package plus extra raw entries [(ZipInfo|name, data)]; ``patch`` rewrites archive bytes."""
        shutil.copy(self.path, self.p(name))
        with zipfile.ZipFile(self.p(name), "a") as z:
            for zi, data in entries:
                z.writestr(zi, data, compress_type=zipfile.ZIP_DEFLATED)
        if patch:
            data = read_bytes(self.p(name))
            for a, b in patch:
                self.assertEqual(len(a), len(b))
                self.assertIn(a, data)
                data = data.replace(a, b)
            with open(self.p(name), "wb") as f:
                f.write(data)
        return self.p(name)

    def test_unsafe_names(self):
        cases = {"xx/e.txt": "../e.txt", "a_b.txt": "a\\b.txt", "xabs.txt": "/abs.txt", "C_x.txt": "C:x.txt",
                 "a/x/b.txt": "a/./b.txt", "nul_.txt": "nul\x01.txt"}
        for k, (placeholder, bad) in enumerate(cases.items()):
            path = self.with_extra(f"u{k}.mbmap", [(placeholder, b"x")], [(placeholder.encode(), bad.encode())])
            self.assertInvalid(path, "unsafe entry name")
        for bad in ["../x", "/abs", "a/../../b", "C:/x", "a\\b", "", "a//b", "./a", "a/", "a" * 300]:
            self.assertFalse(safe_member_name(bad), bad)
        self.assertTrue(safe_member_name("collision/map.mbcol"))

    def test_symlink_directory_encrypted_and_case_duplicates(self):
        link = zipfile.ZipInfo("link.txt")
        link.external_attr = (0o120777) << 16
        self.assertInvalid(self.with_extra("sym.mbmap", [(link, b"/etc/passwd")]), "not a regular file")
        self.assertInvalid(self.with_extra("dir.mbmap", [(zipfile.ZipInfo("somedir/"), b"")]), "not a regular file")
        self.assertInvalid(self.with_extra("case.mbmap", [("notices.TXT", b"x")]), "duplicate entry")
        # encrypted: set the flag bit in the central directory record of the extra member
        path = self.with_extra("enc.mbmap", [("secret.txt", b"x")])
        data = bytearray(read_bytes(path))
        cd = data.rfind(b"PK\x01\x02")
        data[cd + 8] |= 1
        with open(path, "wb") as f:
            f.write(data)
        self.assertInvalid(path, "is encrypted")

    def test_resource_bounds(self):
        many = [(f"f{k}.txt", b"x") for k in range(pkg.MAX_ENTRIES)]
        self.assertInvalid(self.with_extra("many.mbmap", many), "too many entries")
        self.assertInvalid(self.with_extra("bomb.mbmap", [("bomb.bin", b"\0" * 2_000_000)]), "compression ratio")
        with mock.patch.object(pkg, "MAX_TOTAL_UNCOMPRESSED", 1000):
            self.assertInvalid(self.path, "uncompressed size")
        with mock.patch.object(pkg, "MAX_MANIFEST_BYTES", 100):
            self.assertInvalid(self.path, "manifest.json exceeds")

    def test_unlisted_missing_and_size_mismatch(self):
        self.assertInvalid(self.with_extra("extra.mbmap", [("extra.bin", b"x")]), "unlisted file in package")
        path = self.variant("missing.mbmap", change_manifest=lambda m: m["files"].append(
            {"path": "extra.bin", "role": "x", "media_type": "x", "sha256": "0" * 64, "bytes": 1}))
        self.assertInvalid(path, "listed file missing from package")

        def grow(m):
            next(f for f in m["files"] if f["path"] == "visual/map.glb")["bytes"] += 1
        self.assertInvalid(self.variant("size.mbmap", change_manifest=grow), "manifest bytes")

    def test_hash_mismatch(self):
        def flip(m):
            m["collision/map.mbcol"] = m["collision/map.mbcol"][:100] + bytes([m["collision/map.mbcol"][100] ^ 1]) \
                + m["collision/map.mbcol"][101:]
        members = copy.deepcopy(self.members)
        flip(members)
        raw_write(self.p("hash.mbmap"), members, self.manifest)
        self.assertInvalid(self.p("hash.mbmap"), "SHA-256 mismatch")

    def test_garbage_and_truncated(self):
        with open(self.p("garbage.mbmap"), "wb") as f:
            f.write(b"not a zip")
        self.assertInvalid(self.p("garbage.mbmap"), "not a readable package")
        data = read_bytes(self.path)
        with open(self.p("trunc.mbmap"), "wb") as f:
            f.write(data[:len(data) // 2])
        self.assertInvalid(self.p("trunc.mbmap"), "not a readable package")
        self.assertInvalid(self.p("does-not-exist.mbmap"), "not a readable package")

    def test_fuzzed_archive_never_raises(self):
        data = read_bytes(self.path)
        rnd = random.Random(99)
        for k in range(60):
            b = bytearray(data)
            for _ in range(rnd.randint(1, 8)):
                b[rnd.randrange(len(b))] = rnd.randrange(256)
            path = self.p("fuzz.mbmap")
            with open(path, "wb") as f:
                f.write(b)
            r = validate_package(path)  # must not raise
            self.assertIsInstance(r.errors, list)

    def test_manifest_json_and_version(self):
        raw = manifest_bytes(self.manifest).decode()

        def with_raw(name, text):
            raw_write(self.p(name), self.members, None, manifest_raw=text.encode())
            return self.p(name)
        self.assertInvalid(with_raw("nan.mbmap", raw.replace("{", '{"x": NaN, ', 1)), "strict")
        self.assertInvalid(with_raw("dupkey.mbmap", raw.replace("{", '{"name": "a", ', 1)), "duplicate key")
        self.assertInvalid(with_raw("array.mbmap", "[]"), "JSON object")
        self.assertInvalid(self.variant("v2.mbmap", change_manifest=lambda m: m.update(schema_version="2.0.0")),
                           "unsupported schema major version")
        self.assertInvalid(self.variant("schema.mbmap", change_manifest=lambda m: m.update(schema="other")),
                           "schema")
        path = self.variant("v11.mbmap", change_manifest=lambda m: m.update(schema_version="1.1.0",
                                                                             future_field={"a": 1}))
        r = validate_package(path)
        self.assertTrue(r.ok, r.summary())
        with zipfile.ZipFile(path) as z:
            self.assertEqual(r.package_id, "sha256:" + pkg.sha256(z.read("manifest.json")))
        self.assertInvalid(self.variant("nogeo.mbmap", change_manifest=lambda m: m.pop("georeference")),
                           "georeference missing")
        self.assertInvalid(self.variant("nodatum.mbmap", change_manifest=lambda m: m["georeference"].pop(
            "vertical_datum")), "vertical_datum")

    def test_payload_tamper_with_fixed_hashes(self):
        def col_version(members):
            b = bytearray(members["collision/map.mbcol"])
            struct.pack_into("<I", b, 8, 2)
            members["collision/map.mbcol"] = bytes(b)
        self.assertInvalid(self.variant("cv.mbmap", col_version), "unsupported version")

        def hf_value(members):
            b = bytearray(members["collision/terrain.mbhf"])
            v = struct.unpack_from("<f", b, 48 + 4 * 7)[0]
            struct.pack_into("<f", b, 48 + 4 * 7, v + 0.5)
            members["collision/terrain.mbhf"] = bytes(b)
        self.assertInvalid(self.variant("hf.mbmap", hf_value), "heightfield: value")
        self.assertInvalid(self.variant("cnt.mbmap", change_manifest=lambda m: m["collision"].update(
            triangle_count=m["collision"]["triangle_count"] + 1)), "counts differ")
        self.assertInvalid(self.variant("hfn.mbmap", change_manifest=lambda m: m["heightfield"].update(nan_cells=3)),
                           "heightfield: manifest")
        self.assertInvalid(self.variant("nohf.mbmap", change_manifest=lambda m: m.update(heightfield=None)),
                           "heightfield must be non-null")
        self.assertInvalid(self.variant("notice.mbmap", lambda ms: ms.update({"NOTICES.txt": b"nothing"})),
                           "NOTICES.txt lacks")
        self.assertInvalid(self.variant("wc.mbmap", change_manifest=lambda m: m.update(
            warnings_count=m["warnings_count"] + 1)), "warnings_count")
        self.assertInvalid(self.variant("ed.mbmap", change_manifest=lambda m: m["edits"].update(removed=2)),
                           "edits lists do not match")
        self.assertInvalid(self.variant("obj.mbmap", change_manifest=lambda m: m["objects"][1].update(
            mb_id="osm:way/12345")), "differ between manifest and collision")
        self.assertInvalid(self.variant("sec.mbmap", change_manifest=lambda m: m["sources"][1].update(
            endpoint="https://x.example/api?token=abcd1234")), "credential-like")
        self.assertInvalid(self.variant("noelev.mbmap", change_manifest=lambda m: m.update(
            sources=[s for s in m["sources"] if s["kind"] != "elevation"])), "no elevation source")


# --- pipeline -----------------------------------------------------------------------------

SECRET_URL = "https://user:hunter2@overpass.example.com/api/SECRETPATH/interpreter?key=SECRETKEY"


class FakeClient:
    def __init__(self, body=None, error=None):
        self.body, self.error, self.calls = body, error, []
        self.max_bytes = 1 << 30
        self.bytes_downloaded = 0

    def fetch(self, url, method="GET", headers=None, data=None, byte_range=None, max_bytes=None,
              not_found_is_coverage=False):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.body


class PipelineTest(TempDirCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.osm, cls.dem, _ = write_synthetic_fixtures(os.path.join(cls.tmp, "src"))
        cls.osm_xml = build_synthetic_osm()[0].xml().encode("utf-8")

    def settings(self, **kw):
        base = dict(elevation_source="file", elevation_file=self.dem, elevation_vertical_datum="SYNTHETIC",
                    elevation_license="SYNTHETIC test data (no licence required)", osm_source="file",
                    osm_file=self.osm, heightfield_spacing=None)
        base.update(kw)
        return Settings(**base)

    def test_settings_validation(self):
        with self.assertRaises(TypeError):
            Settings(elevation_sauce="file")
        with self.assertRaises(ValueError):
            Settings(elevation_source="srtm")
        with self.assertRaises(ValueError):
            Settings(osm_source="file")
        with self.assertRaises(ValueError):
            Settings(terrain_spacing=math.nan)
        self.assertNotIn("SECRET", repr(Settings(overpass_url=SECRET_URL)))
        self.assertNotIn("hunter2", repr(Settings(overpass_url=SECRET_URL)))

    def test_no_secrets_in_package(self):
        client = FakeClient(self.osm_xml)
        out = self.p("cred.mbmap")
        m, r = build_package(AREA, self.settings(osm_source="overpass", overpass_url=SECRET_URL), out, "cred",
                             client=client)
        self.assertTrue(r.ok, r.summary())
        self.assertEqual(client.calls, [SECRET_URL])
        with zipfile.ZipFile(out) as z:
            for n in z.namelist():
                blob = z.read(n)
                for s in (b"SECRET", b"hunter2", b"user:"):
                    self.assertNotIn(s, blob, n)
        osm_src = next(s for s in m["sources"] if s["kind"] == "features")
        self.assertEqual(osm_src["endpoint"], "https://overpass.example.com")
        self.assertNotIn("query", osm_src)
        self.assertEqual(len(osm_src["query_sha256"]), 64)

    def test_cache_override_pass_through(self):
        cache = self.p("cache")
        s = self.settings(osm_source="overpass", overpass_url=SECRET_URL, cache_dir=cache, allow_cache_override=True)
        with self.assertRaises(ValueError):
            build_package(AREA, s, self.p("c0.mbmap"), "c", client=FakeClient(self.osm_xml))
        self.assertFalse(os.path.exists(self.p("c0.mbmap")))
        s = self.settings(osm_source="overpass", overpass_url=SECRET_URL, cache_dir=cache, allow_cache_override=True,
                          osm_cache_dataset_id="test-mirror")
        c1, c2 = FakeClient(self.osm_xml), FakeClient(self.osm_xml)
        build_package(AREA, s, self.p("c1.mbmap"), "c", client=c1)
        m2, _ = build_package(AREA, s, self.p("c2.mbmap"), "c", client=c2)
        self.assertEqual((len(c1.calls), len(c2.calls)), (1, 0))
        self.assertTrue(next(x for x in m2["sources"] if x["kind"] == "features")["from_cache"])
        for root, _, files in os.walk(cache):
            for f in files:
                self.assertNotIn(b"SECRET", read_bytes(os.path.join(root, f)))
        # without the opt-in a non-default endpoint is never cached
        c3, c4 = FakeClient(self.osm_xml), FakeClient(self.osm_xml)
        s = self.settings(osm_source="overpass", overpass_url="https://other.example.com/api", cache_dir=cache)
        build_package(AREA, s, self.p("c3.mbmap"), "c", client=c3)
        build_package(AREA, s, self.p("c4.mbmap"), "c", client=c4)
        self.assertEqual((len(c3.calls), len(c4.calls)), (1, 1))

    def test_no_fallback_on_failure(self):
        cases = [
            (self.settings(elevation_file=self.p("missing.asc")), None, (OSError, MapBuilderError)),
            (self.settings(osm_source="overpass"), FakeClient(error=NetworkError("HTTP 404", status=404)),
             NetworkError),
            (self.settings(elevation_source="copernicus"), FakeClient(error=CoverageError("no tile")), CoverageError),
            (self.settings(osm_source="overpass"), FakeClient(b"<osm><remark>timeout</remark></osm>"),
             MapBuilderError),
            (self.settings(plan_options=PlanOptions(max_triangles=500)), None, LimitError),
        ]
        for k, (s, client, exc) in enumerate(cases):
            out = self.p(f"fail{k}.mbmap")
            with self.subTest(k), self.assertRaises(exc):
                build_package(AREA, s, out, "f", client=client or FakeClient(error=AssertionError("no network")))
            self.assertFalse(os.path.exists(out))

    def test_assemble_refuses_credentials(self):
        sources = synthetic_sources()
        sources[1]["endpoint"] = "https://mirror.example.com/api?access_token=abcdef"
        with self.assertRaises(PackageError):
            scene_members(scene(), sources=sources)
        with self.assertRaises(PackageError):
            scene_members(scene(), sources=[s for s in synthetic_sources() if s["kind"] != "elevation"])


class CliTest(TempDirCase):
    def cli(self, *argv):
        spec = importlib.util.spec_from_file_location("mbmap_cli", os.path.join(ROOT, "tools", "mbmap_cli.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = mod.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_build_and_validate(self):
        osm, dem, _ = write_synthetic_fixtures(self.p("src"))
        out = self.p("cli.mbmap")
        args = ["build", "--osm", osm, "--dem", dem, "--datum", "SYNTHETIC", "--dem-license", "SYNTHETIC",
                "--lat", "47.0", "--lon", "8.0", "--width", "400", "--height", "300", "--name", "cli", "--out", out]
        code, stdout, _ = self.cli(*args)
        self.assertEqual(code, 0, stdout)
        self.assertIn("VALID", stdout)
        self.assertEqual(self.cli("validate", out)[0], 0)
        with open(self.p("junk.mbmap"), "wb") as f:
            f.write(b"junk")
        self.assertEqual(self.cli("validate", self.p("junk.mbmap"))[0], 1)
        bad = list(args)
        bad[bad.index(dem)] = self.p("nope.asc")
        bad[bad.index(out)] = self.p("cli2.mbmap")
        code, _, err = self.cli(*bad)
        self.assertEqual(code, 2)
        self.assertIn("ERROR", err)
        self.assertFalse(os.path.exists(self.p("cli2.mbmap")))


# --- review fixes (PR #4) --------------------------------------------------------------------------

def flipped_mesh(src, name=None, drop_faces=0):
    """Copy of ``src`` with every face reversed; ``drop_faces`` removes the last faces (opens a solid)."""
    m = MeshData(name or src.name)
    for v in src.vertices:
        m.add_vertex(*v)
    faces = list(zip(src.faces, src.face_materials, src.face_colors))
    for f, mi, c in faces[:len(faces) - drop_faces]:
        m.add_face(tuple(reversed(f)), src.materials[mi], c)
    return m


def copy_mesh(src, name=None, drop_faces=0, extra_faces=()):
    m = MeshData(name or src.name)
    for v in src.vertices:
        m.add_vertex(*v)
    faces = list(zip(src.faces, src.face_materials, src.face_colors))
    for f, mi, c in faces[:len(faces) - drop_faces]:
        m.add_face(tuple(f), src.materials[mi], c)
    for pts in extra_faces:
        m.add_face(tuple(m.add_vertex(*p) for p in pts), "MB Wall", (0.5, 0.5, 0.5))
    return m


class ReviewFixesTest(TempDirCase):
    # 1: one-to-one binding on export; visual-only triangles reported by the validator
    def test_writer_requires_one_to_one_binding(self):
        objs = scene()
        chiral = objs[1]
        # an extra visual-only triangle strictly inside the chiral object's box (AABB unchanged)
        extra = copy_mesh(chiral["mesh"], extra_faces=[((1.0, 0.3, 0.2), (2.0, 0.3, 0.2), (1.0, 0.8, 0.2))])
        nodes = [node_of(o, mesh=extra) if o is chiral else node_of(o) for o in objs]
        members, manifest, _ = scene_members(objs, nodes)
        with self.assertRaises(PackageError) as cm:
            pkg.write_package(self.p("extra.mbmap"), members, manifest)
        self.assertIn("one-to-one", str(cm.exception))
        self.assertIn("1 visual triangle(s) have no collision counterpart", str(cm.exception))
        self.assertFalse(os.path.exists(self.p("extra.mbmap")))
        raw_write(self.p("extra_raw.mbmap"), members, manifest)
        r = validate_package(self.p("extra_raw.mbmap"))
        self.assertTrue(r.ok, r.summary())   # consumer side: a warning, per the contract
        self.assertTrue(any("collision object #1 / glTF node #1: 1 visual triangle(s) have no collision counterpart"
                            in w for w in r.warnings), r.warnings)
        # the unchanged scene still exports
        members, manifest, _ = scene_members(scene())
        self.assertTrue(pkg.write_package(self.p("ok.mbmap"), members, manifest).ok)

    def test_one_to_one_matcher(self):
        tris = tri_grid(3)
        self.assertEqual(pkg.match_one_to_one(tris, list(reversed(tris)))["matched"], len(tris))
        st = pkg.match_one_to_one(tris, tris + tris[:1])                     # duplicate visual triangle
        self.assertEqual((st["matched"], st["visual_only"]), (len(tris), 1))
        st = pkg.match_one_to_one(tris + tris[:1], tris)                     # two collision copies, one visual
        self.assertEqual((st["matched"], st["unmatched"]), (len(tris), 1))
        st = pkg.match_one_to_one(tris, [(a, c, b) for a, b, c in tris])
        self.assertEqual(st["reversed"], len(tris))
        self.assertTrue(pkg.match_one_to_one(tris, tris, max_work=3)["work_exhausted"])

    # 2: independent collision orientation
    def test_collision_orientation_checked(self):
        base = scene()
        cases = {
            "inverted": (obj("inv", "osm:way/7", "building", flipped_mesh(chiral_mesh("inv")), (-90.0, 70.0, 3.0)),
                         "signed volume"),
            "open": (obj("open", "osm:way/7", "building", copy_mesh(box_mesh(80, 60, 90, 75, 1, 9), drop_faces=1)),
                     "not a closed, consistently oriented solid"),
            "road": (obj("rd", "osm:way/7", "road", flipped_mesh(grid_terrain_mesh(40, 20, 10.0, name="rd")),
                         (60.0, -80.0, 1.0)), "does not point up"),
        }
        for label, (bad, fragment) in cases.items():
            with self.subTest(label):
                members, manifest, _ = scene_members(base + [bad])   # visual and collision agree
                raw_write(self.p(f"orient_{label}.mbmap"), members, manifest)
                r = self.assertInvalid(self.p(f"orient_{label}.mbmap"), fragment)
                self.assertFalse(any("winding mismatch" in e for e in r.errors), r.errors)
                with self.assertRaises(PackageError):
                    pkg.write_package(self.p(f"orient_{label}_w.mbmap"), members, manifest)
        down = [obj("terrain", "terrain:grid", "terrain", flipped_mesh(grid_terrain_mesh(AREA_W, AREA_H, 20.0)))]
        members, manifest, _ = scene_members(down + base[1:])
        raw_write(self.p("orient_terrain.mbmap"), members, manifest)
        self.assertInvalid(self.p("orient_terrain.mbmap"), "terrain object #0 has")
        # degenerate triangles stay a warning and do not break closure or the up test
        col = read_collision(write_collision([ColObject("t", "terrain:grid", "terrain",
                                                        [(0, 0, 0), (1, 0, 0), (0, 1, 0), (2, 0, 0)],
                                                        [(0, 1, 2), (0, 1, 3)])]))
        self.assertEqual(pkg.collision_orientation_problems(col), [])

    def test_generated_plan_satisfies_orientation(self):
        area, grid, classified, _, sources = synthetic_inputs(self.p("gen"))
        plan = build_plan(area, grid, classified, PlanOptions())
        _, r = plan_to_package(plan, self.p("gen.mbmap"), "synthetic", sources)   # strict export validation
        self.assertTrue(r.ok, r.summary())
        members, _ = load(self.p("gen.mbmap"))
        col = read_collision(members["collision/map.mbcol"])
        self.assertTrue(any(e["class"] == "building" for e in col.objects))
        self.assertEqual(pkg.collision_orientation_problems(col), [])

    # 3: non-string class values
    def test_non_string_class_rejected(self):
        members, manifest, _ = scene_members(scene())
        for k, bad in enumerate((["building"], {"building": 1}, 2)):
            m = copy.deepcopy(manifest)
            m["objects"][1]["class"] = bad
            raw_write(self.p(f"cls{k}.mbmap"), members, m)
            r = self.assertInvalid(self.p(f"cls{k}.mbmap"), "objects[1] must be")
            self.assertIsNone(r.package_id)
        data = write_collision(two_objects())
        _, _, _, nv, nt, *_ = COL_HEADER.unpack_from(data, 0)
        table = json.loads(data[collision_size(nv, nt, 0):].rstrip(b"\0"))
        for bad in (["building"], {"x": 1}, None):
            t = copy.deepcopy(table)
            t[0]["class"] = bad
            with self.assertRaises(PackageError) as cm:
                read_collision(replace_table(data, json.dumps(t).encode()))
            self.assertIn("unknown class", str(cm.exception))
            with self.assertRaises(PackageError):
                write_collision([ColObject("a", "osm:way/1", bad, [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])])

    # 4: heightfield rasterisation work budget
    def test_heightfield_visit_budget(self):
        from map_builder.core import collision as colmod
        nx = ny = 101
        quad = [((0, 0, 0), (100, 0, 0), (100, 100, 0)), ((0, 0, 0), (100, 100, 0), (0, 100, 0))]
        piles = [tuple((p[0], p[1], 0.01 * k) for p in t) for k in range(20) for t in quad]
        with self.assertRaises(LimitError) as cm:
            rasterize_heightfield(piles, 0, 0, 1.0, nx, ny)
        self.assertIn("work budget", str(cm.exception))
        self.assertLess(colmod.heightfield_visit_budget(nx, ny), 20 * len(quad) * nx * ny / 2)
        # a legitimate terrain at the same grid (one triangle pair per cell) is far inside the budget
        legit = grid_terrain_mesh(100, 100, 1.0)
        tris = [tuple(legit.vertices[i] for i in t) for t in legit.triangles()]
        z = rasterize_heightfield(tris, -50, -50, 1.0, nx, ny)
        self.assertFalse(any(math.isnan(v) for row in z for v in row))
        # export refuses; validation reports it as an error instead of rasterising without bound
        stacked = grid_terrain_mesh(AREA_W, AREA_H, 400.0)
        for k in range(1, 20):
            for t in grid_terrain_mesh(AREA_W, AREA_H, 400.0).triangles():
                stacked.add_face(tuple(stacked.add_vertex(*grid_terrain_mesh(AREA_W, AREA_H, 400.0).vertices[i][:2],
                                                          2.0 + 0.05 * k) for i in t), "MB Terrain", (0.3, 0.3, 0.2))
        objs = [obj("terrain", "terrain:grid", "terrain", stacked)] + scene()[1:]
        with self.assertRaises(LimitError):
            scene_members(objs, heightfield_spacing=10.0)
        with mock.patch.object(colmod, "HF_VISITS_PER_POINT", 10_000):
            members, manifest, _ = scene_members(objs, heightfield_spacing=10.0)
        raw_write(self.p("hfbudget.mbmap"), members, manifest)
        r = self.assertInvalid(self.p("hfbudget.mbmap"), "heightfield: cannot be verified")
        self.assertTrue(any("work budget" in e for e in r.errors), r.errors)

    # 5: members too compressible for the ratio limit are stored
    def test_compressible_member_stored(self):
        members, manifest, _ = scene_members(scene(terrain_fn=lambda x, y: 5.0), heightfield_spacing=1.0)
        r = pkg.write_package(self.p("flat.mbmap"), members, manifest)
        self.assertTrue(r.ok, r.summary())
        with zipfile.ZipFile(self.p("flat.mbmap")) as z:
            hf = z.getinfo("collision/terrain.mbhf")
            self.assertEqual(hf.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(z.getinfo("visual/map.glb").compress_type, zipfile.ZIP_DEFLATED)
            for zi in z.infolist():
                self.assertLessEqual(zi.file_size / zi.compress_size, pkg.MAX_RATIO, zi.filename)
        self.assertEqual(pkg.MAX_RATIO, 200)

    # 6: winding candidates pruned by vertex correspondence before the cap; work budget reported
    def test_winding_prunes_noncorresponding_candidates(self):
        a, b, c = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
        cen = (1 / 3, 1 / 3, 0.0)
        visual = [(cen, cen, cen)] * pkg.MAX_WINDING_CANDIDATES + [(a, c, b)]
        st = match_winding([(a, b, c)], visual)
        self.assertEqual((st["reversed"], st["ambiguous"]), (1, 0))
        self.assertFalse(st["work_exhausted"])

    def test_winding_work_budget_reported(self):
        tris = tri_grid(3)
        st = match_winding(tris, tris, max_work=5)
        self.assertTrue(st["work_exhausted"])
        self.assertEqual(st["ambiguous"], 0)
        self.assertEqual(st["same"] + st["unchecked"], len(tris))
        self.assertGreater(st["unchecked"], 0)
        members, manifest, _ = scene_members(scene())
        raw_write(self.p("budget.mbmap"), members, manifest)
        with mock.patch.object(pkg, "MATCH_WORK_PER_TRIANGLE", 0), mock.patch.object(pkg, "MATCH_WORK_SLACK", 1):
            r = validate_package(self.p("budget.mbmap"))
        self.assertTrue(any("stopped at its work budget" in w and "not checked" in w for w in r.warnings),
                        r.warnings)

    # 7: probe triangle match is one-to-one
    def test_probe_match_is_one_to_one(self):
        def unity_to_map(u):
            return [-u[0], -u[2], u[1]]
        A, B, C = (2.0, 1.0, 3.0), (3.0, 1.0, 3.0), (3.0, 1.04, 3.0)
        probe = {"point_unity_x_negated": list(A), "triangle_map": [unity_to_map(p) for p in (A, B, C)],
                 "normal_unity_x_negated": [0.0, 0.0, 1.0]}
        for p, u in zip(probe["triangle_map"], (A, B, C)):
            self.assertLess(math.dist(map_to_unity_x_negated(p), u), 1e-12)
        imported = [(A, B, (2.0, 1.04, 3.0))]     # A twice (within 5 cm); C has no distinct counterpart
        self.assertEqual(verify_probe_in_unity(probe, imported), "no imported triangle matches triangle_map within 5 cm")
        self.assertIsNone(verify_probe_in_unity(probe, [(A, B, C)]))
        self.assertIsNone(verify_probe_in_unity(probe, [(C, A, B)]))     # same cyclic order, other start

    # 8: package_id only for a valid package
    def test_package_id_only_on_success(self):
        members, manifest, _ = scene_members(scene())
        raw_write(self.p("pid_ok.mbmap"), members, manifest)
        self.assertTrue(validate_package(self.p("pid_ok.mbmap")).package_id.startswith("sha256:"))
        bad = dict(members)
        bad["NOTICES.txt"] = members["NOTICES.txt"][:-1] + b"#"                # same size, hash mismatch
        raw_write(self.p("pid_hash.mbmap"), bad, manifest)                    # hash mismatch
        bad_payload = dict(members, **{"NOTICES.txt": b"nothing"})
        raw_write(self.p("pid_payload.mbmap"), bad_payload, rehash(bad_payload, copy.deepcopy(manifest)))
        m = copy.deepcopy(manifest)
        m["files"][0]["bytes"] += 1
        raw_write(self.p("pid_size.mbmap"), members, m)
        for name, fragment in (("pid_hash", "SHA-256 mismatch"), ("pid_payload", "NOTICES.txt lacks"),
                               ("pid_size", "manifest bytes")):
            r = self.assertInvalid(self.p(f"{name}.mbmap"), fragment)
            self.assertIsNone(r.package_id, name)
            self.assertNotIn("package_id", r.summary())

    # 9: one credential policy over the whole manifest, without echoing values
    def test_credentials_anywhere_in_manifest_not_echoed(self):
        members, manifest, _ = scene_members(scene())
        secret = "S3KR1Tvalue"
        changes = {
            "userinfo": lambda m: m["georeference"].update(projection=f"see https://bob:{secret}@x.example/p"),
            "query": lambda m: m["objects"][1]["provenance"].update(src=f"https://x.example/t?api_key={secret}"),
            "header": lambda m: m["area"].update(note=f"Authorization: Bearer {secret}abcdef"),
            "keyname": lambda m: m["generator"].update(extra={"password": secret}),
            "nested": lambda m: m["collision"].update(meta=[{"x": [f"https://h.example/?access_token={secret}"]}]),
            "oddkey": lambda m: m["sources"][0].update({f"https://h.example/?token={secret}": 1}),
        }
        for label, change in changes.items():
            with self.subTest(label):
                m = copy.deepcopy(manifest)
                change(m)
                raw_write(self.p(f"sec_{label}.mbmap"), members, m)
                r = self.assertInvalid(self.p(f"sec_{label}.mbmap"), "credential-like")
                self.assertFalse(any(secret in e for e in r.errors + r.warnings), r.errors)
                with self.assertRaises(PackageError) as cm:
                    pkg.write_package(self.p(f"sec_{label}_w.mbmap"), members, m)
                self.assertNotIn(secret, str(cm.exception))
                self.assertIn("manifest", str(cm.exception))
        m = copy.deepcopy(manifest)
        m["files"][0]["path"] = f"../{secret}"
        m["schema_version"] = secret
        raw_write(self.p("echo.mbmap"), members, m)
        r = validate_package(self.p("echo.mbmap"))
        self.assertFalse(r.ok)
        self.assertFalse(any(secret in e for e in r.errors), r.errors)
        with self.assertRaises(PackageError) as cm:
            objs = scene()
            col_bytes = write_collision([col_of(o) for o in objs])
            glb = write_glb([node_of(o) for o in objs], MATERIALS)
            objects = [{"name": o["name"], "mb_id": o["mb_id"], "class": o["cls"], "collision": True,
                        "provenance": {"api_key": secret}} for o in objs]
            assemble("test", AREA, synthetic_sources(), glb, col_bytes, objects, created_utc=UTC)
        self.assertNotIn(secret, str(cm.exception))
        self.assertIn("api_key", str(cm.exception))
        for benign in ("© OpenStreetMap contributors", "Basic geometry and terrain", "H = z + z_offset_m",
                       "https://opendatacommons.org/licenses/odbl/1-0/", "keyframe=3"):
            self.assertEqual(pkg.find_secrets({"v": benign}), [], benign)

    # 10: NOTICES.txt must carry each licence
    def test_notices_require_licence(self):
        members, manifest, _ = scene_members(scene())
        text = members["NOTICES.txt"].decode()
        for s in manifest["sources"]:
            for key in ("id", "name", "url"):
                if s["license"].get(key):
                    self.assertIn(s["license"][key], text)
        url = next(s["license"]["url"] for s in manifest["sources"] if s["license"].get("url"))
        lic_id = next(s["license"]["id"] for s in manifest["sources"] if s["license"].get("url"))
        for label, new_text, fragment in (("url", text.replace(url, "(link removed)"), "licence url of sources[1]"),
                                          ("id", text.replace(lic_id, "X"), "licence id of sources[1]")):
            with self.subTest(label):
                ms = dict(members, **{"NOTICES.txt": new_text.encode()})
                raw_write(self.p(f"notice_{label}.mbmap"), ms, rehash(ms, copy.deepcopy(manifest)))
                self.assertInvalid(self.p(f"notice_{label}.mbmap"), fragment)
        m = copy.deepcopy(manifest)
        m["sources"][0]["license"] = {"url": "https://example.org/licence"}
        raw_write(self.p("notice_nolic.mbmap"), members, m)
        self.assertInvalid(self.p("notice_nolic.mbmap"), "sources[0].license must declare")
        # a licence text is written verbatim and required verbatim
        srcs = synthetic_sources()
        srcs[0]["license"] = dict(srcs[0]["license"], text="Line one of the licence.\nLine two.")
        members, manifest, _ = scene_members(scene(), sources=srcs)
        self.assertIn("Line one of the licence.\nLine two.", members["NOTICES.txt"].decode())
        self.assertTrue(pkg.write_package(self.p("notice_text.mbmap"), members, manifest).ok)


def merged_mesh(parts, name="shells"):
    """One mesh holding several boxes; ``parts`` = [(mesh, reversed?)]."""
    m = MeshData(name)
    for src, flip in parts:
        base = len(m.vertices)
        for v in src.vertices:
            m.add_vertex(*v)
        for f in src.faces:
            f = tuple(base + i for i in f)
            m.add_face(tuple(reversed(f)) if flip else f, "MB Wall", (0.7, 0.7, 0.7))
    return m


def shifted(tri, dx):
    return tuple((p[0] + dx, p[1], p[2]) for p in tri)


class ReviewRound2Test(TempDirCase):
    """Second gpt-6.2-sol review of PR #4."""

    def orient(self, parts, **kw):
        m = merged_mesh(parts)
        col = read_collision(write_collision([ColObject("b", "osm:way/9", "building", list(m.vertices),
                                                        [tuple(t) for t in m.triangles()])]))
        return pkg.collision_orientation_problems(col, **kw)

    # 1: per-shell orientation (an outward shell cannot hide a separate inverted one)
    def test_inverted_shell_not_hidden_by_outward_shell(self):
        outer = box_mesh(0, 0, 10, 10, 0, 10)
        apart = box_mesh(20, 0, 25, 5, 0, 5)
        cavity = box_mesh(2, 2, 7, 7, 2, 7)
        big_cavity = box_mesh(1, 1, 9, 9, 1, 9)
        island = box_mesh(3, 3, 6, 6, 3, 6)
        probs = self.orient([(outer, False), (apart, True)])
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("is not inside an outward shell", probs[0])
        self.assertIn("building object #0: shell 1 of 2", probs[0])
        self.assertTrue(self.orient([(apart, True), (outer, False)]))                # order does not matter
        self.assertTrue(self.orient([(outer, True)]))                                # a lone inverted solid
        self.assertEqual(self.orient([(outer, False), (cavity, True)]), [])          # legitimate cavity
        self.assertEqual(self.orient([(outer, False), (big_cavity, True), (island, False)]), [])
        self.assertEqual(self.orient([(outer, False), (apart, False)]), [])          # two outward shells
        probs = self.orient([(outer, False), (cavity, True)], max_work=1)
        self.assertTrue(probs and "work budget" in probs[0], probs)
        # package level: visual and collision agree, so only the independent orientation check catches it
        bad = obj("twin", "osm:way/9", "building", merged_mesh([(box_mesh(60, 60, 70, 70, 0, 10), False),
                                                                (box_mesh(80, 60, 85, 65, 0, 5), True)]))
        members, manifest, _ = scene_members(scene() + [bad])
        raw_write(self.p("shells.mbmap"), members, manifest)
        r = self.assertInvalid(self.p("shells.mbmap"), "is not inside an outward shell")
        self.assertFalse(any("winding mismatch" in e for e in r.errors), r.errors)
        with self.assertRaises(PackageError):
            pkg.write_package(self.p("shells_w.mbmap"), members, manifest)
        ok = obj("hollow", "osm:way/9", "building", merged_mesh([(box_mesh(60, 60, 70, 70, 0, 10), False),
                                                                 (box_mesh(62, 62, 67, 67, 2, 7), True)]))
        members, manifest, _ = scene_members(scene() + [ok])
        self.assertTrue(pkg.write_package(self.p("hollow.mbmap"), members, manifest).ok)

    # 2: the one-to-one matcher is a maximum matching, independent of order
    def test_one_to_one_matching_is_order_independent(self):
        t = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        col = [shifted(t, 0.002), shifted(t, 0.0)]
        vis = [shifted(t, 0.001), shifted(t, 0.0065)]                  # tolerance 5 mm
        for c, v in ((col, vis), (col[::-1], vis), (col, vis[::-1]), (col[::-1], vis[::-1])):
            st = pkg.match_one_to_one(c, v)
            self.assertEqual((st["matched"], st["unmatched"], st["visual_only"]), (2, 0, 0), st)
            self.assertFalse(st["work_exhausted"])
        # a real shortage is still reported
        st = pkg.match_one_to_one(col, vis[1:])
        self.assertEqual((st["matched"], st["unmatched"]), (1, 1))
        # the export refuses explicitly when the matcher runs out of budget
        members, manifest, _ = scene_members(scene())
        with mock.patch.object(pkg, "MATCH_WORK_PER_TRIANGLE", 0), mock.patch.object(pkg, "MATCH_WORK_SLACK", 1):
            with self.assertRaises(PackageError) as cm:
                pkg.write_package(self.p("match_budget.mbmap"), members, manifest)
        self.assertIn("cannot verify binding: work budget", str(cm.exception))

    # 3a: the credential policy covers every parsed JSON payload, not only the manifest
    def test_payload_json_credential_policy(self):
        secret = "S3KR1Tvalue"
        members, manifest, _ = scene_members(scene())

        def report(ms):
            rep = json.loads(ms["report.json"])
            rep["counts"]["api_key"] = secret
            ms["report.json"] = json.dumps(rep).encode()

        def table(ms):
            data = ms["collision/map.mbcol"]
            _, _, _, nv, nt, *_ = COL_HEADER.unpack_from(data, 0)
            t = json.loads(data[collision_size(nv, nt, 0):].rstrip(b"\0"))
            t[1]["meta"] = {"password": secret}
            ms["collision/map.mbcol"] = replace_table(data, json.dumps(t).encode())

        def glb(ms):
            ms["visual/map.glb"] = patch_glb(ms["visual/map.glb"],
                                             lambda gl: gl["nodes"][1]["extras"].update(token=secret))

        for label, change in (("report", report), ("mbcol", table), ("glb", glb)):
            with self.subTest(label):
                ms = dict(members)
                change(ms)
                m = rehash(ms, copy.deepcopy(manifest))
                raw_write(self.p(f"psec_{label}.mbmap"), ms, m)
                r = self.assertInvalid(self.p(f"psec_{label}.mbmap"), "credential-like")
                self.assertFalse(any(secret in e for e in r.errors + r.warnings), r.errors)
                with self.assertRaises(PackageError) as cm:
                    pkg.write_package(self.p(f"psec_{label}_w.mbmap"), ms, m)
                self.assertIn("credential-like", str(cm.exception))
                self.assertNotIn(secret, str(cm.exception))
        self.assertTrue(validate_package(self.p("psec_report.mbmap")).errors)
        r = pkg.find_secrets({"a": [{"b": {"c": [[{"access_token": "x"}]]}}]}, "$")
        self.assertEqual(len(r), 1)
        deep = cur = {}
        for _ in range(5000):                                         # deeper than the recursion limit
            cur["k"] = {}
            cur = cur["k"]
        cur["password"] = "x"
        self.assertEqual(len(pkg.find_secrets(deep, "$")), 1)

    # 3b: diagnostics name entries by index, never by strings taken from the package
    def test_diagnostics_do_not_echo_package_strings(self):
        token = "ZZtok3n_9f8e7d"
        members, manifest, _ = scene_members(scene())
        data = members["collision/map.mbcol"]
        _, _, _, nv, nt, *_ = COL_HEADER.unpack_from(data, 0)
        off = collision_size(nv, nt, 0)
        table = json.loads(data[off:].rstrip(b"\0"))

        def renamed(ms):
            t = copy.deepcopy(table)
            t[1]["name"] = token
            ms["collision/map.mbcol"] = replace_table(data, json.dumps(t).encode())

        def dup_key(ms):
            raw = b'[{"%s": 1, "%s": 2, ' % (token.encode(), token.encode()) + json.dumps(table).encode()[2:]
            ms["collision/map.mbcol"] = replace_table(data, raw)

        def bad_class(ms):
            t = copy.deepcopy(table)
            t[1]["class"] = token
            ms["collision/map.mbcol"] = replace_table(data, json.dumps(t).encode())

        def glb_ext(ms):
            ms["visual/map.glb"] = patch_glb(ms["visual/map.glb"],
                                             lambda gl: gl.update(extensionsRequired=[token]))

        def glb_name(ms):
            ms["visual/map.glb"] = patch_glb(ms["visual/map.glb"],
                                             lambda gl: gl["nodes"][1].update(name=token))

        for label, change in (("renamed", renamed), ("dupkey", dup_key), ("class", bad_class),
                              ("glbext", glb_ext), ("glbname", glb_name)):
            with self.subTest(label):
                ms = dict(members)
                change(ms)
                raw_write(self.p(f"echo_{label}.mbmap"), ms, rehash(ms, copy.deepcopy(manifest)))
                r = validate_package(self.p(f"echo_{label}.mbmap"))
                self.assertFalse(r.ok, label)
                self.assertFalse(any(token in s for s in r.errors + r.warnings), r.errors + r.warnings)
        m = copy.deepcopy(manifest)
        m["objects"][1]["name"] = token                               # manifest object name
        raw_write(self.p("echo_manifest.mbmap"), members, m)
        r = validate_package(self.p("echo_manifest.mbmap"))
        self.assertFalse(r.ok)
        self.assertFalse(any(token in s for s in r.errors + r.warnings), r.errors)
        raw_write(self.p("echo_entry.mbmap"), dict(members, **{f"extra/{token}.txt": b"x"}), manifest)
        r = self.assertInvalid(self.p("echo_entry.mbmap"), "unlisted file in package")
        self.assertFalse(any(token in s for s in r.errors + r.warnings), r.errors)
        # writer-side messages do not echo names either
        with self.assertRaises(PackageError) as cm:
            write_collision([ColObject(token, "osm:way/1", "building", [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
                                       [(0, 1, 5)])])
        self.assertNotIn(token, str(cm.exception))
        bad = box_mesh(0, 0, 1, 1, 0, 1, name=token)
        with self.assertRaises(PackageError) as cm:
            write_glb([{"name": token, "mesh": bad, "location": (math.nan, 0.0, 0.0)}], MATERIALS)
        self.assertNotIn(token, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
