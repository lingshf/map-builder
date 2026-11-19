"""The committed examples/synthetic_sample.mbmap must stay valid and reproducible (see examples/README.md)."""

import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
import shutil
import struct
import tempfile
import unittest
import zipfile

from map_builder.core.collision import read_collision, read_heightfield
from map_builder.core.glb import read_glb
from map_builder.core.package import validate_package

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "examples", "synthetic_sample.mbmap")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
# Must match the command documented in examples/README.md.
BUILD_ARGS = ["build", "--osm", os.path.join(FIXTURES, "synthetic_area.osm"),
              "--dem", os.path.join(FIXTURES, "synthetic_dem.asc"), "--datum", "SYNTHETIC",
              "--dem-license", "SYNTHETIC test data (no licence required)",
              "--osm-license", "SYNTHETIC test fixture (hand-written OSM-format XML, not OpenStreetMap data; no licence required)", "--lat", "47.0", "--lon", "8.0",
              "--width", "400", "--height", "300", "--heightfield", "2", "--created-utc", "2026-01-01T00:00:00Z",
              "--name", "synthetic_sample"]


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _members(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


_CT = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _glb_accessors(glb):
    """Decoded values of every accessor (positions, normals, colours, indices...) of a trusted GLB."""
    jlen = struct.unpack_from("<I", glb, 12)[0]
    gl = json.loads(glb[20:20 + jlen])
    bin_start = 20 + jlen + 8
    out = []
    for a in gl.get("accessors", []):
        v = gl["bufferViews"][a["bufferView"]]
        fmt, nc = _CT[a["componentType"]], _NC[a["type"]]
        elem = struct.calcsize("<" + fmt) * nc
        stride = v.get("byteStride") or elem
        start = bin_start + v.get("byteOffset", 0) + a.get("byteOffset", 0)
        out.append([x for k in range(a["count"]) for x in struct.unpack_from(f"<{nc}{fmt}", glb, start + k * stride)])
    return out


def _approx_equal(test, a, b, where, msg, tol=1e-4):
    """Recursive equality; floats within ``tol``; file hashes/sizes (which follow the floats) skipped."""
    if isinstance(a, dict) and isinstance(b, dict):
        test.assertEqual(sorted(a), sorted(b), f"{msg} ({where})")
        for k in a:
            if k in ("sha256", "bytes") and where.startswith("manifest.files"):
                continue
            _approx_equal(test, a[k], b[k], f"{where}.{k}", msg, tol)
    elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        test.assertEqual(len(a), len(b), f"{msg} ({where})")
        for i, (x, y) in enumerate(zip(a, b)):
            _approx_equal(test, x, y, f"{where}[{i}]", msg, tol)
    elif isinstance(a, float) or isinstance(b, float):
        test.assertIsInstance(b, (int, float), f"{msg} ({where})")
        if not (math.isnan(a) and math.isnan(b)):
            test.assertLessEqual(abs(a - b), tol, f"{msg} ({where})")
    else:
        test.assertEqual(a, b, f"{msg} ({where})")


class SyntheticSampleTest(unittest.TestCase):
    def test_committed_sample_is_valid(self):
        r = validate_package(SAMPLE)
        self.assertTrue(r.ok, r.summary())

    def test_synthetic_sample_is_not_credited_as_openstreetmap(self):
        with zipfile.ZipFile(SAMPLE) as z:
            notices = z.read("NOTICES.txt").decode("utf-8")
            sources = json.loads(z.read("manifest.json"))["sources"]
        self.assertNotIn("ODbL", notices)
        self.assertNotIn("OpenStreetMap contributors", notices)
        self.assertTrue(all("SYNTHETIC" in s["attribution"] for s in sources), sources)

    def test_osm_license_override_only_for_local_files(self):
        from map_builder.core.pipeline import Settings, osm_source_entry
        with self.assertRaises(ValueError):
            Settings(elevation_source="file", elevation_file="d.asc", osm_source="overpass", osm_license="mine")
        with self.assertRaises(ValueError):
            Settings(elevation_source="file", elevation_file="d.asc", osm_source="file", osm_file="a.osm",
                     osm_license="  ")

        class Osm:
            source = {"provider": "local-file"}
            timestamp = None
        self.assertEqual(osm_source_entry(Osm())["license"]["id"], "ODbL-1.0")
        declared = osm_source_entry(Osm(), "own survey, CC0")
        self.assertEqual((declared["license"]["id"], declared["attribution"]), ("user-declared", "own survey, CC0"))
        self.assertNotIn("OpenStreetMap", declared["product"].replace("not OpenStreetMap", ""))

    def test_committed_sample_matches_a_fresh_deterministic_build(self):
        tmp = tempfile.mkdtemp()
        try:
            out_path = os.path.join(tmp, "synthetic_sample.mbmap")
            spec = importlib.util.spec_from_file_location("mbmap_cli", os.path.join(ROOT, "tools", "mbmap_cli.py"))
            cli = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cli)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(BUILD_ARGS + ["--out", out_path])
            self.assertEqual(code, 0, err.getvalue())
            if _sha256(out_path) == _sha256(SAMPLE):
                return
            # Not byte-identical. Tolerate only last-ulp float differences between platform maths
            # libraries (e.g. Windows vs Linux libm); any structural or real numeric change fails.
            fresh, committed = _members(out_path), _members(SAMPLE)
            stale = "examples/synthetic_sample.mbmap is stale; regenerate it with the command in examples/README.md"
            self.assertEqual(sorted(fresh), sorted(committed), stale)
            _approx_equal(self, json.loads(fresh["manifest.json"]), json.loads(committed["manifest.json"]),
                          "manifest", stale)
            _approx_equal(self, json.loads(fresh["report.json"]), json.loads(committed["report.json"]),
                          "report", stale)
            self.assertEqual(fresh["NOTICES.txt"], committed["NOTICES.txt"], stale)
            a, b = read_collision(fresh["collision/map.mbcol"]), read_collision(committed["collision/map.mbcol"])
            self.assertEqual((a.indices, a.tri_object, a.tri_class), (b.indices, b.tri_object, b.tri_class), stale)
            _approx_equal(self, [list(v) for v in a.vertices], [list(v) for v in b.vertices], "vertices", stale)
            _approx_equal(self, a.objects, b.objects, "objects", stale)
            _approx_equal(self, read_heightfield(fresh["collision/terrain.mbhf"]),
                          read_heightfield(committed["collision/terrain.mbhf"]), "heightfield", stale)
            (ga, na), (gb, nb) = read_glb(fresh["visual/map.glb"]), read_glb(committed["visual/map.glb"])
            _approx_equal(self, ga, gb, "glb.json", stale)
            _approx_equal(self, [(n.index, n.name, n.extras, n.matrix, n.triangles) for n in na],
                          [(n.index, n.name, n.extras, n.matrix, n.triangles) for n in nb], "glb.nodes", stale)
            acc_a, acc_b = _glb_accessors(fresh["visual/map.glb"]), _glb_accessors(committed["visual/map.glb"])
            self.assertEqual(len(acc_a), len(acc_b), stale)
            for i, (x, y) in enumerate(zip(acc_a, acc_b)):
                if x and isinstance(x[0], int):
                    self.assertEqual(x, y, f"{stale} (glb.accessors[{i}])")
                else:
                    _approx_equal(self, x, y, f"glb.accessors[{i}]", stale)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_created_utc_format_is_enforced(self):
        spec = importlib.util.spec_from_file_location("mbmap_cli", os.path.join(ROOT, "tools", "mbmap_cli.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        args = [a if a != "2026-01-01T00:00:00Z" else "2026-01-01 00:00" for a in BUILD_ARGS]
        for bad in (args, [a if a != "2026-01-01T00:00:00Z" else "2026-02-30T00:00:00Z" for a in BUILD_ARGS],
                    [a if a != "2026-01-01T00:00:00Z" else "2026-01-01T00:00:60Z" for a in BUILD_ARGS]):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    cli.main(bad + ["--out", os.path.join(tempfile.gettempdir(), "never_written.mbmap")])
            self.assertEqual(cm.exception.code, 2)

    def test_validator_rejects_impossible_created_utc(self):
        from map_builder.core.package import is_utc_timestamp
        self.assertTrue(is_utc_timestamp("2024-02-29T23:59:59.5Z"))
        for bad in ("2026-02-30T00:00:00Z", "2026-13-01T00:00:00Z", "2026-01-01T24:00:00Z",
                    "2026-01-01T00:00:60Z", "2026-01-01T00:00:61Z", "2026-01-01T00:00:00.\u0661Z", None):
            self.assertFalse(is_utc_timestamp(bad), bad)


if __name__ == "__main__":
    unittest.main()
