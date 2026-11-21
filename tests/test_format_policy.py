# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Tests of the ``.mbmap`` compatibility and stability policy (D101, draft; docs/PACKAGE_FORMAT.md).

Synthetic in-memory packages only. The future-minor fixture (2.2.0) must load in the current validator and in the
frozen v0.3.0 Python and C# readers (D57, D65); a different major and an unknown ``.mbcol`` format number must be
rejected. The C# cases reuse the shared build (``csharp_build``); the frozen C# reader is built once per run from
``git archive v0.3.0`` the same way. Frozen readers are never modified; they are skipped when the v0.3.0 tag, git or
the .NET SDK is missing (CI fetches the tag).
"""

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

from map_builder.core.package import PACKAGE_SCHEMA_VERSION, file_entry, manifest_bytes, validate_package

from . import csharp_build
from .make_textured_fixture import _load, build_textured_package, edit_glb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUTURE_MINOR = "2.2.0"
EXTRA = "extra/future.bin"
REQUIRED = os.environ.get("MBMAP_REQUIRE_FROZEN") == "1"
HAVE_DOTNET = shutil.which("dotnet") is not None


def unavailable(why):
    """Skip locally; fail where the prerequisite is mandatory (CI)."""
    if REQUIRED:
        raise AssertionError(f"MBMAP_REQUIRE_FROZEN=1 but {why}")
    raise unittest.SkipTest(why)


def write_raw(path, members, manifest):
    """Write without validation; files[] re-hashed so that only the targeted rule is violated."""
    manifest["files"] = [file_entry(p, members[p]) if p != EXTRA else
                         {"path": p, "role": "future_extra", "media_type": "application/octet-stream",
                          "sha256": hashlib.sha256(members[p]).hexdigest(), "bytes": len(members[p])}
                         for p in sorted(members)]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", manifest_bytes(manifest))
        for name in sorted(members):
            z.writestr(name, members[name])


def _glb_extras(gl, binb):
    gl["extras"] = {"future_minor": {"note": "ignored by readers"}}
    gl["asset"]["extras"] = {"future_minor": True}
    gl["nodes"][0]["extras"] = {"future_minor": 1}
    gl["materials"][0]["extras"] = {"future_minor": "x"}


def _git_archive_v030(dest):
    git = subprocess.run(["git", "archive", "v0.3.0", "map_builder", "tools", "examples/csharp"], cwd=ROOT,
                         capture_output=True)
    if git.returncode != 0:
        return False
    tar = subprocess.run(["tar", "-x", "-C", dest], input=git.stdout, capture_output=True)
    return tar.returncode == 0


class Fixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        base = os.path.join(cls.tmp.name, "base.mbmap")
        build_textured_package(base)
        cls.members, cls.manifest = _load(base)

    def package(self, name, mutate):
        members, manifest = dict(self.members), json.loads(json.dumps(self.manifest))
        mutate(members, manifest)
        path = os.path.join(self.tmp.name, name + ".mbmap")
        write_raw(path, members, manifest)
        return path

    # --- fixtures -------------------------------------------------------------------------------

    @staticmethod
    def _future_minor(members, manifest):
        manifest["schema_version"] = FUTURE_MINOR
        manifest["x_future_field"] = {"anything": [1, 2, 3]}
        members["visual/map.glb"] = edit_glb(members["visual/map.glb"], _glb_extras)

    def future_minor(self):
        return self.package("future_minor", self._future_minor)

    def major3(self):
        return self.package("major3", lambda members, manifest: manifest.__setitem__("schema_version", "3.0.0"))

    def mbcol_v3(self):
        def mutate(members, manifest):
            col = bytearray(members["collision/map.mbcol"])
            struct.pack_into("<I", col, 8, 3)   # header: 8-byte magic, then the format number
            members["collision/map.mbcol"] = bytes(col)
        return self.package("mbcol_v3", mutate)

    def extra_member(self):
        def mutate(members, manifest):
            self._future_minor(members, manifest)
            members["extra/future.bin"] = b"future minor payload"
        path = self.package("extra_member", mutate)
        with zipfile.ZipFile(path) as z:   # the member is listed with its hash, not merely present
            m = json.loads(z.read("manifest.json"))
        self.assertIn("extra/future.bin", [f["path"] for f in m["files"]])
        return path

    def run_cs(self, command, path):
        run = subprocess.run([*command, path], capture_output=True, text=True)
        return run.returncode, run.stdout + run.stderr


class PythonPolicyTest(Fixtures):
    def test_current_schema_is_2_1_0_and_fixture_is_a_later_minor(self):
        self.assertEqual(PACKAGE_SCHEMA_VERSION, "2.1.0")
        self.assertEqual(self.manifest["schema_version"], "2.1.0")

    def test_validator_accepts_future_minor(self):
        r = validate_package(self.future_minor())
        self.assertEqual(r.errors, [])
        self.assertIsNotNone(r.package_id)

    def test_validator_rejects_major_3(self):
        r = validate_package(self.major3())
        self.assertTrue(any("unsupported schema major version 3" in e for e in r.errors), r.errors)
        self.assertIsNone(r.package_id)

    def test_validator_rejects_unknown_mbcol_format_number(self):
        r = validate_package(self.mbcol_v3())
        self.assertTrue(any("collision: unsupported version 3" in e for e in r.errors), r.errors)

    def test_validator_extra_listed_member_is_a_warning(self):
        """Today's rule: a hashed, listed unknown member passes the Python validator with a warning only."""
        r = validate_package(self.extra_member())
        self.assertEqual(r.errors, [])
        self.assertTrue(any("unknown package member ignored" in w for w in r.warnings), r.warnings)


