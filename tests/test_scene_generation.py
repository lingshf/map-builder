import math
import random
import tempfile
import unittest
from collections import Counter
from unittest import mock

from map_builder.core.dem import ElevationGrid
from map_builder.core.errors import LimitError, MapBuilderError
from map_builder.core.generate import (MAX_RING_VERTICES, ROAD_LIFT_M, InvalidFeature, PlanOptions, build_building,
                                       build_plan, build_road, build_terrain, footprint_terrain_range, parse_colour,
                                       parse_length, terrain_height)
from map_builder.core.geodesy import Area
from map_builder.core.osm import Classified, Feature, Polygon, parse_osm_xml, ring_area
from map_builder.core.triangulate import TriangulationError, triangulate, verify_triangulation

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
        self.assertIn("base_datum", o.provenance)
        ring = [(50, 20), (90, 20), (90, 35), (65, 35), (65, 80), (50, 80)]
        poly = Polygon(ring)
        dense = [terrain_height(self.grid, x, y) for x, y in ring]
        dense += [terrain_height(self.grid, 50 + i * 0.5, 20 + j * 0.5) for i in range(81) for j in range(121)
                  if poly.contains(50 + i * 0.5, 20 + j * 0.5)]
        base = o.location[2] + self.plan.frame.z_offset
        self.assertLessEqual(base, min(dense) + 1e-6)  # never floating above the terrain inside the footprint
        self.assertGreater(base, min(dense) - 0.05)

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
                above = wz - (terrain_height(self.grid, wx, wy) - z0)
                self.assertGreaterEqual(above, 0.12 - 1e-6)  # never buried
                self.assertLess(above, 0.12 + 1e-6)  # draped exactly on the terrain mesh
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


# --- Regression tests for review findings --------------------------------------

def make_grid(heights, spacing=10.0, x0=0.0, y0=0.0):
    """heights[j][i] -> ElevationGrid with node (i, j) at (x0 + i*s, y0 + j*s)."""
    return ElevationGrid(x0, y0, spacing, len(heights[0]), len(heights), [list(r) for r in heights],
                         {"provider": "test"})


def flat_grid(n=11, spacing=10.0, x0=-50.0, y0=-50.0, h=0.0):
    return make_grid([[h] * n for _ in range(n)], spacing, x0, y0)


