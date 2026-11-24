# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S4-COL-FLOAT audit: does the collision (and heightfield) agree with the visible surface, everywhere?

  py -3.12 tools/floating_audit.py PACKAGE.mbmap [--cell 1.0] [--threshold 0.2] [--hf-tol 0.05]
        [--json OUT.json] [--png-dir DIR] [--crops N] [--min-area 0] [--quiet]

On a dense XY grid (one downward ray per cell centre) the tool takes the FIRST hit (highest surface) of

  * the ``.mbcol`` collision, per class and overall,
  * the ``.mbhf`` heightfield (only at its own nodes, compared with the collision and visual terrain there),
  * the visual GLB, per category (terrain, water, road, bridge, building, roof, vegetation, structure, tunnel).

Rays are evaluated exactly (barycentric test at the cell centre on the triangle plane, both facings), batched with
numpy. Findings are grouped into 4-connected regions with area (m^2), maximum offset (m), and the object / class
involved:

  floating_collision        first collision hit above the first visual hit by more than the threshold
  buried_collision          first visual hit above the first collision hit (the drone enters a visible surface)
  mismatch:<category>       the same category (visual vs collision) differs by more than the threshold
  ground_above_terrain:<c>  a road / water / bridge surface above the terrain first hit by more than the threshold
                            (``vis`` = in the GLB, ``col`` = in the collision)
  hf_vs_collision           heightfield node differs from the terrain collision at that node by more than --hf-tol
  hf_vs_visual              heightfield node above / below the visual terrain by more than the threshold
  hf_below_ground:<c>       heightfield (what a heightfield-only consumer lands on) is below a collision ground
                            surface (terrain / road / water) by more than the threshold
  water_above_bank          water surface above the bank terrain just outside the water body by more than the
                            threshold AND the designed carve depth (a flat sheet hanging over the bank)
  water_shore_step          the same up to the carve depth: the bed of the shore cells (informational)
  water_buried              terrain under the water above the water surface by more than the threshold

Also printed per package: water bodies with level, bed depth and the bank gap statistics.
Exit 0 when no finding of the failing kinds (everything except ``hf_below_ground`` which is informational for
water) exists, 1 otherwise, 2 on a read error.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import zipfile
from collections import Counter, deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from map_builder.core.collision import CLASS_NAMES, CLASSES, read_collision, read_heightfield  # noqa: E402
from map_builder.core.query import ray_cast  # noqa: E402
from map_builder.core.water import CARVE_DEPTH_M  # noqa: E402

NAN = np.nan
COMPARE = ("terrain", "water", "road", "bridge", "building")   # categories present on both sides
HF_GROUND_CLASSES = ("terrain", "road", "water")
ROOF_NORMAL_MIN = 0.1           # a roof face is one whose normal points up by at least this fraction
WATER_BANK_BAND_M = 2.0         # how far outside a water body the bank is looked at
SHORE_STEP_M = CARVE_DEPTH_M    # terrain at the shore cells may lie this far below the sheet: the designed bed
SHORE_STEP_TOL_M = 0.05
INFO_KINDS = ("hf_below_ground:water", "hf_coverage", "water_shore_step:col", "water_shore_step:vis",
              "edge_ambiguous_collision_visual")
EDGE_AMBIGUITY_M = 1e-4


BARY_EPS = 1e-9            # barycentric slack: a ray through a shared edge hits both triangles
DEGENERATE_DET = 1e-12     # |det| below this: a vertical or collapsed triangle has no height at a point
HEIGHT_TIE_EPS = 1e-12     # hits this close to the highest one share the cell; the last triangle given owns it
BATCH_CELLS = 1_000_000    # candidate (triangle, cell) pairs held in memory at once


@dataclass
class CellRanges:
    """Per triangle, the inclusive-start rectangle of grid cells its bounding box covers (``ni`` or ``nj`` = 0: none)."""
    i0: np.ndarray
    j0: np.ndarray
    ni: np.ndarray
    nj: np.ndarray

    @property
    def counts(self) -> np.ndarray:
        return self.ni * self.nj


def _axis_range(lo: np.ndarray, hi: np.ndarray, origin: float, step: float, n: int) -> tuple[np.ndarray, np.ndarray]:
    """First cell index and cell count along one axis for the extents [lo, hi], clipped to the grid."""
    first = np.maximum(np.ceil((lo - origin) / step - BARY_EPS).astype(np.int64), 0)
    last = np.minimum(np.floor((hi - origin) / step + BARY_EPS).astype(np.int64), n - 1)
    return first, np.maximum(last - first + 1, 0)


