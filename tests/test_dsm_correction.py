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
        # mask candidates are bounded separately from the content: over the limit they are dropped and the
        # correction skipped, never a LimitError (round 11)
        cl2 = classify(data, area, max_features=2, mask_extent=(-50.0, -50.0, 55.0, 55.0))
        self.assertEqual((cl2.bridges, cl2.outside_buildings, cl2.mask_trees), ([], [], []))
        self.assertIn("exceed the feature limit (2 features", cl2.mask_unavailable)
        self.assertIsNone(classify(data, area, max_features=3, mask_extent=(-50.0, -50.0, 55.0, 55.0))
                          .mask_unavailable)

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
        data, _ = self._edge_osm()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        _, dem, _ = write_synthetic_fixtures(tmp.name)

        def acquire(dsm_correction, spacing=30.0):
            calls, seen = [], {}

            def fake_fetch(area, client, *a, **kw):
                calls.append(kw)
                return data
            orig = pipeline.fetch_overpass
            orig_classify = pipeline.classify

            def spy_classify(*a, **kw):
                seen["mask_data"] = kw.get("mask_data")
                return orig_classify(*a, **kw)
            pipeline.fetch_overpass = fake_fetch
            pipeline.classify = spy_classify
            try:
                settings = Settings(elevation_source="file", elevation_file=dem, elevation_vertical_datum="SYNTHETIC",
                                    elevation_license="SYNTHETIC", terrain_spacing=spacing,
                                    dsm_correction=dsm_correction)
                grid, cl, _ = pipeline.acquire(Area(*self.AREA), settings, client=object())
            finally:
                pipeline.fetch_overpass = orig
                pipeline.classify = orig_classify
            return grid, cl, [c["margin_m"] for c in calls], seen
        grid, cl, margins, seen = acquire(True)
        # 100 m at 30 m spacing: 5 points, -50..70, so the grid overshoots the area by 20 m; review round 3,
        # finding 3: the mask margin covers the overshoot plus the widest mask reach (a bridge centreline up to
        # dsm.BRIDGE_CANDIDATE_MARGIN_M = 45 m from the grid), rounded up. Review round 5, finding 1: two
        # requests, the normal 30 m one (the content) and the wider one (mask candidates only)
        self.assertEqual((grid.nx, grid.x0), (5, -50.0))
        self.assertEqual(dsm.BRIDGE_CANDIDATE_MARGIN_M, 45.0)
        self.assertEqual(margins, [30.0, 65.0])
        self.assertIs(seen["mask_data"], data)
        self.assertTrue(all(abs(p[1] + 62.0) < 1e-3 for p in cl.bridges[0].geometry))
        # no overshoot (100 m at 25 m spacing: -50..50): still the full bridge reach, wider than the normal 30 m
        grid, _, margins, _ = acquire(True, spacing=25.0)
        self.assertEqual((grid.nx, grid.x0), (5, -50.0))
        self.assertEqual(margins, [30.0, 45.0])
        # review round 2, finding 2c: with the correction off (the local-file default, or explicitly) only the
        # normal 30 m request is made, and everything fetched is content
        for setting in (None, False):
            _, _, margins, seen = acquire(setting)
            self.assertEqual(margins, [30.0], setting)
            self.assertIsNone(seen["mask_data"], setting)

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


class ReviewRound2Test(unittest.TestCase):
    """Regression tests for the PR #11 round-2 review findings. All data SYNTHETIC."""

    AREA = (47.0, 8.0, 100.0, 100.0)

    # --- finding 1: only surface features outside the area enter the mask ---------------------------------

    def test_below_ground_footprints_outside_the_area_do_not_lower_terrain(self):
        g = make_grid(lambda x, y: 120.0 if (x, y) == (50.0, 0.0) else 100.0, n=21, spacing=5.0)   # -50..50
        cases = (({"building": "yes", "location": "underground"}, False), ({"building": "yes", "layer": "-1"}, False),
                 ({"building": "yes", "tunnel": "yes"}, False), ({"building": "yes"}, True))
        for tags, lowered in cases:
            b = OsmBuilder()
            b.way(square(56, 0, 3), tags, closed=True)     # x 53..59: 3 m outside the area, centroid outside
            area = Area(*self.AREA)
            cl = classify(parse_osm_xml(b.xml().encode()), area, mask_extent=(-50.0, -50.0, 50.0, 50.0))
            self.assertEqual(cl.outside, 1, tags)           # still counted as a footprint outside the area
            self.assertEqual(len(cl.outside_buildings), 1 if lowered else 0, tags)
            plan = build_plan(area, g, cl, PlanOptions(trees=False))
            terrain = next(o for o in plan.objects if o.mb_class == "terrain")
            z = terrain.mesh.vertices[_idx(g, 50.0, 0.0)][2] + plan.report["z_offset_m"]
            if lowered:
                self.assertAlmostEqual(z, 100.0, places=2)
            else:
                self.assertEqual(z, 120.0, tags)
                self.assertFalse(plan.report["terrain_correction"]["applied"])

    # --- finding 2: margin-only features are mask candidates only -----------------------------------------

    def test_margin_only_features_affect_only_the_mask(self):
        area = Area(*self.AREA)
        b = OsmBuilder()
        ids = {"forest": b.way(square(-70, 0, 15), {"landuse": "forest"}, closed=True),   # x -85..-55: in the margin
               "bldg": b.way(square(-70, 40, 3), {"building": "yes"}, closed=True),
               "m_forest": b.way(square(100, 0, 8), {"landuse": "forest"}, closed=True),  # x 92..108: margin-only
               "m_under": b.way(square(100, 30, 8), {"landuse": "forest", "layer": "-1"}, closed=True),
               "m_bldg": b.way(square(100, -30, 3), {"building": "yes"}, closed=True),
               "m_ug": b.way(square(100, -42, 3), {"building": "yes", "location": "underground"}, closed=True),
               "m_bowtie": b.way([(95, 40), (105, 50), (105, 40), (95, 50)], {"building": "yes"}, closed=True)}
        # a content multipolygon with a margin-only outer: its member ways come with it, so it is all content
        o1, o2 = b.way(square(-60, -30, 5), closed=True), b.way(square(-110, -30, 5), closed=True)
        rid = b._next()
        b.relations.append((rid, [("way", o1, "outer"), ("way", o2, "outer")],
                            {"type": "multipolygon", "landuse": "forest"}))
        data = parse_osm_xml(b.xml().encode())
        normal = _without(data, ways=[ids[k] for k in ids if k.startswith("m_")])   # the normal 30 m response
        extent = (-60.0, -50.0, 150.0, 50.0)
        cl = classify(normal, area, mask_extent=extent, mask_data=data)
        w = {k: f"osm:way/{v}" for k, v in ids.items()}
        self.assertEqual(sorted(f.id for f in cl.areas),
                         sorted([w["forest"], f"osm:relation/{rid}#0", f"osm:relation/{rid}#1"]))
        self.assertEqual([f.id for f in cl.mask_areas], [w["m_forest"]])   # below-ground forest excluded
        self.assertEqual(sorted(f.id for f in cl.outside_buildings), sorted([w["bldg"], w["m_bldg"]]))
        self.assertEqual(cl.outside, 1)                                   # margin-only footprints not counted
        self.assertEqual(cl.invalid, [])                                  # nor their problems reported
        self.assertEqual((cl.buildings, cl.trees, cl.roads), ([], [], []))
        _, _, forests, _ = dsm_obstacles(cl, extent=extent)
        self.assertEqual(len(forests), 3)   # forest, relation#0 (relation#1 is far from the grid), m_forest
        # without mask_data (a local file) everything is content
        cl = classify(data, area, mask_extent=extent)
        self.assertIn(w["m_forest"], {f.id for f in cl.areas})
        self.assertEqual(cl.mask_areas, [])
        self.assertEqual(cl.outside, 3)
        self.assertIn(w["m_bowtie"], {e["id"] for e in cl.invalid})

    def _scene_osm(self, wide):
        b = OsmBuilder()
        b.way(square(0, 0, 5), {"building": "yes"}, closed=True)
        b.way(square(30, -30, 8), {"landuse": "grass"}, closed=True)
        b.way(square(-30, 30, 12), {"landuse": "forest"}, closed=True)
        b.node(-20.0, 20.0, {"natural": "tree"})
        b.way([(-60.0, 10.0), (60.0, 10.0)], {"highway": "residential"})
        if wide:   # only in the response widened for the DSM margin (the area is 101 m wide: edge x = 50.5)
            b.way([(91.5, -60.0), (107.5, -60.0), (107.5, 60.0), (91.5, 60.0)], {"landuse": "forest"}, closed=True)
            b.way(square(140, -40, 4), {"building": "yes"}, closed=True)
            b.way([(95, 40), (105, 50), (105, 40), (95, 50)], {"building": "yes"}, closed=True)
            b.node(110.0, -20.0, {"natural": "tree"})
        return parse_osm_xml(b.xml().encode())

    def test_content_selection_is_identical_with_the_correction_on_or_off(self):
        # Parity covers the input OSM content and its selection. Here no building's eligibility depends on the
        # terrain (all roofs clear it either way), so the whole scene matches; terrain-dependent eligibility
        # (roof clearance) uses the corrected terrain, see ReviewRound6Test.test_correction_recovers_...
        from map_builder.core.dem import grid_layout
        from map_builder.core.generate import LANDCOVER_COLORS
        geo = (47.0, 8.0, 101.0, 100.0)
        x0, y0, nx, ny = grid_layout(Area(*geo), 100.0)
        self.assertEqual((x0, nx, ny), (-50.5, 3, 2))   # the grid overshoots to x = 149.5
        heights = [[130.0 if (i, j) == (2, 0) else 100.0 for i in range(nx)] for j in range(ny)]
        g = ElevationGrid(x0, y0, 100.0, nx, ny, heights, dict(COPERNICUS))
        extent = (x0, y0, x0 + (nx - 1) * 100.0, y0 + (ny - 1) * 100.0)
        plans = {}
        for on in (True, False):
            area = Area(*geo)
            cl = classify(self._scene_osm(wide=False), area, mask_extent=extent,
                          mask_data=self._scene_osm(wide=True) if on else None)
            plans[on] = build_plan(area, g, cl, PlanOptions(seed=3), dsm_correction=on)
        tc = plans[True].report["terrain_correction"]
        self.assertTrue(tc["applied"])
        self.assertEqual(tc["mask"]["features"]["forest_areas"], 2)   # the margin-only forest masks
        self.assertEqual(tc["mask"]["features"]["buildings"], 2)
        self.assertFalse(plans[False].report["terrain_correction"]["applied"])

        def scene(plan):
            objs = []
            for o in plan.objects:
                m = o.mesh
                prov = {k: v for k, v in o.provenance.items() if not (o.mb_class == "terrain" and k == "surface")}
                objs.append((o.name, o.mb_id, o.mb_class, o.collection, o.mesh_key, o.location[:2], o.rotation_z,
                             o.scale, json.dumps(prov, sort_keys=True, default=str),
                             None if m is None else (m.materials, m.faces, m.face_materials, m.face_colors,
                                                     [v[:2] for v in m.vertices])))
            report = {k: v for k, v in plan.report.items() if k not in ("terrain_correction", "z_offset_m")}
            report["warnings"] = [x for x in report.get("warnings", ()) if "DSM" not in x]
            report["inferred"] = {k: v for k, v in report.get("inferred", {}).items() if k != "terrain.surface"}
            return objs, json.loads(json.dumps(report, default=str))
        on, off = scene(plans[True]), scene(plans[False])
        self.assertEqual(on[0], off[0])
        self.assertEqual(on[1], off[1])
        terrain = next(o for o in plans[True].objects if o.mb_class == "terrain")
        # the overshoot cell (i 1, j 0; centre x 99.5) is not forest coloured
        self.assertEqual(terrain.mesh.face_colors[2], tuple(LANDCOVER_COLORS[None]))
        self.assertNotEqual(tuple(LANDCOVER_COLORS[None]), tuple(LANDCOVER_COLORS["forest"]))

    # --- finding 3: one shared mask validation work budget ------------------------------------------------

    def _holed(self, distinct, n=20):
        outer = square(75, 0, 24)
        holes = [square(52.0 + 1.5 * i, -22.0 + 1.5 * j, 0.4)[::-1] for i in range(30) for j in range(15)]   # 450
        cl = Classified()
        for k in range(n):
            dx = 0.001 * k if distinct else 0.0
            cl.outside_buildings.append(Feature(f"osm:relation/{k}", "building", {"building": "yes"},
                                                Polygon([(x + dx, y) for x, y in outer], [list(h) for h in holes])))
        return cl

    def test_mask_validation_is_charged_to_one_budget(self):
        extent = (-50.0, -50.0, 50.0, 50.0)
        stats = {}
        buildings, _, _, _ = dsm_obstacles(self._holed(False), extent=extent, stats=stats)
        self.assertEqual(len(buildings), 1)              # identical geometry validated and masked once
        one = stats["validation_work"]
        self.assertGreater(one, 100_000)
        stats = {}
        with self.assertRaises(dsm.MaskWorkExceeded):
            dsm_obstacles(self._holed(True), extent=extent, work_budget=3 * one, stats=stats)
        self.assertLessEqual(stats["validation_work"], 3 * one)
        # in the plan: skipped with a warning and a clear reason, terrain unchanged, quickly
        g = make_grid(lambda x, y: ground(x, y) + (10.0 if x >= 45 else 0.0), n=21, spacing=5.0)
        t = time.perf_counter()
        plan = build_plan(Area(*self.AREA), g, self._holed(True), PlanOptions(trees=False,
                                                                              max_mask_validation_work=1000))
        self.assertLess(time.perf_counter() - t, 2.0)
        tc = plan.report["terrain_correction"]
        self.assertFalse(tc["applied"])
        self.assertEqual(tc["reason"], "mask validation work budget exceeded")
        self.assertLessEqual(tc["mask"]["validation_work"], 1000)
        self.assertTrue(any("DSM terrain correction skipped" in x and "mask validation work budget" in x
                            for x in plan.report["warnings"]))
        terrain = next(o for o in plan.objects if o.mb_class == "terrain")
        z = plan.report["z_offset_m"]
        for (i, j, x, y), v in zip(points(g), terrain.mesh.vertices):
            self.assertAlmostEqual(v[2] + z, g.heights[j][i], places=6)
        # with the default budget the identical relations of the repro are validated once
        plan = build_plan(Area(*self.AREA), g, self._holed(False), PlanOptions(trees=False))
        tc = plan.report["terrain_correction"]
        self.assertTrue(tc["applied"])
        self.assertEqual(tc["mask"]["validation_work"], one)
        self.assertEqual(tc["mask"]["features"]["buildings"], 1)


