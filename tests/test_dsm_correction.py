"""DSM terrain correction (map_builder/core/dsm.py). All grids, footprints and OSM data here are SYNTHETIC."""

import contextlib
import io
import json
import math
import os
import random
import tempfile
import time
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
        # the ground is a plane with nothing raised on it: the harmonic fill reproduces it, so (almost) nothing
        # is lowered, even inside the 480 m forest on the 4 % slope
        self.assertLess(entry["max_lowering_m"], 0.5)


def _plane_with_square(n, spacing, half, cx=0.0, cy=0.0, bump=0.0):
    """SYNTHETIC grid of :func:`ground` (4 % slope in x) with a ``bump`` m raised block strictly inside the
    masked square (forest polygons leave their top edge row unmasked), and its mask."""
    def h(x, y):
        return ground(x, y) + (bump if abs(x - cx) < half and abs(y - cy) < half else 0.0)
    g = make_grid(h, n=n, spacing=spacing)
    return g, dsm.build_mask(g, forests=[[square(cx, cy, half)]])


def _max_error(g, rows, fn=ground):
    return max(abs(rows[j][i] - fn(x, y)) for i, j, x, y in points(g))


class HarmonicFillTest(unittest.TestCase):
    """SYNTHETIC checks that the fill interpolates (Laplace) and does not fabricate relief."""

    def test_slope_under_large_masked_square_is_reproduced(self):
        # 480 m square on the 4 % slope: 30 m spacing (GLO-30) and a fine 2 m grid
        for n, spacing, cx in ((41, 30.0, 0.0), (500, 2.0, -100.0)):
            g, mask = _plane_with_square(n, spacing, 240.0, cx=cx, cy=7.0)
            self.assertGreaterEqual(mask.count(), (480 / spacing) ** 2)
            filled = dsm.fill_masked(g.heights, mask.mask, g.nx, g.ny)
            self.assertLess(_max_error(g, filled), 0.5, spacing)
            out, stats = dsm.correct_grid(g, mask)
            self.assertLess(stats["max_lowering_m"], 0.5, spacing)
            self.assertLess(_max_error(g, out.heights), 0.5, spacing)

    def test_raised_block_on_slope_is_lowered_to_the_plane(self):
        for n, spacing in ((41, 30.0), (500, 2.0)):
            g, mask = _plane_with_square(n, spacing, 240.0, cx=-60.0, bump=20.0)
            out, entry, _ = dsm.apply_correction(g, True, forests=[[square(-60.0, 0.0, 240.0)]])
            self.assertTrue(entry["applied"])
            self.assertGreater(entry["max_lowering_m"], 19.5)
            self.assertLess(_max_error(g, out.heights), 0.5, spacing)

    def test_saddle_and_plane_boundaries_give_a_bounded_smooth_fill(self):
        def saddle(x, y):   # x^2 - y^2 is harmonic, also for the discrete 5-point Laplacian
            return 200.0 + (x * x - y * y) / 400.0

        for fn in (saddle, ground):
            g = make_grid(fn, n=161, spacing=2.0)
            mask = dsm.MaskRaster(g)
            for i, j, x, y in points(g):
                if math.hypot(x - 10, y + 6) <= 110 or (abs(x + 60) <= 20 and abs(y - 90) <= 40):
                    mask.mask[j * g.nx + i] = 1
            filled = dsm.fill_masked(g.heights, mask.mask, g.nx, g.ny)
            boundary = [g.heights[j][i] for i, j, _, _ in points(g) if not mask.mask[j * g.nx + i]
                        and any(mask.mask[jj * g.nx + ii] for ii, jj in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                                if 0 <= ii < g.nx and 0 <= jj < g.ny)]
            lo, hi = min(boundary), max(boundary)
            worst_lap = 0.0
            for i, j, _, _ in points(g):
                if mask.mask[j * g.nx + i]:
                    v = filled[j][i]
                    self.assertTrue(lo <= v <= hi, (fn.__name__, i, j, v, lo, hi))   # maximum principle
                    lap = filled[j][i - 1] + filled[j][i + 1] + filled[j - 1][i] + filled[j + 1][i] - 4 * v
                    worst_lap = max(worst_lap, abs(lap))
            self.assertLess(worst_lap, 0.01, fn.__name__)   # smooth: (nearly) zero discrete Laplacian
            self.assertLess(_max_error(g, filled, fn), 0.5, fn.__name__)
            self.assertEqual(filled, dsm.fill_masked(g.heights, mask.mask, g.nx, g.ny))   # deterministic

    def test_largest_grid_is_reproduced_in_bounded_time(self):
        """399 424 points (dem.MAX_GRID_POINTS is 400 000), 360 000 of them masked (a 900 m square)."""
        g, mask = _plane_with_square(632, 1.5, 450.0, cx=3.0, cy=5.0)
        self.assertLessEqual(g.nx * g.ny, 400_000)
        t0 = time.perf_counter()
        out, stats = dsm.correct_grid(g, mask)
        elapsed = time.perf_counter() - t0
        self.assertGreater(stats["masked_points"], 350_000)
        self.assertLess(stats["max_lowering_m"], 0.5)
        self.assertLess(_max_error(g, out.heights), 0.5)
        self.assertLess(elapsed, 60.0)   # a few seconds on a desktop; lenient for shared CI runners

    def test_small_odd_and_thin_grids_match_a_reference_solve(self):
        """Odd, thin (1-row / 1-column) and tiny grids with random masks against a plain Gauss-Seidel
        solve of the same equations (natural boundary at the grid edge) run to round-off."""
        def reference(h, m, nx, ny):
            u = [v for row in h for v in row]
            for _ in range(20000):
                d = 0.0
                for k in range(nx * ny):
                    if m[k]:
                        j, i = divmod(k, nx)
                        nb = [q for q, ok in ((k - 1, i > 0), (k + 1, i < nx - 1), (k - nx, j > 0),
                                              (k + nx, j < ny - 1)) if ok]
                        v = sum(u[q] for q in nb) / len(nb)
                        d, u[k] = max(d, abs(v - u[k])), v
                if d < 1e-10:
                    break
            return u
        rng = random.Random(3)
        for _ in range(120):
            nx, ny = rng.randint(1, 13), rng.randint(1, 13)
            if nx * ny < 2:
                continue
            h = [[rng.uniform(-50.0, 50.0) for _ in range(nx)] for _ in range(ny)]
            p = rng.random()
            m = bytearray(1 if rng.random() < p else 0 for _ in range(nx * ny))
            if all(m):
                m[rng.randrange(nx * ny)] = 0
            flat = [v for row in h for v in row]
            got = [v for row in dsm.fill_masked(h, m, nx, ny) for v in row]
            known = [v for v, q in zip(flat, m) if not q]
            self.assertEqual([v for v, q in zip(got, m) if not q], known)
            self.assertTrue(all(min(known) <= v <= max(known) for v in got))
            err = max(abs(a - b) for a, b in zip(got, reference(h, m, nx, ny)))
            self.assertLess(err, 0.05, (nx, ny, p))


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


