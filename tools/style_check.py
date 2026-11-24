# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5 style checks: G0 flight-data equality, identity checks, and style budget metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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


# The only report drift tolerated by G0 is report.options.style. Omission is treated as "classic"
# for pre-style baselines. The value must be "classic" or "stylized" when present.
ALLOWED_REPORT_OPTIONS_STYLE = frozenset({"classic", "stylized"})


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

    for member in ("collision/map.mbcol", "collision/terrain.mbhf", "report.json"):
        if member not in base.members or member not in head.members:
            failures.append(f"{member} missing")
            continue
        if member != "report.json" and base.members.get(member) != head.members.get(member):
            failures.append(f"{member} differs")

    if base.manifest.get("name") != head.manifest.get("name"):
        failures.append("manifest.name differs (preset mismatch)")
    for key in ("georeference", "passage_probes"):
        if key not in base.manifest or key not in head.manifest:
            failures.append(f"manifest.{key} missing")

    if not _exact_equal(base.manifest.get("georeference"), head.manifest.get("georeference")):
        failures.append("manifest.georeference differs")
    if not _exact_equal(base.manifest.get("passage_probes"), head.manifest.get("passage_probes")):
        failures.append("manifest.passage_probes differs")
    if not _exact_equal(base.report.get("passage_probes_blocked", []), head.report.get("passage_probes_blocked", [])):
        failures.append("report.passage_probes_blocked differs")
    if not _exact_equal(base.report.get("passage_probes_dropped", []), head.report.get("passage_probes_dropped", [])):
        failures.append("report.passage_probes_dropped differs")
    if not _exact_equal(_normalize_report_for_g0(base.report), _normalize_report_for_g0(head.report)):
        failures.append("report.json non-style keys differ")

    return not failures, failures


