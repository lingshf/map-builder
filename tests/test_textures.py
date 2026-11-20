"""The procedural CC0 texture set (S3-TEX-ASSETS): reproducible, valid, small, shipped and licensed."""

import contextlib
import fnmatch
import hashlib
import io
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
import tomllib
import unittest
import zipfile
from unittest import mock

from map_builder.core import textures
from map_builder.core.errors import PackageError
from map_builder.core.glb import MAX_TEXTURE_SIDE, glb_image_sha256s, read_glb, write_glb
from map_builder.core.mesh import MeshData
from tools.textures import make_textures

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(REPO, "map_builder")
TEX_DIR = os.path.join(ADDON, "assets", "textures")
ASSET_FILES = sorted({f for f, _, _ in textures.TEXTURES.values()} | {textures.LICENSE_FILE})
MAX_SET_BYTES = 2 * 1024 * 1024   # D60


def _committed(name):
    with open(os.path.join(TEX_DIR, name), "rb") as f:
        return f.read()


class GeneratorTest(unittest.TestCase):
    def test_regenerated_bytes_equal_committed_files(self):
        """AC1: a fresh run reproduces every committed file byte for byte (same SHA-256)."""
        files = make_textures.generate()
        self.assertEqual(sorted(files), sorted(f for f in os.listdir(TEX_DIR) if not f.startswith(".")))
        self.assertEqual(sorted(files), ASSET_FILES)
        for name, data in files.items():
            self.assertEqual(hashlib.sha256(make_textures._canon(name, data)).hexdigest(),
                             hashlib.sha256(make_textures._canon(name, _committed(name))).hexdigest(), name)

    def test_repeat_run_identical_and_license_lists_hashes(self):
        """AC1: two runs in one process agree, and the licence lists each committed PNG's SHA-256."""
        self.assertEqual(make_textures.generate_one(2), make_textures.generate_one(2))
        lic = _committed(textures.LICENSE_FILE).decode("utf-8")
        for name, _ in make_textures.TEXTURES:
            self.assertIn(f"{hashlib.sha256(_committed(name)).hexdigest()}  {name}", lic)

    def test_check_mode(self):
        committed = {n: _committed(n) for n in ASSET_FILES}
        with mock.patch.object(make_textures, "generate", lambda: committed), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(make_textures.main(["--check"]), 0)
            with tempfile.TemporaryDirectory() as d:
                self.assertEqual(make_textures.main(["--check", "--out", d]), 1)
        self.assertIn("differs: concrete.png", out.getvalue())


class TextureSetTest(unittest.TestCase):
    def test_every_png_passes_the_package_png_check(self):
        """AC2: power-of-two sides <= 512 px, and the S3-TEX-FORMAT GLB image check (read_glb) accepts each."""
        for mat, (fname, tile, rough) in textures.TEXTURES.items():
            with self.subTest(mat):
                png = textures.load(mat)
                self.assertEqual(png, _committed(fname))
                w, h = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
                for side in (w, h):
                    self.assertTrue(side in (256, 512), (w, h))
                    self.assertLessEqual(side, MAX_TEXTURE_SIDE)
                self.assertEqual(png[24:26], b"\x08\x02")   # 8-bit RGB
                self.assertGreater(tile, 0)
                self.assertTrue(0.0 <= rough <= 1.0)
                m = MeshData("q")
                for p in ((0, 0, 0), (1, 0, 0), (1, 1, 0)):
                    m.add_vertex(*p)
                m.add_face((0, 1, 2), mat, (1, 1, 1), uvs=[(0, 0), (1, 0), (1, 1)])
                node = {"name": "q", "mesh": m, "location": (0, 0, 0), "rotation_z": 0.0, "scale": 1.0,
                        "extras": {}}
                glb = write_glb([node], {mat: ((1, 1, 1), rough, 0.0, png)})
                read_glb(glb)
                self.assertEqual(glb_image_sha256s(glb), [textures.sha256(mat)])

    def test_total_bytes_within_budget(self):
        """AC3 (D60): the whole texture set, counted over the shipped directory, is <= 2 MiB."""
        total = sum(os.path.getsize(os.path.join(TEX_DIR, f)) for f in os.listdir(TEX_DIR) if f.endswith(".png"))
        self.assertGreater(total, 0)
        self.assertLessEqual(total, MAX_SET_BYTES)

    def test_unknown_material_and_notice(self):
        with self.assertRaises(PackageError):
            textures.load("MB Probe")
        n = textures.asset_notice(["MB Concrete", "MB Tunnel", "MB Road"])
        self.assertEqual(n["sha256"], sorted({textures.sha256("MB Concrete"), textures.sha256("MB Road")}))
        self.assertEqual(n["license"]["id"], "CC0-1.0")
        from map_builder.core.package import asset_notice_problems
        self.assertEqual(asset_notice_problems([n]), [])


