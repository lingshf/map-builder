# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S4-COL-FLOAT audit: does the collision (and heightfield) agree with the visible surface, everywhere?

  py -3.12 tools/floating_audit.py PACKAGE.mbmap [--cell 1.0] [--threshold 0.2] [--hf-tol 0.05]
        [--json OUT.json] [--png-dir DIR] [--crops N] [--min-area 0] [--quiet]

On a dense XY grid (one downward ray per cell centre) the tool takes the FIRST hit (highest surface) of

  * the ``.mbcol`` collision, per class and overall,
  * the ``.mbhf`` heightfield (at its own nodes, and bilinear at every grid point),
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
import sys
import zipfile
from collections import Counter, deque
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from map_builder.core.collision import CLASS_NAMES, CLASSES, read_collision, read_heightfield  # noqa: E402
from map_builder.core.glb import read_glb  # noqa: E402
from map_builder.core.water import CARVE_DEPTH_M  # noqa: E402

NAN = np.nan
COMPARE = ("terrain", "water", "road", "bridge", "building")   # categories present on both sides
HF_GROUND_CLASSES = ("terrain", "road", "water")
ROOF_NORMAL_MIN = 0.1           # a roof face is one whose normal points up by at least this fraction
WATER_BANK_BAND_M = 2.0         # how far outside a water body the bank is looked at
SHORE_STEP_M = CARVE_DEPTH_M    # terrain at the shore cells may lie this far below the sheet: the designed bed
SHORE_STEP_TOL_M = 0.05
INFO_KINDS = ("hf_below_ground:water", "hf_coverage", "water_shore_step:col", "water_shore_step:vis")


class Raster:
    """Highest-surface raster on a regular grid of cell centres, with the owning object index per cell."""

    def __init__(self, xs: np.ndarray, ys: np.ndarray) -> None:
        self.xs, self.ys = xs, ys
        self.z = np.full((len(ys), len(xs)), -np.inf)
        self.owner = np.full((len(ys), len(xs)), -1, dtype=np.int32)

    def add(self, tris: np.ndarray, owners: np.ndarray, budget: int = 3_000_000) -> None:
        """tris: (T,3,3) map-frame triangles; owners: (T,) object index."""
        if not len(tris):
            return
        xs, ys = self.xs, self.ys
        dx = float(xs[1] - xs[0]) if len(xs) > 1 else 1.0
        dy = float(ys[1] - ys[0]) if len(ys) > 1 else 1.0
        x0, y0 = float(xs[0]), float(ys[0])
        tx, ty = tris[:, :, 0], tris[:, :, 1]
        i0 = np.ceil((tx.min(1) - x0) / dx - 1e-9).astype(np.int64)
        i1 = np.floor((tx.max(1) - x0) / dx + 1e-9).astype(np.int64)
        j0 = np.ceil((ty.min(1) - y0) / dy - 1e-9).astype(np.int64)
        j1 = np.floor((ty.max(1) - y0) / dy + 1e-9).astype(np.int64)
        i0, j0 = np.maximum(i0, 0), np.maximum(j0, 0)
        i1, j1 = np.minimum(i1, len(xs) - 1), np.minimum(j1, len(ys) - 1)
        ni, nj = i1 - i0 + 1, j1 - j0 + 1
        keep = (ni > 0) & (nj > 0)
        idx = np.nonzero(keep)[0]
        if not len(idx):
            return
        size = (ni[idx] * nj[idx])
        order = idx[np.argsort(size, kind="stable")]
        size = ni[order] * nj[order]
        pos = 0
        while pos < len(order):
            # a chunk of similar-size triangles whose padded cell count stays within the budget
            end = pos + 1
            while end < len(order) and (end - pos + 1) * int(size[end]) <= budget and \
                    size[end] <= 2 * size[pos] + 4:
                end += 1
            sel = order[pos:end]
            self._chunk(tris[sel], owners[sel], i0[sel], j0[sel], ni[sel], nj[sel], x0, y0, dx, dy)
            pos = end

    def _chunk(self, t, owner, i0, j0, ni, nj, x0, y0, dx, dy) -> None:
        mi, mj = int(ni.max()), int(nj.max())
        ii = i0[:, None, None] + np.arange(mi)[None, :, None] + np.zeros((1, 1, mj), dtype=np.int64)
        jj = j0[:, None, None] + np.arange(mj)[None, None, :] + np.zeros((1, mi, 1), dtype=np.int64)
        valid = (np.arange(mi)[None, :, None] < ni[:, None, None]) & (np.arange(mj)[None, None, :] < nj[:, None, None])
        px = x0 + ii * dx
        py = y0 + jj * dy
        ax, ay, az = (t[:, 0, k][:, None, None] for k in range(3))
        bx, by, bz = (t[:, 1, k][:, None, None] for k in range(3))
        cx, cy, cz = (t[:, 2, k][:, None, None] for k in range(3))
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        ok = np.abs(det) > 1e-12
        safe = np.where(ok, det, 1.0)
        l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / safe
        l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / safe
        l3 = 1.0 - l1 - l2
        e = 1e-9
        inside = valid & ok & (l1 >= -e) & (l2 >= -e) & (l3 >= -e)
        z = l1 * az + l2 * bz + l3 * cz
        k = np.nonzero(inside)
        if not len(k[0]):
            return
        flat = jj[k] * len(self.xs) + ii[k]
        zz = z[k]
        zf = self.z.reshape(-1)
        np.maximum.at(zf, flat, zz)
        win = zz >= zf[flat] - 1e-12
        self.owner.reshape(-1)[flat[win]] = owner[k[0]][win]

    def final(self) -> np.ndarray:
        return np.where(np.isfinite(self.z), self.z, NAN)