def _normalize_report_for_g0(report: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    options = report.get("options")
    if options is not None:
        if not isinstance(options, dict):
            normalized["options"] = options
        else:
            style = options.get("style", "classic")
            if style is None:
                style = "classic"
            if not isinstance(style, str) or style not in ALLOWED_REPORT_OPTIONS_STYLE:
                normalized["options.style"] = style
            keep_options = {k: v for k, v in options.items() if k != "style"}
            if keep_options:
                normalized["options"] = keep_options
    for key, value in report.items():
        if key == "options":
            continue
        normalized[key] = value
    return normalized


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

    def signature(gl: dict[str, Any], bin_chunk: bytes, nodes: list[Any]) -> list[dict[str, Any]]:
        sig: list[dict[str, Any]] = []
        mats = gl.get("materials", [])
        meshes = gl.get("meshes", [])
        _assert_unique_identity(
            [(_identity_name(m.get("name"), i, "material"), _mb_id_of(m)) for i, m in enumerate(mats) if isinstance(m, dict)],
            "material identity",
        )
        _assert_unique_identity(
            [(str(gl["nodes"][n.index].get("name", n.name)), _mb_id_of(gl["nodes"][n.index])) for n in nodes if "mesh" in gl["nodes"][n.index]],
            "node identity",
        )
        material_payload_by_index: list[dict[str, Any]] = []
        for i, m in enumerate(mats):
            pbr = m.get("pbrMetallicRoughness", {}) if isinstance(m, dict) else {}
            mat_name = _identity_name(m.get("name") if isinstance(m, dict) else None, i, "material")
            material_payload_by_index.append(
                {
                "name": mat_name,
                "mb_id": _mb_id_of(m),
                "baseColorFactor": pbr.get("baseColorFactor"),
                "metallicFactor": pbr.get("metallicFactor"),
                "roughnessFactor": pbr.get("roughnessFactor"),
                "hasBaseColorTexture": isinstance(pbr, dict) and "baseColorTexture" in pbr,
                }
            )
        for n in nodes:
            njs = gl["nodes"][n.index]
            if "mesh" not in njs:
                continue
            mesh = meshes[njs["mesh"]]
            node_name = _identity_name(njs.get("name"), n.index, "node")
            node_mb_id = _mb_id_of(njs)
            for p in mesh.get("primitives", []):
                attrs = p.get("attributes", {})
                material_name = None
                material_mb_id = None
                material_payload = None
                if "material" in p:
                    mat_idx = int(p["material"])
                    if not (0 <= mat_idx < len(material_payload_by_index)):
                        raise ValueError(f"primitive references invalid material index {mat_idx}")
                    material_payload = material_payload_by_index[mat_idx]
                    material_name = str(material_payload["name"])
                    material_mb_id = material_payload["mb_id"]
                color_hash = None
                if "COLOR_0" in attrs:
                    color_hash = hashlib.sha256(_buffer_slice(gl, bin_chunk, attrs["COLOR_0"])).hexdigest()
                sig.append(
                    {
                        "node_name": node_name,
                        "node_mb_id": node_mb_id,
                        "primitive_mb_id": _mb_id_of(p),
                        "material_name": material_name,
                        "material_mb_id": material_mb_id,
                        "material_payload": material_payload,
                        "color_sha256": color_hash,
                        "mode": int(p.get("mode", 4)),
                    }
                )
        return sorted(
            sig,
            key=lambda x: (
                str(x.get("node_name", "")),
                str(x.get("node_mb_id", "")),
                str(x.get("primitive_mb_id", "")),
                str(x.get("material_name", "")),
                str(x.get("material_mb_id", "")),
                str(x.get("color_sha256", "")),
                int(x.get("mode", 0)),
            ),
        )

    try:
        cli_sig = signature(cli_gl, cli_bin, cli_nodes)
        bl_sig = signature(bl_gl, bl_bin, bl_nodes)
    except ValueError as e:
        return False, {"error": str(e)}
    ok = cli_sig == bl_sig
    if ok:
        return True, {"different": [], "cli_count": len(cli_sig), "blender_count": len(bl_sig)}
    cli_only = [entry for entry in cli_sig if entry not in bl_sig]
    bl_only = [entry for entry in bl_sig if entry not in cli_sig]
    return False, {"cli_only": cli_only[:20], "blender_only": bl_only[:20], "cli_count": len(cli_sig), "blender_count": len(bl_sig)}


def _mb_id_of(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    extras = item.get("extras")
    if not isinstance(extras, dict):
        return None
    mb_id = extras.get("mb_id")
    return str(mb_id) if mb_id is not None else None


def _identity_name(name: Any, index: int, prefix: str) -> str:
    if isinstance(name, str) and name:
        return name
    return f"{prefix}:{index}"


def _assert_unique_identity(identity_pairs: list[tuple[str, str | None]], label: str) -> None:
    seen: set[tuple[str, str | None]] = set()
    duplicates: set[tuple[str, str | None]] = set()
    for pair in identity_pairs:
        if pair in seen:
            duplicates.add(pair)
        else:
            seen.add(pair)
    if duplicates:
        sample = ", ".join([f"{name}/{mb_id}" for name, mb_id in sorted(duplicates)[:5]])
        raise ValueError(f"duplicate {label} detected: {sample}")


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    c = hex_color.strip().lstrip("#")
    if len(c) != 6:
        raise ValueError(f"invalid hex color: {hex_color}")
    return (float(int(c[0:2], 16)), float(int(c[2:4], 16)), float(int(c[4:6], 16)))


def _srgb_to_lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    def to_linear(c: float) -> float:
        x = c / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = (to_linear(rgb[0]), to_linear(rgb[1]), to_linear(rgb[2]))
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    xr, yr, zr = x / 0.95047, y / 1.0, z / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = f(xr), f(yr), f(zr)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _delta_e2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c1 = math.sqrt(a1 * a1 + b1 * b1)
    c2 = math.sqrt(a2 * a2 + b2 * b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt((c_bar**7) / (c_bar**7 + 25**7))) if c_bar > 0 else 0.0
    a1p = (1 + g) * a1
    a2p = (1 + g) * a2
    c1p = math.sqrt(a1p * a1p + b1 * b1)
    c2p = math.sqrt(a2p * a2p + b2 * b2)

    def hp(a: float, b: float) -> float:
        if a == 0 and b == 0:
            return 0.0
        ang = math.degrees(math.atan2(b, a))
        return ang + 360 if ang < 0 else ang

    h1p = hp(a1p, b1)
    h2p = hp(a2p, b2)
    dlp = l2 - l1
    dcp = c2p - c1p
    dhp = 0.0
    if c1p * c2p != 0:
        dh = h2p - h1p
        if abs(dh) <= 180:
            dhp = dh
        elif dh > 180:
            dhp = dh - 360
        else:
            dhp = dh + 360
    dhp_rad = math.radians(dhp / 2)
    dh_term = 2 * math.sqrt(c1p * c2p) * math.sin(dhp_rad)
    l_bar = (l1 + l2) / 2
    c_bar_p = (c1p + c2p) / 2
    h_bar = h1p + h2p
    if c1p * c2p != 0:
        if abs(h1p - h2p) <= 180:
            h_bar = (h1p + h2p) / 2
        elif h1p + h2p < 360:
            h_bar = (h1p + h2p + 360) / 2
        else:
            h_bar = (h1p + h2p - 360) / 2
    t = (
        1
        - 0.17 * math.cos(math.radians(h_bar - 30))
        + 0.24 * math.cos(math.radians(2 * h_bar))
        + 0.32 * math.cos(math.radians(3 * h_bar + 6))
        - 0.20 * math.cos(math.radians(4 * h_bar - 63))
    )
    sl = 1 + (0.015 * ((l_bar - 50) ** 2)) / math.sqrt(20 + (l_bar - 50) ** 2)
    sc = 1 + 0.045 * c_bar_p
    sh = 1 + 0.015 * c_bar_p * t
    dtheta = 30 * math.exp(-(((h_bar - 275) / 25) ** 2))
    rc = 2 * math.sqrt((c_bar_p**7) / (c_bar_p**7 + 25**7)) if c_bar_p > 0 else 0.0
    rt = -math.sin(math.radians(2 * dtheta)) * rc
    return math.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dh_term / sh) ** 2 + rt * (dcp / sc) * (dh_term / sh))


