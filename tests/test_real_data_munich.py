"""S2-F2: elevated parts, building passages and roof shapes on real OpenStreetMap data.

The fixture is an excerpt (OSM ways within ~50 m of two spots, plus a few chosen ways) of the 400 x 400 m
Munich Altstadt area of tools/demo/presets/munich-altstadt.json, fetched from Overpass on 2026-11-19 (OpenStreetMap
contributors, ODbL). The terrain is flat (z = 0): the live GLO-30 build is checked separately in the PR."""

import os
import unittest

from map_builder.core.generate import PlanOptions, build_plan
from map_builder.core.geodesy import Area
from map_builder.core.osm import classify, load_osm_file
from map_builder.core.structures import check_probes

from .test_scene_generation import assert_closed_manifold, make_grid

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "munich_altstadt_excerpt.osm")
AREA = Area(48.1395, 11.5764, 400.0, 400.0)

PASSAGE_BUILDING = "osm:way/80965641"      # crossed by the footway osm:way/1163022325 (Rid Passage)
ELEVATED_PART = "osm:way/879138845"        # building:part, building:min_level=1, 6 levels, roof:shape=gabled
DEAD_END = "osm:way/23632544"
BENDING = "osm:way/25882450"
# tagged roof:shape -> mb_ids generated as exactly that shape (rectangular footprints)
MEASURED_ROOFS = {"gabled": ["osm:way/80965553", "osm:way/80965659", "osm:way/144135890", "osm:way/150797496"],
                  "skillion": ["osm:way/108429818"]}


def plan():
    n = 43
    grid = make_grid([[0.0] * n for _ in range(n)], 10.0, -210.0, -210.0)
    return build_plan(AREA, grid, classify(load_osm_file(FIXTURE), AREA), PlanOptions(trees=False))


class MunichRealDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = plan()
        cls.objects = {o.mb_id: o for o in cls.plan.objects}
        cls.probes = {p["id"]: p for p in cls.plan.passage_probes}
        cls.unsupported = {u["id"]: u["reason"] for u in cls.plan.report["unsupported_features"]}

    def test_building_passage_splits_the_real_building(self):
        parts = {k: v for k, v in self.objects.items() if k.startswith(PASSAGE_BUILDING + "#")}
        self.assertEqual(sorted(parts), [PASSAGE_BUILDING + "#%d" % i for i in (1, 2, 3)])
        self.assertNotIn(PASSAGE_BUILDING, self.objects)
        for o in parts.values():
            assert_closed_manifold(self, o.mesh)
        self.assertEqual(self.plan.report["counts"]["building_passages"], 1)
        self.assertIn("passage_height", parts[PASSAGE_BUILDING + "#3"].provenance)

    def test_passage_probe_passes_with_the_probe_radius(self):
        probe = self.probes["osm:way/1163022325:passage"]
        self.assertEqual((probe["kind"], probe["radius_m"]), ("elevated", 1.0))
        kept, blocked = check_probes(self.plan, [probe])
        self.assertEqual((len(kept), blocked), (1, []))
        self.assertNotIn("passage_probes_blocked", self.plan.report)

    def test_elevated_part_is_generated_above_the_ground_with_a_passing_probe(self):
        o = self.objects[ELEVATED_PART]
        self.assertGreater(min(v[2] for v in o.mesh.vertices), 2.5)   # building:min_level=1 -> raised volume
        self.assertNotIn(ELEVATED_PART, self.unsupported)
        probe = self.probes[ELEVATED_PART + ":under"]
        kept, blocked = check_probes(self.plan, [probe])
        self.assertEqual((len(kept), blocked), (1, []))
        zs = {round(p[2], 3) for p in probe["path_map"]}
        self.assertEqual(zs, {1.3})                                   # ground + r + 0.3 m

    def test_dead_end_and_bending_passages_yield_no_probe(self):
        self.assertIn("dead end", self.unsupported[DEAD_END])
        self.assertIn("bends", self.unsupported[BENDING])
        self.assertEqual(sorted(p for p in self.probes if p.endswith(":passage")),
                         ["osm:way/1163022325:passage"])
        self.assertFalse([k for k in self.objects if "#" in k and k.split("#")[0] in
                          (DEAD_END, BENDING)])

    def test_roof_shapes_are_generated_as_tagged(self):
        for shape, ids in MEASURED_ROOFS.items():
            for mb_id in ids:
                prov = self.objects[mb_id].provenance
                self.assertTrue(prov["roof_shape"].startswith("measured:"), (mb_id, prov["roof_shape"]))
                self.assertEqual(prov["roof_shape_built"], shape, mb_id)
                assert_closed_manifold(self, self.objects[mb_id].mesh)

    def test_unmodellable_real_roofs_report_their_fallback(self):
        flat = self.objects["osm:way/85765729"].provenance
        self.assertEqual(flat["roof_shape_built"], "flat")
        self.assertEqual(flat["roof_shape"], "fallback:flat (roof:shape=gabled on non-rectangular footprint)")
        for mb_id in ("osm:way/80965613", "osm:way/80965653"):
            prov = self.objects[mb_id].provenance
            self.assertEqual(prov["roof_shape_built"], "pyramidal")
            self.assertTrue(prov["roof_shape"].startswith("fallback:pyramidal"), prov["roof_shape"])


if __name__ == "__main__":
    unittest.main()
