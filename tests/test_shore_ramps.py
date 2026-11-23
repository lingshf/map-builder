# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Shore ramps (S4-COL-FLOAT-2): the flat water sheet does not hover over its bank. Synthetic scenes only."""
from __future__ import annotations

import unittest

from map_builder.core import shore
from map_builder.core.overlap import triangle_touches
from map_builder.core.query import ray_cast
from map_builder.core.structures import plan_collision

from .test_water import lake_scene

SHEET = 10.0
SHORE_EDGE = ((0.0, 0.0), (0.0, 10.0))        # water on the left, so the bank lies at x > 0
NO_OTHER_BODY = lambda x, y: None             # noqa: E731
NOT_BLOCKED = lambda tri: False               # noqa: E731


def ramps(edges=(SHORE_EDGE,), ground=lambda x, y: 6.0, blocked=NOT_BLOCKED, other=NO_OTHER_BODY):
    return shore.shore_ramps(edges, lambda x, y: SHEET, ground, blocked, other)


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
        out = ramps(other=lambda x, y: 4.0 if x > 0.2 else None)
        self.assertEqual(out.bank, [])
        self.assertTrue(out.cascade)
        self.assertAlmostEqual(min(heights(out.cascade)), 4.0)

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
        out = ramps(other=lambda x, y: 4.0 if x > 0.2 else None, blocked=self.footprint_blocks(building))
        self.assertTrue(out.cascade)
        self.assertGreater(out.blocked_m, 0.0)
        self.assertFalse([t for t in out.cascade if any(2.0 < v[1] < 4.0 for v in t)])

    def test_a_strip_between_a_cascade_and_a_bank_is_split_at_the_edge_of_the_other_body(self):
        out = ramps(other=lambda x, y: 4.0 if x > 0.2 and y < 5.0 else None)
        self.assertTrue(out.cascade and out.bank)
        self.assertLessEqual(max(v[1] for t in out.cascade for v in t), 5.0)
        self.assertGreaterEqual(min(v[1] for t in out.bank for v in t if v[0] > 0.3), 5.0 - 1e-9)


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
