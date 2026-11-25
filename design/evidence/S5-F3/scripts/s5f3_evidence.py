"""S5-F3 step-1 evidence (session files, read-only): per-region measurements for every water and heightfield
finding of ``tools/floating_audit.py`` on one package.

  py -3.12 s5f3_evidence.py --root <tree> --pkg <pkg.mbmap> --blocked <blocked_strips.json> --out <dir>

For every region: id, category, bbox, centre and cell XYs; at every cell the collision top hit (``core/query.py``,
Python and C#), the visual top hit, the water sheet and the outside terrain / ``bank:`` surface on each surface;
Python and C# rays on a +-0.5 m grid at 0.1 m around the centre; category-specific context (blocked shore strips,
ring distance, D117 bed test). Writes ``evidence.json`` and ``summary.md``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import zipfile
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

GRID_HALF_M = 0.5            # spec: rays on a +-0.5 m grid ...
GRID_STEP_M = 0.1            # ... at 0.1 m spacing around the region centre
SHORE_STEP_BOUND_M = 1.501   # spec: 1.5 m designed carve step + 1 mm float error
BLOCKED_STRIP_PAD_M = 3.0    # a blocked shore strip this close to a region bbox is reported with it
WORKERS = 14
RAY_CHUNK = 200
THRESHOLD_M = 0.2
WATER_KINDS = ("water_above_bank", "water_shore_step")
HF_KIND = "hf_below_ground:water"
SIDES = ("col", "vis")
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))

fa: Any = None   # tools/floating_audit.py, imported once --root is on the path
wr: Any = None   # tools/water_replay.py
_worker_col: Any = None


# --- rays -------------------------------------------------------------------------------------------------------

def _init_worker(root: str, col_bytes: bytes) -> None:
    global _worker_col, wr
    sys.path[:0] = [root, str(Path(root) / "tools")]
    from map_builder.core.collision import read_collision
    import water_replay
    wr = water_replay
    _worker_col = read_collision(col_bytes)


def _python_chunk(job: tuple[list[tuple[float, float, float]], float]) -> list[Any]:
    origins, dist = job
    return [wr.py_hit(_worker_col, o, dist) for o in origins]


class Rays:
    """Downward rays through both readers; Python runs in a process pool, C# in one batch."""

    def __init__(self, root: str, col: Any, col_bytes: bytes) -> None:
        lo, hi = col.bounds
        self.root, self.col, self.col_bytes = root, col, col_bytes
        self.top, self.dist = float(hi[2]) + 1000.0, float(hi[2] - lo[2]) + 2000.0

    def cast(self, xys: list[tuple[float, float]], cache: Path) -> list[dict[str, Any]]:
        """Hits for ``xys``; each distinct XY is cast once, and the results are kept in ``cache`` for re-runs."""
        unique = sorted(set(xys))
        if cache.exists():
            hits = json.loads(cache.read_text())
        else:
            hits = self._cast_unique(unique)
            cache.write_text(json.dumps(hits), "utf-8")
        by_xy = {tuple(h["xy"]): h for h in hits}
        return [by_xy[(round(x, 3), round(y, 3))] for x, y in xys]

    def _cast_unique(self, xys: list[tuple[float, float]]) -> list[dict[str, Any]]:
        origins = [(x, y, self.top) for x, y in xys]
        chunks = [(origins[k:k + RAY_CHUNK], self.dist) for k in range(0, len(origins), RAY_CHUNK)]
        with ProcessPoolExecutor(WORKERS, initializer=_init_worker, initargs=(self.root, self.col_bytes)) as pool:
            python = [h for part in pool.map(_python_chunk, chunks) for h in part]
        with tempfile.TemporaryDirectory(prefix="mb-s5f3-cs-") as work:
            csharp = wr.csharp_rays(self.col_bytes, origins, self.dist, work)
        return [self._record(xy, p, c) for xy, p, c in zip(xys, python, csharp)]

    def _record(self, xy: tuple[float, float], python: Any, csharp: Any) -> dict[str, Any]:
        return {"xy": [round(xy[0], 3), round(xy[1], 3)], "python": self._hit(python, by_index=False),
                "csharp": self._hit(csharp, by_index=True), "disagreement": wr.ray_disagreement(python, csharp, self.col)}

    def _hit(self, hit: Any, by_index: bool) -> dict[str, Any] | None:
        if hit is None:
            return None
        t, ident, cls = hit
        obj = self.col.objects[int(ident)] if by_index else next(o for o in self.col.objects if o["name"] == ident)
        return {"z": round(self.top - t, 4), "mb_id": obj["mb_id"] or obj["name"], "class": cls}