def _star(cx, cy, r):
    """A self-intersecting pentagram (non-zero signed area)."""
    pts = [(cx + r * math.cos(math.pi / 2 + 2 * math.pi * k / 5), cy + r * math.sin(math.pi / 2 + 2 * math.pi * k / 5))
           for k in range(5)]
    return [pts[k] for k in (0, 2, 4, 1, 3)]


def _without(data, ways=(), relations=(), nodes=()):
    """``data`` minus the listed elements (and the untagged nodes nothing kept references): the response of a
    query that does not select them, in ``data``'s element order."""
    from map_builder.core.osm import OsmData
    sub = OsmData()
    sub.relations = {k: v for k, v in data.relations.items() if k not in set(relations)}
    sub.ways = {k: v for k, v in data.ways.items() if k not in set(ways)}
    used = {n for nids, _ in sub.ways.values() for n in nids}
    used.update(r for members, _ in sub.relations.values() for t, r, _ in members if t == "node")
    sub.nodes = {k: v for k, v in data.nodes.items() if k in used or (v[2] and k not in set(nodes))}
    sub.timestamp, sub.generator, sub.remarks, sub.source = data.timestamp, data.generator, data.remarks, data.source
    return sub


def _summary(cl):
    """Everything classify produces that affects generation or the report (mask candidates excluded)."""
    def poly(p):
        return [tuple(map(tuple, p.outer))] + [tuple(map(tuple, h)) for h in p.holes]
    return json.loads(json.dumps({
        "buildings": [(f.id, f.kind, f.tags, poly(f.geometry)) for f in cl.buildings],
        "areas": [(f.id, f.tags, poly(f.geometry)) for f in cl.areas],
        "roads": [(f.id, f.tags, f.geometry) for f in cl.roads],
        "trees": [(f.id, f.geometry) for f in cl.trees],
        "invalid": cl.invalid, "unsupported": cl.unsupported, "outside": cl.outside, "warnings": cl.warnings,
        "replaced": [getattr(f, "id", f) for f in cl.replaced_outlines],
        "outline_features": sorted(cl.outline_features), "outline_parts": cl.outline_parts,
        "outline_for": cl.outline_for, "overlaps": cl.overlap_candidates}, sort_keys=True, default=str))


