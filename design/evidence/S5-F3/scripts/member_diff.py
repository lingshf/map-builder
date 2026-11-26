# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5-F3 AC5 evidence: what changed between two packages, member by member and object by object.

  py -3.12 member_diff.py BEFORE.mbmap AFTER.mbmap [--json OUT]

Reports the whole-archive and per-member SHA-256, the collision objects and GLB nodes whose triangles differ (by
mb_id / node name), the heightfield nodes that differ (count and plan bbox), and which manifest and report keys
differ. Run from the repository root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path.cwd()))
from map_builder.core.collision import read_collision, read_heightfield  # noqa: E402
from tools.floating_audit import _f32_trs, _glb_json_bin, _mesh_local_tris_f32  # noqa: E402

# the keys that must not change (AC5), checked whatever else changes
PINNED_MANIFEST_KEYS = ("georeference", "passage_probes", "orientation_probes", "axes", "area")
PINNED_REPORT_KEYS = ("passage_probes_blocked", "passage_probes_dropped", "water_decks_raised", "counts")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _members(z: zipfile.ZipFile) -> dict[str, bytes]:
    return {name: z.read(name) for name in z.namelist()}


def _collision_objects(data: bytes) -> dict[str, str]:
    """mb_id (or name) -> digest of the object's class and triangle vertices."""
    col = read_collision(data)
    vertices = np.asarray(col.vertices, dtype=np.float32)
    tris = vertices[np.asarray(col.indices, dtype=np.int64).reshape(-1, 3)]
    out = {}
    for o in col.objects:
        body = tris[o["tri_start"]:o["tri_start"] + o["tri_count"]]
        out[o["mb_id"] or o["name"]] = _sha(o["class"].encode() + body.tobytes())
    return out


def _glb_nodes(data: bytes) -> dict[str, str]:
    """Node name -> digest of its transform and mesh triangles."""
    gl, binb = _glb_json_bin(data)
    out = {}
    for i, node in enumerate(gl.get("nodes", [])):
        body = _f32_trs(node).tobytes()
        if "mesh" in node:
            body += _mesh_local_tris_f32(gl, binb, int(node["mesh"])).tobytes()
        out[node.get("name", f"#{i}")] = _sha(body)
    return out


def _changed(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    return {"changed": sorted(k for k in before.keys() & after.keys() if before[k] != after[k]),
            "removed": sorted(before.keys() - after.keys()), "added": sorted(after.keys() - before.keys())}


def _heightfield_nodes(before: bytes, after: bytes) -> dict[str, Any]:
    """The number of heightfield nodes whose height differs (NaN equals NaN) and their plan bbox."""
    a, b = read_heightfield(before), read_heightfield(after)
    grid_keys = ("nx", "ny", "x0", "y0", "spacing")
    if any(a[k] != b[k] for k in grid_keys):
        return {"grid_changed": {k: [a[k], b[k]] for k in grid_keys}}
    za, zb = np.asarray(a["z"], dtype=np.float64), np.asarray(b["z"], dtype=np.float64)
    differs = ~((za == zb) | (np.isnan(za) & np.isnan(zb)))
    rows, cols = np.nonzero(differs)
    out: dict[str, Any] = {"changed_nodes": int(differs.sum()), "total_nodes": int(differs.size)}
    if len(rows):
        xs, ys = a["x0"] + cols * a["spacing"], a["y0"] + rows * a["spacing"]
        out["bbox_xy"] = [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]
        out["max_abs_dz_m"] = float(np.nanmax(np.abs(zb[differs] - za[differs])))
    return out


def _keys_differing(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))


def _manifest_objects(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
    def by_id(m: dict[str, Any]) -> dict[str, str]:
        return {o["mb_id"] or o["name"]: _sha(json.dumps(o, sort_keys=True).encode()) for o in m["objects"]}
    return _changed(by_id(before), by_id(after))


def _changed_fields(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, dict[str, list[Any]]]:
    """Per entry id, the fields whose value differs, as [before, after]."""
    old = {e["id"]: e for e in before}
    out = {}
    for entry in after:
        prev = old.get(entry["id"], {})
        fields = {k: [prev.get(k), entry.get(k)] for k in _keys_differing(prev, entry)}
        if fields:
            out[entry["id"]] = fields
    return out


def diff(before_path: Path, after_path: Path) -> dict[str, Any]:
    before_bytes, after_bytes = before_path.read_bytes(), after_path.read_bytes()
    out: dict[str, Any] = {"before": str(before_path), "after": str(after_path),
                           "archive_identical": before_bytes == after_bytes,
                           "archive_sha256": [_sha(before_bytes), _sha(after_bytes)]}
    with zipfile.ZipFile(before_path) as zb, zipfile.ZipFile(after_path) as za:
        mb, ma = _members(zb), _members(za)
    out["members_changed"] = sorted(n for n in mb.keys() | ma.keys() if mb.get(n) != ma.get(n))
    manifest_b, manifest_a = json.loads(mb["manifest.json"]), json.loads(ma["manifest.json"])
    report_b, report_a = json.loads(mb["report.json"]), json.loads(ma["report.json"])
    out["manifest_keys_changed"] = _keys_differing(manifest_b, manifest_a)
    out["manifest_objects"] = _manifest_objects(manifest_b, manifest_a)
    out["report_keys_changed"] = _keys_differing(report_b, report_a)
    out["report_water_bodies"] = _changed_fields(report_b.get("water_bodies", []), report_a.get("water_bodies", []))
    out["report_budget_export"] = {k: [report_b[k], report_a[k]] for k in ("budget", "export")
                                   if report_b[k] != report_a[k]}
    out["pinned_unchanged"] = {
        **{f"manifest.{k}": manifest_b.get(k) == manifest_a.get(k) for k in PINNED_MANIFEST_KEYS},
        **{f"report.{k}": report_b.get(k) == report_a.get(k) for k in PINNED_REPORT_KEYS}}
    paths = {role: manifest_a[role]["path"] for role in ("collision", "visual", "heightfield")}
    out["collision_objects"] = _changed(_collision_objects(mb[paths["collision"]]),
                                        _collision_objects(ma[paths["collision"]]))
    out["glb_nodes"] = _changed(_glb_nodes(mb[paths["visual"]]), _glb_nodes(ma[paths["visual"]]))
    out["heightfield"] = _heightfield_nodes(mb[paths["heightfield"]], ma[paths["heightfield"]])
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    result = diff(args.before, args.after)
    text = json.dumps(result, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
