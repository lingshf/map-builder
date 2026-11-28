# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""Compose and report stage of the style recipe: two-column before/after sheets and paired ΔE2000 reports.

Reads ``render-<camera>-before.png`` and ``render-<camera>-after.png`` written by the render stage. Needs neither
Blender nor Pillow, so it runs under plain Python and inside Blender's Python alike.

    py -3.12 tools\\demo\\style_compare.py --preset tools\\demo\\presets\\synthetic.json ^
        --render-dir out\\synthetic --regions tools\\demo\\palette_regions_synthetic.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import png_io  # noqa: E402
import style_color  # noqa: E402
import style_regions  # noqa: E402
import style_sheet  # noqa: E402
from png_io import RGB_CHANNELS, RgbImage  # noqa: E402
from style_regions import Region  # noqa: E402

MEAN_RGB_DECIMALS = 1
DELTA_E_DECIMALS = 2


def render_path(render_dir: str, camera: str, side: str) -> str:
    return os.path.join(render_dir, f"render-{camera}-{side}.png")


def region_mean_rgb(image: RgbImage, region: Region) -> style_color.Rgb:
    x0, y0, x1, y1 = style_sheet.region_pixel_box(region, image.width, image.height)
    totals = [0, 0, 0]
    for row in image.rows[y0:y1]:
        span = row[x0 * RGB_CHANNELS : x1 * RGB_CHANNELS]
        for channel in range(RGB_CHANNELS):
            totals[channel] += sum(span[channel::RGB_CHANNELS])
    count = (x1 - x0) * (y1 - y0)
    return (totals[0] / count, totals[1] / count, totals[2] / count)


def _round_rgb(rgb: style_color.Rgb) -> list[float]:
    return [round(c, MEAN_RGB_DECIMALS) for c in rgb]


def _swatch_row(region: Region, before: RgbImage, after: RgbImage) -> dict[str, object]:
    target = style_color.hex_to_rgb(region.target_hex)
    row: dict[str, object] = {"label": region.label, "target_hex": region.target_hex}
    delta_e: dict[str, float] = {}
    for side, image in (("before", before), ("after", after)):
        mean = region_mean_rgb(image, region)
        delta_e[side] = style_color.delta_e2000_rgb(mean, target)
        row[side] = {"mean_rgb": _round_rgb(mean), "deltaE2000": round(delta_e[side], DELTA_E_DECIMALS)}
    row["change"] = round(delta_e["after"] - delta_e["before"], DELTA_E_DECIMALS)
    return row


def _contrast_row(pair: tuple[Region, Region], before: RgbImage, after: RgbImage) -> dict[str, object]:
    row: dict[str, object] = {"regions": [r.label for r in pair]}
    delta_e: dict[str, float] = {}
    for side, image in (("before", before), ("after", after)):
        means = [region_mean_rgb(image, r) for r in pair]
        delta_e[side] = style_color.delta_e2000_rgb(*means)
        row[side] = {
            "mean_rgb": {r.label: _round_rgb(m) for r, m in zip(pair, means)},
            "deltaE2000": round(delta_e[side], DELTA_E_DECIMALS),
        }
    row["change"] = round(delta_e["after"] - delta_e["before"], DELTA_E_DECIMALS)
    return row


def paired_report(camera: str, regions: Sequence[Region], before: RgbImage, after: RgbImage) -> dict[str, object]:
    """Swatch rows (ΔE to the target) and contrast pairs (ΔE between two regions of one image), before and after."""
    return {
        "camera": camera,
        "swatches": [_swatch_row(r, before, after) for r in style_regions.swatch_regions(list(regions))],
        "contrast_pairs": [_contrast_row(p, before, after) for p in style_regions.contrast_pairs(list(regions))],
    }


def _write_json(path: str, data: object) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def compare_camera(render_dir: str, out_dir: str, regions: Sequence[Region], camera: str) -> None:
    before = png_io.read_png(render_path(render_dir, camera, "before"))
    after = png_io.read_png(render_path(render_dir, camera, "after"))
    png_io.write_png(os.path.join(out_dir, f"sheet2-{camera}.png"), style_sheet.compose_two_column(before, after))
    camera_regions = style_regions.regions_for_camera(list(regions), camera)
    if not camera_regions:
        return
    outlined = style_sheet.compose_two_column(before, after, camera_regions)
    png_io.write_png(os.path.join(out_dir, f"sheet2-{camera}-regions.png"), outlined)
    _write_json(os.path.join(out_dir, f"paired-{camera}.json"), paired_report(camera, camera_regions, before, after))


def compare_cameras(
    render_dir: str, out_dir: str, regions: Sequence[Region], cameras: Sequence[str], workers: int = 1
) -> None:
    """``workers > 1`` fans cameras out to processes; use 1 inside Blender, where a child process would be Blender."""
    os.makedirs(out_dir, exist_ok=True)
    job = partial(compare_camera, render_dir, out_dir, regions)
    if workers <= 1 or len(cameras) <= 1:
        for camera in cameras:
            job(camera)
        return
    with ProcessPoolExecutor(max_workers=workers) as pool:
        list(pool.map(job, cameras))


def preset_camera_names(preset_path: str) -> list[str]:
    with open(preset_path, "r", encoding="utf-8") as f:
        return [c["name"] for c in json.load(f)["cameras"]]


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", required=True, help="preset json; its cameras name the renders to compose")
    ap.add_argument("--render-dir", required=True, help="folder with render-<camera>-before/after.png")
    ap.add_argument("--regions", required=True, help="preset-scoped palette regions json")
    ap.add_argument("--out", help="output folder (default: --render-dir)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args(argv)

    compare_cameras(
        args.render_dir,
        args.out or args.render_dir,
        style_regions.load_regions(args.regions),
        preset_camera_names(args.preset),
        workers=args.workers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
