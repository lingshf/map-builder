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
from map_builder.core import generate as gen
from map_builder.core.osm import Classified, Feature, Polygon, classify, parse_osm_xml, ring_area
from map_builder.core.triangulate import TriangulationError, triangulate, verify_triangulation

from .synthetic import OsmBuilder, synthetic_inputs


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
        # height 15: the 10 m of relief stays below the eave (>= eave is rejected, see finding 3)
        mesh, origin, prov = build_building(building(rect_ccw(-20, -20, 20, 20), height="15"), grid, 0.0)
        self.assertAlmostEqual(origin[2], 40.0)  # not 50 (vertex-only sampling floated it)
        self.assertEqual(prov["ground_slope_m"], 10.0)
        # a courtyard over the dip excludes it
        mesh, origin, _ = build_building(building(rect_ccw(-20, -20, 20, 20), [rect_cw(-10, -10, 10, 10)],
                                                  height="15"), grid, 0.0)
        self.assertAlmostEqual(origin[2], 50.0)

    def test_terrain_peak_reaching_eave_is_reported(self):
        heights = [[0.0] * 11 for _ in range(11)]
        heights[5][5] = 30.0
        grid = make_grid(heights, x0=-50, y0=-50)
        cl = Classified()
        cl.buildings = [building(rect_ccw(-20, -20, 20, 20), fid="osm:way/90", height="10")]
        plan = build_plan(tiny_area(), grid, cl)
        # round 2, finding 3: rejected and reported, not emitted with only a warning
        self.assertNotIn("osm:way/90", {o.mb_id for o in plan.objects})
        entry = [e for e in plan.report["invalid_features"] if e["id"] == "osm:way/90"]
        self.assertEqual(len(entry), 1)
        self.assertIn("reaches eave/roof", entry[0]["reason"])
        self.assertIn("no grading policy", entry[0]["reason"])
        with self.assertRaises(InvalidFeature):
            build_building(cl.buildings[0], grid, 0.0)
        # a gentle bump below the eave is not reported
        heights[5][5] = 3.0
        plan = build_plan(tiny_area(), make_grid(heights, x0=-50, y0=-50), cl)
        self.assertFalse(any("osm:way/90" in w for w in plan.report["warnings"]))
        self.assertIn("osm:way/90", {o.mb_id for o in plan.objects})
        self.assertFalse(any(e["id"] == "osm:way/90" for e in plan.report["invalid_features"]))

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



# --- Round 2 review findings ----------------------------------------------------

def _clip_left(poly, a, b):
    out = []
    for k in range(len(poly)):
        p, q = poly[k], poly[(k + 1) % len(poly)]
        sp = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        sq = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
        if sp >= 0:
            out.append(p)
        if (sp > 0 > sq) or (sp < 0 < sq):
            t = sp / (sp - sq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def poly_area(poly):
    return sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1]
               for k in range(len(poly))) / 2.0


def tri_overlap(t1, t2):
    """Area of the intersection of two CCW triangles (2D)."""
    poly = list(t1)
    for k in range(3):
        poly = _clip_left(poly, t2[k], t2[(k + 1) % 3])
        if len(poly) < 3:
            return 0.0
    return poly_area(poly)


def union_area(polys):
    """Exact area of a union of convex polygons (vertical slabs at every vertex x and edge
    crossing: inside a slab the covered length is linear in x, so area = width x midpoint length)."""
    edges, xs = [], []
    for pi, poly in enumerate(polys):
        for k in range(len(poly)):
            a, b = poly[k], poly[(k + 1) % len(poly)]
            xs.append(a[0])
            if a[0] != b[0]:
                edges.append((min(a, b), max(a, b), pi))

    def y_at(e, x):
        (x0, y0), (x1, y1), _ = e
        return y0 + (x - x0) * (y1 - y0) / (x1 - x0)

    for u, e in enumerate(edges):
        for f in edges[u + 1:]:
            lo, hi = max(e[0][0], f[0][0]), min(e[1][0], f[1][0])
            if hi > lo:
                d0, d1 = y_at(e, lo) - y_at(f, lo), y_at(e, hi) - y_at(f, hi)
                if d0 * d1 < 0:
                    xs.append(lo + (hi - lo) * d0 / (d0 - d1))
    xs = sorted(set(xs))
    total = 0.0
    for xa, xb in zip(xs, xs[1:]):
        xm = (xa + xb) / 2
        ivs = []
        for pi in range(len(polys)):
            ys = [y_at(e, xm) for e in edges if e[2] == pi and e[0][0] < xm < e[1][0]]
            if len(ys) >= 2:
                ivs.append((min(ys), max(ys)))
        ivs.sort()
        length, cur = 0.0, None
        for lo, hi in ivs:
            if cur is None or lo > cur[1]:
                if cur:
                    length += cur[1] - cur[0]
                cur = [lo, hi]
            else:
                cur[1] = max(cur[1], hi)
        if cur:
            length += cur[1] - cur[0]
        total += (xb - xa) * length
    return total