@unittest.skipUnless(HAVE_DOTNET, "the .NET SDK is not installed")
class CsharpPolicyTest(Fixtures):
    def test_current_csharp_rejects_major_3(self):
        code, out = self.run_cs(csharp_build.reader_command(), self.major3())
        self.assertEqual(code, 1, out)
        self.assertIn("unsupported schema major version 3", out)

    def test_current_csharp_rejects_unknown_mbcol_format_number(self):
        code, out = self.run_cs(csharp_build.reader_command(), self.mbcol_v3())
        self.assertEqual(code, 1, out)
        self.assertIn("collision: unsupported version 3", out)

    def test_current_csharp_accepts_future_minor(self):
        code, out = self.run_cs(csharp_build.reader_command(), self.future_minor())
        self.assertEqual(code, 0, out)

    def test_csharp_rejects_extra_listed_member(self):
        """Rule, not additive: both C# readers treat an unknown member as an error (warnings are errors), unlike the
        Python validator, so the positive fixture omits an extra member (docs/PACKAGE_FORMAT.md)."""
        code, out = self.run_cs(csharp_build.reader_command(), self.extra_member())
        self.assertEqual(code, 1, out)
        self.assertIn("unknown package member", out)


@unittest.skipUnless(HAVE_DOTNET and shutil.which("git") and shutil.which("tar"), "needs dotnet, git and tar")
class FrozenReadersTest(Fixtures):
    """The frozen v0.3.0 Python validator and C# reader on the future-minor fixture (D57, D65)."""

    frozen_dir = None
    frozen_dll = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if subprocess.run(["git", "rev-parse", "--verify", "-q", "v0.3.0^{tag}"], cwd=ROOT,
                          capture_output=True).returncode != 0 and subprocess.run(
                ["git", "rev-parse", "--verify", "-q", "v0.3.0"], cwd=ROOT, capture_output=True).returncode != 0:
            unavailable("the v0.3.0 tag is not available (CI fetches tags)")
        frozen = os.path.join(cls.tmp.name, "v030")
        os.makedirs(frozen)
        if not _git_archive_v030(frozen):
            unavailable("git archive v0.3.0 failed")
        cls.frozen_dir = frozen
        out = os.path.join(cls.tmp.name, "frozen-bin")
        src = os.path.join(frozen, "examples", "csharp", "MbmapReader")
        with csharp_build._FileLock(os.path.join(tempfile.gettempdir(), "mbmap-reader-build.lock")):
            build = subprocess.run(
                ["dotnet", "build", "-c", "Release", "-nologo", "-v", "q", src, "-o", out,
                 f"-p:RestoreConfigFile={os.path.join(ROOT, 'NuGet.config')}", "-p:NuGetAudit=false",
                 "-p:WarningsNotAsErrors=NU1900", "-p:UseSharedCompilation=false"], capture_output=True, text=True)
        if build.returncode != 0:
            raise RuntimeError("frozen reader build failed:\n" + build.stdout + build.stderr)
        cls.frozen_dll = os.path.join(out, "MbmapReader.dll")

    def test_frozen_python_accepts_future_minor(self):
        run = subprocess.run([sys.executable, "-m", "tools.mbmap_cli", "validate", self.future_minor()],
                             cwd=self.frozen_dir, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("VALID: 0 error(s)", run.stdout)

    def test_frozen_csharp_accepts_future_minor(self):
        code, out = self.run_cs(["dotnet", self.frozen_dll], self.future_minor())
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip().splitlines()[-1], "OK")

    def test_frozen_csharp_rejects_extra_listed_member(self):
        code, out = self.run_cs(["dotnet", self.frozen_dll], self.extra_member())
        self.assertEqual(code, 1, out)
        self.assertIn("unknown package member", out)

    def test_frozen_python_extra_listed_member_is_a_warning(self):
        run = subprocess.run([sys.executable, "-m", "tools.mbmap_cli", "validate", self.extra_member()],
                             cwd=self.frozen_dir, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("unknown package member ignored", run.stdout)


if __name__ == "__main__":
    unittest.main()
