# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Blender Extensions platform rules the manifest can be checked against without Blender (S4-EXT-READY)."""

import os
import re
import tomllib
import unittest
import zipfile

from tests.test_textures import ADDON, build_ships

# Licences the platform accepts for add-ons that are GPL-compatible; the manifest must list at least one.
GPL_COMPATIBLE = {
    "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
    "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later",
    "AGPL-3.0-only", "AGPL-3.0-or-later",
}
NATIVE_SUFFIXES = (".exe", ".dll", ".so", ".dylib", ".pyd", ".a", ".o", ".bin", ".jar", ".class")
NATIVE_MAGIC = (b"MZ", b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa")


def _load():
    with open(os.path.join(ADDON, "blender_manifest.toml"), "rb") as f:
        return tomllib.load(f)


def _shipped(build):
    for root, dirs, files in os.walk(ADDON):
        dirs[:] = sorted(dirs)
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(root, name), ADDON).replace(os.sep, "/")
            if build_ships(build, rel):
                yield rel, os.path.join(root, name)


def _is_binary(name, head):
    return name.lower().endswith(NATIVE_SUFFIXES) or head.startswith(NATIVE_MAGIC)


class ManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_tagline(self):
        t = self.m["tagline"]
        self.assertLessEqual(len(t), 64)
        self.assertNotRegex(t, r"[.,;:!?\s]$")

    def test_id_version_schema_formats(self):
        self.assertRegex(self.m["id"], r"^[a-z][a-z0-9_]*$")
        self.assertRegex(self.m["version"], r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$")
        self.assertRegex(self.m["schema_version"], r"^\d+\.\d+\.\d+$")

    def test_licence_is_spdx_with_gpl_compatible_entry(self):
        lic = self.m["license"]
        self.assertIsInstance(lic, list)
        self.assertTrue(lic)
        for entry in lic:
            self.assertRegex(entry, r"^SPDX:[A-Za-z0-9.+-]+$")
        self.assertTrue({e[len("SPDX:"):] for e in lic} & GPL_COMPATIBLE, lic)

    def test_permission_reasons(self):
        perms = self.m.get("permissions", {})
        self.assertTrue(perms)
        for name, reason in perms.items():
            with self.subTest(permission=name):
                self.assertIsInstance(reason, str)
                self.assertTrue(1 <= len(reason) <= 64, f"{len(reason)} characters")
                self.assertFalse(reason.endswith("."))

    def test_blender_version_min(self):
        self.assertEqual(self.m["blender_version_min"], "4.2.0")

    @unittest.skip("TODO(user): the maintainer supplies the website URL; then add `website` to the manifest")
    def test_website_present(self):
        self.assertRegex(self.m["website"], r"^https?://\S+$")

    def test_build_excludes_bytecode(self):
        build = self.m.get("build")
        self.assertTrue(build and build.get("paths_exclude_pattern"))
        for rel in ("core/__pycache__/x.cpython-312.pyc", "__pycache__/a.pyc", "core/a.pyc"):
            with self.subTest(rel=rel):
                self.assertFalse(build_ships(build, rel))
        self.assertTrue(build_ships(build, "core/package.py"))

    def test_shipped_files_have_no_binaries(self):
        shipped = list(_shipped(self.m.get("build")))
        self.assertIn("blender_manifest.toml", [r for r, _ in shipped])
        for rel, path in shipped:
            if rel.startswith("assets/textures/") and rel.endswith(".png"):
                continue   # the CC0 texture set is data, not a binary executable
            with open(path, "rb") as f:
                head = f.read(4)
            with self.subTest(rel=rel):
                self.assertFalse(_is_binary(rel, head))

    def test_built_zip_has_no_binaries(self):
        path = os.environ.get("MB_EXTENSION_ZIP")
        if not path:
            self.skipTest("MB_EXTENSION_ZIP not set (release.yml sets it)")
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.filename.endswith("/") or info.filename.startswith("assets/textures/"):
                    continue
                with self.subTest(entry=info.filename):
                    self.assertFalse(_is_binary(info.filename, z.read(info)[:4]))
                    self.assertNotIn("__pycache__", info.filename)
                    self.assertFalse(info.filename.endswith(".pyc"))


if __name__ == "__main__":
    unittest.main()
