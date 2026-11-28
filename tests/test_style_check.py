# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf

from __future__ import annotations

import json
import math
import os
import struct
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
    d = m.add_vertex(10, 10, 0)
    m.add_face((a, b, c), "MB Terrain", (0.4, 0.6, 0.4))
    m.add_face((b, d, c), "MB Terrain", (0.8, 0.4, 0.3))
    return m


_FLAT_QUAD = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 0.0, 3.0), (0.0, 0.0, 3.0)]


def _quad(name: str, corners: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]],
          colors: list[tuple[float, ...]] | None = None) -> MeshData:
    """Triangles over shared corners, each with its own flat colour (one colour by default)."""
    m = MeshData(name)
    ids = [m.add_vertex(*c) for c in corners]
    for triangle, color in zip(triangles, colors or [(0.8, 0.7, 0.6)] * len(triangles)):
        m.add_face(tuple(ids[i] for i in triangle), "MB Terrain", color)
    return m

def _map_frame_transform(vertex: tuple[float, float, float], location: tuple[float, float, float],
                         rotation_z: float) -> tuple[float, float, float]:
    x, y, z = vertex
    c, s = math.cos(rotation_z), math.sin(rotation_z)
    return (c * x - s * y + location[0], s * x + c * y + location[1], z + location[2])


