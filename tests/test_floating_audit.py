# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""tools/floating_audit.py: ray raster, finding classification and the committed sample (needs numpy)."""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from map_builder.core.glb import write_glb
from map_builder.core.mesh import MeshData

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import floating_audit as fa  # noqa: E402

SAMPLE = os.path.join(ROOT, "examples", "synthetic_sample.mbmap")
GRID = np.arange(0.5, 10.0)            # cell centres of a 10 m x 10 m square, 1 m cells
HOVER_M = 0.5


def square(z: float, lo: float = 0.0, hi: float = 10.0) -> np.ndarray:
    """Two triangles of a horizontal square at height ``z`` over [lo, hi]^2."""
    a, b, c, d = (lo, lo, z), (hi, lo, z), (hi, hi, z), (lo, hi, z)
    return np.array([[a, b, c], [a, c, d]], dtype=float)


def raster_of(*layers: tuple[np.ndarray, int]) -> fa.Raster:
    raster = fa.Raster(GRID, GRID)
    for tris, owner in layers:
        raster.add(tris, np.full(len(tris), owner, dtype=np.int32))
    return raster


def surfaces(road_z: float) -> fa.Surfaces:
    """Collision and visual alike: a terrain square at z=0 with a road square over it at ``road_z``."""
    road = square(road_z)
    terrain = raster_of((square(0.0), 0))
    everything = raster_of((square(0.0), 0), (road, 1))
    names = ["terrain", "road"]
    by_kind = {"terrain": terrain, "road": raster_of((road, 1))}
    ctris = np.concatenate((square(0.0), road))
    cowners = np.array([0, 0, 1, 1], dtype=np.int32)
    return fa.Surfaces(GRID, GRID, everything, by_kind, everything, by_kind, names, names,
                       ["terrain", "road"], ctris, cowners, ctris, cowners,
                       np.array(["terrain", "road", "terrain", "road"], dtype=object), object(), 1000.0, 2000.0)


def road_findings(road_z: float) -> dict[str, list[dict]]:
    findings = fa.Findings(1.0, GRID, GRID, 0.0)
    fa._check_roads(surfaces(road_z), findings, 0.2)
    return findings.regions


