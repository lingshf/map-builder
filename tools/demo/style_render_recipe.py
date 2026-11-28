# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""S5 style render harness: fixed preset cameras, deterministic Cycles/EEVEE renders, contact sheets, palette ΔE2000 report."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from collections.abc import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demo_bundle as db  # noqa: E402
import style_color  # noqa: E402
import style_compare  # noqa: E402
import style_regions  # noqa: E402
from style_regions import Region  # noqa: E402


def _render(
    pkg: db.Package,
    preset: db.Preset,
    suffix: str,
    out_dir: str,
    *,
    engine: str = "CYCLES",
    samples: int = 8,
    seed: int = 1,
    denoise: bool = False,
) -> tuple[list[str], dict[str, float]]:
    import bpy
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    if engine == "BLENDER_EEVEE" and "BLENDER_EEVEE" not in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys():
        engine = "BLENDER_EEVEE_NEXT"
    scene.render.engine = engine
    if engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        scene.eevee.taa_render_samples = int(samples)
    elif engine == "CYCLES":
        scene.cycles.device = "CPU"
        scene.cycles.samples = int(samples)
        scene.cycles.use_denoising = bool(denoise)
        scene.cycles.use_adaptive_sampling = False
        scene.cycles.seed = int(seed)
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
    render_seconds: dict[str, float] = {}
    for c in preset["cameras"]:
        eye = Vector(c["eye"])
        target = Vector(c["target"])
        cam_ob.location = eye
        cam_ob.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
        cam.lens = c.get("lens_mm", 35)
        name = f"render-{c['name']}-{suffix}.png"
        scene.render.filepath = os.path.join(out_dir, name)
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        render_seconds[name] = time.perf_counter() - t0
        names.append(name)
    return names, render_seconds


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
        de = style_color.delta_e2000_rgb(mean, style_color.hex_to_rgb(r.target_hex))
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
    """Swatch regions only: the three-column report and the D187 fallback need a ``target_hex``."""
    return style_regions.swatch_regions(style_regions.load_regions(path))


def _write_reference_outputs(args: argparse.Namespace, preset: db.Preset, notes: list[str]) -> None:
    """Three-column sheets (reference | before | after) and the after-only ΔE report; needs Pillow."""
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        notes.append("Pillow not available in Blender Python; skipped contact sheets and palette reports.")
        return
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
        camera_regions = style_regions.regions_for_camera(regions, camera_name)
        if not camera_regions:
            continue
        _palette_report(
            os.path.join(args.out, f"render-{camera_name}-after.png"),
            camera_regions,
            os.path.join(args.out, f"palette-{camera_name}.json"),
        )


def _write_two_column_outputs(args: argparse.Namespace, preset: db.Preset) -> None:
    """No reference: two-column sheets and paired reports, Pillow-free, in the same process as the render."""
    style_compare.compare_cameras(
        args.out,
        args.out,
        style_regions.load_regions(args.palette_regions),
        [cam["name"] for cam in preset["cameras"]],
    )


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preset", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument(
        "--reference",
        help="reference image: three-column contact sheets (needs Pillow); without it, two-column before/after sheets",
    )
    ap.add_argument("--palette-regions", required=True, help="json file listing fixed regions (preset-scoped)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--engine", choices=("CYCLES", "BLENDER_EEVEE"), default="CYCLES")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--denoise", action="store_true", default=False)
    ap.add_argument("--max-seconds-per-output", type=float, default=120.0)
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    preset = db.load_preset(args.preset)
    before = db.read_package(args.before)
    after = db.read_package(args.after)
    _, before_seconds = _render(
        before,
        preset,
        "before",
        args.out,
        engine=args.engine,
        samples=args.samples,
        seed=args.seed,
        denoise=args.denoise,
    )
    _, after_seconds = _render(
        after,
        preset,
        "after",
        args.out,
        engine=args.engine,
        samples=args.samples,
        seed=args.seed,
        denoise=args.denoise,
    )

    timing_rows: list[dict[str, object]] = []
    for name, sec in sorted({**before_seconds, **after_seconds}.items()):
        timing_rows.append(
            {
                "file": name,
                "seconds": round(float(sec), 3),
                "within_120s": bool(sec <= float(args.max_seconds_per_output)),
            }
        )
    notes: list[str] = []
    if args.reference:
        _write_reference_outputs(args, preset, notes)
    else:
        _write_two_column_outputs(args, preset)
    with open(os.path.join(args.out, "timing.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(
            {
                "engine": args.engine,
                "samples": int(args.samples),
                "seed": int(args.seed),
                "denoise": bool(args.denoise),
                "max_seconds_per_output": float(args.max_seconds_per_output),
                "rows": timing_rows,
                "notes": notes,
            },
            f,
            indent=2,
        )
        f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]))
