# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf

"""Pillow-free two-column compose stage: PNG codec, regions, paired report and fallback equivalence."""

from __future__ import annotations

import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO, "tools", "demo")
sys.path.insert(0, DEMO)

import png_io  # noqa: E402
import style_color  # noqa: E402
import style_compare  # noqa: E402
import style_regions  # noqa: E402
import style_sheet  # noqa: E402

HAS_PILLOW = importlib.util.find_spec("PIL") is not None
FALLBACK_TOLERANCE = 0.01
ORIGINAL_FACTORIA_CAMERAS = ("overview", "factoria-interchange", "factoria-ponds")


def regions_path(name: str) -> str:
    return os.path.join(DEMO, f"palette_regions_{name}.json")


def solid(width: int, height: int, rgb: tuple[int, int, int]) -> png_io.RgbImage:
    return png_io.RgbImage(width, height, tuple(bytes(rgb) * width for _ in range(height)))


def gradient(width: int, height: int) -> png_io.RgbImage:
    rows = (bytes((x * 7 + y * 3) % 256 for x in range(width) for _ in range(3)) for y in range(height))
    return png_io.RgbImage(width, height, tuple(rows))


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    return min((abs(p - a), a), (abs(p - b), b), (abs(p - c), c))[1]


def _filter_line(kind: int, line: bytes, prev: bytes, bpp: int) -> bytes:
    out = bytearray()
    for i, value in enumerate(line):
        left = line[i - bpp] if i >= bpp else 0
        up = prev[i]
        up_left = prev[i - bpp] if i >= bpp else 0
        predictor = (0, left, up, (left + up) // 2, _paeth(left, up, up_left))[kind]
        out.append((value - predictor) & 0xFF)
    return bytes(out)


def png_with_filter(image: png_io.RgbImage, kind: int, color_type: int = 2) -> bytes:
    """Encode ``image`` using one PNG scanline filter, optionally as RGBA with a dummy alpha channel."""
    bpp = 4 if color_type == 6 else 3
    raw = bytearray()
    prev = bytes(image.width * bpp)
    for row in image.rows:
        line = row if bpp == 3 else b"".join(row[i : i + 3] + b"\x80" for i in range(0, len(row), 3))
        raw += bytes([kind]) + _filter_line(kind, line, prev, bpp)
        prev = line

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    header = struct.pack(">IIBBBBB", image.width, image.height, 8, color_type, 0, 0, 0)
    return png_io.PNG_SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")


class PngCodecTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        image = gradient(17, 9)
        data = png_io.encode_png(image)
        self.assertTrue(data.startswith(png_io.PNG_SIGNATURE))
        self.assertEqual(png_io.decode_png(data), image)

    def test_every_filter_decodes_for_rgb_and_rgba(self) -> None:
        image = gradient(13, 6)
        for color_type in (2, 6):
            for kind in range(5):
                with self.subTest(color_type=color_type, filter=kind):
                    self.assertEqual(png_io.decode_png(png_with_filter(image, kind, color_type)), image)

    def test_rejects_non_png(self) -> None:
        with self.assertRaises(png_io.PngError):
            png_io.decode_png(b"not a png")


class ColorTests(unittest.TestCase):
    def test_ciede2000_reference_pairs(self) -> None:
        # Sharma, Wu, Dalal (2005) test data, pairs 1 and 7.
        self.assertAlmostEqual(
            style_color.delta_e2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485)), 2.0425, places=4
        )
        self.assertAlmostEqual(style_color.delta_e2000((50.0, 2.5, 0.0), (50.0, 0.0, -2.5)), 4.3065, places=4)