class RasterTest(unittest.TestCase):
    @staticmethod
    def _split_glb(glb: bytes) -> tuple[dict, bytes]:
        magic, ver, total = struct.unpack_from("<III", glb, 0)
        assert magic == 0x46546C67 and ver == 2 and total == len(glb)
        offset, js, binb = 12, None, b""
        while offset < len(glb):
            clen, ctype = struct.unpack_from("<II", glb, offset)
            offset += 8
            chunk = glb[offset:offset + clen]
            offset += clen
            if ctype == 0x4E4F534A:
                js = json.loads(chunk.rstrip(b" "))
            elif ctype == 0x004E4942:
                binb = bytes(chunk)
        assert js is not None
        return js, binb

    @staticmethod
    def _build_glb(js: dict, binb: bytes) -> bytes:
        j = json.dumps(js, separators=(",", ":"), allow_nan=False).encode("utf-8")
        j += b" " * (-len(j) % 4)
        b = binb + b"\x00" * (-len(binb) % 4)
        total = 12 + 8 + len(j) + 8 + len(b)
        return struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(j), 0x4E4F534A) + j \
            + struct.pack("<II", len(b), 0x004E4942) + b

    @staticmethod
    def _f32_ref(glb: bytes) -> np.ndarray:
        js, binb = RasterTest._split_glb(glb)
        views = js["bufferViews"]
        acc = js["accessors"][js["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
        view = views[acc["bufferView"]]
        base = int(view.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
        count = int(acc["count"])
        pos = np.frombuffer(binb, dtype=np.float32, count=count * 3, offset=base).reshape(count, 3)
        idx_acc = js["accessors"][js["meshes"][0]["primitives"][0]["indices"]]
        idx_view = views[idx_acc["bufferView"]]
        ibase = int(idx_view.get("byteOffset", 0)) + int(idx_acc.get("byteOffset", 0))
        ids = np.frombuffer(binb, dtype=np.uint32, count=int(idx_acc["count"]), offset=ibase).reshape(-1, 3)
        local = pos[ids]
        nodes = js["nodes"]
        root, mid, leaf = nodes[0], nodes[1], nodes[2]

        def trs(n: dict) -> np.ndarray:
            t = np.asarray(n["translation"], dtype=np.float32)
            x, y, z, w = np.asarray(n["rotation"], dtype=np.float32)
            s = np.asarray(n["scale"], dtype=np.float32)
            r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                          [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                          [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]], dtype=np.float32)
            m = np.eye(4, dtype=np.float32)
            m[:3, :3] = r * s[np.newaxis, :]
            m[:3, 3] = t
            return m

        world = (trs(root) @ trs(mid)).astype(np.float32)
        world = (world @ trs(leaf)).astype(np.float32)
        linear = world[:3, :3]
        trans = world[:3, 3]
        out = (local.reshape(-1, 3) @ linear.T + trans).astype(np.float32).reshape(-1, 3, 3)
        if float(np.linalg.det(linear.astype(np.float64))) < 0.0:
            out = out[:, [0, 2, 1], :]
        return np.stack([out[..., 0], -out[..., 2], out[..., 1]], axis=-1).astype(np.float32)
    def test_the_highest_surface_wins_and_names_its_owner(self):
        raster = raster_of((square(0.0), 0), (square(2.0, 2.0, 6.0), 1))
        self.assertEqual(raster.final()[0, 0], 0.0)
        self.assertEqual(raster.final()[3, 3], 2.0)
        self.assertEqual(raster.owner[3, 3], 1)

    def test_cells_outside_every_triangle_are_empty(self):
        raster = raster_of((square(1.0, 0.0, 4.0), 0))
        self.assertTrue(np.isnan(raster.final()[8, 8]))

    def test_a_sloped_triangle_is_sampled_at_the_cell_centre(self):
        ramp = np.array([[(0, 0, 0), (10, 0, 10), (0, 10, 0)]], dtype=float)
        self.assertAlmostEqual(raster_of((ramp, 0)).final()[0, 4], 4.5)

    def test_map_tris_keeps_world_coordinates(self):
        tris = np.array([[[-551.21552877, 139.92381506, -21.10734338],
                          [-552.41236655, 139.92381506, -14.34491009],
                          [-547.81370707, 139.92381506, -13.53395873]]], dtype=np.float64)
        mapped = fa._map_tris(tris)
        self.assertEqual(mapped[0, 0, 0], tris[0, 0, 0])
        self.assertEqual(mapped[0, 1, 0], tris[0, 1, 0])
        self.assertEqual(mapped[0, 2, 1], -tris[0, 2, 2])

    def test_float32_nested_trs_visual_transform_matches_reference_bit_for_bit(self):
        mesh = MeshData("m")
        a = mesh.add_vertex(-1.25, 2.5, 0.75)
        b = mesh.add_vertex(3.0, -0.5, 1.5)
        c = mesh.add_vertex(0.25, 4.0, -2.25)
        mesh.add_face((a, b, c), "m", (1.0, 1.0, 1.0))
        glb = write_glb([{"name": "leaf", "mesh": mesh, "extras": {"mb_id": "osm:way/nested", "mb_class": "building"}}], {})
        js, binb = self._split_glb(glb)
        js["nodes"] = [
            {"name": "root", "translation": [100000.123456, -50000.765432, 1234.5],
             "rotation": [0.0, 0.0, math.sin(0.123 / 2.0), math.cos(0.123 / 2.0)],
             "scale": [1.25, 0.75, 1.1], "children": [1], "extras": {"mb_id": "root", "mb_class": "structure"}},
            {"name": "mid", "translation": [-321.125, 654.875, -98.5],
             "rotation": [0.0, 0.0, math.sin(-0.456 / 2.0), math.cos(-0.456 / 2.0)],
             "scale": [0.5, 1.75, 0.9], "children": [2], "extras": {"mb_id": "mid", "mb_class": "structure"}},
            {"name": "leaf", "mesh": 0, "translation": [12.25, -7.5, 3.125],
             "rotation": [0.0, 0.0, math.sin(1.234 / 2.0), math.cos(1.234 / 2.0)],
             "scale": [1.1, 0.8, 1.3], "extras": {"mb_id": "osm:way/nested", "mb_class": "building"}}
        ]
        js["scenes"][0]["nodes"] = [0]
        nested = self._build_glb(js, binb)
        got, _owners, _cats, _names = fa._visual_triangles_float32(nested)
        want = self._f32_ref(nested)
        self.assertTrue(np.array_equal(got.astype(np.float32).view(np.uint32), want.view(np.uint32)))


class CollisionVisualBoundaryTest(unittest.TestCase):
    @staticmethod
    def _col_raw(tris: np.ndarray, owners: np.ndarray):
        class Col:
            pass
        c = Col()
        verts, indices = [], []
        for t in tris:
            o = len(verts)
            verts.extend([tuple(map(float, t[0])), tuple(map(float, t[1])), tuple(map(float, t[2]))])
            indices.extend([o, o + 1, o + 2])
        c.vertices = verts
        c.indices = indices
        c.bounds = (np.min(tris.reshape(-1, 3), axis=0), np.max(tris.reshape(-1, 3), axis=0))
        c.objects = []
        for owner in sorted(set(owners.tolist())):
            tri_ids = np.where(owners == owner)[0]
            flat = tris[tri_ids].reshape(-1, 3)
            lo = np.min(flat, axis=0)
            hi = np.max(flat, axis=0)
            c.objects.append({"aabb": [float(lo[0]), float(lo[1]), float(lo[2]), float(hi[0]), float(hi[1]), float(hi[2])],
                              "tri_start": int(tri_ids.min()), "tri_count": int(len(tri_ids))})
        return c

    def _surfaces(self, xs: np.ndarray, ys: np.ndarray, col_layers: list[tuple[np.ndarray, int]],
                  vis_layers: list[tuple[np.ndarray, int]], names: list[str], classes: list[str]) -> fa.Surfaces:
        col = fa.Raster(xs, ys)
        vis = fa.Raster(xs, ys)
        ctris, cowners = [], []
        vtris, vowners, vcats = [], [], []
        for tris, owner in col_layers:
            col.add(tris, np.full(len(tris), owner, dtype=np.int32))
            ctris.append(tris)
            cowners.append(np.full(len(tris), owner, dtype=np.int32))
        for tris, owner in vis_layers:
            vis.add(tris, np.full(len(tris), owner, dtype=np.int32))
            vtris.append(tris)
            vowners.append(np.full(len(tris), owner, dtype=np.int32))
            vcats.append(np.full(len(tris), classes[owner], dtype=object))
        col_by_class = {"terrain": fa.Raster(xs, ys)}
        col_by_class["terrain"].add(col_layers[0][0], np.zeros(len(col_layers[0][0]), dtype=np.int32))
        vis_by_category = {"terrain": fa.Raster(xs, ys)}
        vis_by_category["terrain"].add(vis_layers[0][0], np.zeros(len(vis_layers[0][0]), dtype=np.int32))
        col_tris = np.concatenate(ctris)
        col_owners = np.concatenate(cowners)
        order = np.argsort(col_owners, kind="stable")
        col_tris = col_tris[order]
        col_owners = col_owners[order]
        col_raw = self._col_raw(col_tris, col_owners)
        return fa.Surfaces(xs, ys, col, col_by_class, vis, vis_by_category, names, names, classes,
                           col_tris, col_owners, np.concatenate(vtris), np.concatenate(vowners),
                           np.concatenate(vcats), col_raw, 1000.0, 2000.0)

    def test_buried_edge_case_is_reported_as_edge_ambiguous(self):
        xs = np.array([0.0], dtype=float)
        ys = np.array([0.0], dtype=float)
        terrain = square(0.0, -2.0, 2.0)
        vis_roof = np.array([[(0.0, -1.0, 10.0), (0.0, 1.0, 10.0), (1.0, 0.0, 10.0)]], dtype=float)
        col_roof = np.array([[(5.0e-5, -1.5, 10.0), (5.0e-5, 1.5, 10.0), (1.50005, 0.0, 10.0)]], dtype=float)
        s = self._surfaces(xs, ys, [(terrain, 0), (col_roof, 1)], [(terrain, 0), (vis_roof, 1)],
                           ["terrain:grid", "osm:way/537242388"], ["terrain", "building"])
        f = fa.Findings(1.0, xs, ys, 0.0)
        fa._check_collision_vs_visual(s, f, 0.2)
        self.assertNotIn("buried_collision", f.regions)
        self.assertIn("edge_ambiguous_collision_visual", f.regions)

    def test_footprint_boundary_8m_repro_still_flags_floating(self):
        xs = np.array([0.5], dtype=float)
        ys = np.array([0.5], dtype=float)
        terrain = square(0.0, 0.0, 2.0)
        col_roof = np.array([[(0.5, 0.0, 8.0), (2.0, 0.0, 8.0), (0.5, 2.0, 8.0)]], dtype=float)
        vis_roof = np.array([[(0.50000001, 0.0, 8.0), (2.0, 0.0, 8.0), (0.50000001, 2.0, 8.0)]], dtype=float)
        s = self._surfaces(xs, ys, [(terrain, 0), (col_roof, 1)], [(terrain, 0), (vis_roof, 1)],
                           ["terrain:grid", "osm:way/repro"], ["terrain", "building"])
        f = fa.Findings(1.0, xs, ys, 0.0)
        fa._check_collision_vs_visual(s, f, 0.2)
        self.assertIn("floating_collision", f.regions)
        self.assertAlmostEqual(f.regions["floating_collision"][0]["max_offset_m"], 8.0, places=3)

    def test_10m_buried_repro_is_not_downgraded_by_unrelated_wall_edge(self):
        xs = np.array([0.0], dtype=float)
        ys = np.array([0.0], dtype=float)
        terrain = square(0.0, -2.0, 2.0)
        wall = np.array([[(0.0, -0.01, 0.0), (0.0, 0.01, 10.0), (0.0, 0.02, 0.0)]], dtype=float)
        far_roof = np.array([[(0.5, -1.0, 10.0), (0.5, 1.0, 10.0), (1.5, 0.0, 10.0)]], dtype=float)
        vis_roof = np.array([[(-0.5, -1.0, 10.0), (-0.5, 1.0, 10.0), (0.5, 0.0, 10.0)]], dtype=float)
        s = self._surfaces(xs, ys, [(terrain, 0), (wall, 1), (far_roof, 1)], [(terrain, 0), (vis_roof, 1)],
                           ["terrain:grid", "osm:way/repro10"], ["terrain", "building"])
        f = fa.Findings(1.0, xs, ys, 0.0)
        fa._check_collision_vs_visual(s, f, 0.2)
        self.assertIn("buried_collision", f.regions)
        self.assertNotIn("edge_ambiguous_collision_visual", f.regions)

    def test_edge_ambiguity_requires_within_documented_tolerance(self):
        xs = np.array([0.0], dtype=float)
        ys = np.array([0.0], dtype=float)
        terrain = square(0.0, -2.0, 2.0)
        vis_roof = np.array([[(0.0, -1.0, 10.0), (0.0, 1.0, 10.0), (1.0, 0.0, 10.0)]], dtype=float)
        col_roof = np.array([[(1.1e-4, -1.0, 10.0), (1.1e-4, 1.0, 10.0), (1.00011, 0.0, 10.0)]], dtype=float)
        s = self._surfaces(xs, ys, [(terrain, 0), (col_roof, 1)], [(terrain, 0), (vis_roof, 1)],
                           ["terrain:grid", "osm:way/tol"], ["terrain", "building"])
        f = fa.Findings(1.0, xs, ys, 0.0)
        fa._check_collision_vs_visual(s, f, 0.2)
        self.assertIn("buried_collision", f.regions)
        self.assertNotIn("edge_ambiguous_collision_visual", f.regions)

    def test_shifted_ray_must_hit_same_object_not_other_roof(self):
        xs = np.array([0.0], dtype=float)
        ys = np.array([0.0], dtype=float)
        terrain = square(0.0, -2.0, 2.0)
        match_roof = np.array([[(5.0e-5, -5.0e-5, 10.0), (5.0e-5, 5.0e-5, 10.0), (0.50005, 0.0, 10.0)]], dtype=float)
        other_roof = np.array([[(9.0e-5, -1.0, 10.0), (9.0e-5, 1.0, 10.0), (1.00009, 0.0, 10.0)]], dtype=float)
        vis_roof = np.array([[(0.0, -1.0, 10.0), (0.0, 1.0, 10.0), (1.0, 0.0, 10.0)]], dtype=float)
        s = self._surfaces(xs, ys, [(terrain, 0), (match_roof, 1), (other_roof, 2)], [(terrain, 0), (vis_roof, 1)],
                           ["terrain:grid", "osm:way/match", "osm:way/other"], ["terrain", "building", "building"])
        f = fa.Findings(1.0, xs, ys, 0.0)
        fa._check_collision_vs_visual(s, f, 0.2)
        self.assertIn("buried_collision", f.regions)
        self.assertNotIn("edge_ambiguous_collision_visual", f.regions)


class RoadClassificationTest(unittest.TestCase):
    def test_a_road_hovering_above_the_terrain_is_reported_in_collision_and_visual(self):
        regions = road_findings(HOVER_M)
        for kind in ("ground_above_terrain:road:col", "ground_above_terrain:road:vis"):
            self.assertIn(kind, regions)
            self.assertAlmostEqual(regions[kind][0]["max_offset_m"], HOVER_M)

    def test_a_road_on_the_terrain_is_not_reported(self):
        self.assertEqual(road_findings(0.05), {})


class MapExtentTest(unittest.TestCase):
    def test_cells_past_the_terrain_edge_are_off_the_map(self):
        class Col:
            objects = [{"name": "bank:osm:way/1", "aabb": [0, 0, 0, 99, 99, 1]},
                       {"name": "terrain", "aabb": [0, 0, 0, 10, 20, 1]}]
        on_map = fa._on_map(Col, np.array([5.5, 10.5]), np.array([0.5, 19.5, 20.5]))
        self.assertEqual(on_map.tolist(), [[True, False], [True, False], [False, False]])


class SampleAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = fa.audit(SAMPLE)

    def test_no_collision_floats_above_or_is_buried_below_the_visible_surface(self):
        self.assertTrue(self.result["ok"], self.result["findings_summary"])

    def test_the_sample_roads_do_not_hover(self):
        hovering = [kind for kind in self.result["findings_summary"] if kind.startswith("ground_above_terrain:road")]
        self.assertEqual(hovering, [])

    def test_findings_are_json_serialisable_without_infinities(self):
        json.dumps(self.result, allow_nan=False)

    def test_min_area_does_not_crash_summary_or_json(self):
        with tempfile.TemporaryDirectory() as td:
            out_json = os.path.join(td, "out.json")
            run = subprocess.run(
                [sys.executable, os.path.join(ROOT, "tools", "floating_audit.py"), SAMPLE, "--min-area", "2", "--json", out_json],
                capture_output=True, text=True, check=False
            )
            self.assertNotEqual(run.returncode, 2, run.stderr)
            with open(out_json, encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIsInstance(payload["findings_summary"], dict)

    def test_min_area_keeps_summary_semantics_when_nothing_is_filtered(self):
        base = fa.audit(SAMPLE, min_area=0.0)
        same = fa.audit(SAMPLE, min_area=0.5)
        self.assertEqual(base["findings_summary"], same["findings_summary"])
        self.assertEqual(base["ok"], same["ok"])

    def test_min_area_summary_uses_filtered_regions(self):
        xs = np.array([0.5, 1.5], dtype=float)
        ys = np.array([0.5, 1.5], dtype=float)
        f = fa.Findings(1.0, xs, ys, 2.0)
        value = np.array([[10.0, np.nan], [np.nan, 1.0]], dtype=float)
        mask = np.array([[True, False], [False, True]])
        owner = np.array([[0, -1], [-1, 0]], dtype=np.int32)
        f.flag("buried_collision", value, mask, owner, ["terrain"])
        summary_none = fa._summarise(f.regions)
        self.assertNotIn("buried_collision", summary_none)
        f2 = fa.Findings(1.0, xs, ys, 1.0)
        f2.flag("buried_collision", value, mask, owner, ["terrain"])
        summary = fa._summarise(f2.regions)
        self.assertEqual(summary["buried_collision"]["regions"], 2)
        self.assertEqual(summary["buried_collision"]["area_m2"], 2.0)
        self.assertEqual(summary["buried_collision"]["max_offset_m"], 10.0)


class OutputErrorExitCodeTest(unittest.TestCase):
    """The audit is stubbed: only the output handling is under test."""

    def run_main(self, ok: bool, json_path: str) -> int:
        result = {"ok": ok, "package": "p", "grid": [1, 1], "cell_m": 1.0, "threshold_m": 0.2,
                  "triangles": {"collision": 0, "visual": 0}, "water_bodies": [], "findings_summary": {}}
        with mock.patch.object(fa, "audit", return_value=result), contextlib.redirect_stderr(io.StringIO()), \
                contextlib.redirect_stdout(io.StringIO()):
            return fa.main(["p.mbmap", "--json", json_path, "--quiet"])

    def test_a_missing_json_directory_exits_2_even_when_the_audit_passes(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(self.run_main(True, os.path.join(td, "missing", "out.json")), 2)

    def test_a_missing_json_directory_exits_2_even_when_the_audit_fails(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(self.run_main(False, os.path.join(td, "missing", "out.json")), 2)

    def test_a_writable_json_path_keeps_the_audit_exit_code(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(self.run_main(False, os.path.join(td, "out.json")), 1)
            self.assertEqual(self.run_main(True, os.path.join(td, "out.json")), 0)


if __name__ == "__main__":
    unittest.main()
