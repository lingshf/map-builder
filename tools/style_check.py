# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5 style checks: G0 flight-data equality, identity checks, and style budget metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import zipfile
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from map_builder.core.glb import read_glb  # noqa: E402


@dataclass(frozen=True)
class PackageData:
    members: dict[str, bytes]
    manifest: dict[str, Any]
    report: dict[str, Any]
    glb: bytes


def _build_path_kind(manifest: dict[str, Any]) -> str:
    generator = manifest.get("generator")
    if isinstance(generator, dict) and generator.get("blender"):
        return "blender"
    return "cli"


def _load_package(path: str) -> PackageData:
    with zipfile.ZipFile(path, "r") as z:
        members = {name: z.read(name) for name in z.namelist()}
    manifest = json.loads(members["manifest.json"])
    report = json.loads(members.get("report.json", b"{}"))
    glb_path = manifest["visual"]["path"]
    return PackageData(members=members, manifest=manifest, report=report, glb=members[glb_path])


def _exact_equal(a: Any, b: Any) -> bool:
    return a == b


def g0_check(base_path: str, head_path: str) -> tuple[bool, list[str]]:
    base = _load_package(base_path)
    head = _load_package(head_path)
    failures: list[str] = []
    base_kind = _build_path_kind(base.manifest)
    head_kind = _build_path_kind(head.manifest)
    if base_kind != head_kind:
        failures.append(f"cross-path comparison rejected: base={base_kind}, head={head_kind}")
        return False, failures

    for member in ("collision/map.mbcol", "collision/terrain.mbhf"):
        if base.members.get(member) != head.members.get(member):
            failures.append(f"{member} differs")

    if not _exact_equal(base.manifest.get("georeference"), head.manifest.get("georeference")):
        failures.append("manifest.georeference differs")
    if not _exact_equal(base.manifest.get("passage_probes"), head.manifest.get("passage_probes")):
        failures.append("manifest.passage_probes differs")
    if not _exact_equal(base.report.get("passage_probes_blocked"), head.report.get("passage_probes_blocked")):
        failures.append("report.passage_probes_blocked differs")
    if not _exact_equal(base.report.get("passage_probes_dropped"), head.report.get("passage_probes_dropped")):
        failures.append("report.passage_probes_dropped differs")

    return not failures, failures


def classic_identity_check(base_path: str, head_path: str) -> tuple[bool, list[str]]:
    with open(base_path, "rb") as f:
        base = f.read()
    with open(head_path, "rb") as f:
        head = f.read()
    if base == head:
        return True, []
    return False, ["whole archive differs"]


def mode_member_diff(classic_path: str, stylized_path: str) -> dict[str, list[str]]:
    classic = _load_package(classic_path)
    stylized = _load_package(stylized_path)
    cset = set(classic.members)
    sset = set(stylized.members)
    changed = sorted([k for k in sorted(cset & sset) if classic.members[k] != stylized.members[k]])
    return {"added": sorted(sset - cset), "removed": sorted(cset - sset), "changed": changed}


def _buffer_slice(gl: dict[str, Any], bin_chunk: bytes, accessor_index: int) -> bytes:
    accessors = gl.get("accessors", [])
    views = gl.get("bufferViews", [])
    a = accessors[accessor_index]
    v = views[a["bufferView"]]
    voff = int(v.get("byteOffset", 0))
    vlen = int(v["byteLength"])
    aoff = int(a.get("byteOffset", 0))
    ct = int(a["componentType"])
    nc = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
    sz = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}[ct]
    count = int(a["count"])
    stride = int(v.get("byteStride", 0) or (sz * nc))
    start = voff + aoff
    if stride == sz * nc:
        end = start + count * sz * nc
        return bin_chunk[start:end]
    out = bytearray()
    for i in range(count):
        off = start + i * stride
        out.extend(bin_chunk[off:off + sz * nc])
    if count and a["type"] == "SCALAR" and ct in (5121, 5123, 5125):
        fmt = {5121: "<%dB", 5123: "<%dH", 5125: "<%dI"}[ct] % count
        vals = struct.unpack(fmt, bytes(out))
        return struct.pack("<%dI" % count, *vals)
    return bytes(out)


def _glb_json_and_bin(glb_bytes: bytes) -> tuple[dict[str, Any], bytes]:
    gl, _ = read_glb(glb_bytes)
    # read_glb validates structure; re-read raw chunks for byte-exact accessor slices
    if len(glb_bytes) < 20:
        raise ValueError("invalid glb")
    json_len = struct.unpack_from("<I", glb_bytes, 12)[0]
    json_off = 20
    json_end = json_off + json_len
    bin_len = struct.unpack_from("<I", glb_bytes, json_end)[0]
    bin_off = json_end + 8
    return gl, glb_bytes[bin_off:bin_off + bin_len]