def ray_grid(cx: float, cy: float) -> list[tuple[float, float]]:
    n = int(round(GRID_HALF_M / GRID_STEP_M))
    return [(round(cx + i * GRID_STEP_M, 4), round(cy + j * GRID_STEP_M, 4))
            for j in range(-n, n + 1) for i in range(-n, n + 1)]


# --- regions ----------------------------------------------------------------------------------------------------

def components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """4-connected components of ``mask`` as (row, column) cells, the decomposition ``floating_audit._regions`` uses."""
    seen = np.zeros(mask.shape, dtype=bool)
    out = []
    for j, i in zip(*np.nonzero(mask)):
        if seen[j, i]:
            continue
        seen[j, i] = True
        queue, cells = deque([(int(j), int(i))]), []
        while queue:
            cj, ci = queue.popleft()
            cells.append((cj, ci))
            for dj, di in NEIGHBOURS:
                nj, ni = cj + dj, ci + di
                if 0 <= nj < mask.shape[0] and 0 <= ni < mask.shape[1] and mask[nj, ni] and not seen[nj, ni]:
                    seen[nj, ni] = True
                    queue.append((nj, ni))
        out.append(cells)
    return out


def bbox_of(cells: list[tuple[int, int]], xs: np.ndarray, ys: np.ndarray) -> list[float]:
    cx, cy = [float(xs[i]) for _, i in cells], [float(ys[j]) for j, _ in cells]
    return [round(min(cx), 1), round(min(cy), 1), round(max(cx), 1), round(max(cy), 1)]


def centre_cell(cells: list[tuple[int, int]], xs: np.ndarray, ys: np.ndarray) -> tuple[int, int]:
    """The region cell nearest the mean of its cell centres, so the centre always lies in the region."""
    mx = float(np.mean([xs[i] for _, i in cells]))
    my = float(np.mean([ys[j] for j, _ in cells]))
    return min(cells, key=lambda c: (xs[c[1]] - mx) ** 2 + (ys[c[0]] - my) ** 2)


def match_audit_region(cells: list[tuple[int, int]], bbox: list[float], reported: list[dict[str, Any]]) -> int:
    """Index of the audit-reported region with the same cell count and bbox; it must exist exactly once."""
    hits = [k for k, r in enumerate(reported) if r["cells"] == len(cells) and r["bbox"] == bbox]
    if len(hits) != 1:
        raise SystemExit(f"region {bbox} ({len(cells)} cells) matches {len(hits)} audit regions")
    return hits[0]


# --- surfaces at the audit grid ---------------------------------------------------------------------------------

def _z(v: float) -> float | None:
    return round(float(v), 4) if np.isfinite(v) else None