def world_tris(mesh, loc):
    V = [(x + loc[0], y + loc[1]) for x, y, _ in mesh.vertices]
    return [tuple(V[i] for i in t) for t in mesh.triangles()]


def inside_convex(poly, p, margin):
    return all((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) > margin * math.dist(a, b)
               for a, b in zip(poly, poly[1:] + poly[:1]))


class RibbonOverlapTest(unittest.TestCase):
    """Round 2, finding 1: ribbon faces are interior-disjoint and exactly cover the footprint union."""

    def check_ribbon(self, pts, width, grid, samples=0, rng=None):
        mesh, loc, prov = build_road(road(pts, width=str(width)), grid, 0.0)
        self.assertIsNotNone(mesh, prov)
        tris = world_tris(mesh, loc)
        # no duplicate faces
        keys = [tuple(sorted((round(x, 6), round(y, 6)) for x, y in t)) for t in tris]
        self.assertEqual(len(keys), len(set(keys)), "duplicate road faces")
        # no pairwise interior overlap
        boxes = [(min(p[0] for p in t), max(p[0] for p in t), min(p[1] for p in t), max(p[1] for p in t))
                 for t in tris]
        order = sorted(range(len(tris)), key=lambda k: boxes[k][0])
        for n, a in enumerate(order):
            for b in order[n + 1:]:
                if boxes[b][0] >= boxes[a][1]:
                    break
                if boxes[a][2] < boxes[b][3] and boxes[b][2] < boxes[a][3]:
                    self.assertLessEqual(tri_overlap(tris[a], tris[b]), 1e-6, (pts, width, tris[a], tris[b]))
        # summed area == area of the union of the footprint pieces
        pieces = gen._road_pieces(gen._dedupe_polyline(pts), width / 2)
        self.assertAlmostEqual(sum(poly_area(t) for t in tris), union_area(pieces), places=5)
        # point coverage: exactly once inside the union, never outside
        if samples:
            x0, x1, y0, y1 = (min(p[0] for p in pts) - width, max(p[0] for p in pts) + width,
                              min(p[1] for p in pts) - width, max(p[1] for p in pts) + width)
            for _ in range(samples):
                p = (rng.uniform(x0, x1), rng.uniform(y0, y1))
                strict = sum(1 for t in tris if inside_convex(list(t), p, 1e-7))
                loose = sum(1 for t in tris if inside_convex(list(t), p, -1e-7))
                if any(inside_convex(pc, p, 1e-6) for pc in pieces):
                    self.assertGreaterEqual(loose, 1, p)
                elif not any(inside_convex(pc, p, -1e-6) for pc in pieces):
                    self.assertEqual(loose, 0, p)
                self.assertLessEqual(strict, 1, p)
        self.assertTrue(all(tri_normal_z(mesh, t) > 0 for t in mesh.triangles()))
        return tris

    def test_reviewer_turn_covers_footprint_once(self):
        tris = self.check_ribbon([(0, 1), (3, 1), (3, 4)], 4, flat_grid())
        self.assertAlmostEqual(sum(poly_area(t) for t in tris), 22.0, places=9)  # was 26

    def test_reversal_emits_no_duplicates(self):
        tris = self.check_ribbon([(0, 1), (3, 1), (0, 1)], 4, flat_grid())
        self.assertAlmostEqual(sum(poly_area(t) for t in tris), 12.0, places=9)

    def test_randomized_polylines(self):
        rng = random.Random(2024)
        grid = make_grid([[rng.uniform(0, 12) for _ in range(11)] for _ in range(11)], x0=-50, y0=-50)
        for trial in range(60):
            pts = [(rng.uniform(-20, 20), rng.uniform(-20, 20))]
            while len(pts) < rng.randint(2, 8):
                step = rng.choice([0.3, 1.0, 3.0, 8.0, 15.0])
                ang = rng.uniform(0, 2 * math.pi) if rng.random() < 0.7 else \
                    math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0]) + math.pi * rng.choice([1, 0.9, 0.5])\
                    if len(pts) > 1 else 0.0
                q = (pts[-1][0] + step * math.cos(ang), pts[-1][1] + step * math.sin(ang))
                if max(abs(q[0]), abs(q[1])) < 35:
                    pts.append(q)
            width = rng.choice([1.0, 3.5, 6.0, 12.0])
            with self.subTest(trial=trial, pts=pts, width=width):
                self.check_ribbon(pts, width, grid, samples=60, rng=rng)


