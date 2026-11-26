# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Shore ramps (S4-COL-FLOAT-2): the flat water sheet does not hover over its bank. Synthetic scenes only."""
from __future__ import annotations

import unittest

from map_builder.core import shore
from map_builder.core.deck_underside import DeckUnderside, trim_under_decks
from map_builder.core.osm import point_in_ring
from map_builder.core.overlap import convex_intersection, polygon_area, triangle_overlaps_region, triangle_touches
from map_builder.core.query import ray_cast
from map_builder.core.structures import plan_collision, sweep_footprint

from .test_bridges import make_scene
from .test_water import H, W, lake_ground, lake_scene

SHEET = 10.0
SHORE_EDGE = ((0.0, 0.0), (0.0, 10.0))        # water on the left, so the bank lies at x > 0
NO_OTHER_BODY = lambda x, y: None             # noqa: E731
NOT_BLOCKED = lambda tri: False               # noqa: E731
DRY = lambda tri, receiver, source: False             # noqa: E731


def ramps(edges=(SHORE_EDGE,), ground=lambda x, y: 6.0, blocked=NOT_BLOCKED, other=NO_OTHER_BODY, wet=DRY):
    return shore.shore_ramps(edges, lambda x, y: SHEET, ground, blocked, other, wet)


def heights(tris):
    return [v[2] for t in tris for v in t]


def faces_up(tri):
    (ax, ay, _), (bx, by, _), (cx, cy, _) = tri
    return (bx - ax) * (cy - ay) - (cx - ax) * (by - ay) > 0


class RampGeometryTest(unittest.TestCase):
    def test_bank_ramp_starts_under_the_sheet_and_reaches_the_ground(self):
        out = ramps()
        self.assertTrue(out.bank)
        self.assertAlmostEqual(max(heights(out.bank)), SHEET - shore.FREEBOARD_M)
        self.assertAlmostEqual(min(heights(out.bank)), 6.0)
        self.assertTrue(all(faces_up(t) for t in out.bank))

    def test_ramp_falls_at_its_slope(self):
        for tri in ramps().bank:
            for x, _, z in tri:
                self.assertAlmostEqual(z, max(6.0, SHEET - shore.FREEBOARD_M - shore.RAMP_SLOPE * x))

    def test_a_bank_that_is_not_lower_needs_no_ramp(self):
        self.assertEqual(ramps(ground=lambda x, y: SHEET - 0.1).bank, [])

    def test_a_footprint_or_road_blocks_its_ramp_and_is_reported(self):
        out = ramps(blocked=lambda tri: True)
        self.assertEqual(out.bank, [])
        self.assertAlmostEqual(out.blocked_m, 10.0)

    def test_an_abutting_lower_body_gets_a_cascade_not_a_terrain_ramp(self):
        out = ramps(other=lambda x, y: ("water:2", 4.0) if x > 0.2 else None)
        self.assertEqual(out.bank, [])
        self.assertTrue(out.cascade)
        self.assertAlmostEqual(min(heights(out.cascade)), 4.0)

    def test_an_uphill_body_does_not_get_a_cascade(self):
        out = ramps(other=lambda x, y: ("water:2", 12.0) if x > 0.2 else None)
        self.assertFalse(out.cascade)

    def test_a_convex_corner_is_closed_by_a_fan(self):
        square = [((0.0, 0.0), (10.0, 0.0)), ((10.0, 0.0), (10.0, 10.0)),
                  ((10.0, 10.0), (0.0, 10.0)), ((0.0, 10.0), (0.0, 0.0))]
        corner = (10.0, 0.0)
        out = ramps(edges=square, ground=lambda x, y: 0.0)
        beyond_corner = [t for t in out.bank if any(v[0] > corner[0] and v[1] < corner[1] for v in t)]
        self.assertTrue(beyond_corner)