def rect_ccw(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def rect_cw(x0, y0, x1, y1):
    return [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]


def building(outer, holes=(), fid="osm:way/1", **tags):
    t = {"building": "yes"}
    t.update({k.replace("__", ":"): v for k, v in tags.items()})
    return Feature(fid, "building", t, Polygon(list(outer), [list(h) for h in holes]))


def road(points, fid="osm:way/2", **tags):
    t = {"highway": "residential"}
    t.update(tags)
    return Feature(fid, "road", t, list(points))


def tri_normal_z(mesh, tri):
    (ax, ay, _), (bx, by, _), (cx, cy, _) = (mesh.vertices[i] for i in tri)
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def assert_closed_manifold(test, mesh):
    """Closed, consistently oriented, outward (positive volume) solid."""
    edges = Counter()
    for a, b, c in mesh.triangles():
        for u, v in ((a, b), (b, c), (c, a)):
            edges[(u, v)] += 1
    unmatched = [e for e, n in edges.items() if n != 1 or edges.get((e[1], e[0])) != 1]
    test.assertEqual(unmatched, [], f"{mesh.name}: {len(unmatched)} unmatched directed edges")
    test.assertGreater(signed_volume(mesh), 0, mesh.name)


def roof_area(mesh):
    roof = mesh.materials.index("MB Roof")
    return sum(tri_area(*(mesh.vertices[i] for i in f)) for f, mi in zip(mesh.faces, mesh.face_materials)
               if mi == roof)


def tiny_area():
    return Area(47.0, 8.0, 100.0, 100.0)


class BridgeAndClosureTest(unittest.TestCase):
    """Finding 1: bridges along hole edges / through vertices; verified caps; closed solids."""

    OUTER = rect_ccw(0, 0, 20, 20)
    REVIEWER_CASES = [
        [rect_cw(5, 13, 6, 16), rect_cw(2, 3, 6, 6)],   # used to raise TriangulationError
        [rect_cw(12, 7, 13, 9), rect_cw(8, 1, 12, 6)],  # used to leave 6 unmatched directed edges
    ]

    def check(self, outer, holes):
        pts = list(outer) + [p for h in holes for p in h]
        o, idx = list(range(len(outer))), len(outer)
        hidx = []
        for h in holes:
            hidx.append(list(range(idx, idx + len(h))))
            idx += len(h)
        tris = triangulate(pts, o, hidx)
        verify_triangulation(tris, pts, o, hidx)
        areas = [tri_area(pts[a], pts[b], pts[c]) for a, b, c in tris]
        self.assertTrue(all(a > 0 for a in areas))
        expected = ring_area(outer) + sum(ring_area(h) for h in holes)
        self.assertAlmostEqual(sum(areas), expected, places=6)
        mesh, _, _ = build_building(building(outer, holes, height="9"), flat_grid(), 0.0)
        assert_closed_manifold(self, mesh)
        self.assertAlmostEqual(roof_area(mesh), expected, places=6)

    def test_reviewer_hole_configurations(self):
        for holes in self.REVIEWER_CASES:
            with self.subTest(holes=holes):
                self.check(self.OUTER, holes)

    def test_more_hole_configurations(self):
        cases = [
            [rect_cw(2, 2, 4, 4), rect_cw(2, 6, 4, 8), rect_cw(2, 10, 4, 12)],  # vertically aligned
            [rect_cw(2, 2, 4, 4), rect_cw(6, 2, 8, 4), rect_cw(10, 2, 12, 4)],  # horizontally aligned
            [rect_cw(4, 4, 16, 16)],                                           # big courtyard
            [[(10, 3), (8, 6), (12, 6)], rect_cw(9, 8, 11, 10)],         # triangle above a square
        ]
        for holes in cases:
            with self.subTest(holes=holes):
                self.check(self.OUTER, holes)
        # concave outer (L) with holes aligned to its reflex vertex
        self.check([(0, 0), (20, 0), (20, 8), (8, 8), (8, 20), (0, 20)],
                   [rect_cw(2, 2, 4, 8 - 2), rect_cw(10, 2, 12, 4), rect_cw(2, 10, 4, 12)])

    def test_randomized_disjoint_rect_holes(self):
        rng = random.Random(1234)
        for trial in range(40):
            holes, boxes = [], []
            for _ in range(rng.randint(1, 8)):
                for _attempt in range(20):
                    x0, y0 = rng.randint(1, 16), rng.randint(1, 16)
                    x1, y1 = x0 + rng.randint(1, 3), y0 + rng.randint(1, 3)
                    if x1 > 19 or y1 > 19:
                        continue
                    if any(x0 <= bx1 and bx0 <= x1 and y0 <= by1 and by0 <= y1 for bx0, by0, bx1, by1 in boxes):
                        continue  # touching or overlapping: holes must stay disjoint
                    boxes.append((x0, y0, x1, y1))
                    holes.append(rect_cw(x0, y0, x1, y1))
                    break
            with self.subTest(trial=trial, holes=boxes):
                self.check(self.OUTER, holes)

    def test_verification_rejects_incomplete_or_overlapping_caps(self):
        pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
        with self.assertRaises(TriangulationError):
            verify_triangulation([(0, 1, 2)], pts, [0, 1, 2, 3])  # misses two ring edges
        with self.assertRaises(TriangulationError):
            verify_triangulation([(0, 1, 2), (0, 2, 3), (0, 1, 3)], pts, [0, 1, 2, 3])  # overlap


class RingValidationTest(unittest.TestCase):
    """Finding 2: invalid ring topology is rejected, never triangulated into overlapping caps."""

    OUTER = rect_ccw(0, 0, 10, 10)

    def tri(self, outer, holes):
        pts = list(outer) + [p for h in holes for p in h]
        idx, hidx = len(outer), []
        for h in holes:
            hidx.append(list(range(idx, idx + len(h))))
            idx += len(h)
        return triangulate(pts, list(range(len(outer))), hidx)

    def test_invalid_rings_raise(self):
        cases = {
            "touching outer": [[(0, 0), (2, 3), (3, 2)]],   # reviewer: area 112.5 instead of 97.5
            "empty hole": [[]],
            "two-point hole": [[(2, 2), (3, 3)]],
            "overlapping holes": [rect_cw(2, 2, 5, 5), rect_cw(4, 4, 7, 7)],
            "touching holes": [rect_cw(2, 2, 4, 4), rect_cw(4, 2, 6, 4)],
            "nested holes": [rect_cw(2, 2, 8, 8), rect_cw(4, 4, 5, 5)],
            "hole outside": [rect_cw(12, 2, 14, 4)],
            "hole crossing outer": [rect_cw(8, 2, 12, 4)],
            "self-intersecting hole": [[(2, 2), (4, 4), (4, 2), (2, 4)]],
        }
        for name, holes in cases.items():
            with self.subTest(name):
                with self.assertRaises(TriangulationError):
                    self.tri(self.OUTER, holes)
        with self.assertRaises(TriangulationError):
            self.tri([(0, 0), (10, 10), (10, 0), (0, 10)], [])  # bowtie outer
        with self.assertRaises(TriangulationError):
            self.tri([(0, 0), (10, 0), (0, 0)], [])  # < 3 distinct points

    def test_plan_reports_invalid_building_without_caps(self):
        cl = Classified()
        bad = building(rect_ccw(-20, -20, 0, 0), [[(-20, -20), (-17, -18), (-18, -17)][::-1]], fid="osm:way/77",
                       height="10")
        good = building(rect_ccw(5, 5, 20, 20), fid="osm:way/78", height="10")
        cl.buildings = [bad, good]
        plan = build_plan(tiny_area(), flat_grid(), cl)
        ids = {o.mb_id for o in plan.objects}
        self.assertNotIn("osm:way/77", ids)
        self.assertIn("osm:way/78", ids)
        entry = [e for e in plan.report["invalid_features"] if e["id"] == "osm:way/77"]
        self.assertEqual(len(entry), 1)
        self.assertIn("touches", entry[0]["reason"])


class TerrainSurfaceTest(unittest.TestCase):
    """Findings 3 and 4: one exact piecewise-planar terrain surface used everywhere."""

    def test_terrain_height_matches_terrain_mesh(self):
        rng = random.Random(5)
        grid = make_grid([[rng.uniform(0, 30) for _ in range(6)] for _ in range(5)], spacing=7.0, x0=-3, y0=4)
        mesh = build_terrain(grid, 0.0, [])
        V = mesh.vertices
        for tri in mesh.triangles():
            for w in ((1 / 3, 1 / 3, 1 / 3), (0.6, 0.3, 0.1), (0.1, 0.1, 0.8)):
                p = [sum(w[k] * V[tri[k]][d] for k in range(3)) for d in range(3)]
                self.assertAlmostEqual(terrain_height(grid, p[0], p[1]), p[2], places=9)

    def test_base_datum_includes_diagonal_crossings(self):
        # one 10 m cell: diagonal corners at 80, the others at 100; the footprint's
        # vertices are all >= 84 but its edges cross the diagonal valley at 80.
        grid = make_grid([[80, 100], [100, 80]], spacing=10.0)
        ring = rect_ccw(2, 4, 8, 6)
        self.assertEqual(min(terrain_height(grid, x, y) for x, y in ring), 84)
        self.assertEqual(footprint_terrain_range(grid, [ring]), (80, 88))
        mesh, origin, prov = build_building(building(ring, height="10"), grid, 0.0)
        self.assertAlmostEqual(origin[2], 80.0)
        self.assertAlmostEqual(min(v[2] for v in mesh.vertices) + origin[2], 80.0 - 0.3)
        self.assertIn("base_datum", prov)

    def test_base_datum_includes_interior_dip(self):
        heights = [[50.0] * 11 for _ in range(11)]
        heights[5][5] = 40.0  # node at (0, 0), strictly inside the footprint
        grid = make_grid(heights, x0=-50, y0=-50)
        mesh, origin, prov = build_building(building(rect_ccw(-20, -20, 20, 20), height="10"), grid, 0.0)
        self.assertAlmostEqual(origin[2], 40.0)  # not 50 (vertex-only sampling floated it)
        self.assertEqual(prov["ground_slope_m"], 10.0)
        # a courtyard over the dip excludes it
        mesh, origin, _ = build_building(building(rect_ccw(-20, -20, 20, 20), [rect_cw(-10, -10, 10, 10)],
                                                  height="10"), grid, 0.0)
        self.assertAlmostEqual(origin[2], 50.0)

    def test_terrain_peak_reaching_eave_is_reported(self):
        heights = [[0.0] * 11 for _ in range(11)]
        heights[5][5] = 30.0
        grid = make_grid(heights, x0=-50, y0=-50)
        cl = Classified()
        cl.buildings = [building(rect_ccw(-20, -20, 20, 20), fid="osm:way/90", height="10")]
        plan = build_plan(tiny_area(), grid, cl)
        o = next(o for o in plan.objects if o.mb_id == "osm:way/90")
        self.assertIn("terrain_warning", o.provenance)
        self.assertTrue(any(w.startswith("osm:way/90:") for w in plan.report["warnings"]))
        # a gentle bump below the eave is not reported
        heights[5][5] = 3.0
        plan = build_plan(tiny_area(), make_grid(heights, x0=-50, y0=-50), cl)
        self.assertFalse(any("osm:way/90" in w for w in plan.report["warnings"]))

    def test_road_crossing_cell_diagonal_is_not_buried(self):
        # reviewer: 4 m cell, diagonal corners at 10 m, others at 0 (bilinear gives 5 at the centre)
        grid = make_grid([[10, 0], [0, 10]], spacing=4.0)
        mesh, loc, prov = build_road(road([(0.0, 2.0), (4.0, 2.0)], width="1"), grid, 0.0)
        self.assertIsNotNone(mesh, prov)
        V = [(x + loc[0], y + loc[1], z + loc[2]) for x, y, z in mesh.vertices]
        for p in V:
            self.assertAlmostEqual(p[2] - terrain_height(grid, p[0], p[1]), ROAD_LIFT_M, places=9)
        for tri in mesh.triangles():
            pts = [V[i] for i in tri]
            samples = [pts[0], pts[1], pts[2], tuple(sum(c) / 3 for c in zip(*pts))]
            samples += [tuple((a + b) / 2 for a, b in zip(pts[k], pts[(k + 1) % 3])) for k in range(3)]
            for x, y, z in samples:
                self.assertGreaterEqual(z - terrain_height(grid, x, y), ROAD_LIFT_M - 1e-9)
        self.assertAlmostEqual(terrain_height(grid, 2.0, 2.0), 10.0)
        self.assertTrue(any(abs(p[0] - p[1]) < 1e-9 and 0 < p[0] < 4 for p in V))  # split on the diagonal


class RoadRibbonTest(unittest.TestCase):
    """Finding 5 and 8: no folded road faces; collapsed/unbuildable roads are reported."""

    def test_wide_right_angle_turn_is_not_folded(self):
        mesh, _, prov = build_road(road([(0, 0), (3, 0), (3, 3)], width="8"), flat_grid(), 0.0)
        self.assertIsNotNone(mesh, prov)
        self.assertTrue(all(tri_normal_z(mesh, t) > 0 for t in mesh.triangles()))
        self.assertEqual(prov["joins"], "bevel")

    def test_random_polylines_face_up(self):
        rng = random.Random(99)
        heights = [[rng.uniform(0, 15) for _ in range(11)] for _ in range(11)]
        grid = make_grid(heights, x0=-50, y0=-50)
        built = 0
        for k in range(150):
            pts = [(rng.uniform(-40, 40), rng.uniform(-40, 40))]
            for _ in range(rng.randint(1, 6)):
                step = rng.choice([0.5, 2.0, 5.0, 15.0])
                ang = rng.uniform(0, 2 * math.pi)
                pts.append((pts[-1][0] + step * math.cos(ang), pts[-1][1] + step * math.sin(ang)))
            mesh, loc, prov = build_road(road(pts, fid=f"osm:way/{k}", width=str(rng.uniform(1, 14))), grid, 0.0)
            if mesh is None:
                self.assertIn("reason", prov)
                continue
            built += 1
            for t in mesh.triangles():
                self.assertGreater(tri_normal_z(mesh, t), 0, (k, pts))
        self.assertGreater(built, 140)

    def test_collapsed_and_outside_roads_are_reported(self):
        cl = Classified()
        cl.roads = [road([(1, 1), (1, 1.0001)], fid="osm:way/31"),
                    road([(500, 500), (520, 500)], fid="osm:way/32"),
                    road([(-30, 0), (30, 0)], fid="osm:way/33")]
        plan = build_plan(tiny_area(), flat_grid(), cl)
        reasons = {e["id"]: e["reason"] for e in plan.report["invalid_features"]}
        self.assertIn("fewer than 2", reasons["osm:way/31"])
        self.assertIn("outside", reasons["osm:way/32"])
        self.assertNotIn("osm:way/33", reasons)
        self.assertEqual([o.mb_id for o in plan.objects if o.mb_class == "road"], ["osm:way/33"])

    def test_landcover_without_terrain_cells_is_reported(self):
        cl = Classified()
        cl.areas = [Feature("osm:way/41", "area", {"_class": "grass", "landuse": "grass"},
                            Polygon(rect_ccw(1, 1, 2, 2)))]
        plan = build_plan(tiny_area(), flat_grid(), cl)
        self.assertIn("osm:way/41", [u["id"] for u in plan.report["unsupported_features"]])


class BudgetTest(unittest.TestCase):
    """Finding 6: cumulative and per-feature limits, checked before allocation."""

    @classmethod
    def setUpClass(cls):
        cls.area, cls.grid, cls.cl, cls.ids, cls.sources = synthetic_inputs(tempfile.mkdtemp())

    def test_terrain_over_budget(self):
        with self.assertRaises(LimitError) as cm:
            build_plan(self.area, self.grid, self.cl, PlanOptions(max_vertices=10))
        self.assertIn("terrain:grid", str(cm.exception))

    def test_building_over_budget_names_feature(self):
        n = self.grid.nx * self.grid.ny
        with self.assertRaises(LimitError) as cm:
            build_plan(self.area, self.grid, self.cl, PlanOptions(max_vertices=n + 5))
        self.assertIn(self.cl.buildings[0].id, str(cm.exception))

    def test_road_over_budget_names_feature(self):
        base = build_plan(self.area, self.grid, self.cl, PlanOptions(buildings=False, roads=False, trees=False))
        with self.assertRaises(LimitError) as cm:
            build_plan(self.area, self.grid, self.cl, PlanOptions(
                buildings=False, trees=False, max_triangles=base.report["budget"]["triangles"] + 1))
        self.assertIn(self.cl.roads[0].id, str(cm.exception))

    def test_trees_over_budget_names_feature(self):
        base = build_plan(self.area, self.grid, self.cl, PlanOptions(buildings=False, roads=False, trees=False))
        with self.assertRaises(LimitError) as cm:
            build_plan(self.area, self.grid, self.cl, PlanOptions(
                buildings=False, roads=False, max_vertices=base.report["budget"]["vertices"] + 1))
        self.assertIn(self.cl.trees[0].id, str(cm.exception))

    def test_reserve_happens_before_allocation(self):
        def refuse(v, t):
            raise LimitError(f"refused {v} vertices")

        with mock.patch("map_builder.core.generate.MeshData", side_effect=AssertionError("allocated")):
            with self.assertRaises(LimitError):
                build_building(building(rect_ccw(0, 0, 10, 10), height="5"), flat_grid(), 0.0, reserve=refuse)
            with self.assertRaises(LimitError):
                build_road(road([(0, 0), (30, 0)]), flat_grid(), 0.0, reserve=refuse)

    def test_ring_vertex_limit(self):
        def ngon(n, r=20.0):
            return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]

        self.assertEqual(MAX_RING_VERTICES, 2000)
        with self.assertRaises(InvalidFeature):
            build_building(building(ngon(MAX_RING_VERTICES + 1), height="5"), flat_grid(), 0.0)
        cl = Classified()
        cl.buildings = [building(ngon(60), fid="osm:way/51", height="5"),
                        building(ngon(40), fid="osm:way/52", height="5")]
        plan = build_plan(tiny_area(), flat_grid(), cl, PlanOptions(max_ring_vertices=50))
        reasons = {e["id"]: e["reason"] for e in plan.report["invalid_features"]}
        self.assertIn("limit", reasons["osm:way/51"])
        self.assertIn("osm:way/52", {o.mb_id for o in plan.objects})

    def test_triangulation_work_budget(self):
        n = 300
        ring = [(math.cos(2 * math.pi * k / n) * (10 + (k % 2)), math.sin(2 * math.pi * k / n) * (10 + (k % 2)))
                for k in range(n)]
        with self.assertRaises(TriangulationError) as cm:
            triangulate(ring, list(range(n)), max_work=1000)
        self.assertIn("work budget", str(cm.exception))
        self.assertEqual(len(triangulate(ring, list(range(n)))), n - 2)
        cl = Classified()
        cl.buildings = [building(ring, fid="osm:way/61", height="5")]
        plan = build_plan(tiny_area(), flat_grid(), cl, PlanOptions(max_triangulation_work=1000))
        self.assertIn("work budget", {e["id"]: e["reason"] for e in plan.report["invalid_features"]}["osm:way/61"])


