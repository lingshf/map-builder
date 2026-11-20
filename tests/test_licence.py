# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Split licence (D13, option B): SPDX headers, add-on GPL scope, licence texts in sync."""
import os
import re
import subprocess
import tomllib
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GPL = "GPL-3.0-or-later"
APACHE = "Apache-2.0"
SPDX = re.compile(r"^(?:#|//|<!--) SPDX-License-Identifier: (\S+?)(?: -->)?\s*$", re.M)
BPY = re.compile(r"^\s*(?:import bpy|from bpy)", re.M)


def _tracked():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return out.splitlines()


def _expected(rel):
    gpl = rel.startswith("map_builder/blender/") or rel == "map_builder/__init__.py"
    if not gpl and rel.endswith(".py"):
        with open(os.path.join(REPO, rel), encoding="utf-8") as f:
            gpl = BPY.search(f.read()) is not None
    return GPL if gpl else APACHE


def _read(rel):
    with open(os.path.join(REPO, rel), "rb") as f:
        return f.read().replace(b"\r\n", b"\n")


class SpdxTest(unittest.TestCase):
    def test_every_first_party_source_has_the_right_spdx_header(self):
        bad = []
        for rel in _tracked():
            if rel.startswith("tools/demo/viewer/vendor/") or not rel.endswith((".py", ".cs", ".js", ".html")):
                continue
            with open(os.path.join(REPO, rel), encoding="utf-8") as f:
                head = f.read(400)
            m = SPDX.search(head)
            if not m or m.group(1) != _expected(rel) or "Copyright 2026 lingshf" not in head:
                bad.append((rel, m and m.group(1)))
        self.assertEqual(bad, [])

    def test_manifest_declares_gpl(self):
        with open(os.path.join(REPO, "map_builder", "blender_manifest.toml"), "rb") as f:
            self.assertEqual(tomllib.load(f)["license"], ["SPDX:" + GPL])


class LicenceTextTest(unittest.TestCase):
    def test_root_texts_and_addon_copies_match(self):
        self.assertIn(b"Apache License", _read("LICENSE")[:200])
        self.assertIn(b"GNU GENERAL PUBLIC LICENSE", _read("LICENSE-GPL-3.0.txt")[:200])
        self.assertEqual(_read("LICENSE"), _read("map_builder/LICENSE-Apache-2.0.txt"))
        self.assertEqual(_read("LICENSE-GPL-3.0.txt"), _read("map_builder/LICENSE-GPL-3.0.txt"))
        self.assertEqual(_read("NOTICE"), _read("map_builder/NOTICE"))


if __name__ == "__main__":
    unittest.main()
