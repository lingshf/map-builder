# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf

from __future__ import annotations

import json
import os
import tempfile
import unittest
import zipfile

from map_builder.core.glb import write_glb
from map_builder.core.mesh import MeshData

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import style_check  # noqa: E402


def _mesh(name: str) -> MeshData:
    m = MeshData(name)
    a = m.add_vertex(0, 0, 0)
    b = m.add_vertex(10, 0, 0)
    c = m.add_vertex(0, 10, 0)
    m.add_face((a, b, c), "MB Terrain", (0.4, 0.6, 0.4))
    return m


def _build_valid_mbmap(path: str) -> None:
    mesh = _mesh("terrain")
    glb = write_glb([{"name": "terrain", "mesh": mesh}], {"MB Terrain": ((0.4, 0.6, 0.4), 1.0, 0.0)})
    col = b"MBCOL\x00\x00\x00\x02\x00\x00\x00" + b"\x00" * 128
    hf = b"MBHF\x00\x00\x00\x02\x00\x00\x00" + b"\x00" * 96
    probes = [{"id": "p0", "kind": "bridge", "feature": "osm:way/1", "path_map": [[0.0, 0.0, 5.0], [1.0, 0.0, 5.0]],
               "radius_m": 0.5}]
    manifest = {
        "schema": "map-builder.package",
        "schema_version": "2.1.0",
        "name": "style-check-test",
        "generator": {"name": "map-builder", "version": "0.5.0", "blender": None},
        "visual": {"path": "visual/map.glb"},
        "collision": {"path": "collision/map.mbcol"},
        "heightfield": {"path": "collision/terrain.mbhf"},
        "georeference": {
            "origin": {"lat_deg": 47.0, "lon_deg": 8.0},
            "horizontal_datum": "WGS84 (EPSG:4326)",
            "projection": "UTM",
            "vertical_datum": "SYNTHETIC",
            "z_offset_m": 0.0,
            "height_formula": "H = z + z_offset_m",
            "units": "metre",
        },
        "passage_probes": probes,
    }
    report = {"passage_probes_blocked": [], "passage_probes_dropped": []}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, sort_keys=True).encode("utf-8"))
        z.writestr("report.json", json.dumps(report, sort_keys=True).encode("utf-8"))
        z.writestr("visual/map.glb", glb)
        z.writestr("collision/map.mbcol", col)
        z.writestr("collision/terrain.mbhf", hf)