def palette_regions(image_path: str, regions_path: str) -> dict[str, Any]:
    from PIL import Image

    with open(regions_path, "r", encoding="utf-8") as f:
        regions_doc = json.load(f)
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    rows: list[dict[str, Any]] = []
    for raw in regions_doc.get("regions", []):
        x = float(raw["x"])
        y = float(raw["y"])
        rw = float(raw["w"])
        rh = float(raw["h"])
        x0 = max(0, min(w - 1, int(x * w)))
        y0 = max(0, min(h - 1, int(y * h)))
        x1 = max(x0 + 1, min(w, int((x + rw) * w)))
        y1 = max(y0 + 1, min(h, int((y + rh) * h)))
        crop = img.crop((x0, y0, x1, y1))
        px = list(crop.getdata())
        mean = tuple(sum(p[i] for p in px) / len(px) for i in range(3))
        target = _hex_to_rgb(str(raw["target_hex"]))
        de = _delta_e2000(_srgb_to_lab(mean), _srgb_to_lab(target))
        rows.append(
            {
                "camera": raw.get("camera"),
                "label": raw.get("label"),
                "target_hex": raw.get("target_hex"),
                "mean_rgb": [round(mean[0], 1), round(mean[1], 1), round(mean[2], 1)],
                "deltaE2000": round(de, 2),
                "flag_over_15": de > 15.0,
            }
        )
    return {"regions": rows}


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

    pal = sub.add_parser("palette-regions", help="palette ΔE2000 report for fixed screen regions")
    pal.add_argument("--image", required=True)
    pal.add_argument("--regions", required=True)
    pal.add_argument("--output")

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
    if args.cmd == "palette-regions":
        data = palette_regions(args.image, args.regions)
        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
        print(json.dumps(data, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
