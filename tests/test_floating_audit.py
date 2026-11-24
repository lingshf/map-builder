# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""tools/floating_audit.py: ray raster, finding classification and the committed sample (needs numpy)."""
from __future__ import annotations

import json
import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import floating_audit as fa  # noqa: E402

SAMPLE = os.path.join(ROOT, "examples", "synthetic_sample.mbmap")
GRID = np.arange(0.5, 10.0)            # cell centres of a 10 m x 10 m square, 1 m cells
HOVER_M = 0.5


def square(z: float, lo: float = 0.0, hi: float = 10.0) -> np.ndarray:
    """Two triangles of a horizontal square at height ``z`` over [lo, hi]^2."""
    a, b, c, d = (lo, lo, z), (hi, lo, z), (hi, hi, z), (lo, hi, z)
    return np.array([[a, b, c], [a, c, d]], dtype=float)


def raster_of(*layers: tuple[np.ndarray, int]) -> fa.Raster:
    raster = fa.Raster(GRID, GRID)
    for tris, owner in layers:
        raster.add(tris, np.full(len(tris), owner, dtype=np.int32))
    return raster


def surfaces(road_z: float) -> fa.Surfaces:
    """Collision and visual alike: a terrain square at z=0 with a road square over it at ``road_z``."""
    road = square(road_z)
    terrain = raster_of((square(0.0), 0))
    everything = raster_of((square(0.0), 0), (road, 1))
    names = ["terrain", "road"]
    by_kind = {"terrain": terrain, "road": raster_of((road, 1))}
    return fa.Surfaces(GRID, GRID, everything, by_kind, everything, by_kind, names, names)


def road_findings(road_z: float) -> dict[str, list[dict]]:
    findings = fa.Findings(1.0, GRID, GRID, 0.0)
    fa._check_roads(surfaces(road_z), findings, 0.2)
    return findings.regions


class RasterTest(unittest.TestCase):
    def test_the_highest_surface_wins_and_names_its_owner(self):
        raster = raster_of((square(0.0), 0), (square(2.0, 2.0, 6.0), 1))
        self.assertEqual(raster.final()[0, 0], 0.0)
        self.assertEqual(raster.final()[3, 3], 2.0)
        self.assertEqual(raster.owner[3, 3], 1)

    def test_cells_outside_every_triangle_are_empty(self):
        raster = raster_of((square(1.0, 0.0, 4.0), 0))
        self.assertTrue(np.isnan(raster.final()[8, 8]))

    def test_a_sloped_triangle_is_sampled_at_the_cell_centre(self):
        ramp = np.array([[(0, 0, 0), (10, 0, 10), (0, 10, 0)]], dtype=float)
        self.assertAlmostEqual(raster_of((ramp, 0)).final()[0, 4], 4.5)

    def test_map_tris_snaps_visual_vertices_to_float32(self):
        tris = np.array([[[-551.21552877, 139.92381506, -21.10734338],
                          [-552.41236655, 139.92381506, -14.34491009],
                          [-547.81370707, 139.92381506, -13.53395873]]], dtype=np.float64)
        mapped = fa._map_tris(tris)
        self.assertEqual(mapped[0, 0, 0], float(np.float32(tris[0, 0, 0])))
        self.assertEqual(mapped[0, 1, 0], float(np.float32(tris[0, 1, 0])))
        self.assertEqual(mapped[0, 2, 1], float(np.float32(-tris[0, 2, 2])))


class RoadClassificationTest(unittest.TestCase):
    def test_a_road_hovering_above_the_terrain_is_reported_in_collision_and_visual(self):
        regions = road_findings(HOVER_M)
        for kind in ("ground_above_terrain:road:col", "ground_above_terrain:road:vis"):
            self.assertIn(kind, regions)
            self.assertAlmostEqual(regions[kind][0]["max_offset_m"], HOVER_M)

    def test_a_road_on_the_terrain_is_not_reported(self):
        self.assertEqual(road_findings(0.05), {})


class MapExtentTest(unittest.TestCase):
    def test_cells_past_the_terrain_edge_are_off_the_map(self):
        class Col:
            objects = [{"name": "bank:osm:way/1", "aabb": [0, 0, 0, 99, 99, 1]},
                       {"name": "terrain", "aabb": [0, 0, 0, 10, 20, 1]}]
        on_map = fa._on_map(Col, np.array([5.5, 10.5]), np.array([0.5, 19.5, 20.5]))
        self.assertEqual(on_map.tolist(), [[True, False], [True, False], [False, False]])


class SampleAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = fa.audit(SAMPLE)

    def test_no_collision_floats_above_or_is_buried_below_the_visible_surface(self):
        self.assertTrue(self.result["ok"], self.result["findings_summary"])

    def test_the_sample_roads_do_not_hover(self):
        hovering = [kind for kind in self.result["findings_summary"] if kind.startswith("ground_above_terrain:road")]
        self.assertEqual(hovering, [])

    def test_findings_are_json_serialisable_without_infinities(self):
        json.dumps(self.result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