class StripMaskTest(unittest.TestCase):
    """A strip is judged by its whole area, kind by kind and segment by segment."""

    @staticmethod
    def footprint_blocks(ring):
        return lambda tri: triangle_touches(tri, ring, 0.0, closed=True)

    def test_a_footprint_wholly_inside_a_strip_blocks_it(self):
        small_building = [(2.0, 0.5), (3.0, 0.5), (3.0, 1.5), (2.0, 1.5)]
        out = ramps(blocked=self.footprint_blocks(small_building))
        self.assertGreater(out.blocked_m, 0.0)
        self.assertFalse([t for t in out.bank if any(v[1] < 2.0 for v in t)], "ramp covers the building")

    def test_a_road_crossing_the_middle_of_a_strip_blocks_it(self):
        road = [(-1.0, 1.0), (6.0, 1.0)]
        out = ramps(blocked=lambda tri: triangle_touches(tri, road, 0.5, closed=False))
        self.assertGreater(out.blocked_m, 0.0)

    def test_a_cascade_does_not_cover_a_footprint(self):
        building = [(0.5, 3.0), (1.5, 3.0), (1.5, 4.0), (0.5, 4.0)]
        out = ramps(other=lambda x, y: ("water:2", 4.0) if x > 0.2 else None, blocked=self.footprint_blocks(building))
        self.assertTrue(out.cascade)
        self.assertGreater(out.blocked_m, 0.0)
        self.assertFalse([t for t in out.cascade if any(2.0 < v[1] < 4.0 for v in t)])

    def test_a_strip_between_a_cascade_and_a_bank_is_split_at_the_edge_of_the_other_body(self):
        other_body = [(0.2, -5.0), (20.0, -5.0), (20.0, 5.0), (0.2, 5.0)]
        out = ramps(other=lambda x, y: ("water:2", 4.0) if x > 0.2 and y < 5.0 else None,
                    wet=lambda tri, receiver, source: receiver != "water:2" and triangle_overlaps_region(tri, other_body, []))
        self.assertTrue(out.cascade and out.bank)
        self.assertLessEqual(max(v[1] for t in out.cascade for v in t), 5.0)
        self.assertGreaterEqual(min(v[1] for t in out.bank for v in t if v[0] > 0.3), 5.0 - 1e-9)

    def test_a_cascade_may_land_only_on_its_own_receiving_body(self):
        receiver = [(0.45, -1.0), (2.0, -1.0), (2.0, 11.0), (0.45, 11.0)]
        third_body = [(0.2, 0.75), (0.35, 0.75), (0.35, 1.25), (0.2, 1.25)]

        def wet_by(tri, receiving, source):
            bodies = {"water:2": receiver, "water:3": third_body}
            return any(name != receiving and triangle_overlaps_region(tri, ring, []) for name, ring in bodies.items())

        out = ramps(other=lambda x, y: ("water:2", 4.0) if x > 0.45 else None, wet=wet_by)
        self.assertGreater(out.blocked_m, 0.0)
        overlaps_third = [t for t in out.cascade if triangle_overlaps_region([(v[0], v[1]) for v in t], third_body, [])]
        self.assertFalse(overlaps_third)


