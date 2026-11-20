import math
import unittest
from unittest import mock

from map_builder.core import skeleton
from map_builder.core.errors import LimitError
from map_builder.core.skeleton import MAX_SKELETON_VERTICES, SkeletonError, straight_skeleton

from . import roof_checks as rc

TOL = 1e-9


def assert_tiles(test, ring):
    sk = straight_skeleton(ring)
    gap, overlap, outside, lifted = rc.skeleton_tiling(sk)
    test.assertLessEqual(gap, TOL)
    test.assertLessEqual(overlap, TOL)
    test.assertLessEqual(outside, TOL)
    test.assertEqual(rc.check_planar_faces(lifted), {})
    return sk


def assert_planar_lifted(test, sk):
    for i, face in enumerate(sk.faces):
        pts = [sk.nodes[k] for k in face]
        a, b = sk.ring[i], sk.ring[(i + 1) % len(sk.ring)]
        # plane through the ring edge rising with slope 1 towards the interior
        ln = math.dist(a, b)
        nx, ny = -(b[1] - a[1]) / ln, (b[0] - a[0]) / ln
        for x, y, t in pts:
            test.assertAlmostEqual(nx * (x - a[0]) + ny * (y - a[1]), t, places=7)
        test.assertEqual(sk.nodes[face[0]][2], 0.0)
        test.assertEqual(sk.nodes[face[1]][2], 0.0)


def face_set(sk):
    return {frozenset(tuple(round(c, 7) for c in sk.nodes[k]) for k in f) for f in sk.faces}


RECT = [(0, 0), (20, 0), (20, 12), (0, 12)]
L_SHAPE = [(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)]
L_UNEQUAL = [(0, 0), (10, 0), (10, 4), (6, 4), (6, 10), (0, 10)]
T_SHAPE = [(0, 0), (12, 0), (12, 4), (8, 4), (8, 10), (4, 10), (4, 4), (0, 4)]
T_UNEQUAL = [(0, 0), (13, 0), (13, 4), (9, 4), (9, 11), (4, 11), (4, 4), (0, 4)]
U_SHAPE = [(0, 0), (12, 0), (12, 10), (8, 10), (8, 4), (4, 4), (4, 10), (0, 10)]
U_UNEQUAL = [(0, 0), (13, 0), (13, 10), (9, 10), (9, 5), (4, 5), (4, 11), (0, 11)]
Z_SHAPE = [(0, 0), (8, 0), (8, 3), (14, 3), (14, 9), (6, 9), (6, 6), (0, 6)]
ARROW = [(0, 0), (6, 0), (6, 8), (9, 8), (3, 14), (-3, 8), (0, 8)]
SHAPES = {"L": L_SHAPE, "L unequal": L_UNEQUAL, "T": T_SHAPE, "T unequal": T_UNEQUAL, "U": U_SHAPE,
          "U unequal": U_UNEQUAL, "Z": Z_SHAPE, "arrow": ARROW}


def regular(n, r=10.0):
    return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]


class TestSimpleShapes(unittest.TestCase):
    def test_rectangle_matches_analytic_hipped(self):
        sk = straight_skeleton(RECT)
        self.assertEqual(len(sk.faces), 4)
        inner = sorted(n for n in sk.nodes[4:])
        self.assertEqual(len(inner), 2)
        (x0, y0, t0), (x1, y1, t1) = inner
        self.assertAlmostEqual(x1 - x0, 20 - 12, places=9)  # ridge length L - W
        self.assertAlmostEqual(y0, 6.0, places=9)
        self.assertAlmostEqual(y1, 6.0, places=9)
        self.assertAlmostEqual(t0, 6.0, places=9)
        self.assertAlmostEqual(t1, 6.0, places=9)
        self.assertAlmostEqual(x0, 6.0, places=9)
        self.assertEqual(sorted(len(f) for f in sk.faces), [3, 3, 4, 4])
        assert_planar_lifted(self, sk)

    def test_square_and_regular_polygons_have_one_apex(self):
        for n in (3, 4, 5, 6, 8, 12, 24):
            with self.subTest(n=n):
                ring = [(x + 3.0, y - 2.0) for x, y in regular(n)]
                sk = straight_skeleton(ring)
                self.assertEqual(len(sk.nodes), n + 1)
                x, y, t = sk.nodes[n]
                self.assertAlmostEqual(x, 3.0, places=7)
                self.assertAlmostEqual(y, -2.0, places=7)
                self.assertAlmostEqual(t, 10.0 * math.cos(math.pi / n), places=7)
                self.assertTrue(all(len(f) == 3 for f in sk.faces))
        sq = straight_skeleton([(0, 0), (6, 0), (6, 6), (0, 6)])
        self.assertEqual(sq.nodes[4], (3.0, 3.0, 3.0))


