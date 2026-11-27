# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5-DECOR step 1a: a package with a visual-only ``MB Decor`` primitive stays valid and bound (D142)."""

import json
import os
import struct
import tempfile
import unittest
import zipfile

from map_builder.core.glb import read_glb
from map_builder.core.mesh import DECOR_MATERIAL
from map_builder.core.package import validate_package

from .make_decor_fixture import build_package
from .make_textured_fixture import _load, _write, edit_glb

UNMARKED_MATERIAL = "MB Terrain Extra"
UNCHANGED_MEMBERS = ("collision/map.mbcol", "collision/terrain.mbhf")


def read_members(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def glb_json(glb):
    return json.loads(glb[20:20 + struct.unpack_from("<I", glb, 12)[0]])


class DecorPackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.tmp = tmp.name
        cls.plain = os.path.join(cls.tmp, "plain.mbmap")
        cls.decor = os.path.join(cls.tmp, "decor.mbmap")
        build_package(cls.plain)
        build_package(cls.decor, DECOR_MATERIAL)

    def test_decor_primitive_is_marked_by_material_name_and_extras(self):
        gl = glb_json(read_members(self.decor)["visual/map.glb"])
        decor_ids = [i for i, m in enumerate(gl["materials"]) if m["name"] == DECOR_MATERIAL]
        self.assertEqual(len(decor_ids), 1)
        prims = [p for mesh in gl["meshes"] for p in mesh["primitives"]]
        marked = [p["material"] for p in prims if p.get("extras", {}).get("mb_decor")]
        self.assertEqual(marked, decor_ids)
        self.assertEqual([p["material"] for p in prims if p["material"] in decor_ids], decor_ids)

    def test_decor_does_not_change_collision_or_heightfield(self):
        plain, decor = read_members(self.plain), read_members(self.decor)
        for name in UNCHANGED_MEMBERS:
            self.assertEqual(plain[name], decor[name], name)

    def test_validator_reports_nothing_new_and_reader_splits_decor_triangles(self):
        plain, decor = validate_package(self.plain, strict=True), validate_package(self.decor, strict=True)
        self.assertEqual((decor.errors, decor.warnings), (plain.errors, plain.warnings))
        nodes = read_glb(read_members(self.decor)["visual/map.glb"])[1]
        self.assertEqual([len(n.decor_triangles) for n in nodes if n.decor_triangles], [1])

    def test_only_decor_is_exempt_from_the_one_to_one_binding(self):
        def unmark(gl, _binb):
            for m in gl["materials"]:
                if m["name"] == DECOR_MATERIAL:
                    m["name"] = UNMARKED_MATERIAL
            for p in (p for mesh in gl["meshes"] for p in mesh["primitives"]):
                p.pop("extras", None)
        members, manifest = _load(self.decor)
        members["visual/map.glb"] = edit_glb(members["visual/map.glb"], unmark)
        unmarked = os.path.join(self.tmp, "unmarked.mbmap")
        _write(unmarked, members, manifest)
        errors = validate_package(unmarked, strict=True).errors
        self.assertTrue(any("1 visual triangle(s) have no collision counterpart" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
