# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""The C# reader's capsule check must match query.capsule_hits: same hit/clear result and same work units per probe.

Skipped when the .NET SDK is not installed (the CI ``csharp-reader`` job runs it)."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from . import csharp_build
from map_builder.core.collision import ColObject, read_collision, write_collision
from map_builder.core.errors import LimitError
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
    @classmethod
    def setUpClass(cls):
        cls.objs, cls.probes = _cases()
        cls.col = read_collision(write_collision(cls.objs))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        with open(os.path.join(cls.tmp.name, "c.mbcol"), "wb") as f:
            f.write(write_collision(cls.objs))
        with open(os.path.join(cls.tmp.name, "p.json"), "w") as f:
            json.dump([{"path": path, "radius": r} for path, r in cls.probes], f)

    def run_reader(self, *extra):
        run = subprocess.run([*csharp_build.reader_command(), "--probe-work", os.path.join(self.tmp.name, "c.mbcol"),
                              os.path.join(self.tmp.name, "p.json"), *extra], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return run.stdout.splitlines()

    def python_unlimited(self):
        out = []
        for path, r in self.probes:
            res = capsule_hits(self.col, path, r, result=True)
            out.append((res.objects, res.work))
        return out

    def python_shared(self, budget):
        """The validator's loop (package.py): probes draw on one budget in order; the first that does not fit
        ends the run, leaving it and every later probe unchecked."""
        out, left = [], budget
        for i, (path, r) in enumerate(self.probes):
            try:
                res = capsule_hits(self.col, path, r, max_work=left, result=True)
            except LimitError:
                out.append(f"probe {i} unchecked")
                break
            left -= res.work
            out.append(f"probe {i} hits={','.join(map(str, res.objects))} left={left}")
        return out

    def test_hits_and_work_match_python_per_probe(self):
        want = [f"probe {i} hits={','.join(map(str, o))} work={w}" for i, (o, w) in enumerate(self.python_unlimited())]
        self.assertEqual(self.run_reader(), want)
        self.assertTrue(any(not w.split("hits=")[1].startswith(" work") for w in want), "no probe hit anything")
        self.assertTrue(any(w.split("hits=")[1].startswith(" work") for w in want), "no probe was clear")

    def test_shared_budget_boundary_matches_python(self):
        works = [w for _, w in self.python_unlimited()]
        total = sum(works)
        prefix = sum(works[:4])
        for budget in (total, total - 1, prefix, prefix - 1, works[0], works[0] - 1):
            got = self.run_reader(str(budget))
            self.assertEqual(got, self.python_shared(budget), f"shared budget {budget}")
        self.assertEqual(len(self.run_reader(str(total))), len(self.probes))            # exact fit: all checked, left 0
        self.assertTrue(self.run_reader(str(total))[-1].endswith("left=0"))
        short = self.run_reader(str(total - 1))
        self.assertEqual(short[-1], f"probe {len(self.probes) - 1} unchecked")           # one unit short: last unchecked
        self.assertEqual(len(short), len(self.probes))
        self.assertEqual(self.run_reader(str(prefix))[-1], "probe 4 unchecked")          # first four fit exactly
        self.assertEqual(self.run_reader(str(prefix - 1))[-1], "probe 3 unchecked")      # one unit short of them


@unittest.skipUnless(shutil.which("dotnet"), "the .NET SDK is not installed")
class CsharpTexturedPackageTest(unittest.TestCase):
    """Schema 2.1: the C# reader accepts the textured fixture and rejects each negative fixture with the same
    rule as the Python validator (shared message fragment). One --validate-many process covers all packages."""

    @classmethod
    def setUpClass(cls):
        from .make_textured_fixture import negative_fixtures
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.fixtures = negative_fixtures(cls.tmp.name)
        run = subprocess.run([*csharp_build.reader_command(), "--validate-many", cls.tmp.name], capture_output=True, text=True)
        cls.verdicts = dict(line.split(": ", 1) for line in run.stdout.splitlines())

    def test_textured_package_is_accepted(self):
        self.assertEqual(self.verdicts["good.mbmap"], "OK")

    def test_every_negative_fixture_is_rejected_like_python(self):
        self.assertEqual(len(self.verdicts), len(self.fixtures))
        for name, (_, fragment, _kind) in self.fixtures.items():
            if name == "good":
                continue
            with self.subTest(name):
                verdict = self.verdicts[name + ".mbmap"]
                self.assertTrue(verdict.startswith("INVALID:") and fragment in verdict, verdict)


@unittest.skipUnless(shutil.which("dotnet"), "the .NET SDK is not installed")
class CsharpBuildHygieneTest(unittest.TestCase):
    def test_the_reader_is_built_once_per_run_whatever_the_number_of_callers(self):
        csharp_build.reader_dll()
        csharp_build.reader_dll()
        self.assertEqual(csharp_build.BUILD_COUNT, 1)

    def test_a_failed_build_is_attempted_once_per_run(self):
        from unittest import mock
        failed = subprocess.CompletedProcess([], 1, "", "boom")
        with mock.patch.object(csharp_build, "_dll", None), mock.patch.object(csharp_build, "_failure", None), \
                mock.patch.object(csharp_build, "_outdir", None), mock.patch.object(csharp_build, "BUILD_COUNT", 0), \
                mock.patch.object(csharp_build.subprocess, "run", return_value=failed) as run:
            for _ in range(3):
                with self.assertRaises(RuntimeError):
                    csharp_build.reader_dll()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(csharp_build.BUILD_COUNT, 1)
            csharp_build._cleanup()

    def test_a_launch_error_is_attempted_once_per_run(self):
        from unittest import mock
        with mock.patch.object(csharp_build, "_dll", None), mock.patch.object(csharp_build, "_failure", None), \
                mock.patch.object(csharp_build, "_outdir", None), mock.patch.object(csharp_build, "BUILD_COUNT", 0), \
                mock.patch.object(csharp_build.subprocess, "run", side_effect=FileNotFoundError("dotnet")) as run:
            for _ in range(3):
                with self.assertRaises(RuntimeError):
                    csharp_build.reader_dll()
            self.assertEqual(run.call_count, 1)
            csharp_build._cleanup()

    def test_the_repo_nuget_config_ignores_user_level_feeds(self):
        with open(os.path.join(ROOT, "NuGet.config"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("<clear />", text)
        self.assertEqual(text.count("<add key="), 1)


if __name__ == "__main__":
    unittest.main()
