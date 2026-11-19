"""Shared structure helpers (map_builder/core/structures.py): sweep, polyline_z_profile, check_probes."""

import types
import unittest

from map_builder.core.collision import ColObject, read_collision, write_collision
from map_builder.core.generate import InvalidFeature, ObjectSpec
from map_builder.core.mesh import MeshData
from map_builder.core.package import collision_orientation_problems
from map_builder.core.structures import check_probes, plan_collision, polyline_z_profile, sweep

BOX = [(-1.0, 0.0), (1.0, 0.0), (1.0, 2.0), (-1.0, 2.0)]
STRAIGHT = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0)]


def problems(mesh, cls, scale=1.0):
    spec = ObjectSpec(mesh.name, "osm:way/1", cls, "X", mesh=mesh, scale=scale)
    plan = types.SimpleNamespace(objects=[spec], shared_meshes={})
    col, _ = plan_collision(plan)
    return collision_orientation_problems(col)


def box_mesh(name, x0, x1, y0, y1, z0, z1):
    m = MeshData(name)
    for z in (z0, z1):
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            m.add_vertex(x, y, z)
    for q in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        m.add_face(q, "MB Concrete", (1, 1, 1))
    return m


class SweepTest(unittest.TestCase):
    def test_closed_ends_is_a_valid_solid(self):
        self.assertEqual(problems(sweep(BOX, STRAIGHT, True), "bridge"), [])

    def test_open_ends_is_a_valid_tube(self):
        self.assertEqual(problems(sweep(BOX, STRAIGHT, False), "tunnel"), [])

    def test_wrong_rule_is_rejected(self):
        self.assertNotEqual(problems(sweep(BOX, STRAIGHT, False), "bridge"), [])
        self.assertNotEqual(problems(sweep(BOX, STRAIGHT, True), "tunnel"), [])

    def test_mirrored_copies_keep_their_rule(self):
        for closed, cls in ((True, "bridge"), (False, "tunnel")):
            for scale in ((-1.0, 1.0, 1.0), (1.0, -1.0, 1.0), (-1.0, -1.0, 1.0)):
                with self.subTest(cls=cls, scale=scale):
                    self.assertEqual(problems(sweep(BOX, STRAIGHT, closed), cls, scale), [])

    def test_gentle_turn_is_valid_and_sharp_turn_is_rejected(self):
        gentle = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (18.0, 5.0, 1.0)]
        self.assertEqual(problems(sweep(BOX, gentle, True), "bridge"), [])
        with self.assertRaises(InvalidFeature):
            sweep(BOX, [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)], True)

    def test_degenerate_input(self):
        for profile, path in ((BOX[:2], STRAIGHT), (BOX, STRAIGHT[:1]), (BOX, [STRAIGHT[0], STRAIGHT[0]])):
            with self.assertRaises(InvalidFeature):
                sweep(profile, path, True)


class ZProfileTest(unittest.TestCase):
    def test_arc_length_and_subdivision(self):
        out = polyline_z_profile([(0, 0), (3, 4), (3, 14)], lambda x, y: x + y, max_step=5.0)
        self.assertEqual([round(s, 6) for s, *_ in out], [0.0, 5.0, 10.0, 15.0])
        self.assertEqual(out[-1][1:], (3.0, 14.0, 17.0))


class ProbeTest(unittest.TestCase):
    def plan(self, *extra):
        tube = sweep(BOX, STRAIGHT, False, name="tube")
        specs = [ObjectSpec("tube", "osm:way/9", "tunnel", "Tunnels", mesh=tube)]
        specs += [ObjectSpec(m.name, mb, "building", "Buildings", mesh=m) for mb, m in extra]
        return types.SimpleNamespace(objects=specs, shared_meshes={})

    PROBE = {"id": "p1", "kind": "tunnel", "feature": "osm:way/9", "radius_m": 0.3,
             "path_map": [(-5.0, 0.0, 1.0), (25.0, 0.0, 1.0)]}

    def test_open_tube_passes(self):
        kept, blocked = check_probes(self.plan(), [self.PROBE])
        self.assertEqual((kept, blocked), ([self.PROBE], []))

    def test_blocker_is_named(self):
        plan = self.plan(("osm:way/77", box_mesh("blocker", 8, 12, -0.5, 0.5, 0.5, 1.5)))
        kept, blocked = check_probes(plan, [self.PROBE])
        self.assertEqual(kept, [])
        self.assertEqual(blocked, [{"id": "p1", "blocker": "osm:way/77"}])

    def test_budget_exhaustion_is_reported(self):
        kept, blocked = check_probes(self.plan(), [self.PROBE, dict(self.PROBE, id="p2")], max_work=3)
        self.assertEqual(kept, [])
        self.assertEqual([b["id"] for b in blocked], ["p1", "p2"])
        self.assertTrue(all(b["blocker"] is None and "budget" in b["reason"] for b in blocked))


if __name__ == "__main__":
    unittest.main()