class ScatterBoundsTest(unittest.TestCase):
    """Round 2, finding 2: landcover indexing and scatter are bounded by the scene, not the polygon."""

    def test_huge_forest_polygon(self):
        cl = Classified()
        cl.areas = [Feature("osm:way/71", "area", {"_class": "forest", "landuse": "forest"},
                            Polygon(rect_ccw(-10_000, -10_000, 10_000, 10_000)))]
        sizes = []
        real = gen._Buckets

        def record(*a, **k):
            b = real(*a, **k)
            sizes.append(len(b.map))
            return b

        with mock.patch("map_builder.core.generate._Buckets", side_effect=record):
            plan = build_plan(tiny_area(), flat_grid(), cl, PlanOptions(max_trees=500))
        self.assertTrue(sizes)
        self.assertLessEqual(max(sizes), 16, sizes)  # old code: 160,801 buckets for this polygon
        trees = [o for o in plan.objects if o.mb_class == "vegetation"]
        self.assertGreater(len(trees), 50)  # old code: the limit filled with points outside the area -> 0
        self.assertTrue(all(abs(o.location[0]) <= 50 and abs(o.location[1]) <= 50 for o in trees))

    def test_polygon_inside_bounds_is_unchanged(self):
        f = Feature("osm:way/72", "area", {"_class": "forest"}, Polygon(rect_ccw(-30, -20, 25, 30)))
        a = gen.scatter_points(f, 1 / 60, random.Random(5), 1000)
        b = gen.scatter_points(f, 1 / 60, random.Random(5), 1000, bounds=(-50, -50, 50, 50))
        self.assertEqual(a, b)
        self.assertTrue(a)


class HoleToleranceTest(unittest.TestCase):
    """Round 2, finding 4: small holes are kept; degenerate ones reject the footprint (never solid)."""

    def plan_for(self, hole_side):
        b = OsmBuilder()
        rid = b.multipolygon(rect_ccw(-10, -10, 10, 10), [rect_ccw(3, 3, 3 + hole_side, 3 + hole_side)],
                             {"building": "yes", "height": "10"})
        cl = classify(parse_osm_xml(b.xml().encode()), tiny_area())
        return f"osm:relation/{rid}", cl, build_plan(tiny_area(), flat_grid(), cl, PlanOptions(trees=False))

    def test_small_valid_hole_is_kept(self):
        fid, cl, plan = self.plan_for(0.2)
        o = next(o for o in plan.objects if o.mb_id == fid)
        geom = next(f for f in cl.buildings if f.id == fid).geometry
        self.assertEqual(len(geom.holes), 1)
        self.assertAlmostEqual(ring_area(geom.holes[0]), -0.04, places=3)
        assert_closed_manifold(self, o.mesh)
        # old code: the hole was dropped and the roof covered the full outer ring
        self.assertAlmostEqual(roof_area(o.mesh), ring_area(geom.outer) + ring_area(geom.holes[0]), places=6)
        self.assertLess(roof_area(o.mesh), ring_area(geom.outer) - 0.03)

    def test_degenerate_hole_reports_footprint(self):
        fid, cl, plan = self.plan_for(0.05)
        self.assertEqual([o.mb_id for o in plan.objects if o.mb_class == "building"], [])
        reasons = [e["reason"] for e in plan.report["invalid_features"] if e["id"] == fid]
        self.assertEqual(len(reasons), 1)
        self.assertIn("degenerate inner ring", reasons[0])


class ManMadeBridgeTest(unittest.TestCase):
    """Round 2, finding 5: man_made=bridge/tunnel and building=bridge never become ground geometry."""

    def test_reported_not_built(self):
        b = OsmBuilder()
        w1 = b.way([(-30, 0), (30, 0)], {"highway": "service", "man_made": "bridge"})
        w2 = b.way([(-30, 10), (30, 10)], {"highway": "footway", "man_made": "tunnel"})
        w3 = b.way(rect_ccw(10, 10, 20, 20), {"building": "bridge"}, closed=True)
        w4 = b.way(rect_ccw(-20, -20, -10, -10), {"building:part": "bridge"}, closed=True)
        r1 = b.multipolygon(rect_ccw(-30, 20, -20, 30), [], {"man_made": "bridge"})
        w5 = b.way([(-30, -30), (30, -30)], {"highway": "service"})
        cl = classify(parse_osm_xml(b.xml().encode()), tiny_area())
        unsup = {u["id"]: u["reason"] for u in cl.unsupported}
        for wid in (w1, w2, w3, w4):
            self.assertIn(f"osm:way/{wid}", unsup)
        self.assertIn("man_made=bridge", unsup[f"osm:way/{w1}"])
        self.assertIn("man_made=tunnel", unsup[f"osm:way/{w2}"])
        self.assertIn("building=bridge", unsup[f"osm:way/{w3}"])
        self.assertIn(f"osm:relation/{r1}", unsup)
        self.assertEqual([r.id for r in cl.roads], [f"osm:way/{w5}"])
        self.assertEqual(cl.buildings, [])
        plan = build_plan(tiny_area(), flat_grid(), cl)
        self.assertEqual([o.mb_id for o in plan.objects if o.mb_class in ("road", "building")], [f"osm:way/{w5}"])


