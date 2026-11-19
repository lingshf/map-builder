"""Bounded collision queries (map_builder/core/query.py)."""

import math
import unittest

from map_builder.core.collision import ColObject, read_collision, write_collision
from map_builder.core.errors import LimitError
from map_builder.core.query import capsule_hits, ray_cast, segment_triangle_distance


def box(x0, y0, z0, x1, y1, z1):
    v = [(x, y, z) for z in (z0, z1) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]


def collision():
    ground = [(-50, -50, 0), (50, -50, 0), (50, 50, 0), (-50, 50, 0)]
    objs = [ColObject("ground", "terrain:grid", "terrain", ground, [(0, 1, 2), (0, 2, 3)]),
            ColObject("box", "osm:way/1", "building", *box(10, -5, 0, 20, 5, 10)),
            ColObject("far", "osm:way/2", "building", *box(30, -5, 0, 40, 5, 10))]
    return read_collision(write_collision(objs))


class SegmentTriangleTest(unittest.TestCase):
    TRI = ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (0.0, 4.0, 0.0))

    def test_distances(self):
        d = segment_triangle_distance
        self.assertEqual(d((1, 1, -1), (1, 1, 1), *self.TRI), 0.0)                 # crosses
        self.assertEqual(d((1, 1, 1), (1, 1, -1), *self.TRI), 0.0)                 # two-sided
        self.assertAlmostEqual(d((1, 1, 2), (2, 1, 3), *self.TRI), 2.0)            # endpoint over the face
        self.assertAlmostEqual(d((-1, -1, 1), (-1, 5, 1), *self.TRI), math.sqrt(2))  # parallel to an edge
        self.assertAlmostEqual(d((5, 5, 0), (5, 5, 0), *self.TRI), 3 * math.sqrt(2), places=6)  # a point
        self.assertAlmostEqual(d((-3, 1, 0), (-1, 1, 0), *self.TRI), 1.0)          # coplanar, outside
        self.assertEqual(d((0.5, 0.5, 0), (1, 1, 0), *self.TRI), 0.0)              # coplanar, inside
        line = ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (4.0, 0.0, 0.0))                 # degenerate: its edges
        self.assertAlmostEqual(d((1, 3, -1), (1, 3, 1), *line), 3.0)


class CapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.col = collision()

    def test_free_path_is_clear(self):
        self.assertEqual(capsule_hits(self.col, [(-40, 20, 3), (40, 20, 3)], 2.0), [])
        self.assertEqual(capsule_hits(self.col, [(-40, 0, 13), (0, 0, 13), (45, 0, 13)], 2.0), [])

    def test_through_box_is_blocked(self):
        self.assertEqual(capsule_hits(self.col, [(0, 0, 5), (25, 0, 5)], 1.0), [1])
        self.assertEqual(capsule_hits(self.col, [(0, 0, 5), (45, 0, 5)], 1.0), [1, 2])
        self.assertEqual(capsule_hits(self.col, [(0, 0, 0.5), (5, 0, 0.5)], 1.0), [0])    # ground within r
        self.assertEqual(capsule_hits(self.col, [(15, 0, 9.5)], 1.0), [1])                # inside: two-sided walls
        self.assertEqual(capsule_hits(self.col, [(15, 0, 5)], 1.0), [])                   # hollow: no wall within r
        res = capsule_hits(self.col, [(0, 0, 5), (25, 0, 5)], 1.0, result=True)
        self.assertEqual(res.objects, [1])
        self.assertGreater(res.work, 0)

    def test_grazing_at_radius_plus_epsilon_is_clear(self):
        r, eps = 1.5, 1e-3
        top = [(12, 0, 10 + r + eps), (18, 0, 10 + r + eps)]
        self.assertEqual(capsule_hits(self.col, top, r), [])
        side = [(0, -5 - r - eps, 5), (25, -5 - r - eps, 5)]
        self.assertEqual(capsule_hits(self.col, side, r), [])
        self.assertEqual(capsule_hits(self.col, [(0, -5 - r + eps, 5), (25, -5 - r + eps, 5)], r), [1])

    def test_budget(self):
        with self.assertRaises(LimitError):
            capsule_hits(self.col, [(0, 0, 5), (45, 0, 5)], 1.0, max_work=5)
        with self.assertRaises(ValueError):
            capsule_hits(self.col, [(0, 0, math.nan)], 1.0)


class RayCastTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.col = collision()

    def test_nearest_hit(self):
        hit = ray_cast(self.col, (0, 0, 5), (2, 0, 0), 100.0)
        self.assertEqual(hit.object, 1)
        self.assertAlmostEqual(hit.t, 10.0, places=5)
        self.assertEqual(self.col.objects[hit.object]["name"], "box")
        self.assertIsNone(ray_cast(self.col, (0, 0, 5), (1, 0, 0), 9.0))
        down = ray_cast(self.col, (0, 0, 5), (0, 0, -1), 100.0)
        self.assertEqual((down.object, round(down.t, 6)), (0, 5.0))
        inside = ray_cast(self.col, (15, 0, 5), (1, 0, 0), 100.0)                 # back face: two-sided
        self.assertEqual(inside.object, 1)
        self.assertAlmostEqual(inside.t, 5.0, places=5)
        a, b, c = self.col.triangle(hit.triangle)
        self.assertTrue(all(abs(p[0] - 10.0) < 1e-6 for p in (a, b, c)))

    def test_budget_and_bad_input(self):
        with self.assertRaises(LimitError):
            ray_cast(self.col, (0, 0, 5), (1, 0, 0), 100.0, max_work=3)
        with self.assertRaises(ValueError):
            ray_cast(self.col, (0, 0, 5), (0, 0, 0), 100.0)


if __name__ == "__main__":
    unittest.main()
