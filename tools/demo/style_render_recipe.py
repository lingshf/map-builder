# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5 style render harness: fixed preset cameras, Blender EEVEE, contact sheets, palette ΔE2000 report."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demo_bundle as db  # noqa: E402


@dataclass(frozen=True)
class Region:
    camera: str
    label: str
    target_hex: str
    x: float
    y: float
    w: float
    h: float


def _srgb_to_lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    def to_linear(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = [to_linear(c / 255.0) for c in rgb]
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    xr, yr, zr = x / 0.95047, y / 1.0, z / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = f(xr), f(yr), f(zr)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _delta_e2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    # CIEDE2000 with kL=kC=kH=1
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


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    c = hex_color.strip().lstrip("#")
    if len(c) != 6:
        raise ValueError(f"invalid hex color: {hex_color}")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _render(pkg: db.Package, preset: db.Preset, suffix: str, out_dir: str, engine: str = "BLENDER_EEVEE") -> list[str]:
    import bpy
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    if engine == "BLENDER_EEVEE" and "BLENDER_EEVEE" not in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys():
        engine = "BLENDER_EEVEE_NEXT"
    scene.render.engine = engine
    if engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        scene.eevee.taa_render_samples = db.SAMPLES
    scene.render.resolution_x, scene.render.resolution_y = db.RENDER_SIZE
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"

    world = bpy.data.worlds.new("style-world")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.63, 0.77, 0.91, 1.0)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs[0])

    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 2.0
    sun_ob = bpy.data.objects.new("sun", sun)
    scene.collection.objects.link(sun_ob)
    sun_ob.rotation_euler = (math.radians(40), 0, math.radians(150))

    with tempfile.TemporaryDirectory() as td:
        glb = os.path.join(td, "map.glb")
        with open(glb, "wb") as f:
            f.write(pkg["glb"])
        bpy.ops.import_scene.gltf(filepath=glb)

    cam = bpy.data.cameras.new("cam")
    cam_ob = bpy.data.objects.new("cam", cam)
    scene.collection.objects.link(cam_ob)
    scene.camera = cam_ob
    cam.clip_end = 5000

    names: list[str] = []
    for c in preset["cameras"]:
        eye = Vector(c["eye"])
        target = Vector(c["target"])
        cam_ob.location = eye
        cam_ob.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
        cam.lens = c.get("lens_mm", 35)
        name = f"render-{c['name']}-{suffix}.png"
        scene.render.filepath = os.path.join(out_dir, name)
        bpy.ops.render.render(write_still=True)
        names.append(name)
    return names


def _make_sheet(reference_path: str, base_path: str, head_path: str, out_path: str) -> None:
    from PIL import Image, ImageDraw

    ref = Image.open(reference_path).convert("RGB")
    base = Image.open(base_path).convert("RGB")
    head = Image.open(head_path).convert("RGB")
    if ref.size != base.size:
        ref = ref.resize(base.size, Image.Resampling.LANCZOS)
    if head.size != base.size:
        head = head.resize(base.size, Image.Resampling.LANCZOS)
    w, h = base.size
    pad = 8
    label_h = 28
    out = Image.new("RGB", (w * 3 + pad * 4, h + label_h + pad * 2), (28, 30, 36))
    d = ImageDraw.Draw(out)
    x = pad
    for label, img in (("reference", ref), ("base", base), ("head", head)):
        out.paste(img, (x, pad + label_h))
        d.text((x + 6, pad + 6), label, fill=(220, 230, 240))
        x += w + pad
    out.save(out_path)


def _palette_report(image_path: str, regions: list[Region], out_path: str) -> None:
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    rows: list[dict[str, object]] = []
    for r in regions:
        x0 = max(0, min(w - 1, int(r.x * w)))
        y0 = max(0, min(h - 1, int(r.y * h)))
        x1 = max(x0 + 1, min(w, int((r.x + r.w) * w)))
        y1 = max(y0 + 1, min(h, int((r.y + r.h) * h)))
        crop = img.crop((x0, y0, x1, y1))
        px = list(crop.getdata())
        mean = tuple(sum(p[i] for p in px) / len(px) for i in range(3))
        de = _delta_e2000(_srgb_to_lab(mean), _srgb_to_lab(_hex_to_rgb(r.target_hex)))
        rows.append(
            {
                "camera": r.camera,
                "label": r.label,
                "target_hex": r.target_hex,
                "mean_rgb": [round(c, 1) for c in mean],
                "deltaE2000": round(de, 2),
                "flag_over_15": de > 15.0,
            }
        )
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"regions": rows}, f, indent=2)
        f.write("\n")


def _load_regions(path: str) -> list[Region]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out: list[Region] = []
    for r in raw.get("regions", []):
        out.append(
            Region(
                camera=str(r["camera"]),
                label=str(r["label"]),
                target_hex=str(r["target_hex"]),
                x=float(r["x"]),
                y=float(r["y"]),
                w=float(r["w"]),
                h=float(r["h"]),
            )
        )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preset", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--reference", required=True, help="reference image to place on contact sheets")
    ap.add_argument("--palette-regions", required=True, help="json file listing fixed regions and target colors")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    preset = db.load_preset(args.preset)
    before = db.read_package(args.before)
    after = db.read_package(args.after)
    _render(before, preset, "before", args.out, engine="BLENDER_EEVEE")
    _render(after, preset, "after", args.out, engine="BLENDER_EEVEE")

    for cam in preset["cameras"]:
        name = cam["name"]
        _make_sheet(
            args.reference,
            os.path.join(args.out, f"render-{name}-before.png"),
            os.path.join(args.out, f"render-{name}-after.png"),
            os.path.join(args.out, f"contact-sheet-{name}.png"),
        )

    regions = _load_regions(args.palette_regions)
    for cam in preset["cameras"]:
        camera_name = cam["name"]
        camera_regions = [r for r in regions if r.camera == camera_name]
        if not camera_regions:
            continue
        _palette_report(
            os.path.join(args.out, f"render-{camera_name}-after.png"),
            camera_regions,
            os.path.join(args.out, f"palette-{camera_name}.json"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]))
