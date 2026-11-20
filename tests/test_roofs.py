# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
import math
import random
import unittest

from map_builder.core import roofs
from map_builder.core.generate import build_building

from .test_scene_generation import (assert_closed_consistent, building, flat_grid, rect_ccw, rect_cw,
                                    signed_volume)

HEIGHT, ROOF_H = 10.0, 3.0
EAVE = HEIGHT - ROOF_H
RECT = rect_ccw(-10, -6, 10, 6)  # 20 x 12 m, long side along x


def build(outer=RECT, holes=(), **tags):
    tags.setdefault("height", str(HEIGHT))
    tags.setdefault("roof__height", str(ROOF_H))
    mesh, _, prov = build_building(building(outer, holes, **tags), flat_grid(), 0.0)
    return mesh, prov


def roof_verts(mesh):
    """Vertices above the footprint's wall tops (the roof apex region) and all above-ground ones."""
    return [v for v in mesh.vertices if v[2] > -1e-6]


class RoofShapeTest(unittest.TestCase):
    NEW_RECT = ("half-hipped", "gambrel", "mansard", "round", "saltbox")

    def check_solid(self, shape, outer=RECT):
        mesh, prov = build(outer, roof__shape=shape)
        self.assertEqual(prov["roof_shape_built"], shape, prov)
        self.assertTrue(prov["roof_shape"].startswith("measured:"), prov["roof_shape"])
        assert_closed_consistent(self, mesh)
        self.assertGreater(signed_volume(mesh), 0, shape)
        zs = [v[2] for v in roof_verts(mesh)]
        self.assertAlmostEqual(max(zs), HEIGHT, delta=1e-3)
        self.assertAlmostEqual(min(zs), EAVE, delta=1e-3)  # nothing between the ground and the eave but walls
        self.assertAlmostEqual(prov["eave_height_m"], EAVE, delta=1e-2)
        self.assertEqual(set(mesh.materials) - {"MB Facade", "MB Roof"}, set())
        return mesh, prov

    def test_new_rectangular_shapes_are_closed_outward_and_exact_height(self):
        for shape in self.NEW_RECT:
            for outer in (RECT, rect_ccw(-6, -10, 6, 10), rect_cw(-10, -6, 10, 6)[::-1]):
                self.check_solid(shape, outer)

    def test_convex_shapes_on_a_square_and_a_hexagon(self):
        hexagon = [(8 * math.cos(k * math.pi / 3), 8 * math.sin(k * math.pi / 3)) for k in range(6)]
        for shape in ("dome", "onion"):
            for outer in (rect_ccw(-7, -7, 7, 7), RECT, hexagon):
                self.check_solid(shape, outer)

    def test_dome_is_round_and_onion_narrows_to_the_tip(self):
        mesh, _ = build(rect_ccw(-7, -7, 7, 7), roof__shape="dome")
        top = [v for v in mesh.vertices if v[2] > EAVE + 1e-6]
        self.assertEqual(len(top), 5 * 4 + 1)  # 5 rings of 4 + apex
        for x, y, z in top:  # quarter ellipse: r = cos, z = sin
            r = math.hypot(x, y) / math.hypot(7, 7)
            self.assertAlmostEqual(r * r + ((z - EAVE) / ROOF_H) ** 2, 1.0, places=6)
        onion, _ = build(rect_ccw(-7, -7, 7, 7), roof__shape="onion")
        rings = sorted({round(v[2], 6) for v in onion.vertices if v[2] > EAVE + 1e-6})
        self.assertEqual(len(rings), 7)  # six rings and the apex
        radius = [max(math.hypot(v[0], v[1]) for v in onion.vertices if abs(v[2] - z) < 1e-6) for z in rings]
        self.assertEqual(radius, sorted(radius, reverse=True))

    def test_big_footprint_keeps_roof_within_budget(self):
        n = 1800
        ring = [(40 * math.cos(2 * math.pi * k / n), 40 * math.sin(2 * math.pi * k / n)) for k in range(n)]
        for shape in ("dome", "onion"):
            mesh, prov = build_big(ring, shape)
            roof_tris = sum(len(f) - 2 for f, m in zip(mesh.faces, mesh.face_materials)
                            if mesh.materials[m] == "MB Roof")
            self.assertLessEqual(roof_tris, roofs.MAX_ROOF_TRIANGLES, shape)
            self.assertEqual(prov["roof_shape_built"], shape)

    def test_reservation_is_exact_for_every_roof_kind(self):
        """S4-ROOF-NAMED AC5: reserved == emitted (vertices and triangles) for every roof kind, so it never undercounts
        and stays within RESERVE_MARGIN of the emitted geometry."""
        round_ring = [(8 * math.cos(2 * math.pi * k / 12), 8 * math.sin(2 * math.pi * k / 12)) for k in range(12)]
        cases = [(s, RECT) for s in ("flat", "skillion", "pyramidal", "gabled", "hipped", "half-hipped", "gambrel",
                                     "mansard", "round", "saltbox", "dome", "onion")]
        cases += [(s, round_ring) for s in ("flat", "pyramidal", "dome", "onion")]
        for shape, ring in cases:
            calls = []
            feature = building(ring, height=str(HEIGHT), roof__height=str(ROOF_H), roof__shape=shape)
            mesh, _, prov = build_building(feature, flat_grid(), 0.0, reserve=lambda v, t: calls.append((v, t)))
            self.assertEqual(prov["roof_shape_built"], shape)
            self.assertEqual(len(calls), 1)
            emitted = (len(mesh.vertices), len(list(mesh.triangles())))
            for got, want in zip(calls[0], emitted):
                self.assertGreaterEqual(got, want, (shape, calls, emitted))
                self.assertLessEqual(got, want * (1 + roofs.RESERVE_MARGIN), (shape, calls, emitted))

    def test_near_rectangle_gable_with_unequal_ends_is_a_planar_skeleton_roof(self):
        """S4-ROOF-NAMED AC3: the analytic gable's slopes are quads that are not planar unless the eave edges are
        parallel; such a footprint is built from the skeleton (or named), and the emitted slopes are planar."""
        skew = [(-10, -6), (10, -6), (11, 6), (-10, 5.5)]
        _, prov = build(skew, roof__shape="gabled")
        self.assertIn("roof_construction", prov)
        self.assertEqual(prov["roof_shape_built"], "gabled")
        mesh, prov = build(rect_ccw(-10, -6, 10, 6), roof__shape="gabled")
        self.assertEqual(prov["roof_shape"], "measured:osm roof:shape")
        self.assertNotIn("roof_faces", prov)

    def test_analytic_gable_slope_error_judges_parallel_eaves(self):
        self.assertIsNone(roofs.analytic_gable_slope_error(rect_ccw(-10, -6, 10, 6), False))
        self.assertIsNone(roofs.analytic_gable_slope_error([(-10, -6), (10, -6), (10, 6), (-10, 6 + 1e-7)], False))
        self.assertIn("off parallel", roofs.analytic_gable_slope_error([(-10, -6), (10, -6), (11, 6), (-10, 5.5)], False))

    def test_skeleton_gable_survives_a_hair_of_noise_on_a_noisy_l_footprint(self):
        """A noisy L splits its ridge into two nodes 2e-4 m apart; they are merged, so the gable never depends on
        float noise (S4-ROOF-NAMED: CI-only 9007 failure)."""
        l_ring = [(-10.000001477974797, -10.000014143973283), (13.999977313955497, -10.00003311884352),
                  (14.000016107356643, -3.999945795143959), (-4.000023546915706, -4.000024391166052),
                  (-3.9999994245597428, 14.00001553617018), (-9.999968971861902, 14.000001912956636)]
        rng = random.Random(1)
        for _ in range(60):
            ring = [(x + rng.uniform(-1e-10, 1e-10), y + rng.uniform(-1e-10, 1e-10)) for x, y in l_ring]
            prov: dict = {}
            plan = roofs.plan_roof("gabled", ring, [], prov)
            self.assertEqual(plan.shape_built, "gabled", prov["roof_shape"])
            self.assertTrue(plan.skeleton)