def _mutate(path_in: str, path_out: str, mutator) -> None:
    with zipfile.ZipFile(path_in, "r") as zin:
        members = {n: zin.read(n) for n in zin.namelist()}
    mutator(members)
    with zipfile.ZipFile(path_out, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in members.items():
            zout.writestr(name, data)


class StyleCheckTests(unittest.TestCase):
    def test_g0_and_negative_cases(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "base.mbmap")
            _build_valid_mbmap(base)
            ok, failures = style_check.g0_check(base, base)
            self.assertTrue(ok, failures)

            # mbcol byte flipped
            bad1 = os.path.join(td, "bad1.mbmap")
            _mutate(base, bad1, lambda m: m.__setitem__("collision/map.mbcol",
                                                        m["collision/map.mbcol"][:-1] + bytes([m["collision/map.mbcol"][-1] ^ 1])))
            self.assertFalse(style_check.g0_check(base, bad1)[0])

            # mbhf byte flipped
            bad2 = os.path.join(td, "bad2.mbmap")
            _mutate(base, bad2, lambda m: m.__setitem__("collision/terrain.mbhf",
                                                        m["collision/terrain.mbhf"][:-1] + bytes([m["collision/terrain.mbhf"][-1] ^ 1])))
            self.assertFalse(style_check.g0_check(base, bad2)[0])

            # probe moved 1mm
            bad3 = os.path.join(td, "bad3.mbmap")
            def mut_probe(members):
                manifest = json.loads(members["manifest.json"])
                manifest["passage_probes"][0]["path_map"][0][0] += 0.001
                members["manifest.json"] = json.dumps(manifest).encode("utf-8")
            _mutate(base, bad3, mut_probe)
            self.assertFalse(style_check.g0_check(base, bad3)[0])

            # georeference field changed
            bad4 = os.path.join(td, "bad4.mbmap")
            def mut_geo(members):
                manifest = json.loads(members["manifest.json"])
                manifest["georeference"]["units"] = "meter"
                members["manifest.json"] = json.dumps(manifest).encode("utf-8")
            _mutate(base, bad4, mut_geo)
            self.assertFalse(style_check.g0_check(base, bad4)[0])

            # blocked changed only
            bad5 = os.path.join(td, "bad5.mbmap")
            def mut_blocked(members):
                report = json.loads(members["report.json"])
                report["passage_probes_blocked"] = [{"id": "p0", "blocker": "osm:way/9"}]
                members["report.json"] = json.dumps(report).encode("utf-8")
            _mutate(base, bad5, mut_blocked)
            self.assertFalse(style_check.g0_check(base, bad5)[0])

            # dropped changed only
            bad6 = os.path.join(td, "bad6.mbmap")
            def mut_dropped(members):
                report = json.loads(members["report.json"])
                report["passage_probes_dropped"] = [{"id": "p0", "reason": "not_exported"}]
                members["report.json"] = json.dumps(report).encode("utf-8")
            _mutate(base, bad6, mut_dropped)
            self.assertFalse(style_check.g0_check(base, bad6)[0])

    def test_g0_fails_on_missing_required_data_even_if_missing_on_both(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "base.mbmap")
            _build_valid_mbmap(base)
            bad = os.path.join(td, "bad.mbmap")
            def mut_missing(members):
                members.pop("collision/map.mbcol", None)
                members.pop("collision/terrain.mbhf", None)
                members.pop("report.json", None)
                manifest = json.loads(members["manifest.json"])
                manifest.pop("georeference", None)
                manifest.pop("passage_probes", None)
                members["manifest.json"] = json.dumps(manifest).encode("utf-8")
            _mutate(base, bad, mut_missing)
            ok, failures = style_check.g0_check(bad, bad)
            self.assertFalse(ok)
            self.assertTrue(any("missing" in f for f in failures), failures)

    def test_g0_rejects_same_path_different_preset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "base.mbmap")
            head = os.path.join(td, "head.mbmap")
            _build_valid_mbmap(base)
            _mutate(base, head, lambda m: m.__setitem__(
                "manifest.json",
                json.dumps({**json.loads(m["manifest.json"]), "name": "other-preset"}).encode("utf-8"),
            ))
            ok, failures = style_check.g0_check(base, head)
            self.assertFalse(ok)
            self.assertTrue(any("preset mismatch" in f for f in failures), failures)

    def test_g0_allows_missing_optional_blocked_and_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "base.mbmap")
            head = os.path.join(td, "head.mbmap")
            _build_valid_mbmap(base)
            _mutate(base, head, lambda m: m.__setitem__(
                "report.json",
                json.dumps({}).encode("utf-8"),
            ))
            ok, failures = style_check.g0_check(head, head)
            self.assertTrue(ok, failures)

    def test_g0_rejects_cross_path_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cli = os.path.join(td, "cli.mbmap")
            bl = os.path.join(td, "blender.mbmap")
            _build_valid_mbmap(cli)
            _mutate(cli, bl, lambda m: m.__setitem__(
                "manifest.json",
                json.dumps({**json.loads(m["manifest.json"]), "generator": {
                    "name": "map-builder", "version": "0.5.0", "blender": "4.2.23 LTS"}}).encode("utf-8"),
            ))
            ok, failures = style_check.g0_check(cli, bl)
            self.assertFalse(ok)
            self.assertTrue(any("cross-path comparison rejected" in f for f in failures), failures)

    def test_classic_identity_negative_single_glb_byte(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "base.mbmap")
            _build_valid_mbmap(base)
            head = os.path.join(td, "head.mbmap")
            _mutate(base, head, lambda m: m.__setitem__("visual/map.glb",
                                                        m["visual/map.glb"][:-1] + bytes([m["visual/map.glb"][-1] ^ 1])))
            ok, failures = style_check.classic_identity_check(base, head)
            self.assertFalse(ok)
            self.assertIn("whole archive differs", failures)

    def test_metrics_and_mode_diff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "base.mbmap")
            _build_valid_mbmap(base)
            m = style_check.glb_metrics(base)
            self.assertGreaterEqual(m["materials"], 1)
            self.assertGreaterEqual(m["draw_submissions"], 1)
            self.assertGreaterEqual(m["triangles"], 1)
            self.assertGreater(m["glb_bytes"], 0)

            stylized = os.path.join(td, "stylized.mbmap")
            _mutate(base, stylized, lambda mb: mb.__setitem__("report.json",
                                                              json.dumps({**json.loads(mb["report.json"]),
                                                                          "style": "stylized"}).encode("utf-8")))
            diff = style_check.mode_member_diff(base, stylized)
            self.assertIn("report.json", diff["changed"])

    def test_palette_regions_report(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        with tempfile.TemporaryDirectory() as td:
            image_path = os.path.join(td, "img.png")
            regions_path = os.path.join(td, "regions.json")
            img = Image.new("RGB", (2, 2), (185, 209, 122))
            img.save(image_path)
            with open(regions_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(
                    {
                        "regions": [
                            {
                                "camera": "overview",
                                "label": "grass-light",
                                "target_hex": "#b9d17a",
                                "x": 0.0,
                                "y": 0.0,
                                "w": 1.0,
                                "h": 1.0,
                            }
                        ]
                    },
                    f,
                )
            out = style_check.palette_regions(image_path, regions_path)
            self.assertEqual(len(out["regions"]), 1)
            self.assertEqual(out["regions"][0]["label"], "grass-light")
            self.assertAlmostEqual(out["regions"][0]["deltaE2000"], 0.0, places=2)
            self.assertFalse(out["regions"][0]["flag_over_15"])


if __name__ == "__main__":
    unittest.main()
