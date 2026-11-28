# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Two-column before/after sheets without a reference image (no Pillow, no bpy)."""

from __future__ import annotations

from collections.abc import Sequence

from png_io import RGB_CHANNELS, RgbImage
from style_regions import Region

PAD = 12
LABEL_HEIGHT = 28
BACKGROUND = (28, 30, 36)
LABEL_COLOR = (235, 235, 235)
OUTLINE_COLOR = (255, 0, 255)
OUTLINE_GAP = 2
TEXT_SCALE = 2

# 5x7 glyphs, one string per pixel row, for the letters the column labels use.
GLYPHS: dict[str, tuple[str, ...]] = {
    "a": (".....", ".....", ".###.", "....#", ".####", "#...#", ".####"),
    "b": ("#....", "#....", "####.", "#...#", "#...#", "#...#", "####."),
    "e": (".....", ".....", ".###.", "#...#", "#####", "#....", ".###."),
    "f": ("..##.", ".#...", "####.", ".#...", ".#...", ".#...", ".#..."),
    "o": (".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."),
    "r": (".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."),
    "t": (".#...", ".#...", "####.", ".#...", ".#...", ".#..#", "..##."),
}
GLYPH_ADVANCE = 6


class Canvas:
    """Mutable RGB pixel grid."""

    def __init__(self, width: int, height: int, fill: tuple[int, int, int]) -> None:
        self.width = width
        self.height = height
        self.rows = [bytearray(bytes(fill) * width) for _ in range(height)]

    def paste(self, image: RgbImage, left: int, top: int) -> None:
        start = left * RGB_CHANNELS
        for y, row in enumerate(image.rows):
            self.rows[top + y][start : start + len(row)] = row

    def fill_rect(self, left: int, top: int, width: int, height: int, color: tuple[int, int, int]) -> None:
        left, top = max(0, left), max(0, top)
        right, bottom = min(self.width, left + width), min(self.height, top + height)
        run = bytes(color) * max(0, right - left)
        for y in range(top, bottom):
            self.rows[y][left * RGB_CHANNELS : right * RGB_CHANNELS] = run

    def outline_rect(self, left: int, top: int, width: int, height: int, color: tuple[int, int, int]) -> None:
        self.fill_rect(left, top, width, 1, color)
        self.fill_rect(left, top + height - 1, width, 1, color)
        self.fill_rect(left, top, 1, height, color)
        self.fill_rect(left + width - 1, top, 1, height, color)

    def draw_text(self, text: str, left: int, top: int, color: tuple[int, int, int]) -> None:
        for index, char in enumerate(text):
            glyph = GLYPHS[char]
            origin = left + index * GLYPH_ADVANCE * TEXT_SCALE
            for gy, glyph_row in enumerate(glyph):
                for gx, cell in enumerate(glyph_row):
                    if cell == "#":
                        self.fill_rect(origin + gx * TEXT_SCALE, top + gy * TEXT_SCALE, TEXT_SCALE, TEXT_SCALE, color)

    def to_image(self) -> RgbImage:
        return RgbImage(self.width, self.height, tuple(bytes(row) for row in self.rows))


def region_pixel_box(region: Region, width: int, height: int) -> tuple[int, int, int, int]:
    """Half-open ``(x0, y0, x1, y1)`` pixel box, at least one pixel in each direction."""
    x0 = max(0, min(width - 1, int(region.x * width)))
    y0 = max(0, min(height - 1, int(region.y * height)))
    x1 = max(x0 + 1, min(width, int((region.x + region.w) * width)))
    y1 = max(y0 + 1, min(height, int((region.y + region.h) * height)))
    return x0, y0, x1, y1


def _draw_region_outlines(canvas: Canvas, regions: Sequence[Region], left: int, top: int, image: RgbImage) -> None:
    for region in regions:
        x0, y0, x1, y1 = region_pixel_box(region, image.width, image.height)
        canvas.outline_rect(
            left + x0 - OUTLINE_GAP,
            top + y0 - OUTLINE_GAP,
            x1 - x0 + 2 * OUTLINE_GAP,
            y1 - y0 + 2 * OUTLINE_GAP,
            OUTLINE_COLOR,
        )


def compose_two_column(before: RgbImage, after: RgbImage, outlined_regions: Sequence[Region] = ()) -> RgbImage:
    """Left column ``before``, right column ``after``; regions are outlined on both when given."""
    if (before.width, before.height) != (after.width, after.height):
        raise ValueError("before and after renders must have the same size")
    canvas = Canvas(
        before.width * 2 + PAD * 3,
        before.height + LABEL_HEIGHT + PAD * 2,
        BACKGROUND,
    )
    for column, (label, image) in enumerate((("before", before), ("after", after))):
        left = PAD + column * (before.width + PAD)
        top = PAD + LABEL_HEIGHT
        canvas.draw_text(label, left, PAD, LABEL_COLOR)
        canvas.paste(image, left, top)
        _draw_region_outlines(canvas, outlined_regions, left, top, image)
    return canvas.to_image()