class RoofProvenanceTest(unittest.TestCase):
    """Finding 7: roof:orientation honoured; unusable source values kept apart from built ones."""

    FOOT = rect_ccw(-5, -3, 5, 3)  # 10 x 6

    def ridge(self, mesh):
        top = max(v[2] for v in mesh.vertices)
        return [v for v in mesh.vertices if abs(v[2] - top) < 1e-9]

    def test_reviewer_case_across(self):
        mesh, _, prov = build_building(building(self.FOOT, height="8", roof__height="6", roof__shape="gabled",
                                                roof__orientation="across"), flat_grid(), 0.0)
        ridge = self.ridge(mesh)
        self.assertEqual(len(ridge), 2)
        for x, y, z in ridge:
            self.assertAlmostEqual(z, 8.0)
            self.assertAlmostEqual(x, 0.0)          # ridge parallel to the short (y) side
            self.assertAlmostEqual(abs(y), 3.0)
        eave = sorted({round(v[2], 9) for v in mesh.vertices})
        self.assertIn(2.0, eave)  # 8 - 6: measured roof height honoured, not clamped to 4.8
        self.assertEqual(prov["roof_height"], "measured:osm roof:height")
        self.assertEqual(prov["roof_height_m"], 6.0)
        self.assertNotIn("roof_height_source", prov)
        self.assertEqual(prov["roof_orientation"], "measured:osm roof:orientation=across")
        assert_closed_manifold(self, mesh)

    def test_along_and_hipped_across(self):
        mesh, _, prov = build_building(building(self.FOOT, height="8", roof__height="3", roof__shape="gabled",
                                                roof__orientation="along"), flat_grid(), 0.0)
        for x, y, _ in self.ridge(mesh):
            self.assertAlmostEqual(y, 0.0)
            self.assertAlmostEqual(abs(x), 5.0)
        mesh, _, prov = build_building(building(self.FOOT, height="8", roof__height="3", roof__shape="hipped",
                                                roof__orientation="across"), flat_grid(), 0.0)
        ridge = self.ridge(mesh)
        self.assertTrue(all(abs(x) < 1e-9 for x, _, _ in ridge))
        self.assertGreater(max(abs(y) for _, y, _ in ridge), 0)
        self.assertLess(max(abs(y) for _, y, _ in ridge), 3.0)
        assert_closed_manifold(self, mesh)

    def test_unusable_roof_height_is_not_labelled_measured(self):
        mesh, _, prov = build_building(building(self.FOOT, height="6", roof__height="6", roof__shape="gabled"),
                                       flat_grid(), 0.0)
        self.assertTrue(prov["roof_height"].startswith("fallback"), prov["roof_height"])
        self.assertIn("measured", prov["roof_height_source"])
        self.assertIn("6", prov["roof_height_source"])
        self.assertIn("wall", prov["roof_height_reason"])
        self.assertAlmostEqual(prov["roof_height_m"], 5.5)
        self.assertAlmostEqual(max(v[2] for v in mesh.vertices), 6.0)
        _, _, prov = build_building(building(self.FOOT, height="6", roof__height="3", roof__shape="flat"),
                                    flat_grid(), 0.0)
        self.assertFalse(prov["roof_height"].startswith("measured"), prov["roof_height"])
        self.assertEqual(prov["roof_height_m"], 0.0)
        self.assertIn("roof_height_source", prov)


if __name__ == "__main__":
    unittest.main()
