"""S1-TUNNEL: road tunnels (map_builder/core/tunnels.py)."""

import math
import os
import tempfile
import unittest

from map_builder.core.collision import rasterize_heightfield
from map_builder.core.dem import ElevationGrid
from map_builder.core.generate import PlanOptions, ROAD_LIFT_M, build_plan, terrain_height
from map_builder.core.geodesy import Area
from map_builder.core.osm import classify, parse_osm_xml
from map_builder.core.package import collision_orientation_problems, validate_package
from map_builder.core.pipeline import plan_to_package
from map_builder.core.structures import plan_collision

from .synthetic import OsmBuilder

AREA = Area(47.0, 8.0, 100.0, 100.0)
TUNNEL_TAGS = {"highway": "service", "tunnel": "yes", "layer": "-1"}


def hill_grid(peak=15.0, spacing=5.0):
    n = int(100 / spacing) + 1
    heights = [[peak * math.exp(-(-50 + i * spacing) ** 2 / 400.0) * math.exp(-(-50 + j * spacing) ** 2 / 900.0)
                for i in range(n)] for j in range(n)]
    return ElevationGrid(-50.0, -50.0, spacing, n, n, heights, {"provider": "test"})


def flat_grid():
    return ElevationGrid(-50.0, -50.0, 10.0, 11, 11, [[0.0] * 11 for _ in range(11)], {"provider": "test"})


def plan_for(grid, tags=TUNNEL_TAGS, extra=None, options=None, pts=((-35, 0), (35, 0))):
    b = OsmBuilder()
    wid = b.way(list(pts), tags)
    if extra:
        extra(b)
    cl = classify(parse_osm_xml(b.xml().encode()), AREA)
    return build_plan(AREA, grid, cl, options), wid


def gallery_grid(spacing=5.0):
    """High ground at both portals, a deep valley between: the tube is a gallery over lower ground."""
    n = int(100 / spacing) + 1
    row = [15.0 - 40.0 * math.exp(-(-50 + i * spacing) ** 2 / 400.0) for i in range(n)]
    return ElevationGrid(-50.0, -50.0, spacing, n, n, [list(row) for _ in range(n)], {"provider": "test"})


def hits_at(tris, x, y):
    """Sorted z of every triangle crossing the vertical line through (x, y)."""
    out = []
    for a, b, c in tris:
        if x < min(a[0], b[0], c[0]) or x > max(a[0], b[0], c[0]) or y < min(a[1], b[1], c[1]) or \
                y > max(a[1], b[1], c[1]):
            continue
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) >= -1e-9:
            out.append(l1 * a[2] + l2 * b[2] + l3 * c[2])
    return sorted(out)


def terrain_edge_problems(mesh, nx, ny, spacing, x0, y0, footprint, tol=1e-3):
    """Defects of a cut terrain mesh: faces that are not CCW, unused vertices, and open edges away from both the
    outer border and the footprint ``(xa, xb, ya, yb)``."""
    probs = []
    used = set()
    edges = {}
    for fi, f in enumerate(mesh.faces):
        a, b, c = (mesh.vertices[v] for v in f)
        if (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]) <= 0:
            probs.append(("not ccw", fi))
        used.update(f)
        for u, v in zip(f, f[1:] + f[:1]):
            edges.setdefault(frozenset((u, v)), []).append((u, v))
    if len(used) != len(mesh.vertices):
        probs.append(("unused vertices", len(mesh.vertices) - len(used)))
    xa, xb, ya, yb = footprint
    for k, uses in edges.items():
        if len(uses) == 1:
            p, q = (mesh.vertices[v] for v in tuple(k))
            on_border = all(abs(abs(r[0]) - 50) < tol or abs(abs(r[1]) - 50) < tol for r in (p, q)) and \
                (abs(p[0] - q[0]) < tol or abs(p[1] - q[1]) < tol)
            in_foot = all(xa - tol <= r[0] <= xb + tol and ya - tol <= r[1] <= yb + tol for r in (p, q))
            if not (on_border or in_foot):
                probs.append(("open edge", p, q))
        elif len(uses) > 2 or (uses[0] == uses[1]):
            probs.append(("bad edge", tuple(k)))
    return probs


def tris_of(col, *classes):
    out = []
    for c in classes:
        out.extend(col.class_triangles(c))
    return out


