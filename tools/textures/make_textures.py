# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Deterministic generator of the map-builder procedural texture set (S3-TEX-ASSETS, D56).

    python -m tools.textures.make_textures            # rewrite map_builder/assets/textures/
    python -m tools.textures.make_textures --check    # exit 1 if the committed files differ

Every image is our own work: seeded value noise and simple geometry, no photographs, no map or
Google imagery (D2). The output is dedicated to the public domain under CC0 1.0.

The bytes are reproducible on any platform and Python >= 3.11:

* pixels use only ``random.Random(int).random()`` and + - * / on floats (no libm calls), and are
  rounded to integers;
* PNGs are written with pure Python: one Paeth-filtered RGB image, compressed by our own
  Huffman-only deflate encoder. ``zlib`` is used only for CRC-32 and Adler-32, so the output
  does not depend on which zlib (or zlib-ng) Python was built with.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import os
import random
import struct
import sys
import zlib
from collections.abc import Callable, Iterable, Sequence

Rgb = tuple[int, ...]             # (r, g, b), 0..255
Rows = list[list[Rgb]]            # image rows of 8-bit RGB pixels
Field = list[list[float]]         # a size x size scalar field
Color = tuple[float, ...]

SIZE = 256
SEED = 56   # D56
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "map_builder", "assets", "textures")
LICENSE_NAME = "LICENSE-textures.txt"
CC0_TEXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CC0-1.0.txt")
COMMAND = "python -m tools.textures.make_textures"


# ---------------------------------------------------------------- noise helpers (tileable)

