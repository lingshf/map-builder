# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Water surfaces on carved beds (S4-WATER-SURFACE, D113-D118). Synthetic scenes only."""
from __future__ import annotations

import math
import unittest
from unittest import mock

from map_builder.core import bridges, generate, shore, style, water
from map_builder.core.dem import ElevationGrid
from map_builder.core.generate import ROAD_LIFT_M
from map_builder.core.overlap import triangle_overlaps_region
from map_builder.core.osm import Feature, Polygon
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

    def test_at_grade_road_follows_the_carved_bed_instead_of_floating_over_it(self):
        z_off = self.plan.report["z_offset_m"]
        (water_obj,) = objects(self.plan, "water")
        level = water_obj.mesh.vertices[0][2] + z_off
        wet = [v[2] + r.location[2] for r in objects(self.plan, "road") for v in r.mesh.vertices
               if abs(v[0] + r.location[0]) < 30]
        self.assertTrue(wet)
        self.assertLessEqual(max(wet) + z_off, level - water.CARVE_DEPTH_M + ROAD_LIFT_M + 0.1)

    def test_at_grade_road_over_water_is_reported(self):
        row = bodies(self.plan)[self.ids[0]]
        (line,) = row["at_grade_roads"]
        self.assertEqual(line.split(",")[0], f"at-grade road over water: {self.ids[2]}")
        self.assertIn("80.0 m inside", line)
        self.assertRegex(line, r"[0-9.]+ m below L$")


def boundary_edges(mesh):
    count = {}
    for f in mesh.faces:
        for k in range(3):
            a, b = f[k], f[(k + 1) % 3]
            count.setdefault((min(a, b), max(a, b)), []).append((a, b))
    return [(mesh.vertices[e[0]][:2], mesh.vertices[e[1]][:2]) for e, uses in count.items() if len(uses) == 1]


def seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ll = dx * dx + dy * dy
    u = 0.0 if ll == 0 else min(1.0, max(0.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ll))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


def hausdorff(mesh, rings):
    """Both directions between the mesh's boundary edges and the polygon rings (endpoints and midpoints)."""
    edges = boundary_edges(mesh)
    ring_edges = [(r[k], r[(k + 1) % len(r)]) for r in rings for k in range(len(r))]
    mid = lambda e: ((e[0][0] + e[1][0]) / 2, (e[0][1] + e[1][1]) / 2)   # noqa: E731
    to_ring = max(seg_dist(p, *re_) for e in edges for p in (*e, mid(e))
                  for re_ in [min(ring_edges, key=lambda r: seg_dist(p, *r))])
    to_mesh = max(min(seg_dist(p, *e) for e in edges) for r in rings for k, p in enumerate(r))
    return max(to_ring, to_mesh)


class RiverBoundaryTest(unittest.TestCase):
    def build(self, length, hole=False):
        ring = [(-length / 2, -20.0), (length / 2, -20.0), (length / 2, 20.0), (-length / 2, 20.0)]
        ways = [([(-240.0, 0.0), (240.0, 0.0)], {"waterway": "river"}), (ring, {"natural": "water"}, True)]
        if hole:
            ways.append(([(-8.0, -6.0), (8.0, -6.0), (8.0, 6.0), (-8.0, 6.0)], {"natural": "water"}, True))
        return make_scene(ways, river_ground, width=W, height=H)

    def test_a_299_m_river_is_flat_and_a_301_m_river_is_profiled(self):
        plan, ids, _ = self.build(299.0)
        self.assertEqual(bodies(plan)[ids[1]]["outcome"], "built(flat)")
        plan, ids, _ = self.build(301.0)
        self.assertTrue(bodies(plan)[ids[1]]["outcome"].startswith("built(profile"), bodies(plan)[ids[1]])

    def test_island_hole_boundary_matches_the_polygon_within_a_millimetre(self):
        poly = water.Polygon(RIVER_RING, [[(-8.0, -6.0), (-8.0, 6.0), (8.0, 6.0), (8.0, -6.0)]])
        pieces = water.clip_polygon(poly, (-W / 2, -H / 2, W / 2, H / 2))
        body = water.Body("osm:way/1", poly, "area", pieces=pieces)
        body.level = water.Level(flat=10.0)
        water._triangulate_body(body)
        mesh = water.WaterModel(None, None, [body]).mesh(body)
        [(outer, holes)] = pieces
        self.assertLess(hausdorff(mesh, [outer, *holes]), 1e-3)
        self.assertEqual(len(boundary_edges(mesh)), len(outer) + 4)

    def test_level_is_the_p20_of_the_shore_band_for_a_lake(self):
        plan, ids, _ = lake_scene()
        row = bodies(plan)[ids[0]]
        self.assertEqual(row["level_m"], row["shore_percentiles"][20])


