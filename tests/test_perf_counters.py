# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""The perf counter registry through real counted sites: off by default, counts when enabled, resets per run."""

from __future__ import annotations

import unittest

from map_builder.core import dem, overlap, osm, perf_counters
from map_builder.core.collision import ColObject, write_collision
from map_builder.core.geodesy import Area

SQUARE = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
TRIANGLE = [(0.0, 0.0), (4.0, 0.0), (0.0, 4.0)]
FAR_PATH = [(100.0, 100.0), (110.0, 100.0), (110.0, 110.0)]


class PerfCounterRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._was_enabled = perf_counters.ENABLED
        perf_counters.reset()
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        perf_counters.set_enabled(self._was_enabled)
        perf_counters.reset()

    def test_disabled_sites_record_nothing(self) -> None:
        perf_counters.set_enabled(False)
        osm.point_in_ring(1.0, 1.0, SQUARE)
        self.assertEqual({}, perf_counters.snapshot())

    def test_enabled_site_counts_its_unit(self) -> None:
        perf_counters.set_enabled(True)
        osm.point_in_ring(1.0, 1.0, SQUARE)
        self.assertEqual({"ring_edge_tests": {"total": 4, "stages": {"other": 4}}}, perf_counters.snapshot())

    def test_tri_emitted_counts_the_triangles_the_collision_actually_appends(self) -> None:
        perf_counters.set_enabled(True)
        quad = ColObject("a", "id-a", "terrain", [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
                         [(0, 1, 2), (0, 2, 3)])
        write_collision([quad])
        self.assertEqual({"tri_emitted[terrain]": 2}, {k: v["total"] for k, v in perf_counters.snapshot().items()})

    def test_reset_clears_counts(self) -> None:
        perf_counters.set_enabled(True)
        osm.point_in_ring(1.0, 1.0, SQUARE)
        perf_counters.reset()
        self.assertEqual({}, perf_counters.snapshot())

    def test_count_goes_to_innermost_stage_then_parent_then_other(self) -> None:
        perf_counters.set_enabled(True)
        with perf_counters.stage("outer"):
            perf_counters.inc("clip_steps")
            with perf_counters.stage("inner"):
                perf_counters.inc("clip_steps", 2)
            perf_counters.inc("clip_steps", 4)
        perf_counters.inc("clip_steps", 8)
        self.assertEqual({"total": 15, "stages": {"outer": 5, "inner": 2, "other": 8}},
                         perf_counters.snapshot()["clip_steps"])

    def test_overlap_early_return_counts_pair_but_no_edge_tests(self) -> None:
        perf_counters.set_enabled(True)
        self.assertFalse(overlap.triangle_touches(TRIANGLE, FAR_PATH, 0.0, closed=False))
        counts = perf_counters.snapshot()
        self.assertEqual(1, counts["overlap_pairs"]["total"])
        self.assertNotIn("overlap_edge_tests", counts)

    def test_overlap_counts_each_exact_edge_pair_tested(self) -> None:
        perf_counters.set_enabled(True)
        crossing_path = [(-1.0, 3.0), (3.0, -1.0)]
        self.assertTrue(overlap.triangle_touches(TRIANGLE, crossing_path, 0.0, closed=False))
        # The first of the three triangle edges already answers; the loop stops there.
        self.assertEqual(1, perf_counters.snapshot()["overlap_edge_tests"]["total"])

    def test_dem_resample_counts_every_grid_cell(self) -> None:
        perf_counters.set_enabled(True)
        area = Area(48.0, 11.0, 60.0, 60.0)
        _, _, nx, ny = dem.grid_layout(area, 20.0)
        with self.assertRaises(dem.NoDataError):
            dem._sample_grid(area, 20.0, [], lambda lat, lon: None, {})
        self.assertEqual(nx * ny, perf_counters.snapshot()["grid_cells"]["total"])


if __name__ == "__main__":
    unittest.main()
