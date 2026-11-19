"""Bounded collision queries (map_builder/core/query.py)."""

import math
import unittest

from map_builder.core.collision import ColObject, read_collision, write_collision
from map_builder.core.errors import LimitError
from map_builder.core.query import (capsule_hits, closest_point_segment, closest_point_triangle, ray_cast,
                                    segment_segment_distance, segment_triangle_distance, triangle_is_degenerate)


def _sub_(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


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

    def test_collapsed_and_collinear_triangles(self):
        a, c = (0.0, 0.0, 0.0), (0.0, 4.0, 0.0)
        p = (1.0, 2.0, 0.5)                                    # projects inside the "a == b" sliver's span
        self.assertTrue(triangle_is_degenerate(a, a, c))
        self.assertEqual(closest_point_triangle(p, a, a, c), (0.0, 2.0, 0.0))     # was ZeroDivisionError
        self.assertEqual(closest_point_triangle(p, c, a, a), (0.0, 2.0, 0.0))
        self.assertEqual(closest_point_triangle(p, a, a, a), a)                   # a point
        self.assertAlmostEqual(segment_triangle_distance(p, (1.0, 3.0, 0.5), a, a, c), math.sqrt(1.25))
        self.assertAlmostEqual(segment_triangle_distance((-1, 2, -1), (1, 2, 1), a, a, c), 0.0)   # crosses it
        near = (0.0, 0.0, 0.0), (1e5, 0.0, 0.0), (5e4, 1e-6, 0.0)                # collinear within 1e-11
        self.assertTrue(triangle_is_degenerate(*near))
        self.assertAlmostEqual(segment_triangle_distance((5e4, 2.0, -1), (5e4, 2.0, 1), *near), 2.0, places=5)
        self.assertFalse(triangle_is_degenerate(*self.TRI))
        for tri in ((a, a, c), near):
            self.assertTrue(all(math.isfinite(x) for x in closest_point_triangle((3.0, 1.0, 2.0), *tri)))

    def test_nearly_parallel_segment_keeps_precision(self):
        p, q = (0.0, 0.0001, -0.001), (100000.0, 0.0001, 0.001)
        tri = ((0.0, 0.0, 0.0), (100000.0, 0.0, 0.0), (50000.0, -1.0, 0.0))
        self.assertAlmostEqual(segment_triangle_distance(p, q, *tri), 0.0001, delta=1e-9)
        self.assertAlmostEqual(segment_segment_distance(p, q, tri[0], tri[1]), 0.0001, delta=1e-9)
        # the same configuration rotated about z and shifted (no axis alignment to help the arithmetic)
        cs, sn, off = math.cos(0.7), math.sin(0.7), (1234.5, -987.25, 42.0)
        rot = lambda v: (cs * v[0] - sn * v[1] + off[0], sn * v[0] + cs * v[1] + off[1], v[2] + off[2])
        self.assertAlmostEqual(segment_triangle_distance(rot(p), rot(q), *map(rot, tri)), 0.0001, delta=1e-8)
        col = read_collision(write_collision([ColObject("deck", "osm:way/7", "bridge", list(tri), [(0, 1, 2)])]))
        self.assertEqual(capsule_hits(col, [p, q], 0.00015), [0])
        self.assertEqual(capsule_hits(col, [p, q], 0.00005), [])

    def test_shallow_crossing_of_a_collapsed_triangle_hits(self):
        """Review round 2: sin^2 of the angle (2.5e-25) is below the old parallel cutoff, which skipped the
        interior solution; the path crosses the edge exactly at its midpoint."""
        p, q = (0.0, -5e-8, 0.0), (200000.0, 5e-8, 0.0)
        e0, e1 = (0.0, 0.0, 0.0), (200000.0, 0.0, 0.0)
        self.assertEqual(segment_segment_distance(p, q, e0, e1), 0.0)
        self.assertEqual(segment_segment_distance(e0, e1, p, q), 0.0)
        for tri in ((e0, e1, e1), (e0, e1, (100000.0, 0.0, 0.0))):            # collapsed / collinear on the edge
            with self.subTest(tri=tri):
                self.assertTrue(triangle_is_degenerate(*tri))
                self.assertEqual(segment_triangle_distance(p, q, *tri), 0.0)
                col = read_collision(write_collision([ColObject("edge", "osm:way/8", "prop", list(tri),
                                                                [(0, 1, 2)])]))
                self.assertEqual(capsule_hits(col, [p, q], 1e-8), [0])
        # exactly parallel segments still use the endpoint distances
        self.assertAlmostEqual(segment_segment_distance((0, 1, 0), (5, 1, 0), (2, 0, 0), (9, 0, 0)), 1.0)

    def test_segment_segment_matches_brute_force(self):
        import random
        rng = random.Random(7)
        for _ in range(300):
            pts = [tuple(rng.uniform(-10, 10) for _ in range(3)) for _ in range(4)]
            if rng.random() < 0.3:                              # parallel or overlapping pairs
                d = _sub_(pts[1], pts[0])
                k = rng.uniform(-2, 2)
                pts[3] = (pts[2][0] + d[0] * k, pts[2][1] + d[1] * k, pts[2][2] + d[2] * k)
            got = segment_segment_distance(*pts)
            n = 200
            ref = min(math.dist(lerp(pts[0], pts[1], i / n), closest_point_segment(lerp(pts[0], pts[1], i / n),
                                                                                    pts[2], pts[3]))
                      for i in range(n + 1))
            self.assertLessEqual(got, ref + 1e-9)
            self.assertGreaterEqual(got, ref - 0.2)            # the sampled reference over-estimates a little


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

    def test_extreme_direction_magnitudes(self):
        want = ray_cast(self.col, (0, 0, 5), (0, 0, -1), 100.0)
        for d in ((0, 0, -1e200), (0, 0, -1e-200), (0, 0, -5e-324), (1e-300, 0, -1e300)):
            with self.subTest(d=d):
                got = ray_cast(self.col, (0, 0, 5), d, 100.0)
                self.assertIsNotNone(got)
                self.assertEqual((got.object, got.triangle), (want.object, want.triangle))
                self.assertAlmostEqual(got.t, want.t, places=9)
        side = ray_cast(self.col, (0, 0, 5), (3e-200, 0, 0), 100.0)
        self.assertEqual((side.object, round(side.t, 5)), (1, 10.0))

    def test_grazing_ray_with_subnormal_determinant(self):
        """Review round 2: det = 1e-310 made 1/det overflow and u = 0 * inf = NaN, so t came back NaN."""
        col = read_collision(write_collision([ColObject("tri", "osm:way/4", "prop",
                                                        [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])]))
        for d in ((1, 0, -1e-310), (1, 0, 1e-310), (1, 0, -5e-324)):
            with self.subTest(d=d):
                hit = ray_cast(col, (0, 0, 0), d, 10.0)
                if hit is not None:
                    self.assertTrue(math.isfinite(hit.t))
                    self.assertEqual((hit.t, hit.triangle, hit.object), (0.0, 0, 0))
        hit = ray_cast(col, (0, 0, 0), (1, 0, -1e-310), 10.0)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.t, 0.0)
        miss = ray_cast(col, (0, 0, 1e-300), (1, 0, -1e-310), 10.0)            # numerator / det overflows: a miss
        self.assertIsNone(miss)

    def test_ray_through_a_shared_diagonal_does_not_slip_through(self):
        """Review round 4: both triangles rounded their barycentrics against the shared edge."""
        q = [(46, -92, 0), (160, -92, 0), (160, 36, 0), (46, 36, 0)]
        col = read_collision(write_collision([ColObject("g", "terrain:grid", "terrain", q, [(0, 1, 2), (0, 2, 3)])]))
        hit = ray_cast(col, (222, 91, 119), (-1, -1, -1), 1000.0)
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit.t, 119 * math.sqrt(3), places=9)

    def test_exactly_tangent_capsule_is_a_hit(self):
        """Review round 4: exact 1 m contact computed as 1.0000000000000013 m reported a 1 m capsule clear."""
        col = read_collision(write_collision([ColObject("t", "osm:way/5", "prop",
                                                        [(-40, 30, 0), (40, -30, 0), (0, 0, 10)], [(0, 1, 2)])]))
        self.assertEqual(capsule_hits(col, [(-1, 2, 2), (-1, 2, 3)], 1.0), [0])
        self.assertEqual(capsule_hits(col, [(-1, 2, 2), (-1, 2, 3)], 0.999), [])

    def test_oversized_integers_are_value_errors(self):
        with self.assertRaises(ValueError):
            capsule_hits(self.col, [(10 ** 400, 0, 0)], 1.0)
        with self.assertRaises(ValueError):
            capsule_hits(self.col, [(0, 0, 0)], 10 ** 400)
        with self.assertRaises(ValueError):
            ray_cast(self.col, (0, 0, 5), (0, 0, -1), 10 ** 400)

    def test_degenerate_triangle_is_never_hit(self):
        col = read_collision(write_collision([ColObject("sliver", "osm:way/3", "prop",
                                                        [(0, 0, 0), (0, 0, 0), (0, 4, 0)], [(0, 1, 2)])]))
        self.assertIsNone(ray_cast(col, (0, 2, 5), (0, 0, -1), 100.0))
        self.assertEqual(capsule_hits(col, [(1, 2, 0.5), (1, 3, 0.5)], 1.2), [0])
        self.assertEqual(capsule_hits(col, [(1, 2, 0.5), (1, 3, 0.5)], 1.1), [])


if __name__ == "__main__":
    unittest.main()
