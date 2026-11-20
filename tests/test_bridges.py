"""Bridge decks (map_builder/core/bridges.py, S1-BRIDGE): profile maths, end heights, validity, probes."""

import math
import re
import os
import tempfile
import types
import unittest
from unittest import mock

from map_builder.core import bridges
from map_builder.core.errors import LimitError
from map_builder.core.bridges import MAX_GRADE, deck_profile
from map_builder.core.dem import ElevationGrid
from map_builder.core.generate import ROAD_LIFT_M, PlanOptions, build_plan, terrain_height
from map_builder.core.geodesy import Area
from map_builder.core.osm import classify, parse_osm_xml
from map_builder.core.package import validate_package
from map_builder.core.pipeline import plan_to_package
from map_builder.core.query import ray_cast
from map_builder.core.structures import plan_collision

from .synthetic import OsmBuilder, synthetic_inputs, synthetic_sources

W, H, SPACING = 200.0, 100.0, 5.0


def valley_height(x, y):
    """Plateau at 15 m with a 15 m deep valley (floor 0 m for |x| <= 20, 0.75 slopes)."""
    return min(15.0, max(0.0, (abs(x) - 20.0) * 0.75))


def make_scene(ways, height_fn, width=W, height=H, opts=None, trees=(), joins=()):
    """Plan from hand-placed ways ``[(points, tags)]`` (and mapped trees ``[(x, y)]``) over a synthetic terrain;
    returns (plan, ids, grid) with the tree ids after the way ids. ``joins`` ``[(way, vertex, way, vertex)]`` make
    two ways share one OSM node."""
    area = Area(47.0, 8.0, width, height)
    b = OsmBuilder(area.frame)
    ids = [f"osm:way/{b.way(pts, tags)}" for pts, tags in ways]
    for wa, ia, wb, ib in joins:
        wmap = {f"osm:way/{w[0]}": k for k, w in enumerate(b.ways)}
        a, c = wmap[ids[wa]], wmap[ids[wb]]
        shared = b.ways[a][1][ia]
        b.nodes[:] = [n for n in b.nodes if n[0] != b.ways[c][1][ib]]
        b.ways[c] = (b.ways[c][0], [shared if k == ib else n for k, n in enumerate(b.ways[c][1])], b.ways[c][2])
    ids += [f"osm:node/{b.node(x, y, {'natural': 'tree', 'height': '8'})}" for x, y in trees]
    cl = classify(parse_osm_xml(b.xml().encode()), area)
    nx, ny = int(width / SPACING) + 1, int(height / SPACING) + 1
    x0, y0 = -width / 2, -height / 2
    grid = ElevationGrid(x0, y0, SPACING, nx, ny,
                         [[height_fn(x0 + i * SPACING, y0 + j * SPACING) for i in range(nx)] for j in range(ny)],
                         {"provider": "test"})
    return build_plan(area, grid, cl, opts or PlanOptions(trees=bool(trees), scatter=False)), ids, grid


def valley_scene():
    return make_scene([([(-100, 0), (-45, 0)], {"highway": "secondary"}),
                       ([(45, 0), (100, 0)], {"highway": "secondary"}),
                       ([(-45, 0), (0, 0), (45, 0)], {"highway": "secondary", "bridge": "yes"})],
                      valley_height, joins=[(2, 0, 0, 1), (2, 2, 1, 0)])


def objects(plan, cls):
    return [o for o in plan.objects if o.mb_class == cls]


class ProfileTest(unittest.TestCase):
    S = [10.0 * i for i in range(11)]

    def test_grade_never_exceeds_the_limit_and_ends_stay_put(self):
        top = deck_profile(self.S, [0.0] + [9.0] * 9 + [0.0], 0.0, 0.0)
        self.assertEqual((top[0], top[-1]), (0.0, 0.0))
        for a, b, s0, s1 in zip(top, top[1:], self.S, self.S[1:]):
            self.assertLessEqual(abs(b - a), MAX_GRADE * (s1 - s0) + 1e-9)
        self.assertAlmostEqual(top[5], 4.0)   # limited by 8 % from the nearer end (50 m x 0.08)

    def test_sloped_baseline_limits_the_deck_grade_not_just_the_raise(self):
        s = [2.0 * i for i in range(101)]   # 200 m with ends 8 m apart: a 4 % line
        lower = [0.0] * 101
        lower[50] = 7.0
        top = deck_profile(s, lower, 0.0, 8.0)
        self.assertLessEqual(max(abs(b - a) / (s1 - s0) for a, b, s0, s1 in zip(top, top[1:], s, s[1:])),
                             MAX_GRADE + 1e-9)
        self.assertGreaterEqual(top[50], 7.0)

    def test_need_is_met_when_the_grade_allows_it(self):
        top = deck_profile(self.S, [0.0] * 5 + [3.0] + [0.0] * 5, 0.0, 0.0)
        self.assertGreaterEqual(top[5], 3.0)
        self.assertEqual(top[0], 0.0)
        self.assertLess(top[1], 1.0)

    def test_nothing_needed_keeps_the_line(self):
        for a, b in zip(deck_profile(self.S, [-1.0] * 11, 0.0, 4.0), [0.4 * i for i in range(11)]):
            self.assertAlmostEqual(a, b)


class ValleyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.ids, cls.grid = valley_scene()
        cls.bridge = cls.ids[2]

    def test_one_bridge_object_and_report(self):
        bridges = objects(self.plan, "bridge")
        self.assertEqual([o.mb_id for o in bridges], [self.bridge])
        self.assertEqual(self.plan.report["counts"]["bridges"], 1)
        self.assertFalse(any(u["id"] == self.bridge for u in self.plan.report["unsupported_features"]))
        self.assertEqual(self.plan.report["invalid_features"], [])
        prov = bridges[0].provenance
        self.assertEqual(prov["width_m"], 8.0)
        self.assertTrue(prov["width"].startswith("inferred:road width + 2 x 0.5"))
        self.assertIn("raised up to", prov["profile"])   # ground at the abutments is within 5 m of the line
        self.assertTrue(prov["start_joint"].startswith("joins at-grade road osm:way/"))

    def test_deck_ends_meet_the_road_ribbon_within_5_cm(self):
        deck = objects(self.plan, "bridge")[0]
        for x, road_id in ((-45.0, self.ids[0]), (45.0, self.ids[1])):
            road = next(o for o in self.plan.objects if o.mb_id == road_id)
            r_tops = [road.location[2] + v[2] for v in road.mesh.vertices
                      if abs(v[0] + road.location[0] - x) < 0.5 and abs(v[1] + road.location[1]) < 2.0]
            tops = [deck.location[2] + v[2] for v in deck.mesh.vertices   # the parapet's inner edge: surface and top
                    if abs(v[0] + deck.location[0] - x) < 0.01 and 3.65 < abs(v[1] + deck.location[1]) < 3.75]
            self.assertTrue(r_tops and tops)
            self.assertLess(abs(min(tops) - max(r_tops)), 0.05)

    def test_probes_present_and_pass_in_the_validator(self):
        self.assertEqual([p["id"] for p in self.plan.passage_probes], [f"{self.bridge}:deck", f"{self.bridge}:under"])
        self.assertNotIn("passage_probes_blocked", self.plan.report)
        with tempfile.TemporaryDirectory() as d:
            _, r = plan_to_package(self.plan, os.path.join(d, "v.mbmap"), "valley", synthetic_sources())
            v = validate_package(os.path.join(d, "v.mbmap"))
        self.assertTrue(v.ok, v.errors)
        self.assertEqual([w for w in v.warnings if "probe" in w], [])

    def test_ray_from_the_valley_floor_hits_the_deck_underside(self):
        col, _ = plan_collision(self.plan)
        z0 = terrain_height(self.grid, 0.0, 0.0) - self.plan.frame.z_offset
        hit = ray_cast(col, (0.0, 0.0, z0 + 2.0), (0.0, 0.0, 1.0), 40.0)
        self.assertIsNotNone(hit)
        self.assertEqual(col.objects[hit.object]["mb_id"], self.bridge)
        self.assertAlmostEqual(z0 + 2.0 + hit.t, 15.0 + ROAD_LIFT_M - 1.0 - self.plan.frame.z_offset, delta=0.05)

    def test_terrain_is_unchanged_under_the_deck(self):
        bare, _, _ = make_scene([([(-100, 0), (-45, 0)], {"highway": "secondary"})], valley_height)
        a = objects(self.plan, "terrain")[0].mesh.vertices
        b = objects(bare, "terrain")[0].mesh.vertices
        self.assertEqual(a, b)

    def test_deterministic(self):
        again, _, _ = valley_scene()
        self.assertEqual(again.passage_probes, self.plan.passage_probes)
        self.assertEqual(objects(again, "bridge")[0].mesh.vertices, objects(self.plan, "bridge")[0].mesh.vertices)


def valley_scene_long(extra=(), joins=(), opts=None, half_len=60.0):
    """A bridge over the valley, ``2 * half_len`` m long, ending on at-grade roads."""
    ways = [([(-100, 0), (-half_len, 0)], {"highway": "secondary"}),
            ([(half_len, 0), (100, 0)], {"highway": "secondary"}),
            ([(-half_len, 0), (0, 0), (half_len, 0)], {"highway": "secondary", "bridge": "yes"})]
    return make_scene(ways + list(extra), valley_height, joins=[(2, 0, 0, 1), (2, 2, 1, 0)] + list(joins), opts=opts)