def _cell_ranges(tris: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> CellRanges:
    step_x = float(xs[1] - xs[0]) if len(xs) > 1 else 1.0
    step_y = float(ys[1] - ys[0]) if len(ys) > 1 else 1.0
    i0, ni = _axis_range(tris[:, :, 0].min(1), tris[:, :, 0].max(1), float(xs[0]), step_x, len(xs))
    j0, nj = _axis_range(tris[:, :, 1].min(1), tris[:, :, 1].max(1), float(ys[0]), step_y, len(ys))
    return CellRanges(i0, j0, ni, nj)


def _batches(counts: np.ndarray) -> list[np.ndarray]:
    """Triangle indices (those with at least one cell) in groups of about BATCH_CELLS candidate cells."""
    used = np.nonzero(counts)[0]
    ends = np.cumsum(counts[used])
    batches, start = [], 0
    while start < len(used):
        stop = max(int(np.searchsorted(ends, (ends[start - 1] if start else 0) + BATCH_CELLS, side="right")),
                   start + 1)
        batches.append(used[start:stop])
        start = stop
    return batches


def _candidate_cells(ranges: CellRanges, tri: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every (triangle, cell column, cell row) whose cell lies in the bounding box of a triangle of ``tri``."""
    counts = ranges.counts[tri]
    owner = np.repeat(tri, counts)
    offset = np.arange(int(counts.sum())) - np.repeat(np.cumsum(counts) - counts, counts)
    width = ranges.ni[owner]
    return owner, ranges.i0[owner] + offset % width, ranges.j0[owner] + offset // width


def _plane_heights(tris: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    """Height of each triangle's plane at its own point (px, py), NaN where the point is outside the triangle.

    ``tris`` is (N, 3, 3) vertices x coordinates in the map frame; the test is barycentric, so both facings hit."""
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = (tris[:, v].T for v in range(3))
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    usable = np.abs(det) > DEGENERATE_DET
    det = np.where(usable, det, 1.0)
    w_a = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
    w_b = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
    w_c = 1.0 - w_a - w_b
    inside = usable & (w_a >= -BARY_EPS) & (w_b >= -BARY_EPS) & (w_c >= -BARY_EPS)
    return np.where(inside, w_a * az + w_b * bz + w_c * cz, NAN)


class Raster:
    """Highest-surface raster on a regular grid of cell centres, with the owning object index per cell."""

    def __init__(self, xs: np.ndarray, ys: np.ndarray) -> None:
        self.xs, self.ys = xs, ys
        self.z = np.full((len(ys), len(xs)), -np.inf)
        self.owner = np.full((len(ys), len(xs)), -1, dtype=np.int32)
        self.triangle = np.full((len(ys), len(xs)), -1, dtype=np.int32)

    def add(self, tris: np.ndarray, owners: np.ndarray) -> None:
        """Ray-cast every cell centre against ``tris`` (T, 3, 3), keeping the highest hit and its ``owners`` (T,)."""
        if not len(tris):
            return
        ranges = _cell_ranges(tris, self.xs, self.ys)
        for batch in _batches(ranges.counts):
            tri, column, row = _candidate_cells(ranges, batch)
            heights = _plane_heights(tris[tri], self.xs[column], self.ys[row])
            self._keep_highest(row * len(self.xs) + column, heights, owners[tri], tri)

    def _keep_highest(self, flat_cell: np.ndarray, heights: np.ndarray, owners: np.ndarray,
                      tri_ids: np.ndarray) -> None:
        hit = np.isfinite(heights)
        flat_cell, heights, owners, tri_ids = flat_cell[hit], heights[hit], owners[hit], tri_ids[hit]
        best = self.z.reshape(-1)
        np.maximum.at(best, flat_cell, heights)
        wins = heights >= best[flat_cell] - HEIGHT_TIE_EPS
        self.owner.reshape(-1)[flat_cell[wins]] = owners[wins]
        self.triangle.reshape(-1)[flat_cell[wins]] = tri_ids[wins]

    def final(self) -> np.ndarray:
        return np.where(np.isfinite(self.z), self.z, NAN)



def _load(path: str) -> tuple[dict[str, Any], Any, Any, bytes]:
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("manifest.json"))
        names = z.namelist()
        col = read_collision(z.read(manifest["collision"]["path"]))
        hf = None
        if manifest.get("heightfield") and manifest["heightfield"].get("path") in names:
            hf = read_heightfield(z.read(manifest["heightfield"]["path"]))
        glb = z.read(manifest["visual"]["path"])
    return manifest, col, hf, glb


def _map_tris(tris: Any) -> np.ndarray:
    a = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    return np.stack([a[..., 0], -a[..., 2], a[..., 1]], axis=-1)


def _f32_mat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a @ b).astype(np.float32)


def _f32_trs(node: dict[str, Any]) -> np.ndarray:
    if "matrix" in node:
        m = np.asarray(node["matrix"], dtype=np.float32).reshape(4, 4, order="F")
        return m
    t = np.asarray(node.get("translation", [0, 0, 0]), dtype=np.float32)
    x, y, z, w = np.asarray(node.get("rotation", [0, 0, 0, 1]), dtype=np.float32)
    s = np.asarray(node.get("scale", [1, 1, 1]), dtype=np.float32)
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]], dtype=np.float32)
    out = np.eye(4, dtype=np.float32)
    out[:3, :3] = r * s[np.newaxis, :]
    out[:3, 3] = t
    return out


def _glb_json_bin(glb: bytes) -> tuple[dict[str, Any], bytes]:
    if len(glb) < 20:
        raise ValueError("glb too short")
    magic, ver, total = struct.unpack_from("<III", glb, 0)
    if magic != 0x46546C67 or ver != 2 or total != len(glb):
        raise ValueError("bad glb header")
    offset = 12
    js, binb = None, b""
    while offset < len(glb):
        clen, ctype = struct.unpack_from("<II", glb, offset)
        offset += 8
        chunk = glb[offset:offset + clen]
        offset += clen
        if ctype == 0x4E4F534A:
            js = chunk.rstrip(b" ")
        elif ctype == 0x004E4942:
            binb = bytes(chunk)
    if js is None:
        raise ValueError("missing glb json chunk")
    return cast(dict[str, Any], json.loads(js)), binb


def _accessor_data(gl: dict[str, Any], binb: bytes, accessor_index: int) -> np.ndarray:
    accessors = cast(list[dict[str, Any]], gl.get("accessors", []))
    views = cast(list[dict[str, Any]], gl.get("bufferViews", []))
    acc = accessors[accessor_index]
    view = views[int(acc["bufferView"])]
    comps = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[str(acc["type"])]
    ctype = int(acc["componentType"])
    dtype = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}[ctype]
    count = int(acc["count"])
    stride = int(view.get("byteStride", np.dtype(dtype).itemsize * comps))
    base = int(view.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
    item = np.dtype(dtype).itemsize * comps
    if stride == item:
        return np.frombuffer(binb, dtype=dtype, count=count * comps, offset=base).reshape(count, comps)
    out = np.empty((count, comps), dtype=dtype)
    for i in range(count):
        start = base + i * stride
        out[i] = np.frombuffer(binb, dtype=dtype, count=comps, offset=start)
    return out


def _mesh_local_tris_f32(gl: dict[str, Any], binb: bytes, mesh_index: int) -> np.ndarray:
    meshes = cast(list[dict[str, Any]], gl.get("meshes", []))
    tris: list[np.ndarray] = []
    for p in cast(list[dict[str, Any]], meshes[mesh_index].get("primitives", [])):
        if int(p.get("mode", 4)) != 4:
            continue
        attrs = cast(dict[str, Any], p["attributes"])
        pos = _accessor_data(gl, binb, int(attrs["POSITION"])).astype(np.float32, copy=False)
        if "indices" in p:
            ids = _accessor_data(gl, binb, int(p["indices"])).reshape(-1).astype(np.int64, copy=False)
        else:
            ids = np.arange(len(pos), dtype=np.int64)
        if len(ids) % 3:
            continue
        tris.append(pos[ids.reshape(-1, 3)])
    return np.concatenate(tris) if tris else np.zeros((0, 3, 3), dtype=np.float32)


def _regions(mask: np.ndarray, value: np.ndarray, cell: float, owner: np.ndarray, names: list[str],
             xs: np.ndarray, ys: np.ndarray, min_area: float) -> list[dict[str, Any]]:
    out = []
    seen = np.zeros(mask.shape, dtype=bool)
    ny, nx = mask.shape
    for j, i in zip(*np.nonzero(mask)):
        if seen[j, i]:
            continue
        q = deque([(j, i)])
        seen[j, i] = True
        cells = []
        while q:
            cj, ci = q.popleft()
            cells.append((cj, ci))
            for nj_, ni_ in ((cj + 1, ci), (cj - 1, ci), (cj, ci + 1), (cj, ci - 1)):
                if 0 <= nj_ < ny and 0 <= ni_ < nx and mask[nj_, ni_] and not seen[nj_, ni_]:
                    seen[nj_, ni_] = True
                    q.append((nj_, ni_))
        cj = np.array([c[0] for c in cells])
        ci = np.array([c[1] for c in cells])
        area = len(cells) * cell * cell
        if area < min_area:
            continue
        v = value[cj, ci]
        k = int(np.argmax(np.abs(v)))
        own = Counter(int(o) for o in owner[cj, ci] if o >= 0)
        out.append({
            "area_m2": round(area, 2), "cells": len(cells), "max_offset_m": round(float(v[k]), 3),
            "mean_offset_m": round(float(v.mean()), 3),
            "at_xy": [round(float(xs[ci[k]]), 1), round(float(ys[cj[k]]), 1)],
            "bbox": [round(float(xs[ci].min()), 1), round(float(ys[cj].min()), 1),
                     round(float(xs[ci].max()), 1), round(float(ys[cj].max()), 1)],
            "objects": [{"name": names[o] if 0 <= o < len(names) else str(o), "cells": n}
                        for o, n in own.most_common(3)],
        })
    out.sort(key=lambda r: -cast(float, r["area_m2"]))
    return out


@dataclass
class Surfaces:
    """The highest-surface rasters of one package: collision and visual, overall and per class / category."""
    xs: np.ndarray
    ys: np.ndarray
    col: Raster
    col_by_class: dict[str, Raster]
    vis: Raster
    vis_by_category: dict[str, Raster]
    col_names: list[str]
    vis_names: list[str]
    col_obj_classes: list[str]
    col_tris: np.ndarray
    col_tri_owner: np.ndarray
    vis_tris: np.ndarray
    vis_owner: np.ndarray
    vis_category: np.ndarray
    col_raw: Any
    ray_origin_z: float
    ray_max_dist: float

    def terrain(self, side: str) -> np.ndarray:
        rasters = self.col_by_class if side == "col" else self.vis_by_category
        return rasters["terrain"].final() if "terrain" in rasters else np.full((len(self.ys), len(self.xs)), NAN)


class Findings:
    """Collects findings per kind, with the value layer that the heatmaps draw."""

    def __init__(self, cell: float, xs: np.ndarray, ys: np.ndarray, min_area: float) -> None:
        self.cell, self.xs, self.ys, self.min_area = cell, xs, ys, min_area
        self.regions: dict[str, list[dict[str, Any]]] = {}
        self.layers: dict[str, np.ndarray] = {}

    def flag(self, kind: str, value: np.ndarray, mask: np.ndarray, owner: np.ndarray, names: list[str]) -> None:
        mask = mask & np.isfinite(value)
        self.layers[kind] = np.where(mask, value, NAN)
        if mask.any():
            kept = _regions(mask, np.where(mask, value, 0.0), self.cell, owner, names,
                            self.xs, self.ys, self.min_area)
            if kept:
                self.regions[kind] = kept
            elif kind in self.regions:
                del self.regions[kind]

    def flag_nodes(self, kind: str, value: np.ndarray, mask: np.ndarray, owner: np.ndarray, names: list[str],
                   hf: dict[str, Any]) -> None:
        """Heightfield findings live on the node grid, which has its own spacing."""
        if mask.any():
            kept = _regions(mask, np.where(mask, value, 0.0), hf["spacing"], owner, names,
                            _node_axis(hf, "x"), _node_axis(hf, "y"), self.min_area)
            if kept:
                self.regions[kind] = kept
            elif kind in self.regions:
                del self.regions[kind]


def _node_axis(hf: dict[str, Any], axis: str) -> np.ndarray:
    return hf[axis + "0"] + np.arange(hf["n" + axis]) * hf["spacing"]


def _raster_of(tris: np.ndarray, owners: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> Raster:
    raster = Raster(xs, ys)
    raster.add(tris, owners)
    return raster


def _collision_triangles(col: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    vertices = np.asarray(col.vertices, dtype=np.float64)
    indices = np.asarray(col.indices, dtype=np.int64).reshape(-1, 3)
    classes = np.frombuffer(col.tri_class, dtype=np.uint8)[:len(indices)]
    return vertices[indices], classes, np.asarray(col.tri_object, dtype=np.int32)


def _is_roof(tris: np.ndarray, categories: np.ndarray) -> np.ndarray:
    """Upward-facing triangles of buildings."""
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    upward = normals[:, 2] > ROOF_NORMAL_MIN * np.maximum(np.linalg.norm(normals, axis=1), 1e-12)
    return (categories == "building") & upward


def _visual_triangles_float32(glb: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Visual triangles transformed with consumer-equivalent float32 node composition and vertex transform."""
    gl, binb = _glb_json_bin(glb)
    nodes = cast(list[dict[str, Any]], gl.get("nodes", []))
    names = [str(cast(dict[str, Any], n).get("extras", {}).get("mb_id") or n.get("name") or f"node{i}")
             for i, n in enumerate(nodes)]
    roots: list[int]
    scenes = cast(list[dict[str, Any]], gl.get("scenes", []))
    if scenes:
        si = int(gl.get("scene", 0))
        roots = [int(x) for x in cast(list[Any], scenes[si].get("nodes", []))]
    else:
        roots = list(range(len(nodes)))
    tris, owners, categories = [], [], []
    mesh_cache: dict[int, np.ndarray] = {}
    ident = np.eye(4, dtype=np.float32)
    stack: list[tuple[int, np.ndarray]] = [(int(i), ident.copy()) for i in reversed(roots)]
    while stack:
        ni, parent = stack.pop()
        node = nodes[ni]
        world = _f32_mat_mul(parent, _f32_trs(node))
        if "mesh" in node:
            mesh_index = int(node["mesh"])
            if mesh_index not in mesh_cache:
                mesh_cache[mesh_index] = _mesh_local_tris_f32(gl, binb, mesh_index)
            local = mesh_cache[mesh_index]
            if len(local):
                linear = world[:3, :3]
                trans = world[:3, 3]
                world_tris = (local.reshape(-1, 3) @ linear.T + trans).astype(np.float32).reshape(-1, 3, 3)
                if float(np.linalg.det(linear.astype(np.float64))) < 0.0:
                    world_tris = world_tris[:, [0, 2, 1], :]
                tris.append(_map_tris(world_tris))
                owners.append(np.full(len(world_tris), ni, dtype=np.int32))
                cat = str(cast(dict[str, Any], node.get("extras", {})).get("mb_class") or "user")
                categories.append(np.full(len(world_tris), cat, dtype=object))
        for child in reversed(cast(list[Any], node.get("children", []))):
            stack.append((int(child), world))
    if not tris:
        return np.zeros((0, 3, 3)), np.zeros(0, dtype=np.int32), np.zeros(0, dtype=object), names
    return np.concatenate(tris), np.concatenate(owners), np.concatenate(categories), names


def _build_surfaces(col: Any, visual_glb: bytes, xs: np.ndarray, ys: np.ndarray) -> Surfaces:
    ctris, cclasses, cowners = _collision_triangles(col)
    col_by_class = {}
    for class_id in np.unique(cclasses):
        sel = cclasses == class_id
        col_by_class[CLASS_NAMES[int(class_id)]] = _raster_of(ctris[sel], cowners[sel], xs, ys)
    vtris, vowners, vcats, vis_names = _visual_triangles_float32(visual_glb)
    vis_by_category = {}
    for category in sorted(set(vcats.tolist())):
        sel = vcats == category
        vis_by_category[category] = _raster_of(vtris[sel], vowners[sel], xs, ys)
    roofs = _is_roof(vtris, vcats) if len(vtris) else np.zeros(0, dtype=bool)
    if roofs.any():
        vis_by_category["roof"] = _raster_of(vtris[roofs], vowners[roofs], xs, ys)
    col_names = [o["mb_id"] or o["name"] for o in col.objects]
    lo, hi = col.bounds
    return Surfaces(xs, ys, _raster_of(ctris, cowners, xs, ys), col_by_class, _raster_of(vtris, vowners, xs, ys),
                    vis_by_category, col_names, vis_names, [o["class"] for o in col.objects], ctris, cowners, vtris,
                    vowners, vcats, col, float(hi[2]) + 1000.0, float(hi[2] - lo[2]) + 2000.0)


def _segment_distance_xy(x: float, y: float, a: np.ndarray, b: np.ndarray) -> float:
    dx, dy = float(b[0] - a[0]), float(b[1] - a[1])
    den = dx * dx + dy * dy
    if den == 0.0:
        return math.hypot(x - float(a[0]), y - float(a[1]))
    t = min(1.0, max(0.0, ((x - float(a[0])) * dx + (y - float(a[1])) * dy) / den))
    qx, qy = float(a[0]) + t * dx, float(a[1]) + t * dy
    return math.hypot(x - qx, y - qy)


def _triangle_edge_distance_xy(tri: np.ndarray, x: float, y: float) -> float:
    return min(_segment_distance_xy(x, y, tri[k], tri[(k + 1) % 3]) for k in range(3))


def _triangle_plane_z_xy(tri: np.ndarray, x: float, y: float) -> float:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(float(det)) <= DEGENERATE_DET:
        return NAN
    w_a = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / det
    w_b = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / det
    w_c = 1.0 - w_a - w_b
    return float(w_a * az + w_b * bz + w_c * cz)


def _top_surface_tris_by_object(s: Surfaces) -> dict[int, np.ndarray]:
    normals = np.cross(s.col_tris[:, 1] - s.col_tris[:, 0], s.col_tris[:, 2] - s.col_tris[:, 0])
    up = np.abs(normals[:, 2]) > ROOF_NORMAL_MIN * np.maximum(np.linalg.norm(normals, axis=1), 1e-12)
    out: dict[int, np.ndarray] = {}
    for oi in np.unique(s.col_tri_owner):
        sel = (s.col_tri_owner == oi) & up
        if sel.any():
            out[int(oi)] = s.col_tris[sel]
    return out


def _buried_edge_ambiguous(s: Surfaces, buried: np.ndarray, threshold: float, tol: float) -> np.ndarray:
    """Edge-ambiguous buried cells satisfy both:
    (a) near an edge of the matched collision top-surface triangle(s) at the visual hit height,
    (b) one of the four ±tol x/y shifted collision rays reaches the visual height within ``threshold``."""
    out = np.zeros_like(buried, dtype=bool)
    col_index = {name: i for i, name in enumerate(s.col_names)}
    top_tris = _top_surface_tris_by_object(s)
    top_tri_mask = np.zeros(len(s.col_tris), dtype=bool)
    for oi, _tris in top_tris.items():
        own = np.nonzero(s.col_tri_owner == oi)[0]
        if len(own):
            normals = np.cross(s.col_tris[own, 1] - s.col_tris[own, 0], s.col_tris[own, 2] - s.col_tris[own, 0])
            up = np.abs(normals[:, 2]) > ROOF_NORMAL_MIN * np.maximum(np.linalg.norm(normals, axis=1), 1e-12)
            top_tri_mask[own[up]] = True
    for j, i in zip(*np.nonzero(buried)):
        vi = int(s.vis.owner[j, i])
        if vi < 0:
            continue
        vis_name = s.vis_names[vi]
        coi = col_index.get(vis_name)
        if coi is None or coi not in top_tris:
            continue
        if s.col_obj_classes[coi] == "terrain":
            continue
        x, y = float(s.xs[i]), float(s.ys[j])
        visual_z = float(s.vis.z[j, i])
        candidates = [t for t in top_tris[coi]
                      if _triangle_edge_distance_xy(t, x, y) <= tol
                      and abs(_triangle_plane_z_xy(t, x, y) - visual_z) <= threshold]
        if not candidates:
            continue
        hit = ray_cast(s.col_raw, (x, y, s.ray_origin_z), (0.0, 0.0, -1.0), s.ray_max_dist)
        if hit is not None and int(hit.object) == coi:
            tri = s.col_tris[int(hit.triangle)]
            if _triangle_edge_distance_xy(tri, x, y) > tol or abs(_triangle_plane_z_xy(tri, x, y) - visual_z) > threshold:
                continue
        for dx, dy in ((tol, tol), (tol, -tol), (-tol, tol), (-tol, -tol)):
            h = ray_cast(s.col_raw, (x + dx, y + dy, s.ray_origin_z), (0.0, 0.0, -1.0), s.ray_max_dist)
            if h is None:
                continue
            if int(h.object) != coi or not top_tri_mask[int(h.triangle)]:
                continue
            shifted_tri = s.col_tris[int(h.triangle)]
            if _triangle_edge_distance_xy(shifted_tri, x + dx, y + dy) > tol:
                continue
            z = s.ray_origin_z - float(h.t)
            if abs(z - visual_z) <= threshold:
                out[j, i] = True
                break
    return out


def _check_collision_vs_visual(s: Surfaces, f: Findings, threshold: float) -> None:
    c, v = s.col.final(), s.vis.final()
    d = c - v
    buried = d < -threshold
    edge_ambiguous = _buried_edge_ambiguous(s, buried, threshold, EDGE_AMBIGUITY_M)
    f.flag("edge_ambiguous_collision_visual", d, edge_ambiguous, s.vis.owner, s.vis_names)
    f.flag("floating_collision", d, d > threshold, s.col.owner, s.col_names)
    f.flag("buried_collision", d, buried & ~edge_ambiguous, s.vis.owner, s.vis_names)
    for category in COMPARE:
        cr, vr = s.col_by_class.get(category), s.vis_by_category.get(category)
        if cr is not None and vr is not None:
            diff = cr.final() - vr.final()
            f.flag(f"mismatch:{category}", diff, np.abs(diff) > threshold, cr.owner, s.col_names)


def _check_roads(s: Surfaces, f: Findings, threshold: float) -> None:
    """Road ribbons must lie on the terrain mesh, not hover above it."""
    for side, rasters, names in (("col", s.col_by_class, s.col_names), ("vis", s.vis_by_category, s.vis_names)):
        if "road" in rasters:
            above = rasters["road"].final() - s.terrain(side)
            f.flag(f"ground_above_terrain:road:{side}", above, above > threshold, rasters["road"].owner, names)


def _check_heightfield(s: Surfaces, f: Findings, hf: dict[str, Any], col: Any, threshold: float, hf_tol: float) -> None:
    hx, hy = _node_axis(hf, "x"), _node_axis(hf, "y")
    hz = np.asarray(hf["z"], dtype=np.float64)
    ctris, cclasses, cowners = _collision_triangles(col)

    def at_nodes(tris: np.ndarray, owners: np.ndarray) -> Raster:
        return _raster_of(tris, owners, hx, hy)

    terrain = cclasses == CLASSES["terrain"]
    col_terrain = at_nodes(ctris[terrain], cowners[terrain])
    diff = hz - col_terrain.final()
    f.flag_nodes("hf_vs_collision", diff, np.abs(diff) > hf_tol, col_terrain.owner, s.col_names, hf)
    one_sided = np.isnan(hz) != np.isnan(col_terrain.final())
    f.flag_nodes("hf_coverage", np.ones_like(hz), one_sided, col_terrain.owner, s.col_names, hf)

    vis = s.vis_category == "terrain"
    vis_terrain = at_nodes(s.vis_tris[vis], s.vis_owner[vis])
    diff = hz - vis_terrain.final()
    f.flag_nodes("hf_vs_visual", diff, np.abs(diff) > threshold, vis_terrain.owner, s.vis_names, hf)

    for category in HF_GROUND_CLASSES:
        if category in s.col_by_class:
            sel = cclasses == CLASSES[category]
            ground = at_nodes(ctris[sel], cowners[sel])
            below = hz - ground.final()
            f.flag_nodes(f"hf_below_ground:{category}", below, np.isfinite(below) & (below < -threshold),
                         ground.owner, s.col_names, hf)


def _spread(level: np.ndarray, steps: int) -> np.ndarray:
    """Nearest-water level propagated outward (a body is flat, so the max over neighbours is exact)."""
    spread = level.copy()
    for _ in range(steps):
        grown = spread.copy()
        grown[1:] = np.fmax(grown[1:], spread[:-1])
        grown[:-1] = np.fmax(grown[:-1], spread[1:])
        grown[:, 1:] = np.fmax(grown[:, 1:], spread[:, :-1])
        grown[:, :-1] = np.fmax(grown[:, :-1], spread[:, 1:])
        spread = grown
    return spread


def _dilate(mask: np.ndarray, steps: int) -> np.ndarray:
    return np.isfinite(_spread(np.where(mask, 0.0, NAN), steps))


def _check_water(s: Surfaces, f: Findings, threshold: float, cell: float, on_map: np.ndarray) -> None:
    """Water against its banks: a bank more than the carve depth below the sheet is a floating mat; the carve-depth
    step inside the shore cells is the designed bed (info)."""
    steps = max(1, int(round(WATER_BANK_BAND_M / cell)))
    for side, rasters, names in (("col", s.col_by_class, s.col_names), ("vis", s.vis_by_category, s.vis_names)):
        if "water" not in rasters:
            continue
        water, owner = rasters["water"].final(), rasters["water"].owner
        wet = np.isfinite(water)
        bank_ring = _dilate(wet, steps) & ~wet & on_map
        gap = _spread(water, steps) - s.terrain(side)
        nearest = _spread(np.where(owner >= 0, owner + 1.0, NAN), steps)
        ring_owner = np.where(np.isfinite(nearest), nearest - 1, -1).astype(np.int32)
        designed = gap <= SHORE_STEP_M + SHORE_STEP_TOL_M
        f.flag(f"water_above_bank:{side}", gap, bank_ring & (gap > threshold) & ~designed, ring_owner, names)
        f.flag(f"water_shore_step:{side}", gap, bank_ring & (gap > threshold) & designed, ring_owner, names)
        under = water - s.terrain(side)
        f.flag(f"water_buried:{side}", under, wet & (under < -threshold), owner, names)


def _water_bodies(s: Surfaces) -> list[dict]:
    if "water" not in s.col_by_class:
        return []
    water = s.col_by_class["water"]
    levels, terrain = water.final(), s.terrain("col")
    bodies = []
    for owner in np.unique(water.owner[np.isfinite(water.z)]):
        mine = (water.owner == owner) & np.isfinite(levels)
        bed = (terrain - levels)[mine]
        has_bed = np.isfinite(bed).any()
        bodies.append({
            "object": s.col_names[owner], "level_m": round(float(np.nanmedian(levels[mine])), 3),
            "level_span_m": round(float(np.nanmax(levels[mine]) - np.nanmin(levels[mine])), 3),
            "area_m2": round(float(mine.sum() * (s.xs[1] - s.xs[0]) * (s.ys[1] - s.ys[0])), 1),
            "bed_min_m": round(float(np.nanmin(bed)), 2) if has_bed else None,
            "bed_max_m": round(float(np.nanmax(bed)), 2) if has_bed else None})
    return bodies


def _on_map(col: Any, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Cells over the terrain grid itself; shore ramps may spill past the map edge, where there is no ground."""
    box = next(e["aabb"] for e in col.objects if e["name"] == "terrain")
    return (((xs >= box[0]) & (xs <= box[3]))[None, :]) & (((ys >= box[1]) & (ys <= box[4]))[:, None])


def _grid_axes(col: Any, cell: float) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = col.bounds
    axes = []
    for k in (0, 1):
        start = math.floor(lo[k])
        axes.append(start + (np.arange(int(math.ceil(hi[k] - start) / cell) + 1) + 0.5) * cell)
    return axes[0], axes[1]


def _summarise(regions: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, float | int]]:
    out: dict[str, dict[str, float | int]] = {}
    for kind, found in regions.items():
        if not found:
            continue
        out[kind] = {"regions": len(found), "area_m2": round(sum(r["area_m2"] for r in found), 1),
                     "max_offset_m": max((r["max_offset_m"] for r in found), key=abs)}
    return out


def audit(path: str, cell: float = 1.0, threshold: float = 0.2, hf_tol: float = 0.05, min_area: float = 0.0,
          png_dir: str | None = None, crops: int = 0) -> dict:
    manifest, col, hf, visual_glb = _load(path)
    xs, ys = _grid_axes(col, cell)
    surfaces = _build_surfaces(col, visual_glb, xs, ys)
    findings = Findings(cell, xs, ys, min_area)
    with np.errstate(invalid="ignore"):
        _check_collision_vs_visual(surfaces, findings, threshold)
        _check_roads(surfaces, findings, threshold)
        if hf is not None:
            _check_heightfield(surfaces, findings, hf, col, threshold, hf_tol)
        _check_water(surfaces, findings, threshold, cell, _on_map(col, xs, ys))
    summary = _summarise(findings.regions)
    result = {"package": os.path.basename(path), "cell_m": cell, "threshold_m": threshold, "hf_tol_m": hf_tol,
              "grid": [len(xs), len(ys)],
              "triangles": {"collision": int(len(col.indices) // 3), "visual": int(len(surfaces.vis_tris))},
              "findings_summary": summary, "findings": findings.regions,
              "water_bodies": _water_bodies(surfaces),
              "ok": not any(kind not in INFO_KINDS for kind in summary)}
    if png_dir:
        vis_terrain = surfaces.terrain("vis")
        _render(png_dir, os.path.splitext(os.path.basename(path))[0], xs, ys, findings.layers,
                surfaces.vis.final(), vis_terrain, findings.regions, crops)
    return result


CROP_PAD_M = 12.0          # context around a region in its crop
CROP_MIN_PIXELS = 160      # crops are enlarged until their short side has about this many pixels
HEATMAP_MIN_RANGE_M = 1.0  # the colour scale spans at least this much, so tiny offsets do not look severe


def _shade(h: np.ndarray) -> np.ndarray:
    """Grey hill-shade of a height raster (NaN cells take its lowest height)."""
    z = np.nan_to_num(h, nan=float(np.nanmin(h)) if np.isfinite(h).any() else 0.0)
    gy, gx = np.gradient(z)
    s = np.clip(0.5 + 0.6 * (-gx - gy), 0, 1)
    return (60 + 150 * s).astype(np.uint8)


def _colour(v: np.ndarray, vmax: float) -> np.ndarray:
    """Red for positive offsets, blue for negative, white at zero."""
    t = np.clip(np.abs(v) / vmax, 0, 1)
    pos = v >= 0
    r = np.where(pos, 255, 40 + 100 * (1 - t)).astype(np.uint8)
    g = (230 * (1 - t)).astype(np.uint8)
    b = np.where(pos, 40 + 60 * (1 - t), 255).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)


def _overlay(base: np.ndarray, layer: np.ndarray) -> np.ndarray:
    """Copy of the grey ``base`` image with the finite cells of ``layer`` painted by offset."""
    image = base.copy()
    painted = np.isfinite(layer)
    if painted.any():
        image[painted] = _colour(layer[painted], max(HEATMAP_MIN_RANGE_M, float(np.nanmax(np.abs(layer)))))
    return image


def _index_window(axis: np.ndarray, lo: float, hi: float) -> slice:
    """Cells of a regular ``axis`` covering [lo - pad, hi + pad]."""
    step = axis[1] - axis[0]
    first = max(0, int((lo - CROP_PAD_M - axis[0]) / step))
    last = min(len(axis), int((hi + CROP_PAD_M - axis[0]) / step) + 1)
    return slice(first, last)


def _enlarge(image: np.ndarray) -> np.ndarray:
    scale = max(1, CROP_MIN_PIXELS // max(1, min(image.shape[:2])))
    return np.kron(image, np.ones((scale, scale, 1), dtype=np.uint8))


def _save_png(image: np.ndarray, png_dir: str, name: str) -> None:
    from PIL import Image
    Image.fromarray(np.flipud(image)).save(os.path.join(png_dir, name))   # row 0 is the southern edge


def _render(png_dir: str, stem: str, xs: np.ndarray, ys: np.ndarray, layers: dict[str, np.ndarray],
            visible: np.ndarray, visible_terrain: np.ndarray, findings: dict[str, list[dict[str, Any]]],
            crops: int) -> None:
    """One heatmap per finding kind, plus crops of the ``crops`` largest regions of each kind."""
    os.makedirs(png_dir, exist_ok=True)
    grey = _shade(np.where(np.isfinite(visible), visible, visible_terrain))
    base = np.stack([grey] * 3, axis=-1)
    for kind, layer in layers.items():
        if np.isfinite(layer).any():
            _save_png(_overlay(base, layer), png_dir, f"{stem}.{kind.replace(':', '-')}.heat.png")
    crop_number = 0
    for kind, regions in findings.items():
        for region in regions[:crops] if kind in layers else []:
            x0, y0, x1, y1 = region["bbox"]
            rows, columns = _index_window(ys, y0, y1), _index_window(xs, x0, x1)
            crop = _overlay(base[rows, columns], layers[kind][rows, columns])
            _save_png(_enlarge(crop), png_dir, f"{stem}.{kind.replace(':', '-')}.crop{crop_number}.png")
            crop_number += 1



def _print(res: dict[str, Any], quiet: bool) -> None:
    print(f"{res['package']}: grid {res['grid'][0]}x{res['grid'][1]} @ {res['cell_m']} m, threshold "
          f"{res['threshold_m']} m, triangles col {res['triangles']['collision']} / vis {res['triangles']['visual']}")
    for b in res["water_bodies"]:
        print(f"  water {b['object']}: level {b['level_m']} m (span {b['level_span_m']}), area {b['area_m2']} m2, "
              f"bed below water {b['bed_min_m']}..{b['bed_max_m']} m (terrain - water)")
    if not res["findings_summary"]:
        print("  no findings")
    for k, s in sorted(res["findings_summary"].items()):
        tag = " (info)" if k in INFO_KINDS else ""
        print(f"  {k:36s} regions {s['regions']:5d}  area {s['area_m2']:10.1f} m2  max offset {s['max_offset_m']:8.3f} m{tag}")
        if not quiet:
            for r in res["findings"][k][:3]:
                o = ", ".join(f"{x['name']}({x['cells']})" for x in r["objects"]) or "-"
                print(f"      {r['area_m2']:9.1f} m2  max {r['max_offset_m']:7.3f} m at {r['at_xy']}  {o}")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package")
    ap.add_argument("--cell", type=float, default=1.0, help="grid cell size in metres (default 1)")
    ap.add_argument("--threshold", type=float, default=0.2, help="floating threshold in metres (default 0.2)")
    ap.add_argument("--hf-tol", type=float, default=0.05, help="heightfield vs collision node tolerance")
    ap.add_argument("--min-area", type=float, default=0.0, help="drop regions smaller than this (m^2)")
    ap.add_argument("--json", help="write the full result as JSON")
    ap.add_argument("--png-dir", help="write heatmaps (and --crops regions) as PNG")
    ap.add_argument("--crops", type=int, default=0, help="crops of the N largest regions per finding kind")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    try:
        res = audit(a.package, a.cell, a.threshold, a.hf_tol, a.min_area, a.png_dir, a.crops)
    except Exception as e:  # noqa: BLE001 - report any read failure uniformly
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    _print(res, a.quiet)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