class WideRoadBudgetTest(unittest.TestCase):
    """Round 2, finding 6: a tight count replaces the cheap bound before a road is rejected."""

    @classmethod
    def setUpClass(cls):
        cls.grid = make_grid([[0.0] * 501 for _ in range(501)], spacing=2.0, x0=-500, y0=-500)
        cls.road = road([(-450, -450), (450, 450)], fid="osm:way/81", width="60")

    def test_wide_diagonal_road_fits_default_budget(self):
        cl = Classified()
        cl.roads = [self.road]
        plan = build_plan(Area(47.0, 8.0, 1000.0, 1000.0), self.grid, cl, PlanOptions(trees=False))
        o = next(o for o in plan.objects if o.mb_id == "osm:way/81")  # old estimate: 5.3M vertices -> LimitError
        self.assertLess(len(o.mesh.vertices), 60_000)
        self.assertLessEqual(plan.report["budget"]["vertices"], gen.MAX_SCENE_VERTICES)

    def test_over_budget_still_rejected_before_allocation(self):
        calls = []

        def reserve(v, t):
            calls.append((v, t))
            if t > 30_000:
                raise LimitError(f"refused {t} triangles")

        with mock.patch("map_builder.core.generate.MeshData", side_effect=AssertionError("allocated")):
            with self.assertRaises(LimitError):
                build_road(self.road, self.grid, 0.0, reserve=reserve)
        # round 3, finding 5: one reservation, with the exact final counts (no per-candidate estimate)
        self.assertEqual(len(calls), 1)
        mesh, _, _ = build_road(self.road, self.grid, 0.0)
        self.assertEqual(calls[0], (len(mesh.vertices), sum(1 for _ in mesh.triangles())))


def assert_planar_faces(test, mesh, tol=1e-6):
    V = mesh.vertices
    for f in mesh.faces:
        if len(f) == 3:
            continue
        a, b, c = (V[i] for i in f[:3])
        u = [b[k] - a[k] for k in range(3)]
        w = [c[k] - a[k] for k in range(3)]
        n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        ln = math.sqrt(sum(x * x for x in n))
        test.assertGreater(ln, 1e-9, f"{mesh.name}: degenerate face {f}")
        for i in f[3:]:
            d = sum((V[i][k] - a[k]) * n[k] for k in range(3)) / ln
            test.assertLessEqual(abs(d), tol, f"{mesh.name}: face {f} is not planar ({d:.3g} m)")


class PlanarFacesTest(unittest.TestCase):
    """Round 2, finding 7: every emitted face is planar or an explicit triangle."""

    def test_all_roof_shapes_and_footprints(self):
        trapezoid = [(0, 0), (10, 0), (10, 5), (0, 6)]
        rotated = [(0, 0), (8.660254, 5), (5.660254, 10.196152), (-3, 5.196152)]
        lshape = [(0, 0), (12, 0), (12, 5), (5, 5), (5, 10), (0, 10)]
        footprints = {"rect": (rect_ccw(-6, -4, 6, 4), []), "trapezoid": (trapezoid, []),
                      "rotated": (rotated, []), "L": (lshape, []),
                      "courtyard": (rect_ccw(-10, -10, 10, 10), [rect_cw(-4, -4, 4, 4)])}
        for name, (outer, holes) in footprints.items():
            for shape in ("flat", "gabled", "hipped", "pyramidal", "skillion"):
                with self.subTest(footprint=name, shape=shape):
                    mesh, _, prov = build_building(building(outer, holes, height="10", roof__shape=shape,
                                                            roof__direction="30"), flat_grid(), 0.0)
                    assert_planar_faces(self, mesh)
                    assert_closed_manifold(self, mesh)
        _, _, prov = build_building(building(trapezoid, height="10", roof__shape="gabled"), flat_grid(), 0.0)
        self.assertEqual(prov["roof_shape_built"], "gabled")
        self.assertIn("split", prov["roof_faces"])


