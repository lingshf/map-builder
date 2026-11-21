# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Blender Extensions platform rules the manifest can be checked against without Blender (S4-EXT-READY)."""

import os
import re
import tomllib
import unicodedata
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


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _tagline_ok(t):
    """Blender 4.2 strict: non-empty, at most 64 characters, no leading whitespace, no control characters
    (newlines included), ending in an alphanumeric character or ) ] }."""
    return (0 < len(t) <= 64 and t == t.lstrip() and not any(unicodedata.category(c) == "Cc" for c in t)
            and (t[-1].isalnum() or t[-1] in ")]}"))


def _forbidden(name, data):
    """Why an entry may not ship, or None. A .png must carry the PNG signature in its own bytes; native
    binaries and bytecode are rejected by name or content in every directory."""
    low = name.lower()
    if "__pycache__" in low.split("/") or low.endswith((".pyc", ".pyo")):
        return "bytecode"
    if low.endswith(NATIVE_SUFFIXES) or data.startswith(NATIVE_MAGIC):
        return "native binary"
    if low.endswith(".png") and not data.startswith(PNG_SIGNATURE):
        return "not a PNG"
    return None


class ManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_tagline(self):
        t = self.m["tagline"]
        self.assertTrue(_tagline_ok(t), t)

    def test_tagline_rule_matches_blender(self):
        for ok in ("Build maps", "Build maps (OSM)", "Maps [v2]", "x" * 64):
            self.assertTrue(_tagline_ok(ok), ok)
        for bad in ("", "Build maps.", "Build maps\u2014", "Build maps -", "Build maps ", "Maps!", "x" * 65,
                    " Build maps", "\tBuild maps", "Build\nmaps", "Build\x00maps", "Build\x1fmaps", "Build\x7fmaps"):
            self.assertFalse(_tagline_ok(bad), bad)

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
        self.assertTrue(any(r.startswith("assets/textures/") for r, _ in shipped))
        for rel, path in shipped:
            with open(path, "rb") as f:
                data = f.read(8)
            with self.subTest(rel=rel):
                self.assertIsNone(_forbidden(rel, data))

    def test_binary_rule_covers_textures(self):
        png = PNG_SIGNATURE + b"rest"
        self.assertIsNone(_forbidden("assets/textures/a.png", png))
        for name, data in (
            ("assets/textures/example.dll", png),
            ("assets/textures/a.so", b"x"),
            ("assets/textures/a.png", b"\x7fELFrest"),
            ("assets/textures/a.png", b"MZ\x90\x00"),
            ("assets/textures/fake.png", b"not a png"),
            ("assets/textures/a.pyc", png),
            ("assets/textures/__pycache__/a.dat", b"x"),
            ("core/tool", b"\x7fELF"),
        ):
            with self.subTest(name=name):
                self.assertIsNotNone(_forbidden(name, data))

    def test_built_zip_has_no_binaries(self):
        path = os.environ.get("MB_EXTENSION_ZIP")
        if not path:
            self.skipTest("MB_EXTENSION_ZIP not set (release.yml sets it)")
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.filename.endswith("/"):
                    continue
                with self.subTest(entry=info.filename):
                    self.assertIsNone(_forbidden(info.filename, z.read(info)[:8]))


if __name__ == "__main__":
    unittest.main()