class WaterLayers:
    """Per surface: the sheet level spread over the bank band (as the audit), its owner, and the outside terrain."""

    def __init__(self, s: Any) -> None:
        steps = max(1, int(round(fa.WATER_BANK_BAND_M / 1.0)))
        self.s, self.layers = s, {}
        for side, rasters, names in (("col", s.col_by_class, s.col_names), ("vis", s.vis_by_category, s.vis_names)):
            water = rasters["water"]
            nearest = fa._spread(np.where(water.owner >= 0, water.owner + 1.0, np.nan), steps)
            self.layers[side] = {"sheet": fa._spread(water.final(), steps), "sheet_owner": nearest,
                                 "terrain": s.terrain(side), "terrain_owner": rasters["terrain"].owner,
                                 "wet": np.isfinite(water.final()), "names": names}

    def cell_row(self, j: int, i: int, top_hit: dict[str, Any]) -> dict[str, Any]:
        s = self.s
        vis_tri = int(s.vis.triangle[j, i])
        row = {"xy": [float(s.xs[i]), float(s.ys[j])], "collision_top": top_hit,
               "visual_top": {"z": _z(s.vis.final()[j, i]), "owner": self._name("vis", s.vis.owner[j, i]),
                              "category": str(s.vis_category[vis_tri]) if vis_tri >= 0 else None}}
        for side in SIDES:
            L = self.layers[side]
            sheet, terrain = L["sheet"][j, i], L["terrain"][j, i]
            row[side] = {"sheet_z": _z(sheet), "sheet_owner": self._name(side, L["sheet_owner"][j, i] - 1),
                         "outside_z": _z(terrain), "outside_owner": self._name(side, L["terrain_owner"][j, i]),
                         "offset_m": _z(sheet - terrain)}
        return row

    def _name(self, side: str, owner: float) -> str | None:
        names = self.layers[side]["names"]
        return names[int(owner)] if np.isfinite(owner) and 0 <= int(owner) < len(names) else None

    def ring_steps(self, j: int, i: int) -> int:
        """Grid steps (4-neighbour) from the cell to the nearest collision-wet cell, the audit's ring distance."""
        wet = self.layers["col"]["wet"]
        for steps in range(1, 3):
            for dj in range(-steps, steps + 1):
                di = steps - abs(dj)
                for ii in {i - di, i + di}:
                    jj = j + dj
                    if 0 <= jj < wet.shape[0] and 0 <= ii < wet.shape[1] and wet[jj, ii]:
                        return steps
        return 0


# --- category context -------------------------------------------------------------------------------------------

def _in_padded_bbox(p: list[float], bbox: list[float], pad: float) -> bool:
    return bbox[0] - pad <= p[0] <= bbox[2] + pad and bbox[1] - pad <= p[1] <= bbox[3] + pad


def _point_in_tri_xy(x: float, y: float, t: np.ndarray) -> bool:
    (ax, ay), (bx, by), (cx, cy) = t[0, :2], t[1, :2], t[2, :2]
    d1 = (x - bx) * (ay - by) - (ax - bx) * (y - by)
    d2 = (x - cx) * (by - cy) - (bx - cx) * (y - cy)
    d3 = (x - ax) * (cy - ay) - (cx - ax) * (y - ay)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


class MaskObjects:
    """Names the package objects under a blocking line mask: the bridge/road ribbons covering its centreline."""

    def __init__(self, s: Any) -> None:
        self.s = s
        self.by_object: dict[int, np.ndarray] = {}
        for k, cls in enumerate(s.col_obj_classes):
            if cls in ("bridge", "road"):
                self.by_object[k] = s.col_tris[s.col_tri_owner == k]
        self._memo: dict[str, list[str]] = {}

    def under_polyline_near(self, polyline: list[list[float]], bbox: list[float], reach: float) -> list[str]:
        key = json.dumps([polyline, bbox, reach])
        if key not in self._memo:
            points = self._centreline_points(polyline, bbox, reach)
            self._memo[key] = sorted({self.s.col_names[k] for k, tris in self._objects_near(bbox, reach).items()
                                      for x, y in points
                                      if any(_point_in_tri_xy(x, y, t) for t in self._near(tris, x, y))})
        return self._memo[key]

    def _objects_near(self, bbox: list[float], reach: float) -> dict[int, np.ndarray]:
        out = {}
        for k, tris in self.by_object.items():
            lo, hi = tris[:, :, :2].min(axis=(0, 1)), tris[:, :, :2].max(axis=(0, 1))
            if lo[0] <= bbox[2] + reach and hi[0] >= bbox[0] - reach and lo[1] <= bbox[3] + reach \
                    and hi[1] >= bbox[1] - reach:
                out[k] = tris
        return out

    @staticmethod
    def _near(tris: np.ndarray, x: float, y: float) -> np.ndarray:
        lo, hi = tris[:, :, :2].min(axis=1), tris[:, :, :2].max(axis=1)
        keep = (lo[:, 0] <= x) & (hi[:, 0] >= x) & (lo[:, 1] <= y) & (hi[:, 1] >= y)
        return tris[keep]

    @staticmethod
    def _centreline_points(polyline: list[list[float]], bbox: list[float], reach: float) -> list[tuple[float, float]]:
        out = []
        for (ax, ay), (bx, by) in zip(polyline, polyline[1:]):
            n = max(1, int(math.hypot(bx - ax, by - ay)))
            for k in range(n + 1):
                x, y = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
                if _in_padded_bbox([x, y], bbox, reach):
                    out.append((x, y))
        return out


