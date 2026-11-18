"""Minimal GeoTIFF reader (stdlib only).

Supported: classic (non-Big) TIFF, little/big endian, single-band rasters in
strips or tiles, uint8/int16/uint16/int32/uint32/float32/float64 samples,
compression none/LZW/Deflate, predictors 1/2/3, ModelPixelScale+Tiepoint
georeferencing, GeoKeys for EPSG:4326 and WGS84 UTM (326xx/327xx),
GDAL_NODATA. Anything else raises :class:`FormatError` explicitly.

Byte access goes through a *source* object with ``read(offset, length)`` so
the same code reads local files and HTTP range requests (cloud-optimised
GeoTIFFs such as the Copernicus DEM on AWS) without downloading whole files.
"""

import math
import struct
import zlib

from .errors import FormatError, LimitError

_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
_TYPE_FMT = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f", 12: "d"}

MAX_RASTER_PIXELS_READ = 16_000_000


class FileSource:
    def __init__(self, path, max_bytes=2 * 1024 ** 3):
        self.path = path
        self._f = open(path, "rb")
        self._f.seek(0, 2)
        self.size = self._f.tell()
        if self.size > max_bytes:
            self._f.close()
            raise LimitError(f"{path}: file larger than {max_bytes} bytes")
        self.description = path

    def read(self, offset, length):
        if offset < 0 or length < 0 or offset + length > self.size:
            raise FormatError(f"{self.description}: read beyond end of file (corrupt TIFF?)")
        self._f.seek(offset)
        return self._f.read(length)

    def close(self):
        self._f.close()


class BytesSource:
    def __init__(self, data, description="<memory>"):
        self.data = data
        self.size = len(data)
        self.description = description

    def read(self, offset, length):
        if offset < 0 or length < 0 or offset + length > self.size:
            raise FormatError(f"{self.description}: read beyond end of data (corrupt TIFF?)")
        return self.data[offset:offset + length]

    def close(self):
        pass


class HttpRangeSource:
    """Reads a remote file via HTTP Range requests with a prefetched header."""

    HEAD_BYTES = 256 * 1024

    def __init__(self, client, url, description, cache=None, max_total_bytes=96 * 1024 * 1024):
        self.client = client
        self.url = url
        self.description = description
        self.cache = cache
        self.max_total_bytes = max_total_bytes
        self.fetched = 0
        self._head = self._get(0, self.HEAD_BYTES, allow_short=True)
        self.size = None

    def _get(self, offset, length, allow_short=False):
        key = f"{self.description}#{offset}+{length}"
        body = self.cache.get("ranges", key) if self.cache else None
        if body is None:
            if self.fetched + length > self.max_total_bytes:
                raise LimitError(f"{self.description}: download budget of {self.max_total_bytes} bytes exceeded")
            body = self.client.fetch(self.url, byte_range=(offset, length), not_found_is_coverage=True)
            self.fetched += len(body)
            if self.cache:
                self.cache.put("ranges", key, body, {"source": self.description})
        if len(body) < length and not allow_short:
            raise FormatError(f"{self.description}: short read at {offset}")
        return body

    def read(self, offset, length):
        if offset + length <= len(self._head):
            return self._head[offset:offset + length]
        return self._get(offset, length)

    def close(self):
        pass


def lzw_decode(data):
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    width = 9
    bitpos = 0
    nbits = len(data) * 8
    prev = None
    while bitpos + width <= nbits:
        byte_i = bitpos >> 3
        chunk = int.from_bytes(data[byte_i:byte_i + 3].ljust(3, b"\0"), "big")
        code = (chunk >> (24 - (bitpos & 7) - width)) & ((1 << width) - 1)
        bitpos += width
        if code == 256:
            table = table[:258]
            width = 9
            prev = None
            continue
        if code == 257:
            break
        if prev is None:
            if code >= len(table):
                raise FormatError("corrupt LZW stream")
            entry = table[code]
            out += entry
            prev = entry
            continue
        if code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        elif code == len(table):
            entry = prev + prev[:1]
            table.append(entry)
        else:
            raise FormatError("corrupt LZW stream")
        out += entry
        prev = entry
        if len(table) >= (1 << width) - 1 and width < 12:
            width += 1
    return bytes(out)