# Blender's defaults when blender_manifest.toml has no [build] table (bl_pkg cli/blender_ext.py, 4.2).
BLENDER_DEFAULT_EXCLUDES = ["__pycache__/", ".*", "/*.zip"]


def _glob_regex(pattern):
    """Regex for one gitignore-style pattern, applied to a path whose components are joined by newlines.
    Same rules as Blender's extension build (``PathPatternMatch``): components use ``fnmatch`` and never
    cross a separator; ``**`` spans any number of components; a leading ``/`` anchors the pattern at the
    add-on root, otherwise it may start at any component (even if it contains a ``/``); a trailing ``/``
    matches directories only."""
    if pattern.startswith("\\!"):
        pattern = pattern[1:]
    pattern = re.sub("/+", "/", pattern)
    pattern = re.sub("(/\\*\\*)+/?$", "/", pattern)
    pattern = re.sub("^/?(\\*\\*/)+", "", pattern)
    pattern = re.sub("(/\\*\\*)+/", "/**/", pattern)
    anchored, dir_only = pattern.startswith("/"), pattern.endswith("/")
    parts = pattern.strip("/").split("/")
    out = ""
    for i, part in enumerate(parts):
        if part == "**":
            continue
        rx = fnmatch.translate(part).removesuffix("\\Z")
        rx = "(?:" + rx[4:] if rx.startswith("(?s:") else rx
        if i:
            out += "(?:\n|\n(?s:.*)\n)?" if parts[i - 1] == "**" else "\n"
        out += rx
    return ("\\A" if anchored else "(?s:.*)^") + out + ("[\n/]" if dir_only else "/?\\Z")


def _excluded(path, patterns):
    """Whether Blender's exclude test rejects ``path`` (posix, relative; directories end with ``/``).
    Consecutive patterns of the same sign form groups; scanning the groups in order, a matching
    ``!`` group re-includes the path and stops, a matching positive group excludes it."""
    groups = []
    for p in patterns:
        neg = p.startswith("!")
        p = p.lstrip("!") if neg else p
        if not p:
            continue
        if not groups or groups[-1][0] != neg:
            groups.append((neg, []))
        groups[-1][1].append(_glob_regex(p))
    probe = path.rstrip("/").replace("/", "\n") + ("/" if path.endswith("/") else "")
    result = False
    for neg, rxs in groups:
        if re.match("(?:" + "|".join(rxs) + ")", probe, re.M):
            if neg:
                return False
            result = True
    return result


def build_ships(build, rel):
    """Whether ``blender --command extension build`` with manifest ``[build]`` table ``build`` (None = no
    table) ships the file ``rel``. Either a ``paths`` entry names exactly that file, or no exclude pattern
    matches the file or any of its parent directories (the build prunes excluded directories).

    Blender writes each ``paths`` entry as-is with ``ZipFile.write(abs, entry)``. A directory entry adds
    only the directory, not its contents. The arcname is normalised by ``os.path.normpath`` and has its
    leading slashes stripped. The build fails outright, so nothing ships, in two cases: a duplicate entry
    after normalisation, or a file entry with a trailing slash."""
    if build is not None and "paths" in build:
        entries = [p.replace("\\", "/") for p in build["paths"]]
        norm = [posixpath.normpath(p).lstrip("/") for p in entries]
        if len(set(norm)) != len(norm) or any(p.endswith("/") and n == rel for p, n in zip(entries, norm)):
            return False
        return rel in norm
    patterns = BLENDER_DEFAULT_EXCLUDES if build is None else build.get("paths_exclude_pattern")
    if not patterns:   # Blender then skips dot-files only
        return not any(p.startswith(".") for p in rel.split("/"))
    parts = rel.split("/")
    dirs = ["/".join(parts[:i]) + "/" for i in range(1, len(parts))]
    return not any(_excluded(p, patterns) for p in dirs + [rel])


def _missing_textures(build):
    return [n for n in ASSET_FILES if not build_ships(build, f"assets/textures/{n}")]


def _extension_zip():
    """A built extension zip: $MB_EXTENSION_ZIP, else ``blender --command extension build`` if Blender is
    on PATH (as in release.yml), else None."""
    env = os.environ.get("MB_EXTENSION_ZIP")
    if env:
        if not os.path.isfile(env):
            raise AssertionError(f"MB_EXTENSION_ZIP={env!r} is not a file")
        return env, None
    blender = shutil.which("blender")
    if not blender:
        return None, None
    d = tempfile.TemporaryDirectory()
    subprocess.run([blender, "--command", "extension", "build", "--source-dir", ADDON, "--output-dir", d.name],
                   check=True, capture_output=True)
    zips = [f for f in os.listdir(d.name) if f.endswith(".zip")]
    if len(zips) != 1:
        d.cleanup()
        raise AssertionError(f"expected exactly one built zip, got {zips}")
    return os.path.join(d.name, zips[0]), d