class TestTiling(unittest.TestCase):
    def test_shapes_have_planar_faces_that_tile_the_footprint(self):
        for name, ring in SHAPES.items():
            with self.subTest(shape=name):
                sk = assert_tiles(self, ring)
                self.assertEqual(len(sk.faces), len(ring))
                assert_planar_lifted(self, sk)

    def test_orientation_and_rotation_do_not_change_the_result(self):
        for name, ring in SHAPES.items():
            with self.subTest(shape=name):
                ref = straight_skeleton(ring)
                variants = [ring[::-1]] + [ring[k:] + ring[:k] for k in range(1, len(ring))]
                variants += [(ring[k:] + ring[:k])[::-1] for k in range(len(ring))]
                for v in variants:
                    other = straight_skeleton(v)
                    self.assertEqual(face_set(other), face_set(ref))
                    self.assertEqual(other.nodes, ref.nodes)

    def test_largest_supported_ring_is_one_apex_within_the_event_cap(self):
        sk = straight_skeleton(regular(MAX_SKELETON_VERTICES))
        self.assertEqual(len(sk.nodes), MAX_SKELETON_VERTICES + 1)
        self.assertLessEqual(sk.events, 4 * MAX_SKELETON_VERTICES)

    def test_event_counter_is_reported(self):
        self.assertEqual(straight_skeleton(RECT).events, 2)  # one edge event + one spike step
        self.assertGreater(straight_skeleton(ARROW).events, 1)


class TestSplitEvent(unittest.TestCase):
    def test_reflex_vertex_splits_the_opposite_edge(self):
        # Reflex corner (6, 4) moves along (-1, -1) and reaches the bottom wavefront edge at
        # t = 2, at (4, 2): there the 4 m wide horizontal arm collapses onto the ridge y = 2.
        sk = straight_skeleton(L_UNEQUAL)
        nodes = {(round(x, 7), round(y, 7), round(t, 7)) for x, y, t in sk.nodes[6:]}
        self.assertIn((4.0, 2.0, 2.0), nodes)
        # the bottom edge face has the split node as its only inner node left of the ridge end
        bottom = [sk.nodes[k] for k in sk.faces[0]]
        self.assertIn((4.0, 2.0, 2.0), {(round(x, 7), round(y, 7), round(t, 7)) for x, y, t in bottom})

    def test_arrow_head_reflex_vertices(self):
        sk = assert_tiles(self, ARROW)
        # both reflex corners (6, 8) and (0, 8) travel into the shaft and create nodes
        self.assertGreaterEqual(len(sk.nodes) - len(ARROW), 3)


class TestDegenerateInput(unittest.TestCase):
    def test_collinear_runs_are_merged(self):
        ring = [(0, 0), (5, 0), (20, 0), (20, 6), (20, 12), (7, 12), (0, 12), (0, 3)]
        sk = straight_skeleton(ring)
        ref = straight_skeleton(RECT)
        self.assertEqual(sk.ring, ref.ring)
        self.assertEqual(sk.faces, ref.faces)
        self.assertEqual(len(sk.faces), 4)

    def test_closing_vertex_is_accepted(self):
        self.assertEqual(straight_skeleton(RECT + [RECT[0]]).nodes, straight_skeleton(RECT).nodes)

    def test_self_touching_ring(self):
        with self.assertRaisesRegex(SkeletonError, "touches itself|self-intersects"):
            straight_skeleton([(0, 0), (4, 0), (4, 4), (2, 0), (0, 4)])

    def test_self_intersecting_ring(self):
        with self.assertRaisesRegex(SkeletonError, "self-intersects"):
            straight_skeleton([(0, 0), (6, 0), (1, 4), (5, 5)])

    def test_zero_length_edge(self):
        with self.assertRaisesRegex(SkeletonError, "zero-length edge"):
            straight_skeleton([(0, 0), (4, 0), (4, 0), (4, 4), (0, 4)])
        with self.assertRaisesRegex(SkeletonError, "zero-length edge"):
            straight_skeleton([(0, 0), (4, 0), (4, 5e-7), (4, 4), (0, 4)])

    def test_zero_width_spike(self):
        with self.assertRaisesRegex(SkeletonError, "zero-width spike"):
            straight_skeleton([(0, 0), (4, 0), (4, 4), (4, 6), (4, 4.5), (0, 4)])

    def test_too_many_vertices(self):
        with self.assertRaisesRegex(SkeletonError, "65 vertices exceed the limit of 64"):
            straight_skeleton(regular(MAX_SKELETON_VERTICES + 1))

    def test_fewer_than_three_vertices(self):
        with self.assertRaisesRegex(SkeletonError, "fewer than 3"):
            straight_skeleton([(0, 0), (1, 0)])

    def test_spike_steps_are_charged_against_the_cap(self):
        # RECT needs one edge event plus one spike-resolution step
        with mock.patch.object(skeleton, "MAX_SKELETON_EVENTS", 1):
            with self.assertRaisesRegex(LimitError, "exceeded 1 events"):
                straight_skeleton(RECT)
        with mock.patch.object(skeleton, "MAX_SKELETON_EVENTS", 2):
            straight_skeleton(RECT)

    def test_event_cap_raises_limit_error(self):
        with mock.patch.object(skeleton, "MAX_SKELETON_EVENTS", 0):
            with self.assertRaisesRegex(LimitError, "exceeded 0 events"):
                straight_skeleton(RECT)


if __name__ == "__main__":
    unittest.main()