def _load(path: str):
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("manifest.json"))
        names = z.namelist()
        col = read_collision(z.read(manifest["collision"]["path"]))
        hf = None
        if manifest.get("heightfield") and manifest["heightfield"].get("path") in names:
            hf = read_heightfield(z.read(manifest["heightfield"]["path"]))
        glb = read_glb(z.read(manifest["visual"]["path"]))
    return manifest, col, hf, glb


def _map_tris(tris) -> np.ndarray:
    a = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    return np.stack([a[..., 0], -a[..., 2], a[..., 1]], axis=-1)


def _regions(mask: np.ndarray, value: np.ndarray, cell: float, owner: np.ndarray, names: list[str], xs, ys,
             min_area: float) -> list[dict]:
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
    out.sort(key=lambda r: -r["area_m2"])
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

    def terrain(self, side: str) -> np.ndarray:
        rasters = self.col_by_class if side == "col" else self.vis_by_category
        return rasters["terrain"].final() if "terrain" in rasters else np.full((len(self.ys), len(self.xs)), NAN)


class Findings:
    """Collects findings per kind, with the value layer that the heatmaps draw."""

    def __init__(self, cell: float, xs: np.ndarray, ys: np.ndarray, min_area: float) -> None:
        self.cell, self.xs, self.ys, self.min_area = cell, xs, ys, min_area
        self.regions: dict[str, list[dict]] = {}
        self.layers: dict[str, np.ndarray] = {}

    def flag(self, kind: str, value: np.ndarray, mask: np.ndarray, owner: np.ndarray, names: list[str]) -> None:
        mask = mask & np.isfinite(value)
        self.layers[kind] = np.where(mask, value, NAN)
        if mask.any():
            self.regions[kind] = _regions(mask, np.where(mask, value, 0.0), self.cell, owner, names,
                                          self.xs, self.ys, self.min_area)

    def flag_nodes(self, kind: str, value: np.ndarray, mask: np.ndarray, owner: np.ndarray, names: list[str],
                   hf: dict) -> None:
        """Heightfield findings live on the node grid, which has its own spacing."""
        if mask.any():
            self.regions[kind] = _regions(mask, np.where(mask, value, 0.0), hf["spacing"], owner, names,
                                          _node_axis(hf, "x"), _node_axis(hf, "y"), self.min_area)


def _node_axis(hf: dict, axis: str) -> np.ndarray:
    return hf[axis + "0"] + np.arange(hf["n" + axis]) * hf["spacing"]


