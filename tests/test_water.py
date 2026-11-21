# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Water surfaces on carved beds (S4-WATER-SURFACE, D113-D118). Synthetic scenes only."""
from __future__ import annotations

import math
import unittest
from unittest import mock

from map_builder.core import bridges, generate, water
from map_builder.core.generate import ROAD_LIFT_M
from map_builder.core.query import ray_cast
from map_builder.core.structures import plan_collision

from .synthetic import OsmBuilder
from .test_bridges import SPACING, make_scene, objects

W, H = 500.0, 160.0


def river_ground(x, y):
    """Gently falling valley floor (0.4 %), a shallow channel at |y| < 8 and low banks."""
    return 20.0 - 0.004 * x + min(6.0, 0.15 * max(0.0, abs(y) - 8.0))


def lake_ground(x, y):
    return 10.0 + 0.02 * x + 0.01 * y


RIVER = [(-250.0, 0.0), (250.0, 0.0)]
RIVER_RING = [(-260.0, -20.0), (260.0, -20.0), (260.0, 20.0), (-260.0, 20.0)]


def river_ways(extra=()):
    return [(RIVER, {"waterway": "river"}), (RIVER_RING, {"natural": "water"}, True), *extra]


def river_scene(extra=(), **kw):
    return make_scene(river_ways(extra), river_ground, width=W, height=H, **kw)


def lake_scene():
    ring = [(-40.0, -30.0), (40.0, -30.0), (40.0, 30.0), (-40.0, 30.0)]
    return make_scene([(ring, {"natural": "water"}, True)], lake_ground, width=W, height=H)


def bodies(plan):
    return {b["id"]: b for b in plan.report["water_bodies"]}


class LakeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.ids, cls.grid = lake_scene()

    def test_flat_surface_in_its_own_object(self):
        (obj,) = objects(self.plan, "water")
        self.assertEqual(obj.name, f"water:{self.ids[0]}")
        self.assertEqual(bodies(self.plan)[self.ids[0]]["outcome"], "built(flat)")
        zs = {round(v[2], 6) for v in obj.mesh.vertices}
        self.assertEqual(len(zs), 1)
        self.assertTrue(all(len(f) == 3 for f in obj.mesh.faces))
        self.assertEqual({obj.mesh.materials[m] for m in obj.mesh.face_materials}, {"MB Water"})

    def test_bed_is_below_the_surface_everywhere(self):
        row = bodies(self.plan)[self.ids[0]]
        self.assertLess(row["max_terrain_above_water_m"], 0.0)
        (obj,) = objects(self.plan, "water")
        level = obj.mesh.vertices[0][2] + self.plan.report["z_offset_m"]
        terrain = objects(self.plan, "terrain")[0].mesh
        z_off = self.plan.report["z_offset_m"]
        inside = [v for v in terrain.vertices if abs(v[0]) < 38 and abs(v[1]) < 28]
        self.assertTrue(inside)
        self.assertTrue(all(v[2] + z_off <= level - water.CARVE_DEPTH_M + 1e-3 for v in inside))


class RiverProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.ids, cls.grid = river_scene()

    def test_downstream_profile_is_non_increasing(self):
        row = bodies(self.plan)[self.ids[1]]
        self.assertTrue(row["outcome"].startswith("built(profile"), row)
        levels = row["levels_m"]
        self.assertGreaterEqual(len(levels), 2)
        self.assertTrue(all(a >= b - 1e-9 for a, b in zip(levels, levels[1:])))

    def test_surface_clipped_to_the_extent(self):
        (obj,) = objects(self.plan, "water")
        xs = [v[0] for v in obj.mesh.vertices]
        self.assertLessEqual(max(xs), W / 2 + 1e-6)
        self.assertGreaterEqual(min(xs), -W / 2 - 1e-6)


class FallbackTest(unittest.TestCase):
    def test_failed_invariant_falls_back_to_the_pre_carve_terrain(self):
        real = water.build_water

        def uphill(*a, **k):   # a bed carved *up* breaks the invariant; no remedy rounds are allowed
            k["carve_depth"] = -3.0
            return real(*a, **k)
        with mock.patch.object(water, "REMEDY_ROUNDS", 0), mock.patch.object(generate.water, "build_water", uphill):
            plan, ids, _ = lake_scene()
        self.assertEqual(bodies(plan)[ids[0]]["outcome"], "fallback(carve invariant)")
        self.assertEqual(objects(plan, "water"), [])


def high_banks(x, y):
    return 20.0 - 0.004 * x + min(15.0, 0.4 * max(0.0, abs(y) - 8.0))


class BridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        real = water.build_water
        seen = {}

        def spy(*a, **k):
            seen["model"] = real(*a, **k)
            return seen["model"]
        cross = ([(0.0, -60.0), (0.0, 0.0), (0.0, 60.0)], {"highway": "secondary", "bridge": "yes"})
        with mock.patch.object(generate.water, "build_water", spy):
            cls.plan, cls.ids, _ = make_scene(river_ways([cross]), high_banks, width=W, height=H)
        cls.model = seen["model"]
        cls.z_off = cls.plan.report["z_offset_m"]

    def test_deck_stays_above_the_water_and_piers_reach_the_carved_bed(self):
        (bridge,) = objects(self.plan, "bridge")
        levels = bodies(self.plan)[self.ids[1]]["levels_m"]
        lowest = min(v[2] for v in bridge.mesh.vertices) + bridge.location[2] + self.z_off
        self.assertLessEqual(lowest, min(levels) - water.CARVE_DEPTH_M - bridges.PIER_SINK_M + 0.5)
        deck = next(p for p in self.plan.passage_probes if p["id"].endswith(":deck"))
        centre = min(deck["path_map"], key=lambda p: abs(p[1]))
        self.assertGreaterEqual(centre[2] + self.z_off, max(levels) + ROAD_LIFT_M)

    def test_wet_probe_clears_the_water_and_the_ground_over_the_whole_capsule(self):
        cap = bridges.capsule_polygon((-7.0, 0.0), (7.0, 0.0), bridges.PROBE_RADIUS_M)
        wmax, gmax = self.model.wmax_polygon(cap), self.model.ground_max_polygon(cap)
        self.assertIsNotNone(wmax)
        self.assertEqual(bridges._wet_max(self.model, (0.0, 0.0), (0.0, 1.0), 7.0, 0.0), max(wmax, gmax))

    def test_dry_probe_keeps_the_legacy_ground(self):
        self.assertEqual(bridges._wet_max(self.model, (0.0, 100.0), (0.0, 1.0), 7.0, 5.5), 5.5)

    def test_water_is_a_collision_surface_hit_before_the_bed(self):
        col, _ = plan_collision(self.plan)
        self.assertTrue(col.class_triangles("water"))
        hit = ray_cast(col, (30.0, 5.0, 60.0), (0.0, 0.0, -1.0), 200.0)
        self.assertEqual(col.objects[hit.object]["class"], "water")


class LakeStructuresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ring = [(-40.0, -30.0), (40.0, -30.0), (40.0, 30.0), (-40.0, 30.0)]
        bld = [(-30.0, -10.0), (-10.0, -10.0), (-10.0, 10.0), (-30.0, 10.0)]
        road = ([(-100.0, 20.0), (100.0, 20.0)], {"highway": "residential"})
        cls.plan, cls.ids, cls.grid = make_scene(
            [(ring, {"natural": "water"}, True), (bld, {"building": "yes"}, True), road],
            lake_ground, width=W, height=H)

    def test_building_walls_reach_the_carved_bed(self):
        rows = self.plan.report.get("water_buildings") or []
        self.assertEqual(len(rows), 1)
        (b,) = objects(self.plan, "building")
        (w,) = objects(self.plan, "water")
        bed = min(v[2] for v in objects(self.plan, "terrain")[0].mesh.vertices if abs(v[0] + 20) < 15 and abs(v[1]) < 15)
        low = min(v[2] + b.location[2] for v in b.mesh.vertices)
        self.assertLessEqual(low, bed + 1e-6)
        self.assertLess(low, w.mesh.vertices[0][2])

    def test_at_grade_road_keeps_its_pre_carve_surface(self):
        roads = objects(self.plan, "road")
        self.assertTrue(roads)
        top = max(v[2] for r in roads for v in r.mesh.vertices)
        self.assertGreater(top, objects(self.plan, "terrain")[0].mesh.vertices[0][2] - 100)

class CapsuleTest(unittest.TestCase):
    def test_polygon_is_convex_ccw_and_contains_the_capsule(self):
        poly = bridges.capsule_polygon((0.0, 0.0), (10.0, 0.0), 1.0)
        n = len(poly)
        for k in range(n):
            a, b, c = poly[k], poly[(k + 1) % n], poly[(k + 2) % n]
            self.assertGreater((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]), 0.0)
        for ang in range(0, 360, 10):
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            for cx, outward in ((0.0, ca <= 0.0), (10.0, ca >= 0.0)):
                if outward:
                    self.assertTrue(_inside(poly, cx + ca * 0.999, sa * 0.999), (cx, ang))

    def test_dry_probe_formula_is_untouched(self):
        class Dry:
            def touches_water(self, poly):
                return False
        self.assertEqual(bridges._wet_max(Dry(), (0.0, 0.0), (1.0, 0.0), 4.0, 12.345), 12.345)

def _inside(poly, x, y):
    n = len(poly)
    return all((poly[(k + 1) % n][0] - poly[k][0]) * (y - poly[k][1])
               - (poly[(k + 1) % n][1] - poly[k][1]) * (x - poly[k][0]) >= -1e-9 for k in range(n))


class RiverbankTest(unittest.TestCase):
    def test_riverbank_polygon_is_collected_only_in_riverbanks(self):
        from map_builder.core.geodesy import Area
        from map_builder.core.osm import classify, parse_osm_xml
        area = Area(47.0, 8.0, 200.0, 200.0)
        b = OsmBuilder(area.frame)
        wid = b.way([(-50, -20), (50, -20), (50, 20), (-50, 20)], {"waterway": "riverbank"}, closed=True)
        cl = classify(parse_osm_xml(b.xml().encode()), area)
        self.assertEqual([f.id for f in cl.riverbanks], [f"osm:way/{wid}"])
        self.assertEqual(cl.areas, [])


if __name__ == "__main__":
    unittest.main()