def top_hit(tris, x, y):
    best = -math.inf
    for a, b, c in tris:
        if x < min(a[0], b[0], c[0]) or x > max(a[0], b[0], c[0]) or y < min(a[1], b[1], c[1]) or \
                y > max(a[1], b[1], c[1]):
            continue
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) >= -1e-9:
            best = max(best, l1 * a[2] + l2 * b[2] + l3 * c[2])
    return best


class HillTunnelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = hill_grid()
        cls.plan, cls.wid = plan_for(cls.grid)
        cls.mb = f"osm:way/{cls.wid}"
        cls.col, _ = plan_collision(cls.plan)
        cls.tube = next(o for o in cls.plan.objects if o.mb_id == cls.mb)

    def test_objects_and_rules(self):
        by_class = {}
        for o in self.plan.objects:
            by_class.setdefault(o.mb_class, []).append(o.mb_id)
        self.assertEqual(by_class["tunnel"], [self.mb])
        self.assertEqual(sorted(by_class["structure"]), [f"{self.mb}:headwall0", f"{self.mb}:headwall1"])
        self.assertEqual(collision_orientation_problems(self.col), [])
        self.assertEqual(self.plan.report["counts"]["tunnels"], 1)
        self.assertNotIn(self.mb, [u["id"] for u in self.plan.report["unsupported_features"]])

    def test_heightfield_is_nan_exactly_at_cut_cells(self):
        terrain = self.col.class_triangles("terrain")
        x0, y0, nx, ny, sp = -34.13, -4.07, 137, 17, 0.5
        z = rasterize_heightfield(terrain, x0, y0, sp, nx, ny)
        base, _ = plan_for(self.grid, dict(TUNNEL_TAGS, tunnel="culvert"))
        zb = rasterize_heightfield(plan_collision(base)[0].class_triangles("terrain"), x0, y0, sp, nx, ny)
        a = self.tube.provenance["floor_width_m"] / 2.0
        clearance = self.tube.provenance["clearance_m"]
        z_off = self.plan.objects[0].location[2]
        floor0 = terrain_height(self.grid, -35, 0) + ROAD_LIFT_M
        floor1 = terrain_height(self.grid, 35, 0) + ROAD_LIFT_M
        checked = [0, 0]
        for j in range(ny):
            for i in range(nx):
                x, y = x0 + i * sp, y0 + j * sp
                orig = zb[j][i] + self.z_off()
                roof = floor0 + (floor1 - floor0) * (x + 35) / 70.0 + clearance
                if abs(y) > a + 0.1:
                    self.assertFalse(math.isnan(z[j][i]), (x, y))
                    self.assertAlmostEqual(z[j][i], zb[j][i], delta=1e-4)
                    checked[0] += 1
                elif abs(y) <= 0.3 and abs(orig - roof) > 0.05:
                    self.assertEqual(math.isnan(z[j][i]), orig < roof, (x, y, orig, roof))
                    checked[1] += 1
        self.assertGreater(checked[0], 100)
        self.assertGreater(checked[1], 50)

    def z_off(self):
        terrain = next(o for o in self.plan.objects if o.mb_id == "terrain:grid")
        return terrain_height(self.grid, *terrain.mesh.vertices[0][:2]) - terrain.mesh.vertices[0][2]

    def test_no_leak_around_the_tunnel(self):
        tris = tris_of(self.col, "terrain", "tunnel", "structure", "road")
        z_off = self.z_off()
        n = 0
        for xi in range(-40, 41, 3):
            for yj in range(-9, 10):
                x, y = xi + 0.137, yj * 0.93 + 0.071
                top = top_hit(tris, x, y)
                self.assertGreaterEqual(top, terrain_height(self.grid, x, y) - z_off - 2e-3, (x, y))
                n += 1
        self.assertGreater(n, 400)

    def test_bore_probe_is_kept(self):
        self.assertEqual([p["id"] for p in self.plan.passage_probes], [f"{self.mb}:bore"])
        self.assertEqual(self.plan.passage_probes[0]["kind"], "tunnel")
        self.assertNotIn("passage_probes_blocked", self.plan.report)

    def test_deterministic(self):
        again, _ = plan_for(hill_grid())
        a = next(o for o in again.objects if o.mb_id == self.mb)
        self.assertEqual(a.mesh.vertices, self.tube.mesh.vertices)

    def test_package_is_valid(self):
        from .synthetic import write_dem_asc  # noqa: F401  (module import keeps the tests package layout)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "hill.mbmap")
            plan_to_package(self.plan, path, "hill", _sources(d))
            r = validate_package(path)
            self.assertTrue(r.ok, r.errors)


