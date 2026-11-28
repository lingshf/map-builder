# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Standard-library PNG reader and writer (zlib + struct only, no Pillow) for the style demo tools.

Reads 8-bit non-interlaced RGB or RGBA PNGs (what Blender writes) and drops alpha, like Pillow's
``convert("RGB")``. Writes 8-bit RGB PNGs.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import accumulate
from operator import add

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS_BY_COLOR_TYPE = {2: 3, 6: 4}
RGB_CHANNELS = 3
BYTE_MASK = 0xFF
ENCODE_COMPRESSION_LEVEL = 3

FILTER_NONE, FILTER_SUB, FILTER_UP, FILTER_AVERAGE, FILTER_PAETH = range(5)


class PngError(ValueError):
    """The input is not a PNG this module can read."""


@dataclass(frozen=True)
class RgbImage:
    """Image as scanlines of packed ``RGBRGB...`` bytes."""

    width: int
    height: int
    rows: tuple[bytes, ...]

    def __post_init__(self) -> None:
        if len(self.rows) != self.height or any(len(row) != self.width * RGB_CHANNELS for row in self.rows):
            raise ValueError("rows do not match width and height")


def _chunks(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    if data[: len(PNG_SIGNATURE)] != PNG_SIGNATURE:
        raise PngError("missing PNG signature")
    pos = len(PNG_SIGNATURE)
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        yield kind, data[pos + 8 : pos + 8 + length]
        pos += length + 12


def _wrap8(values: Iterable[int]) -> bytes:
    return bytes(map(BYTE_MASK.__and__, values))


def _paeth_predictor(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    d_left, d_up, d_up_left = abs(estimate - left), abs(estimate - up), abs(estimate - up_left)
    if d_left <= d_up and d_left <= d_up_left:
        return left
    return up if d_up <= d_up_left else up_left


def _unfilter_sub(line: bytes, bpp: int) -> bytes:
    out = bytearray(len(line))
    for channel in range(bpp):
        out[channel::bpp] = _wrap8(accumulate(line[channel::bpp]))
    return bytes(out)


def _unfilter_up(line: bytes, prev: bytes) -> bytes:
    return _wrap8(map(add, line, prev))


def _unfilter_sequential(kind: int, line: bytes, prev: bytes, bpp: int) -> bytes:
    """Average and Paeth read the already-decoded left neighbour, so they cannot be vectorised."""
    out = bytearray(line)
    for i in range(len(out)):
        left = out[i - bpp] if i >= bpp else 0
        up = prev[i]
        if kind == FILTER_AVERAGE:
            predicted = (left + up) >> 1
        else:
            predicted = _paeth_predictor(left, up, prev[i - bpp] if i >= bpp else 0)
        out[i] = (out[i] + predicted) & BYTE_MASK
    return bytes(out)


def _unfilter(kind: int, line: bytes, prev: bytes, bpp: int) -> bytes:
    if kind == FILTER_NONE:
        return line
    if kind == FILTER_SUB:
        return _unfilter_sub(line, bpp)
    if kind == FILTER_UP:
        return _unfilter_up(line, prev)
    if kind in (FILTER_AVERAGE, FILTER_PAETH):
        return _unfilter_sequential(kind, line, prev, bpp)
    raise PngError(f"unknown scanline filter {kind}")


def _to_rgb(line: bytes, channels: int) -> bytes:
    if channels == RGB_CHANNELS:
        return line
    out = bytearray(len(line) // channels * RGB_CHANNELS)
    for channel in range(RGB_CHANNELS):
        out[channel::RGB_CHANNELS] = line[channel::channels]
    return bytes(out)


def decode_png(data: bytes) -> RgbImage:
    header = None
    compressed = bytearray()
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            compressed += body
    if header is None:
        raise PngError("missing IHDR")
    width, height, depth, color_type, _compression, _filter_method, interlace = header
    if depth != 8 or color_type not in CHANNELS_BY_COLOR_TYPE or interlace != 0:
        raise PngError("only 8-bit non-interlaced RGB/RGBA PNGs are supported")
    channels = CHANNELS_BY_COLOR_TYPE[color_type]
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    if len(raw) != height * (stride + 1):
        raise PngError("image data length does not match the header")

    rows: list[bytes] = []
    prev = bytes(stride)
    for y in range(height):
        start = y * (stride + 1)
        prev = _unfilter(raw[start], raw[start + 1 : start + 1 + stride], prev, channels)
        rows.append(_to_rgb(prev, channels))
    return RgbImage(width, height, tuple(rows))


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def encode_png(image: RgbImage) -> bytes:
    raw = b"".join(bytes([FILTER_NONE]) + row for row in image.rows)
    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, ENCODE_COMPRESSION_LEVEL))
        + _chunk(b"IEND", b"")
    )


def read_png(path: str) -> RgbImage:
    with open(path, "rb") as f:
        return decode_png(f.read())


def write_png(path: str, image: RgbImage) -> None:
    with open(path, "wb") as f:
        f.write(encode_png(image))
