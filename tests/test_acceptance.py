"""End-to-end acceptance tests (validation stage).

They use the committed SYNTHETIC fixtures (tests/fixtures) and only fill gaps left by the unit tests:
an independent per-object GLB <-> collision cross-check of a real package, the courtyard hole, terrain
heights against the DEM, axes/handedness on a geographic package, collision after Blender-style edits,
determinism of independent builds, per-member tamper detection and resource bounds before network access.
The cross-checks below deliberately do not use the validator's own matching code.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

from map_builder.blender.bake import bake_object, export_baked
from map_builder.core import dem as dem_mod
from map_builder.core import pipeline
from map_builder.core.collision import heightfield_layout, read_collision, read_heightfield
from map_builder.core.dem import fetch_copernicus
from map_builder.core.errors import AreaError, LimitError
from map_builder.core.generate import MATERIALS, PlanOptions, build_plan
from map_builder.core.geodesy import Area, LocalFrame
from map_builder.core.glb import read_glb
from map_builder.core.package import manifest_bytes, validate_package, verify_probe_in_unity
from map_builder.core.pipeline import Settings, acquire, build_package, generate_plan

from .synthetic import dem_height
from .test_blender_bake import trs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
OSM = os.path.join(FIXTURES, "synthetic_area.osm")
DEM = os.path.join(FIXTURES, "synthetic_dem.asc")
LICENSE = "SYNTHETIC test data (no licence required)"
UTC = "2024-01-01T00:00:00Z"
TOL = 2e-3          # float32 storage of coordinates up to a few hundred metres

# features of tests/synthetic.py (map frame, metres)
COURTYARD = "bld_relation_1018"     # outer 40 x 40, inner (hole) 16 x 16, centred at (-100, -60)
COURTYARD_CENTRE = (-100.0, -60.0)
L_BUILDING = "bld_way_1007"         # L shape at x 50..90, y 20..80 (north-east)
GABLED = "bld_way_1023"
HIPPED = "bld_way_1028"
DOME = "bld_way_1043"


def fixture_settings(**kw):
    base = dict(elevation_source="file", elevation_file=DEM, elevation_vertical_datum="SYNTHETIC",
                elevation_license=LICENSE, osm_source="file", osm_file=OSM, heightfield_spacing=2.0,
                plan_options=PlanOptions(seed=1))
    base.update(kw)
    return Settings(**base)


def fixture_area():
    return Area(47.0, 8.0, 400, 300)


def read_members(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


# --- independent geometry helpers ----------------------------------------------------------------

def gltf_to_enu(p):
    """docs/PACKAGE_FORMAT.md: gltf = (x, z, -y)  =>  map = (gx, -gz, gy)."""
    return (p[0], -p[2], p[1])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v) if n > 1e-12 else None


def normal(t):
    return unit(cross(sub(t[1], t[0]), sub(t[2], t[0])))


def signed_volume(tris):
    return sum(a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
               + a[2] * (b[0] * c[1] - b[1] * c[0]) for a, b, c in tris) / 6.0


def _close(p, q, tol):
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol and abs(p[2] - q[2]) <= tol


def _same_cyclic(t, u, tol):
    """Same triangle with the same winding: ``u`` is a cyclic rotation of ``t`` (never a reversal)."""
    return any(all(_close(t[k], u[(k + r) % 3], tol) for k in range(3)) for r in range(3))


def unmatched(want, got, tol=TOL):
    """Match triangle lists one-to-one as sets with winding. Returns (unmatched in want, unmatched in got)."""
    def cell(t):
        return tuple(int(math.floor(sum(p[i] for p in t) / 3.0)) for i in range(3))
    buckets = {}
    for i, t in enumerate(got):
        buckets.setdefault(cell(t), []).append(i)
    used = set()
    missing = []
    for t in want:
        cx, cy, cz = cell(t)
        hit = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for i in buckets.get((cx + dx, cy + dy, cz + dz), ()):
                        if i not in used and _same_cyclic(t, got[i], tol):
                            hit = i
                            break
                    if hit is not None:
                        break
                if hit is not None:
                    break
            if hit is not None:
                break
        if hit is None:
            missing.append(t)
        else:
            used.add(hit)
    return missing, [t for i, t in enumerate(got) if i not in used]


def reverse(tris):
    return [(a, c, b) for a, b, c in tris]


def xy_hit(t, x, y):
    """z of triangle ``t`` above (x, y) if its XY projection (non-degenerate) contains the point, else None."""
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
    d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-9:
        return None
    u = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / d
    v = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / d
    w = 1.0 - u - v
    if min(u, v, w) < -1e-9:
        return None
    return u * az + v * bz + w * cz


def ray_hits(tris, x, y):
    return [z for z in (xy_hit(t, x, y) for t in tris) if z is not None]


class TerrainIndex:
    """Vertical ray queries on terrain triangles: height = max z at (x, y) (the heightfield rule)."""

    def __init__(self, tris, cell=10.0):
        self.cell = cell
        self.buckets = {}
        for t in tris:
            xs, ys = [p[0] for p in t], [p[1] for p in t]
            for i in range(int(math.floor(min(xs) / cell)), int(math.floor(max(xs) / cell)) + 1):
                for j in range(int(math.floor(min(ys) / cell)), int(math.floor(max(ys) / cell)) + 1):
                    self.buckets.setdefault((i, j), []).append(t)

    def height(self, x, y):
        hits = ray_hits(self.buckets.get((int(math.floor(x / self.cell)), int(math.floor(y / self.cell))), ()), x, y)
        return max(hits) if hits else None


def apply(m, p):
    return tuple(m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + m[r][3] for r in range(3))


def det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


# --- 1 + 2: committed fixture -> CLI -> .mbmap -> read back ---------------------------------------

class PackageBindingMixin:
    """Reads of a built package (cls.col / cls.entries / cls.nodes) shared by the package tests."""

    def col_tris(self, name):
        return [tuple(tuple(p) for p in t) for t in self.col.object_triangles(self.entries[name])]

    def glb_tris(self, name):
        return [tuple(gltf_to_enu(p) for p in t) for t in self.nodes[name].triangles]

    def assert_bound(self, name):
        """GLB node triangles (glTF -> ENU) == collision triangles, as sets with winding."""
        col, vis = self.col_tris(name), self.glb_tris(name)
        self.assertGreater(len(col), 0, name)
        self.assertEqual(len(col), len(vis), name)
        miss_c, miss_v = unmatched(col, vis)
        self.assertEqual((len(miss_c), len(miss_v)), (0, 0), f"{name}: {miss_c[:2]} / {miss_v[:2]}")
        # the comparison is winding-sensitive: reversed visual triangles must not match (degenerates aside)
        solid = [t for t in col if normal(t) is not None]
        miss_r, _ = unmatched(solid, reverse(vis))
        self.assertEqual(len(miss_r), len(solid), name)
        return col, vis


class FixturePackageTest(PackageBindingMixin, unittest.TestCase):
    """Builds the committed fixtures with tools/mbmap_cli.py (in process) and reads the package back."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.path = os.path.join(cls.tmp, "synthetic_sample.mbmap")
        spec = importlib.util.spec_from_file_location("mbmap_cli", os.path.join(ROOT, "tools", "mbmap_cli.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            cls.code = cli.main(["build", "--osm", OSM, "--dem", DEM, "--datum", "SYNTHETIC", "--dem-license",
                                 LICENSE, "--lat", "47.0", "--lon", "8.0", "--width", "400", "--height", "300",
                                 "--name", "synthetic_sample", "--out", cls.path])
        cls.stdout = out.getvalue()
        cls.result = validate_package(cls.path)
        members = read_members(cls.path)
        cls.manifest = json.loads(members["manifest.json"])
        cls.col = read_collision(members["collision/map.mbcol"])
        _, nodes = read_glb(members["visual/map.glb"])
        cls.nodes = {n.name: n for n in nodes}
        cls.entries = {e["name"]: e for e in cls.col.objects}
        cls.objects = {o["name"]: o for o in cls.manifest["objects"]}
        cls.hf = read_heightfield(members["collision/terrain.mbhf"])
        cls.z_offset = cls.manifest["georeference"]["z_offset_m"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_cli_build_is_valid(self):
        self.assertEqual(self.code, 0, self.stdout)
        self.assertIn("VALID", self.stdout)
        self.assertTrue(self.result.ok, self.result.summary())
        self.assertEqual(set(self.nodes), set(self.entries))     # one-to-one binding by name

    def test_non_flat_roofs_match_collision(self):
        for name, shape in ((GABLED, "gabled"), (HIPPED, "hipped"), (DOME, "dome")):
            prov = self.objects[name]["provenance"]
            self.assertEqual(prov["roof_shape_built"], shape)
            self.assertTrue(prov["roof_shape"].startswith("measured:"), prov["roof_shape"])
            col, _ = self.assert_bound(name)
            sloped = [n for n in map(normal, col) if n is not None and 0.2 < n[2] < 0.98]
            self.assertGreaterEqual(len(sloped), 2 if shape == "gabled" else 4, name)
            self.assertGreater(signed_volume(col), 0, name)

    def test_courtyard_hole_is_preserved(self):
        self.assertEqual(self.objects[COURTYARD]["mb_id"], "osm:relation/1018")
        self.assert_bound(COURTYARD)
        cls_of = {o["name"]: o["class"] for o in self.manifest["objects"]}
        col_bld = self.col.class_triangles("building")
        vis_bld = [t for n, node in self.nodes.items() if cls_of[n] == "building"
                   for t in (tuple(gltf_to_enu(p) for p in t) for t in node.triangles)]
        cx, cy = COURTYARD_CENTRE
        self.assertEqual(ray_hits(col_bld, cx, cy), [], "collision closes the courtyard")
        self.assertEqual(ray_hits(vis_bld, cx, cy), [], "GLB closes the courtyard")
        self.assertIsNotNone(TerrainIndex(self.col.class_triangles("terrain")).height(cx, cy), "no ground")
        # control: the ring itself (between the inner 16 m and outer 40 m squares) is solid in both
        for x, y in ((cx + 14.0, cy), (cx, cy - 14.0)):
            self.assertTrue(ray_hits(self.col_tris(COURTYARD), x, y))
            self.assertTrue(ray_hits(self.glb_tris(COURTYARD), x, y))

    def test_terrain_on_slope_matches_dem_and_heightfield(self):
        self.assert_bound("terrain")
        terrain = TerrainIndex(self.col.class_triangles("terrain"))
        # open ground away from buildings, roads and water (tests/synthetic.py layout)
        samples = [(-170.0, -120.0), (-150.0, 100.0), (150.0, 120.0), (160.0, -60.0), (75.0, -40.0),
                   (-80.0, 30.0), (0.0, -120.0), (120.0, 40.0)]
        for x, y in samples:
            expected = dem_height(x, y) - self.z_offset
            got = terrain.height(x, y)
            self.assertIsNotNone(got, (x, y))
            self.assertAlmostEqual(got, expected, delta=0.2, msg=f"terrain at {(x, y)}")
        # it is really a slope (0.05 east, 0.02 north + a 6 m bump), not a flat substitute
        self.assertGreater(terrain.height(150.0, 120.0) - terrain.height(-150.0, 100.0), 14.0)
        # heightfield = max z of the terrain collision at its grid points, and agrees with the DEM
        hf = self.hf
        self.assertEqual((hf["nx"], hf["ny"], hf["x0"], hf["y0"], hf["spacing"]), (201, 151, -200.0, -150.0, 2.0))
        for j in range(0, hf["ny"], 15):
            for i in range(0, hf["nx"], 20):
                x, y = hf["x0"] + i * hf["spacing"], hf["y0"] + j * hf["spacing"]
                self.assertAlmostEqual(hf["z"][j][i], terrain.height(x, y), delta=TOL, msg=f"hf at {(x, y)}")
        for x, y in samples:
            i, j = round((x - hf["x0"]) / hf["spacing"]), round((y - hf["y0"]) / hf["spacing"])
            self.assertAlmostEqual(hf["z"][j][i], dem_height(x, y) - self.z_offset, delta=0.2)

    def test_axes_and_handedness_on_geographic_package(self):
        """North-east object -> glTF +x/-z; south-west -> -x/+z; Unity (-x, z, -y) needs the winding flip."""
        frame = LocalFrame(47.0, 8.0)
        l_col = self.col_tris(L_BUILDING)
        cx = sum(p[0] for t in l_col for p in t) / (3 * len(l_col))
        cy = sum(p[1] for t in l_col for p in t) / (3 * len(l_col))
        lat, lon = frame.to_geographic(cx, cy)
        self.assertGreater(lat, 47.0)
        self.assertGreater(lon, 8.0)                      # geographically north-east of the origin
        l_gltf = [p for t in self.nodes[L_BUILDING].triangles for p in t]
        self.assertTrue(all(p[0] > 40.0 and p[2] < -10.0 for p in l_gltf))     # +x, -z
        c_gltf = [p for t in self.nodes[COURTYARD].triangles for p in t]
        self.assertTrue(all(p[0] < -70.0 and p[2] > 30.0 for p in c_gltf))     # south-west: -x, +z
        # Unity: an importer negating X gives unity = (-gx, gy, gz) = (-x, z, -y) and reverses index order;
        # Unity's left-handed Cross(b - a, c - a) in that order is the map normal mapped to Unity.
        m_from_u = self.manifest["axes"]["map_from_unity"]
        checked = 0
        for t in self.nodes[L_BUILDING].triangles:
            tm = tuple(gltf_to_enu(p) for p in t)
            n = normal(tm)
            if n is None:
                continue
            u = [(-p[0], p[1], p[2]) for p in t]
            for pu, pm in zip(u, tm):
                self.assertTrue(_close(pu, (-pm[0], pm[2], -pm[1]), 1e-9))
                back = tuple(sum(m_from_u[r][k] * pu[k] for k in range(3)) for r in range(3))
                self.assertTrue(_close(back, pm, 1e-9))
            n_unity = (-n[0], n[2], -n[1])
            flipped = normal((u[0], u[2], u[1]))
            kept = normal((u[0], u[1], u[2]))
            self.assertGreater(sum(a * b for a, b in zip(flipped, n_unity)), 0.99)
            self.assertLess(sum(a * b for a, b in zip(kept, n_unity)), -0.99)
            checked += 1
        self.assertGreaterEqual(checked, 12)

    def test_orientation_probes_match_glb_and_collision_in_unity(self):
        """The serialized manifest probes (not a re-run of the selector) agree with the collision triangles
        and with the GLB triangles transformed independently to glTF and Unity; the Unity check passes only
        with the documented winding reversal."""
        probes = self.manifest["orientation_probes"]
        self.assertGreater(len(probes), 0, "fixture package has no orientation probes")
        report = json.loads(read_members(self.path)[self.manifest["report"]])
        self.assertNotIn("orientation probes unavailable", report["warnings"])
        for k, p in enumerate(probes):
            node = p["node"]
            pm = tuple(p["point_map"])
            tri_m = [tuple(q) for q in p["triangle_map"]]
            nm = tuple(p["normal_map"])
            self.assertTrue(_close(tri_m[0], pm, 1e-9), k)
            # collision: triangle_map is one of the node's triangles, same winding; normal_map is its normal
            col_hits = [t for t in self.col_tris(node) if _same_cyclic(tri_m, t, 1e-4)]
            self.assertEqual(len(col_hits), 1, (k, node))
            self.assertGreater(sum(a * b for a, b in zip(normal(col_hits[0]), nm)), 0.999, k)
            # glTF = (x, z, -y), applied here (not via the package helpers)
            to_gltf = lambda q: (q[0], q[2], -q[1])  # noqa: E731
            self.assertTrue(_close(tuple(p["point_gltf"]), to_gltf(pm), 1e-6), k)
            glb = [tuple(tuple(q) for q in t) for t in self.nodes[node].triangles]
            want_g = tuple(to_gltf(q) for q in tri_m)
            glb_hits = [t for t in glb if _same_cyclic(want_g, t, TOL)]
            self.assertEqual(len(glb_hits), 1, (k, node))
            g = glb_hits[0]
            # Unity = (-x, z, -y) = glTF with X negated; that reflection needs the index order reversed
            to_unity = lambda q: (-q[0], q[2], -q[1])  # noqa: E731
            pu, nu = tuple(p["point_unity_x_negated"]), tuple(p["normal_unity_x_negated"])
            self.assertTrue(_close(pu, to_unity(pm), 1e-6), k)
            self.assertTrue(_close(nu, to_unity(nm), 1e-6), k)
            ux = [(-q[0], q[1], q[2]) for q in g]
            self.assertTrue(any(_close(q, pu, 0.05) for q in ux), k)
            imported = [(ux[0], ux[2], ux[1])]          # importer: negate X and reverse index order
            not_reversed = [(ux[0], ux[1], ux[2])]      # negate X only
            self.assertGreater(sum(a * b for a, b in zip(normal(imported[0]), nu)), 0.99, k)
            self.assertLess(sum(a * b for a, b in zip(normal(not_reversed[0]), nu)), -0.99, k)
            # the documented consumer check accepts the reversed import and rejects the plain reflection
            self.assertIsNone(verify_probe_in_unity(p, imported), k)
            reason = verify_probe_in_unity(p, not_reversed)
            self.assertIsNotNone(reason, k)
            self.assertIn("winding", reason)


# --- 3: simulated Blender edits through the pure bake path --------------------------------------

class RoofShapesPackageTest(PackageBindingMixin, unittest.TestCase):
    """Every new roof shape through the real export: validator-clean, GLB node == collision, and the
    fallbacks (unsupported shape, courtyard dome) listed in report.json."""

    SHAPES = ("half-hipped", "gambrel", "mansard", "round", "saltbox", "dome", "onion")

    @classmethod
    def setUpClass(cls):
        from .synthetic import OsmBuilder, rect
        cls.tmp = tempfile.mkdtemp()
        b = OsmBuilder()
        cls.ids = {}
        for k, shape in enumerate(cls.SHAPES):
            cls.ids[shape] = b.way(rect(-150 + 45 * k, 60, 14, 14 if shape in ("dome", "onion") else 22),
                                   {"building": "yes", "roof:shape": shape, "height": "10", "roof:height": "3"},
                                   closed=True)
        cls.ids["butterfly"] = b.way(rect(-150, -60, 12, 12), {"building": "yes", "roof:shape": "butterfly",
                                                              "height": "10", "roof:height": "3"}, closed=True)
        cls.ids["court"] = b.multipolygon(rect(0, -60, 30, 30), [rect(0, -60, 10, 10)[::-1]],
                                          {"building": "yes", "roof:shape": "dome", "height": "10",
                                           "roof:height": "3"})
        osm = os.path.join(cls.tmp, "roofs.osm")
        with open(osm, "w", encoding="utf-8") as f:
            f.write(b.xml())
        cls.path = os.path.join(cls.tmp, "roofs.mbmap")
        _, cls.result = build_package(fixture_area(), fixture_settings(osm_file=osm), cls.path, "roofs",
                                      created_utc=UTC)
        members = read_members(cls.path)
        cls.manifest = json.loads(members["manifest.json"])
        cls.report = json.loads(members["report.json"])
        cls.col = read_collision(members["collision/map.mbcol"])
        _, nodes = read_glb(members["visual/map.glb"])
        cls.nodes = {n.name: n for n in nodes}
        cls.entries = {e["name"]: e for e in cls.col.objects}
        cls.objects = {o["name"]: o for o in cls.manifest["objects"]}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def name(self, key):
        return ("bld_relation_" if key == "court" else "bld_way_") + str(self.ids[key])

    def test_package_is_valid(self):
        self.assertTrue(self.result.ok, self.result.summary())
        self.assertEqual(set(self.nodes), set(self.entries))

    def test_each_new_shape_is_bound_closed_and_sloped(self):
        for shape in self.SHAPES:
            name = self.name(shape)
            prov = self.objects[name]["provenance"]
            self.assertEqual(prov["roof_shape_built"], shape)
            self.assertTrue(prov["roof_shape"].startswith("measured:"), prov["roof_shape"])
            col, _ = self.assert_bound(name)
            self.assertGreater(signed_volume(col), 0, shape)
            sloped = [n for n in map(normal, col) if n is not None and 0.2 < n[2] < 0.98]
            self.assertGreaterEqual(len(sloped), 4, shape)

    def test_fallbacks_are_in_object_provenance_and_report(self):
        for key, built in (("butterfly", "flat"), ("court", "flat")):
            prov = self.objects[self.name(key)]["provenance"]
            self.assertEqual(prov["roof_shape_built"], built, key)
            self.assertTrue(prov["roof_shape"].startswith("fallback:"), prov["roof_shape"])
            self.assert_bound(self.name(key))
        self.assertTrue(self.objects[self.name("butterfly")]["provenance"]["roof_shape"].startswith(
            "fallback:flat (roof:shape=butterfly"))
        self.assertEqual(self.report["inferred"]["building.roof_shape"], 2)


class BakeEditsAcceptanceTest(unittest.TestCase):
    """Edits not asserted by test_blender_bake: collision of a uniformly scaled, a negatively scaled
    (mirrored), a moved and a duplicated building equals the independently transformed mesh; the deleted
    building is gone from collision, GLB and manifest; every node still matches its collision."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.area = fixture_area()
        grid, classified, cls.sources = acquire(cls.area, fixture_settings())
        cls.plan = build_plan(cls.area, grid, classified, PlanOptions(seed=1))
        cls.generated = [o.mb_id for o in cls.plan.objects]
        specs = {o.name: o for o in cls.plan.objects}
        cls.moved, cls.scaled, cls.mirrored, cls.deleted, cls.duped = (
            specs[GABLED], specs[HIPPED], specs[L_BUILDING], specs["bld_way_1033"], specs["bld_way_1038"])
        cls.dup_name = cls.duped.name + ".001"
        cls.dup_offset = (0.0, -25.0, 0.0)
        cls.expected = {}
        baked = []
        for spec in cls.plan.objects:
            if spec is cls.deleted:
                continue
            m = cls.matrix(spec)
            if spec is cls.moved:
                m = trs((spec.location[0] + 9.0, spec.location[1] - 4.0, spec.location[2]), spec.rotation_z + 0.35)
            elif spec is cls.scaled:
                m = trs(spec.location, spec.rotation_z, (1.25, 1.25, 1.25))
            elif spec is cls.mirrored:
                m = trs(spec.location, spec.rotation_z, (-1.2, 1.0, 1.1))        # negative scale = mirror
            baked.append(cls.bake(spec, m))
            if spec is cls.duped:
                loc = tuple(a + b for a, b in zip(spec.location, cls.dup_offset))
                baked.append(cls.bake(spec, trs(loc, spec.rotation_z), cls.dup_name))
        cls.path = os.path.join(cls.tmp, "edited.mbmap")
        report = {"warnings": [], "unsupported_features": [], "invalid_features": [],
                  "z_offset_m": cls.area.frame.z_offset}
        cls.manifest, cls.export_result, cls.edits = export_baked(
            cls.path, "edited", cls.area, cls.sources, baked, cls.generated, MATERIALS, report,
            blender_version="4.2.23 LTS", heightfield_spacing=2.0, created_utc=UTC)
        members = read_members(cls.path)
        cls.col = read_collision(members["collision/map.mbcol"])
        _, nodes = read_glb(members["visual/map.glb"])
        cls.nodes = {n.name: n for n in nodes}
        cls.entries = {e["name"]: e for e in cls.col.objects}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def matrix(spec):
        s = spec.scale if isinstance(spec.scale, (tuple, list)) else (spec.scale,) * 3
        return trs(spec.location, spec.rotation_z, s)

    def mesh(self, spec):
        return spec.mesh if spec.mesh is not None else self.plan.shared_meshes[spec.mesh_key]

    @classmethod
    def bake(cls, spec, m, name=None):
        md = spec.mesh if spec.mesh is not None else cls.plan.shared_meshes[spec.mesh_key]
        name = name or spec.name
        local = [tuple(tuple(md.vertices[i]) for i in t) for t in md.triangles()]
        cls.expected[name] = (local, m)
        return bake_object(name, md.vertices, list(md.triangles()), m, mb_id=spec.mb_id, mb_class=spec.mb_class,
                           provenance=spec.provenance)

    def expected_world(self, name):
        """Independent: world = M * local; a mirroring M (det < 0) must reverse the winding."""
        local, m = self.expected[name]
        world = [tuple(apply(m, p) for p in t) for t in local]
        return reverse(world) if det3(m) < 0 else world, world

    def col_tris(self, name):
        return [tuple(tuple(p) for p in t) for t in self.col.object_triangles(self.entries[name])]

    def test_package_validates_with_edit_record(self):
        self.assertTrue(self.export_result.ok, self.export_result.summary())
        r = validate_package(self.path)
        self.assertTrue(r.ok, r.summary())
        self.assertEqual(self.edits["removed"], [self.deleted.mb_id])

    def test_collision_follows_final_transforms(self):
        for spec in (self.moved, self.scaled, self.mirrored):
            want, _ = self.expected_world(spec.name)
            got = self.col_tris(spec.name)
            self.assertEqual(len(got), len(want), spec.name)
            self.assertEqual(unmatched(want, got), ([], []), spec.name)
            self.assertEqual(self.entries[spec.name]["mb_id"], spec.mb_id)
        # the edits really moved things: the moved building is no longer at its generated place
        gen = self.mesh(self.moved)
        at_origin = [tuple(apply(self.matrix(self.moved), tuple(gen.vertices[i])) for i in t)
                     for t in gen.triangles()]
        self.assertNotEqual(len(unmatched(at_origin, self.col_tris(self.moved.name))[0]), 0)

    def test_mirrored_building_keeps_outward_positive_volume(self):
        name = self.mirrored.name
        want, unflipped = self.expected_world(name)
        got = self.col_tris(name)
        # without the winding flip the mirrored solid would be inside-out: nothing would match
        solid = [t for t in unflipped if normal(t) is not None]
        self.assertEqual(len(unmatched(solid, got)[0]), len(solid))
        local, m = self.expected[name]
        self.assertGreater(signed_volume(local), 0)
        self.assertAlmostEqual(signed_volume(got), abs(det3(m)) * signed_volume(local),
                               delta=1e-3 * abs(signed_volume(got)))
        self.assertLess(det3(m), 0)

    def test_duplicate_is_distinct_and_at_its_own_transform(self):
        orig, dup = self.entries[self.duped.name], self.entries[self.dup_name]
        self.assertEqual(orig["mb_id"], self.duped.mb_id)
        self.assertNotEqual(dup["mb_id"], orig["mb_id"])
        self.assertEqual(len({e["mb_id"] for e in self.col.objects}), len(self.col.objects))
        shifted = [tuple(tuple(a + b for a, b in zip(p, self.dup_offset)) for p in t)
                   for t in self.col_tris(self.duped.name)]
        self.assertEqual(unmatched(shifted, self.col_tris(self.dup_name)), ([], []))

    def test_deleted_building_is_absent_everywhere(self):
        name, mb_id = self.deleted.name, self.deleted.mb_id
        self.assertNotIn(name, self.entries)
        self.assertNotIn(mb_id, {e["mb_id"] for e in self.col.objects})
        self.assertNotIn(name, self.nodes)
        self.assertNotIn(name, {o["name"] for o in self.manifest["objects"]})
        # and no collision triangle remains where it stood
        cx, cy = self.deleted.location[0], self.deleted.location[1]
        self.assertEqual(ray_hits(self.col.class_triangles("building"), cx, cy), [])

    def test_every_edited_node_matches_its_collision(self):
        self.assertEqual(set(self.nodes), set(self.entries))
        for name in (self.moved.name, self.scaled.name, self.mirrored.name, self.duped.name, self.dup_name):
            vis = [tuple(gltf_to_enu(p) for p in t) for t in self.nodes[name].triangles]
            self.assertEqual(unmatched(self.col_tris(name), vis), ([], []), name)


# --- 4: determinism and immutability ------------------------------------------------------------

class DeterminismTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.paths = []
        for k in range(2):     # two fully independent acquisitions + builds from the same inputs
            path = os.path.join(cls.tmp, f"build{k}.mbmap")
            manifest, result = build_package(fixture_area(), fixture_settings(), path, "det", created_utc=UTC)
            assert result.ok, result.summary()
            cls.paths.append(path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_independent_builds_have_identical_identity_and_bytes(self):
        r0, r1 = validate_package(self.paths[0]), validate_package(self.paths[1])
        self.assertTrue(r0.ok and r1.ok)
        self.assertEqual(r0.package_id, r1.package_id)
        m0, m1 = read_members(self.paths[0]), read_members(self.paths[1])
        self.assertEqual(m0, m1)
        with open(self.paths[0], "rb") as a, open(self.paths[1], "rb") as b:
            self.assertEqual(a.read(), b.read())
        # package_id is sha256 of the raw manifest bytes
        raw = m0["manifest.json"]
        self.assertEqual(r0.package_id, "sha256:" + hashlib.sha256(raw).hexdigest())
        self.assertEqual(manifest_bytes(json.loads(raw)), raw)

    def test_single_byte_change_in_any_member_fails_with_hash_error(self):
        members = read_members(self.paths[0])
        hashed = [f["path"] for f in json.loads(members["manifest.json"])["files"]]
        self.assertEqual(set(hashed), set(members) - {"manifest.json"})
        self.assertEqual(len(hashed), 5)
        for path in hashed:
            data = members[path]
            for pos in (0, len(data) // 2, len(data) - 1):
                if pos != len(data) // 2 and path != "visual/map.glb":
                    continue         # middle byte of each member, plus both ends of the GLB
                bad = bytearray(data)
                bad[pos] ^= 0x01
                out = os.path.join(self.tmp, "tampered.mbmap")
                with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:    # no rehash
                    for name in sorted(members):
                        z.writestr(name, bytes(bad) if name == path else members[name])
                r = validate_package(out)
                self.assertFalse(r.ok, f"{path}@{pos}")
                self.assertTrue(any(f"({path}): SHA-256 mismatch" in e for e in r.errors), (path, pos, r.errors))


# --- 5: resource bounds before network access --------------------------------------------------

class NoNetworkClient:
    max_bytes = 1 << 30
    bytes_downloaded = 0

    def __init__(self):
        self.calls = []

    def fetch(self, url, *a, **kw):
        self.calls.append(url)
        raise AssertionError("network accessed for an over-limit request")


class ResourceBoundsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def online(self, area, **kw):
        client = NoNetworkClient()
        out = os.path.join(self.tmp, "never.mbmap")
        with self.assertRaises(LimitError):
            build_package(area, Settings(**kw), out, "too_big", client=client)   # copernicus + overpass
        self.assertEqual(client.calls, [])
        self.assertFalse(os.path.exists(out))

    def test_area_beyond_documented_maximum_is_rejected(self):
        for w, h in ((2001.0, 500.0), (500.0, 2500.0), (6000.0, 6000.0)):
            with self.assertRaises(AreaError):
                Area(47.0, 8.0, w, h)
        with self.assertRaises(AreaError):
            Area(47.0, 8.0, 5001.0, 100.0, max_side_m=10000.0)     # hard cap
        with self.assertRaises(AreaError):
            Area.from_bbox(47.0, 8.0, 47.03, 8.01)                  # ~3.3 km north-south

    def test_oversize_terrain_grid_rejected_before_network(self):
        big = Area(47.0, 8.0, 2000.0, 2000.0)          # allowed area, but 1001 x 1001 grid points at 2 m
        self.online(big, terrain_spacing=2.0)
        self.online(big, terrain_spacing=0.5)          # finer than the 1 m minimum
        client = NoNetworkClient()
        with self.assertRaises(LimitError):
            fetch_copernicus(big, client, spacing=2.0)
        self.assertEqual(client.calls, [])

    def test_oversize_heightfield_rejected_before_network(self):
        self.online(Area(47.0, 8.0, 2000.0, 2000.0), heightfield_spacing=0.25)    # 8001 x 8001 points

    def test_heightfield_below_two_by_two_rejected_before_network(self):
        thin = Area(47.0, 8.0, 400.0, 50.0)            # heightfield_spacing 60 m -> 7 x 1 points
        with self.assertRaises(LimitError):
            heightfield_layout(thin.half, 60.0)
        self.assertEqual(heightfield_layout(thin.half, 50.0)[2:], (9, 2))
        self.online(thin, heightfield_spacing=60.0)
        with self.local_loaders() as calls:
            with self.assertRaises(LimitError):
                build_package(thin, fixture_settings(heightfield_spacing=60.0), self.out(), "thin")
        self.assertEqual(calls, [])

    # local sources: the same bounds hold before any file is opened

    @contextlib.contextmanager
    def local_loaders(self):
        calls = []

        def refuse(name):
            def loader(*a, **kw):
                calls.append(name)
                raise AssertionError(f"{name} called for an over-limit request")
            return loader
        with mock.patch.object(pipeline, "load_local_elevation", refuse("load_local_elevation")), \
                mock.patch.object(pipeline, "load_osm_file", refuse("load_osm_file")):
            yield calls

    def out(self):
        return os.path.join(self.tmp, "never.mbmap")

    def test_oversize_terrain_grid_from_local_file_rejected_before_loading(self):
        big = Area(47.0, 8.0, 2000.0, 2000.0)          # 1001 x 1001 terrain points at 2 m
        for call in (lambda s: acquire(big, s), lambda s: generate_plan(big, s),
                     lambda s: build_package(big, s, self.out(), "too_big")):
            with self.local_loaders() as calls:
                with self.assertRaises(LimitError):
                    call(fixture_settings(terrain_spacing=2.0, heightfield_spacing=None))
            self.assertEqual(calls, [])
        self.assertFalse(os.path.exists(self.out()))

    def test_oversize_heightfield_from_local_file_rejected_before_loading(self):
        big = Area(47.0, 8.0, 2000.0, 2000.0)          # terrain 201 x 201 is fine; heightfield 8001 x 8001
        with self.local_loaders() as calls:
            with self.assertRaises(LimitError):
                build_package(big, fixture_settings(terrain_spacing=10.0, heightfield_spacing=0.25), self.out(),
                              "too_big")
        self.assertEqual(calls, [])
        self.assertFalse(os.path.exists(self.out()))

    def test_direct_local_loader_checks_grid_before_opening(self):
        big = Area(47.0, 8.0, 2000.0, 2000.0)          # 1001 x 1001 terrain points at 2 m
        fail = AssertionError("file reader called for an over-limit request")
        with mock.patch.object(dem_mod, "load_ascii_grid", side_effect=fail), \
                mock.patch.object(dem_mod, "load_local_geotiff", side_effect=fail):
            for path in ("x.asc", "x.tif"):
                with self.assertRaises(LimitError):
                    dem_mod.load_local_elevation(big, path, spacing=2.0)

    def test_absurdly_fine_heightfield_spacing_is_a_limit_error(self):
        big = Area(47.0, 8.0, 400.0, 300.0)
        for spacing in (1e-310, 5e-324):               # 2*h/spacing overflows to inf
            with self.assertRaises(LimitError):
                heightfield_layout(big.half, spacing)
            with self.local_loaders() as calls:
                with self.assertRaises(LimitError):
                    build_package(big, fixture_settings(heightfield_spacing=spacing), self.out(), "too_fine")
            self.assertEqual(calls, [])


class HeightfieldPreflightScopeTest(unittest.TestCase):
    """The heightfield bound belongs to package export: plan generation produces no heightfield."""

    def test_generate_plan_ignores_heightfield_spacing(self):
        settings = fixture_settings(heightfield_spacing=0.005)        # 80001 x 60001 points if exported
        plan, sources = generate_plan(fixture_area(), settings)
        self.assertGreater(len(plan.objects), 0)
        self.assertEqual(len(sources), 2)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "never.mbmap")
            with mock.patch.object(pipeline, "load_local_elevation",
                                   side_effect=AssertionError("loaded before the heightfield check")):
                with self.assertRaises(LimitError):
                    build_package(fixture_area(), settings, out, "too_fine")
            self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