def shells(obj):
    """Vertex sets of the connected shells of the object's mesh, in world coordinates."""
    parent = list(range(len(obj.mesh.vertices)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for f in obj.mesh.faces:
        for a in f[1:]:
            parent[find(a)] = find(f[0])
    groups = {}
    for i, v in enumerate(obj.mesh.vertices):
        groups.setdefault(find(i), []).append(tuple(c + o for c, o in zip(v, obj.location)))
    return sorted(groups.values(), key=lambda g: min(p[0] for p in g))


def volume(obj, verts):
    inside = set(verts)
    vol = 0.0
    for f in obj.mesh.faces:
        pts = [tuple(c + o for c, o in zip(obj.mesh.vertices[i], obj.location)) for i in f]
        if pts[0] not in inside:
            continue
        for k in range(1, len(pts) - 1):
            a, b, c = pts[0], pts[k], pts[k + 1]
            vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                    + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return vol


class PierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.ids, cls.grid = valley_scene_long()
        cls.obj = objects(cls.plan, "bridge")[0]
        cls.parts = shells(cls.obj)
        cls.piers = cls.parts[1:-1]   # sorted by x: the deck spans the lot, so it sorts first by its min x

    def pier_shells(self, obj, parts):
        return [p for p in parts if max(q[0] for q in p) - min(q[0] for q in p) < 3.0]

    def test_two_closed_positive_shells_touching_the_underside(self):
        piers = self.pier_shells(self.obj, self.parts)
        self.assertEqual(len(self.parts), 3)
        self.assertEqual(len(piers), 2)
        col, _ = plan_collision(self.plan)
        zo = self.plan.frame.z_offset
        for p in piers:
            self.assertEqual(len(p), 8)
            self.assertGreater(volume(self.obj, p), 1.0)
            px = (min(q[0] for q in p) + max(q[0] for q in p)) / 2
            hit = ray_cast(col, (px, 3.9, 1.0 - zo), (0.0, 0.0, 1.0), 40.0)   # the deck underside beside the pier
            self.assertAlmostEqual(sum(sorted(q[2] for q in p)[-4:]) / 4, 1.0 - zo + hit.t, delta=0.01)
            low = sorted(p, key=lambda q: q[2])[:4]   # 1 m below the lowest ground under the footprint
            self.assertAlmostEqual(low[0][2] + zo, min(terrain_height(self.grid, q[0], q[1]) for q in low) - 1.0, delta=0.3)
            self.assertLess(low[0][2] + zo, min(terrain_height(self.grid, q[0], q[1]) for q in low))
            self.assertAlmostEqual(max(q[1] for q in p) - min(q[1] for q in p), 7.0, delta=1e-6)   # 8 m deck - 1 m
        for p, nominal in zip(piers, (-20.0, 20.0)):   # evenly spaced, shifted off a profile kink by at most 5 m
            self.assertLessEqual(abs((min(q[0] for q in p) + max(q[0] for q in p)) / 2 - nominal), 5.0)

    def test_triangle_budget_per_pier(self):
        again, _, _ = valley_scene_long(opts=PlanOptions(trees=False, scatter=False, bridge_piers=False))
        bare = objects(again, "bridge")[0]
        self.assertEqual(len(shells(bare)), 1)
        extra = sum(1 for _ in self.obj.mesh.triangles()) - sum(1 for _ in bare.mesh.triangles())
        self.assertEqual(extra, 2 * 12)

    def test_probes_pass_and_package_is_valid(self):
        self.assertEqual([p["id"] for p in self.plan.passage_probes], [f"{self.ids[2]}:deck", f"{self.ids[2]}:under"])
        self.assertNotIn("passage_probes_blocked", self.plan.report)
        with tempfile.TemporaryDirectory() as d:
            plan_to_package(self.plan, os.path.join(d, "p.mbmap"), "piers", synthetic_sources())
            v = validate_package(os.path.join(d, "p.mbmap"))
        self.assertTrue(v.ok, v.errors)
        self.assertEqual([w for w in v.warnings if "probe" in w], [])

    def test_pier_shifts_off_an_at_grade_road_ribbon(self):
        road = ([(20, -45), (20, 45)], {"highway": "residential"})
        plan, ids, _ = valley_scene_long(extra=[road])
        obj = objects(plan, "bridge")[0]
        piers = self.pier_shells(obj, shells(obj))
        self.assertEqual(len(piers), 2)
        hw = 3.0 * 0.5 + 0.5   # generous bound on a residential ribbon half width
        for p in piers:
            xs = [q[0] for q in p]
            self.assertTrue(min(xs) > 20.0 + hw - 1e-6 or max(xs) < 20.0 - hw + 1e-6, (min(xs), max(xs)))
        centers = [(min(q[0] for q in p) + max(q[0] for q in p)) / 2 for p in piers]
        self.assertLessEqual(centers[1] - centers[0], 40.0 + 1e-6)
        self.assertNotIn("passage_probes_blocked", plan.report)

    def test_graded_deck_pier_tops_follow_the_underside_at_every_corner(self):
        slope = lambda x, y: 0.06 * x + valley_height(x, y) - 15.0   # noqa: E731
        plan, ids, grid = make_scene([([(-100, 0), (-60, 0)], {"highway": "secondary"}),
                                      ([(60, 0), (100, 0)], {"highway": "secondary"}),
                                      ([(-60, 0), (0, 0), (60, 0)], {"highway": "secondary", "bridge": "yes"})],
                                     slope, joins=[(2, 0, 0, 1), (2, 2, 1, 0)])
        obj = objects(plan, "bridge")[0]
        piers = self.pier_shells(obj, shells(obj))
        self.assertEqual(len(piers), 2)
        col, _ = plan_collision(plan)
        zo = plan.frame.z_offset
        for p in piers:
            tops = sorted(p, key=lambda q: q[2])[-4:]
            self.assertGreater(max(q[2] for q in tops) - min(q[2] for q in tops), 0.05)   # a real grade
            for q in tops:
                hit = ray_cast(col, (q[0], 3.9, q[2] - 6.0), (0.0, 0.0, 1.0), 20.0)   # the deck beside the pier
                self.assertAlmostEqual(q[2], q[2] - 6.0 + hit.t, delta=0.001)

    def test_parapets_cost_at_most_4_triangles_per_sample_each(self):
        plan, _, _ = valley_scene_long(opts=PlanOptions(trees=False, scatter=False, bridge_piers=False))
        obj = objects(plan, "bridge")[0]
        tri = sum(1 for _ in obj.mesh.triangles())
        nodes = (len(obj.mesh.faces) - 6) // 8 + 1   # 8 side quads per interval + 3 quads per end cap
        slab = 8 * (nodes - 1) + 4   # the same deck without parapets
        self.assertEqual(tri, 16 * (nodes - 1) + 12)
        self.assertLessEqual(tri - slab, 2 * 4 * nodes)

    def test_pier_keeps_3_m_from_the_under_probe(self):
        plan, ids, _ = valley_scene_long(half_len=40.0)   # 80 m: one pier, nominally right under the probe
        obj = objects(plan, "bridge")[0]
        piers = self.pier_shells(obj, shells(obj))
        under = next(p for p in plan.passage_probes if p["id"].endswith(":under"))
        px = under["path_map"][0][0]
        self.assertEqual(len(piers), 1)
        self.assertGreaterEqual(min(abs(q[0] - px) for q in piers[0]), 3.0)
        self.assertNotIn("passage_probes_blocked", plan.report)

    def test_ray_along_the_deck_edge_hits_the_parapet(self):
        col, _ = plan_collision(self.plan)
        zo = self.plan.frame.z_offset
        z = 15.0 + ROAD_LIFT_M + 0.5 - zo
        hit = ray_cast(col, (-80.0, 3.85, z), (1.0, 0.0, 0.0), 40.0)
        self.assertIsNotNone(hit)
        self.assertEqual(col.objects[hit.object]["mb_id"], self.ids[2])
        self.assertAlmostEqual(-80.0 + hit.t, -60.5, delta=0.01)

    def test_short_low_bridge_has_no_piers(self):
        plan, _, _ = valley_scene()
        self.assertEqual(len(shells(objects(plan, "bridge")[0])), 1 + len(
            self.pier_shells(objects(plan, "bridge")[0], shells(objects(plan, "bridge")[0]))))


class CrossingTest(unittest.TestCase):
    JOINS = [(3, 0, 0, 1), (3, 1, 1, 0)]   # the deck (way 3) ends on the two approach roads' end nodes
    ROADS = [([(-240, 0), (-100, 0)], {"highway": "residential"}), ([(100, 0), (240, 0)], {"highway": "residential"}),
             ([(0, -45), (0, 45)], {"highway": "residential"})]

    def test_layer_clearance_over_a_crossing_road_with_limited_grade(self):
        plan, ids, _ = make_scene(
            self.ROADS + [([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})],
            lambda x, y: 0.0, width=500.0, joins=self.JOINS)
        deck = objects(plan, "bridge")[0]
        self.assertIn("raised", deck.provenance["profile"])
        self.assertTrue(deck.provenance["clearance_met"])
        deck_probe = next(p for p in plan.passage_probes if p["id"].endswith(":deck"))
        pts = deck_probe["path_map"]
        for a, b in zip(pts, pts[1:]):
            self.assertLessEqual(abs(b[2] - a[2]) / math.hypot(b[0] - a[0], b[1] - a[1]), MAX_GRADE + 1e-6)
        col, _ = plan_collision(plan)
        road_z = ROAD_LIFT_M - plan.frame.z_offset
        hit = ray_cast(col, (0.0, 0.0, road_z + 0.5), (0.0, 0.0, 1.0), 30.0)
        self.assertEqual(col.objects[hit.object]["mb_id"], ids[3])
        self.assertGreaterEqual(0.5 + hit.t, 5.0 - 1e-6)
        under = next(p for p in plan.passage_probes if p["id"].endswith(":under"))
        self.assertAlmostEqual(under["path_map"][0][0], 0.0, delta=6.0)   # across the span near its middle
        self.assertEqual(plan.report.get("passage_probes_blocked"), None)

    def test_a_span_too_short_for_the_clearance_is_reported_not_claimed(self):
        plan, ids, _ = make_scene(
            self.ROADS[:2] + [([(-40, 0), (40, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})],
            lambda x, y: 0.0, width=500.0)
        prov = objects(plan, "bridge")[0].provenance
        self.assertFalse(prov["clearance_met"])
        self.assertLess(prov["clearance_m"], 5.0)
        self.assertIn("NOT met", prov["profile"])
        self.assertTrue(any(ids[2] in w and "clearance" in w for w in plan.report["warnings"]))
        self.assertNotIn(f"{ids[2]}:under", [p["id"] for p in plan.passage_probes])   # under 4 m: no under probe

    def test_clearance_is_judged_at_an_off_centre_crossing_not_at_the_best_sample(self):
        side = ([(-75, -45), (-75, 45)], {"highway": "residential"})   # 25 m from the end: cannot rise 5 m
        plan, ids, _ = make_scene(
            self.ROADS[:2] + [side, ([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})],
            lambda x, y: 0.0, width=500.0, joins=self.JOINS)
        prov = objects(plan, "bridge")[0].provenance
        self.assertIs(prov["clearance_met"], False)
        self.assertLess(prov["clearance_m"], 2.5)
        self.assertTrue(any(ids[3] in w and "crossing road" in w and ids[2] in w for w in plan.report["warnings"]))

    def test_clearance_holds_over_the_whole_crossing_ribbon_not_just_its_centreline(self):
        # a 3 m ground ridge at the edge of the crossing road's ribbon (x = 5): the centreline has more than 5 m
        # but the deck underside is under 5 m above the ridge, which the grade limit cannot cure
        road = ([(0, -45), (0, 45)], {"highway": "primary"})
        plan, ids, _ = make_scene(
            self.ROADS[:2] + [road, ([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})],
            lambda x, y: 3.0 if abs(x - 5.0) < 0.1 else 0.0, width=500.0, joins=self.JOINS)
        prov = objects(plan, "bridge")[0].provenance
        col, _ = plan_collision(plan)
        edge_z = 3.0 + ROAD_LIFT_M - plan.frame.z_offset
        hit = ray_cast(col, (5.0, 0.0, edge_z), (0.0, 0.0, 1.0), 30.0)
        self.assertEqual(col.objects[hit.object]["mb_id"], ids[3])
        self.assertLess(hit.t, 5.0 - 0.5)   # the edge really is below the wanted clearance
        self.assertIs(prov["clearance_met"], False)
        self.assertLess(prov["clearance_m"], 5.0 - 0.5)
        self.assertTrue(any(ids[3] in w and "crossing road" in w and "clearance" in w for w in plan.report["warnings"]))

    def _end_crossing(self, x):
        roads = [([(-240, 0), (-100, 0)], {"highway": "residential"}), ([(100, 0), (240, 0)], {"highway": "residential"}),
                 ([(x, -45), (x, 45)], {"highway": "residential", "width": "1"})]
        plan, ids, _ = make_scene(
            roads + [([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})],
            lambda x, y: 0.0, width=500.0)
        col, _ = plan_collision(plan)
        return objects(plan, "bridge")[0].provenance, col

    def test_an_unrelated_road_crossing_near_the_deck_end_is_checked(self):
        prov, col = self._end_crossing(98.0)   # 2 m from the end: inside the old fixed end zone
        self.assertLess(prov["clearance_m"], 0.0)   # the deck underside is below that road (rays start inside the deck)
        self.assertIs(prov["clearance_met"], False)

    def test_an_unrelated_road_crossing_at_the_exact_deck_end_is_checked(self):
        prov, col = self._end_crossing(100.0)
        self.assertIs(prov["clearance_met"], False)
        self.assertLess(prov["clearance_m"], 0.0)

    @staticmethod
    def _valley_bridge(side_x):
        return make_scene([([(-100, 0), (100, 0)], {"highway": "secondary", "bridge": "yes"}),
                           ([(side_x, -45), (side_x, 45)], {"highway": "residential"})],
                          valley_height, width=300.0)

    def test_a_road_meeting_an_unsplit_approach_gives_no_clearance_warning(self):
        plan, ids, _ = self._valley_bridge(-60)   # on the plateau, short of the valley: the approach run
        prov = objects(plan, "bridge")[0].provenance
        self.assertEqual([w for w in plan.report["warnings"] if "clearance" in w], [])
        self.assertIsNot(prov["clearance_met"], False)
        self.assertIn(f"{ids[0]}:under", [p["id"] for p in plan.passage_probes])

    def test_a_low_middle_span_still_warns(self):
        plan, ids, _ = make_scene(
            [([(-40, 0), (40, 0)], {"highway": "secondary", "bridge": "yes"}),
             ([(0, -45), (0, 45)], {"highway": "residential"})],
            lambda x, y: 0.0, width=300.0)   # never 5 m over the ground: no approach run to exempt
        self.assertIs(objects(plan, "bridge")[0].provenance["clearance_met"], False)
        self.assertTrue(any(ids[0] in w and "crossing road" in w and "clearance" in w
                            for w in plan.report["warnings"]))

    def test_connected_approach_roads_give_no_false_low_clearance(self):
        plan, ids, _ = make_scene(
            self.ROADS + [([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})],
            lambda x, y: 0.0, width=500.0, joins=[(3, 0, 0, 1), (3, 1, 1, 0)])
        prov = objects(plan, "bridge")[0].provenance
        self.assertIs(prov["clearance_met"], True)
        self.assertGreaterEqual(prov["clearance_m"], 5.0 - 1e-6)

    def test_a_road_near_the_deck_end_with_its_own_node_is_not_exempt(self):
        # perpendicular road at x=-99.7 with a centre vertex of its own node id: proximity must not exempt it
        roads = [([(-99.7, -45), (-99.7, 0), (-99.7, 45)], {"highway": "residential"}),
                 ([(100, 0), (240, 0)], {"highway": "residential"})]
        plan, ids, _ = make_scene(
            roads + [([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})],
            lambda x, y: 0.0, width=500.0, joins=[(2, 1, 1, 0)])
        prov = objects(plan, "bridge")[0].provenance
        self.assertIs(prov["clearance_met"], False)
        self.assertLess(prov["clearance_m"], 5.0)
        self.assertEqual(prov["start_joint"], "free end: terrain + road lift")   # shares no node: not a joint
        self.assertIn(ids[1], prov["end_joint"])
        self.assertFalse(any("joins" in w for w in plan.report["warnings"]))

    def _fork(self, branch_end):
        roads = [([(-140, 0), (-100, 0)], {"highway": "residential", "width": "0.5"}),
                 ([(-100, 0), branch_end], {"highway": "service", "width": "8"}),
                 ([(100, 0), (240, 0)], {"highway": "residential"})]
        plan, ids, _ = make_scene(
            [([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})] + roads,
            lambda x, y: 0.0, width=500.0, joins=[(0, 0, 1, 1), (0, 0, 2, 0), (0, 1, 3, 0)])
        return objects(plan, "bridge")[0].provenance, plan, ids

    def test_only_the_straight_approach_is_exempt_at_a_fork(self):
        prov, plan, ids = self._fork((-120, 25))   # a straight approach and a 51 degree branch at the same node
        self.assertIs(prov["clearance_met"], False)
        self.assertAlmostEqual(prov["clearance_m"], -1.0, delta=0.05)
        self.assertTrue(any(ids[2] in w for w in plan.report["warnings"]))

    def test_two_near_equal_continuations_are_ambiguous_and_neither_is_exempt(self):
        prov, plan, ids = self._fork((-140, 3))   # about 4 degrees apart from the straight approach
        self.assertIs(prov["clearance_met"], False)

    def test_shared_endpoint_node_ids_survive_clipping_by_index(self):
        area = Area(47.0, 8.0, 400.0, 200.0)
        b = OsmBuilder(area.frame)
        a, mid, c = b.node(-140.1, 0), b.node(-0.1, 0), b.node(100, 0)
        for nids, tags in (([a, mid], {"highway": "residential"}), ([mid, c], {"highway": "residential", "bridge": "yes"})):
            b.ways.append((b._next(), nids, tags))
        cl = classify(parse_osm_xml(b.xml().encode()), area)
        self.assertEqual(cl.roads[0].node_ids[-1], mid)
        self.assertEqual(cl.structure_bridges[0].node_ids[0], mid)
        self.assertEqual(cl.structure_bridges[0].node_ids[-1], c)

    def test_a_duplicated_first_deck_vertex_does_not_exempt_an_inward_road(self):
        # the raw first segment has zero length; the end direction must come from the next distinct vertex
        roads = [([(-100, 0), (-60, 0)], {"highway": "residential", "width": "8"}),   # leaves the deck end inward
                 ([(100, 0), (240, 0)], {"highway": "residential"})]
        plan, ids, _ = make_scene(
            [([(-100, 0), (-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})] + roads,
            lambda x, y: 0.0, width=500.0, joins=[(0, 0, 1, 0), (0, 2, 2, 0)])
        prov = objects(plan, "bridge")[0].provenance
        self.assertIs(prov["clearance_met"], False)
        self.assertAlmostEqual(prov["clearance_m"], -1.0, delta=0.05)

    @staticmethod
    def _approach(roads, deck_geo, deck_nodes):
        """_approach_segments on hand-made features, with the deck ends taken from the swept (deduplicated) path."""
        from map_builder.core import generate as gen
        feat = lambda fid, geo, nids: types.SimpleNamespace(id=fid, geometry=geo, node_ids=nids,   # noqa: E731
                                                            tags={"highway": "residential"})
        kept = gen._dedupe_indices(deck_geo)
        pts = [deck_geo[k] for k in kept]
        nodes = bridges._end_nodes(deck_nodes)
        ends = [(nodes[0], pts[0], pts[1]), (nodes[1], pts[-1], pts[-2])]
        g = types.SimpleNamespace(road_width=lambda tags: (4.0, "x"), POLYLINE_DEDUP_TOL_M=gen.POLYLINE_DEDUP_TOL_M)
        return bridges._approach_segments([feat(*r) for r in roads], [r[0] for r in roads], ends, g)

    def test_duplicate_vertices_never_give_a_zero_direction(self):
        inward = ("in", [(60, 0), (100, 0), (100, 0)], [1, 2, 3])   # duplicated vertex at the shared node
        outward = ("out", [(100, 0), (100, 0), (140, 0)], [3, 4, 5])
        got = self._approach([inward, outward], [(-100, 0), (100, 0), (100, 0)], [9, 8, 3])
        self.assertEqual(list(got), ["out"])   # only the outward continuation; the inward road is not exempt
        self.assertEqual(got["out"][0][1], (140, 0))   # its direction skips the duplicated vertex
        clean = ([(-100, 0), (100, 0)], [9, 3])
        self.assertEqual(self._approach([inward], *clean), {})   # road-side duplicate only
        self.assertEqual(list(self._approach([outward], *clean)), ["out"])   # still found

    def test_an_interior_node_merged_into_the_end_is_not_the_end_node(self):
        # deck vertex 1 (node 3) is within the sweep's tolerance of the start, so it is swept away; it is still an
        # interior node of the way, and a road that ends there is not an approach
        side = ("side", [(-100, 0), (-100, -40)], [3, 4])
        deck = [(-100, 0), (-100, 5e-4), (100, 0)]
        self.assertEqual(self._approach([side], deck, [9, 3, 8]), {})
        out = ("out", [(-100, 0), (-140, 0)], [3, 4])
        self.assertEqual(list(self._approach([out], deck, [3, 9, 8])), ["out"])   # the true end node: control
        through = ("through", [(-140, 0), (-100, 0), (-60, 0)], [1, 3, 2])   # node 3 is interior to the road
        self.assertEqual(self._approach([through], [(-100, 0), (100, 0)], [3, 8]), {})

    def test_an_interior_deck_node_is_not_a_joint_in_the_scene(self):
        plan, ids, _ = make_scene(
            [([(-100, 0), (-100, 5e-4), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"}),
             ([(-100, 0), (-140, 0)], {"highway": "residential", "width": "8"})],
            lambda x, y: 0.0, width=500.0, joins=[(0, 1, 1, 0)])
        prov = objects(plan, "bridge")[0].provenance
        self.assertIs(prov["clearance_met"], False)
        self.assertLess(prov["clearance_m"], 0.0)

    def test_the_duplicate_tolerance_is_the_sweeps(self):
        # a deck whose second vertex sits `off` m sideways of the first: the sweep drops it below its tolerance
        # (the deck then leaves along +x, so a road leaving along -y is a side branch), keeps it above (the deck
        # then leaves along +y, so that road is the straight continuation)
        from map_builder.core.generate import POLYLINE_DEDUP_TOL_M as tol
        side = ("side", [(-100, 0), (-100, -40)], [3, 4])
        for off in (1e-5, 1e-4, 5e-4, 0.9 * tol, 1.1 * tol, 2e-3, 1e-2):
            got = self._approach([side], [(-100, 0), (-100, off), (100, 0)], [3, 8, 9])
            self.assertEqual(list(got), ["side"] if off > tol else [], off)

    def test_a_half_millimetre_duplicate_deck_vertex_does_not_exempt_a_side_branch(self):
        roads = [([(-100, 0), (-100, -40)], {"highway": "residential", "width": "8"}),
                 ([(100, 0), (240, 0)], {"highway": "residential"})]
        plan, ids, _ = make_scene(
            [([(-100, 0), (-100, 5e-4), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})]
            + roads, lambda x, y: 0.0, width=500.0, joins=[(0, 0, 1, 0), (0, 2, 2, 0)])
        prov = objects(plan, "bridge")[0].provenance
        self.assertIs(prov["clearance_met"], False)
        self.assertLess(prov["clearance_m"], 0.0)

    def test_a_perpendicular_segment_at_the_shared_node_is_not_exempt(self):
        # the road shares the deck's end node but turns 90 degrees there: only the outward continuation is exempt
        roads = [([(-240, 0), (-100, 0), (-100, 40)], {"highway": "residential"}),
                 ([(100, 0), (240, 0)], {"highway": "residential"})]
        plan, ids, _ = make_scene(
            roads + [([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})],
            lambda x, y: 0.0, width=500.0, joins=[(2, 0, 0, 1), (2, 1, 1, 0)])
        self.assertIs(objects(plan, "bridge")[0].provenance["clearance_met"], False)

    def _ray_clearance(self, plan, ids, step=2.8):
        """Lowest deck-underside-to-road-surface distance over the footprints, by rays on the exported meshes."""
        col, _ = plan_collision(plan)
        low = None
        for i in range(-3, 4):
            for j in range(-1, 2):
                x, y = i * step, j * step
                top = ray_cast(col, (x, y, 40.0), (0, 0, -1), 80.0)
                if top is None or col.objects[top.object]["mb_id"] != ids[3]:
                    continue
                z = 40.0 - top.t - 0.5
                under = ray_cast(col, (x, y, z), (0, 0, -1), 80.0)
                z -= under.t + 0.02
                road = ray_cast(col, (x, y, z), (0, 0, -1), 80.0)
                if road is None or col.objects[road.object]["mb_id"] != ids[2]:
                    continue
                low = road.t + 0.02 if low is None else min(low, road.t + 0.02)
        return low

    def test_clearance_over_a_road_at_45_degrees_agrees_with_rays_on_the_exported_meshes(self):
        c = math.cos(math.radians(45))
        road = ([(-45 * c, -45 * c), (45 * c, 45 * c)], {"highway": "primary"})
        for ground in (lambda x, y: 0.0, lambda x, y: 0.1 * y):   # flat; and rising across the deck
            plan, ids, _ = make_scene(
                [([(-125, 0), (-100, 0)], {"highway": "residential"}), ([(100, 0), (125, 0)], {"highway": "residential"}), road, ([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes",
                                                                 "layer": "1"})], ground, width=260.0, joins=self.JOINS)
            prov = objects(plan, "bridge")[0].provenance
            measured = self._ray_clearance(plan, ids)
            self.assertIsNotNone(measured)
            self.assertAlmostEqual(prov["clearance_m"], measured, delta=0.03)
            self.assertIs(prov["clearance_met"], measured >= 5.0 - 0.03)

    def _ray_gap(self, col, x, y, z):
        up = ray_cast(col, (x, y, z), (0, 0, 1), 30)
        down = ray_cast(col, (x, y, z), (0, 0, -1), 30)
        return up.t + down.t

    def test_clearance_is_exact_at_the_corner_of_a_45_degree_overlap(self):
        # the reviewer's case: flat ground, 10 m road at 45 degrees; the lowest point is a corner of the overlap
        road = ([(-51.5, -35), (18.5, 35)], {"highway": "residential", "width": "10"})
        deck = ([(-100, 0), (100, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})
        plan, ids, _ = make_scene([deck, road], lambda x, y: 0.0, width=300.0)
        prov = objects(plan, "bridge")[0].provenance
        half = prov["width_m"] / 2.0
        col, _ = plan_collision(plan)
        gaps = []
        for sy in (-1.0, 1.0):
            for k in (-1.0, 1.0):
                y = sy * (half - 0.02)
                x = y - 16.5 + k * 5.0 * math.sqrt(2.0) * (1.0 - 0.01)
                gaps.append(self._ray_gap(col, x, y, 0.22))
        self.assertAlmostEqual(prov["clearance_m"], min(gaps), delta=0.01)
        self.assertIs(prov["clearance_met"], False)

    def test_an_interior_ridge_under_a_wide_crossing_is_not_missed(self):
        # a 3 m terrain ridge at x = 5 inside a 20 m wide crossing: between the corner and edge samples
        plan, ids, _ = make_scene(
            [([(-120, 0), (120, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"}),
             ([(0, -35), (0, 35)], {"highway": "residential", "width": "20"})],
            lambda x, y: 3.0 if abs(x - 5.0) < 0.1 else 0.0, width=300.0)
        prov = objects(plan, "bridge")[0].provenance
        col, _ = plan_collision(plan)
        self.assertAlmostEqual(prov["clearance_m"], self._ray_gap(col, 5.0, 0.0, 3.22), delta=0.01)
        self.assertIs(prov["clearance_met"], False)

    def test_the_pair_enumeration_stops_at_the_production_cap_before_any_clipping(self):
        # a 560 m deck of 7000 vertices (14000 underside triangles) over a wide road: the bbox pairs exceed
        # the production cap; the error comes before anything is clipped and with at most cap + 1 pairs held
        n = 7000
        deck = ([(-280 + 560 * i / n, 0.0) for i in range(n + 1)], {"highway": "residential", "bridge": "yes"})
        road = ([(-290, -30), (290, 30)], {"highway": "service", "width": "20"})
        with mock.patch.object(bridges, "_clip", wraps=bridges._clip) as clip:
            with self.assertRaises(LimitError) as ctx:
                make_scene([deck, road], lambda x, y: 0.0, width=700.0, height=100.0)
        self.assertEqual(clip.call_count, 0)
        held = int(re.search(r"stopped at (\d+)", str(ctx.exception)).group(1))
        self.assertEqual(held, bridges.MAX_TRIANGLE_PAIRS + 1)

    def _mitre_case(self, deck_pts, road_pts):
        """The deck's provenance clearance and the lowest ray gap over the road's footprint (its ends and edges)."""
        plan, ids, _ = make_scene(
            [(deck_pts, {"highway": "residential", "bridge": "yes", "layer": "1"}),
             (road_pts, {"highway": "service", "width": "0.5"})], lambda x, y: 0.0, width=300.0, height=240.0)
        prov = objects(plan, "bridge")[0].provenance
        col, _ = plan_collision(plan)
        (x0, y0), (x1, y1) = road_pts
        gaps = [self._ray_gap(col, x0 + (x1 - x0) * u + dy * 0.2, y0 + (y1 - y0) * u + dy * 0.0, 0.22)
                for u in (0.02, 0.5, 0.98) for dy in (-1.0, 0.0, 1.0)]
        return prov, min(gaps)

    def test_a_road_in_the_outer_wedge_of_a_45_degree_mitre_is_checked(self):
        # the reviewer's case: no deck segment rectangle covers the wedge, the exported mitre does
        prov, gap = self._mitre_case([(-60, 0), (0, 0), (80, 80)], [(0.4, -2.7), (1.0, -2.7)])
        self.assertAlmostEqual(prov["clearance_m"], gap, delta=0.01)
        self.assertIs(prov["clearance_met"], False)

    def test_a_road_in_the_outer_wedge_of_the_sharpest_mitre_is_checked(self):
        # 60 degrees is the largest turn the sweep builds in one joint
        prov, gap = self._mitre_case([(-60, 0), (0, 0), (30, 51)], [(0.4, -2.7), (1.0, -2.7)])
        self.assertAlmostEqual(prov["clearance_m"], gap, delta=0.01)
        self.assertIs(prov["clearance_met"], False)

    def _crossing_case(self, angle_deg, road_w, reach=150.0):
        a = math.radians(angle_deg)
        d = 160.0
        road = ([(-d * math.cos(a), -d * math.sin(a)), (d * math.cos(a), d * math.sin(a))],
                {"highway": "residential", "width": str(road_w)})
        deck = ([(-reach, 0), (reach, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})
        plan, ids, _ = make_scene([deck, road], lambda x, y: 0.0, width=400.0)
        return plan, objects(plan, "bridge")[0].provenance

    def _first_overlap_gap(self, plan, prov, deg, road_w):
        # ray gap at the first point where the road ribbon enters the deck footprint, where the deck is lowest
        half, th = prov["width_m"] / 2.0, math.radians(deg)
        x = (-half - road_w / 2.0 / math.cos(th)) / math.tan(th) + 0.02
        col, _ = plan_collision(plan)
        return self._ray_gap(col, x, -half + 0.0005, 0.22)

    def test_a_shallow_crossing_is_not_certified_by_a_clamped_overlap(self):
        # the reviewer's case: a 1 m road at ~1.72 degrees under a 300 m deck (rays at (-108, -2.8) measure 2.36 m,
        # but the deck is lower where the ribbon first enters its footprint)
        deg = math.degrees(math.atan2(4.8, 160.0))
        plan, ids, _ = make_scene([
            ([(-150, 0), (150, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"}),
            ([(-160, -4.8), (160, 4.8)], {"highway": "residential", "width": "1"})],
            lambda x, y: 0.0, width=400)
        prov = objects(plan, "bridge")[0].provenance
        self.assertAlmostEqual(prov["clearance_m"], self._first_overlap_gap(plan, prov, deg, 1.0), delta=0.01)
        self.assertLess(prov["clearance_m"], 2.0)
        self.assertIs(prov["clearance_met"], False)

    def test_a_road_directly_under_the_deck_along_its_length(self):
        plan, prov = self._crossing_case(0.0, 6)
        col, _ = plan_collision(plan)
        # an unrelated road counts wherever it lies: it runs under the deck's sunk end, below the 0.16 m gap
        # the rays still measure 2 m in from the end (the deck rises 8 % from there)
        self.assertLessEqual(prov["clearance_m"], 0.0)
        self.assertLess(prov["clearance_m"], self._ray_gap(col, -148.0, 0.0, 0.22))
        self.assertIs(prov["clearance_met"], False)

    def test_a_three_degree_crossing_agrees_with_rays(self):
        plan, prov = self._crossing_case(3.0, 4)
        self.assertAlmostEqual(prov["clearance_m"], self._first_overlap_gap(plan, prov, 3.0, 4), delta=0.01)
        self.assertIs(prov["clearance_met"], False)

    def test_a_span_with_no_interior_sample_is_unverified_not_successful(self):
        plan, ids, _ = make_scene([([(-4, 0), (4, 0)], {"highway": "residential", "bridge": "yes", "layer": "1"})],
                                  lambda x, y: 0.0)
        prov = objects(plan, "bridge")[0].provenance
        self.assertIsNone(prov["clearance_met"])
        self.assertNotIn("clearance_m", prov)
        self.assertTrue(any(ids[0] in w and "could not be verified" in w for w in plan.report["warnings"]))

    def test_a_sloped_baseline_keeps_the_deck_grade_within_8_percent(self):
        def hill(x, y):   # a 4 % slope with a 1.5 m hump under the middle of the span
            return 0.04 * x + max(0.0, 1.5 - abs(x) * 0.02)
        plan, ids, _ = make_scene(
            [([(-320, 0), (-200, 0)], {"highway": "residential"}), ([(200, 0), (320, 0)], {"highway": "residential"}),
             ([(-200, 0), (200, 0)], {"highway": "residential", "bridge": "yes"})], hill, width=700.0)
        deck = objects(plan, "bridge")[0]
        self.assertLessEqual(deck.provenance["max_grade_pct"], 8.0)
        pts = next(p for p in plan.passage_probes if p["id"].endswith(":deck"))["path_map"]
        for a, b in zip(pts, pts[1:]):
            self.assertLessEqual(abs(b[2] - a[2]) / math.hypot(b[0] - a[0], b[1] - a[1]), MAX_GRADE + 1e-6)


class TreeTest(unittest.TestCase):
    def test_mapped_tree_beside_the_span_blocks_the_under_probe(self):
        plan, ids, _ = make_scene(
            [([(-100, 0), (-45, 0)], {"highway": "secondary"}), ([(45, 0), (100, 0)], {"highway": "secondary"}),
             ([(-45, 0), (0, 0), (45, 0)], {"highway": "secondary", "bridge": "yes"})],
            valley_height, trees=[(0, 8)])
        under = f"{ids[2]}:under"
        self.assertNotIn(under, [p["id"] for p in plan.passage_probes])
        blocked = {e["id"]: e["blocker"] for e in plan.report["passage_probes_blocked"]}
        self.assertEqual(blocked[under], ids[3])

    def test_mapped_tree_inside_the_deck_footprint_is_not_placed(self):
        plan, ids, _ = make_scene(
            [([(-100, 0), (-45, 0)], {"highway": "secondary"}), ([(45, 0), (100, 0)], {"highway": "secondary"}),
             ([(-45, 0), (0, 0), (45, 0)], {"highway": "secondary", "bridge": "yes"})],
            valley_height, trees=[(0, 2)])
        self.assertEqual(objects(plan, "vegetation"), [])
        self.assertTrue(any(e["id"] == ids[3] and "deck footprint" in e["reason"]
                            for e in plan.report["invalid_features"]))
        self.assertNotIn("passage_probes_blocked", plan.report)


class SharedProbesTest(unittest.TestCase):
    ELEV, TUNNEL = "elev:probe", "tunnel:probe"

    def _mixed(self, ways, budget=None, cap=None):
        """A scene of bridges whose finalisation also sees one ELEV and one tunnel probe (staged like their
        stages do: the ELEV one before the bridges, the tunnel one after), with the work budget and the cap
        optionally replaced. Returns ``(plan, ids)``."""
        from map_builder.core import passages, structures
        orig = bridges.build

        def build(plan, ctx):
            orig(plan, ctx)
            tpl = ctx.probes[0]
            elev = dict(tpl, id=self.ELEV, kind="elevated", path_map=[[x, y + 20.0, z] for x, y, z in tpl["path_map"]])
            plan.passage_probes.insert(0, elev)
            passages._state(ctx).probes.append(self.ELEV)
            ctx.probes.append(dict(tpl, id=self.TUNNEL, kind="tunnel",
                                   path_map=[[x, y + 20.0, z] for x, y, z in tpl["path_map"]]))
        patches = [mock.patch.object(bridges, "build", build)]
        if budget is not None:
            patches.append(mock.patch.object(structures, "WorkBudget", lambda: budget))
        if cap is not None:
            from map_builder.core import package
            patches.append(mock.patch.object(package, "PASSAGE_PROBE_MAX", cap))
        for pt in patches:
            pt.start()
        try:
            plan, ids, _ = make_scene(ways, lambda x, y: 0.0, width=300.0, height=500.0)
        finally:
            for pt in patches:
                pt.stop()
        return plan, ids

    WAYS = [([(-100, y), (100, y)], {"highway": "residential", "bridge": "yes"}) for y in range(-160, 161, 80)]

    def test_bridge_probes_draw_from_the_one_shared_work_budget(self):
        from map_builder.core import structures
        everything = structures.WorkBudget(10 ** 9)
        plan, ids = self._mixed(self.WAYS, budget=everything)
        cost = 10 ** 9 - everything.left
        staged = sorted(p["id"] for p in plan.passage_probes)
        self.assertEqual(plan.report.get("passage_probes_blocked", []), [])
        self.assertTrue(self.ELEV in staged and self.TUNNEL in staged and any(s.endswith(":deck") for s in staged))
        small = structures.WorkBudget(int(cost * 0.6))   # not enough for every probe of every kind
        plan, ids = self._mixed(self.WAYS, budget=small)
        unchecked = [e["id"] for e in plan.report["passage_probes_blocked"] if e.get("reason") == "budget_exhausted"]
        kept = [p["id"] for p in plan.passage_probes]
        self.assertEqual(sorted(kept + unchecked), staged)   # every probe is either checked or reported, none lost
        self.assertTrue(any(u.endswith((":deck", ":under")) for u in unchecked))   # bridge probes ran dry
        self.assertIn(self.TUNNEL, unchecked)                  # the last in plan order
        self.assertIn(self.ELEV, kept)                         # the first in plan order was checked
        self.assertLessEqual(small.left, 0)                    # a failed call is debited: nothing left over

    def test_bridge_probes_fall_under_the_global_cap_in_plan_order(self):
        full, ids = self._mixed(self.WAYS)
        order = [p["id"] for p in full.passage_probes]   # ELEV, the bridges' probes in plan order, the tunnel
        self.assertEqual((order[0], order[-1]), (self.ELEV, self.TUNNEL))
        plan, _ = self._mixed(self.WAYS, cap=3)
        self.assertEqual([p["id"] for p in plan.passage_probes], order[:3])
        self.assertEqual([e["id"] for e in plan.report["passage_probes_dropped"]], order[3:])
        self.assertNotIn("passage_probes_blocked", plan.report)

    def test_many_decks_all_get_checked_and_kept(self):
        ways = [([(-100, y), (100, y)], {"highway": "residential", "bridge": "yes"}) for y in range(-200, 200, 40)]
        plan, ids, _ = make_scene(ways, lambda x, y: 0.0, width=300.0, height=500.0)
        self.assertEqual(len(objects(plan, "bridge")), len(ways))
        self.assertEqual({p["id"] for p in plan.passage_probes if p["id"].endswith(":deck")},
                         {f"{i}:deck" for i in ids})
        self.assertNotIn("passage_probes_blocked", plan.report)


class InvalidAndBlockedTest(unittest.TestCase):
    def flat(self, ways):
        return make_scene(ways, lambda x, y: 0.0)

    def test_degenerate_bridges_are_reported_invalid(self):
        plan, ids, _ = self.flat([([(0, 0), (1, 0)], {"highway": "service", "bridge": "yes"}),
                                  ([(-60, 20), (0, 20), (0, 60)], {"highway": "service", "bridge": "yes"})])
        self.assertEqual(objects(plan, "bridge"), [])
        reasons = {e["id"]: e["reason"] for e in plan.report["invalid_features"]}
        self.assertIn("shorter than", reasons[ids[0]])
        self.assertIn("turns by more than", reasons[ids[1]])

    def test_other_bridges_stay_unsupported(self):
        plan, ids, _ = self.flat([([(-60, 20), (60, 20)], {"railway": "rail", "bridge": "yes"}),
                                  ([(-60, 30), (60, 30)], {"highway": "service", "man_made": "bridge",
                                                           "bridge": "yes"})])
        self.assertEqual(objects(plan, "bridge"), [])
        self.assertEqual({e["id"] for e in plan.report["unsupported_features"]}, set(ids))

    def test_blocked_probe_is_reported_not_emitted(self):
        b = OsmBuilder()
        area = Area(47.0, 8.0, W, H)
        b = OsmBuilder(area.frame)
        bridge = f"osm:way/{b.way([(-60, 0), (60, 0)], {'highway': 'service', 'bridge': 'yes'})}"
        tower = f"osm:way/{b.way([(-5, -5), (5, -5), (5, 5), (-5, 5)], {'building': 'yes', 'height': '40'}, closed=True)}"
        cl = classify(parse_osm_xml(b.xml().encode()), area)
        nx, ny = int(W / SPACING) + 1, int(H / SPACING) + 1
        grid = ElevationGrid(-W / 2, -H / 2, SPACING, nx, ny, [[0.0] * nx for _ in range(ny)], {"provider": "test"})
        plan = build_plan(area, grid, cl, PlanOptions(trees=False, scatter=False))
        blocked = {e["id"]: e["blocker"] for e in plan.report["passage_probes_blocked"]}
        self.assertEqual(blocked[f"{bridge}:deck"], tower)
        self.assertNotIn(f"{bridge}:deck", [p["id"] for p in plan.passage_probes])


class FixtureTest(unittest.TestCase):
    def test_fixture_footway_bridge_is_generated(self):
        area, grid, cl, ids, _ = synthetic_inputs(tempfile.mkdtemp())
        plan = build_plan(area, grid, cl)
        mb = f"osm:way/{ids['bridge']}"
        self.assertEqual([o.mb_id for o in objects(plan, "bridge")], [mb])
        self.assertIn(f"{mb}:deck", [p["id"] for p in plan.passage_probes])


if __name__ == "__main__":
    unittest.main()
