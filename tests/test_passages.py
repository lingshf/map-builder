"""Building passages (core/passages.py, D24) and the probe under elevated parts (D21)."""

import unittest

from map_builder.core.generate import PlanOptions, build_plan
from map_builder.core.osm import Classified, Feature
from map_builder.core.query import capsule_hits
from map_builder.core.structures import check_probes, plan_collision

from .test_scene_generation import assert_closed_manifold, building, flat_grid, make_grid, rect_ccw, tiny_area

BLD = rect_ccw(-15, -10, 15, 10)          # 30 x 20 m
PASSAGE = [(-30.0, 0.0), (30.0, 0.0)]
OPTS = PlanOptions(trees=False)


def passage(points=PASSAGE, fid="osm:way/2", **tags):
    t = {"highway": "service", "tunnel": "building_passage"}
    t.update(tags)
    f = Feature(fid, "passage", t, [tuple(p) for p in points])
    f.report_pos = (0, 0)
    return f


def plan_for(buildings, passages=(), grid=None, **_):
    cl = Classified()
    cl.buildings = list(buildings)
    cl.passages = list(passages)
    return build_plan(tiny_area(), grid or flat_grid(), cl, OPTS)


def parts(plan, prefix="osm:way/1#"):
    return {o.mb_id: o for o in plan.objects if o.mb_id.startswith(prefix)}


def ray_hits(plan, a, b):
    col, _ = plan_collision(plan)
    return capsule_hits(col, [a, b], 0.05, result=True).objects


class PassageSplitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = plan_for([building(BLD, height="9")], [passage()])

    def test_two_lower_parts_and_one_upper_part(self):
        ps = parts(self.plan)
        self.assertEqual(sorted(ps), ["osm:way/1#1", "osm:way/1#2", "osm:way/1#3"])
        for o in ps.values():
            assert_closed_manifold(self, o.mesh)
        zs = {k: (min(v[2] for v in o.mesh.vertices), max(v[2] for v in o.mesh.vertices)) for k, o in ps.items()}
        self.assertAlmostEqual(zs["osm:way/1#1"][1], 4.5, places=4)    # inferred: min(4.5, eave - 1)
        self.assertAlmostEqual(zs["osm:way/1#2"][1], 4.5, places=4)
        self.assertAlmostEqual(zs["osm:way/1#3"][0], 4.5, places=4)
        self.assertAlmostEqual(zs["osm:way/1#3"][1], 9.0, places=4)
        self.assertIn("inferred", ps["osm:way/1#3"].provenance["passage_height"])
        self.assertEqual(self.plan.report["unsupported_features"], [])

    def test_passage_probe_is_kept_and_passes(self):
        probes = [p for p in self.plan.passage_probes if p["id"] == "osm:way/2:passage"]
        self.assertEqual(len(probes), 1)
        self.assertEqual((probes[0]["kind"], probes[0]["feature"]), ("elevated", "osm:way/2"))
        self.assertEqual(check_probes(self.plan, probes)[1], [])
        self.assertNotIn("passage_probes_blocked", self.plan.report)
        self.assertIn("osm:way/2", [o.mb_id for o in self.plan.objects if o.mb_class == "road"])

    def test_rays_along_and_across_the_building(self):
        z = self.plan.frame.z_offset
        self.assertEqual(ray_hits(self.plan, (-20.0, 0.0, 2.0 - z), (20.0, 0.0, 2.0 - z)), [])
        hit = ray_hits(self.plan, (-20.0, 5.0, 2.0 - z), (20.0, 5.0, 2.0 - z))
        self.assertTrue(hit)


