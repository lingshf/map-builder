"""PERF-PROBE-INDEX: the indexed probe check gives exactly the brute-force (reference) result."""

import copy
import functools
import math
import random
import unittest
from types import SimpleNamespace
from unittest import mock

from map_builder.core import package, passages, structures
from map_builder.core.generate import MeshData, ObjectSpec, ScenePlan
from map_builder.core.geodesy import Area


def _box(name, x, y, z, w, d, h):
    m = MeshData(name)
    v = [m.add_vertex(x + dx, y + dy, z + dz) for dz in (0, h) for dy in (0, d) for dx in (0, w)]
    for f in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
        m.add_face(tuple(v[i] for i in f), "m", (0.5, 0.5, 0.5))
    return m


def _scene(rng):
    plan = ScenePlan(None, Area(47.0, 8.0, 200.0, 200.0))
    n = 61    # 2 m cells: a probe's tiles hold > 256 terrain triangles, so the grid path runs
    ter = MeshData("terrain")
    for j in range(n):
        for i in range(n):
            ter.add_vertex(-60 + i * 2.0, -60 + j * 2.0, 3 * math.sin(i / 8.0) + 2 * math.cos(j / 10.0))
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            ter.add_face((a, a + 1, a + n + 1), "m", (0.5, 0.5, 0.5))
            ter.add_face((a, a + n + 1, a + n), "m", (0.5, 0.5, 0.5))
    plan.objects.append(ObjectSpec("terrain", "osm:terrain", "terrain", "Terrain", mesh=ter))
    for k in range(40):
        x, y = rng.uniform(-90, 80), rng.uniform(-90, 80)
        md = _box(f"b{k}", 0, 0, 0, rng.uniform(3, 14), rng.uniform(3, 14), rng.uniform(3, 12))
        plan.objects.append(ObjectSpec(f"b{k}", f"osm:way/{k}", "building", "Buildings", mesh=md,
                                       location=(x, y, rng.uniform(-2, 4)), rotation_z=rng.uniform(0, 6.28),
                                       scale=rng.choice((1.0, 1.0, 1.3))))
    tree = MeshData("tree")
    for p in ((0, 0, 0), (1, 0, 0), (0, 1, 3)):
        tree.add_vertex(*p)
    tree.add_face((0, 1, 2), "m", (0.1, 0.5, 0.1))
    plan.shared_meshes["tree"] = tree
    for k in range(30):
        plan.objects.append(ObjectSpec(f"t{k}", f"osm:node/{k}", "vegetation", "Vegetation", mesh_key="tree",
                                       location=(rng.uniform(-90, 90), rng.uniform(-90, 90), rng.uniform(0, 4)),
                                       scale=rng.uniform(1, 3)))
    probes = []
    for k in range(36):
        x, y, z = rng.uniform(-90, 80), rng.uniform(-90, 80), rng.uniform(-1, 8)
        heading, path = rng.uniform(0, 6.28), []
        for _ in range(rng.randint(2, 7)):
            path.append([x, y, z])
            heading += rng.uniform(-0.4, 0.4)
            step = rng.uniform(4, 30)
            x, y, z = x + step * math.cos(heading), y + step * math.sin(heading), z + rng.uniform(-1, 1)
        kind = rng.choice(("elevated", "tunnel", "deck", "under"))
        probes.append({"id": f"{kind}{k}", "kind": kind, "feature": f"f{k}", "path_map": path,
                       "radius_m": rng.choice((0.3, 0.8, 1.5, 2.5))})
    return plan, probes


def _finalize(seed, indexed, work=None, cap=None):
    """Finalise the random scene's probes (ELEV staged on the plan, tunnel and bridge ones on ``ctx.probes``, in
    one mixed order) and return everything an observer sees."""
    plan, probes = _scene(random.Random(seed))
    ctx = SimpleNamespace(probes=[p for p in probes if p["kind"] != "elevated"], terrain=None)
    elev = [p for p in probes if p["kind"] == "elevated"]
    plan.passage_probes.extend(copy.deepcopy(elev))
    passages._state(ctx).probes = [p["id"] for p in elev]
    ctx.probes = copy.deepcopy(ctx.probes)
    budget = structures.WorkBudget(work if work is not None else structures.DEFAULT_MAX_WORK)
    check = functools.partial(structures.check_probes, indexed=indexed)
    patches = [mock.patch.object(structures, "WorkBudget", lambda: budget),
               mock.patch.object(structures, "check_probes", check), mock.patch.object(passages, "check_probes", check)]
    if cap is not None:
        patches.append(mock.patch.object(package, "PASSAGE_PROBE_MAX", cap))
    for p in patches:
        p.start()
    try:
        structures.finalize_probes(plan, ctx)
    finally:
        for p in patches:
            p.stop()
    return plan.passage_probes, plan.report, budget.left


class ProbeIndexDifferentialTest(unittest.TestCase):
    def test_indexed_equals_brute_force_on_random_scenes(self):
        outcomes = set()
        for seed in range(2):
            ref = _finalize(seed, False)
            self.assertEqual(_finalize(seed, True), ref)
            cost = structures.DEFAULT_MAX_WORK - ref[2]
            self.assertGreater(cost, 0)
            blocked = ref[1].get("passage_probes_blocked", [])
            outcomes.update(("blocked", "kept") if blocked and ref[0] else ())
            for fraction in (0.2, 0.7):    # the shared budget runs out part-way (the failed call is debited)
                work = int(cost * fraction)
                short = _finalize(seed, False, work=work)
                self.assertEqual(_finalize(seed, True, work=work), short)
                if any(e.get("reason") == "budget_exhausted" for e in short[1].get("passage_probes_blocked", [])):
                    outcomes.add("budget_exhausted")
                    self.assertEqual(short[2], 0)
            capped = _finalize(seed, False, cap=3)
            self.assertEqual(_finalize(seed, True, cap=3), capped)
            if "passage_probes_dropped" in capped[1]:
                outcomes.add("dropped")
        self.assertEqual(outcomes, {"blocked", "kept", "budget_exhausted", "dropped"})


if __name__ == "__main__":
    unittest.main()