def build_big(ring, shape):
    feature = building(ring, height=str(HEIGHT), roof__height=str(ROOF_H), roof__shape=shape)
    mesh, _, prov = build_building(feature, flat_grid(21, 10.0, -100.0, -100.0), 0.0, max_ring_vertices=2000)
    return mesh, prov


class RoofOrientationTest(unittest.TestCase):
    def ridge(self, mesh):
        """(x extent, y extent) of the vertices at the highest z."""
        top = [v for v in mesh.vertices if v[2] > HEIGHT - 1e-6]
        xs, ys = [v[0] for v in top], [v[1] for v in top]
        return max(xs) - min(xs), max(ys) - min(ys)

    def test_orientation_swaps_the_ridge_axis(self):
        for shape in ("gabled", "gambrel", "saltbox", "half-hipped", "round"):
            along, prov_a = build(roof__shape=shape)
            across, prov_c = build(roof__shape=shape, roof__orientation="across")
            ax, ay = self.ridge(along)
            cx, cy = self.ridge(across)
            self.assertGreater(ax, 1.0, shape)
            self.assertLess(ay, 1e-6, shape)
            self.assertGreater(cy, 1.0, shape)
            self.assertLess(cx, 1e-6, shape)
            self.assertTrue(prov_c["roof_orientation"].startswith("measured:"), shape)
            self.assertTrue(prov_a["roof_orientation"].startswith("inferred:"), shape)
            assert_closed_consistent(self, across)
            self.assertGreater(signed_volume(across), 0, shape)

    def test_direction_puts_the_ridge_perpendicular_to_the_slope(self):
        for shape in ("gabled", "saltbox"):
            east, prov = build(roof__shape=shape, roof__direction="90")  # slopes face east/west
            self.assertEqual(self.ridge(east)[0] < 1e-6, True, shape)  # ridge runs north-south
            self.assertTrue(prov["roof_orientation"].startswith("measured:osm roof:direction"), prov)
            north, _ = build(roof__shape=shape, roof__direction="0")
            self.assertLess(self.ridge(north)[1], 1e-6, shape)  # ridge runs east-west
            explicit, _ = build(roof__shape=shape, roof__direction="90", roof__orientation="along")
            self.assertLess(self.ridge(explicit)[1], 1e-6, shape)  # roof:orientation wins

    def test_saltbox_long_slope_faces_the_direction(self):
        for direction, sign in (("0", 1), ("180", -1)):
            mesh, prov = build(roof__shape="saltbox", roof__direction=direction)
            ridge_y = {round(v[1], 6) for v in mesh.vertices if v[2] > HEIGHT - 1e-6}
            self.assertEqual(len(ridge_y), 1)
            # the ridge sits a third of the width from the short slope's eave: the long slope faces `direction`
            self.assertAlmostEqual(ridge_y.pop(), -sign * 12 / 6.0 * 1.0, places=6)
            self.assertTrue(prov["roof_direction"].startswith("measured:"))
        _, prov = build(roof__shape="saltbox")
        self.assertTrue(prov["roof_direction"].startswith("inferred:"))

    def test_skillion_direction_rotates_the_slope(self):
        for direction, low in (("0", (0, 6)), ("90", (10, 0)), ("180", (0, -6)), ("270", (-10, 0))):
            mesh, _ = build(roof__shape="skillion", roof__direction=direction)
            low_z = min(v[2] for v in mesh.vertices if v[2] > 0)
            lows = [v for v in mesh.vertices if abs(v[2] - low_z) < 1e-6]
            self.assertAlmostEqual(max(v[2] for v in mesh.vertices), HEIGHT, delta=1e-6)
            cx = sum(v[0] for v in lows) / len(lows)
            cy = sum(v[1] for v in lows) / len(lows)
            self.assertAlmostEqual(cx, low[0], places=6, msg=direction)
            self.assertAlmostEqual(cy, low[1], places=6, msg=direction)