class ExtensionZipTest(unittest.TestCase):
    def test_manifest_build_rules_keep_the_textures(self):
        """AC4 (always runs): the manifest's [build] rules ship every texture asset."""
        with open(os.path.join(ADDON, "blender_manifest.toml"), "rb") as f:
            build = tomllib.load(f).get("build")
        self.assertFalse(build and "paths" in build and "paths_exclude_pattern" in build)
        self.assertEqual(_missing_textures(build), [])

    def test_build_rule_mutations_are_caught(self):
        """The rule check is not vacuous: each of these [build] tables drops a texture, or keeps them all."""
        drops = {
            "exact file": ["__pycache__/", "assets/textures/asphalt.png"],
            "anchored exact file": ["/assets/textures/asphalt.png"],
            "glob": ["assets/textures/*.png"],
            "basename glob": ["*.png"],
            "single-char glob": ["asphal?.png"],
            "double star": ["assets/**/*.png"],
            "directory": ["assets/"],
            "anchored directory": ["/assets/textures/"],
            "nested directory name": ["textures/"],
            "licence": ["LICENSE-*"],
        }
        for label, pats in drops.items():
            with self.subTest(label):
                self.assertNotEqual(_missing_textures({"paths_exclude_pattern": pats}), [], pats)
        keeps = {
            "repo manifest": ["__pycache__/", "*.pyc"],
            "negated": ["*.png", "!assets/textures/*.png"],
            "anchored elsewhere": ["/textures/"],
            "file pattern is not a directory pattern": ["asphalt.png/"],
            "other extension": ["*.jpg", "assets/textures/*.jpeg"],
            "escaped bang": ["\\!asphalt.png"],
        }
        for label, pats in keeps.items():
            with self.subTest(label):
                self.assertEqual(_missing_textures({"paths_exclude_pattern": pats}), [], pats)
        # A directory in `paths` ships only the directory entry, not its files (checked against a real build).
        for dirs in (["__init__.py", "assets/textures/"], ["assets/"], ["./assets/textures"], ["core/", "assets"]):
            with self.subTest(paths=dirs):
                self.assertEqual(_missing_textures({"paths": dirs}), ASSET_FILES)
        every_file = ["__init__.py"] + [f"assets/textures/{n}" for n in ASSET_FILES]
        self.assertEqual(_missing_textures({"paths": every_file}), [])
        self.assertEqual(_missing_textures({"paths": [f"./assets/textures/{n}" for n in ASSET_FILES]}), [])
        self.assertEqual(_missing_textures({"paths": every_file[:-1]}), ASSET_FILES[-1:])
        # Both of these make Blender's build fail, so the guard rejects them.
        slash = every_file[:-1] + [every_file[-1] + "/"]
        self.assertIn(ASSET_FILES[-1], _missing_textures({"paths": slash}))
        self.assertNotEqual(_missing_textures({"paths": every_file + ["./" + every_file[1]]}), [])
        self.assertEqual(_missing_textures(None), [])
        self.assertEqual(_missing_textures({"paths_exclude_pattern": [".*", "assets/"]}), ASSET_FILES)

    def test_built_zip_contains_the_textures(self):
        """AC4: the zip built as in release.yml lists every texture file (skipped without Blender/zip)."""
        path, tmp = _extension_zip()
        if path is None:
            self.skipTest("no MB_EXTENSION_ZIP and no blender on PATH")
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                root = [n[:-len("blender_manifest.toml")] for n in names if n.endswith("blender_manifest.toml")]
                self.assertEqual(len(root), 1, names[:20])
                for name in ASSET_FILES:
                    entry = f"{root[0]}assets/textures/{name}"
                    self.assertIn(entry, names)
                    if name.endswith(".png"):
                        self.assertEqual(z.read(entry), _committed(name), name)
        finally:
            if tmp:
                tmp.cleanup()


class LicenceTest(unittest.TestCase):
    def test_license_and_readme_name_cc0_own_work(self):
        """AC5"""
        lic = textures.license_text()
        self.assertIn("CC0 1.0 Universal", lic)
        self.assertIn("own work", lic)
        self.assertIn(make_textures.COMMAND, lic)
        self.assertIn("Statement of Purpose", lic)   # the CC0 legal code itself
        with open(os.path.join(REPO, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        section = re.search(r"^## Data licences\n(.*?)^## ", readme, re.S | re.M).group(1)
        self.assertIn("CC0", section)
        self.assertIn("own work", section)
        self.assertIn("map_builder/assets/textures", section)


if __name__ == "__main__":
    unittest.main()