def _raster_of(tris: np.ndarray, owners: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> Raster:
    raster = Raster(xs, ys)
    raster.add(tris, owners)
    return raster


def _collision_triangles(col) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    vertices = np.asarray(col.vertices, dtype=np.float64)
    indices = np.asarray(col.indices, dtype=np.int64).reshape(-1, 3)
    classes = np.frombuffer(col.tri_class, dtype=np.uint8)[:len(indices)]
    return vertices[indices], classes, np.asarray(col.tri_object, dtype=np.int32)


def _is_roof(tris: np.ndarray, categories: np.ndarray) -> np.ndarray:
    """Upward-facing triangles of buildings."""
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    upward = normals[:, 2] > ROOF_NORMAL_MIN * np.maximum(np.linalg.norm(normals, axis=1), 1e-12)
    return (categories == "building") & upward


def _visual_triangles(nodes) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """(triangles, node index, category, node names) of every GLB node, in the map frame."""
    tris, owners, categories, names = [], [], [], []
    for index, node in enumerate(nodes):
        names.append(str(node.extras.get("mb_id") or node.name))
        if not node.triangles:
            continue
        mapped = _map_tris(node.triangles)
        tris.append(mapped)
        owners.append(np.full(len(mapped), index, dtype=np.int32))
        categories.append(np.full(len(mapped), str(node.extras.get("mb_class") or "user"), dtype=object))
    if not tris:
        return np.zeros((0, 3, 3)), np.zeros(0, dtype=np.int32), np.zeros(0, dtype=object), names
    return np.concatenate(tris), np.concatenate(owners), np.concatenate(categories), names


def _build_surfaces(col, nodes, xs: np.ndarray, ys: np.ndarray) -> Surfaces:
    ctris, cclasses, cowners = _collision_triangles(col)
    col_by_class = {}
    for class_id in np.unique(cclasses):
        sel = cclasses == class_id
        col_by_class[CLASS_NAMES[int(class_id)]] = _raster_of(ctris[sel], cowners[sel], xs, ys)
    vtris, vowners, vcats, vis_names = _visual_triangles(nodes)
    vis_by_category = {}
    for category in sorted(set(vcats.tolist())):
        sel = vcats == category
        vis_by_category[category] = _raster_of(vtris[sel], vowners[sel], xs, ys)
    roofs = _is_roof(vtris, vcats) if len(vtris) else np.zeros(0, dtype=bool)
    if roofs.any():
        vis_by_category["roof"] = _raster_of(vtris[roofs], vowners[roofs], xs, ys)
    col_names = [o["mb_id"] or o["name"] for o in col.objects]
    return Surfaces(xs, ys, _raster_of(ctris, cowners, xs, ys), col_by_class, _raster_of(vtris, vowners, xs, ys),
                    vis_by_category, col_names, vis_names)


def _check_collision_vs_visual(s: Surfaces, f: Findings, threshold: float) -> None:
    c, v = s.col.final(), s.vis.final()
    d = c - v
    f.flag("floating_collision", d, d > threshold, s.col.owner, s.col_names)
    f.flag("buried_collision", d, d < -threshold, s.vis.owner, s.vis_names)
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


def _check_heightfield(s: Surfaces, f: Findings, hf: dict, col, nodes, threshold: float, hf_tol: float) -> None:
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

    vtris, vowners, vcats, _ = _visual_triangles(nodes)
    vis = vcats == "terrain"
    vis_terrain = at_nodes(vtris[vis], vowners[vis])
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


def _check_water(s: Surfaces, f: Findings, threshold: float, cell: float) -> None:
    """Water against its banks: a bank more than the carve depth below the sheet is a floating mat; the carve-depth
    step inside the shore cells is the designed bed (info)."""
    steps = max(1, int(round(WATER_BANK_BAND_M / cell)))
    for side, rasters, names in (("col", s.col_by_class, s.col_names), ("vis", s.vis_by_category, s.vis_names)):
        if "water" not in rasters:
            continue
        water, owner = rasters["water"].final(), rasters["water"].owner
        wet = np.isfinite(water)
        bank_ring = _dilate(wet, steps) & ~wet
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


def _grid_axes(col, cell: float) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = col.bounds
    axes = []
    for k in (0, 1):
        start = math.floor(lo[k])
        axes.append(start + (np.arange(int(math.ceil(hi[k] - start) / cell) + 1) + 0.5) * cell)
    return axes[0], axes[1]


def _summarise(regions: dict[str, list[dict]]) -> dict[str, dict]:
    return {kind: {"regions": len(found), "area_m2": round(sum(r["area_m2"] for r in found), 1),
                   "max_offset_m": max((r["max_offset_m"] for r in found), key=abs)}
            for kind, found in regions.items()}


def audit(path: str, cell: float = 1.0, threshold: float = 0.2, hf_tol: float = 0.05, min_area: float = 0.0,
          png_dir: str | None = None, crops: int = 0) -> dict:
    manifest, col, hf, (_glb, nodes) = _load(path)
    xs, ys = _grid_axes(col, cell)
    surfaces = _build_surfaces(col, nodes, xs, ys)
    findings = Findings(cell, xs, ys, min_area)
    with np.errstate(invalid="ignore"):
        _check_collision_vs_visual(surfaces, findings, threshold)
        _check_roads(surfaces, findings, threshold)
        if hf is not None:
            _check_heightfield(surfaces, findings, hf, col, nodes, threshold, hf_tol)
        _check_water(surfaces, findings, threshold, cell)
    result = {"package": os.path.basename(path), "cell_m": cell, "threshold_m": threshold, "hf_tol_m": hf_tol,
              "grid": [len(xs), len(ys)],
              "triangles": {"collision": int(len(col.indices) // 3), "visual": int(sum(len(n.triangles) for n in nodes))},
              "findings_summary": _summarise(findings.regions), "findings": findings.regions,
              "water_bodies": _water_bodies(surfaces),
              "ok": not any(kind not in INFO_KINDS for kind in findings.regions)}
    if png_dir:
        vis_terrain = surfaces.terrain("vis")
        _render(png_dir, os.path.splitext(os.path.basename(path))[0], xs, ys, findings.layers,
                surfaces.vis.final(), vis_terrain, findings.regions, crops)
    return result


def _shade(h: np.ndarray) -> np.ndarray:
    z = np.nan_to_num(h, nan=float(np.nanmin(h)) if np.isfinite(h).any() else 0.0)
    gy, gx = np.gradient(z)
    s = np.clip(0.5 + 0.6 * (-gx - gy), 0, 1)
    return (60 + 150 * s).astype(np.uint8)


def _colour(v: np.ndarray, vmax: float) -> np.ndarray:
    t = np.clip(np.abs(v) / vmax, 0, 1)
    pos = v >= 0
    r = np.where(pos, 255, 40 + 100 * (1 - t)).astype(np.uint8)
    g = (230 * (1 - t)).astype(np.uint8)
    b = np.where(pos, 40 + 60 * (1 - t), 255).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)


def _render(png_dir, stem, xs, ys, layers, V, vterr, findings, crops) -> None:
    from PIL import Image
    os.makedirs(png_dir, exist_ok=True)
    base = _shade(np.where(np.isfinite(V), V, vterr))
    rgb0 = np.stack([base] * 3, axis=-1)

    def save(img: np.ndarray, name: str) -> None:
        Image.fromarray(np.flipud(img)).save(os.path.join(png_dir, name))

    for kind, lay in layers.items():
        if not np.isfinite(lay).any():
            continue
        vmax = max(1.0, float(np.nanmax(np.abs(lay))))
        rgb = rgb0.copy()
        m = np.isfinite(lay)
        rgb[m] = _colour(lay[m], vmax)
        save(rgb, f"{stem}.{kind.replace(':', '-')}.heat.png")
    n = 0
    for kind, regs in findings.items():
        for r in regs[:crops]:
            lay = layers.get(kind)
            if lay is None:
                continue
            pad = 12.0
            x0, y0, x1, y1 = r["bbox"]
            i0 = max(0, int((x0 - pad - xs[0]) / (xs[1] - xs[0])))
            i1 = min(len(xs), int((x1 + pad - xs[0]) / (xs[1] - xs[0])) + 1)
            j0 = max(0, int((y0 - pad - ys[0]) / (ys[1] - ys[0])))
            j1 = min(len(ys), int((y1 + pad - ys[0]) / (ys[1] - ys[0])) + 1)
            rgb = rgb0[j0:j1, i0:i1].copy()
            sub = lay[j0:j1, i0:i1]
            m = np.isfinite(sub)
            if m.any():
                rgb[m] = _colour(sub[m], max(1.0, float(np.nanmax(np.abs(sub)))))
            scale = max(1, 160 // max(1, min(rgb.shape[:2])))
            rgb = np.kron(rgb, np.ones((scale, scale, 1), dtype=np.uint8))
            save(rgb, f"{stem}.{kind.replace(':', '-')}.crop{n}.png")
            n += 1


def _print(res: dict, quiet: bool) -> None:
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


def main(argv=None) -> int:
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