class ReviewRound3Test(unittest.TestCase):
    """Regression tests for the PR #11 round-3 review findings. All data SYNTHETIC. The area is 100 m wide
    (edges at +-50 m); the normal-extent content bbox reaches about +-80 m, margin-only elements lie beyond 90 m."""

    AREA = (47.0, 8.0, 100.0, 100.0)
    EXTENT = (-50.0, -50.0, 150.0, 50.0)   # a grid overshooting the area by 100 m on +x

    # --- finding 1: the content is exactly the normal-extent response ---------------------------------------

    def _repro(self):
        """A building way in the area; an untagged multipolygon using it as an outer with an inner ring; a
        type=building relation with that multipolygon as outline and a margin-only way as part. None of the
        relations (nor the untagged inner way) is selected by the normal query."""
        b = OsmBuilder()
        w = b.way(square(0, 0, 10), {"building": "yes"}, closed=True)
        inner = b.way(square(0, 0, 3), closed=True)
        m = b._next()
        b.relations.append((m, [("way", w, "outer"), ("way", inner, "inner")], {"type": "multipolygon"}))
        part = b.way(square(100, 0, 4), {"building:part": "yes"}, closed=True)
        rel = b._next()
        b.relations.append((rel, [("relation", m, "outline"), ("way", part, "part")], {"type": "building"}))
        data = parse_osm_xml(b.xml().encode())
        return data, w, _without(data, ways=(inner, part), relations=(m, rel))

    def test_a_margin_only_relation_does_not_remove_a_building(self):
        data, w, normal = self._repro()
        area = Area(*self.AREA)
        self.assertEqual((list(normal.ways), list(normal.relations)), ([w], []))
        ref = classify(normal, area, mask_extent=self.EXTENT)
        self.assertEqual([f.id for f in ref.buildings], [f"osm:way/{w}"])
        self.assertEqual(ref.invalid, [])
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=data)
        self.assertEqual([f.id for f in cl.buildings], [f"osm:way/{w}"])
        self.assertEqual(cl.invalid, [])
        self.assertEqual(_summary(cl), _summary(ref))
        part = list(data.ways)[2]
        self.assertEqual([f.id for f in cl.outside_buildings], [f"osm:way/{part}"])   # a mask candidate only

    def _config_landcover(self):
        b = OsmBuilder()
        b.way(square(0, 0, 5), {"building": "yes"}, closed=True)
        forest = b.way(square(-30, 30, 15), {"landuse": "forest"}, closed=True)
        hole = b.way(square(-30, 30, 4), closed=True)
        m = b._next()   # untagged, so not selected: under the old-style rule it would suppress the forest way
        b.relations.append((m, [("way", forest, "outer"), ("way", hole, "inner")], {"type": "multipolygon"}))
        b.way([(-60.0, 10.0), (60.0, 10.0)], {"highway": "residential"})
        b.way([(-60.0, -20.0), (60.0, -20.0)], {"highway": "primary", "bridge": "yes"})   # unsupported, content
        b.node(-20.0, 20.0, {"natural": "tree"})
        margin = {"ways": [b.way(square(100, 0, 8), {"landuse": "forest"}, closed=True),
                           b.way(square(100, -30, 3), {"building": "yes"}, closed=True),
                           b.way(_star(100, 35, 6), {"building": "yes"}, closed=True),
                           b.way([(90.0, -45.0), (140.0, -45.0)], {"highway": "primary", "bridge": "yes"}),
                           b.way(square(130, 20, 3), {"building": "yes", "layer": "-1"}, closed=True)],
                  "nodes": [b.node(120.0, 0.0, {"natural": "tree"})], "relations": []}
        mo, mi = b.way(square(125, -20, 10), closed=True), b.way(square(125, -20, 3), closed=True)
        margin["ways"] += [mo, mi, hole]
        rid = b._next()
        b.relations.append((rid, [("way", mo, "outer"), ("way", mi, "inner")],
                            {"type": "multipolygon", "natural": "wood"}))
        margin["relations"] += [rid, m]
        data = parse_osm_xml(b.xml().encode())
        return data, _without(data, **margin)

    def _config_building_relations(self):
        b = OsmBuilder()
        outline = b.way(square(0, -25, 10), {"building": "yes"}, closed=True)
        x = b.way(square(0, -25, 4), {"building:part": "yes", "building:levels": "3"}, closed=True)
        # outside the content bbox, but a member of a selected type=building relation: content
        y = b.way(square(100, -25, 4), {"building:part": "yes"}, closed=True)
        r = b._next()
        b.relations.append((r, [("way", outline, "outline"), ("way", x, "part"), ("way", y, "part")],
                            {"type": "building"}))
        b.multipolygon(square(20, 20, 12), [square(20, 20, 4)], {"building": "yes"})
        margin = {"ways": [b.way(square(120, 0, 5), {"building": "yes"}, closed=True),
                           b.way(square(120, 0, 2), {"building:part": "yes"}, closed=True)]}
        r2 = b._next()
        b.relations.append((r2, [("way", margin["ways"][0], "outline"), ("way", margin["ways"][1], "part")],
                            {"type": "building"}))
        mo = b.way(square(110, 30, 6), {"building": "yes"}, closed=True)   # outer of a margin-only multipolygon
        mi = b.way(square(110, 30, 2), closed=True)
        r3 = b._next()
        b.relations.append((r3, [("way", mo, "outer"), ("way", mi, "inner")], {"type": "multipolygon",
                                                                                 "building": "yes"}))
        margin["ways"] += [mo, mi]
        margin["relations"] = [r2, r3]
        data = parse_osm_xml(b.xml().encode())
        return data, _without(data, **margin), y

    def _config_random(self, seed):
        rng = random.Random(seed)
        b = OsmBuilder()
        margin = {"ways": [], "nodes": []}
        tag_sets = ({"building": "yes"}, {"building:part": "yes"}, {"landuse": "forest"}, {"landuse": "grass"},
                    {"natural": "wood"}, {"building": "yes", "location": "underground"})
        for _ in range(40):
            inside = rng.random() < 0.5
            cx = rng.uniform(-60, 60) if inside else rng.uniform(95, 140)
            cy = rng.uniform(-60, 60) if inside else rng.uniform(-40, 40)
            ring = _star(cx, cy, 4) if rng.random() < 0.1 else square(cx, cy, rng.uniform(1.0, 8.0))
            wid = b.way(ring, dict(rng.choice(tag_sets)), closed=True)
            if not inside:
                margin["ways"].append(wid)
        for _ in range(20):
            inside = rng.random() < 0.5
            nid = b.node(rng.uniform(-49, 49) if inside else rng.uniform(95, 140), rng.uniform(-49, 49),
                         {"natural": "tree"})
            if not inside:
                margin["nodes"].append(nid)
        data = parse_osm_xml(b.xml().encode())
        return data, _without(data, **margin)

    def test_wide_classification_matches_the_normal_response(self):
        area = Area(*self.AREA)
        configs = {"repro": self._repro()[::2], "landcover": self._config_landcover(),
                   "building relations": self._config_building_relations()[:2]}
        configs.update({f"random {s}": self._config_random(s) for s in range(3)})
        for name, (wide, normal) in configs.items():
            with self.subTest(name):
                ref = classify(normal, area, mask_extent=self.EXTENT)
                cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide)
                self.assertEqual(_summary(cl), _summary(ref))
                self.assertTrue(ref.buildings or ref.areas)
                # the margin only adds mask candidates
                for key in ("outside_buildings", "mask_trees", "mask_areas", "bridges"):
                    ids = {f.id for f in getattr(cl, key)}
                    self.assertLessEqual({f.id for f in getattr(ref, key)}, ids, (name, key))

    def test_margin_only_elements_are_mask_candidates(self):
        area = Area(*self.AREA)
        wide, normal = self._config_landcover()
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide)
        margin_ways = [w for w in wide.ways if w not in normal.ways and wide.ways[w][1]]   # tagged ones
        forest, bldg, star, bridge, under = (f"osm:way/{w}" for w in margin_ways[:5])
        wood = next(f"osm:relation/{r}" for r, (_m, t) in wide.relations.items() if t.get("natural") == "wood")
        self.assertIn(f"osm:way/{list(normal.ways)[1]}", {f.id for f in cl.areas})   # the forest way is kept
        self.assertEqual(sorted(f.id for f in cl.mask_areas), sorted([forest, wood]))
        self.assertEqual(len(next(f for f in cl.mask_areas if f.id == wood).geometry.holes), 1)
        self.assertEqual(sorted(f.id for f in cl.outside_buildings), sorted([bldg, star]))   # layer=-1 excluded
        self.assertIn(bridge, {f.id for f in cl.bridges})
        self.assertEqual(len(cl.mask_trees), 1)
        # the self-intersecting margin-only footprint is rejected by the budgeted mask validation
        excluded = {}
        buildings, trees, forests, bridges = dsm_obstacles(cl, extent=self.EXTENT, excluded=excluded)
        self.assertEqual(excluded.get("buildings"), 1)
        self.assertEqual(len(forests), 2)   # margin forest, margin wood relation
        # review round 4, finding 2: the content forest way is the outer of a margin-only untagged multipolygon
        # with an inner ring (old-style tagging): as in the scene, its solid copy never fills that hole
        self.assertEqual(cl.mask_suppressed, {f"osm:way/{list(normal.ways)[1]}"})

    def test_building_relation_members_outside_the_bbox_stay_content(self):
        area = Area(*self.AREA)
        wide, normal, y = self._config_building_relations()
        self.assertIn(y, normal.ways)
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide)
        self.assertEqual(cl.outside, 1)   # the far part, counted as in the normal response
        self.assertEqual(_summary(cl), _summary(classify(normal, area, mask_extent=self.EXTENT)))

    # --- finding 2: margin-only polygons are not topology checked in classify ---------------------------

    def _shared_ring(self):
        b = OsmBuilder()
        ring = b.way([(110.0 + 20.0 * math.cos(2 * math.pi * k / 1500), 20.0 * math.sin(2 * math.pi * k / 1500))
                      for k in range(1500)], closed=True)
        rels = []
        for _ in range(5):
            rels.append(b._next())
            b.relations.append((rels[-1], [("way", ring, "outer")], {"type": "multipolygon", "landuse": "forest"}))
        b.way(square(0, 0, 5), {"building": "yes"}, closed=True)
        data = parse_osm_xml(b.xml().encode())
        return data, _without(data, ways=[ring], relations=rels)

    def test_margin_only_multipolygons_sharing_a_large_ring_classify_quickly(self):
        area = Area(*self.AREA)
        data, normal = self._shared_ring()
        t = time.perf_counter()
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=data)
        self.assertLess(time.perf_counter() - t, 2.0)
        self.assertEqual(len(cl.mask_areas), 5)
        self.assertEqual(len(cl.buildings), 1)
        self.assertEqual(cl.invalid, [])
        # the grid: -50..150 x -50..50 at 10 m; 30 m high bumps under the ring
        nx, ny = 21, 11
        heights = [[100.0 + (30.0 if math.hypot(-50 + i * 10.0 - 110.0, -50 + j * 10.0) < 19 else 0.0)
                    for i in range(nx)] for j in range(ny)]
        g = ElevationGrid(-50.0, -50.0, 10.0, nx, ny, heights, dict(COPERNICUS))
        # default budget: the shared ring is validated once (deduplicated) and masks
        plan = build_plan(area, g, cl, PlanOptions(trees=False))
        tc = plan.report["terrain_correction"]
        self.assertTrue(tc["applied"])
        self.assertEqual(tc["mask"]["features"]["forest_areas"], 1)
        self.assertLess(tc["mask"]["validation_work"], dsm.MASK_VALIDATION_WORK_BUDGET)
        # exhausted budget: the correction is skipped with the usual warning, never raising or stalling
        t = time.perf_counter()
        plan = build_plan(area, g, cl, PlanOptions(trees=False, max_mask_validation_work=1000))
        self.assertLess(time.perf_counter() - t, 2.0)
        tc = plan.report["terrain_correction"]
        self.assertFalse(tc["applied"])
        self.assertEqual(tc["reason"], "mask validation work budget exceeded")
        self.assertTrue(any("DSM terrain correction skipped" in x and "mask validation work budget" in x
                            for x in plan.report["warnings"]))
        terrain = next(o for o in plan.objects if o.mb_class == "terrain")
        z = plan.report["z_offset_m"]
        for (i, j, x, y), v in zip(points(g), terrain.mesh.vertices):
            self.assertAlmostEqual(v[2] + z, g.heights[j][i], places=6)

    def test_content_polygons_keep_their_topology_checks(self):
        area = Area(*self.AREA)
        b = OsmBuilder()
        star = b.way(_star(0, 0, 10), {"building": "yes"}, closed=True)
        data = parse_osm_xml(b.xml().encode())
        cl = classify(data, area, mask_extent=self.EXTENT, mask_data=data)
        self.assertEqual(cl.invalid, [{"id": f"osm:way/{star}", "reason": "self-intersecting ring"}])
        self.assertEqual(cl.buildings, [])


class ReviewRound4Test(unittest.TestCase):
    """Regression tests for the PR #11 round-4 review findings. All data SYNTHETIC. As in round 3, the area is
    100 m wide and the normal-extent content bbox reaches about +-80 m."""

    AREA = (47.0, 8.0, 100.0, 100.0)
    EXTENT = (-50.0, -50.0, 150.0, 50.0)

    # --- finding 1: margin-only ring assembly and hole assignment are budgeted ------------------------------

    def _holed_outers(self, stacked):
        """One margin-only building multipolygon with 3000 4-vertex outers, one hole each: disjoint (a 60 x 50
        lattice at 1 m) or ``stacked`` (all covering the same spot, so every hole lies in every outer)."""
        b = OsmBuilder()
        b.way(square(0, 0, 5), {"building": "yes"}, closed=True)
        members = []
        for k in range(3000):
            cx, cy = (110.0 + 0.0001 * k, 0.0) if stacked else (92.0 + k % 60, -25.0 + k // 60)
            members.append(("way", b.way(square(cx, cy, 0.4), closed=True), "outer"))
            members.append(("way", b.way(square(cx, cy, 0.1), closed=True), "inner"))
        b.relations.append((b._next(), members, {"type": "multipolygon", "building": "yes"}))
        data = parse_osm_xml(b.xml().encode())
        return data, _without(data, ways=[r for _t, r, _role in members], relations=[b._id])

    def _grid(self):
        nx, ny = 21, 11
        heights = [[100.0 + (8.0 if -50 + i * 10.0 >= 90 else 0.0) for i in range(nx)] for j in range(ny)]
        return ElevationGrid(-50.0, -50.0, 10.0, nx, ny, heights, dict(COPERNICUS))

    def test_disjoint_holed_outers_are_assigned_quickly(self):
        area = Area(*self.AREA)
        data, normal = self._holed_outers(stacked=False)
        t = time.perf_counter()
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=data)
        self.assertLess(time.perf_counter() - t, 2.0)
        self.assertIsNone(cl.mask_work_exceeded)
        self.assertEqual(len(cl.outside_buildings), 3000)
        self.assertTrue(all(len(f.geometry.holes) == 1 for f in cl.outside_buildings))
        self.assertLess(cl.mask_work, 200_000)
        self.assertEqual(_summary(cl), _summary(classify(normal, area, mask_extent=self.EXTENT)))
        stats = {}
        dsm_obstacles(cl, extent=self.EXTENT, stats=stats)
        self.assertGreaterEqual(stats["validation_work"], cl.mask_work)   # one budget, continued

    def test_exhausted_assembly_budget_skips_the_correction(self):
        area = Area(*self.AREA)
        data, normal = self._holed_outers(stacked=True)
        t = time.perf_counter()
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=data)
        # bounded by the whole budget (about 2 s of mask validation work), so a looser bound than the repro's
        self.assertLess(time.perf_counter() - t, 4.0)
        self.assertIn("mask validation work budget", cl.mask_work_exceeded)
        self.assertEqual(cl.mask_work, dsm.MASK_VALIDATION_WORK_BUDGET)
        ref = classify(normal, area, mask_extent=self.EXTENT)
        self.assertEqual(_summary(cl), _summary(ref))   # generated content unaffected
        g = self._grid()
        plan = build_plan(area, g, cl, PlanOptions(trees=False))
        tc = plan.report["terrain_correction"]
        self.assertFalse(tc["applied"])
        self.assertEqual(tc["reason"], "mask validation work budget exceeded")
        self.assertEqual(tc["mask"]["validation_work"], dsm.MASK_VALIDATION_WORK_BUDGET)
        self.assertTrue(any("DSM terrain correction skipped: DSM mask candidate assembly" in x
                            for x in plan.report["warnings"]))
        terrain = next(o for o in plan.objects if o.mb_class == "terrain")
        z = plan.report["z_offset_m"]
        for (i, j, x, y), v in zip(points(g), terrain.mesh.vertices):
            self.assertAlmostEqual(v[2] + z, g.heights[j][i], places=6)
        # a smaller budget is shared the same way (pipeline passes PlanOptions.max_mask_validation_work)
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=data, max_mask_work=1000)
        self.assertEqual(cl.mask_work, 1000)
        plan = build_plan(area, g, cl, PlanOptions(trees=False, max_mask_validation_work=1000))
        self.assertEqual(plan.report["terrain_correction"]["reason"], "mask validation work budget exceeded")

    def test_assembly_of_many_open_member_ways_is_budgeted(self):
        area = Area(*self.AREA)
        b = OsmBuilder()
        b.way(square(0, 0, 5), {"building": "yes"}, closed=True)
        # a 1500-vertex ring around (115, 0) split into 1500 one-segment member ways, listed in reverse order
        n = 1500
        pts = [(115.0 + 20.0 * math.cos(2 * math.pi * k / n), 20.0 * math.sin(2 * math.pi * k / n))
               for k in range(n)]
        ids = [b.node(x, y) for x, y in pts]
        ways = []
        for k in range(n):
            wid = b._next()
            b.ways.append((wid, [ids[k], ids[(k + 1) % n]], {}))
            ways.append(wid)
        rid = b._next()
        b.relations.append((rid, [("way", w, "outer") for w in reversed(ways)],
                            {"type": "multipolygon", "landuse": "forest"}))
        data = parse_osm_xml(b.xml().encode())
        normal = _without(data, ways=ways, relations=[rid])
        t = time.perf_counter()
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=data, max_mask_work=100_000)
        self.assertLess(time.perf_counter() - t, 2.0)
        self.assertIsNotNone(cl.mask_work_exceeded)
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=data)
        self.assertIsNone(cl.mask_work_exceeded)
        self.assertEqual([f.id for f in cl.mask_areas], [f"osm:relation/{rid}"])

    # --- finding 2: a content outline never fills a courtyard known only to the wider response ---------------

    def _courtyard(self):
        """A type=building relation (selected by its part P in the area) with outline W, a building way
        enclosing the normal bbox; a building multipolygon M (outer W, courtyard H around (98, 24) on the
        grid overshoot side), selected only by the wide query."""
        b = OsmBuilder()
        w = b.way(square(30, 0, 125), {"building": "yes"}, closed=True)   # x -95..155, y -125..125
        p = b.way(square(0, 0, 10), {"building:part": "yes"}, closed=True)
        h = b.way(square(101, 24, 20), closed=True)   # x 81..121: outside the normal bbox; (98, 24) 17 m inside
        m = b._next()
        b.relations.append((m, [("way", w, "outer"), ("way", h, "inner")], {"type": "multipolygon",
                                                                            "building": "yes"}))
        r = b._next()
        b.relations.append((r, [("way", w, "outline"), ("way", p, "part")], {"type": "building"}))
        data = parse_osm_xml(b.xml().encode())
        return data, _without(data, ways=[h], relations=[m]), w

    def test_a_content_outline_does_not_fill_a_margin_only_courtyard(self):
        from map_builder.core.dem import grid_layout
        area = Area(*self.AREA)
        x0, y0, nx, ny = grid_layout(area, 74.0)
        self.assertEqual((x0, y0, nx, ny), (-50.0, -50.0, 3, 3))   # points at -50, 24, 98
        extent = (x0, y0, x0 + 148.0, y0 + 148.0)
        data, normal, w = self._courtyard()
        cl = classify(normal, area, mask_extent=extent, mask_data=data)
        ref = classify(normal, area, mask_extent=extent)
        self.assertEqual(_summary(cl), _summary(ref))       # the scene still uses W (replaced by its part)
        self.assertIn(f"osm:way/{w}", cl.outline_features)
        self.assertEqual(cl.mask_suppressed, {f"osm:way/{w}"})
        heights = [[100.0 + (0.0 if (i, j) == (2, 1) else 10.0) for i in range(nx)] for j in range(ny)]
        g = ElevationGrid(x0, y0, 74.0, nx, ny, heights, dict(COPERNICUS))
        plan = build_plan(area, g, cl, PlanOptions(trees=False))
        tc = plan.report["terrain_correction"]
        self.assertTrue(tc["applied"], tc)
        self.assertEqual(tc["masked_points"], 8)             # every point but the courtyard one, (98, 24)
        terrain = next(o for o in plan.objects if o.mb_class == "terrain")
        z = terrain.mesh.vertices[_idx(g, 98.0, 24.0)][2] + plan.report["z_offset_m"]
        self.assertAlmostEqual(z, 100.0, places=6)
        # the same for a forest outer of a margin-only wood multipolygon (the clearing stays unmasked)
        b = OsmBuilder()
        fw = b.way(square(30, 0, 125), {"landuse": "forest"}, closed=True)
        fp = b.way(square(0, 0, 3), {"building:part": "yes"}, closed=True)
        hole = b.way(square(101, 24, 20), closed=True)
        rel = b._next()
        b.relations.append((rel, [("way", fw, "outer"), ("way", hole, "inner")], {"type": "multipolygon",
                                                                                  "landuse": "forest"}))
        b.relations.append((b._next(), [("way", fw, "outline"), ("way", fp, "part")], {"type": "building"}))
        data = parse_osm_xml(b.xml().encode())
        cl = classify(_without(data, ways=[hole], relations=[rel]), area, mask_extent=extent, mask_data=data)
        self.assertIn(f"osm:way/{fw}", {f.id for f in cl.areas})
        self.assertEqual(cl.mask_suppressed, {f"osm:way/{fw}"})
        tc = build_plan(area, g, cl, PlanOptions(trees=False)).report["terrain_correction"]
        self.assertEqual(tc["masked_points"], 8)


