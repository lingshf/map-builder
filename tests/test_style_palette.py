# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
import colorsys
import math
import unittest

from map_builder.core import style
from map_builder.core.glb import read_glb, write_glb
from map_builder.core.mesh import MeshData

FLAT = (0.0, 0.0, 1.0)
SUN_SIDE = (math.sin(math.radians(60)) * -0.64, math.sin(math.radians(60)) * -0.77, math.cos(math.radians(60)))
SHADE_SIDE = (-SUN_SIDE[0], -SUN_SIDE[1], SUN_SIDE[2])
SIDE_ON = (0.6, -0.5, 0.3)    # perpendicular to the sun's horizontal direction, tilted up: mid tone


def hue(linear_rgb):
    return colorsys.rgb_to_hsv(*(style.linear_to_srgb(c) for c in linear_rgb))[0]


class TerrainFaceColorTest(unittest.TestCase):
    def test_steep_faces_use_cliff_colours_by_facing(self):
        lit = style.terrain_face_color("grass", SUN_SIDE, near_water=False)
        shadow = style.terrain_face_color("grass", SHADE_SIDE, near_water=False)
        self.assertNotEqual(lit, shadow)
        self.assertEqual(lit, style.terrain_face_color("forest", SUN_SIDE, near_water=True))

    def test_gentle_slope_is_not_a_cliff(self):
        gentle = (math.sin(math.radians(30)), 0.0, math.cos(math.radians(30)))
        self.assertNotIn(style.terrain_face_color("grass", gentle, False),
                         (style.terrain_face_color("grass", SUN_SIDE, False),
                          style.terrain_face_color("grass", SHADE_SIDE, False)))

    def test_bank_band_is_sand_only_near_water(self):
        near = style.terrain_face_color("grass", FLAT, near_water=True)
        far = style.terrain_face_color("grass", FLAT, near_water=False)
        self.assertEqual(near, style.bank_color("stylized"))
        self.assertNotEqual(near, far)

    def test_classic_terrain_has_no_slope_ramp(self):
        self.assertEqual(style.terrain_color("classic", "grass", 0.0), style.terrain_color("classic", "grass", 0.4))


class FoliageTest(unittest.TestCase):
    def test_crown_faces_have_three_tones_by_facing(self):
        up = style.foliage_color("stylized", 1, FLAT)
        sun = style.foliage_color("stylized", 1, SIDE_ON)
        shade = style.foliage_color("stylized", 1, SHADE_SIDE)
        self.assertEqual(len({up, sun, shade}), 3)

    def test_tint_variant_is_deterministic_and_spreads(self):
        variants = {style.tree_tint_variant("stylized", f"way/{i}") for i in range(30)}
        self.assertEqual(variants, set(range(len(style.TREE_TINT_SCALES))))
        self.assertEqual(style.tree_tint_variant("stylized", "way/7"), style.tree_tint_variant("stylized", "way/7"))
        self.assertEqual(style.tree_tint_variant("classic", "way/7"), 0)

    def test_classic_foliage_ignores_facing(self):
        self.assertEqual(style.foliage_color("classic", 0, FLAT), style.foliage_color("classic", 0, SHADE_SIDE))


class TaggedColourTest(unittest.TestCase):
    def test_tagged_colours_keep_their_hue_inside_the_palette(self):
        red = (1.0, 0.0, 0.0)
        for pulled in (style.facade_color(red, "k"), style.roof_color(red, "k", False)):
            self.assertAlmostEqual(hue(pulled), hue(red), places=2)
            self.assertNotEqual(pulled, red)

    def test_untagged_colours_come_from_the_palette_by_key(self):
        self.assertEqual(style.facade_color(None, "a"), style.facade_color(None, "a"))
        self.assertEqual(style.roof_color(None, "a", is_flat=True), style.roof_color(None, "b", is_flat=True))


class GlbNormalsTest(unittest.TestCase):
    def _glb(self, with_normals):
        mesh = MeshData("m")
        mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        mesh.add_face((0, 1, 2), "MB Terrain", (0.5, 0.5, 0.5))
        spec = {"MB Terrain": ((1.0, 1.0, 1.0), 1.0, 0.0)}
        return write_glb([{"name": "n", "mesh": mesh}], spec, with_normals=with_normals)

    def test_normals_are_optional_and_the_file_shrinks(self):
        with_n, without_n = self._glb(True), self._glb(False)
        self.assertLess(len(without_n), len(with_n))
        self.assertTrue(read_glb(without_n))


if __name__ == "__main__":
    unittest.main()