class NumericTagBoundsTest(unittest.TestCase):
    """Round 2, finding 8: absurd numeric tags never reach vertices; they are reported."""

    CASES = {
        "roof:levels": {"roof__levels": "1e308", "roof__shape": "gabled"},
        "building:levels": {"building__levels": "1e308"},
        "height": {"height": "9" * 400},
        "min_height": {"height": "10", "min_height": "1e300"},
        "roof:height": {"roof__height": "5000", "roof__shape": "hipped"},
        "building:min_level": {"building__min_level": "1e308"},
    }

    def test_out_of_range_tags_fall_back(self):
        for key, tags in self.CASES.items():
            with self.subTest(tag=key):
                f = building(rect_ccw(-6, -4, 6, 4), fid="osm:way/95", **tags)
                mesh, origin, prov = build_building(f, flat_grid(), 0.0)
                self.assertTrue(all(math.isfinite(c) for v in mesh.vertices for c in v))
                self.assertTrue(all(math.isfinite(c) for c in origin))
                self.assertLessEqual(max(v[2] for v in mesh.vertices), gen.MAX_HEIGHT_M)
                self.assertIn(key + "=", prov["rejected_tags"])
                cl = Classified()
                cl.buildings = [f]
                plan = build_plan(tiny_area(), flat_grid(), cl, PlanOptions(trees=False))
                self.assertIn("osm:way/95", {o.mb_id for o in plan.objects})
                self.assertTrue(any(w.startswith("osm:way/95: out-of-range tags") for w in plan.report["warnings"]))

    def test_height_fallback_provenance(self):
        _, _, prov = build_building(building(rect_ccw(-6, -4, 6, 4), height="9" * 400, building__levels="4"),
                                    flat_grid(), 0.0)
        self.assertEqual(prov["height_m"], 12.0)
        self.assertTrue(prov["height"].startswith("fallback:building:levels"))
        self.assertIn("not a finite number", prov["height_reason"])
        self.assertIn("osm height", prov["height_source"])
        self.assertIsNone(parse_length("9" * 400))
        self.assertIsNone(parse_length("9" * 400 + " ft"))
        self.assertIsNone(parse_length("9" * 400 + "'"))


# --- Round 3 review findings ----------------------------------------------------

def plan_road_tris(plan):
    """[(mb_id, world 2D triangle)] over every road object of a plan."""
    return [(o.mb_id, t) for o in plan.objects if o.mb_class == "road" for t in world_tris(o.mesh, o.location)]


def assert_no_shared_area(test, tagged, tol=1e-6):
    """No coincident triangles and no pairwise 2D overlap > tol m2 across all (id, triangle)s."""
    tris = [t for _, t in tagged]
    keys = [tuple(sorted((round(x, 6), round(y, 6)) for x, y in t)) for t in tris]
    dup = [k for k, n in Counter(keys).items() if n > 1]
    test.assertEqual(dup, [], "coincident road triangles")
    boxes = [(min(p[0] for p in t), max(p[0] for p in t), min(p[1] for p in t), max(p[1] for p in t)) for t in tris]
    order = sorted(range(len(tris)), key=lambda k: boxes[k][0])
    for n, a in enumerate(order):
        for b in order[n + 1:]:
            if boxes[b][0] >= boxes[a][1]:
                break
            if boxes[a][2] < boxes[b][3] and boxes[b][2] < boxes[a][3]:
                ov = tri_overlap(tris[a], tris[b])
                test.assertLessEqual(ov, tol, (tagged[a][0], tagged[b][0], tris[a], tris[b], ov))


def road_union_area(features):
    return union_area([pc for f in features
                       for pc in gen._road_pieces(gen._dedupe_polyline(f.geometry), gen.road_width(f.tags)[0] / 2)])