class PassageHeightTest(unittest.TestCase):
    def test_maxheight_is_measured(self):
        plan = plan_for([building(BLD, height="12")], [passage(maxheight="3.5")])
        ps = parts(plan)
        self.assertAlmostEqual(max(v[2] for v in ps["osm:way/1#1"].mesh.vertices), 3.5, places=4)
        self.assertIn("measured", ps["osm:way/1#3"].provenance["passage_height"])
        self.assertEqual(plan.report["inferred"].get("building.passage_height", 0), 0)

    def test_inferred_height_follows_the_eave(self):
        plan = plan_for([building(BLD, height="5.2")], [passage()])
        self.assertAlmostEqual(max(v[2] for v in parts(plan)["osm:way/1#1"].mesh.vertices), 4.2, places=4)

    def test_low_building_is_left_unchanged(self):
        plan = plan_for([building(BLD, height="3")], [passage()])
        self.assertEqual(list(parts(plan, "osm:way/1")), ["osm:way/1"])
        self.assertIn("does not fit", plan.report["unsupported_features"][0]["reason"])

    def test_slope_keeps_lower_tops_flush_with_the_upper_part(self):
        heights = [[0.1 * i for i in range(11)] for _ in range(11)]
        plan = plan_for([building(BLD, height="12")], [passage()], grid=make_grid(heights, x0=-50, y0=-50))
        ps = parts(plan)
        top = lambda o: max(v[2] for v in o.mesh.vertices) + o.location[2]
        bottom = lambda o: min(v[2] for v in o.mesh.vertices) + o.location[2]
        self.assertAlmostEqual(top(ps["osm:way/1#1"]), bottom(ps["osm:way/1#3"]), places=4)
        self.assertAlmostEqual(top(ps["osm:way/1#2"]), bottom(ps["osm:way/1#3"]), places=4)


class PassageFallbackTest(unittest.TestCase):
    def check_unchanged(self, plan, text):
        self.assertEqual(list(parts(plan, "osm:way/1")), ["osm:way/1"])
        self.assertEqual([p for p in plan.passage_probes if p["id"].endswith(":passage")], [])
        entries = plan.report["unsupported_features"]
        self.assertEqual([e["id"] for e in entries], ["osm:way/2"])
        self.assertIn(text, entries[0]["reason"])
        self.assertNotIn("osm:way/2", [o.mb_id for o in plan.objects])

    def test_dead_end_inside_the_footprint(self):
        self.check_unchanged(plan_for([building(BLD, height="9")], [passage([(-30, 0), (0, 0)])]), "dead end")

    def test_courtyard_building(self):
        hole = [(-3, -3), (-3, 3), (3, 3), (3, -3)]
        self.check_unchanged(plan_for([building(BLD, [hole], height="9")], [passage([(-30, 8), (30, 8)])]),
                             "courtyard")

    def test_passage_crossing_no_building(self):
        plan = plan_for([building(BLD, height="9")], [passage([(-30, 40), (30, 40)])])
        self.assertEqual(list(parts(plan, "osm:way/1")), ["osm:way/1"])
        self.assertIn("crosses no building", plan.report["unsupported_features"][0]["reason"])

    def test_already_elevated_building(self):
        self.check_unchanged(plan_for([building(BLD, height="12", min_height="4")], [passage()]), "min_height")


class ElevatedProbeTest(unittest.TestCase):
    def test_probe_under_an_elevated_part(self):
        plan = plan_for([building(BLD, height="12", min_height="6")])
        probe = next(p for p in plan.passage_probes if p["id"] == "osm:way/1:under")
        self.assertEqual(probe["kind"], "elevated")
        self.assertAlmostEqual(probe["radius_m"], 1.0)
        z = plan.frame.z_offset
        self.assertAlmostEqual(probe["path_map"][0][2], 1.3 - z)
        self.assertEqual(check_probes(plan, [probe])[1], [])

    def test_low_clearance_has_no_probe(self):
        self.assertEqual(plan_for([building(BLD, height="12", min_height="2.5")]).passage_probes, [])

    def test_blocked_probe_is_reported_not_exported(self):
        under = building(rect_ccw(-5, -5, 5, 5), fid="osm:way/9", height="3")
        plan = plan_for([building(BLD, height="12", min_height="6"), under])
        self.assertEqual(plan.passage_probes, [])
        self.assertEqual(plan.report["passage_probes_blocked"],
                         [{"id": "osm:way/1:under", "blocker": "osm:way/9"}])


if __name__ == "__main__":
    unittest.main()
