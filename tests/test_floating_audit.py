# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""tools/floating_audit.py: ray raster, finding classification and the committed sample (needs numpy)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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
    ctris = np.concatenate((square(0.0), road))
    cowners = np.array([0, 0, 1, 1], dtype=np.int32)
    return fa.Surfaces(GRID, GRID, everything, by_kind, everything, by_kind, names, names,
                       ["terrain", "road"], ctris, cowners, ctris, cowners,
                       np.array(["terrain", "road", "terrain", "road"], dtype=object), object(), 1000.0, 2000.0)


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

    def test_map_tris_keeps_world_coordinates(self):
        tris = np.array([[[-551.21552877, 139.92381506, -21.10734338],
                          [-552.41236655, 139.92381506, -14.34491009],
                          [-547.81370707, 139.92381506, -13.53395873]]], dtype=np.float64)
        mapped = fa._map_tris(tris)
        self.assertEqual(mapped[0, 0, 0], tris[0, 0, 0])
        self.assertEqual(mapped[0, 1, 0], tris[0, 1, 0])
        self.assertEqual(mapped[0, 2, 1], -tris[0, 2, 2])


class CollisionVisualBoundaryTest(unittest.TestCase):
    @staticmethod
    def _col_raw(tris: np.ndarray, owners: np.ndarray):
        class Col:
            pass
        c = Col()
        verts, indices = [], []
        for t in tris:
            o = len(verts)
            verts.extend([tuple(map(float, t[0])), tuple(map(float, t[1])), tuple(map(float, t[2]))])
            indices.extend([o, o + 1, o + 2])
        c.vertices = verts
        c.indices = indices
        c.bounds = (np.min(tris.reshape(-1, 3), axis=0), np.max(tris.reshape(-1, 3), axis=0))
        c.objects = []
        for owner in sorted(set(owners.tolist())):
            tri_ids = np.where(owners == owner)[0]
            flat = tris[tri_ids].reshape(-1, 3)
            lo = np.min(flat, axis=0)
            hi = np.max(flat, axis=0)
            c.objects.append({"aabb": [float(lo[0]), float(lo[1]), float(lo[2]), float(hi[0]), float(hi[1]), float(hi[2])],
                              "tri_start": int(tri_ids.min()), "tri_count": int(len(tri_ids))})
        return c

    def _surfaces(self, xs: np.ndarray, ys: np.ndarray, col_layers: list[tuple[np.ndarray, int]],
                  vis_layers: list[tuple[np.ndarray, int]], names: list[str], classes: list[str]) -> fa.Surfaces:
        col = fa.Raster(xs, ys)
        vis = fa.Raster(xs, ys)
        ctris, cowners = [], []
        vtris, vowners, vcats = [], [], []
        for tris, owner in col_layers:
            col.add(tris, np.full(len(tris), owner, dtype=np.int32))
            ctris.append(tris)
            cowners.append(np.full(len(tris), owner, dtype=np.int32))
        for tris, owner in vis_layers:
            vis.add(tris, np.full(len(tris), owner, dtype=np.int32))
            vtris.append(tris)
            vowners.append(np.full(len(tris), owner, dtype=np.int32))
            vcats.append(np.full(len(tris), classes[owner], dtype=object))
        col_by_class = {"terrain": fa.Raster(xs, ys)}
        col_by_class["terrain"].add(col_layers[0][0], np.zeros(len(col_layers[0][0]), dtype=np.int32))
        vis_by_category = {"terrain": fa.Raster(xs, ys)}
        vis_by_category["terrain"].add(vis_layers[0][0], np.zeros(len(vis_layers[0][0]), dtype=np.int32))
        col_tris = np.concatenate(ctris)
        col_owners = np.concatenate(cowners)
        order = np.argsort(col_owners, kind="stable")
        col_tris = col_tris[order]
        col_owners = col_owners[order]
        col_raw = self._col_raw(col_tris, col_owners)
        return fa.Surfaces(xs, ys, col, col_by_class, vis, vis_by_category, names, names, classes,
                           col_tris, col_owners, np.concatenate(vtris), np.concatenate(vowners),
                           np.concatenate(vcats), col_raw, 1000.0, 2000.0)

    def test_buried_edge_case_is_reported_as_edge_ambiguous(self):
        xs = np.array([0.0], dtype=float)
        ys = np.array([0.0], dtype=float)
        terrain = square(0.0, -2.0, 2.0)
        vis_roof = np.array([[(0.0, -1.0, 10.0), (0.0, 1.0, 10.0), (1.0, 0.0, 10.0)]], dtype=float)
        col_roof = np.array([[(5.0e-5, -1.5, 10.0), (5.0e-5, 1.5, 10.0), (1.50005, 0.0, 10.0)]], dtype=float)
        s = self._surfaces(xs, ys, [(terrain, 0), (col_roof, 1)], [(terrain, 0), (vis_roof, 1)],
                           ["terrain:grid", "osm:way/537242388"], ["terrain", "building"])
        f = fa.Findings(1.0, xs, ys, 0.0)
        fa._check_collision_vs_visual(s, f, 0.2)
        self.assertNotIn("buried_collision", f.regions)
        self.assertIn("edge_ambiguous_collision_visual", f.regions)

    def test_footprint_boundary_8m_repro_still_flags_floating(self):
        xs = np.array([0.5], dtype=float)
        ys = np.array([0.5], dtype=float)
        terrain = square(0.0, 0.0, 2.0)
        col_roof = np.array([[(0.5, 0.0, 8.0), (2.0, 0.0, 8.0), (0.5, 2.0, 8.0)]], dtype=float)
        vis_roof = np.array([[(0.50000001, 0.0, 8.0), (2.0, 0.0, 8.0), (0.50000001, 2.0, 8.0)]], dtype=float)
        s = self._surfaces(xs, ys, [(terrain, 0), (col_roof, 1)], [(terrain, 0), (vis_roof, 1)],
                           ["terrain:grid", "osm:way/repro"], ["terrain", "building"])
        f = fa.Findings(1.0, xs, ys, 0.0)
        fa._check_collision_vs_visual(s, f, 0.2)
        self.assertIn("floating_collision", f.regions)
        self.assertAlmostEqual(f.regions["floating_collision"][0]["max_offset_m"], 8.0, places=3)

    def test_10m_buried_repro_is_not_downgraded_by_unrelated_wall_edge(self):
        xs = np.array([0.0], dtype=float)
        ys = np.array([0.0], dtype=float)
        terrain = square(0.0, -2.0, 2.0)
        wall = np.array([[(0.0, -0.01, 0.0), (0.0, 0.01, 10.0), (0.0, 0.02, 0.0)]], dtype=float)
        far_roof = np.array([[(0.5, -1.0, 10.0), (0.5, 1.0, 10.0), (1.5, 0.0, 10.0)]], dtype=float)
        vis_roof = np.array([[(-0.5, -1.0, 10.0), (-0.5, 1.0, 10.0), (0.5, 0.0, 10.0)]], dtype=float)
        s = self._surfaces(xs, ys, [(terrain, 0), (wall, 1), (far_roof, 1)], [(terrain, 0), (vis_roof, 1)],
                           ["terrain:grid", "osm:way/repro10"], ["terrain", "building"])
        f = fa.Findings(1.0, xs, ys, 0.0)
        fa._check_collision_vs_visual(s, f, 0.2)
        self.assertIn("buried_collision", f.regions)
        self.assertNotIn("edge_ambiguous_collision_visual", f.regions)

    def test_edge_ambiguity_requires_within_documented_tolerance(self):
        xs = np.array([0.0], dtype=float)
        ys = np.array([0.0], dtype=float)
        terrain = square(0.0, -2.0, 2.0)
        vis_roof = np.array([[(0.0, -1.0, 10.0), (0.0, 1.0, 10.0), (1.0, 0.0, 10.0)]], dtype=float)
        col_roof = np.array([[(1.1e-4, -1.0, 10.0), (1.1e-4, 1.0, 10.0), (1.00011, 0.0, 10.0)]], dtype=float)
        s = self._surfaces(xs, ys, [(terrain, 0), (col_roof, 1)], [(terrain, 0), (vis_roof, 1)],
                           ["terrain:grid", "osm:way/tol"], ["terrain", "building"])
        f = fa.Findings(1.0, xs, ys, 0.0)
        fa._check_collision_vs_visual(s, f, 0.2)
        self.assertIn("buried_collision", f.regions)
        self.assertNotIn("edge_ambiguous_collision_visual", f.regions)


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

    def test_min_area_does_not_crash_summary_or_json(self):
        with tempfile.TemporaryDirectory() as td:
            out_json = os.path.join(td, "out.json")
            run = subprocess.run(
                [sys.executable, os.path.join(ROOT, "tools", "floating_audit.py"), SAMPLE, "--min-area", "2", "--json", out_json],
                capture_output=True, text=True, check=False
            )
            self.assertNotEqual(run.returncode, 2, run.stderr)
            with open(out_json, encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIsInstance(payload["findings_summary"], dict)


if __name__ == "__main__":
    unittest.main()