def _sources(d):
    from .synthetic import synthetic_inputs
    return synthetic_inputs(d)[4]


class TunnelVariantsTest(unittest.TestCase):
    def test_gallery_keeps_the_ground_below_the_floor(self):
        grid = gallery_grid()
        plan, wid = plan_for(grid)
        base, _ = plan_for(grid, dict(TUNNEL_TAGS, tunnel="culvert"))
        col, bcol = plan_collision(plan)[0], plan_collision(base)[0]
        x0, y0, nx, ny, sp = -12.13, -3.07, 49, 13, 0.5
        z = rasterize_heightfield(col.class_triangles("terrain"), x0, y0, sp, nx, ny)
        zb = rasterize_heightfield(bcol.class_triangles("terrain"), x0, y0, sp, nx, ny)
        for j in range(ny):
            for i in range(nx):
                self.assertFalse(math.isnan(z[j][i]), (i, j))
                self.assertAlmostEqual(z[j][i], zb[j][i], delta=1e-4)
        tris = tris_of(col, "terrain")
        self.assertEqual(len(hits_at(tris, 0.3, 0.2)), 1)    # the valley floor, ~25 m below the tube

    def test_bore_is_empty_between_floor_and_roof(self):
        """Inside the bore a ray going up meets the roof before any terrain; terrain above the roof stays."""
        grid = hill_grid()
        plan, wid = plan_for(grid)
        col, _ = plan_collision(plan)
        tube = next(o for o in plan.objects if o.mb_id == f"osm:way/{wid}")
        terrain, tunnel = tris_of(col, "terrain"), tris_of(col, "tunnel")
        clearance = tube.provenance["clearance_m"]
        z_off = next(o for o in plan.objects if o.mb_id == "terrain:grid").mesh.vertices[0][2]
        z_off = terrain_height(grid, -50, -50) - z_off
        floor0 = terrain_height(grid, -35, 0) + ROAD_LIFT_M
        floor1 = terrain_height(grid, 35, 0) + ROAD_LIFT_M
        n = 0
        for x in (-30.3, -20.7, -10.1, -1.3, 0.2, 8.9, 19.4, 31.1):
            floor = floor0 + (floor1 - floor0) * (x + 35) / 70.0 - z_off
            roof_hits = [h for h in hits_at(tunnel, x, 0.11) if h > floor + 1.0]
            self.assertTrue(roof_hits, x)
            roof = min(roof_hits)
            self.assertAlmostEqual(roof, floor + clearance, delta=0.3)
            inside = [h for h in hits_at(terrain, x, 0.11) if floor - 0.05 < h < roof - 1e-3]
            self.assertEqual(inside, [], x)     # nothing between the floor and the roof
            self.assertGreaterEqual(max(hits_at(terrain + tunnel, x, 0.11)),
                                    terrain_height(grid, x, 0.11) - z_off - 2e-3)
            n += 1
        self.assertEqual(n, 8)

    def test_cut_is_watertight_and_local_near_the_edge_and_on_grid_lines(self):
        grid = hill_grid()
        for pts, foot in ((((-35, 44), (35, 44)), (-36, 36, 40, 48)), (((-35, 0), (35, 0)), (-36, 36, -4, 4)),
                          (((-30, -20.3), (30, 21.7)), (-34, 34, -26, 26))):
            with self.subTest(pts=pts):
                plan, wid = plan_for(grid, pts=pts)
                base, _ = plan_for(grid, dict(TUNNEL_TAGS, tunnel="culvert"), pts=pts)
                terrain = next(o for o in plan.objects if o.mb_id == "terrain:grid")
                self.assertEqual(terrain_edge_problems(terrain.mesh, 21, 21, 5.0, -50, -50, foot, tol=5.5), [])
                self.assertGreater(plan.report["counts"]["terrain_cut_cells"], 0)
                col, bcol = plan_collision(plan)[0], plan_collision(base)[0]
                x0, y0, nx, ny, sp = -49.13, -49.07, 197, 197, 0.5
                z = rasterize_heightfield(col.class_triangles("terrain"), x0, y0, sp, nx, ny)
                zb = rasterize_heightfield(bcol.class_triangles("terrain"), x0, y0, sp, nx, ny)
                nan = changed = 0
                for j in range(ny):
                    for i in range(nx):
                        x, y = x0 + i * sp, y0 + j * sp
                        if math.isnan(z[j][i]):
                            nan += 1
                            self.assertTrue(foot[0] <= x <= foot[1] and foot[2] <= y <= foot[3], (x, y))
                        elif not (foot[0] <= x <= foot[1] and foot[2] <= y <= foot[3]):
                            self.assertAlmostEqual(z[j][i], zb[j][i], delta=1e-4)
                            changed += 1
                self.assertGreater(nan, 20)
                self.assertGreater(changed, 10000)

    def test_cut_leaves_far_terrain_untouched(self):
        grid = hill_grid()
        plan, _ = plan_for(grid)
        base, _ = plan_for(grid, dict(TUNNEL_TAGS, tunnel="culvert"))
        t = next(o for o in plan.objects if o.mb_id == "terrain:grid").mesh
        b = next(o for o in base.objects if o.mb_id == "terrain:grid").mesh
        far = lambda m: sorted(tuple(m.vertices[v]) for f in m.faces for v in f   # noqa: E731
                               if abs(m.vertices[v][1]) > 12)
        self.assertEqual(far(t), far(b))

    def test_tree_beside_a_portal_never_blocks_the_bore(self):
        ids = {}

        def add(b):
            ids["near"] = b.node(-37.0, 0.0, {"natural": "tree", "height": "8"})
            ids["far"] = b.node(-44.0, 7.0, {"natural": "tree", "height": "8"})

        plan, wid = plan_for(hill_grid(), extra=add)
        self.assertEqual([p["id"] for p in plan.passage_probes], [f"osm:way/{wid}:bore"])
        self.assertNotIn("passage_probes_blocked", plan.report)
        trees = {o.mb_id for o in plan.objects if o.mb_class == "vegetation"}
        self.assertNotIn(f"osm:node/{ids['near']}", trees)
        self.assertIn(f"osm:node/{ids['far']}", trees)
        self.assertTrue(any(e["id"] == f"osm:node/{ids['near']}" and "portal" in e["reason"]
                            for e in plan.report["invalid_features"]))

    def test_probes_are_checked_on_the_finished_scene(self):
        from types import SimpleNamespace
        from map_builder.core.generate import ObjectSpec
        from map_builder.core.structures import finalize_probes
        plan, wid = plan_for(hill_grid())
        pr = plan.passage_probes.pop()
        px, py, pz = pr["path_map"][len(pr["path_map"]) // 2]
        plan.objects.append(ObjectSpec("tree_x", "osm:node/999", "vegetation", "Vegetation", mesh_key="tree_generic",
                                       location=(px, py, pz - 2.0), scale=1.0, provenance={}))
        finalize_probes(plan, SimpleNamespace(probes=[pr]))
        self.assertEqual(plan.passage_probes, [])
        self.assertEqual(plan.report["passage_probes_blocked"], [{"id": pr["id"], "blocker": "osm:node/999"}])

    def test_probe_cap_is_explicit(self):
        from types import SimpleNamespace
        from map_builder.core.package import PASSAGE_PROBE_MAX
        from map_builder.core.structures import finalize_probes
        plan, wid = plan_for(hill_grid())
        pr = plan.passage_probes.pop()
        probes = [dict(pr, id=f"p{k}") for k in range(PASSAGE_PROBE_MAX + 2)]
        finalize_probes(plan, SimpleNamespace(probes=probes))
        self.assertEqual(len(plan.passage_probes), PASSAGE_PROBE_MAX)
        over = plan.report["passage_probes_blocked"]
        self.assertEqual([e["id"] for e in over], ["p256", "p257"])
        self.assertTrue(all(e["blocker"] is None and "cap" in e["reason"] for e in over))

    def test_chunked_probe_check_matches_the_whole_scene_query(self):
        from map_builder.core.generate import ObjectSpec
        from map_builder.core.query import capsule_hits
        from map_builder.core.structures import check_probes
        plan, wid = plan_for(hill_grid())
        pr = plan.passage_probes[0]
        z = pr["path_map"][0][2]
        for k, x in enumerate((-30.0, -4.0, 22.0)):    # trees along the bore, inside it and beside it
            plan.objects.append(ObjectSpec(f"tree_{k}", f"osm:node/90{k}", "vegetation", "Vegetation",
                                           mesh_key="tree_generic", location=(x, 0.0, z - 1.5 + 5.0 * k), scale=1.0,
                                           provenance={}))
        probes = [pr, dict(pr, id="far", path_map=[[x, 30.0, z] for x in range(-45, 46, 3)]),
                  dict(pr, id="wide", radius_m=pr["radius_m"] + 6.0)]
        kept, blocked = check_probes(plan, probes)
        self.assertTrue(blocked, "the fixture should block at least one probe")
        col, _ = plan_collision(plan)
        for p in probes:
            whole = [col.objects[i]["mb_id"] for i in capsule_hits(col, [tuple(q) for q in p["path_map"]],
                                                                   p["radius_m"])]
            got = next((b["blocker"] for b in blocked if b["id"] == p["id"]), None)
            self.assertEqual(got is not None, bool(whole), p["id"])
            if whole:
                self.assertEqual(got, whole[0], p["id"])
            self.assertEqual(any(q["id"] == p["id"] for q in kept), not whole, p["id"])

    def test_cut_matches_the_per_tile_reference_without_gaps_or_overlaps(self):
        import random
        from map_builder.core import generate as G, tunnels as T

        def reference_left(mesh, grid, tubes):
            """Plan area left of every cell after cutting tile by tile, one convex difference per tile."""
            groups = T._roof_triangles(tubes)
            nx, left = grid.nx, {}
            cells = {(i, j) for g in groups
                     for j in range(G._cell_range(grid, *g.bbox)[2], G._cell_range(grid, *g.bbox)[3] + 1)
                     for i in range(G._cell_range(grid, *g.bbox)[0], G._cell_range(grid, *g.bbox)[1] + 1)}
            for (i, j) in sorted(cells):
                if True:
                    for upper in (0, 1):
                        tri = [mesh.vertices[v] for v in mesh.faces[2 * (j * (nx - 1) + i) + upper]]
                        plane = T._plane(*tri)
                        poly = [(p[0], p[1]) for p in tri]
                        pieces = [poly]
                        for g in groups:
                            for rpoly, rplane, fplane, _bb, _e, _fz, _rz in T._tiles_of(g):
                                q = G._clip_convex(poly, rpoly)
                                if len(q) < 3:
                                    continue
                                q = T._clip_linear(q, rplane[0] - plane[0], rplane[1] - plane[1],
                                                   rplane[2] - plane[2])
                                if len(q) >= 3 and fplane is not None:
                                    q = T._clip_linear(q, plane[0] - fplane[0], plane[1] - fplane[1],
                                                       plane[2] - fplane[2] + T.CUT_BELOW_FLOOR_M)
                                if len(q) >= 3 and T._poly_area2(q) > G._MIN_AREA2:
                                    pieces = [r for p in pieces for r in G._convex_difference(p, q)]
                        left[(i, j)] = left.get((i, j), 0.0) + sum(T._poly_area2(p) for p in pieces) / 2.0
            return left

        rng = random.Random(7)
        cases = [((-35, 0), (35, 0)), ((-30, -20.3), (30, 21.7))]
        cases += [((rng.uniform(-40, -20), rng.uniform(-30, 30)), (rng.uniform(20, 40), rng.uniform(-30, 30)))
                  for _ in range(3)]
        grid = hill_grid()
        for pts in cases:
            with self.subTest(pts=pts):
                seen = {}
                real = T.cut_terrain

                def spy(mesh, g, tubes):
                    import copy
                    seen["args"] = (copy.deepcopy(mesh), g, tubes)
                    return real(mesh, g, tubes)

                T.cut_terrain = spy
                try:
                    plan, _ = plan_for(grid, pts=pts)
                finally:
                    T.cut_terrain = real
                before, g, tubes = seen["args"]
                want = reference_left(before, g, tubes)
                mesh = next(o for o in plan.objects if o.mb_id == "terrain:grid").mesh
                got = {}
                for f in mesh.faces:
                    P = [mesh.vertices[v] for v in f]
                    cx, cy = sum(p[0] for p in P) / 3.0, sum(p[1] for p in P) / 3.0
                    key = (int((cx - g.x0) // g.spacing), int((cy - g.y0) // g.spacing))
                    got[key] = got.get(key, 0.0) + abs(T._poly_area2([(p[0], p[1]) for p in P])) / 2.0
                self.assertGreater(len(want), 8)
                for key in want:
                    self.assertAlmostEqual(got.get(key, 0.0), want[key], delta=2e-3, msg=str(key))

    def test_tube_triangles_fit_the_ceiling_and_budget_is_reserved_first(self):
        from map_builder.core import tunnels
        plan, wid = plan_for(hill_grid())
        tube = next(o for o in plan.objects if o.mb_id == f"osm:way/{wid}")
        walls = [o for o in plan.objects if o.mb_id.startswith(f"osm:way/{wid}:headwall")]
        n = len(tunnels.cross_section(6.0, 5.5))
        samples = len(tube.mesh.vertices) // n
        tris = sum(len(f) - 2 for f in tube.mesh.faces) + sum(len(f) - 2 for o in walls for f in o.mesh.faces)
        self.assertLessEqual(tris, 2 * n * (samples - 1) + tunnels.HEADWALL_TRIANGLE_RESERVE * 2)
        # with a budget too small for the reservation, the failure happens before the mesh is allocated
        real = tunnels._tube_mesh
        tunnels._tube_mesh = lambda *a, **k: self.fail("mesh allocated before the budget check")
        from map_builder.core.errors import LimitError
        try:
            with self.assertRaises(LimitError):
                plan_for(hill_grid(), options=PlanOptions(max_triangles=1000))
        finally:
            tunnels._tube_mesh = real

    def test_arc_lookup_matches_a_linear_walk(self):
        from map_builder.core.tunnels import _Arc
        path = [(0, 0, 0), (3, 4, 1), (3, 10, 2), (-5, 10, 5)]
        arc = _Arc(path)
        self.assertAlmostEqual(arc.length, 5 + 6 + 8)
        x, y, z, d, k, s0 = arc.at(5.0)
        self.assertEqual((round(x, 9), round(y, 9), k), (3.0, 4.0, 0))
        x, y, z, d, k, s0 = arc.at(8.0)
        self.assertEqual((round(x, 9), round(y, 9), round(z, 9), k, s0), (3.0, 7.0, 1.5, 1, 5.0))
        self.assertEqual(arc.at(99.0)[4], 2)

    def test_maxheight_sets_clearance(self):
        plan, wid = plan_for(hill_grid(), dict(TUNNEL_TAGS, maxheight="4.2"))
        tube = next(o for o in plan.objects if o.mb_id == f"osm:way/{wid}")
        self.assertEqual(tube.provenance["clearance_m"], 4.2)
        self.assertTrue(tube.provenance["clearance"].startswith("measured"))

    def test_flat_terrain_warns_about_cover(self):
        plan, wid = plan_for(flat_grid())
        self.assertTrue(any("cut-and-cover" in w and f"osm:way/{wid}" in w for w in plan.report["warnings"]))
        self.assertEqual(plan.report["counts"]["tunnels"], 1)

    def test_blocked_probe_names_the_building(self):
        ids = {}

        def add(b):
            ids["b"] = b.way([(-34, -4), (-30, -4), (-30, 4), (-34, 4)], {"building": "yes", "height": "10"},
                             closed=True)

        plan, wid = plan_for(hill_grid(), extra=add)
        self.assertEqual(plan.passage_probes, [])
        self.assertEqual(plan.report["passage_probes_blocked"],
                         [{"id": f"osm:way/{wid}:bore", "blocker": f"osm:way/{ids['b']}"}])

    def test_excluded_tunnels_stay_unsupported(self):
        for tags in (dict(TUNNEL_TAGS, tunnel="culvert"), {"railway": "rail", "tunnel": "yes"},
                     {"highway": "service", "man_made": "tunnel"}):
            with self.subTest(tags=tags):
                plan, wid = plan_for(hill_grid(), tags)
                self.assertNotIn("tunnels", plan.report["counts"])
                self.assertIn(f"osm:way/{wid}", [u["id"] for u in plan.report["unsupported_features"]])

    def test_roads_off_reports_unsupported(self):
        plan, wid = plan_for(hill_grid(), options=PlanOptions(roads=False))
        self.assertNotIn("tunnels", plan.report["counts"])
        self.assertIn(f"osm:way/{wid}", [u["id"] for u in plan.report["unsupported_features"]])


if __name__ == "__main__":
    unittest.main()