def _idx(g, x, y):
    return int(round((y - g.y0) / g.spacing)) * g.nx + int(round((x - g.x0) / g.spacing))


class ReviewRound1Test(unittest.TestCase):
    """Regression tests for the PR #11 round-1 review findings. All data SYNTHETIC."""

    AREA = (47.0, 8.0, 100.0, 100.0)

    # --- finding 1: ring topology is validated before the mask is built -----------------------------------

    def test_invalid_forest_does_not_lower_terrain_outside_it(self):
        outer = square(0, 0, 20)
        hole = square(25, 0, 8)[::-1]      # CW hole crossing the outer ring at x = 20 (x 17..33)
        # the hazard: even-odd rasterising of these rings marks points outside the forest
        g = make_grid(ground, n=41, spacing=2.5)
        self.assertTrue(dsm.build_mask(g, forests=[[outer, hole]]).mask[_idx(g, 30, 0)])

        def h(x, y):   # 20 m "canopy" both inside the forest and in the crossing hole's outside part
            return ground(x, y) + (20.0 if max(abs(x), abs(y)) <= 20 or (20 < x <= 33 and abs(y) <= 8) else 0.0)
        g = make_grid(h, n=41, spacing=2.5)
        cl = Classified()
        cl.areas.append(Feature("osm:relation/9", "area", {"landuse": "forest", "_class": "forest"},
                                Polygon(outer, [hole])))
        plan = build_plan(Area(*self.AREA), g, cl, PlanOptions(trees=False))
        self.assertIn("osm:relation/9", {e["id"] for e in plan.report["invalid_features"]})
        tc = plan.report["terrain_correction"]
        self.assertEqual(tc["mask"]["features"]["forest_areas"], 0)
        self.assertEqual(tc["mask"]["excluded_invalid"], {"forest_areas": 1})
        self.assertFalse(tc["applied"])
        self.assertEqual(tc["reason"], "nothing to mask")
        terrain = next(o for o in plan.objects if o.mb_class == "terrain")
        z = plan.report["z_offset_m"]
        for (i, j, x, y), v in zip(points(g), terrain.mesh.vertices):
            self.assertAlmostEqual(v[2] + z, g.heights[j][i], places=6, msg=(x, y))

    def test_invalid_building_footprints_are_excluded_from_the_mask(self):
        bowtie = [(-10.0, -10.0), (10.0, 10.0), (10.0, -10.0), (-10.0, 10.0)]   # self-intersecting
        cl = Classified()
        cl.buildings.append(Feature("osm:way/1", "building", {"building": "yes"}, Polygon(bowtie)))
        cl.outside_buildings.append(Feature("osm:way/2", "building", {"building": "yes"},
                                            Polygon([(p[0] + 55.0, p[1]) for p in bowtie])))
        cl.buildings.append(Feature("osm:way/3", "building", {"building": "yes"}, Polygon(square(-30, -30, 4))))
        excluded = {}
        buildings, _, _, _ = dsm_obstacles(cl, excluded=excluded)
        self.assertEqual(buildings, [[square(-30, -30, 4)]])
        self.assertEqual(excluded, {"buildings": 2})
        # too many ring vertices: excluded like the generator would reject it
        excluded = {}
        buildings, _, _, _ = dsm_obstacles(cl, max_ring_vertices=3, excluded=excluded)
        self.assertEqual((buildings, excluded), ([], {"buildings": 3}))
        g = make_grid(lambda x, y: ground(x, y) + (9.0 if max(abs(x), abs(y)) <= 10 else 0.0), n=21, spacing=6.0)
        plan = build_plan(Area(*self.AREA), g, cl, PlanOptions(trees=False))
        tc = plan.report["terrain_correction"]
        self.assertEqual(tc["mask"]["features"]["buildings"], 1)
        self.assertEqual(tc["mask"]["excluded_invalid"], {"buildings": 2})
        terrain = next(o for o in plan.objects if o.mb_class == "terrain")
        z = plan.report["z_offset_m"]
        k = _idx(g, 0, 0)
        self.assertAlmostEqual(terrain.mesh.vertices[k][2] + z, g.heights[10][10], places=6)   # bowtie: unchanged

    # --- finding 2: rasteriser memory and work budget ------------------------------------------------------

    def test_many_holes_rasterise_in_bounded_memory(self):
        import tracemalloc
        nx, ny = 76, 2001
        g = ElevationGrid(0.0, 0.0, 1.0, nx, ny, [[0.0] * nx for _ in range(ny)], dict(COPERNICUS))
        outer = [(-1.0, -1.0), (77.0, -1.0), (77.0, 2002.0), (-1.0, 2002.0)]
        holes = [[(x, -0.5), (x, 2001.5), (x + 0.05, 2001.5), (x + 0.05, -0.5)]
                 for x in (0.52 + 0.15 * k for k in range(500))]          # 500 tall CW slivers
        tracemalloc.start()
        try:
            m = dsm.build_mask(g, forests=[[outer] + holes])
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 8 * 1024 * 1024, peak)   # the old all-crossings rasteriser used ~63 MiB
        for j in (0, 1000, 2000):
            for i in range(nx):
                inside_hole = any(x < i < x + 0.05 for x in (0.52 + 0.15 * k for k in range(500)))
                self.assertEqual(bool(m.mask[j * nx + i]), not inside_hole, (i, j))
        self.assertGreater(m.work, 1000 * ny)

    def test_work_budget_is_checked_before_any_terrain_change(self):
        from map_builder.core.errors import LimitError
        g = make_grid(lambda x, y: ground(x, y) + (9.0 if max(abs(x), abs(y)) <= 8 else 0.0))
        fp = [[square(0, 0, 8)]]
        need = dsm.build_mask(g, buildings=fp).work
        self.assertEqual(dsm.build_mask(g, buildings=fp, work_budget=need).work, need)
        with self.assertRaises(LimitError):
            dsm.build_mask(g, buildings=fp, work_budget=need - 1)
        before = [list(r) for r in g.heights]
        out, entry, warning = dsm.apply_correction(g, True, buildings=fp, work_budget=need - 1)
        self.assertIs(out, g)
        self.assertEqual(g.heights, before)
        self.assertFalse(entry["applied"])
        self.assertEqual(entry["reason"], "mask rasterisation work budget exceeded")
        self.assertIn("DSM terrain correction skipped", warning)
        out, entry, warning = dsm.apply_correction(g, True, buildings=fp, work_budget=need)
        self.assertTrue(entry["applied"])
        self.assertEqual(entry["mask"]["rasterisation_work"], need)

    # --- finding 3: the fill converges on elongated grids or is skipped -------------------------------------

    def test_elongated_grid_fill_converges_or_is_skipped(self):
        nx, ny, s = 5001, 51, 30.0

        def plane(x):
            return 100.0 + 0.04 * x
        heights = [[plane(i * s) + (20.0 if 500 <= i < 4500 else 0.0) for i in range(nx)] for _ in range(ny)]
        g = ElevationGrid(0.0, 0.0, s, nx, ny, heights, dict(COPERNICUS))
        mask = bytearray(1 if 500 <= i < 4500 else 0 for _ in range(ny) for i in range(nx))   # a 120 km strip
        out, stats = dsm.correct_grid(g, mask)
        self.assertIn("fill_cycles", stats)
        self.assertIn("fill_residual_m", stats)
        if out is None:
            self.assertEqual(stats["skipped"], "fill did not converge")
            self.assertFalse(stats["fill_converged"])
            return
        self.assertTrue(stats["fill_converged"])
        self.assertLessEqual(stats["fill_cycles"], dsm.vcycle_cap(nx, ny))
        err = max(abs(out.heights[j][i] - plane(i * s)) for j in range(ny) for i in range(nx))
        self.assertLess(err, 0.5)

    def test_fill_that_does_not_converge_is_not_applied(self):
        g, mask = _plane_with_square(129, 2.0, 50.0, bump=10.0)
        out, entry, warning = dsm.apply_correction(g, True, buildings=[[square(0, 0, 30)]])
        self.assertTrue(entry["applied"])
        self.assertTrue(entry["fill_converged"])
        self.assertGreaterEqual(entry["fill_cycles"], 1)
        self.assertLessEqual(entry["fill_residual_m"], dsm.VCYCLE_TOLERANCE_M)
        cap = dsm.vcycle_cap
        dsm.vcycle_cap = lambda nx, ny: 0
        try:
            out, entry, warning = dsm.apply_correction(g, True, buildings=[[square(0, 0, 30)]])
        finally:
            dsm.vcycle_cap = cap
        self.assertIs(out, g)
        self.assertFalse(entry["applied"])
        self.assertEqual(entry["reason"], "fill did not converge")
        self.assertFalse(entry["fill_converged"])
        self.assertEqual(entry["fill_cycles"], 0)
        self.assertGreater(entry["fill_residual_m"], dsm.VCYCLE_TOLERANCE_M)
        self.assertIn("did not converge", warning)

    # --- finding 4: mask candidates just outside the area ---------------------------------------------------

    def _edge_osm(self):
        b = OsmBuilder()
        ids = {"building": b.way(square(62, 0, 6), {"building": "yes"}, closed=True),   # x 56..68, area edge 50
               "tree": b.node(53.0, -20.0, {"natural": "tree"}),
               "bridge": b.way([(-70.0, -62.0), (70.0, -62.0)], {"highway": "primary", "bridge": "yes"}),
               "far": b.way(square(200, 0, 6), {"building": "yes"}, closed=True),
               "far_tree": b.node(80.0, 0.0, {"natural": "tree"})}
        return parse_osm_xml(b.xml().encode()), ids

    def test_features_just_outside_the_area_are_mask_candidates_only(self):
        data, ids = self._edge_osm()
        area = Area(*self.AREA)
        cl = classify(data, area, mask_extent=(-50.0, -50.0, 55.0, 55.0))
        self.assertEqual([f.id for f in cl.outside_buildings], [f"osm:way/{ids['building']}"])
        self.assertEqual([f.id for f in cl.mask_trees], [f"osm:node/{ids['tree']}"])
        self.assertEqual(cl.trees, [])
        self.assertEqual([f.id for f in cl.bridges], [f"osm:way/{ids['bridge']}"])
        self.assertTrue(all(abs(p[1] + 62.0) < 1e-3 for p in cl.bridges[0].geometry))
        self.assertEqual(cl.buildings, [])
        self.assertEqual(cl.roads, [])
        self.assertNotIn(f"osm:way/{ids['bridge']}", {u["id"] for u in cl.unsupported})   # outside the area
        # every candidate counts toward max_features
        from map_builder.core.errors import LimitError
        with self.assertRaises(LimitError):
            classify(data, area, max_features=2, mask_extent=(-50.0, -50.0, 55.0, 55.0))
        classify(data, area, max_features=3, mask_extent=(-50.0, -50.0, 55.0, 55.0))

        # edge samples under them are masked and lowered; none of them is generated
        def h(x, y):
            bump = 15.0 if (x >= 50 and abs(y) <= 6) or math.hypot(x - 53, y + 20) <= 3 or y <= -45 else 0.0
            return ground(x, y) + bump
        # -50..55: the grid overshoots the area by 5 m on the +x/+y sides
        g = ElevationGrid(-50.0, -50.0, 5.0, 22, 22, [[h(-50 + i * 5.0, -50 + j * 5.0) for i in range(22)]
                                                      for j in range(22)], dict(COPERNICUS))
        plan = build_plan(area, g, cl, PlanOptions(trees=True, seed=1))
        tc = plan.report["terrain_correction"]
        self.assertTrue(tc["applied"])
        self.assertEqual(tc["mask"]["features"], {"buildings": 1, "trees": 1, "forest_areas": 0, "bridges": 1})
        terrain = next(o for o in plan.objects if o.mb_class == "terrain")
        z = plan.report["z_offset_m"]
        for x, y in ((50.0, 0.0), (55.0, 0.0), (50.0, -20.0), (0.0, -50.0)):
            k = _idx(g, x, y)
            self.assertLess(terrain.mesh.vertices[k][2] + z, g.heights[k // g.nx][k % g.nx] - 5.0, (x, y))
        self.assertEqual([o.mb_class for o in plan.objects], ["terrain"])   # nothing generated outside

    def test_default_mask_extent_is_the_area(self):
        data, ids = self._edge_osm()
        cl = classify(data, Area(*self.AREA))
        self.assertEqual([f.id for f in cl.outside_buildings], [f"osm:way/{ids['building']}"])   # within 15 m
        self.assertEqual([f.id for f in cl.mask_trees], [f"osm:node/{ids['tree']}"])             # within 6 m
        self.assertEqual(len(cl.bridges), 1)

    def test_online_acquisition_fetches_the_grid_overshoot_plus_a_margin(self):
        from map_builder.core import pipeline
        seen = {}
        data, _ = self._edge_osm()

        def fake_fetch(area, client, *a, **kw):
            seen.update(kw)
            return data
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        _, dem, _ = write_synthetic_fixtures(tmp.name)
        orig = pipeline.fetch_overpass
        pipeline.fetch_overpass = fake_fetch
        try:
            settings = Settings(elevation_source="file", elevation_file=dem, elevation_vertical_datum="SYNTHETIC",
                                elevation_license="SYNTHETIC", terrain_spacing=30.0)
            grid, cl, _ = pipeline.acquire(Area(*self.AREA), settings, client=object())
        finally:
            pipeline.fetch_overpass = orig
        # 100 m at 30 m spacing: 5 points, -50..70, so the grid overshoots the area by 20 m
        self.assertEqual((grid.nx, grid.x0), (5, -50.0))
        self.assertEqual(seen["margin_m"], 50.0)
        self.assertTrue(all(abs(p[1] + 62.0) < 1e-3 for p in cl.bridges[0].geometry))

    # --- finding 5: lowered points and the provenance note --------------------------------------------------

    def test_lowered_points_and_note(self):
        from map_builder.core.pipeline import elevation_correction_note
        bump = make_grid(lambda x, y: ground(x, y) + (6.0 if math.hypot(x, y) <= 6.0 else 0.0), n=41, spacing=1.0)
        _, entry, _ = dsm.apply_correction(bump, True, trees=[(0.0, 0.0)])
        self.assertTrue(entry["applied"])
        self.assertGreater(entry["lowered_points"], 100)
        self.assertLessEqual(entry["lowered_points"], entry["masked_points"])
        note = elevation_correction_note(entry)
        self.assertIn(f"{entry['lowered_points']} of {entry['total_points']} terrain points", note)
        self.assertIn(f"{entry['masked_points']} masked", note)
        pit = make_grid(lambda x, y: ground(x, y) - (5.0 if math.hypot(x, y) <= 6.0 + 1e-6 else 0.0), n=41,
                        spacing=1.0)
        out, entry, _ = dsm.apply_correction(pit, True, trees=[(0.0, 0.0)])
        self.assertTrue(entry["applied"])
        self.assertGreater(entry["masked_points"], 100)
        self.assertEqual(entry["lowered_points"], 0)
        self.assertEqual(out.heights, pit.heights)
        note = elevation_correction_note(entry)
        self.assertIn("ran", note)
        self.assertIn("lowered no points", note)
        self.assertNotIn("were lowered", note)
        self.assertIsNone(elevation_correction_note({"applied": False}))


if __name__ == "__main__":
    unittest.main()