class RegionFileTests(unittest.TestCase):
    PINNED = {
        "munich": {
            "overview": {"roof-1": None, "wall-1": None},
            "roofs": {"roof-1": None, "wall-1": None, "roof-2": None, "wall-2": None},
            "roofscape": {"roof-1": None, "wall-1": None, "roof-2": None, "wall-2": None},
        },
        "pittsburgh": {
            "overview": {"water-open": "#6dc0e7"},
            "river-bend": {"water-open": "#6dc0e7", "water-shore": "#ceeef6"},
            "dsm-ground": {"grass-mid": "#96b671"},
        },
        "synthetic": {"top": {"grass-mid": "#96b671", "grass-light": "#b9d17a"}},
    }

    def test_pinned_region_map_is_present_with_exact_targets(self) -> None:
        for preset, cameras in self.PINNED.items():
            regions = style_regions.load_regions(regions_path(preset))
            for camera, expected in cameras.items():
                actual = {r.label: r.target_hex for r in style_regions.regions_for_camera(regions, camera)}
                self.assertEqual(actual, expected, f"{preset}/{camera}")

    def test_factoria_extends_original_swatches_with_contrast_pairs(self) -> None:
        regions = style_regions.load_regions(regions_path("factoria"))
        originals = style_regions.load_regions(regions_path("factoria_v060"))
        self.assertEqual(style_regions.swatch_regions(regions), originals)
        for camera in ("overview", "factoria-interchange"):
            style_regions.contrast_pairs(style_regions.regions_for_camera(regions, camera))
        interchange = style_regions.regions_for_camera(regions, "factoria-interchange")
        self.assertEqual(len(style_regions.contrast_pairs(interchange)), 2)

    def test_every_region_file_loads_and_pairs_per_camera(self) -> None:
        for name in ("factoria", "factoria_v060", "munich", "pittsburgh", "synthetic"):
            regions = style_regions.load_regions(regions_path(name))
            for camera in {r.camera for r in regions}:
                style_regions.contrast_pairs(style_regions.regions_for_camera(regions, camera))

    def test_duplicate_keys_and_lone_contrast_region_are_rejected(self) -> None:
        region = {"camera": "c", "label": "roof-1", "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}
        with self.assertRaises(ValueError):
            style_regions.parse_regions({"regions": [region, region]})
        with self.assertRaises(ValueError):
            style_regions.contrast_pairs(style_regions.parse_regions({"regions": [region]}))


class SheetAndReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.before = png_io.RgbImage(40, 20, tuple(bytes((200, 0, 0)) * 40 for _ in range(10)) + tuple(bytes((0, 200, 0)) * 40 for _ in range(10)))
        self.after = solid(40, 20, (0, 0, 200))
        self.regions = style_regions.parse_regions(
            {
                "regions": [
                    {"camera": "cam", "label": "grass", "target_hex": "#0000c8", "x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5},
                    {"camera": "cam", "label": "roof-1", "x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5},
                    {"camera": "cam", "label": "wall-1", "x": 0.5, "y": 0.5, "w": 0.5, "h": 0.5},
                ]
            }
        )

    def test_two_column_geometry_and_order(self) -> None:
        sheet = style_sheet.compose_two_column(self.before, self.after)
        pad, label = style_sheet.PAD, style_sheet.LABEL_HEIGHT
        self.assertEqual((sheet.width, sheet.height), (3 * pad + 80, label + 2 * pad + 20))
        row = sheet.rows[label + pad + 5]
        self.assertEqual(tuple(row[(pad + 5) * 3 : (pad + 5) * 3 + 3]), (200, 0, 0))
        after_x = 2 * pad + 40 + 5
        self.assertEqual(tuple(row[after_x * 3 : after_x * 3 + 3]), (0, 0, 200))

    def test_report_separates_swatches_from_contrast_pairs(self) -> None:
        report = style_compare.paired_report("cam", self.regions, self.before, self.after)
        (swatch,) = report["swatches"]
        self.assertEqual(swatch["label"], "grass")
        self.assertEqual(swatch["after"]["deltaE2000"], 0.0)
        self.assertLess(swatch["change"], 0)
        (pair,) = report["contrast_pairs"]
        self.assertEqual(pair["regions"], ["roof-1", "wall-1"])
        self.assertGreater(pair["before"]["deltaE2000"], 0)
        self.assertEqual(set(pair["after"]["mean_rgb"]), {"roof-1", "wall-1"})

    def test_compare_camera_writes_sheets_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            png_io.write_png(style_compare.render_path(tmp, "cam", "before"), self.before)
            png_io.write_png(style_compare.render_path(tmp, "cam", "after"), self.after)
            style_compare.compare_cameras(tmp, tmp, self.regions, ["cam"])
            self.assertEqual(
                sorted(os.listdir(tmp)),
                ["paired-cam.json", "render-cam-after.png", "render-cam-before.png", "sheet2-cam-regions.png", "sheet2-cam.png"],
            )
            with open(os.path.join(tmp, "paired-cam.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["camera"], "cam")


class NoPillowTests(unittest.TestCase):
    def test_compose_stage_never_imports_pillow(self) -> None:
        code = (
            "import sys; sys.modules['PIL'] = None\n"
            f"sys.path.insert(0, {DEMO!r})\n"
            "import style_compare, png_io, style_sheet\n"
            "img = png_io.RgbImage(2, 2, (bytes(6), bytes(6)))\n"
            "style_sheet.compose_two_column(img, img)\n"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(HAS_PILLOW, "Pillow only needed for the D187 fallback equivalence check")
class FallbackEquivalenceTests(unittest.TestCase):
    def test_original_factoria_swatches_match_pillow_fallback(self) -> None:
        import style_render_recipe as recipe

        path = regions_path("factoria_v060")
        fallback_regions = recipe._load_regions(path)
        swatches = style_regions.load_regions(path)
        with tempfile.TemporaryDirectory() as tmp:
            for camera in ORIGINAL_FACTORIA_CAMERAS:
                image = gradient(64, 36)
                png_path = os.path.join(tmp, f"{camera}.png")
                png_io.write_png(png_path, image)
                out_path = os.path.join(tmp, f"{camera}.json")
                recipe._palette_report(png_path, style_regions.regions_for_camera(fallback_regions, camera), out_path)
                with open(out_path, encoding="utf-8") as f:
                    expected = {row["label"]: row["deltaE2000"] for row in json.load(f)["regions"]}
                report = style_compare.paired_report(camera, style_regions.regions_for_camera(swatches, camera), image, image)
                for row in report["swatches"]:
                    for side in ("before", "after"):
                        self.assertAlmostEqual(row[side]["deltaE2000"], expected[row["label"]], delta=FALLBACK_TOLERANCE)

    def test_fallback_loader_ignores_contrast_regions(self) -> None:
        import style_render_recipe as recipe

        loaded = recipe._load_regions(regions_path("factoria"))
        self.assertTrue(all(r.target_hex for r in loaded))


if __name__ == "__main__":
    unittest.main()
