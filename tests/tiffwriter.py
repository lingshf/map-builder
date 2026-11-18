"""Minimal GeoTIFF *writer* used only by tests to build SYNTHETIC rasters in memory."""

import struct
import zlib


def lzw_encode(data):
    """TIFF LZW (MSB-first, early change) encoder."""
    out_bits = []
    table = {bytes([i]): i for i in range(256)}
    next_code, width = 258, 9

    def emit(code):
        out_bits.append((code, width))

    emit(256)
    w = b""
    for byte in data:
        wc = w + bytes([byte])
        if wc in table:
            w = wc
            continue
        emit(table[w])
        table[wc] = next_code
        next_code += 1
        if next_code >= (1 << width) and width < 12:
            width += 1
        if next_code >= 4093:
            emit(256)
            table = {bytes([i]): i for i in range(256)}
            next_code, width = 258, 9
        w = bytes([byte])
    if w:
        emit(table[w])
        next_code += 1
        if next_code >= (1 << width) and width < 12:
            width += 1
    emit(257)
    acc, nbits, out = 0, 0, bytearray()
    for code, wbits in out_bits:
        acc = (acc << wbits) | code
        nbits += wbits
        while nbits >= 8:
            nbits -= 8
            out.append((acc >> nbits) & 0xFF)
    if nbits:
        out.append((acc << (8 - nbits)) & 0xFF)
    return bytes(out)


def _predict(rows_vals, w, bo, fmt, predictor):
    b = struct.calcsize(fmt)
    out = bytearray()
    for row in rows_vals:
        if predictor == 1:
            out += struct.pack(f"{bo}{len(row)}{fmt}", *row)
        elif predictor == 2:
            mask = (1 << (8 * b)) - 1
            d = [row[0]] + [(row[c] - row[c - 1]) & mask for c in range(1, len(row))]
            ufmt = {"h": "H", "i": "I", "b": "B"}.get(fmt, fmt)
            out += struct.pack(f"{bo}{len(d)}{ufmt}", *[v & mask for v in d])
        else:
            be = struct.pack(f">{len(row)}{fmt}", *row)
            planes = bytearray(len(be))
            for c in range(w):
                for k in range(b):
                    planes[k * w + c] = be[c * b + k]
            for i in range(len(planes) - 1, 0, -1):
                planes[i] = (planes[i] - planes[i - 1]) & 0xFF
            out += planes
    return bytes(out)


def make_geotiff(values, x0, y0, sx, sy, epsg=4326, *, big_endian=False, tile=None, rows_per_strip=None,
                 compression=8, predictor=1, sample="f32", nodata=None, pixel_is_point=False,
                 tag_overrides=None, payload_hook=None):
    """values[row][col], row 0 = north. (x0, y0) = upper-left corner of pixel (0,0) (PixelIsArea)
    or centre (PixelIsPoint).

    ``tag_overrides`` {tag: (type, values)} replaces/adds IFD entries (types 2/7 take raw bytes);
    ``payload_hook(raw_uncompressed) -> stored bytes`` replaces block encoding (for corrupt-data tests)."""
    bo = ">" if big_endian else "<"
    fmt, sfmt, bps = {"f32": ("f", 3, 32), "i16": ("h", 2, 16), "u16": ("H", 1, 16)}[sample]
    h, w = len(values), len(values[0])
    blocks = []
    if tile:
        bw, bh = tile
        for by in range(0, h, bh):
            for bx in range(0, w, bw):
                rows = []
                for r in range(by, by + bh):
                    row = [values[r][c] if r < h and c < w else 0 for c in range(bx, bx + bw)]
                    rows.append(row)
                blocks.append((rows, bw))
    else:
        rps = rows_per_strip or h
        for by in range(0, h, rps):
            blocks.append(([values[r] for r in range(by, min(h, by + rps))], w))
    payloads = []
    for rows, bw in blocks:
        raw = _predict(rows, bw, bo, fmt, predictor)
        if payload_hook is not None:
            raw = payload_hook(raw)
        elif compression == 8:
            raw = zlib.compress(raw)
        elif compression == 5:
            raw = lzw_encode(raw)
        payloads.append(raw)
    if epsg == 4326:
        keys = [(1024, 2), (1025, 2 if pixel_is_point else 1), (2048, 4326)]
    else:
        keys = [(1024, 1), (1025, 2 if pixel_is_point else 1), (3072, epsg)]
    gk = [1, 1, 0, len(keys)]
    for k, v in keys:
        gk += [k, 0, 1, v]
    tags = [(256, 4, [w]), (257, 4, [h]), (258, 3, [bps]), (259, 3, [compression]), (262, 3, [1]),
            (277, 3, [1]), (284, 3, [1]), (317, 3, [predictor]), (339, 3, [sfmt]),
            (33550, 12, [sx, sy, 0.0]), (33922, 12, [0.0, 0.0, 0.0, x0, y0, 0.0]), (34735, 3, gk)]
    if tile:
        tags += [(322, 3, [tile[0]]), (323, 3, [tile[1]]), (324, 4, None), (325, 4, [len(p) for p in payloads])]
    else:
        tags += [(273, 4, None), (278, 4, [rows_per_strip or h]), (279, 4, [len(p) for p in payloads])]
    if nodata is not None:
        tags.append((42113, 2, (str(nodata) + "\0").encode("ascii")))
    for tag, (typ, vals) in (tag_overrides or {}).items():
        tags = [t for t in tags if t[0] != tag] + [(tag, typ, vals)]
    tags.sort(key=lambda t: t[0])
    fmts = {1: "B", 3: "H", 4: "I", 12: "d", 2: "s", 7: "s"}
    header = 8
    ifd_size = 2 + 12 * len(tags) + 4
    data_off = header + ifd_size
    extra = bytearray()
    payload_start = None
    # first pass to place blocks after the extra area: compute extra sizes
    def tag_bytes(typ, vals):
        if typ in (2, 7):
            return vals
        return struct.pack(f"{bo}{len(vals)}{fmts[typ]}", *vals)
    sizes = {}
    for tag, typ, vals in tags:
        n = len(payloads) if vals is None else (len(vals))
        sizes[tag] = n * struct.calcsize(fmts[typ]) if typ not in (2, 7) else len(vals)
    extra_len = sum(s for s in sizes.values() if s > 4)
    payload_start = data_off + extra_len
    offsets = []
    pos = payload_start
    for p in payloads:
        offsets.append(pos)
        pos += len(p)
    entries = bytearray()
    for tag, typ, vals in tags:
        if vals is None:
            vals = offsets
        b = tag_bytes(typ, vals)
        count = len(vals)
        if len(b) <= 4:
            entries += struct.pack(f"{bo}HHI", tag, typ, count) + b.ljust(4, b"\0")
        else:
            entries += struct.pack(f"{bo}HHII", tag, typ, count, data_off + len(extra))
            extra += b
    out = bytearray((b"MM" if big_endian else b"II") + struct.pack(f"{bo}HI", 42, 8))
    out += struct.pack(f"{bo}H", len(tags)) + entries + struct.pack(f"{bo}I", 0)
    out += extra
    assert len(out) == payload_start
    for p in payloads:
        out += p
    return bytes(out)