def blocked_strips_near(strips: list[dict[str, Any]], bbox: list[float], masks: MaskObjects,
                        reach: float) -> list[dict[str, Any]]:
    out = []
    for strip in strips:
        if not (_in_padded_bbox(strip["a"], bbox, BLOCKED_STRIP_PAD_M)
                or _in_padded_bbox(strip["b"], bbox, BLOCKED_STRIP_PAD_M)):
            continue
        reasons = []
        for r in strip["reasons"]:
            entry = {"mask": r["mask"]}
            if r["mask"] == "line":
                entry["half_width_m"] = r["half_width_m"]
                entry["objects"] = masks.under_polyline_near(r["polyline"], bbox, reach)
            reasons.append(entry)
        out.append({"a": strip["a"], "b": strip["b"], "length_m": round(math.dist(strip["a"][:2], strip["b"][:2]), 3),
                    "kind": "cascade" if strip["cascade"] else "bank", "reasons": _unique(reasons)})
    return out


def _unique(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen, out = set(), []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


# --- heightfield ------------------------------------------------------------------------------------------------

class HeightfieldLayers:
    """Heightfield nodes against the collision and visual terrain and water at the same nodes."""

    def __init__(self, s: Any, hf: dict[str, Any], hf_tol: float) -> None:
        self.hx, self.hy = fa._node_axis(hf, "x"), fa._node_axis(hf, "y")
        self.hz, self.hf_tol = np.asarray(hf["z"], dtype=np.float64), hf_tol
        self.col_terrain = self._at_nodes(s.col_tris, s.col_tri_owner, s.col_obj_classes, "terrain")
        self.col_water = self._at_nodes(s.col_tris, s.col_tri_owner, s.col_obj_classes, "water")
        self.vis_terrain = self._vis_at_nodes(s, "terrain")
        self.vis_water = self._vis_at_nodes(s, "water")
        self.names = s.col_names

    def _at_nodes(self, tris: np.ndarray, owner: np.ndarray, classes: list[str], cls: str) -> Any:
        sel = np.array([classes[o] == cls for o in owner])
        return fa._raster_of(tris[sel], owner[sel], self.hx, self.hy)

    def _vis_at_nodes(self, s: Any, category: str) -> Any:
        sel = s.vis_category == category
        return fa._raster_of(s.vis_tris[sel], s.vis_owner[sel], self.hx, self.hy)

    def finding_mask(self) -> np.ndarray:
        """The audit's ``hf_below_ground:water`` test: the heightfield more than the threshold under the water."""
        below = self.hz - self.col_water.final()
        return np.isfinite(below) & (below < -THRESHOLD_M)

    def node_row(self, j: int, i: int, top_hit: dict[str, Any]) -> dict[str, Any]:
        hz, terrain, water = self.hz[j, i], self.col_terrain.final()[j, i], self.col_water.final()[j, i]
        owner = int(self.col_water.owner[j, i])
        return {"xy": [round(float(self.hx[i]), 3), round(float(self.hy[j]), 3)], "collision_top": top_hit,
                "hf_z": _z(hz), "col_terrain_z": _z(terrain), "col_water_z": _z(water),
                "vis_terrain_z": _z(self.vis_terrain.final()[j, i]), "vis_water_z": _z(self.vis_water.final()[j, i]),
                "water_owner": self.names[owner] if owner >= 0 else None, "offset_m": _z(hz - water),
                "hf_is_bed": bool(np.isfinite(terrain) and abs(hz - terrain) <= self.hf_tol)}


# --- assembly ---------------------------------------------------------------------------------------------------

def water_regions(s: Any, layers: WaterLayers, audit_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Every water region per side, rebuilt from the audit's own value layers and matched to the report."""
    findings = fa.Findings(1.0, s.xs, s.ys, 0.0)
    with np.errstate(invalid="ignore"):
        fa._check_water(s, findings, THRESHOLD_M, 1.0, fa._on_map(s.col_raw, s.xs, s.ys))
    out = []
    for base in WATER_KINDS:
        for side in SIDES:
            kind = f"{base}:{side}"
            reported = audit_json["findings"].get(kind, [])
            for cells in components(np.isfinite(findings.layers[kind])):
                bbox = bbox_of(cells, s.xs, s.ys)
                k = match_audit_region(cells, bbox, reported)
                out.append({"id": f"{kind}#{k + 1}", "category": kind, "side": side, "bbox": bbox, "cells": cells,
                            "reported": reported[k]})
    return out


def hf_regions(hl: HeightfieldLayers, audit_json: dict[str, Any]) -> list[dict[str, Any]]:
    reported = audit_json["findings"].get(HF_KIND, [])
    out = []
    for cells in components(hl.finding_mask()):
        bbox = bbox_of(cells, hl.hx, hl.hy)
        k = match_audit_region(cells, bbox, reported)
        out.append({"id": f"{HF_KIND}#{k + 1}", "category": HF_KIND, "side": "col", "bbox": bbox, "cells": cells,
                    "reported": reported[k]})
    return out


def cast_all(rays: Rays, regions: list[dict[str, Any]], axes: dict[str, tuple[np.ndarray, np.ndarray]],
             cache: Path) -> None:
    """Cell rays and centre-grid rays for every region, cast in one batch per reader."""
    plan: list[tuple[dict[str, Any], str, tuple[float, float]]] = []
    for r in regions:
        xs, ys = axes[r["category"]]
        plan += [(r, "cell", (float(xs[i]), float(ys[j]))) for j, i in r["cells"]]
        cj, ci = centre_cell(r["cells"], xs, ys)
        r["centre"] = [float(xs[ci]), float(ys[cj])]
        plan += [(r, "grid", xy) for xy in ray_grid(*r["centre"])]
    hits = rays.cast([xy for _, _, xy in plan], cache)
    for (r, what, _), hit in zip(plan, hits):
        r.setdefault(f"{what}_rays", []).append(hit)


def describe_water(r: dict[str, Any], layers: WaterLayers, strips: list[dict[str, Any]], masks: MaskObjects,
                   body_info: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = [layers.cell_row(j, i, hit["python"]) for (j, i), hit in zip(r["cells"], r["cell_rays"])]
    side = r["side"]
    offsets = [row[side]["offset_m"] for row in rows if row[side]["offset_m"] is not None]
    bodies = sorted({row[side]["sheet_owner"] for row in rows if row[side]["sheet_owner"]})
    out = _region_head(r) | {
        "max_offset_m": max(offsets), "over_shore_step_bound": max(offsets) > SHORE_STEP_BOUND_M,
        "bodies": bodies, "shore_ramp_blocked_m": {b: body_info.get(b, {}).get("shore_ramp_blocked_m") for b in bodies},
        "outside_owners": sorted({row[side]["outside_owner"] or "-" for row in rows}),
        "bank_ramp_cells": sum(1 for row in rows if (row[side]["outside_owner"] or "").startswith("bank:")),
        "ring_steps": sorted({layers.ring_steps(j, i) for j, i in r["cells"]}),
        "blocked_strips": blocked_strips_near(strips, r["bbox"], masks, BLOCKED_STRIP_PAD_M + 12.0),
        "cells": rows}
    return out | _ray_summary(r)


def describe_hf(r: dict[str, Any], hl: HeightfieldLayers) -> dict[str, Any]:
    rows = [hl.node_row(j, i, hit["python"]) for (j, i), hit in zip(r["cells"], r["cell_rays"])]
    bed = sum(row["hf_is_bed"] for row in rows)
    return _region_head(r) | {
        "bodies": sorted({row["water_owner"] or "-" for row in rows}), "max_offset_m": r["reported"]["max_offset_m"],
        "nodes_hf_equals_collision_bed": bed, "nodes": len(rows),
        "depth_below_sheet_m": [min(-row["offset_m"] for row in rows), max(-row["offset_m"] for row in rows)],
        "cells": rows} | _ray_summary(r)


def _region_head(r: dict[str, Any]) -> dict[str, Any]:
    return {"id": r["id"], "category": r["category"], "bbox": r["bbox"], "centre": r["centre"],
            "cell_count": len(r["cells"])}


def _ray_summary(r: dict[str, Any]) -> dict[str, Any]:
    every = r["cell_rays"] + r["grid_rays"]
    return {"python_csharp_disagreements": sum(1 for h in every if h["disagreement"]),
            "grid_top_objects": sorted({f'{h["python"]["mb_id"]} ({h["python"]["class"]})'
                                        for h in r["grid_rays"] if h["python"]}),
            "grid_rays": r["grid_rays"]}


def body_report(pkg: str) -> dict[str, dict[str, Any]]:
    with zipfile.ZipFile(pkg) as z:
        report = json.loads(z.read("report.json"))
    return {f'water:{b["id"]}': b for b in report.get("water_bodies", [])}


def main(argv: list[str]) -> int:
    global fa, wr
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--audit", required=True, help="floating_audit --json output for --pkg")
    ap.add_argument("--blocked", required=True, help="blocked_strips.py output for the same build")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    sys.path[:0] = [a.root, str(Path(a.root) / "tools")]
    import floating_audit
    import water_replay
    fa, wr = floating_audit, water_replay

    manifest, col, hf, glb = fa._load(a.pkg)
    with zipfile.ZipFile(a.pkg) as z:
        col_bytes = z.read(manifest["collision"]["path"])
    audit_json = json.loads(Path(a.audit).read_text())
    xs, ys = fa._grid_axes(col, 1.0)
    s = fa._build_surfaces(col, glb, xs, ys)
    layers, hl = WaterLayers(s), HeightfieldLayers(s, hf, audit_json["hf_tol_m"])
    regions = water_regions(s, layers, audit_json) + hf_regions(hl, audit_json)
    axes = {r["category"]: (hl.hx, hl.hy) if r["category"] == HF_KIND else (xs, ys) for r in regions}
    a.out.mkdir(parents=True, exist_ok=True)
    cast_all(Rays(a.root, col, col_bytes), regions, axes, a.out / "rays-cache.json")

    strips, masks, bodies = json.loads(Path(a.blocked).read_text()), MaskObjects(s), body_report(a.pkg)
    evidence = [describe_hf(r, hl) if r["category"] == HF_KIND else describe_water(r, layers, strips, masks, bodies)
                for r in regions]
    (a.out / "evidence.json").write_text(json.dumps({"package": Path(a.pkg).name, "regions": evidence}), "utf-8")
    print(f"{len(evidence)} regions; disagreements {sum(e['python_csharp_disagreements'] for e in evidence)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
