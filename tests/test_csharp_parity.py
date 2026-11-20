"""The C# reader's capsule check must match query.capsule_hits: same hit/clear result and same work units per probe.

Skipped when the .NET SDK is not installed (the CI ``csharp-reader`` job runs it)."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from map_builder.core.collision import ColObject, read_collision, write_collision
from map_builder.core.query import capsule_hits

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "examples", "csharp", "MbmapReader")


def _grid_object(name, n, step=2.0, z=0.0):
    """n triangles laid out on a row-major strip of squares, one 8 m cell holding several of them."""
    verts, tris = [], []
    side = int(n ** 0.5) + 1
    for k in range(n):
        x, y = (k % side) * step, (k // side) * step
        o = len(verts)
        verts += [(x, y, z), (x + step, y, z), (x, y + step, z)]
        tris.append((o, o + 1, o + 2))
    return ColObject(name, "terrain:grid" if name == "ground" else f"osm:way/{n}", "terrain" if name == "ground" else "prop", verts, tris)


def _cases():
    objs = [
        _grid_object("ground", 900, z=0.0),                                   # grid object, many cells
        _grid_object("slab", 300, step=1.0, z=5.0),                           # grid object, dense cells
        ColObject("small", "osm:way/5", "prop", [(100, 100, 0), (104, 100, 0), (100, 104, 0)], [(0, 1, 2)]),
        ColObject("big", "osm:way/6", "prop",                                  # 300 tris incl. a "big" one (> 64 cells)
                  [(i * 10.0, 200.0, 0.0) for i in range(300)] * 1 + [(i * 10.0 + 5, 205.0, 0.0) for i in range(300)]
                  + [(-1e5, -1e5, 50.0), (1e5, -1e5, 50.0), (0.0, 1e5, 50.0)],
                  [(i, i + 300, (i + 1) % 300) for i in range(299)] + [(600, 601, 602)] * 2),
    ]
    long_path = [(float(i), 1.0 + (i % 7) * 0.5, 0.4 + (i % 5) * 0.01) for i in range(0, 120)]
    return objs, [
        ([(0.5, 0.5, 0.2), (3.0, 1.0, 0.2)], 0.3),                            # hits ground (grid)
        ([(0.5, 0.5, 2.0), (3.0, 1.0, 2.0)], 0.3),                            # clear, plane-clear prefilter
        ([(0.0, 0.0, 4.7), (30.0, 10.0, 4.7)], 0.5),                          # hits slab
        (long_path, 0.2),                                                      # long path, many segments
        ([(-500.0, -500.0, 300.0), (-400.0, -500.0, 300.0), (-300.0, -500.0, 300.0)], 0.5),  # whole-path skip
        ([(-1e6, 0.0, 50.2), (1e6, 0.0, 50.2)], 0.5),                          # query spans > 1024 cells: scan fallback
        ([(101.0, 101.0, 0.2)], 0.1),                                          # single point (sphere)
        ([(1.0, 1.0, 49.0), (2.0, 1.0, 49.0)], 0.5),                          # near the big triangle, clear
        ([(0.0, 195.0, 0.5), (3000.0, 195.0, 0.5)], 6.0),                      # long segment through the many-tri object
    ]


@unittest.skipUnless(shutil.which("dotnet"), "the .NET SDK is not installed")
class CsharpCapsuleParityTest(unittest.TestCase):
    def test_hits_and_work_match_python_per_probe(self):
        objs, probes = _cases()
        col = read_collision(write_collision(objs))
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "c.mbcol"), "wb") as f:
                f.write(write_collision(objs))
            with open(os.path.join(d, "p.json"), "w") as f:
                json.dump([{"path": path, "radius": r} for path, r in probes], f)
            build = subprocess.run(["dotnet", "build", "-c", "Release", "-nologo", "-v", "q", PROJECT],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run(["dotnet", os.path.join(PROJECT, "bin", "Release", "net8.0", "MbmapReader.dll"),
                                  "--probe-work", os.path.join(d, "c.mbcol"), os.path.join(d, "p.json")],
                                 capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        got = run.stdout.splitlines()
        self.assertEqual(len(got), len(probes), run.stdout)
        want = []
        for i, (path, r) in enumerate(probes):
            res = capsule_hits(col, path, r, result=True)
            want.append(f"probe {i} hits={','.join(map(str, res.objects))} work={res.work}")
        self.assertEqual(got, want)
        self.assertTrue(any("hits=" in w and "hits= " not in w and not w.split("hits=")[1].startswith(" ") for w in want))
        self.assertTrue(any(w.split("hits=")[1].startswith(" work") for w in want))


if __name__ == "__main__":
    unittest.main()