def _assemble_rings_round4(way_lists):
    """The round-4 ring assembly (front removal, list prepends), unbudgeted: the reference that the content
    path's results must still equal."""
    segs = [list(w) for w in way_lists if len(w) >= 2]
    rings, ok = [], True
    while segs:
        cur = segs.pop(0)
        guard = 0
        while cur[0] != cur[-1]:
            guard += 1
            if guard > 10000:
                ok = False
                break
            for k, s in enumerate(segs):
                if s[0] == cur[-1]:
                    cur.extend(s[1:])
                elif s[-1] == cur[-1]:
                    cur.extend(reversed(s[:-1]))
                elif s[-1] == cur[0]:
                    cur[:0] = s[:-1]
                elif s[0] == cur[0]:
                    cur[:0] = list(reversed(s[1:]))
                else:
                    continue
                segs.pop(k)
                break
            else:
                ok = False
                break
        if cur[0] == cur[-1] and len(cur) >= 4:
            rings.append(cur)
        else:
            ok = False
    return rings, ok


class ReviewRound5Test(unittest.TestCase):
    """Regression tests for the PR #11 round-5 review findings. All data SYNTHETIC."""

    AREA = (47.0, 8.0, 100.0, 100.0)
    EXTENT = (-50.0, -50.0, 150.0, 50.0)

    # --- finding 1: the content is the normal response itself; the wider one only adds mask candidates -------

    def _dateline(self, lons):
        """A building in ``Area(0, 179.98, 100, 100)`` and a ``man_made=bridge`` way at latitude 0 through
        ``lons``, which leaves the normal bbox eastward across the antimeridian: in the wide response only."""
        from map_builder.core.geodesy import LocalFrame
        b = OsmBuilder(LocalFrame(0.0, 179.98))
        b.way(square(0, 0, 5), {"building": "yes"}, closed=True)
        ids = []
        for lon in lons:
            ids.append(b._next())
            b.nodes.append((ids[-1], 0.0, lon, {}))
        bridge = b._next()
        b.ways.append((bridge, ids, {"man_made": "bridge"}))
        data = parse_osm_xml(b.xml().encode())
        return data, _without(data, ways=[bridge])

    def test_content_equals_the_normal_response_classification(self):
        dateline = Area(0.0, 179.98, 100.0, 100.0)
        bb = dateline.geographic_bbox(margin_m=30.0)
        self.assertLess(bb[3], 180.0)
        cases = {"round 5 dateline": (dateline, None, self._dateline((179.9790, 179.9792, -179.9999))),
                 "round 4 dateline": (dateline, None, self._dateline((179.9808, -179.9999))),
                 "round 3 repro": (Area(*self.AREA), self.EXTENT, ReviewRound3Test._repro(self)[::2])}
        self.assertLess(179.9792, bb[1])   # the round-5 way's nodes all lie outside the normal bbox
        for name, (area, extent, (wide, normal)) in cases.items():
            with self.subTest(name):
                ref = classify(normal, area, mask_extent=extent)
                cl = classify(normal, area, mask_extent=extent, mask_data=wide)
                self.assertEqual(_summary(cl), _summary(ref))
                self.assertEqual(len(cl.buildings), 1)
                if "dateline" in name:
                    self.assertEqual(cl.unsupported, [])   # before (round 5): a man_made=bridge entry

    def _fixture(self):
        b = OsmBuilder()
        b.way(square(0, 0, 5), {"building": "yes"}, closed=True)
        b.node(-20.0, 20.0, {"natural": "tree"})
        normal = b.xml().encode()
        # scripted: only in the wide response, so mask candidates (within the grid extent, x <= 70)
        b.way(square(62, 0, 6), {"building": "yes"}, closed=True)
        b.node(65.0, 0.0, {"natural": "tree"})
        return normal, b.xml().encode()

    def _acquire(self, responses, dsm_correction, cache_dir=""):
        from map_builder.core import pipeline
        from map_builder.core.http import HttpClient, Response
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        _, dem, _ = write_synthetic_fixtures(tmp.name)

        class Transport:
            def __init__(self):
                self.queries = []

            def request(self, method, url, headers, data, timeout, max_bytes):
                import urllib.parse
                self.queries.append(urllib.parse.parse_qs(data.decode("ascii"))["data"][0])
                status, body = responses.pop(0)
                return Response(status, body)
        tr = Transport()
        settings = Settings(elevation_source="file", elevation_file=dem, elevation_vertical_datum="SYNTHETIC",
                            elevation_license="SYNTHETIC", terrain_spacing=30.0, dsm_correction=dsm_correction,
                            cache_dir=cache_dir)
        grid, cl, sources = pipeline.acquire(Area(*self.AREA), settings, client=HttpClient(tr))
        return grid, cl, sources, tr.queries

    def test_two_requests_share_the_normal_query_and_cache(self):
        from map_builder.core.osm import OSM_LICENSE, overpass_query
        import hashlib
        normal, wide = self._fixture()
        area = Area(*self.AREA)
        q30, q65 = (overpass_query(*area.geographic_bbox(margin_m=m)) for m in (30.0, 65.0))
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        _, off, src_off, queries = self._acquire([(200, normal)], False, cache.name)
        self.assertEqual(queries, [q30])                        # off: one request, the normal 30 m query
        self.assertNotIn("dsm_mask_query", src_off[1])
        _, on, src_on, queries = self._acquire([(200, wide)], True, cache.name)
        self.assertEqual(queries, [q65])                        # on: the normal query is served from the cache
        self.assertTrue(src_on[1]["from_cache"])
        self.assertEqual(src_on[1]["query_sha256"], src_off[1]["query_sha256"])
        mq = src_on[1]["dsm_mask_query"]
        self.assertEqual(mq["margin_m"], 65.0)
        self.assertEqual(mq["query_sha256"], hashlib.sha256(q65.encode("utf-8")).hexdigest())
        self.assertFalse(mq["from_cache"])
        self.assertEqual(mq["osm_base_timestamp"], "2026-01-01T00:00:00Z")
        self.assertIn("mask candidates only", mq["purpose"])
        self.assertEqual(src_on[1]["license"], OSM_LICENSE)    # one dataset, one licence and attribution
        self.assertEqual(_summary(on), _summary(off))
        self.assertEqual(len(on.outside_buildings), 1)
        self.assertEqual(len(on.mask_trees), 1)
        self.assertEqual((off.outside_buildings, off.mask_trees), ([], []))
        # no cache: both requests go out, normal first
        _, _, _, queries = self._acquire([(200, normal), (200, wide)], True)
        self.assertEqual(queries, [q30, q65])

    def test_a_failed_mask_request_skips_the_correction_with_a_warning(self):
        normal, _wide = self._fixture()
        partial = normal.replace(b"</osm>", b"<remark>runtime error: Query timed out</remark></osm>")
        for name, resp in (("HTTP 429", (429, b"")), ("server remark", (200, partial))):
            with self.subTest(name):
                grid, cl, sources, queries = self._acquire([(200, normal), resp], True)
                self.assertEqual(len(queries), 2)
                mq = sources[1]["dsm_mask_query"]
                self.assertIn("error", mq)
                self.assertNotIn("query_sha256", mq)
                self.assertIn("DSM mask request", cl.mask_unavailable)
                self.assertEqual(len(cl.buildings), 1)            # the content stands
                heights = [[100.0 + (10.0 if math.hypot(-50 + i * 30.0, -50 + j * 30.0) < 20 else 0.0)
                            for i in range(grid.nx)] for j in range(grid.ny)]
                g = ElevationGrid(grid.x0, grid.y0, grid.spacing, grid.nx, grid.ny, heights, dict(COPERNICUS))
                plan = build_plan(Area(*self.AREA), g, cl, PlanOptions(trees=False), dsm_correction=True)
                tc = plan.report["terrain_correction"]
                self.assertFalse(tc["applied"])
                self.assertEqual(tc["reason"], "mask candidates unavailable")
                self.assertTrue(any(w.startswith("DSM terrain correction skipped: the DSM mask request")
                                    for w in plan.report["warnings"]))
                terrain = next(o for o in plan.objects if o.mb_class == "terrain")
                z = plan.report["z_offset_m"]
                for (i, j, x, y), v in zip(points(g), terrain.mesh.vertices):
                    self.assertAlmostEqual(v[2] + z, g.heights[j][i], places=6)
        # a failed normal (content) request still fails the acquisition, as with the correction off
        from map_builder.core.errors import NetworkError
        with self.assertRaises(NetworkError):
            self._acquire([(429, b"")], True)

    # --- finding 2: ring assembly charges before copying and has no uncharged quadratic work ----------------

    def test_many_closed_members_are_bounded(self):
        from map_builder.core.osm import _assemble_rings, _MaskWork, _MaskWorkExhausted
        members = [[4 * k + 1, 4 * k + 2, 4 * k + 3, 4 * k + 1] for k in range(50_000)]
        work = _MaskWork(dsm.MASK_VALIDATION_WORK_BUDGET)
        t = time.perf_counter()
        rings, ok = _assemble_rings(members, work)
        self.assertLess(time.perf_counter() - t, 1.0)       # 8.7 s before (in classify)
        self.assertTrue(ok)
        self.assertEqual(len(rings), 50_000)
        self.assertEqual(work.n, 50_000 * 5)                 # each member and its vertices
        # a small budget runs out on the first members, before the rest are copied
        work = _MaskWork(1000)
        t = time.perf_counter()
        with self.assertRaises(_MaskWorkExhausted):
            _assemble_rings(members, work)
        self.assertLess(time.perf_counter() - t, 0.1)
        self.assertLessEqual(work.n, 1005)

    def test_joining_open_members_is_charged(self):
        from map_builder.core.osm import _assemble_rings, _MaskWork
        n = 1500
        members = [[(k + 1) % n, (k + 2) % n] for k in reversed(range(n))]   # one-segment ways, reverse order
        work = _MaskWork(10 ** 9)
        rings, ok = _assemble_rings(members, work)
        self.assertTrue(ok)
        self.assertEqual(len(rings), 1)
        self.assertGreaterEqual(work.n, n * (n - 1) // 2)    # every scan of the remaining members is charged

    def test_content_assembly_is_unchanged(self):
        from map_builder.core.osm import _assemble_rings
        rng = random.Random(5)
        for _ in range(500):
            members = []
            for _ in range(rng.randint(0, 12)):
                w = [rng.randint(0, 9) for _ in range(rng.randint(1, 5))]
                if rng.random() < 0.3 and len(w) >= 3:
                    w.append(w[0])
                members.append(w)
            self.assertEqual(_assemble_rings(members), _assemble_rings_round4(members), members)
        # and a ring split into many members in shuffled order
        for seed in range(20):
            ids = list(range(200))
            segs = [[ids[k], ids[(k + 1) % 200]] for k in range(200)]
            random.Random(seed).shuffle(segs)
            segs = [s[::-1] if random.Random(seed + k).random() < 0.5 else s for k, s in enumerate(segs)]
            self.assertEqual(_assemble_rings(segs), _assemble_rings_round4(segs))


class ReviewRound6Test(unittest.TestCase):
    """Regression tests for the PR #11 round-6 review findings. All data SYNTHETIC."""

    AREA = (47.0, 8.0, 100.0, 100.0)

    # --- finding 1: roof clearance uses the corrected terrain (intended) -------------------------------------

    def test_correction_recovers_a_building_a_dsm_spike_rejects(self):
        b = OsmBuilder()
        b.way(square(0, 0, 12), {"building": "yes", "height": "4"}, closed=True)   # flat 24 x 24 m footprint
        data = parse_osm_xml(b.xml().encode())
        g = make_grid(lambda x, y: 130.0 if (x, y) == (0.0, 0.0) else 100.0, n=11, spacing=10.0)
        self.assertEqual(g.heights[5][5], 130.0)                    # the 30 m spike at the footprint centre
        plans = {}
        for on in (False, True):
            area = Area(*self.AREA)
            cl = classify(data, area, mask_extent=(-50.0, -50.0, 50.0, 50.0))
            plans[on] = build_plan(area, g, cl, PlanOptions(trees=False), dsm_correction=on)
        fid = "osm:way/" + str(b.ways[0][0])
        off, on = plans[False], plans[True]
        self.assertFalse(any(o.mb_class == "building" for o in off.objects))
        reason = next(e["reason"] for e in off.report["invalid_features"] if e["id"] == fid)
        self.assertIn("terrain inside footprint reaches eave/roof", reason)
        self.assertTrue(on.report["terrain_correction"]["applied"])
        self.assertEqual([o.mb_id for o in on.objects if o.mb_class == "building"], [fid])
        self.assertFalse(any(e["id"] == fid for e in on.report["invalid_features"]))
        self.assertEqual(on.report["counts"].get("buildings"), 1)

    # --- finding 2: a cache write failure of the mask request is best effort ---------------------------------

    def _acquire_with_failing_write(self, fail_on):
        from map_builder.core import pipeline
        from map_builder.core.cache import DiskCache
        normal, wide = ReviewRound5Test._fixture(self)
        writes = []

        class FailingCache(DiskCache):
            def put(self, namespace, key, body, meta=None):
                writes.append(namespace)
                if len(writes) == fail_on:
                    raise OSError(28, "No space left on device", os.path.join(self.root, "SYNTHETIC"))
                return super().put(namespace, key, body, meta)
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        orig = pipeline.DiskCache
        pipeline.DiskCache = FailingCache
        try:
            return ReviewRound5Test._acquire(self, [(200, normal), (200, wide)], True, cache.name), writes, cache.name
        finally:
            pipeline.DiskCache = orig

    def test_a_failed_mask_cache_write_keeps_the_response_and_warns(self):
        (grid, cl, sources, queries), writes, root = self._acquire_with_failing_write(fail_on=2)
        self.assertEqual(len(queries), 2)
        self.assertEqual(writes, ["osm", "osm"])                   # the second (mask) write raised
        mq = sources[1]["dsm_mask_query"]
        self.assertNotIn("error", mq)
        self.assertEqual(mq["cache_write_error"], "OSError: No space left on device")
        self.assertNotIn(root, json.dumps(sources))                 # no cache path in the provenance
        self.assertIsNone(cl.mask_unavailable)
        self.assertEqual(len(cl.buildings), 1)                      # content kept
        self.assertEqual(len(cl.outside_buildings), 1)              # and the mask candidates too
        self.assertEqual(len(cl.mask_trees), 1)
        self.assertTrue(any(w.startswith("DSM mask request") and "could not be cached" in w for w in cl.warnings))

    def test_a_failed_normal_cache_write_still_fails_acquisition(self):
        # unchanged from main: the normal (content) request's cache write error propagates
        with self.assertRaises(OSError):
            self._acquire_with_failing_write(fail_on=1)

    # --- finding 3: wide-only elements inside the area are mask candidates only ------------------------------

    def test_wide_only_elements_inside_the_area_are_mask_candidates(self):
        normal = parse_osm_xml(OsmBuilder().xml().encode())        # an empty normal response
        b = OsmBuilder()
        tree = b.node(0.0, 0.0, {"natural": "tree"})
        bld = b.way(square(30, 30, 4), {"building": "yes"}, closed=True)
        forest = b.way(square(-30, -30, 8), {"landuse": "forest"}, closed=True)
        wide = parse_osm_xml(b.xml().encode())
        area = Area(*self.AREA)
        cl = classify(normal, area, mask_extent=(-50.0, -50.0, 50.0, 50.0), mask_data=wide)
        self.assertEqual((cl.trees, cl.buildings, cl.areas, cl.outside), ([], [], [], 0))
        self.assertEqual([f.id for f in cl.mask_trees], [f"osm:node/{tree}"])
        self.assertEqual([f.id for f in cl.outside_buildings], [f"osm:way/{bld}"])
        self.assertEqual([f.id for f in cl.mask_areas], [f"osm:way/{forest}"])
        g = make_grid(lambda x, y: 115.0 if (x, y) == (0.0, 0.0) else 100.0, n=11, spacing=10.0)
        plan = build_plan(area, g, cl, PlanOptions(seed=1), dsm_correction=True)
        tc = plan.report["terrain_correction"]
        self.assertTrue(tc["applied"])
        self.assertEqual(tc["mask"]["features"]["trees"], 1)
        self.assertEqual([o.mb_class for o in plan.objects], ["terrain"])   # nothing generated from them
        self.assertEqual(plan.report["invalid_features"], [])
        terrain = plan.objects[0]
        z = plan.report["z_offset_m"]
        centre = next(k for k, (i, j, x, y) in enumerate(points(g)) if (x, y) == (0.0, 0.0))
        self.assertAlmostEqual(terrain.mesh.vertices[centre][2] + z, 100.0, places=2)   # lowered from 115 m
        from map_builder.core.generate import LANDCOVER_COLORS
        self.assertTrue(all(c == tuple(LANDCOVER_COLORS[None]) for c in terrain.mesh.face_colors))


class ReviewRound7Test(unittest.TestCase):
    """Regression tests for the PR #11 round-7 review findings. All data SYNTHETIC."""

    AREA = (47.0, 8.0, 100.0, 100.0)
    EXTENT = (-50.0, -50.0, 150.0, 50.0)
    BAD_ENCODING = b'<?xml version="1.0" encoding="not-a-real-encoding"?><osm/>'
    SECRET = "token=synthetic"

    def _build(self, responses, dsm_correction=True):
        """build_package (local SYNTHETIC DEM, scripted Overpass ``responses``): (plan, sources, manifest,
        package bytes as text, queries)."""
        from map_builder.core import pipeline
        from map_builder.core.http import HttpClient, Response
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        _, dem, _ = write_synthetic_fixtures(tmp.name)
        queries, captured = [], {}

        class Transport:
            def request(self, method, url, headers, data, timeout, max_bytes):
                queries.append(data)
                status, body = responses.pop(0)
                return Response(status, body)
        settings = Settings(elevation_source="file", elevation_file=dem, elevation_vertical_datum="SYNTHETIC",
                            elevation_license="SYNTHETIC", terrain_spacing=30.0, dsm_correction=dsm_correction)
        orig = pipeline.plan_to_package

        def capture(plan, path, name, sources, **kw):
            captured["plan"], captured["sources"] = plan, sources
            return orig(plan, path, name, sources, **kw)
        pipeline.plan_to_package = capture
        try:
            path = os.path.join(tmp.name, "out.mbmap")
            manifest, result = build_package(Area(*self.AREA), settings, path, "SYNTHETIC",
                                             client=HttpClient(Transport()), created_utc="2026-01-01T00:00:00Z")
        finally:
            pipeline.plan_to_package = orig
        self.assertTrue(result.ok, result.errors)
        with zipfile.ZipFile(path) as z:
            text = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist())
        return captured["plan"], captured["sources"], manifest, text, queries

    def _assert_persistable(self, plan, sources, text, *raw):
        from map_builder.blender.sources import check_persistable
        check_persistable({"sources": sources, "report": plan.report})   # Blender's persistence check passes
        persisted = json.dumps([sources, plan.report]) + text
        for r in raw:
            self.assertNotIn(r, persisted)

    # --- finding 1: every parser exception on hostile input is a sanitised FormatError -----------------------

    def test_parser_converts_hostile_input_to_format_error(self):
        from map_builder.core.errors import FormatError
        from map_builder.core.osm import load_osm_file
        cases = {"unknown encoding": (self.BAD_ENCODING, "not-a-real-encoding"),
                 "unsupported encoding": (b'<?xml version="1.0" encoding="utf-7"?><osm/>', "utf-7"),
                 "invalid utf-8": (b'<osm><node id="1" lat="0" lon="0"><tag k="a" v="\xff\xfe"/></node></osm>',
                                   "\ufffd"),
                 "malformed id": (b'<osm><node id="1?token=synthetic" lat="0" lon="0"/></osm>', self.SECRET),
                 "malformed ref": (b'<osm><way id="5"><nd ref="?token=synthetic"/></way></osm>', self.SECRET),
                 "foreign root": (b'<token_synthetic_root/>', "token_synthetic_root")}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, (doc, raw) in cases.items():
            with self.subTest(name):
                with self.assertRaises(FormatError) as cm:
                    parse_osm_xml(doc, description="SYNTHETIC")
                self.assertNotIn(raw, str(cm.exception))
                self.assertIsNone(cm.exception.__cause__)
                path = os.path.join(tmp.name, "hostile.osm")
                with open(path, "wb") as f:
                    f.write(doc)
                with self.assertRaises(FormatError) as cm:                     # the local-file path too
                    load_osm_file(path)
                self.assertNotIn(raw, str(cm.exception))

    def test_unknown_encoding_of_the_mask_response_skips_the_correction(self):
        normal, _wide = ReviewRound5Test._fixture(self)
        grid, cl, sources, queries = ReviewRound5Test._acquire(self, [(200, normal), (200, self.BAD_ENCODING)],
                                                               True)
        self.assertEqual(len(queries), 2)
        self.assertEqual(len(cl.buildings), 1)                                  # the content stands
        mq = sources[1]["dsm_mask_query"]
        self.assertEqual(mq["error_class"], "FormatError")
        self.assertIn("not usable OSM XML", mq["error"])
        self.assertIn("FormatError", cl.mask_unavailable)
        self.assertNotIn("not-a-real-encoding", json.dumps(sources) + cl.mask_unavailable)
        plan = build_plan(Area(*self.AREA), grid, cl, PlanOptions(trees=False), dsm_correction=True)
        self.assertEqual(plan.report["terrain_correction"]["reason"], "mask candidates unavailable")
        self.assertTrue(any(w.startswith("DSM terrain correction skipped: the DSM mask request")
                            for w in plan.report["warnings"]))
        # the normal (content) request still fails, now with the project error type
        from map_builder.core.errors import FormatError
        with self.assertRaises(FormatError):
            ReviewRound5Test._acquire(self, [(200, self.BAD_ENCODING)], True)

    # --- finding 2: only safe structured summaries reach provenance and the report ---------------------------

    def test_a_credential_like_parser_diagnostic_is_not_persisted(self):
        normal, wide = ReviewRound5Test._fixture(self)
        bad = wide.replace(b"</osm>", b'<node id="7?token=synthetic" lat="0" lon="0"/></osm>')
        plan, sources, manifest, text, queries = self._build([(200, normal), (200, bad)])
        self.assertEqual(len(queries), 2)
        mq = sources[1]["dsm_mask_query"]
        self.assertEqual((mq["error_class"], mq["error"]), ("FormatError", pipeline_mask_message("FormatError")))
        self.assertEqual(plan.report["terrain_correction"]["reason"], "mask candidates unavailable")
        self.assertTrue(any(o.mb_class == "building" for o in plan.objects))   # the content was generated
        self._assert_persistable(plan, sources, text, self.SECRET, "7?token")

    def test_a_network_error_is_summarised(self):
        normal, _wide = ReviewRound5Test._fixture(self)
        plan, sources, _m, text, _q = self._build([(200, normal), (429, b"")])
        mq = sources[1]["dsm_mask_query"]
        self.assertEqual(mq["error_class"], "NetworkError")
        self.assertEqual(mq["error_status"], 429)
        self.assertEqual(mq["error"], pipeline_mask_message("NetworkError"))
        self._assert_persistable(plan, sources, text)

    def test_an_invalid_osm_base_is_omitted_with_a_note(self):
        from map_builder.core.pipeline import OSM_BASE_NOTE
        bad_base = b'<meta osm_base="https://user:pw@example.invalid/?token=synthetic"/>'
        normal, wide = ReviewRound5Test._fixture(self)
        hostile_wide = wide.replace(b'<meta osm_base="2026-01-01T00:00:00Z"/>', bad_base)
        hostile_normal = normal.replace(b'<meta osm_base="2026-01-01T00:00:00Z"/>', bad_base)
        self.assertNotEqual(hostile_wide, wide)
        # the wide (mask) response: its candidates are used, only the timestamp is dropped
        plan, sources, _m, text, _q = self._build([(200, normal), (200, hostile_wide)])
        mq = sources[1]["dsm_mask_query"]
        self.assertNotIn("osm_base_timestamp", mq)
        self.assertEqual(mq["osm_base_timestamp_note"], OSM_BASE_NOTE)
        self.assertNotIn("error", mq)
        self.assertEqual(sources[1]["osm_base_timestamp"], "2026-01-01T00:00:00Z")   # the normal one, valid
        self.assertNotEqual(plan.report["terrain_correction"]["reason"], "mask candidates unavailable")
        self._assert_persistable(plan, sources, text, self.SECRET, "user:pw")
        # the normal (content) response, with the correction on and off: the same validation
        for on, responses in ((True, [(200, hostile_normal), (200, wide)]), (False, [(200, hostile_normal)])):
            with self.subTest(correction=on):
                plan, sources, _m, text, _q = self._build(responses, dsm_correction=on)
                self.assertNotIn("osm_base_timestamp", sources[1])
                self.assertEqual(sources[1]["osm_base_timestamp_note"], OSM_BASE_NOTE)
                self.assertTrue(any(o.mb_class == "building" for o in plan.objects))
                if on:
                    self.assertEqual(sources[1]["dsm_mask_query"]["osm_base_timestamp"], "2026-01-01T00:00:00Z")
                self._assert_persistable(plan, sources, text, self.SECRET, "user:pw")
        # unchanged otherwise: a valid timestamp is recorded and a missing one stays None
        from map_builder.core.osm import OsmData
        from map_builder.core.pipeline import osm_source_entry
        d = OsmData()
        d.source = {"provider": "local-file", "file_name": "x.osm", "file_generator": "SYNTHETIC?token=x"}
        src = osm_source_entry(d)
        self.assertIsNone(src["osm_base_timestamp"])
        self.assertNotIn("file_generator", src)                         # a credential-like generator, too
        self.assertIn("file_generator_note", src)
        d.timestamp, d.source["file_generator"] = "2024-02-29T23:59:59.5Z", "SYNTHETIC generator"
        src = osm_source_entry(d)
        self.assertEqual((src["osm_base_timestamp"], src["file_generator"]),
                         ("2024-02-29T23:59:59.5Z", "SYNTHETIC generator"))
        self.assertNotIn("osm_base_timestamp_note", src)

    # --- finding 3: wide multipolygon assembly is deduplicated and bounded by the feature allowance -----------

    def _repeated_triangle(self, n=200_000):
        b = OsmBuilder()
        b.way(square(0, 0, 5), {"building": "yes"}, closed=True)
        tri = b.way([(60.0, 0.0), (64.0, 0.0), (62.0, 3.0)], closed=True)
        rid = b._next()
        b.relations.append((rid, [("way", tri, "outer")] * n, {"type": "multipolygon", "building": "yes"}))
        data = parse_osm_xml(b.xml().encode())
        return data, _without(data, ways=[tri], relations=[rid]), rid

    def test_repeated_member_references_are_bounded(self):
        import tracemalloc
        area = Area(*self.AREA)
        wide, normal, rid = self._repeated_triangle()
        for name, args in (("mask", (normal, wide)), ("content", (wide, None))):
            with self.subTest(name):
                tracemalloc.start()
                try:
                    t = time.perf_counter()
                    cl = classify(args[0], area, mask_extent=self.EXTENT, mask_data=args[1])
                    elapsed = time.perf_counter() - t
                    peak = tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()
                self.assertLess(peak, 20 * 2 ** 20)          # about 119 MiB before
                self.assertLess(elapsed, 2.0)                 # about 11 s (mask) and 15 s (content) before
                self.assertEqual([f.id for f in cl.outside_buildings], [f"osm:relation/{rid}"])
                self.assertIsNone(cl.mask_work_exceeded)
                self.assertIsNone(cl.mask_unavailable)
                self.assertEqual(len(cl.buildings), 1)

    def test_member_repeated_with_an_empty_role_is_used_once(self):
        b = OsmBuilder()
        w = b.way(square(0, 0, 5), closed=True)
        rid = b._next()
        b.relations.append((rid, [("way", w, "outer"), ("way", w, ""), ("way", w, "outer")],
                            {"type": "multipolygon", "building": "yes"}))
        cl = classify(parse_osm_xml(b.xml().encode()), Area(*self.AREA))
        self.assertEqual([f.id for f in cl.buildings], [f"osm:relation/{rid}"])   # before: #0, #1, #2 copies

    def test_mask_candidates_beyond_the_feature_allowance_skip_the_correction(self):
        area = Area(*self.AREA)
        b = OsmBuilder()
        b.way(square(0, 0, 5), {"building": "yes"}, closed=True)
        normal = parse_osm_xml(b.xml().encode())
        members = [("way", b.way(square(60.0 + (k % 40), -20.0 + (k // 40), 0.4), closed=True),
                    "outer") for k in range(2000)]
        b.relations.append((b._next(), members, {"type": "multipolygon", "building": "yes"}))
        for k in range(30):
            b.node(-45.0 + k, 45.0, {"natural": "tree"})
        wide = parse_osm_xml(b.xml().encode())
        from map_builder.core import osm as osm_mod
        made = []
        orig = osm_mod.Polygon

        class Counting(orig):
            def __init__(self, *a, **kw):
                made.append(1)
                super().__init__(*a, **kw)
        osm_mod.Polygon = Counting
        try:
            cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide, max_features=10)   # no LimitError
        finally:
            osm_mod.Polygon = orig
        self.assertIn("exceed the feature limit (10 features", cl.mask_unavailable)
        # round 8: the allowance is charged on retention only, so the rings are assembled (bounded by the mask
        # work budget, which charges every allocation) and the limit is hit when the relation is kept
        self.assertEqual(len(made), 2001)
        self.assertLessEqual(cl.mask_work, dsm.MASK_VALIDATION_WORK_BUDGET)
        self.assertEqual(_summary(cl), _summary(classify(normal, area, mask_extent=self.EXTENT)))
        self.assertLessEqual(len(cl.buildings) + len(cl.outside_buildings) + len(cl.mask_trees), 10)
        g = ReviewRound4Test._grid(self)
        plan = build_plan(area, g, cl, PlanOptions(trees=False), dsm_correction=True)
        tc = plan.report["terrain_correction"]
        self.assertEqual((tc["applied"], tc["reason"]), (False, "mask candidates unavailable"))
        self.assertTrue(any(w.startswith("DSM terrain correction skipped: the DSM mask candidates") for w in
                            plan.report["warnings"]))
        # within the allowance the same candidates are used
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide)
        self.assertIsNone(cl.mask_unavailable)
        self.assertEqual(len(cl.mask_trees), 30)
        self.assertEqual(len(cl.outside_buildings), 2000)

    def test_a_closed_member_is_charged_its_allocations(self):
        area = Area(*self.AREA)
        b = OsmBuilder()
        w = b.way(square(110.0, 0.0, 4.0), closed=True)
        rid = b._next()
        b.relations.append((rid, [("way", w, "outer")], {"type": "multipolygon", "building": "yes"}))
        wide = parse_osm_xml(b.xml().encode())
        cl = classify(parse_osm_xml(OsmBuilder().xml().encode()), area, mask_extent=self.EXTENT, mask_data=wide)
        self.assertEqual(len(cl.outside_buildings), 1)
        n = len(wide.ways[w][0])
        self.assertGreaterEqual(cl.mask_work, 3 * n)        # the copy, the point list and the cleaned ring


class ReviewRound8Test(unittest.TestCase):
    """Regression tests for the PR #11 round-8 review findings. All data SYNTHETIC."""

    AREA = (47.0, 8.0, 100.0, 100.0)
    EXTENT = (-50.0, -50.0, 150.0, 50.0)

    # --- finding 1: a tag without k or v (and other missing required attributes) -----------------------------

    def _layer_without_value(self):
        """The round-5 fixture plus a wide-only building tagged ``<tag k="layer"/>`` (no ``v``)."""
        normal, wide = ReviewRound5Test._fixture(self)
        b = OsmBuilder()
        b._id = 10_000
        b.way(square(40.0, -30.0, 4.0), {"building": "yes", "SYNTHETIC_LAYER": "x"}, closed=True)
        extra = b.xml().encode()
        body = extra[extra.index(b"<node"):extra.index(b"</osm>")]
        bad = body.replace(b'<tag k="SYNTHETIC_LAYER" v="x"/>', b'<tag k="layer"/>')
        self.assertNotEqual(bad, body)
        return normal, wide.replace(b"</osm>", bad + b"</osm>")

    def test_parser_rejects_missing_required_attributes(self):
        from map_builder.core.errors import FormatError
        from map_builder.core.osm import load_osm_file
        _normal, wide = self._layer_without_value()
        node = b'<node id="1" lat="0" lon="0"/><node id="2" lat="0" lon="0.001"/>'
        cases = {"layer without v": wide,
                 "tag without v": b'<osm><node id="1" lat="0" lon="0"><tag k="token_synthetic"/></node></osm>',
                 "tag without k": b'<osm><node id="1" lat="0" lon="0"><tag v="token_synthetic"/></node></osm>',
                 "nd without ref": b'<osm>' + node + b'<way id="5"><nd ref="1"/><nd/></way></osm>',
                 "member without type": b'<osm>' + node + b'<relation id="9"><member ref="1" role="token_synthetic"/>'
                                        b'</relation></osm>',
                 "member without ref": b'<osm><relation id="9"><member type="way" role="token_synthetic"/>'
                                       b'</relation></osm>'}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, doc in cases.items():
            with self.subTest(name):
                with self.assertRaises(FormatError) as cm:
                    parse_osm_xml(doc, description="SYNTHETIC")
                self.assertIn("malformed <", str(cm.exception))
                self.assertNotIn("token_synthetic", str(cm.exception))
                self.assertIsNone(cm.exception.__cause__)
                path = os.path.join(tmp.name, "missing.osm")
                with open(path, "wb") as f:
                    f.write(doc)
                with self.assertRaises(FormatError):                          # the local-file path too
                    load_osm_file(path)
        # an empty value is still a value; a relation member without a role is still an outer
        d = parse_osm_xml(b'<osm>' + node + b'<way id="5"><nd ref="1"/><nd ref="2"/><tag k="name" v=""/></way>'
                          b'<relation id="9"><member type="way" ref="5"/></relation></osm>')
        self.assertEqual(d.ways[5][1], {"name": ""})
        self.assertEqual(d.relations[9][0], [("way", 5, "")])

    def test_a_tag_without_value_in_the_mask_response_keeps_the_content(self):
        normal, wide = self._layer_without_value()
        grid, cl, sources, queries = ReviewRound5Test._acquire(self, [(200, normal), (200, wide)], True)
        self.assertEqual(len(queries), 2)
        self.assertEqual(len(cl.buildings), 1)                                  # the content stands
        mq = sources[1]["dsm_mask_query"]
        self.assertEqual((mq["error_class"], mq["error"]), ("FormatError", pipeline_mask_message("FormatError")))
        self.assertIn("DSM mask request", cl.mask_unavailable)
        plan = build_plan(Area(*self.AREA), grid, cl, PlanOptions(trees=False), dsm_correction=True)
        self.assertEqual(plan.report["terrain_correction"]["reason"], "mask candidates unavailable")
        self.assertTrue(any(w.startswith("DSM terrain correction skipped: the DSM mask request")
                            for w in plan.report["warnings"]))
        # the same document as the normal (content) response is a FormatError, as for any malformed content
        from map_builder.core.errors import FormatError
        with self.assertRaises(FormatError):
            ReviewRound5Test._acquire(self, [(200, wide)], True)

    def test_non_integer_layers_are_tolerated_on_both_paths(self):
        from map_builder.core.osm import surface_mask_eligible
        for layer in ("1;2", "-1.5", "", "x", "\u0661"):
            self.assertTrue(surface_mask_eligible({"building": "yes", "layer": layer}), layer)
        self.assertFalse(surface_mask_eligible({"building": "yes", "layer": "-1"}))
        self.assertTrue(surface_mask_eligible({"building": "yes", "layer": None}))   # never from the parser
        area = Area(*self.AREA)
        b = OsmBuilder()
        b.way(square(0, 0, 5), {"building": "yes", "layer": "1;2"}, closed=True)
        normal = parse_osm_xml(b.xml().encode())
        b.way(square(62, 0, 6), {"building": "yes", "layer": "-0.5"}, closed=True)
        wide = parse_osm_xml(b.xml().encode())
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide)
        self.assertEqual((len(cl.buildings), len(cl.outside_buildings)), (1, 1))
        self.assertIsNone(cl.mask_unavailable)

    def test_unexpected_mask_errors_skip_the_correction(self):
        from map_builder.core import osm as osm_mod
        from map_builder.core.errors import LimitError
        area = Area(*self.AREA)
        normal, wide = (parse_osm_xml(d) for d in ReviewRound5Test._fixture(self))
        ref = classify(normal, area, mask_extent=self.EXTENT)
        orig = osm_mod._mask_polygons
        for exc in (TypeError("token_synthetic"), ValueError("token_synthetic"), KeyError("token_synthetic"),
                    MemoryError(), KeyboardInterrupt(), LimitError("SYNTHETIC")):
            with self.subTest(type(exc).__name__):
                def boom(*_a, **_kw):
                    raise exc
                osm_mod._mask_polygons = boom
                try:
                    if isinstance(exc, (MemoryError, KeyboardInterrupt, LimitError)):
                        with self.assertRaises(type(exc)):                  # never swallowed
                            classify(normal, area, mask_extent=self.EXTENT, mask_data=wide)
                        continue
                    cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide)
                finally:
                    osm_mod._mask_polygons = orig
                self.assertEqual(cl.mask_unavailable, "the wider DSM mask response could not be processed "
                                                      "(unexpected data in its DSM mask candidates)")
                self.assertEqual(_summary(cl), _summary(ref))                # the content is unaffected
                plan = build_plan(area, ReviewRound4Test._grid(self), cl, PlanOptions(trees=False),
                                  dsm_correction=True)
                tc = plan.report["terrain_correction"]
                self.assertEqual((tc["applied"], tc["reason"]), (False, "mask candidates unavailable"))
                warnings = [w for w in plan.report["warnings"]
                            if w.startswith("DSM terrain correction skipped: the wider DSM mask response")]
                self.assertEqual(len(warnings), 1)
                self.assertNotIn("token_synthetic", json.dumps(plan.report))
        # content classification is not wrapped: the same failure there still raises
        orig_reason = osm_mod._unsupported_reason

        def bad_reason(_tags):
            raise TypeError("SYNTHETIC")
        osm_mod._unsupported_reason = bad_reason
        try:
            with self.assertRaises(TypeError):
                classify(normal, area, mask_extent=self.EXTENT, mask_data=wide)
        finally:
            osm_mod._unsupported_reason = orig_reason

    # --- finding 2: the feature allowance is charged only for retained mask candidates -----------------------

    def _forest_with_off_grid_outers(self):
        b = OsmBuilder()
        normal = parse_osm_xml(b.xml().encode())                       # no content: the allowance is max_features
        outers = [b.way(square(cx, 0.0, 20.0), closed=True) for cx in (-600.0, 100.0, 700.0)]
        rid = b._next()
        b.relations.append((rid, [("way", w, "outer") for w in outers],
                            {"type": "multipolygon", "landuse": "forest"}))
        return normal, parse_osm_xml(b.xml().encode()), rid

    def test_off_grid_outer_rings_do_not_exhaust_the_allowance(self):
        area = Area(*self.AREA)
        normal, wide, rid = self._forest_with_off_grid_outers()
        for max_features in (1, 3):
            with self.subTest(max_features=max_features):
                cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide, max_features=max_features)
                self.assertIsNone(cl.mask_unavailable)                       # before (max_features=1): unavailable
                self.assertEqual([f.id for f in cl.mask_areas], [f"osm:relation/{rid}#1"])
                plan = build_plan(area, ReviewRound4Test._grid(self), cl, PlanOptions(trees=False),
                                  dsm_correction=True)
                tc = plan.report["terrain_correction"]
                self.assertTrue(tc["applied"], tc)
                self.assertGreater(tc["masked_points"], 0)
        # a retained candidate beyond the allowance still skips the correction
        b = OsmBuilder()
        normal = parse_osm_xml(b.xml().encode())
        outers = [b.way(square(cx, 0.0, 20.0), closed=True) for cx in (0.0, 100.0)]
        b.relations.append((b._next(), [("way", w, "outer") for w in outers],
                            {"type": "multipolygon", "landuse": "forest"}))
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=parse_osm_xml(b.xml().encode()),
                      max_features=1)
        self.assertIn("exceed the feature limit (1 features", cl.mask_unavailable)


