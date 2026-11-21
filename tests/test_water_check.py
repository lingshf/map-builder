# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""tools/water_check.py (S4-WATER-SURFACE AC6): wet-probe clearance is measured against the exact PRE-CARVE ground,
not the carved terrain the package emits."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import water_check as wc  # noqa: E402
from map_builder.core.collision import ColObject, read_collision, write_collision  # noqa: E402


def quad(z: float, x0: float = -50.0, x1: float = 50.0) -> tuple[list, list]:
    return [(x0, -50.0, z), (x1, -50.0, z), (x1, 50.0, z), (x0, 50.0, z)], [(0, 1, 2), (0, 2, 3)]


def col(terrain_z: float, with_water: bool) -> object:
    objs = [ColObject("terrain", "terrain:grid", "terrain", *quad(terrain_z))]
    if with_water:
        objs.append(ColObject("water:osm:way/1", "water:osm:way/1", "water", *quad(5.0, -10.0, 10.0)))
    return read_collision(write_collision(objs))


class WetClearanceTest(unittest.TestCase):
    PROBE = {"id": "osm:way/9:under", "radius_m": 1.0, "path_map": [[-5.0, 0.0, 7.0], [5.0, 0.0, 7.0]]}

    def rows(self, pre_z: float) -> list:
        return wc.wet_clearance(col(3.0, True), [self.PROBE], 0.62, col(pre_z, False))

    def test_clearance_is_measured_over_the_pre_carve_ground(self) -> None:
        [(_, pre, emitted, ok)] = self.rows(3.0)
        self.assertAlmostEqual(pre, 1.0, places=5)       # 7 - 1 - max(water 5, ground 3)
        self.assertTrue(ok)
        self.assertAlmostEqual(emitted, 1.0, places=5)

    def test_pre_carve_ground_higher_than_the_carved_bed_is_caught(self) -> None:
        # clears the carved terrain (3 m) and the water (5 m), but not the pre-carve ground at 6.8 m
        [(_, pre, emitted, ok)] = self.rows(6.8)
        self.assertFalse(ok)
        self.assertAlmostEqual(pre, -0.8, places=5)
        self.assertAlmostEqual(emitted, 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