class CrossWayOwnershipTest(unittest.TestCase):
    """Round 3, finding 1: at-grade roads that cross or meet never share area."""

    GRID = flat_grid(n=101, spacing=1.0, x0=-50, y0=-50)

    def crossing(self, foot_pts=((0, -10), (0, 10))):
        cl = Classified()
        cl.roads = [road(foot_pts, fid="osm:way/102", highway="footway", width="2"),
                    road([(-10, 0), (10, 0)], fid="osm:way/101", width="4")]
        return cl, build_plan(tiny_area(), self.GRID, cl, PlanOptions(trees=False))

    def test_reviewer_crossing(self):
        cl, plan = self.crossing()
        tagged = plan_road_tris(plan)
        assert_no_shared_area(self, tagged)  # old code: 16 identical triangles in both objects
        area = {k: sum(poly_area(t) for i, t in tagged if i == k) for k in ("osm:way/101", "osm:way/102")}
        self.assertAlmostEqual(area["osm:way/101"], 80.0, places=6)       # residential keeps its full ribbon
        self.assertAlmostEqual(area["osm:way/102"], 40.0 - 8.0, places=6)  # footway minus the crossing
        self.assertAlmostEqual(sum(area.values()), road_union_area(cl.roads), places=6)
        objs = {o.mb_id: o for o in plan.objects if o.mb_class == "road"}
        self.assertEqual([o.mb_id for o in plan.objects if o.mb_class == "road"], ["osm:way/102", "osm:way/101"])
        self.assertIn("osm:way/101", objs["osm:way/102"].provenance["overlap"])
        self.assertIn("8.00 m2", objs["osm:way/102"].provenance["overlap"])
        self.assertNotIn("overlap", objs["osm:way/101"].provenance)
        self.assertNotEqual(objs["osm:way/101"].mesh.face_colors[0], objs["osm:way/102"].mesh.face_colors[0])
        self.assertEqual(plan.report["counts"]["roads_clipped_by_higher_priority"], 1)
        self.assertEqual(plan.report["invalid_features"], [])

    def test_fully_covered_way_is_a_warning(self):
        cl, plan = self.crossing(foot_pts=((-5, 0), (5, 0)))
        self.assertEqual([o.mb_id for o in plan.objects if o.mb_class == "road"], ["osm:way/101"])
        self.assertFalse(any(e["id"] == "osm:way/102" for e in plan.report["invalid_features"]))
        w = [w for w in plan.report["warnings"] if w.startswith("osm:way/102")]
        self.assertEqual(len(w), 1)
        self.assertIn("osm:way/101", w[0])
        self.assertEqual(plan.report["counts"]["roads_fully_covered"], 1)

    def test_priority_class_then_width_then_id(self):
        r = lambda fid, **t: road([(0, 0), (1, 0)], fid=fid, **t)  # noqa: E731
        ranked = sorted([r("osm:way/5", highway="footway"), r("osm:way/4", width="9"), r("osm:way/3"),
                         r("osm:way/2", highway="primary"), r("osm:way/1")], key=gen.road_priority)
        self.assertEqual([f.id for f in ranked], ["osm:way/2", "osm:way/4", "osm:way/1", "osm:way/3", "osm:way/5"])

    def test_randomized_multi_road(self):
        rng = random.Random(77)
        grid = make_grid([[rng.uniform(0, 10) for _ in range(21)] for _ in range(21)], spacing=5.0, x0=-50, y0=-50)
        classes = ["primary", "residential", "service", "footway", "path", "cycleway"]
        for trial in range(8):
            cl = Classified()
            for k in range(rng.randint(3, 5)):
                pts = [(rng.uniform(-25, 25), rng.uniform(-25, 25))]
                for _ in range(rng.randint(1, 3)):
                    pts.append((min(30, max(-30, pts[-1][0] + rng.uniform(-20, 20))),
                                min(30, max(-30, pts[-1][1] + rng.uniform(-20, 20)))))
                tags = {"highway": rng.choice(classes)}
                if rng.random() < 0.5:
                    tags["width"] = str(rng.choice([1.5, 3.0, 4.0, 7.0, 10.0]))
                cl.roads.append(road(pts, fid=f"osm:way/{500 + k}", **tags))
            if rng.random() < 0.5:  # an exact duplicate of another way (same class and width)
                src = cl.roads[0]
                cl.roads.append(Feature("osm:way/599", "road", dict(src.tags), list(src.geometry)))
            calls = []
            real = gen.SceneBudget.reserve

            def record(budget, fid, v, t):
                calls.append((fid, v, t))
                return real(budget, fid, v, t)

            with self.subTest(trial=trial), mock.patch.object(gen.SceneBudget, "reserve", autospec=True,
                                                              side_effect=record):
                plan = build_plan(tiny_area(), grid, cl, PlanOptions(trees=False))
                tagged = plan_road_tris(plan)
                assert_no_shared_area(self, tagged)
                self.assertAlmostEqual(sum(poly_area(t) for _, t in tagged), road_union_area(cl.roads), places=4)
                self.assertEqual(plan.report["invalid_features"], [])
                for o in plan.objects:
                    if o.mb_class == "road":
                        self.assertIn((o.mb_id, len(o.mesh.vertices), sum(1 for _ in o.mesh.triangles())), calls)
                        self.assertTrue(all(tri_normal_z(o.mesh, t) > 0 for t in o.mesh.triangles()))


