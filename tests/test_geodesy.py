# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
import math
import unittest

from map_builder.core.errors import AreaError
from map_builder.core.geodesy import (Area, LocalFrame, gltf_to_map, map_to_gltf, map_to_unity_x_negated,
                                      unity_x_negated_to_map, utm_forward)


def det3(cols):
    (a, b, c), (d, e, f), (g, h, i) = cols
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


class GeodesyTest(unittest.TestCase):
    def test_local_frame_round_trip_and_directions(self):
        f = LocalFrame(47.3, 8.5)
        for x, y in ((0, 0), (1000, -700), (-2500, 2500), (3.25, 0.5)):
            lat, lon = f.to_geographic(x, y)
            x2, y2 = f.to_local(lat, lon)
            self.assertAlmostEqual(x, x2, delta=1e-6)
            self.assertAlmostEqual(y, y2, delta=1e-6)
        x, y = f.to_local(47.3, 8.501)
        self.assertGreater(x, 0)
        self.assertAlmostEqual(y, 0, delta=0.01)
        x, y = f.to_local(47.301, 8.5)
        self.assertAlmostEqual(x, 0, delta=1e-6)
        self.assertAlmostEqual(y, 111.19, delta=0.2)  # ~1 mdeg latitude at 47N

    def test_utm_central_meridian_known_value(self):
        e, n = utm_forward(45.0, 9.0, 32, False)
        self.assertAlmostEqual(e, 500000.0, delta=1e-3)
        self.assertAlmostEqual(n, 4982950.4, delta=0.1)
        e, n = utm_forward(-33.0, 21.0, 34, True)
        self.assertAlmostEqual(e, 500000.0, delta=1e-3)
        self.assertGreater(n, 6_000_000)

    def test_axis_conventions_on_asymmetric_point(self):
        p = (1.0, 2.0, 3.0)  # east, north, up
        self.assertEqual(map_to_gltf(p), (1.0, 3.0, -2.0))       # glTF +Y up, +Z = south
        self.assertEqual(gltf_to_map(map_to_gltf(p)), p)
        self.assertEqual(map_to_unity_x_negated(p), (-1.0, 3.0, -2.0))
        self.assertEqual(unity_x_negated_to_map(map_to_unity_x_negated(p)), p)
        basis = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
        self.assertEqual(det3([map_to_gltf(b) for b in basis]), 1)  # proper rotation: winding kept
        self.assertEqual(det3([map_to_unity_x_negated(b) for b in basis]), -1)  # mirror: winding flips

    def test_area_bounds(self):
        with self.assertRaises(AreaError):
            Area(47, 8, 10, 500)
        with self.assertRaises(AreaError):
            Area(47, 8, 2500, 500)
        with self.assertRaises(AreaError):
            Area(47, 8, math.nan, 500)
        a = Area.from_bbox(47.0, 8.0, 47.009, 8.013)
        self.assertAlmostEqual(a.height, 1000.7, delta=2)
        self.assertAlmostEqual(a.width, 986, delta=5)
        s, w, n, e = a.geographic_bbox()
        self.assertLess(s, 47.0005)
        self.assertGreater(e, 8.0125)
        with self.assertRaises(AreaError):
            Area.from_bbox(47.01, 8.0, 47.0, 8.01)

    def test_bbox_fit_encloses_request_and_rejects_nonlocal(self):
        south, west, north, east = 47.0, 8.0, 47.009, 8.013
        a = Area.from_bbox(south, west, north, east)
        for la in (south, north):
            for lo in (west, east):
                x, y = a.frame.to_local(la, lo)
                self.assertTrue(a.contains(x * (1 - 1e-9), y * (1 - 1e-9)), (la, lo, x, y))
        with self.assertRaises(AreaError):  # would fold onto ~1 km at Greenwich
            Area.from_bbox(-0.005, -179.995, 0.005, 179.995)
        with self.assertRaises(AreaError):
            Area.from_bbox(47.0, 8.0, 47.0 + math.nan, 8.01)

    def test_antimeridian_pole_and_limit_guards(self):
        with self.assertRaises(AreaError):
            Area(0.0, 179.999, 1000, 1000)
        with self.assertRaises(AreaError):
            Area(89.0, 0.0, 1000, 1000)
        with self.assertRaises(AreaError):
            Area(47, 8, 100_000_000, 1000, max_side_m=float("nan"))
        with self.assertRaises(AreaError):  # hard cap still applies with a huge requested limit
            Area(47, 8, 6000, 1000, max_side_m=1e9)
        s, w, n, e = Area(0.0, 179.9, 1000, 1000).geographic_bbox()
        self.assertLessEqual(e, 180.0)
        with self.assertRaises(AreaError):  # centre inside the limit, footprint outside it
            Area(84.0, 0.0, 1000, 1000)
        a = Area.from_bbox(83.985, -0.15, 83.995, 0.15, max_side_m=5000)  # ~3.5 km x 1.1 km near 84N
        self.assertAlmostEqual(a.width, 3510, delta=40)


if __name__ == "__main__":
    unittest.main()