class RoofFallbackTest(unittest.TestCase):
    L_SHAPE = [(-10, -10), (10, -10), (10, 0), (0, 0), (0, 10), (-10, 10)]
    COURT = [rect_cw(-3, -3, 3, 3)]

    def test_unsupported_shape_falls_back_to_flat(self):
        _, prov = build(roof__shape="butterfly")
        self.assertEqual(prov["roof_shape_built"], "flat")
        self.assertEqual(prov["roof_shape"], "fallback:flat (roof:shape=butterfly not modelled)")

    def test_rect_shapes_on_other_footprints(self):
        pentagon = [(0, 10), (-9.5, 3), (-6, -8), (6, -8), (9.5, 3)]
        for shape in ("half-hipped", "gambrel", "mansard", "round", "saltbox"):
            _, prov = build(pentagon, roof__shape=shape)
            self.assertEqual(prov["roof_shape_built"], "pyramidal", shape)
            self.assertTrue(prov["roof_shape"].startswith("fallback:pyramidal"), prov["roof_shape"])
            _, prov = build(self.L_SHAPE, roof__shape=shape)
            self.assertEqual(prov["roof_shape_built"], "flat", shape)
            self.assertTrue(prov["roof_shape"].startswith("fallback:flat"), prov["roof_shape"])

    def test_dome_and_onion_on_concave_or_courtyard_footprints(self):
        for shape in ("dome", "onion"):
            _, prov = build(self.L_SHAPE, roof__shape=shape)
            self.assertEqual(prov["roof_shape"], f"fallback:flat ({shape} roof on concave footprint)")
            _, prov = build(rect_ccw(-10, -10, 10, 10), self.COURT, roof__shape=shape)
            self.assertEqual(prov["roof_shape"], f"fallback:flat (roof:shape={shape} with courtyard)")
            self.assertEqual(prov["roof_shape_built"], "flat")

    def test_zero_roof_height_falls_back(self):
        _, prov = build(roof__shape="dome", roof__height="0")
        self.assertEqual(prov["roof_shape_built"], "flat")
        self.assertTrue(prov["roof_shape"].startswith("fallback:flat"))


if __name__ == "__main__":
    unittest.main()