def _build_valid_mbmap(path: str, nodes: list[dict] | None = None) -> None:
    nodes = nodes or [{"name": "terrain", "mesh": _mesh("terrain")}]
    glb = write_glb(nodes, {"MB Terrain": ((0.4, 0.6, 0.4), 1.0, 0.0)})
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
    report = {"passage_probes_blocked": [], "passage_probes_dropped": [], "terrain_stats": {"triangles": 1}}
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

    def test_g0_allows_style_only_report_change(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "base.mbmap")
            head = os.path.join(td, "head.mbmap")
            _build_valid_mbmap(base)

            def mut_report_style(members):
                report = json.loads(members["report.json"])
                report["options"] = {"style": "stylized"}
                members["report.json"] = json.dumps(report).encode("utf-8")

            _mutate(base, head, mut_report_style)
            ok, failures = style_check.g0_check(base, head)
            self.assertTrue(ok, failures)

    def test_g0_fails_when_report_flight_key_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "base.mbmap")
            head = os.path.join(td, "head.mbmap")
            _build_valid_mbmap(base)

            def mut_report_flight_key(members):
                report = json.loads(members["report.json"])
                report["terrain_stats"]["triangles"] = 2
                members["report.json"] = json.dumps(report).encode("utf-8")

            _mutate(base, head, mut_report_flight_key)
            ok, failures = style_check.g0_check(base, head)
            self.assertFalse(ok)
            self.assertTrue(any("non-style keys differ" in f for f in failures), failures)

    def test_g0_rejects_nested_flight_fields_in_former_exempt_paths(self) -> None:
        former_paths = [
            ("style",),
            ("material",),
            ("materials",),
            ("visual",),
            ("options", "style"),
            ("options", "material"),
            ("options", "materials"),
            ("options", "visual"),
        ]
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "base.mbmap")
            _build_valid_mbmap(base)
            for idx, path in enumerate(former_paths):
                head = os.path.join(td, f"head-{idx}.mbmap")

                def mut_nested(members, *, path=path):
                    report = json.loads(members["report.json"])
                    cursor = report
                    for key in path[:-1]:
                        node = cursor.get(key)
                        if not isinstance(node, dict):
                            node = {}
                            cursor[key] = node
                        cursor = node
                    cursor[path[-1]] = {"passage_probes_dropped": [{"id": "p0", "reason": "removed"}], "dsm": False}
                    members["report.json"] = json.dumps(report).encode("utf-8")

                _mutate(base, head, mut_nested)
                ok, failures = style_check.g0_check(base, head)
                self.assertFalse(ok, f"path {'.'.join(path)} unexpectedly passed")
                self.assertTrue(any("report.json non-style keys differ" in f for f in failures), failures)

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

    def test_parity_duplicate_identity_fails_loudly(self) -> None:
        with self.assertRaises(ValueError):
            style_check._assert_unique_identity([("terrain", "osm:1"), ("terrain", "osm:1")], "node identity")

    def test_parity_detects_color_swap_at_same_positions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cli = os.path.join(td, "cli.mbmap")
            bl = os.path.join(td, "bl.mbmap")
            _build_valid_mbmap(cli)
            _mutate(cli, bl, self._swap_first_two_colors)
            ok, details = style_check.cli_blender_parity(cli, bl)
            self.assertFalse(ok)
            self.assertGreater(len(details.get("cli_only", [])), 0)
            self.assertGreater(len(details.get("blender_only", [])), 0)

    def test_parity_detects_color_swap_at_shared_edge_corners(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cli = os.path.join(td, "cli.mbmap")
            bl = os.path.join(td, "bl.mbmap")
            _build_valid_mbmap(cli)
            # corners 1, 2 of the first triangle and 3, 5 of the second sit on the shared edge
            _mutate(cli, bl, lambda m: self._swap_corner_colors(m, [(1, 3), (2, 5)]))
            ok, details = style_check.cli_blender_parity(cli, bl)
            self.assertFalse(ok)
            self.assertGreater(len(details.get("cli_only", [])), 0)

    def test_parity_accepts_node_transform_baked_into_vertices(self) -> None:
        pivot, angle = (110.5, 52.25, 5.75), 0.7
        local = _quad("local", [(-4.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 0.0, 15.0), (-4.0, 0.0, 15.0)], [(0, 1, 2), (0, 2, 3)])
        baked = _quad("baked", [_map_frame_transform(v, pivot, angle) for v in local.vertices], [(0, 1, 2), (0, 2, 3)])
        ok, details = self._parity([{"name": "wall", "mesh": local, "location": pivot, "rotation_z": angle}],
                                   [{"name": "wall", "mesh": baked}])
        self.assertTrue(ok, details)

    def test_parity_accepts_flat_quad_split_on_other_diagonal(self) -> None:
        corners = _FLAT_QUAD
        ok, details = self._parity([{"name": "wall", "mesh": _quad("a", corners, [(0, 1, 2), (0, 2, 3)])}],
                                   [{"name": "wall", "mesh": _quad("b", corners, [(0, 1, 3), (1, 2, 3)])}])
        self.assertTrue(ok, details)

    def test_parity_rejects_other_diagonal_when_triangle_colors_differ(self) -> None:
        corners = _FLAT_QUAD
        colors = [(0.9, 0.1, 0.1), (0.1, 0.1, 0.9)]
        ok, details = self._parity([{"name": "wall", "mesh": _quad("a", corners, [(0, 1, 2), (0, 2, 3)], colors)}],
                                   [{"name": "wall", "mesh": _quad("b", corners, [(0, 1, 3), (1, 2, 3)], colors)}])
        self.assertFalse(ok)
        self.assertIn("first_cli_triangle", details["cli_only"][0]["difference"])

    def test_parity_rejects_other_diagonal_of_a_non_coplanar_quad(self) -> None:
        folded = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 0.0, 3.0), (0.0, 1.0, 3.0)]
        self._assert_diagonal_rejected(folded, [(0, 1, 2), (0, 2, 3)], [(0, 1, 3), (1, 2, 3)])

    def test_parity_rejects_other_diagonal_of_a_twisted_quad_with_equal_areas(self) -> None:
        twisted = [(1.0, 0.0, 0.0), (0.0, 1.0, 1.0), (-1.0, 0.0, 0.0), (0.0, -1.0, 1.0)]
        self._assert_diagonal_rejected(twisted, [(0, 1, 2), (0, 2, 3)], [(0, 1, 3), (1, 2, 3)])

    def test_parity_rejects_other_diagonal_when_color_differs_beyond_tolerance(self) -> None:
        ok, _ = self._parity([{"name": "wall", "mesh": _quad("a", _FLAT_QUAD, [(0, 1, 2), (0, 2, 3)])}],
                             [{"name": "wall", "mesh": _quad("b", _FLAT_QUAD, [(0, 1, 3), (1, 2, 3)], [(0.80004, 0.7, 0.6)] * 2)}])
        self.assertFalse(ok)

    def test_parity_rejects_other_diagonal_with_reversed_winding(self) -> None:
        self._assert_diagonal_rejected(_FLAT_QUAD, [(0, 1, 2), (0, 2, 3)], [(0, 3, 1), (3, 2, 1)])

    def test_parity_rejects_other_diagonal_with_an_extra_triangle(self) -> None:
        self._assert_diagonal_rejected(_FLAT_QUAD, [(0, 1, 2), (0, 2, 3)], [(0, 1, 3), (1, 2, 3), (0, 1, 2)])

    def test_parity_rejects_a_parent_node_translation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cli, bl = os.path.join(td, "cli.mbmap"), os.path.join(td, "bl.mbmap")
            _build_valid_mbmap(cli)
            _mutate(cli, bl, lambda m: self._nest_under_parent(m, [10.0, 0.0, 0.0]))
            ok, _ = style_check.cli_blender_parity(cli, bl)
            self.assertFalse(ok)

    def _assert_diagonal_rejected(self, corners: list[tuple[float, float, float]], cli_split: list[tuple[int, int, int]],
                                  bl_split: list[tuple[int, int, int]]) -> None:
        ok, _ = self._parity([{"name": "wall", "mesh": _quad("a", corners, cli_split)}],
                             [{"name": "wall", "mesh": _quad("b", corners, bl_split)}])
        self.assertFalse(ok)

    @staticmethod
    def _parity(cli_nodes: list[dict], bl_nodes: list[dict]) -> tuple[bool, dict]:
        with tempfile.TemporaryDirectory() as td:
            cli, bl = os.path.join(td, "cli.mbmap"), os.path.join(td, "bl.mbmap")
            _build_valid_mbmap(cli, cli_nodes)
            _build_valid_mbmap(bl, bl_nodes)
            return style_check.cli_blender_parity(cli, bl)

    @staticmethod
    def _swap_first_two_colors(members: dict[str, bytes]) -> None:
        StyleCheckTests._swap_corner_colors(members, [(0, 1)])

    @staticmethod
    def _swap_corner_colors(members: dict[str, bytes], corner_pairs: list[tuple[int, int]]) -> None:
        glb = members["visual/map.glb"]
        gl, bin_chunk = style_check._glb_json_and_bin(glb)
        meshes = gl.get("meshes", [])
        if not meshes:
            raise AssertionError("missing mesh")
        attrs = meshes[0]["primitives"][0]["attributes"]
        color_accessor = int(attrs["COLOR_0"])
        color_slice = style_check._buffer_slice(gl, bin_chunk, color_accessor)
        if len(color_slice) < 32:
            raise AssertionError("not enough COLOR_0 data for swap")
        vals = list(struct.unpack("<" + "f" * (len(color_slice) // 4), color_slice))
        for a, b in corner_pairs:
            vals[4 * a:4 * a + 4], vals[4 * b:4 * b + 4] = vals[4 * b:4 * b + 4], vals[4 * a:4 * a + 4]
        swapped = struct.pack("<" + "f" * len(vals), *vals)

        accessor = gl["accessors"][color_accessor]
        view = gl["bufferViews"][accessor["bufferView"]]
        offset = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
        out_bin = bytearray(bin_chunk)
        out_bin[offset:offset + len(swapped)] = swapped
        StyleCheckTests._repack_glb(members, gl, out_bin)

    @staticmethod
    def _nest_under_parent(members: dict[str, bytes], translation: list[float]) -> None:
        gl, bin_chunk = style_check._glb_json_and_bin(members["visual/map.glb"])
        gl["nodes"].append({"name": "parent", "children": [0], "translation": translation})
        gl["scenes"][0]["nodes"] = [len(gl["nodes"]) - 1]
        StyleCheckTests._repack_glb(members, gl, bytearray(bin_chunk))

    @staticmethod
    def _repack_glb(members: dict[str, bytes], gl: dict, out_bin: bytearray) -> None:
        json_bytes = json.dumps(gl, separators=(",", ":"), sort_keys=True).encode("utf-8")
        while len(json_bytes) % 4:
            json_bytes += b" "
        while len(out_bin) % 4:
            out_bin += b"\x00"
        header = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(json_bytes) + 8 + len(out_bin))
        members["visual/map.glb"] = (
            header
            + struct.pack("<I4s", len(json_bytes), b"JSON")
            + json_bytes
            + struct.pack("<I4s", len(out_bin), b"BIN\x00")
            + bytes(out_bin)
        )

if __name__ == "__main__":
    unittest.main()
