"""DSM terrain correction (map_builder/core/dsm.py). All grids, footprints and OSM data here are SYNTHETIC."""

import contextlib
import io
import json
import math
import os
import random
import tempfile
import unittest
import zipfile

from map_builder.blender.sources import SettingsInputError, settings_kwargs
from map_builder.core import dsm
from map_builder.core.dem import ElevationGrid
from map_builder.core.errors import NoDataError
from map_builder.core.generate import (DSM_CORRECTED_SURFACE, TERRAIN_SURFACE, PlanOptions, build_plan,
                                       dsm_obstacles, road_width)
from map_builder.core.geodesy import Area
from map_builder.core.osm import Classified, Feature, Polygon, classify, parse_osm_xml
from map_builder.core.pipeline import Settings, build_package, generate_plan
from map_builder.core.package import validate_package

from .synthetic import OsmBuilder, write_synthetic_fixtures

COPERNICUS = {"kind": "elevation", "provider": "copernicus-glo30-aws", "tiles": ["SYNTHETIC"]}
LOCAL = {"kind": "elevation", "provider": "local-file", "sha256": "0" * 64}


def ground(x, y):
    """SYNTHETIC ground: a gently tilted plane."""
    return 100.0 + 0.04 * x - 0.02 * y


def make_grid(fn, n=41, spacing=5.0, prov=COPERNICUS):
    x0 = y0 = -(n - 1) * spacing / 2
    heights = [[fn(x0 + i * spacing, y0 + j * spacing) for i in range(n)] for j in range(n)]
    return ElevationGrid(x0, y0, spacing, n, n, heights, dict(prov))


def points(grid):
    for j in range(grid.ny):
        for i in range(grid.nx):
            yield i, j, grid.x0 + i * grid.spacing, grid.y0 + j * grid.spacing


def square(cx, cy, half):
    return [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half)]


class MaskTest(unittest.TestCase):
    """SYNTHETIC mask rasterisation."""

    def test_building_buffer_and_holes(self):
        g = make_grid(ground, n=81, spacing=1.0)
        outer = square(0, 0, 20)
        hole = square(0, 0, 18)[::-1]   # wide courtyard: its centre is > 15 m from every wall
        m = dsm.build_mask(g, buildings=[[outer, hole]])
        for i, j, x, y in points(g):
            d_out = max(abs(x), abs(y))
            inside_ring = 18 < d_out <= 20
            dist_outer = math.hypot(max(abs(x) - 20, 0), max(abs(y) - 20, 0))
            dist_hole = 18 - d_out if d_out < 18 else 0.0
            expected = inside_ring or (d_out > 20 and dist_outer <= 15) or (d_out <= 18 and dist_hole <= 15)
            self.assertEqual(bool(m.mask[j * g.nx + i]), expected, (x, y))

    def test_tree_disc(self):
        g = make_grid(ground, n=41, spacing=1.0)
        m = dsm.build_mask(g, trees=[(3.0, -2.0)])
        for i, j, x, y in points(g):
            self.assertEqual(bool(m.mask[j * g.nx + i]), math.hypot(x - 3, y + 2) <= dsm.TREE_RADIUS_M + 1e-9)

    def test_bridge_ribbon(self):
        g = make_grid(ground, n=101, spacing=2.0)
        pts = [(-60.0, -10.0), (0.0, 0.0), (40.0, 30.0)]
        width = 8.0
        m = dsm.build_mask(g, bridges=[(pts, width)])
        r = width / 2 + dsm.BRIDGE_BUFFER_M
        for i, j, x, y in points(g):
            d = min(_seg_dist(x, y, a, b) for a, b in zip(pts, pts[1:]))
            if abs(d - r) > 1e-6:
                self.assertEqual(bool(m.mask[j * g.nx + i]), d < r, (x, y, d))

    def test_bridge_ways_kept_for_the_mask_and_still_unsupported(self):
        b = OsmBuilder()
        wid = b.way([(-40, 0), (40, 0)], {"highway": "primary", "bridge": "yes", "layer": "1"})
        rid = b.way([(-40, 20), (40, 20)], {"railway": "rail", "bridge": "viaduct"})
        nid = b.way([(-40, -20), (40, -20)], {"highway": "residential", "bridge": "no"})
        cl = classify(parse_osm_xml(b.xml().encode()), Area(47.0, 8.0, 100.0, 100.0))
        self.assertEqual(sorted(f.id for f in cl.bridges), sorted([f"osm:way/{wid}", f"osm:way/{rid}"]))
        unsup = {u["id"] for u in cl.unsupported}
        self.assertIn(f"osm:way/{wid}", unsup)
        self.assertIn(f"osm:way/{rid}", unsup)
        self.assertIn(f"osm:way/{nid}", {r.id for r in cl.roads})
        _, _, _, bridges = dsm_obstacles(cl)
        widths = sorted(w for _, w in bridges)
        self.assertEqual(widths, sorted([road_width({"highway": "primary"})[0], road_width({"railway": "rail"})[0]]))
        # the primary deck (8 m) is masked out to 4 + 15 m from its centreline
        g = make_grid(ground, n=51, spacing=2.0)
        m = dsm.build_mask(g, bridges=bridges)
        idx = lambda x, y: int(round((y - g.y0) / g.spacing)) * g.nx + int(round((x - g.x0) / g.spacing))  # noqa: E731
        self.assertTrue(m.mask[idx(0, -18)])
        self.assertFalse(m.mask[idx(0, -50)])


