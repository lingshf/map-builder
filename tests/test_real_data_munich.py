# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S2-F2: elevated parts, building passages and roof shapes on real OpenStreetMap data.

The fixture is an excerpt (OSM ways within ~50 m of two spots, plus a few chosen ways) of the 400 x 400 m
Munich Altstadt area of tools/demo/presets/munich-altstadt.json, fetched from Overpass on 2026-11-19 (OpenStreetMap
contributors, ODbL). The terrain is flat (z = 0): the live GLO-30 build is checked separately in the PR."""

import math
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
# mb_id -> (eave z, rise to the apex) in metres, from building:levels x 3 m and the roof height rule / roof:height=7
ROOF_GEOMETRY = {"osm:way/80965553": (15.0, 3.0), "osm:way/80965659": (15.0, 3.32),
                 "osm:way/144135890": (15.0, 6.0), "osm:way/150797496": (18.0, 4.29),
                 "osm:way/108429818": (15.0, 7.0)}
TOL = 0.05


def fit_plane(pts):
    """Least-squares z = a*x + b*y + c through pts (normal equations, 3 x 3)."""
    n = len(pts)
    sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts); sz = sum(p[2] for p in pts)
    sxx = sum(p[0] ** 2 for p in pts); syy = sum(p[1] ** 2 for p in pts); sxy = sum(p[0] * p[1] for p in pts)
    sxz = sum(p[0] * p[2] for p in pts); syz = sum(p[1] * p[2] for p in pts)
    m = [[sxx, sxy, sx, sxz], [sxy, syy, sy, syz], [sx, sy, n, sz]]
    for i in range(3):
        k = max(range(i, 3), key=lambda r: abs(m[r][i]))
        m[i], m[k] = m[k], m[i]
        for r in range(3):
            if r != i:
                f = m[r][i] / m[i][i]
                m[r] = [x - f * y for x, y in zip(m[r], m[i])]
    return tuple(m[i][3] / m[i][i] for i in range(3))


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

    def test_exported_roof_geometry_has_the_tagged_rise_ridge_and_gables(self):
        for shape, ids in MEASURED_ROOFS.items():
            for mb_id in ids:
                eave, rise = ROOF_GEOMETRY[mb_id]
                mesh = self.objects[mb_id].mesh
                verts = mesh.vertices
                top = max(v[2] for v in verts)
                base = min(v[2] for v in verts) + 0.3                    # terrain is z = 0; the foundation is 0.3 m below
                self.assertAlmostEqual(base, 0.0, delta=TOL, msg=mb_id)
                # the eave is measured from the mesh: the lowest vertex above the foundation is the wall top
                measured_eave = min(v[2] for v in verts if v[2] > base + TOL)
                self.assertAlmostEqual(measured_eave - base, eave, delta=TOL, msg=mb_id)     # wall height
                self.assertAlmostEqual(top - measured_eave, rise, delta=TOL, msg=mb_id)      # roof rise
                self.assertAlmostEqual(top - base, eave + rise, delta=TOL, msg=mb_id)        # total height
                roof_verts = [i for i, v in enumerate(verts) if v[2] > measured_eave + TOL]
                self.assertTrue(roof_verts, mb_id)
                faces_on_roof = [f for f in mesh.faces if any(i in roof_verts for i in f)]
                if shape == "gabled" and "roof_construction" in self.objects[mb_id].provenance:
                    # S4-ROOF-NAMED: a near-rectangle with unequal eaves is a skeleton roof (planar slopes, a ridge
                    # that may rise towards one end); roof_checks judges its tiling, planarity and gables
                    self.assertTrue(any(abs(v[2] - top) <= TOL for v in verts), mb_id)
                    continue
                if shape == "gabled":
                    ridge = [i for i, v in enumerate(verts) if abs(v[2] - top) <= TOL]
                    self.assertEqual(len(ridge), 2, mb_id)
                    self.assertGreater(math.dist(verts[ridge[0]][:2], verts[ridge[1]][:2]), 2.0, mb_id)
                    # two slopes (non-planar quads split into 2 triangles each) and two gable-end triangles
                    self.assertEqual(len(faces_on_roof), 6, mb_id)
                    self.assertTrue(all(len(f) == 3 for f in faces_on_roof), mb_id)
                    for r in ridge:
                        self.assertGreaterEqual(sum(r in f for f in faces_on_roof), 3, mb_id)
                    self.assert_gable_slopes(mb_id, verts, faces_on_roof, ridge, top - measured_eave)
                else:
                    self.assert_skillion_plane(mb_id, verts, roof_verts, rise)
                    low = [v for v in verts if abs(v[2] - measured_eave) <= TOL]
                    self.assertTrue(low, mb_id)                          # slope starts at the eave

    def assert_skillion_plane(self, mb_id, verts, roof_verts, rise):
        """All roof vertices lie on one plane that falls to the north (roof:direction=N) by rise over the depth."""
        pts = [verts[i] for i in roof_verts]
        a, b, c = fit_plane(pts)
        for x, y, z in pts:
            self.assertAlmostEqual(a * x + b * y + c, z, delta=TOL, msg=mb_id)       # coplanar
        self.assertAlmostEqual(a, 0.0, delta=0.05, msg=mb_id)
        self.assertLess(b, 0.0, mb_id)                                                # high side south
        ys = [v[1] for v in verts]
        self.assertAlmostEqual(-b, rise / (max(ys) - min(ys)), delta=0.01, msg=mb_id)   # slope = rise / depth

    def assert_gable_slopes(self, mb_id, verts, faces_on_roof, ridge, rise):
        """Every sloping roof triangle falls away from the ridge with rise / half-width (the two slopes of a
        non-rectangular footprint are split into triangles, so each triangle is its own plane, within 20 %)."""
        r0, r1 = verts[ridge[0]], verts[ridge[1]]
        d = (r1[0] - r0[0], r1[1] - r0[1])
        norm = math.hypot(*d)
        n = (-d[1] / norm, d[0] / norm)
        eave_pts = [v for v in verts if abs(v[2] - (max(w[2] for w in verts) - rise)) <= TOL]
        half = {side: sum(abs((e[0] - r0[0]) * n[0] + (e[1] - r0[1]) * n[1]) for e in eave_pts
                          if side * ((e[0] - r0[0]) * n[0] + (e[1] - r0[1]) * n[1]) > 0)
                / sum(1 for e in eave_pts if side * ((e[0] - r0[0]) * n[0] + (e[1] - r0[1]) * n[1]) > 0)
                for side in (1, -1)}
        slopes = []
        for f in faces_on_roof:
            (x0, y0, _), (x1, y1, _), (x2, y2, _) = (verts[i] for i in f)
            if abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)) < 1e-6:           # vertical: a gable end
                continue
            a, b, c = fit_plane([verts[i] for i in f])
            side = 1 if (a * n[0] + b * n[1]) < 0 else -1                             # z falls away from the ridge
            grad = math.hypot(a, b)
            self.assertAlmostEqual(grad, rise / half[side], delta=0.2 * rise / half[side], msg=mb_id)
            slopes.append((side, grad))
        self.assertEqual(sorted(side for side, _ in slopes), [-1, -1, 1, 1], mb_id)
        for side in (-1, 1):                    # the two triangles of one slope average to the expected pitch
            mean = sum(g for sd, g in slopes if sd == side) / 2
            self.assertAlmostEqual(mean, rise / half[side], delta=0.02, msg=mb_id)

    def test_non_rectangular_gabled_real_roofs_are_built_gabled(self):
        for i in ("osm:way/85765729", "osm:way/80965613"):       # S3-ROOF-GABLED: straight skeleton + vertical gable walls
            prov = self.objects[i].provenance
            self.assertEqual(prov["roof_shape_built"], "gabled", i)
            self.assertIn("vertical gable wall", prov["roof_construction"], i)
        prov = self.objects["osm:way/80965653"].provenance      # S3-ROOF-HIPPED: now built from the straight skeleton
        self.assertEqual(prov["roof_shape_built"], "hipped")


if __name__ == "__main__":
    unittest.main()
