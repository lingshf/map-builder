# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S4-COL-DEGEN: ring cleanup, the 1 mm right-triangle counterexample (Python and C#), empty objects and the
kept-degenerate report."""

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from map_builder.core.collision import ColObject, is_degenerate, read_collision, write_collision
from map_builder.core.generate import PlanOptions, build_plan
from map_builder.core.mesh import MeshData
from map_builder.core.pipeline import plan_to_package
from map_builder.core.query import capsule_hits, ray_cast
from map_builder.core.triangulate import clean_ring, fan_triangles

from . import csharp_build
from .synthetic import synthetic_inputs

MM_TRIANGLE = ((0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.001, 0.0))   # 0.5 mm2: validator-degenerate, still a surface


def _area2(t):
    return abs((t[1][0] - t[0][0]) * (t[2][1] - t[0][1]) - (t[1][1] - t[0][1]) * (t[2][0] - t[0][0]))


class RingCleanupTest(unittest.TestCase):
    def test_clean_ring_drops_duplicate_and_collinear_vertices(self):
        ring = [(0.0, 0.0), (0.0, 0.0), (2.0, 0.0), (4.0, 0.0), (4.0, 3.0), (4.0, 3.0), (0.0, 3.0)]
        self.assertEqual(clean_ring(ring, 1e-7), [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)])

    def test_clean_ring_collapsed_ring_is_empty(self):
        self.assertEqual(clean_ring([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)], 1e-7), [])

    def test_fan_starts_at_the_first_vertex_and_is_not_re_chosen(self):
        ring = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0 - 1e-6)]   # D119: same triangulation as before the cleanup
        tris = fan_triangles(ring)
        self.assertEqual(tris, [(ring[0], ring[1], ring[2]), (ring[0], ring[2], ring[3])])


class MillimetreTriangleTest(unittest.TestCase):
    """AC1: a validator-degenerate triangle that the query (and the reader) still hit, so it cannot be post-filtered."""

    def setUp(self):
        self.col = read_collision(write_collision([ColObject("t", "osm:way/1", "road", list(MM_TRIANGLE), [(0, 1, 2)])]))

    def test_validator_degenerate_but_hit_at_one_metre(self):
        self.assertTrue(is_degenerate(*self.col.triangle(0)))
        hit = ray_cast(self.col, (0.0003, 0.0003, -1.0), (0.0, 0.0, 1.0), 2.0)
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit.t, 1.0, places=9)
        self.assertEqual(capsule_hits(self.col, [(0.0003, 0.0003, -0.5), (0.0003, 0.0003, 0.5)], 0.0), [0])

    @unittest.skipUnless(shutil.which("dotnet"), "the .NET SDK is not installed")
    def test_csharp_reader_hits_it_too(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "c.mbcol"), "wb") as f:
                f.write(write_collision([ColObject("t", "osm:way/1", "road", list(MM_TRIANGLE), [(0, 1, 2)])]))
            with open(os.path.join(d, "p.json"), "w") as f:
                json.dump([{"path": [[0.0003, 0.0003, -0.5], [0.0003, 0.0003, 0.5]], "radius": 0.0}], f)
            run = subprocess.run([*csharp_build.reader_command(), "--probe-work", os.path.join(d, "c.mbcol"),
                                  os.path.join(d, "p.json")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("probe 0 hits=0 ", run.stdout)


class FlatFaceDropTest(unittest.TestCase):
    LOC = (100.0, 100.0, 0.0)   # float32 spacing there is 7.6e-6 m, so a 1e-9 m offset vanishes in storage

    def run_drop(self, extra_vertex):
        from map_builder.core.generate import drop_unstorable_slivers
        local = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1e-9, 1e-9, 0.0)]
        if extra_vertex is None:
            return drop_unstorable_slivers(local, [(0, 1, 2), (0, 1, 3)], self.LOC)
        return drop_unstorable_slivers([*local, extra_vertex], [(0, 1, 2), (0, 4, 3)], self.LOC)

    def test_flat_face_on_an_edge_of_a_kept_face_is_dropped(self):
        kept, dropped = self.run_drop(None)
        self.assertEqual(kept, [(0, 1, 2)])
        self.assertEqual(len(dropped), 1)

    def test_flat_face_off_every_kept_edge_stays(self):
        kept, dropped = self.run_drop((2.0, 0.0, 0.0))
        self.assertEqual(kept, [(0, 1, 2), (0, 4, 3)])
        self.assertEqual(dropped, [])


class ExportReportTest(unittest.TestCase):
    def test_empty_object_is_dropped_and_reported(self):
        with tempfile.TemporaryDirectory() as d:
            area, grid, cl, _ids, sources = synthetic_inputs(os.path.join(d, "src"))
            plan = build_plan(area, grid, cl, PlanOptions(seed=1))
            empty = copy.copy(plan.objects[-1])
            empty.name, empty.mb_id, empty.mesh, empty.mesh_key = "empty_one", "user:empty_one", MeshData("empty_one"), None
            plan.objects = [*plan.objects, empty]
            path = os.path.join(d, "e.mbmap")
            _m, r = plan_to_package(plan, path, "synthetic", sources, created_utc="2026-01-01T00:00:00Z")
            self.assertTrue(r.ok, r.summary())
            with zipfile.ZipFile(path) as z:
                report = json.loads(z.read("report.json"))
                col = read_collision(z.read("collision/map.mbcol"))
            self.assertNotIn("empty_one", [o["name"] for o in col.objects])
            self.assertTrue(all(o["tri_count"] > 0 for o in col.objects))
            self.assertEqual([e["object"] for e in report["objects_dropped_empty"]], ["empty_one"])
            kept = {e["object"]: e["triangles"] for e in report["degenerate_objects"]}
            self.assertEqual(sum(kept.values()), report["export"]["degenerate_triangles"])


if __name__ == "__main__":
    unittest.main()