def _seg_dist(x, y, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)


class CorrectionTest(unittest.TestCase):
    """SYNTHETIC raised features over a tilted plane."""

    def test_raised_building_block_is_lowered_and_never_raised(self):
        fp = square(5, -5, 12)

        def dsm_h(x, y):
            return ground(x, y) + (15.0 if abs(x - 5) <= 12 and abs(y + 5) <= 12 else 0.0)
        g = make_grid(dsm_h)
        out, entry, warning = dsm.apply_correction(g, None, buildings=[[fp]])
        self.assertTrue(entry["applied"])
        self.assertIsNone(warning)
        self.assertIsNot(out, g)
        for i, j, x, y in points(g):
            self.assertLessEqual(out.heights[j][i], g.heights[j][i])
            if abs(x - 5) <= 12 and abs(y + 5) <= 12:
                self.assertAlmostEqual(out.heights[j][i], ground(x, y), delta=0.5, msg=(x, y))
        self.assertGreater(entry["max_lowering_m"], 14.0)
        self.assertGreater(entry["mean_lowering_m"], 0.0)

    def test_tree_bump_is_lowered(self):
        def dsm_h(x, y):
            return ground(x, y) + 8.0 * math.exp(-((x - 2) ** 2 + (y - 4) ** 2) / 8.0)
        g = make_grid(dsm_h, n=41, spacing=1.0)
        out, entry, _ = dsm.apply_correction(g, True, trees=[(2.0, 4.0)])
        self.assertTrue(entry["applied"])
        j, i = int(round(4.0 - g.y0)), int(round(2.0 - g.x0))
        self.assertGreater(g.heights[j][i] - ground(2, 4), 7.9)
        self.assertLess(abs(out.heights[j][i] - ground(2, 4)), 0.3)

    def test_unmasked_points_unchanged_bit_for_bit(self):
        rng = random.Random(7)
        g = make_grid(lambda x, y: ground(x, y) + rng.uniform(-3, 3))
        mask = dsm.build_mask(g, buildings=[[square(0, 0, 10)]], trees=[(-60.0, 60.0)],
                              forests=[[square(60, -60, 20)]])
        out, stats = dsm.correct_grid(g, mask)
        self.assertGreater(stats["masked_points"], 0)
        for i, j, _, _ in points(g):
            if not mask.mask[j * g.nx + i]:
                self.assertEqual(math.copysign(1, out.heights[j][i]), math.copysign(1, g.heights[j][i]))
                self.assertEqual(out.heights[j][i].hex(), g.heights[j][i].hex())
            else:
                self.assertLessEqual(out.heights[j][i], g.heights[j][i])
        self.assertIs(out.provenance, g.provenance)

    def test_guard_skips_when_fewer_than_5_percent_unmasked(self):
        g = make_grid(ground)
        whole = [[square(0, 0, 1000)]]
        out, entry, warning = dsm.apply_correction(g, None, forests=whole)
        self.assertIs(out, g)
        self.assertFalse(entry["applied"])
        self.assertEqual(entry["reason"], "too few unmasked points")
        self.assertIn("skipped", warning)
        # exactly at the threshold the correction still runs
        mask = dsm.MaskRaster(g)
        n = g.nx * g.ny
        keep = math.ceil(0.05 * n)
        for k in range(keep, n):
            mask.mask[k] = 1
        self.assertIsNotNone(dsm.correct_grid(g, mask)[0])
        mask.mask[keep - 1] = 1
        self.assertIsNone(dsm.correct_grid(g, mask)[0])

    def test_nothing_masked_is_not_applied(self):
        g = make_grid(ground)
        out, entry, warning = dsm.apply_correction(g, None)
        self.assertIs(out, g)
        self.assertFalse(entry["applied"])
        self.assertIsNone(warning)

    def test_nodata_is_never_filled(self):
        g = make_grid(ground)
        g.heights[3][4] = math.nan
        with self.assertRaises(NoDataError):
            dsm.apply_correction(g, True, buildings=[[square(0, 0, 10)]])

    def test_defaults_and_overrides(self):
        self.assertEqual(dsm.resolve(None, COPERNICUS), (True, "dsm source"))
        self.assertEqual(dsm.resolve(None, LOCAL), (False, "local file (opt-in off)"))
        self.assertEqual(dsm.resolve(True, LOCAL), (True, "local file (opt-in on)"))
        self.assertEqual(dsm.resolve(False, COPERNICUS), (False, "disabled"))
        self.assertEqual(dsm.resolve(True, COPERNICUS), (True, "dsm source"))
        with self.assertRaises(ValueError):
            dsm.resolve("yes", COPERNICUS)
        fp = [[square(0, 0, 10)]]
        for prov, requested, applied in ((COPERNICUS, None, True), (LOCAL, None, False), (LOCAL, True, True),
                                         (COPERNICUS, False, False)):
            g = make_grid(lambda x, y: ground(x, y) + (5.0 if max(abs(x), abs(y)) <= 10 else 0.0), prov=prov)
            _, entry, _ = dsm.apply_correction(g, requested, buildings=fp)
            self.assertEqual(entry["applied"], applied, (prov["provider"], requested))
            self.assertEqual(entry["setting"], {None: "auto", True: "on", False: "off"}[requested])

    def test_settings_validation_and_ui_mapping(self):
        self.assertIsNone(Settings().dsm_correction)
        self.assertFalse(Settings(dsm_correction=False).dsm_correction)
        with self.assertRaises(ValueError):
            Settings(dsm_correction="on")
        base = {"elevation_source": "copernicus", "osm_source": "overpass", "terrain_spacing": 10.0}
        self.assertIsNone(settings_kwargs(base, {})["dsm_correction"])
        self.assertIs(settings_kwargs(dict(base, dsm_correction="ON"), {})["dsm_correction"], True)
        self.assertIs(settings_kwargs(dict(base, dsm_correction="OFF"), {})["dsm_correction"], False)
        with self.assertRaises(SettingsInputError):
            settings_kwargs(dict(base, dsm_correction="MAYBE"), {})

    def test_large_fine_grid_is_bounded(self):
        """250 000 points, more than half masked (forest + buildings), in one call."""
        g = make_grid(ground, n=500, spacing=2.0)
        forests = [[square(-100, 0, 240)]]
        buildings = [[square(x, y, 6)] for x in range(100, 480, 40) for y in range(-480, 480, 40)]
        out, entry, _ = dsm.apply_correction(g, True, buildings=buildings, forests=forests)
        self.assertTrue(entry["applied"])
        self.assertGreater(entry["masked_points"], g.nx * g.ny // 2)
        for j in range(0, g.ny, 7):
            for i in range(0, g.nx, 7):
                self.assertLessEqual(out.heights[j][i], g.heights[j][i])
        # the fill is an approximation: inside a 480 m masked area on a 4 % slope it flattens the ground by
        # metres (documented limit), but never beyond the relief of the area
        self.assertLess(entry["max_lowering_m"], 0.04 * 480)


class PlanReportTest(unittest.TestCase):
    """build_plan with SYNTHETIC grids and hand-built classified features."""

    AREA = (47.0, 8.0, 100.0, 100.0)

    def classified(self):
        cl = Classified()
        cl.buildings.append(Feature("osm:way/1", "building", {"building": "yes", "height": "6"},
                                    Polygon(square(0, 0, 8))))
        cl.trees.append(Feature("osm:node/2", "tree", {"natural": "tree"}, (-35.0, 35.0)))
        cl.areas.append(Feature("osm:way/3", "area", {"landuse": "forest", "_class": "forest"},
                                Polygon(square(35, -35, 10))))
        cl.bridges.append(Feature("osm:way/4", "bridge", {"highway": "footway", "bridge": "yes"},
                                  [(-45.0, -40.0), (-20.0, -40.0)]))
        return cl

    def grid(self, prov):
        def h(x, y):
            return ground(x, y) + (12.0 if max(abs(x), abs(y)) <= 8 else 0.0)
        return make_grid(h, n=21, spacing=6.0, prov=prov)

    def test_report_and_provenance_when_applied(self):
        g = self.grid(COPERNICUS)
        plan = build_plan(Area(*self.AREA), g, self.classified(), PlanOptions(trees=False))
        tc = plan.report["terrain_correction"]
        for k in ("applied", "masked_points", "total_points", "max_lowering_m", "mean_lowering_m", "reason"):
            self.assertIn(k, tc)
        self.assertTrue(tc["applied"])
        self.assertEqual(tc["reason"], "dsm source")
        self.assertEqual(tc["total_points"], 21 * 21)
        self.assertEqual(tc["mask"]["features"], {"buildings": 1, "trees": 1, "forest_areas": 1, "bridges": 1})
        self.assertGreater(tc["max_lowering_m"], 10.0)
        terrain = next(o for o in plan.objects if o.mb_class == "terrain")
        self.assertEqual(terrain.provenance["surface"], DSM_CORRECTED_SURFACE)
        self.assertTrue(terrain.provenance["surface"].startswith("inferred:"))
        self.assertEqual(plan.report["inferred"].get("terrain.surface"), 1)
        # the building stands on the corrected ground, not on the DSM roof
        b = next(o for o in plan.objects if o.mb_class == "building")
        zmin = min(v[2] for v in b.mesh.vertices) + b.location[2] + plan.report["z_offset_m"]
        self.assertLess(zmin, ground(0, 0) + 1.0)
        json.dumps(plan.report)
        self.assertEqual(g.provenance, COPERNICUS)   # raw provenance untouched

    def test_report_when_not_applied(self):
        plan = build_plan(Area(*self.AREA), self.grid(LOCAL), self.classified(), PlanOptions(trees=False))
        tc = plan.report["terrain_correction"]
        self.assertFalse(tc["applied"])
        self.assertEqual(tc["reason"], "local file (opt-in off)")
        terrain = next(o for o in plan.objects if o.mb_class == "terrain")
        self.assertEqual(terrain.provenance["surface"], TERRAIN_SURFACE)
        plan = build_plan(Area(*self.AREA), self.grid(COPERNICUS), self.classified(), PlanOptions(trees=False),
                          dsm_correction=False)
        self.assertEqual(plan.report["terrain_correction"]["reason"], "disabled")

    def test_guard_warning_in_report(self):
        cl = Classified()
        cl.areas.append(Feature("osm:way/3", "area", {"landuse": "forest", "_class": "forest"},
                                Polygon(square(0, 0, 500))))
        plan = build_plan(Area(*self.AREA), self.grid(COPERNICUS), cl, PlanOptions(trees=False))
        self.assertFalse(plan.report["terrain_correction"]["applied"])
        self.assertEqual(plan.report["terrain_correction"]["reason"], "too few unmasked points")
        self.assertTrue(any("DSM terrain correction skipped" in w for w in plan.report["warnings"]))


class PipelineTest(unittest.TestCase):
    """Pipeline/CLI with the SYNTHETIC local fixtures (offline)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.osm, cls.dem, _ = write_synthetic_fixtures(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def settings(self, **kw):
        return Settings(elevation_source="file", elevation_file=self.dem, elevation_vertical_datum="SYNTHETIC",
                        elevation_license="SYNTHETIC test data (no licence required)", osm_source="file",
                        osm_file=self.osm, osm_license="SYNTHETIC fixture", plan_options=PlanOptions(seed=1), **kw)

    def area(self):
        return Area(47.0, 8.0, 400.0, 300.0)

    def test_local_file_default_off_and_opt_in(self):
        plan, sources = generate_plan(self.area(), self.settings())
        self.assertFalse(plan.report["terrain_correction"]["applied"])
        self.assertEqual(plan.report["terrain_correction"]["reason"], "local file (opt-in off)")
        self.assertNotIn("processing", sources[0])
        raw_sha = sources[0]["sha256"]
        plan_on, sources_on = generate_plan(self.area(), self.settings(dsm_correction=True))
        tc = plan_on.report["terrain_correction"]
        self.assertTrue(tc["applied"])
        self.assertEqual(tc["reason"], "local file (opt-in on)")
        self.assertIn("DSM terrain correction applied", sources_on[0]["processing"])
        self.assertEqual(sources_on[0]["sha256"], raw_sha)   # source hashes unchanged
        t_off = next(o for o in plan.objects if o.mb_class == "terrain").mesh.vertices
        t_on = next(o for o in plan_on.objects if o.mb_class == "terrain").mesh.vertices
        self.assertTrue(all(b[2] <= a[2] for a, b in zip(t_off, t_on)))
        self.assertTrue(any(b[2] < a[2] for a, b in zip(t_off, t_on)))

    def test_package_with_correction_validates(self):
        out = os.path.join(self.tmp.name, "dsm.mbmap")
        manifest, result = build_package(self.area(), self.settings(dsm_correction=True, heightfield_spacing=10.0),
                                         out, "dsm")
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(validate_package(out).ok)
        self.assertIn("processing", manifest["sources"][0])
        with zipfile.ZipFile(out) as z:
            report = json.loads(z.read("report.json"))
            notices = z.read("NOTICES.txt").decode("utf-8")
        self.assertTrue(report["terrain_correction"]["applied"])
        self.assertIn("Processing: DSM terrain correction applied", notices)
        terrain = next(o for o in manifest["objects"] if o["class"] == "terrain")
        self.assertTrue(terrain["provenance"]["surface"].startswith("inferred:DSM corrected"))

    def test_cli_flag(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mbmap_cli", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools",
                                      "mbmap_cli.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        common = ["build", "--osm", self.osm, "--dem", self.dem, "--datum", "SYNTHETIC", "--dem-license", "SYNTHETIC",
                  "--osm-license", "SYNTHETIC fixture", "--lat", "47.0", "--lon", "8.0", "--width", "400",
                  "--height", "300", "--heightfield", "0"]
        for flag, applied in (([], False), (["--dsm-correction"], True), (["--no-dsm-correction"], False)):
            out = os.path.join(self.tmp.name, f"cli{len(flag)}{applied}.mbmap")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(common + flag + ["--out", out]), 0)
            with zipfile.ZipFile(out) as z:
                tc = json.loads(z.read("report.json"))["terrain_correction"]
            self.assertEqual(tc["applied"], applied, flag)
            self.assertEqual(tc["setting"], {0: "auto"}.get(len(flag), "on" if applied else "off"))


if __name__ == "__main__":
    unittest.main()