class ReviewRound9Test(unittest.TestCase):
    """Regression tests for the PR #11 round-9 review findings. All data SYNTHETIC."""

    AREA = (47.0, 8.0, 100.0, 100.0)
    EXTENT = (-50.0, -50.0, 50.0, 50.0)

    def test_off_grid_building_polygons_do_not_exhaust_the_allowance(self):
        area = Area(*self.AREA)
        b = OsmBuilder()
        normal = parse_osm_xml(b.xml().encode())
        outers = [b.way(square(cx, 0.0, 20.0), closed=True) for cx in (-600.0, 0.0, 700.0)]
        rid = b._next()
        b.relations.append((rid, [("way", w, "outer") for w in outers],
                            {"type": "multipolygon", "building": "yes"}))
        wide = parse_osm_xml(b.xml().encode())
        for max_features in (1, 3):
            with self.subTest(max_features=max_features):
                cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide, max_features=max_features)
                self.assertIsNone(cl.mask_unavailable)                       # before (max_features=1): unavailable
                self.assertEqual(len(cl.outside_buildings), 1)               # only the polygon near the grid
                self.assertLess(abs(cl.outside_buildings[0].geometry.centroid()[0]), 1.0)

    def test_content_does_not_reduce_the_mask_allowance(self):
        area = Area(*self.AREA)
        b = OsmBuilder()
        b.way(square(0.0, 0.0, 10.0), {"building": "yes"}, closed=True)
        b.way(square(0.0, 0.0, 10.0), {"building:part": "yes", "building:levels": "2"}, closed=True)
        normal = parse_osm_xml(b.xml().encode())
        b.node(5.0, 0.0, {"natural": "tree"})
        b.node(6.0, 0.0, {"natural": "tree"})
        b.node(7.0, 0.0, {"natural": "tree"})
        wide = parse_osm_xml(b.xml().encode())
        ref = classify(normal, area, mask_extent=self.EXTENT)
        self.assertEqual((len(ref.buildings), len(ref.outline_features)), (1, 1))   # the outline was replaced
        # round 11: content and mask candidates are bounded separately
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide, max_features=3)
        self.assertIsNone(cl.mask_unavailable)
        self.assertEqual(len(cl.mask_trees), 3)
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide, max_features=2)
        self.assertEqual(cl.mask_trees, [])
        self.assertIn("exceed the feature limit (2 features", cl.mask_unavailable)

    def test_off_grid_polygons_of_a_normal_relation_are_not_kept(self):
        area = Area(*self.AREA)
        b = OsmBuilder()
        outers = [b.way(square(cx, 0.0, 5.0), closed=True) for cx in (60.0, 600.0, 700.0)]
        b.relations.append((b._next(), [("way", w, "outer") for w in outers],
                            {"type": "multipolygon", "building": "yes"}))
        data = parse_osm_xml(b.xml().encode())
        cl = classify(data, area, mask_extent=self.EXTENT, max_features=2)   # before: LimitError (3 kept)
        self.assertEqual((len(cl.buildings), cl.outside, len(cl.outside_buildings)), (0, 1, 1))
        self.assertLess(abs(cl.outside_buildings[0].geometry.centroid()[0] - 60.0), 1.0)

    def test_bridges_out_of_their_own_reach_are_not_kept(self):
        area = Area(*self.AREA)
        b = OsmBuilder()
        normal = parse_osm_xml(b.xml().encode())
        bridge = {"highway": "service", "bridge": "yes", "width": "4"}      # reach 2 + 15 m < 85 - 50 m
        b.way([(85.0, -40.0), (85.0, 40.0)], bridge)
        b.node(0.0, 0.0, {"natural": "tree"})
        wide = parse_osm_xml(b.xml().encode())
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide, max_features=1)
        self.assertIsNone(cl.mask_unavailable)                               # before: the bridge took the slot
        self.assertEqual((len(cl.bridges), len(cl.mask_trees)), (0, 1))
        self.assertEqual(len(classify(wide, area, mask_extent=self.EXTENT).bridges), 0)   # the content path too
        b2 = OsmBuilder()
        b2.way([(85.0, -40.0), (85.0, 40.0)], dict(bridge, width="60"))     # reach 45 m: within it
        self.assertEqual(len(classify(parse_osm_xml(b2.xml().encode()), area, mask_extent=self.EXTENT).bridges), 1)