def glb_metrics(path: str) -> dict[str, int]:
    pkg = _load_package(path)
    gl, _ = _glb_json_and_bin(pkg.glb)
    _, nodes = read_glb(pkg.glb)
    meshes = gl.get("meshes", [])
    materials = gl.get("materials", [])
    accessors = gl.get("accessors", [])
    views = gl.get("bufferViews", [])

    draw_submissions = 0
    tri_count = 0
    vertex_count = 0
    used_view_indices: set[int] = set()
    texture_bytes = 0

    for im in gl.get("images", []):
        if isinstance(im, dict) and "bufferView" in im:
            vi = int(im["bufferView"])
            texture_bytes += int(views[vi]["byteLength"])

    for node in nodes:
        node_js = gl["nodes"][node.index]
        if "mesh" not in node_js:
            continue
        mesh = meshes[node_js["mesh"]]
        prims = mesh.get("primitives", [])
        draw_submissions += len(prims)
        for p in prims:
            attrs = p.get("attributes", {})
            if "POSITION" in attrs:
                pa = accessors[attrs["POSITION"]]
                vertex_count += int(pa["count"])
                used_view_indices.add(int(pa["bufferView"]))
            if "indices" in p:
                ia = accessors[p["indices"]]
                tri_count += int(ia["count"]) // 3
                used_view_indices.add(int(ia["bufferView"]))
            else:
                tri_count += int(pa["count"]) // 3
            for key in ("NORMAL", "COLOR_0", "TEXCOORD_0"):
                if key in attrs:
                    used_view_indices.add(int(accessors[attrs[key]]["bufferView"]))

    render_memory = sum(int(views[vi]["byteLength"]) for vi in used_view_indices) + texture_bytes
    return {
        "materials": len(materials),
        "draw_submissions": draw_submissions,
        "render_memory_bytes": render_memory,
        "triangles": tri_count,
        "vertices": vertex_count,
        "texture_bytes": texture_bytes,
        "glb_bytes": len(pkg.glb),
        "package_bytes": sum(len(v) for v in pkg.members.values()),
    }


def cli_blender_parity(cli_path: str, blender_path: str) -> tuple[bool, dict[str, Any]]:
    cli = _load_package(cli_path)
    bl = _load_package(blender_path)
    cli_gl, cli_bin = _glb_json_and_bin(cli.glb)
    bl_gl, bl_bin = _glb_json_and_bin(bl.glb)
    _, cli_nodes = read_glb(cli.glb)
    _, bl_nodes = read_glb(bl.glb)

    def signature(gl: dict[str, Any], bin_chunk: bytes, nodes: list[Any]) -> dict[str, Any]:
        sig: dict[str, Any] = {}
        mats = gl.get("materials", [])
        meshes = gl.get("meshes", [])
        for n in nodes:
            njs = gl["nodes"][n.index]
            if "mesh" not in njs:
                continue
            mesh = meshes[njs["mesh"]]
            parts = []
            for p in mesh.get("primitives", []):
                attrs = p.get("attributes", {})
                mat_name = ""
                if "material" in p:
                    mat_name = mats[p["material"]].get("name", f"material:{p['material']}")
                color_hash = None
                if "COLOR_0" in attrs:
                    color_hash = hashlib.sha256(_buffer_slice(gl, bin_chunk, attrs["COLOR_0"])).hexdigest()
                parts.append({"material": mat_name, "color_sha256": color_hash, "mode": int(p.get("mode", 4))})
            sig[n.name] = parts
        return sig

    cli_sig = signature(cli_gl, cli_bin, cli_nodes)
    bl_sig = signature(bl_gl, bl_bin, bl_nodes)
    ok = cli_sig == bl_sig
    return ok, {"cli_only": sorted(set(cli_sig) - set(bl_sig)), "blender_only": sorted(set(bl_sig) - set(cli_sig)),
                "different": sorted([k for k in set(cli_sig) & set(bl_sig) if cli_sig[k] != bl_sig[k]])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g0 = sub.add_parser("g0", help="G0 flight-data equality")
    g0.add_argument("--base", required=True)
    g0.add_argument("--head", required=True)

    cid = sub.add_parser("classic-identity", help="whole-archive byte identity")
    cid.add_argument("--base", required=True)
    cid.add_argument("--head", required=True)

    md = sub.add_parser("mode-diff", help="member diff classic vs stylized")
    md.add_argument("--classic", required=True)
    md.add_argument("--stylized", required=True)

    met = sub.add_parser("metrics", help="style budget metrics")
    met.add_argument("package")

    par = sub.add_parser("parity", help="CLI vs Blender per-node material/color parity")
    par.add_argument("--cli", required=True)
    par.add_argument("--blender", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "g0":
        ok, failures = g0_check(args.base, args.head)
        print(json.dumps({"ok": ok, "failures": failures}, indent=2))
        return 0 if ok else 1
    if args.cmd == "classic-identity":
        ok, failures = classic_identity_check(args.base, args.head)
        print(json.dumps({"ok": ok, "failures": failures}, indent=2))
        return 0 if ok else 1
    if args.cmd == "mode-diff":
        print(json.dumps(mode_member_diff(args.classic, args.stylized), indent=2))
        return 0
    if args.cmd == "metrics":
        print(json.dumps(glb_metrics(args.package), indent=2))
        return 0
    if args.cmd == "parity":
        ok, details = cli_blender_parity(args.cli, args.blender)
        print(json.dumps({"ok": ok, "details": details}, indent=2))
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