def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def value_noise(rng: random.Random, cells: int, size: int = SIZE) -> Field:
    """Periodic value noise in [0, 1]: a ``cells`` x ``cells`` random lattice, smoothstep-blended.
    It wraps at the image edges, so the result tiles."""
    lat = [[rng.random() for _ in range(cells)] for _ in range(cells)]
    step = size // cells
    i0 = [x // step for x in range(size)]
    i1 = [(i + 1) % cells for i in i0]
    tx = [_smooth((x % step) / step) for x in range(size)]
    xs = list(zip(i0, i1, tx))
    out = []
    for y in range(size):
        a, b = lat[y // step], lat[(y // step + 1) % cells]
        t = _smooth((y % step) / step)
        r = [p + (q - p) * t for p, q in zip(a, b)]
        out.append([r[j] + (r[k] - r[j]) * s for j, k, s in xs])
    return out


def fbm(rng: random.Random, octaves: Sequence[tuple[int, float]], size: int = SIZE) -> Field:
    """Weighted sum of value-noise octaves ``[(cells, weight), ...]``, normalised to [0, 1]."""
    total = sum(w for _, w in octaves)
    acc = [[0.0] * size for _ in range(size)]
    for cells, w in octaves:
        n = value_noise(rng, cells, size)
        k = w / total
        acc = [[a + v * k for a, v in zip(ra, rn)] for ra, rn in zip(acc, n)]
    return acc


def white(rng: random.Random, size: int = SIZE) -> Field:
    return [[rng.random() for _ in range(size)] for _ in range(size)]


def _clamp(v: float) -> int:
    v = int(v + 0.5) if v > 0 else 0
    return 255 if v > 255 else v


def _mix(c0: Color, c1: Color, t: float) -> Color:
    return tuple(a + (b - a) * t for a, b in zip(c0, c1))


# ---------------------------------------------------------------- the textures (RGB rows)

def facade(rng: random.Random) -> Rows:
    """Plaster with a window-grid hint: one window per 3 m x 3 m tile."""
    low, grain = fbm(rng, [(4, 3), (16, 2), (64, 1)]), white(rng)
    base: Color
    base, frame, glass_top, glass_bot = (214, 204, 186), (236, 234, 228), (88, 100, 112), (58, 68, 80)
    x0, x1, y0, y1, fw = 80, 176, 60, 196, 7
    rows: Rows = []
    for y in range(SIZE):
        row: list[Rgb] = []
        for x in range(SIZE):
            c: Color
            if x0 <= x < x1 and y0 <= y < y1:
                if x < x0 + fw or x >= x1 - fw or y < y0 + fw or y >= y1 - fw or abs(x - 128) < 3:
                    c = frame
                else:
                    c = _mix(glass_top, glass_bot, (y - y0) / (y1 - y0))
                f = 0.97 + 0.06 * low[y][x]
            elif x0 - 6 <= x < x1 + 6 and y1 <= y < y1 + 8:   # sill
                c, f = (190, 186, 178), 0.95 + 0.05 * grain[y][x]
            else:
                c, f = base, 0.88 + 0.16 * low[y][x] + 0.05 * (grain[y][x] - 0.5)
            row.append(tuple(_clamp(v * f) for v in c))
        rows.append(row)
    return rows


def roof_tiles(rng: random.Random) -> Rows:
    """Clay roof tiles: 8 courses of 8 tiles per 2 m tile, alternate courses offset by half a tile."""
    tone = [[0.85 + 0.25 * rng.random() for _ in range(8)] for _ in range(8)]
    low, grain = fbm(rng, [(8, 2), (32, 1)]), white(rng)
    base, gap = (172, 78, 54), (70, 34, 26)
    rows = []
    for y in range(SIZE):
        course, ty = y // 32, (y % 32) / 32.0
        shift = 16 if course % 2 else 0
        row = []
        for x in range(SIZE):
            xx = (x + shift) % SIZE
            col, tx = xx // 32, (xx % 32) / 32.0
            if ty > 0.9 or tx < 0.04:
                c, f = gap, 0.9 + 0.2 * grain[y][x]
            else:
                edge = 4.0 * tx * (1.0 - tx)              # rounded tile profile
                f = tone[course][col] * (0.78 + 0.22 * edge) * (1.0 - 0.25 * ty * ty)
                f *= 0.92 + 0.12 * low[y][x] + 0.06 * (grain[y][x] - 0.5)
                c = base
            row.append(tuple(_clamp(v * f) for v in c))
        rows.append(row)
    return rows


def roof_gravel(rng: random.Random) -> Rows:
    """Flat-roof gravel: speckled grey pebbles with a few warm stones."""
    big, small, warm, grain = value_noise(rng, 64), value_noise(rng, 128), value_noise(rng, 32), white(rng)
    dark, light, tan = (88, 86, 82), (184, 180, 172), (170, 150, 120)
    rows = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            t = 0.45 * big[y][x] + 0.35 * small[y][x] + 0.2 * grain[y][x]
            t = _smooth(t)
            c = _mix(dark, light, t)
            w = warm[y][x]
            if w > 0.7:
                c = _mix(c, tan, (w - 0.7) * 2.0)
            row.append(tuple(_clamp(v) for v in c))
        rows.append(row)
    return rows


def asphalt(rng: random.Random) -> Rows:
    """Asphalt with lane-agnostic noise: dark binder, light aggregate specks, wear patches."""
    patch, fine, grain = fbm(rng, [(4, 2), (8, 1)]), value_noise(rng, 128), white(rng)
    base, stone = (60, 60, 62), (150, 148, 142)
    rows = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            g = grain[y][x]
            if g > 0.975:
                c = _mix(base, stone, (g - 0.975) * 40.0)
            else:
                c = base
            f = 0.82 + 0.3 * patch[y][x] + 0.12 * (fine[y][x] - 0.5) + 0.08 * (g - 0.5)
            row.append(tuple(_clamp(v * f) for v in c))
        rows.append(row)
    return rows


def terrain(rng: random.Random) -> Rows:
    """Terrain: grass with soil patches (8 m tile)."""
    mask, detail, blades = fbm(rng, [(4, 3), (8, 2), (16, 1)]), value_noise(rng, 64), white(rng)
    grass, dry, soil = (92, 126, 58), (128, 134, 72), (122, 100, 72)
    rows = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            m = mask[y][x]
            c = _mix(grass, dry, detail[y][x])
            s = (m - 0.5) * 5.0
            if s > 0.0:
                c = _mix(c, soil, s if s < 1.0 else 1.0)
            f = 0.86 + 0.24 * blades[y][x]
            row.append(tuple(_clamp(v * f) for v in c))
        rows.append(row)
    return rows


def concrete(rng: random.Random) -> Rows:
    """Cast concrete: low-contrast mottling, fine pores and 2 m formwork joints."""
    low, fine, grain = fbm(rng, [(4, 2), (16, 2), (64, 1)]), value_noise(rng, 128), white(rng)
    base = (172, 170, 164)
    rows = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            g = grain[y][x]
            f = 0.9 + 0.14 * low[y][x] + 0.05 * (fine[y][x] - 0.5) + 0.04 * (g - 0.5)
            if (x % 128) < 2 or (y % 128) < 2:
                f *= 0.82
            if g > 0.996:
                f *= 0.6
            row.append(tuple(_clamp(v * f) for v in base))
        rows.append(row)
    return rows


TEXTURES: list[tuple[str, Callable[[random.Random], Rows]]] = [   # (file name, generator); the order fixes each texture's seed
    ("facade_plaster.png", facade),
    ("roof_tiles.png", roof_tiles),
    ("roof_gravel.png", roof_gravel),
    ("asphalt.png", asphalt),
    ("terrain_grass.png", terrain),
    ("concrete.png", concrete),
]


# ---------------------------------------------------------------- deterministic PNG writer

def _huffman_lengths(freqs: Iterable[int], limit: int) -> list[int]:
    """Code lengths of a Huffman code over ``freqs`` (zero frequency -> length 0), at most ``limit``.
    Ties are broken by symbol index, so the result is deterministic."""
    freqs = list(freqs)
    while True:
        heap: list[tuple[int, int, tuple[int, ...]]] = [(f, i, (i,)) for i, f in enumerate(freqs) if f > 0]
        lengths = [0] * len(freqs)
        if len(heap) == 1:
            lengths[heap[0][1]] = 1
            return lengths
        heapq.heapify(heap)
        order = len(freqs)
        while len(heap) > 1:
            f1, _, s1 = heapq.heappop(heap)
            f2, _, s2 = heapq.heappop(heap)
            for s in s1 + s2:
                lengths[s] += 1
            heapq.heappush(heap, (f1 + f2, order, s1 + s2))
            order += 1
        if max(lengths) <= limit:
            return lengths
        freqs = [(f + 1) // 2 if f else 0 for f in freqs]   # flatten and retry


def _canonical(lengths: Sequence[int]) -> dict[int, str]:
    """Canonical deflate codes (RFC 1951 3.2.2): {symbol: bit string, most significant bit first}."""
    bl_count = [0] * 16
    for n in lengths:
        if n:
            bl_count[n] += 1
    code, next_code = 0, [0] * 16
    for bits in range(1, 16):
        code = (code + bl_count[bits - 1]) << 1
        next_code[bits] = code
    out = {}
    for sym, n in enumerate(lengths):
        if n:
            out[sym] = format(next_code[n], f"0{n}b")
            next_code[n] += 1
    return out


def _lsb(value: int, nbits: int) -> str:
    """A header field in deflate stream order (least significant bit first)."""
    return format(value, f"0{nbits}b")[::-1]


CL_ORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)


def deflate_literals(data: bytes) -> bytes:
    """One final dynamic-Huffman deflate block of literals only (no LZ77 matches), in a zlib wrapper.
    The stream is built as a string of bits in stream order, then packed in one step."""
    freqs = [0] * 257
    for b in data:
        freqs[b] += 1
    freqs[256] = 1   # end of block
    lit_len = _huffman_lengths(freqs, 15)
    lit_codes = _canonical(lit_len)
    hlit = max(i for i, n in enumerate(lit_len) if n) + 1
    cl_seq = lit_len[:hlit] + [0]   # one distance code of zero bits: no distances (RFC 1951 3.2.7)
    cl_freqs = [0] * 19
    for n in cl_seq:
        cl_freqs[n] += 1
    cl_len = _huffman_lengths(cl_freqs, 7)
    cl_codes = _canonical(cl_len)
    hclen = max(i for i, s in enumerate(CL_ORDER) if cl_len[s]) + 1
    head = ["1", "01",  # BFINAL = 1, BTYPE = 10 (dynamic), each field least significant bit first
            _lsb(hlit - 257, 5), _lsb(0, 5), _lsb(hclen - 4, 4)]
    head += [_lsb(cl_len[s], 3) for s in CL_ORDER[:hclen]]
    head += [cl_codes[n] for n in cl_seq]
    table = [lit_codes.get(b, "") for b in range(256)]
    bits = "".join(head) + "".join([table[b] for b in data]) + lit_codes[256]
    bits += "0" * (-len(bits) % 8)
    body = int(bits[::-1], 2).to_bytes(len(bits) // 8, "little") if bits else b""
    return b"\x78\x01" + body + struct.pack(">I", zlib.adler32(data))


def _paeth_rows(rows: Rows) -> bytes:
    """Filter type 4 (Paeth) on every scanline of 8-bit RGB rows."""
    out, prev = bytearray(), bytes(len(rows[0]) * 3)
    for row in rows:
        cur = bytes(v for px in row for v in px)
        out.append(4)
        for i, x in enumerate(cur):
            a = cur[i - 3] if i >= 3 else 0
            b = prev[i]
            c = prev[i - 3] if i >= 3 else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
            out.append((x - pred) & 0xFF)
        prev = cur
    return bytes(out)


def png_bytes(rows: Rows) -> bytes:
    """An 8-bit RGB PNG from rows of (r, g, b) tuples (no ancillary chunks, no timestamps)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    h, w = len(rows), len(rows[0])
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", deflate_literals(_paeth_rows(rows)))
            + chunk(b"IEND", b""))


# ---------------------------------------------------------------- outputs

def generate_one(index: int) -> tuple[str, bytes]:
    """(file name, PNG bytes) of texture ``index`` in :data:`TEXTURES`."""
    name, fn = TEXTURES[index]
    return name, png_bytes(fn(random.Random(SEED * 1000 + index)))


def license_text(pngs: dict[str, bytes]) -> bytes:
    """LICENSE-textures.txt for ``{file name: PNG bytes}``."""
    with open(CC0_TEXT, encoding="utf-8") as f:
        cc0 = f.read()
    lines = [
        "map-builder procedural textures",
        "",
        "These images are our own work, generated procedurally by a seeded script from noise and",
        "simple geometry. They contain no photographs and no third-party, map or Google imagery.",
        "",
        "Licence: CC0 1.0 Universal (CC0-1.0), public domain dedication.",
        "https://creativecommons.org/publicdomain/zero/1.0/",
        "",
        "To the extent possible under law, the map-builder contributors have waived all copyright",
        "and related or neighboring rights to these textures. The full legal code follows below.",
        "",
        f"Generated by: {COMMAND}  (tools/textures/make_textures.py, seed {SEED})",
        "",
        "Files (SHA-256):",
    ]
    lines += [f"  {hashlib.sha256(data).hexdigest()}  {name}" for name, data in sorted(pngs.items())]
    lines += ["", "-" * 72, ""]
    return ("\n".join(lines) + "\n" + cc0).encode("utf-8")


def _canon(name: str, data: bytes) -> bytes:
    """Bytes for comparison: PNGs exactly; the licence text with CRLF folded to LF, because a Windows
    checkout with ``core.autocrlf`` may rewrite its line endings (git never converts the binary PNGs)."""
    return data.replace(b"\r\n", b"\n") if name.endswith(".txt") else data


def generate() -> dict[str, bytes]:
    """All output files: {file name: bytes}, including LICENSE-textures.txt."""
    pngs = dict(generate_one(i) for i in range(len(TEXTURES)))
    return {**pngs, LICENSE_NAME: license_text(pngs)}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT_DIR, help="output directory (default: the package assets)")
    ap.add_argument("--check", action="store_true", help="compare with --out instead of writing")
    args = ap.parse_args(argv)
    files = generate()
    if args.check:
        bad = []
        for name, data in files.items():
            path = os.path.join(args.out, name)
            if not os.path.isfile(path):
                bad.append(name)
                continue
            with open(path, "rb") as f:
                if _canon(name, f.read()) != _canon(name, data):
                    bad.append(name)
        for name in bad:
            print(f"differs: {name}")
        print("OK" if not bad else f"{len(bad)} file(s) differ")
        return 1 if bad else 0
    os.makedirs(args.out, exist_ok=True)
    for name, data in files.items():
        with open(os.path.join(args.out, name), "wb") as f:
            f.write(data)
        print(f"{len(data):8d}  {name}")
    print(f"{sum(len(d) for n, d in files.items() if n.endswith('.png')):8d}  PNG bytes in total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