class SlopedRoofClearanceTest(unittest.TestCase):
    """Round 3, finding 2: terrain is compared with the roof underside at the same XY."""

    FOOT = rect_ccw(-10, -5, 10, 5)

    @staticmethod
    def falling_east():
        # terrain 4 m at x = -10 falling linearly to 0 m at x = 10
        return make_grid([[2.0 - 0.2 * (-50 + 10 * i) for i in range(11)] for _ in range(11)], x0=-50, y0=-50)

    def skillion(self, direction):
        return building(self.FOOT, fid="osm:way/201", height="8", roof__height="5", roof__shape="skillion",
                        roof__direction=direction)

    def test_reviewer_skillion_clears_falling_terrain(self):
        grid = self.falling_east()
        mesh, origin, prov = build_building(self.skillion("90"), grid, 0.0)  # high (8 m) west, low (3 m) east
        self.assertIn("terrain_clearance", prov)
        tops = [v for v in mesh.vertices if v[2] > 0]
        self.assertAlmostEqual(max(v[2] for v in tops), 8.0)
        self.assertAlmostEqual(min(v[2] for v in tops), 3.0)
        for x, y, z in tops:
            clearance = z + origin[2] - terrain_height(grid, x + origin[0], y + origin[1])
            self.assertGreaterEqual(clearance, 3.0 - 1e-9)
        cl = Classified()
        cl.buildings = [self.skillion("90")]
        plan = build_plan(tiny_area(), grid, cl, PlanOptions(trees=False))
        self.assertIn("osm:way/201", {o.mb_id for o in plan.objects})

    def test_penetrating_skillion_is_rejected(self):
        # low (3 m) edge on the west, where the terrain is 4 m above the base datum
        with self.assertRaises(InvalidFeature) as cm:
            build_building(self.skillion("270"), self.falling_east(), 0.0)
        self.assertIn("reaches eave/roof", str(cm.exception))
        self.assertIn("(-10.00,", str(cm.exception))

    def test_interior_node_against_sloped_underside(self):
        # flat terrain with one node at (0, 0); the skillion underside is 5.5 m there
        for bump, ok in ((5.0, True), (6.0, False)):
            heights = [[0.0] * 11 for _ in range(11)]
            heights[5][5] = bump
            grid = make_grid(heights, x0=-50, y0=-50)
            with self.subTest(bump=bump):
                if ok:
                    build_building(self.skillion("90"), grid, 0.0)
                else:
                    with self.assertRaises(InvalidFeature) as cm:
                        build_building(self.skillion("90"), grid, 0.0)
                    self.assertIn("(0.00, 0.00)", str(cm.exception))

    def test_flat_roof_still_uses_eave(self):
        with self.assertRaises(InvalidFeature):
            build_building(building(self.FOOT, height="4"), self.falling_east(), 0.0)
        build_building(building(self.FOOT, height="4.5"), self.falling_east(), 0.0)


class TerrainExtentTest(unittest.TestCase):
    """Round 3, finding 3: nothing is emitted outside the terrain extent without a report."""

    def test_features_beyond_terrain_edge(self):
        area = Area(47.0, 8.0, 140.0, 100.0)  # x -70..70, terrain only -50..50
        grid = flat_grid()
        cl = Classified()
        cl.buildings = [building(rect_ccw(35, -5, 55, 5), fid="osm:way/301", height="6"),
                        building(rect_ccw(20, -5, 30, 5), fid="osm:way/302", height="6")]
        cl.trees = [Feature("osm:node/303", "tree", {"natural": "tree"}, (55.0, 20.0)),
                    Feature("osm:node/304", "tree", {"natural": "tree"}, (10.0, 20.0))]
        cl.roads = [road([(30, 30), (65, 30)], fid="osm:way/305")]
        cl.areas = [Feature("osm:way/306", "area", {"_class": "forest", "landuse": "forest"},
                            Polygon(rect_ccw(-70, -50, 70, 50)))]
        plan = build_plan(area, grid, cl, PlanOptions(max_trees=1000))
        reasons = {e["id"]: e["reason"] for e in plan.report["invalid_features"]}
        self.assertIn("terrain extent", reasons["osm:way/301"])   # old code: built, overhanging x = 50..55
        self.assertIn("terrain extent", reasons["osm:node/303"])
        ids = {o.mb_id for o in plan.objects}
        self.assertTrue({"osm:way/302", "osm:node/304", "osm:way/305"} <= ids)
        self.assertNotIn("osm:way/301", ids)
        self.assertNotIn("osm:node/303", ids)
        self.assertEqual(plan.report["counts"]["roads_trimmed_at_terrain_edge"], 1)
        self.assertTrue(any("does not cover the scene area" in w for w in plan.report["warnings"]))
        for o in plan.objects:
            if o.mesh is not None:
                for x, y, _ in o.mesh.vertices:
                    self.assertLessEqual(abs(x + o.location[0]), 50 + 1e-9, o.mb_id)
                    self.assertLessEqual(abs(y + o.location[1]), 50 + 1e-9, o.mb_id)
            else:
                self.assertTrue(gen.inside_terrain(grid, o.location[0], o.location[1], tol=0.0), o.mb_id)
        self.assertGreater(sum(1 for o in plan.objects if o.mb_id.startswith("scatter:")), 50)
        with self.assertRaises(InvalidFeature):
            build_building(cl.buildings[0], grid, 0.0)
        build_building(building(rect_ccw(40, -5, 50.0005, 5), height="6"), grid, 0.0)  # within tolerance