class GeoTiff:
    def __init__(self, source):
        self.src = source
        head = source.read(0, 8)
        if head[:2] == b"II":
            self.bo = "<"
        elif head[:2] == b"MM":
            self.bo = ">"
        else:
            raise FormatError(f"{source.description}: not a TIFF file")
        magic = struct.unpack(self.bo + "H", head[2:4])[0]
        if magic == 43:
            raise FormatError(f"{source.description}: BigTIFF is not supported")
        if magic != 42:
            raise FormatError(f"{source.description}: bad TIFF magic")
        ifd = struct.unpack(self.bo + "I", head[4:8])[0]
        self.tags = self._read_ifd(ifd)
        self._parse()
        self._blocks = {}

    # -- parsing ---------------------------------------------------------
    def _read_ifd(self, off):
        n = struct.unpack(self.bo + "H", self.src.read(off, 2))[0]
        if n == 0 or n > 4096:
            raise FormatError(f"{self.src.description}: implausible IFD entry count {n}")
        raw = self.src.read(off + 2, n * 12)
        tags = {}
        for i in range(n):
            tag, typ, count = struct.unpack(self.bo + "HHI", raw[i * 12:i * 12 + 8])
            size = _TYPE_SIZES.get(typ)
            if size is None:
                continue
            total = size * count
            if total > 64 * 1024 * 1024:
                raise FormatError(f"{self.src.description}: tag {tag} too large")
            valbytes = raw[i * 12 + 8:i * 12 + 12]
            data = valbytes[:total] if total <= 4 else self.src.read(struct.unpack(self.bo + "I", valbytes)[0], total)
            if typ == 2:
                tags[tag] = data.split(b"\0", 1)[0].decode("latin-1")
            elif typ in (5, 10):
                fmt = "I" if typ == 5 else "i"
                v = struct.unpack(self.bo + fmt * (2 * count), data)
                tags[tag] = tuple(v[j] / v[j + 1] if v[j + 1] else 0.0 for j in range(0, len(v), 2))
            elif typ == 7:
                tags[tag] = data
            else:
                tags[tag] = struct.unpack(self.bo + _TYPE_FMT[typ] * count, data)
        return tags

    def _tag1(self, tag, default=None):
        v = self.tags.get(tag)
        if v is None:
            return default
        return v[0] if isinstance(v, tuple) else v

    def _parse(self):
        d = self.src.description
        self.width = self._tag1(256)
        self.height = self._tag1(257)
        if not self.width or not self.height:
            raise FormatError(f"{d}: missing raster size")
        if self._tag1(277, 1) != 1:
            raise FormatError(f"{d}: only single-band rasters are supported")
        self.bps = self._tag1(258, 1)
        self.sample_format = self._tag1(339, 1)
        fmt = {(1, 8): "B", (1, 16): "H", (1, 32): "I", (2, 8): "b", (2, 16): "h", (2, 32): "i",
               (3, 32): "f", (3, 64): "d"}.get((self.sample_format, self.bps))
        if fmt is None:
            raise FormatError(f"{d}: unsupported sample type format={self.sample_format} bits={self.bps}")
        self.fmt = fmt
        self.bytes_ps = self.bps // 8
        self.compression = self._tag1(259, 1)
        if self.compression not in (1, 5, 8, 32946):
            raise FormatError(f"{d}: unsupported compression {self.compression}")
        self.predictor = self._tag1(317, 1)
        if self.predictor not in (1, 2, 3):
            raise FormatError(f"{d}: unsupported predictor {self.predictor}")
        if 322 in self.tags:
            self.block_w = self._tag1(322)
            self.block_h = self._tag1(323)
            self.offsets = self.tags[324]
            self.counts = self.tags[325]
        else:
            self.block_w = self.width
            self.block_h = min(self._tag1(278, self.height), self.height)
            self.offsets = self.tags.get(273)
            self.counts = self.tags.get(279)
        if not self.offsets or not self.counts or len(self.offsets) != len(self.counts):
            raise FormatError(f"{d}: missing or inconsistent strip/tile offsets")
        self.blocks_across = (self.width + self.block_w - 1) // self.block_w
        nodata = self.tags.get(42113)
        self.nodata = None
        if isinstance(nodata, str) and nodata.strip():
            try:
                self.nodata = float(nodata.strip())
            except ValueError:
                raise FormatError(f"{d}: unparsable GDAL_NODATA {nodata!r}") from None
        self._parse_geo()

    def _parse_geo(self):
        d = self.src.description
        if 34264 in self.tags:
            m = self.tags[34264]
            if abs(m[1]) > 1e-12 or abs(m[4]) > 1e-12:
                raise FormatError(f"{d}: rotated rasters are not supported")
            sx, x0, sy, y0 = m[0], m[3], -m[5], m[7]
            ti, tj = 0.0, 0.0
        else:
            if 33550 not in self.tags or 33922 not in self.tags:
                raise FormatError(f"{d}: no georeferencing (ModelPixelScale/Tiepoint missing)")
            sx, sy = self.tags[33550][0], self.tags[33550][1]
            ti, tj, _, x0, y0, _ = self.tags[33922][:6]
        if sx <= 0 or sy <= 0:
            raise FormatError(f"{d}: invalid pixel scale")
        keys = {}
        gk = self.tags.get(34735)
        if gk:
            for i in range(4, 4 + 4 * gk[3], 4):
                kid, loc, cnt, val = gk[i:i + 4]
                if loc == 0:
                    keys[kid] = val
        raster_type = keys.get(1025, 1)
        shift = 0.5 if raster_type == 1 else 0.0  # PixelIsArea -> centres are half a pixel in
        self.x_c0 = x0 + (shift - ti) * sx
        self.y_c0 = y0 - (shift - tj) * sy
        self.sx, self.sy = sx, sy
        self.pixel_is_point = raster_type == 2
        model = keys.get(1024)
        geog = keys.get(2048)
        proj = keys.get(3072)
        self.vertical_epsg = keys.get(4096)
        if model == 2 or (model is None and geog is not None and proj is None):
            if geog not in (4326, None) and geog != 32767:
                raise FormatError(f"{d}: geographic CRS EPSG:{geog} unsupported; reproject to EPSG:4326")
            if geog is None:
                raise FormatError(f"{d}: geographic CRS not declared; expected EPSG:4326")
            self.crs = {"kind": "geographic", "epsg": 4326}
        elif model == 1 and proj is not None and (32601 <= proj <= 32660 or 32701 <= proj <= 32760):
            self.crs = {"kind": "utm", "epsg": proj, "zone": proj % 100, "south": proj >= 32701}
        else:
            raise FormatError(
                f"{d}: unsupported CRS (model={model}, geographic={geog}, projected={proj}); "
                "reproject to EPSG:4326 or a WGS84 UTM zone (EPSG:326xx/327xx)")

    # -- pixel access ----------------------------------------------------
    def col_row(self, x, y):
        """Fractional pixel-centre coordinates of CRS position (x, y)."""
        return (x - self.x_c0) / self.sx, (self.y_c0 - y) / self.sy

    def _block(self, idx):
        if idx in self._blocks:
            return self._blocks[idx]
        if idx >= len(self.offsets):
            raise FormatError(f"{self.src.description}: block index out of range")
        raw = self.src.read(self.offsets[idx], self.counts[idx]) if self.counts[idx] else b""
        try:
            if self.compression in (8, 32946):
                raw = zlib.decompress(raw)
            elif self.compression == 5:
                raw = lzw_decode(raw)
        except zlib.error as e:
            raise FormatError(f"{self.src.description}: corrupt deflate block: {e}") from None
        n = self.block_w * self.block_h
        need = n * self.bytes_ps
        if len(raw) < need:
            # last strip may be short
            rows = len(raw) // (self.block_w * self.bytes_ps)
            n = rows * self.block_w
            need = n * self.bytes_ps
        raw = raw[:need]
        rows = n // self.block_w
        vals = self._unpredict(raw, rows)
        self._blocks[idx] = vals
        if len(self._blocks) > 64:
            self._blocks.pop(next(iter(self._blocks)))
        return vals

    def _unpredict(self, raw, rows):
        w, b = self.block_w, self.bytes_ps
        if self.predictor == 1:
            return struct.unpack(f"{self.bo}{w * rows}{self.fmt}", raw)
        if self.predictor == 2:
            vals = list(struct.unpack(f"{self.bo}{w * rows}{self.fmt}", raw))
            mask = (1 << self.bps) - 1
            signed = self.sample_format == 2
            for r in range(rows):
                base = r * w
                for c in range(1, w):
                    v = (vals[base + c] + vals[base + c - 1]) & mask
                    if signed and v >= 1 << (self.bps - 1):
                        v -= 1 << self.bps
                    vals[base + c] = v
            return vals
        # predictor 3: byte-wise differencing over byte planes (MSB plane first)
        out = []
        rowbytes = w * b
        for r in range(rows):
            row = bytearray(raw[r * rowbytes:(r + 1) * rowbytes])
            for i in range(1, rowbytes):
                row[i] = (row[i] + row[i - 1]) & 0xFF
            be = bytearray(rowbytes)
            for c in range(w):
                for k in range(b):
                    be[c * b + k] = row[k * w + c]
            out.extend(struct.unpack(f">{w}{self.fmt}", bytes(be)))
        return out

    def pixel(self, col, row):
        if not (0 <= col < self.width and 0 <= row < self.height):
            return None
        bx, by = col // self.block_w, row // self.block_h
        vals = self._block(by * self.blocks_across + bx)
        i = (row - by * self.block_h) * self.block_w + (col - bx * self.block_w)
        if i >= len(vals):
            raise FormatError(f"{self.src.description}: truncated block")
        v = float(vals[i])
        if self.nodata is not None and (v == self.nodata or (math.isnan(self.nodata) and math.isnan(v))):
            return None
        if math.isnan(v):
            return None
        return v

    def check_window(self, col0, row0, col1, row1):
        if (col1 - col0 + 1) * (row1 - row0 + 1) > MAX_RASTER_PIXELS_READ:
            raise LimitError(f"{self.src.description}: requested window too large")