class CentrelineChainTest(unittest.TestCase):
    def test_chain_parts_rejects_duplicate_endpoints(self):
        a = Feature("osm:way/1", "area", {}, [(0.0, 0.0), (1.0, 0.0)])
        b = Feature("osm:way/2", "area", {}, [(1.0, 0.0), (2.0, 0.0)])
        c = Feature("osm:way/3", "area", {}, [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0)])
        a.node_ids = [1, 2]
        b.node_ids = [2, 3]
        c.node_ids = [2, 4, 5, 2]
        self.assertIsNone(water._chain_parts([a, b, c]))


class SamplesAndBudgetTest(unittest.TestCase):
    def test_too_few_samples_widen_the_band_then_fall_back(self):
        plan, ids, _ = lake_scene()
        n = bodies(plan)[ids[0]]["samples"]
        with mock.patch.object(water, "N_MIN", n + 1):
            plan, ids, _ = lake_scene()
        row = bodies(plan)[ids[0]]
        self.assertEqual((row["outcome"], row["band_cells"]), ("built(flat)", 4))
        with mock.patch.object(water, "N_MIN", 10 ** 6):
            plan, ids, _ = lake_scene()
        row = bodies(plan)[ids[0]]
        self.assertEqual(row["outcome"], "fallback(no shore samples)")
        self.assertEqual(objects(plan, "water"), [])
        self.assertIn("shore samples", " ".join(row["notes"]))

    def test_budget_refusal_keeps_the_painted_cells(self):
        from map_builder.core.errors import LimitError
        real = generate.SceneBudget.charge

        def refuse(self, fid, v, t):
            if fid.startswith("water:"):
                raise LimitError(f"{fid} needs too much")
            return real(self, fid, v, t)
        with mock.patch.object(generate.SceneBudget, "charge", refuse):
            plan, ids, _ = lake_scene()
        self.assertEqual(bodies(plan)[ids[0]]["outcome"], "fallback(budget)")
        self.assertEqual(objects(plan, "water"), [])
        z_off = plan.report["z_offset_m"]
        near = [v for v in objects(plan, "terrain")[0].mesh.vertices if abs(v[0]) < 1 and abs(v[1]) < 1]
        self.assertTrue(near)
        self.assertTrue(all(abs(v[2] + z_off - lake_ground(v[0], v[1])) < 1e-6 for v in near))


class DeckRaiseListTest(unittest.TestCase):
    def test_a_deck_raised_by_the_water_is_listed_and_never_lowered(self):
        cross = ([(0.0, -60.0), (0.0, 0.0), (0.0, 60.0)], {"highway": "secondary", "bridge": "yes"})
        plan, ids, _ = make_scene(river_ways([cross]), river_ground, width=W, height=H)
        (row,) = plan.report["water_decks_raised"]
        (bridge,) = objects(plan, "bridge")
        self.assertEqual(row["id"], ids[2])
        self.assertEqual(row["raised_m"], bridge.provenance["water_raise_m"])
        self.assertGreater(row["raised_m"], 0.0)
        dry, _, _ = make_scene([([(-250.0, 0.0), (250.0, 0.0)], {"waterway": "river"}), cross], river_ground,
                               width=W, height=H)
        self.assertNotIn("water_decks_raised", dry.report)
        (dry_bridge,) = objects(dry, "bridge")
        top = lambda o: max(v[2] + o.location[2] for v in o.mesh.vertices)   # noqa: E731
        self.assertGreaterEqual(top(bridge), top(dry_bridge) - 1e-3)


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