class WetPatchTest(unittest.TestCase):
    """A bank ramp must not cover water, however small the patch or wherever it lies in the strip."""

    @staticmethod
    def wet_where(outer):
        return lambda tri, receiver, source: receiver is None and triangle_overlaps_region(tri, outer, [])

    def test_a_small_patch_inside_a_strip_blocks_it(self):
        patch = [(2.0, 0.55), (2.1, 0.55), (2.1, 0.65), (2.0, 0.65)]
        out = ramps(wet=self.wet_where(patch))
        self.assertGreater(out.blocked_m, 0.0)
        self.assertFalse([t for t in out.bank if any(v[0] < 2.1 and 0.5 < v[1] < 0.7 for v in t)])

    def test_the_bodys_own_sheet_edge_is_not_wet_cover(self):
        own_water = [(-5.0, 0.0), (0.0, 0.0), (0.0, 10.0), (-5.0, 10.0)]
        self.assertTrue(ramps(wet=self.wet_where(own_water)).bank)

    def test_boundary_touch_is_not_wet_overlap_but_positive_area_is(self):
        tri = [(0.0, 0.0), (12.0, 0.0), (12.0, 2.0)]
        touch = [(5.0, -1.0), (7.0, -1.0), (7.0, 0.0), (5.0, 0.0)]
        overlap = [(5.0, -1.0), (7.0, -1.0), (7.0, 0.0005), (5.0, 0.0005)]
        self.assertFalse(triangle_overlaps_region(tri, touch, []))
        self.assertTrue(triangle_overlaps_region(tri, overlap, []))

    def test_coincident_triangle_and_ring_have_positive_overlap(self):
        tri = [(0.0, 0.0), (4.0, 0.0), (0.0, 4.0)]
        self.assertTrue(triangle_overlaps_region(tri, tri, []))

    def test_partial_containment_with_wet_vertices_on_triangle_boundary_is_wet(self):
        tri = [(0.0, 0.0), (4.0, 0.0), (0.0, 4.0)]
        wet = [(0.0, 0.0), (2.0, 0.0), (0.0, 1.0)]
        self.assertTrue(triangle_overlaps_region(tri, wet, []))

    def test_water_hole_is_dry_but_crossing_the_hole_boundary_is_wet(self):
        outer = [(0.0, 0.0), (12.0, 0.0), (12.0, 12.0), (0.0, 12.0)]
        hole = [(4.0, 4.0), (8.0, 4.0), (8.0, 8.0), (4.0, 8.0)]
        inside_hole = [(4.5, 4.5), (7.5, 4.5), (6.0, 7.0)]
        crossing = [(3.5, 5.5), (6.5, 5.5), (3.5, 7.5)]
        self.assertFalse(triangle_overlaps_region(inside_hole, outer, [hole]))
        self.assertTrue(triangle_overlaps_region(crossing, outer, [hole]))

    def test_disjoint_ring_stays_dry_for_small_clip_triangle(self):
        tri = [(0.0, 0.0), (0.01, 0.0), (0.0, 0.01)]
        wet = [(0.001, 0.0090001), (0.008, 0.0020001), (0.008, 0.0020009), (0.001, 0.0090009)]
        self.assertFalse(triangle_overlaps_region(tri, wet, []))

    def test_translated_triangle_just_above_cutoff_stays_wet(self):
        x0, y0 = 1000.0, 1000.0
        tri = [(x0, y0), (x0 + 1.0, y0), (x0, y0 + 1.0)]
        wet = [(x0, y0), (x0 + 4.5e-5, y0), (x0, y0 + 4.5e-5)]
        self.assertTrue(triangle_overlaps_region(tri, wet, []))

    def test_translated_cutoff_is_pinned_on_both_sides(self):
        x0, y0 = 1000.0, 1000.0
        tri = [(x0, y0), (x0 + 1.0, y0), (x0, y0 + 1.0)]
        above = [(x0, y0), (x0 + 4.5e-5, y0), (x0, y0 + 4.5e-5)]       # area 1.0125e-9 > 1e-9
        below = [(x0, y0), (x0 + 4.4e-5, y0), (x0, y0 + 4.5e-5)]       # area 9.9e-10 < 1e-9
        self.assertTrue(triangle_overlaps_region(tri, above, []))
        self.assertFalse(triangle_overlaps_region(tri, below, []))


class LakeBankTest(unittest.TestCase):
    """On main the carve leaves the sheet hanging 1.5 m over the cell just outside it."""

    @classmethod
    def setUpClass(cls):
        plan, _, _ = lake_scene()
        cls.col, _ = plan_collision(plan)
        cls.level = cls.first_hit(0.0, 0.0)

    @classmethod
    def first_hit(cls, x, y):
        return 200.0 - ray_cast(cls.col, (x, y, 200.0), (0.0, 0.0, -1.0), 400.0).t

    def test_surface_just_outside_every_shore_is_within_a_ramp_step_of_the_sheet(self):
        reach = 0.5
        lowest_allowed = self.level - shore.FREEBOARD_M - shore.RAMP_SLOPE * (reach + 0.5)
        outside = [(40 + reach, 0.0), (-40 - reach, 0.0), (0.0, 30 + reach), (0.0, -30 - reach),
                   (40 + reach, 20.0), (-40 - reach, -20.0)]
        for x, y in outside:
            self.assertGreaterEqual(self.first_hit(x, y), lowest_allowed, (x, y))


LAKE_RING = [(-40.0, -30.0), (40.0, -30.0), (40.0, 30.0), (-40.0, 30.0)]   # its west bank is the low one
SECONDARY = {"highway": "secondary", "bridge": "yes"}                         # 7 m road: an 8 m deck
FLOAT32_M = 1e-4             # mesh vertices are stored in float32: tens of metres from the origin, about 4e-6 m
FLOAT32_SLIVER_M2 = 1e-3


def bank_tris_over_lake_with(bridge_way):
    plan, _, _ = make_scene([(LAKE_RING, {"natural": "water"}, True), (bridge_way, SECONDARY)], lake_ground,
                            width=W, height=H)
    (bank,) = [o for o in plan.objects if o.mb_id.startswith("bank:")]
    vs = bank.mesh.vertices
    return [[(vs[i][0], vs[i][1]) for i in face] for face in bank.mesh.faces]