class StoreyHeightTest(unittest.TestCase):
    """Round 3, finding 4: building:levels gives the eave; the roof is added on top."""

    FOOT = rect_ccw(-5, -3, 5, 3)  # short side 6 -> inferred roof 1.8 m

    def levels(self, mesh):
        return sorted({round(v[2], 6) for v in mesh.vertices})

    def test_reviewer_levels_gabled_without_height(self):
        mesh, _, prov = build_building(building(self.FOOT, building__levels="2", roof__shape="gabled"),
                                       flat_grid(), 0.0)
        self.assertEqual(self.levels(mesh), [-0.3, 6.0, 7.8])  # old code: eave 3, ridge 6
        self.assertEqual(prov["height_m"], 7.8)
        self.assertEqual(prov["eave_height_m"], 6.0)
        self.assertEqual(prov["roof_height_m"], 1.8)
        self.assertIn("to the eave", prov["height"])
        self.assertTrue(prov["height"].startswith("inferred:building:levels"))
        self.assertIn("above the storey-derived eave", prov["roof_height"])
        assert_closed_manifold(self, mesh)

    def test_explicit_height_is_total(self):
        mesh, _, prov = build_building(building(self.FOOT, height="8", building__levels="2", roof__shape="gabled"),
                                       flat_grid(), 0.0)
        self.assertEqual(self.levels(mesh), [-0.3, 6.2, 8.0])
        self.assertEqual(prov["height"], "measured:osm height")
        self.assertNotIn("above the storey-derived eave", prov["roof_height"])

    def test_roof_sources_added_on_top_of_levels(self):
        cases = [({"roof__levels": "1"}, [-0.3, 6.0, 9.0], "inferred:roof:levels x 3 m"),
                 ({"roof__height": "2.5"}, [-0.3, 6.0, 8.5], "measured:osm roof:height")]
        for tags, zs, label in cases:
            with self.subTest(tags=tags):
                mesh, _, prov = build_building(building(self.FOOT, building__levels="2", roof__shape="hipped",
                                                        **tags), flat_grid(), 0.0)
                self.assertEqual(self.levels(mesh), zs)
                self.assertEqual(prov["roof_height"], label)
        mesh, _, prov = build_building(building(self.FOOT, building__levels="2"), flat_grid(), 0.0)
        self.assertEqual(self.levels(mesh), [-0.3, 6.0])  # flat roof: eave == top
        h, _, roof, _ = gen.building_height({"building": "yes", "building:levels": "2", "roof:levels": "1"})
        self.assertEqual((h, roof), (9.0, 3.0))


class ExactRoadCountTest(unittest.TestCase):
    """Round 3, finding 5: the road budget count is exactly the emitted mesh."""

    GRID = flat_grid(n=101, spacing=1.0, x0=-50, y0=-50)

    def test_reviewer_road_count_is_exact(self):
        calls = []
        mesh, _, _ = build_road(road([(0, 0), (6, 0)], width="4"), self.GRID, 0.0,
                                reserve=lambda v, t: calls.append((v, t)))
        self.assertEqual((len(mesh.vertices), sum(1 for _ in mesh.triangles())), (35, 48))
        self.assertEqual(calls, [(35, 48)])  # old code requested 144 vertices

    def test_clipped_slivers_and_turns_count_exactly(self):
        rng = random.Random(8)
        grid = make_grid([[rng.uniform(0, 5) for _ in range(41)] for _ in range(41)], spacing=1.0, x0=-20, y0=-20)
        for k in range(40):
            pts = [(rng.uniform(-15, 15), rng.uniform(-15, 15)) for _ in range(rng.randint(2, 4))]
            calls = []
            mesh, _, prov = build_road(road(pts, width=str(rng.choice([0.7, 2.0, 3.3, 6.1]))), grid, 0.0,
                                       reserve=lambda v, t: calls.append((v, t)))
            if mesh is None:
                continue
            with self.subTest(k=k):
                self.assertEqual(calls, [(len(mesh.vertices), sum(1 for _ in mesh.triangles()))])
                used = {i for f in mesh.faces for i in f}
                self.assertEqual(len(used), len(mesh.vertices))  # no orphan vertices

    def test_budget_exactly_equal_to_need(self):
        cl = Classified()
        cl.roads = [road([(0, 0), (6, 0)], fid="osm:way/401", width="4")]
        n_v, n_t = self.GRID.nx * self.GRID.ny, 2 * (self.GRID.nx - 1) * (self.GRID.ny - 1)
        plan = build_plan(tiny_area(), self.GRID, cl, PlanOptions(trees=False, max_vertices=n_v + 35,
                                                                  max_triangles=n_t + 48))
        self.assertIn("osm:way/401", {o.mb_id for o in plan.objects})
        self.assertEqual(plan.report["budget"]["vertices"], n_v + 35)
        for opts in (dict(max_vertices=n_v + 34, max_triangles=n_t + 48),
                     dict(max_vertices=n_v + 35, max_triangles=n_t + 47)):
            with self.assertRaises(LimitError) as cm:
                build_plan(tiny_area(), self.GRID, cl, PlanOptions(trees=False, **opts))
            self.assertIn("osm:way/401", str(cm.exception))