class BankColourTest(unittest.TestCase):
    """S4-WATER-BANK: a built water surface does not paint the terrain cells under it."""
    WATER = generate.LANDCOVER_COLORS["water"]
    FOREST = generate.LANDCOVER_COLORS["forest"]

    @staticmethod
    def cell_colours(plan, tmesh_obj):
        _, _, x0, y0, sp = tmesh_obj.mesh.grid_layout
        nx = tmesh_obj.mesh.grid_layout[0]
        out = {}
        for k, col in enumerate(tmesh_obj.mesh.face_colors[::2]):
            out[(k % (nx - 1), k // (nx - 1))] = (x0 + (k % (nx - 1) + 0.5) * sp, y0 + (k // (nx - 1) + 0.5) * sp, col)
        return out

    def test_built_body_paints_no_water_colour_and_other_landcover_wins(self):
        lake = [(-40.0, -30.0), (40.0, -30.0), (40.0, 30.0), (-40.0, 30.0)]
        wood = [(-60.0, -30.0), (0.0, -30.0), (0.0, 30.0), (-60.0, 30.0)]
        plan, ids, _ = make_scene([(lake, {"natural": "water"}, True), (wood, {"landuse": "forest"}, True)],
                                  lake_ground, width=W, height=H)
        self.assertTrue(bodies(plan)[ids[0]]["outcome"].startswith("built"))
        cells = self.cell_colours(plan, objects(plan, "terrain")[0])
        self.assertNotIn(self.WATER, [c for _, _, c in cells.values()])
        inside_both = [c for x, y, c in cells.values() if -35 < x < -5 and abs(y) < 25]
        self.assertTrue(inside_both)
        self.assertTrue(all(c == self.FOREST for c in inside_both))

    def test_fallback_keeps_water_colour_and_built_body_wins_over_it(self):
        from map_builder.core.dem import ElevationGrid
        from map_builder.core.generate import build_terrain
        from map_builder.core.osm import Feature, Polygon

        def rect(x0, y0, x1, y1):
            return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        fb = Feature("osm:way/1", "area", {"_class": "water"}, Polygon(rect(-16.0, -16.0, 16.0, 16.0), []))
        grid = ElevationGrid(-20.0, -20.0, 5.0, 9, 9, [[0.0] * 9 for _ in range(9)], {})
        # a built riverbank is not in ``areas``: only its polygon can win over the overlapping fallback area
        bank = water.Body("osm:way/2", Polygon(rect(-4.0, -4.0, 4.0, 4.0), []), "riverbank", outcome="built(flat)")
        bank.pieces = [(rect(-4.0, -4.0, 4.0, 4.0), [])]
        cov: dict[str, int] = {}
        only = build_terrain(grid, 0.0, [fb], {})
        both = build_terrain(grid, 0.0, [fb], cov, [bank])
        default = generate.LANDCOVER_COLORS[None]

        def cell(mesh, i, j):
            k = 2 * (j * 8 + i)
            return mesh.face_colors[k], mesh.face_colors[k + 1]
        self.assertEqual(cell(only, 4, 4), (self.WATER, self.WATER))
        self.assertEqual(cell(both, 4, 4), (default, default))     # cell centre (2.5, 2.5): inside the bank
        self.assertEqual(cell(both, 1, 4), (self.WATER, self.WATER))   # fallback-only cell keeps the colour
        self.assertEqual([sum(c == self.WATER for c in m.face_colors) // 2 for m in (only, both)], [36, 32])
        self.assertEqual(cov, {fb.id: 36})
    def test_riverbank_only_body_changes_nothing(self):
        ring = [(-50.0, -20.0), (50.0, -20.0), (50.0, 20.0), (-50.0, 20.0)]
        plan, _, _ = make_scene([(ring, {"waterway": "riverbank"}, True)], river_ground, width=W, height=H)
        colours = set(objects(plan, "terrain")[0].mesh.face_colors)
        self.assertEqual(colours, {generate.LANDCOVER_COLORS[None]})


class ShoreRampWetWiringTest(unittest.TestCase):
    @staticmethod
    def rect(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def test_attach_ramps_checks_source_body_wet_overlap_by_area(self):
        source_piece = self.rect(-4.0, -1.0, 0.0, 3.0)
        wet_patch = self.rect(2.0, 0.55, 2.1, 0.65)
        body = water.Body("osm:way/1", Polygon(source_piece, []), "area",
                          pieces=[(source_piece, []), (wet_patch, [])], outcome="built(flat)",
                          level=water.Level(flat=10.0), shore=[((0.0, 0.0), (0.0, 2.0))])
        heights = [[6.0] * 12 for _ in range(12)]
        grid = ElevationGrid(-6.0, -6.0, 1.0, 12, 12, heights, {})
        model = water.WaterModel(grid, grid, [body])

        water._attach_ramps(model, lambda tri: False, shore.keep_whole, charge=None)
        self.assertGreater(body.info["shore_ramp_blocked_m"], 0.0)
        self.assertFalse(any(triangle_overlaps_region([(v[0], v[1]) for v in t], wet_patch, []) for t in body.bank))

    def test_attach_ramps_blocks_overlap_with_connected_concave_source_piece(self):
        source_piece = [(-5.0, -1.0), (0.0, -1.0), (0.0, 10.0), (2.0, 10.0),
                        (2.0, 0.55), (2.1, 0.55), (2.1, 11.0), (-5.0, 11.0)]
        body = water.Body("osm:way/1", Polygon(source_piece, []), "area",
                          pieces=[(source_piece, [])], outcome="built(flat)",
                          level=water.Level(flat=10.0), shore=[((0.0, 0.0), (0.0, 10.0))])
        heights = [[6.0] * 16 for _ in range(16)]
        grid = ElevationGrid(-6.0, -6.0, 1.0, 16, 16, heights, {})
        model = water.WaterModel(grid, grid, [body])

        water._attach_ramps(model, lambda tri: False, shore.keep_whole, charge=None)
        self.assertGreater(body.info["shore_ramp_blocked_m"], 0.0)


class StylizedWaterColourTest(unittest.TestCase):
    """S5-STYLE-WATER: cyan water, terrain-side shore band and sandy banks; colour only."""

    @staticmethod
    def build(style):
        opts = generate.PlanOptions(trees=False, scatter=False, style=style)
        return make_scene([([(-40.0, -30.0), (40.0, -30.0), (40.0, 30.0), (-40.0, 30.0)],
                            {"natural": "water"}, True)], lake_ground, width=W, height=H, opts=opts)[0]

    @staticmethod
    def colours(plan, prefix):
        return {tuple(c) for o in plan.objects if o.name.startswith(prefix) for c in o.mesh.face_colors}

    @staticmethod
    def shore_cell_centres(plan):
        mesh = objects(plan, "terrain")[0].mesh
        nx, _, x0, y0, sp = mesh.grid_layout
        return [(x0 + (k % (nx - 1) + 0.5) * sp, y0 + (k // (nx - 1) + 0.5) * sp, tuple(col))
                for k, col in enumerate(mesh.face_colors[::2])]

    def test_stylized_colours_water_bank_and_shore_band(self):
        plan = self.build("stylized")
        self.assertEqual(self.colours(plan, "water:"), {style.water_color("stylized")})
        self.assertEqual(self.colours(plan, "bank:"), {style.bank_color("stylized")})
        band = style.shore_band_color("stylized")
        banded = [(x, y) for x, y, c in self.shore_cell_centres(plan) if c == band]
        self.assertTrue(banded)
        for x, y in banded:  # within one cell of the lake rectangle, never inside it
            self.assertFalse(abs(x) < 40 and abs(y) < 30)
            self.assertLessEqual(max(abs(x) - 40, abs(y) - 30), 1.5 * SPACING)

    def test_colour_only_and_classic_has_no_band(self):
        classic, stylized = self.build("classic"), self.build("stylized")
        self.assertNotIn(style.shore_band_color("stylized"), {c for _, _, c in self.shore_cell_centres(classic)})
        self.assertEqual(self.colours(classic, "water:"), {style.water_color("classic")})
        self.assertEqual([(o.name, len(o.mesh.faces)) for o in classic.objects if o.mesh],
                         [(o.name, len(o.mesh.faces)) for o in stylized.objects if o.mesh])


if __name__ == "__main__":
    unittest.main()
