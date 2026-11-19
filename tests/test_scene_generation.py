import math
import tempfile
import unittest
from collections import Counter

from map_builder.core.errors import MapBuilderError
from map_builder.core.generate import PlanOptions, build_plan, parse_colour, parse_length
from map_builder.core.osm import parse_osm_xml, ring_area
from map_builder.core.triangulate import triangulate

from .synthetic import synthetic_inputs


def tri_area(a, b, c):
    return ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0


def signed_volume(mesh):
    v = mesh.vertices
    vol = 0.0
    for a, b, c in mesh.triangles():
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = v[a], v[b], v[c]
        vol += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return vol / 6.0


def assert_closed_consistent(test, mesh):
    edges = Counter()
    for f in mesh.faces:
        for k in range(len(f)):
            edges[(f[k], f[(k + 1) % len(f)])] += 1
    for (u, v), n in edges.items():
        test.assertEqual(n, 1, f"{mesh.name}: directed edge {u}->{v} used {n} times")
        test.assertEqual(edges.get((v, u)), 1, f"{mesh.name}: edge {u}->{v} has no opposite (open/flipped)")


class OsmTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.area, cls.grid, cls.cl, cls.ids, cls.sources = synthetic_inputs(tempfile.mkdtemp())

    def test_rejects_entity_expansion(self):
        evil = b'<?xml version="1.0"?><!DOCTYPE osm [<!ENTITY a "aaaa">]><osm>&a;</osm>'
        with self.assertRaises(MapBuilderError):
            parse_osm_xml(evil)

    def test_unsupported_features_reported_not_flattened(self):
        unsup = {u["id"]: u["reason"] for u in self.cl.unsupported}
        self.assertIn("bridge", unsup[f"osm:way/{self.ids['bridge']}"])
        self.assertIn("tunnel", unsup[f"osm:way/{self.ids['tunnel']}"])
        road_ids = {r.id for r in self.cl.roads}
        self.assertNotIn(f"osm:way/{self.ids['bridge']}", road_ids)
        self.assertNotIn(f"osm:way/{self.ids['tunnel']}", road_ids)

    def test_invalid_and_outside(self):
        invalid = {i["id"] for i in self.cl.invalid}
        self.assertIn(f"osm:way/{self.ids['bowtie']}", invalid)
        self.assertEqual(self.cl.outside, 1)

    def test_courtyard_multipolygon(self):
        b = next(f for f in self.cl.buildings if f.id == f"osm:relation/{self.ids['court']}")
        self.assertEqual(len(b.geometry.holes), 1)
        self.assertAlmostEqual(ring_area(b.geometry.outer), 1600, delta=1)
        self.assertAlmostEqual(ring_area(b.geometry.holes[0]), -256, delta=1)  # CW hole
        self.assertFalse(b.geometry.contains(-100, -60))
        self.assertTrue(b.geometry.contains(-100, -75))

    def test_landcover_classes(self):
        self.assertEqual(sorted(a.tags["_class"] for a in self.cl.areas), ["forest", "grass", "water"])

    def test_tag_parsing(self):
        self.assertAlmostEqual(parse_length("10 ft"), 3.048)
        self.assertAlmostEqual(parse_length("12'6\""), 3.81)
        self.assertEqual(parse_length("12 m"), 12.0)
        self.assertIsNone(parse_length("tall"))
        self.assertIsNotNone(parse_colour("#ff8800"))
        self.assertIsNone(parse_colour("ultraviolet"))


class TriangulateTest(unittest.TestCase):
    def test_polygon_with_two_holes_conserves_area(self):
        outer = [(0, 0), (30, 0), (30, 10), (20, 10), (20, 20), (0, 20)]
        h1 = [(2, 2), (2, 6), (6, 6), (6, 2)]
        h2 = [(10, 12), (10, 16), (14, 16), (14, 12)]
        pts = outer + h1 + h2
        tris = triangulate(pts, list(range(6)), [list(range(6, 10)), list(range(10, 14))])
        areas = [tri_area(pts[a], pts[b], pts[c]) for a, b, c in tris]
        self.assertTrue(all(a > 0 for a in areas))
        self.assertAlmostEqual(sum(areas), 30 * 10 + 20 * 10 - 16 - 16, places=6)


class PlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.area, cls.grid, cls.cl, cls.ids, cls.sources = synthetic_inputs(tempfile.mkdtemp())
        cls.plan = build_plan(cls.area, cls.grid, cls.cl, PlanOptions(seed=3))
        cls.by_id = {o.mb_id: o for o in cls.plan.objects}

    def obj(self, key, kind="way"):
        return self.by_id[f"osm:{kind}/{self.ids[key]}"]

    def test_buildings_closed_and_outward(self):
        n = 0
        for o in self.plan.objects:
            if o.mb_class != "building":
                continue
            n += 1
            assert_closed_consistent(self, o.mesh)
            self.assertGreater(signed_volume(o.mesh), 0, o.name)
        self.assertEqual(n, 8)

    def test_measured_height_and_sunk_foundation(self):
        o = self.obj("L")
        zs = [v[2] for v in o.mesh.vertices]
        self.assertAlmostEqual(max(zs), 12.0)
        self.assertAlmostEqual(min(zs), -0.3)
        self.assertEqual(o.provenance["height"], "measured:osm height")
        self.assertIn("ground_slope_m", o.provenance)  # synthetic terrain is tilted
        ground = min(self.grid.sample(x, y) for x, y in [(50, 20), (90, 20), (90, 35), (65, 35), (65, 80), (50, 80)])
        self.assertAlmostEqual(o.location[2], ground - self.plan.frame.z_offset, places=4)

    def test_courtyard_roof_keeps_hole(self):
        o = self.obj("court", "relation")
        m = o.mesh
        roof = m.materials.index("MB Roof")
        area = 0.0
        for f, mi in zip(m.faces, m.face_materials):
            if mi == roof:
                area += tri_area(*(m.vertices[i] for i in f))
        self.assertAlmostEqual(area, 1600 - 256, delta=0.5)
        self.assertAlmostEqual(max(v[2] for v in m.vertices), 12.0)  # 4 levels x 3 m (inferred)
        self.assertTrue(o.provenance["height"].startswith("inferred"))

    def test_roof_shapes_and_fallbacks(self):
        self.assertEqual(self.obj("gabled").provenance["roof_shape_built"], "gabled")
        self.assertAlmostEqual(max(v[2] for v in self.obj("gabled").mesh.vertices), 8.0)
        self.assertEqual(self.obj("hipped").provenance["roof_shape_built"], "hipped")
        self.assertEqual(self.obj("pyramid").provenance["roof_shape_built"], "pyramidal")
        self.assertEqual(self.obj("skillion").provenance["roof_shape_built"], "skillion")
        dome = self.obj("dome").provenance
        self.assertEqual(dome["roof_shape_built"], "flat")
        self.assertTrue(dome["roof_shape"].startswith("fallback"))

    def test_elevated_volume_is_flagged(self):
        o = self.obj("elevated")
        self.assertAlmostEqual(min(v[2] for v in o.mesh.vertices), 6.0)
        self.assertIn("NOT modelled", o.provenance["elevated"])
        reasons = [u["reason"] for u in self.plan.report["unsupported_features"] if u["id"] == o.mb_id]
        self.assertTrue(reasons and "elevated" in reasons[0])

    def test_roads_drape_on_terrain(self):
        z0 = self.plan.frame.z_offset
        roads = [o for o in self.plan.objects if o.mb_class == "road"]
        self.assertEqual(len(roads), 2)
        for o in roads:
            for x, y, z in o.mesh.vertices:
                wx, wy, wz = x + o.location[0], y + o.location[1], z + o.location[2]
                above = wz - (self.grid.sample(wx, wy) - z0)
                self.assertGreaterEqual(above, 0.12 - 1e-6)  # never buried
                self.assertLess(above, 1.0)  # outer edge lifted to centreline on cross-slope
                hx, hy = self.area.half
                self.assertLessEqual(abs(wx), hx + 10)
                self.assertLessEqual(abs(wy), hy + 10)

    def test_trees_avoid_buildings(self):
        polys = [f.geometry for f in self.cl.buildings]
        trees = [o for o in self.plan.objects if o.mb_class == "vegetation"]
        self.assertGreater(len(trees), 3)
        for t in trees:
            self.assertFalse(any(p.contains(t.location[0], t.location[1]) for p in polys), t.name)
        osm_tree = self.by_id[f"osm:node/{self.ids['tree0']}"]
        self.assertAlmostEqual(osm_tree.scale, 11 / 8)
        scattered = [t for t in trees if t.mb_id.startswith("scatter:")]
        self.assertTrue(scattered and all(t.provenance.get("position", "").startswith("inferred")
                                          for t in scattered))

    def test_deterministic_and_unique_names(self):
        again = build_plan(self.area, self.grid, self.cl, PlanOptions(seed=3))
        self.assertEqual([o.name for o in again.objects], [o.name for o in self.plan.objects])
        self.assertEqual([o.location for o in again.objects], [o.location for o in self.plan.objects])
        names = [o.name for o in self.plan.objects]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(len(n) <= 63 for n in names))

    def test_object_cap(self):
        with self.assertRaises(MapBuilderError):
            build_plan(self.area, self.grid, self.cl, PlanOptions(max_objects=5))


if __name__ == "__main__":
    unittest.main()