class ReviewRound11Test(unittest.TestCase):
    """Round 11: wide-only forest mask features share a minimal tag dict, and mask-only candidates never
    count toward the hard content feature limit."""

    AREA = (47.0, 8.0, 100.0, 100.0)
    EXTENT = (-50.0, -50.0, 150.0, 50.0)

    def test_wide_forest_with_many_outers_and_tags_stays_bounded(self):
        import tracemalloc
        area = Area(*self.AREA)
        normal = parse_osm_xml(OsmBuilder().xml().encode())
        b = OsmBuilder()
        outers = [b.way(square(52.0 + 2.4 * (k % 40), -48.0 + 0.96 * (k // 40), 0.4), closed=True)
                  for k in range(4000)]
        tags = {"type": "multipolygon", "landuse": "forest"}
        tags.update({f"note:{i}": "x" * 40 for i in range(2000)})
        b.relations.append((b._next(), [("way", w, "outer") for w in outers], tags))
        wide = parse_osm_xml(b.xml().encode())
        tracemalloc.start()
        try:
            cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide)
            _cur, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertIsNone(cl.mask_unavailable)
        self.assertIsNone(cl.mask_work_exceeded)
        self.assertEqual(len(cl.mask_areas), 4000)
        self.assertEqual(cl.mask_areas[0].tags, {"_class": "forest"})
        self.assertLess(peak, 48 * 2 ** 20)   # before: a 2,000-tag copy per polygon (~200 MiB)

    def test_mask_only_trees_never_fail_the_content_limit(self):
        from map_builder.core.errors import LimitError
        area = Area(*self.AREA)
        b = OsmBuilder()
        b.way(square(0.0, 0.0, 10.0), {"building": "yes"}, closed=True)
        for k in range(11):
            b.node(53.0, -40.0 + 7.0 * k, {"natural": "tree"})              # 3 m outside the east edge
        data = parse_osm_xml(b.xml().encode())
        cl = classify(data, area, mask_extent=self.EXTENT, max_features=10)   # before: LimitError (12 > 10)
        self.assertEqual((len(cl.buildings), cl.mask_trees), (1, []))
        self.assertIn("exceed the feature limit (10 features", cl.mask_unavailable)
        g = ElevationGrid(-50.0, -50.0, 5.0, 41, 21, [[ground(-50 + i * 5.0, -50 + j * 5.0) for i in range(41)]
                                                      for j in range(21)], dict(COPERNICUS))
        on = build_plan(area, g, cl, PlanOptions(trees=True, seed=1))
        self.assertFalse(on.report["terrain_correction"]["applied"])       # the correction skipped, with a warning
        self.assertEqual(on.report["terrain_correction"]["reason"], "mask candidates unavailable")
        off = build_plan(area, g, cl, PlanOptions(trees=True, seed=1), dsm_correction=False)
        self.assertEqual(sum(o.mb_class == "building" for o in off.objects), 1)
        # the content limit itself is unchanged
        b.node(0.0, 30.0, {"natural": "tree"})
        b.node(0.0, 35.0, {"natural": "tree"})
        with self.assertRaises(LimitError):
            classify(parse_osm_xml(b.xml().encode()), area, mask_extent=self.EXTENT, max_features=2)

    def test_bridge_mask_fragments_are_bounded_while_emitted(self):
        # round 12: each zig-zag bridge way clips into ~100 off-area fragments; before, all were kept, then dropped
        import tracemalloc
        area = Area(*self.AREA)
        b = OsmBuilder()
        zig = [(55.0, 0.0), (80.0, 5.0), (80.0, -5.0)] * 100
        for _ in range(200):
            b.way(zig, {"highway": "service", "bridge": "yes", "width": "4"})
        data = parse_osm_xml(b.xml().encode())
        self.assertGreater(len(classify(data, area, mask_extent=(-50.0, -50.0, 50.0, 50.0)).bridges), 15000)
        def peak(d):
            tracemalloc.start()
            try:
                cl = classify(d, area, mask_extent=(-50.0, -50.0, 50.0, 50.0), max_features=100)
                return cl, tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
        cl, bridged = peak(data)
        self.assertEqual(cl.bridges, [])
        self.assertIn("exceed the feature limit (100 features", cl.mask_unavailable)
        plain = OsmBuilder()
        for _ in range(200):
            plain.way(zig, {"highway": "service", "width": "4"})
        _cl, baseline = peak(parse_osm_xml(plain.xml().encode()))      # the same ways, not bridges
        self.assertLess(bridged, 1.5 * baseline)                       # before: ~2.5 x (all fragments kept)

    def test_one_bridge_way_is_not_clipped_past_the_allowance(self):
        # round 13: one way of 20 000 zig-zags clips into 20 000 fragments; both paths stop at the allowance
        import tracemalloc
        area = Area(*self.AREA)
        ext = (-50.0, -50.0, 50.0, 50.0)
        zig = [(55.0, 0.0), (80.0, 5.0), (80.0, -5.0)] * 20000
        bridged, plain = OsmBuilder(), OsmBuilder()
        bridged.way(zig, {"highway": "service", "bridge": "yes", "width": "4"})
        plain.way(zig, {"highway": "service", "width": "4"})
        bridged, plain = parse_osm_xml(bridged.xml().encode()), parse_osm_xml(plain.xml().encode())
        empty = parse_osm_xml(OsmBuilder().xml().encode())

        def peak(normal, wide):
            tracemalloc.start()
            try:
                cl = classify(normal, area, mask_extent=ext, mask_data=wide, max_features=100)
                return cl, tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
        for normal, wide, base in ((bridged, None, (plain, None)), (empty, bridged, (plain, None))):
            cl, p = peak(normal, wide)
            self.assertEqual(cl.bridges, [])
            self.assertIn("exceed the feature limit (100 features", cl.mask_unavailable)
            self.assertLess(p, 1.5 * peak(*base)[1])                    # before: all 20 000 fragments held

    def test_bridge_width_parsed_once_per_way(self):
        # round 14: dsm_obstacles parsed each fragment's (possibly huge) width tag again
        from unittest import mock
        from map_builder.core import generate
        area = Area(*self.AREA)
        b = OsmBuilder()
        b.way([(55.0, 0.0), (80.0, 5.0), (80.0, -5.0)] * 300, {"highway": "service", "bridge": "yes", "width": "4"})
        cl = classify(parse_osm_xml(b.xml().encode()), area, mask_extent=(-50.0, -50.0, 50.0, 50.0))
        self.assertGreater(len(cl.bridges), 250)
        with mock.patch.object(generate, "road_width", wraps=generate.road_width) as rw:
            _, _, _, bridges = generate.dsm_obstacles(cl, extent=(-50.0, -50.0, 50.0, 50.0))
        self.assertEqual(rw.call_count, 1)                              # before: once per fragment
        self.assertEqual(len(bridges), len(cl.bridges))
        self.assertTrue(all(w == 4.0 for _pts, w in bridges))

    def test_ineligible_wide_relation_does_not_spend_the_mask_work(self):
        # round 15: an underground building multipolygon (never masked) was assembled first, against the budget
        area = Area(*self.AREA)
        normal = parse_osm_xml(OsmBuilder().xml().encode())

        def wide(location):
            b = OsmBuilder()
            ring = [b.node(88.0 + 5.0 * math.cos(2 * math.pi * k / 400), 5.0 * math.sin(2 * math.pi * k / 400))
                    for k in range(400)]
            ways = []
            for k in range(400):
                wid = b._next()
                b.ways.append((wid, [ring[k], ring[(k + 1) % 400]], {}))
                ways.append(wid)
            b.relations.append((b._next(), [("way", w, "outer") for w in ways],
                                dict({"type": "multipolygon", "building": "yes"}, **location)))
            b.node(0.0, 0.0, {"natural": "tree"})
            return parse_osm_xml(b.xml().encode())
        surface = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide({}), max_mask_work=5000)
        self.assertIsNotNone(surface.mask_work_exceeded)                # the assembly does cost work
        cl = classify(normal, area, mask_extent=self.EXTENT, mask_data=wide({"location": "underground"}),
                      max_mask_work=5000)
        self.assertIsNone(cl.mask_work_exceeded)                        # before: exceeded, no correction at all
        self.assertEqual((len(cl.mask_trees), cl.outside_buildings), (1, []))


def pipeline_mask_message(cls_name):
    from map_builder.core import errors, pipeline
    return pipeline._mask_error_message(getattr(errors, cls_name)("SYNTHETIC"))


if __name__ == "__main__":
    unittest.main()