class DeckClearanceTest(unittest.TestCase):
    """D178: a bank ramp runs under an elevated deck and is clipped out of an at-grade deck's footprint."""

    def test_a_ramp_runs_under_an_elevated_deck(self):
        # 160 m long, crossing the west shore 90 m from its west end: the deck stands over 4 m above the ramp there
        tris = bank_tris_over_lake_with([(-130.0, 0.0), (30.0, 0.0)])
        for x in (-40.5, -42.0):
            self.assertTrue(any(point_in_ring(x, 0.0, t) for t in tris), x)

    def test_a_ramp_is_clipped_out_of_an_at_grade_deck_footprint_only(self):
        tris = bank_tris_over_lake_with([(-48.0, 12.0), (-32.0, 12.0)])   # 16 m long: at-grade over the shore
        footprint = [(-48.5, 8.0), (-31.5, 8.0), (-31.5, 16.0), (-48.5, 16.0)]   # 0.5 m sunk ends, 4 m half width
        under_deck_m2 = sum(polygon_area(convex_intersection(t, footprint)) for t in tris)
        self.assertLess(under_deck_m2, FLOAT32_SLIVER_M2)
        south_of_deck = [p[1] for t in tris for p in t if -44.0 < p[0] < -40.0 and p[1] < 8.0 + FLOAT32_M]
        self.assertAlmostEqual(max(south_of_deck), 8.0, delta=FLOAT32_M)   # cut at the footprint, not a strip short


RAMP_TRI = ((0.0, 0.0, 0.0), (10.0, 0.0, 1.0), (0.0, 10.0, 2.0))


def deck_across_ramp(underside_z, abutment=False):
    """A 20 m deck along y = 4 with a 2 m half width and a flat underside at ``underside_z``; with ``abutment``,
    its west end is a section sunk into an abutment."""
    z = [None if abutment else underside_z, underside_z]
    return DeckUnderside(footprint=[[(-5.0, 6.0), (-5.0, 2.0), (15.0, 2.0), (15.0, 6.0)]], z=z)


def mitred_deck(underside_z):
    """A deck turning 45 degrees at (10, 0), its sections ``underside_z`` swept by the production mitre."""
    return DeckUnderside(footprint=sweep_footprint([(0.0, 0.0), (10.0, 0.0), (20.0, 10.0)], 2.0), z=underside_z)


class TrimUnderDecksTest(unittest.TestCase):
    def test_an_elevated_deck_keeps_the_triangle_whole(self):
        self.assertEqual(trim_under_decks(RAMP_TRI, [deck_across_ramp(10.0)]), [RAMP_TRI])

    def test_an_abutment_masks_even_a_high_deck(self):
        self.assertNotEqual(trim_under_decks(RAMP_TRI, [deck_across_ramp(10.0, abutment=True)]), [RAMP_TRI])

    def test_a_low_corner_of_a_mitred_deck_is_at_grade(self):
        # the swept underside rises 0 -> 2.6 m along the outer edge to the mitre corner (10.83, -2): about 2.43 m
        # over (10.1, -1.9), though the nearest centre-line station (10, 0) is at 2.6 m
        tri = ((10.1, -1.9, 0.0), (10.2, -1.9, 0.0), (10.1, -1.8, 0.0))
        self.assertEqual(trim_under_decks(tri, [mitred_deck([0.0, 2.6, 2.6])]), [])
        self.assertEqual(trim_under_decks(tri, [mitred_deck([2.6, 2.6, 2.6])]), [tri])

    def test_an_at_grade_deck_cuts_out_exactly_its_footprint(self):
        pieces = trim_under_decks(RAMP_TRI, [deck_across_ramp(3.0)])
        plans = [[(x, y) for x, y, _ in t] for t in pieces]
        band_area = (8.0 + 4.0) / 2 * 4.0                  # the triangle between y = 2 and y = 6
        self.assertAlmostEqual(sum(polygon_area(p) for p in plans), 50.0 - band_area)
        self.assertFalse(any(2.0 < sum(y for _, y in p) / 3 < 6.0 for p in plans))
        for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in pieces:   # on the ramp plane z = x / 10 + y / 5, wound CCW
            for x, y, z in ((ax, ay, az), (bx, by, bz), (cx, cy, cz)):
                self.assertAlmostEqual(z, x / 10 + y / 5)
            self.assertGreater((bx - ax) * (cy - ay) - (by - ay) * (cx - ax), 0.0)
