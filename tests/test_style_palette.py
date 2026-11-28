# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
import colorsys
import math
import unittest
from types import SimpleNamespace

from map_builder.core import style, water
from map_builder.core.dem import ElevationGrid
from map_builder.core.generate import PlanOptions
from map_builder.core.glb import read_glb, write_glb
from map_builder.core.mesh import MeshData

from .test_water import lake_scene

FLAT = (0.0, 0.0, 1.0)
SUN_SIDE = (math.sin(math.radians(60)) * -0.64, math.sin(math.radians(60)) * -0.77, math.cos(math.radians(60)))
SHADE_SIDE = (-SUN_SIDE[0], -SUN_SIDE[1], SUN_SIDE[2])
SIDE_ON = (0.6, -0.5, 0.3)    # perpendicular to the sun's horizontal direction, tilted up: mid tone


def hue(linear_rgb):
    return colorsys.rgb_to_hsv(*(style.linear_to_srgb(c) for c in linear_rgb))[0]


class TerrainFaceColorTest(unittest.TestCase):
    def test_steep_faces_use_cliff_colours_by_facing(self):
        lit = style.terrain_face_color("grass", SUN_SIDE, in_bank_band=False)
        shadow = style.terrain_face_color("grass", SHADE_SIDE, in_bank_band=False)
        self.assertNotEqual(lit, shadow)
        self.assertEqual(lit, style.terrain_face_color("forest", SUN_SIDE, in_bank_band=True))

    def test_gentle_slope_is_not_a_cliff(self):
        gentle = (math.sin(math.radians(30)), 0.0, math.cos(math.radians(30)))
        self.assertNotIn(style.terrain_face_color("grass", gentle, False),
                         (style.terrain_face_color("grass", SUN_SIDE, False),
                          style.terrain_face_color("grass", SHADE_SIDE, False)))

    def test_bank_band_faces_are_sand_not_shallow_water(self):
        in_band = style.terrain_face_color("grass", FLAT, in_bank_band=True)
        out_of_band = style.terrain_face_color("grass", FLAT, in_bank_band=False)
        self.assertNotEqual(in_band, out_of_band)
        self.assertGreater(in_band[0], in_band[2])    # warm sand, not water-blue

    def test_water_colour_differs_by_style(self):
        self.assertNotEqual(style.water_color("stylized"), style.water_color("classic"))
        self.assertEqual(style.water_color("classic"), water.WATER_COLOR)

    def test_classic_terrain_has_no_slope_ramp(self):
        self.assertEqual(style.terrain_color("classic", "grass", 0.0), style.terrain_color("classic", "grass", 0.4))


class RoadColorTest(unittest.TestCase):
    def test_footpaths_and_tracks_share_one_sand_colour_apart_from_roads(self):
        foot = {style.road_color("stylized", {"highway": h}) for h in ("footway", "path", "track")}
        self.assertEqual(len(foot), 1)
        for road in ("residential", "primary", "service"):
            self.assertNotIn(style.road_color("stylized", {"highway": road}), foot)

    def test_classic_footpaths_are_unchanged(self):
        self.assertEqual(style.road_color("classic", {"highway": "footway"}), (0.35, 0.32, 0.28))


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


class ShoreBandFacesTest(unittest.TestCase):
    GRID = ElevationGrid(0.0, 0.0, 1.0, 20, 20, [[0.0] * 20 for _ in range(20)], {})
    SQUARE_SHORE = [((2.0, 2.0), (18.0, 2.0)), ((18.0, 2.0), (18.0, 18.0)),
                    ((18.0, 18.0), (2.0, 18.0)), ((2.0, 18.0), (2.0, 2.0))]

    def faces_within(self, band: float) -> set:
        return water.shore_band_faces(self.GRID, [SimpleNamespace(shore=self.SQUARE_SHORE)], band)

    def test_faces_next_to_the_shore_on_both_sides_are_in_the_band(self) -> None:
        faces = self.faces_within(2.0)
        self.assertIn((10, 1, 0), faces)        # outside the square
        self.assertIn((10, 3, 1), faces)        # inside the square

    def test_face_deep_inside_the_body_or_far_inland_is_not_in_the_band(self) -> None:
        faces = self.faces_within(2.0)
        self.assertNotIn((10, 10, 0), faces)
        self.assertNotIn((10, 10, 1), faces)

    def test_the_two_faces_of_a_cell_are_decided_by_their_own_centroid(self) -> None:
        faces = self.faces_within(0.5)
        self.assertEqual({k for (i, j, k) in faces if (i, j) == (10, 2)}, {0})


class ShorePlanColoursTest(unittest.TestCase):
    """The visible shallow band must be the ramp that adjoins the water, not terrain triangles beyond it."""

    @staticmethod
    def face_colours(plan, prefix):
        (obj,) = [o for o in plan.objects if o.mb_id.startswith(prefix)]
        return set(obj.mesh.face_colors)

    def lake_plan(self, style_name):
        plan, _, _ = lake_scene(PlanOptions(style=style_name))
        return plan

    def test_stylized_bank_ramp_is_the_blue_dominant_shallow_band(self):
        (ramp,) = self.face_colours(self.lake_plan("stylized"), "bank:")
        self.assertEqual(ramp, style.bank_color("stylized"))
        self.assertGreater(ramp[2], ramp[0])

    def test_no_stylized_terrain_face_is_shallow_band_coloured(self):
        self.assertNotIn(style.bank_color("stylized"), self.face_colours(self.lake_plan("stylized"), "terrain"))

    def test_classic_bank_ramp_keeps_the_classic_colour(self):
        self.assertEqual(self.face_colours(self.lake_plan("classic"), "bank:"), {style.bank_color("classic")})


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
