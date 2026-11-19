"""Platform-neutral static collision formats (see docs/PACKAGE_FORMAT.md).

``.mbcol`` (authoritative): triangles in the map frame (metres, +X east, +Y north,
+Z up, right-handed), world space, front faces CCW seen from outside
(normal = (b - a) x (c - a)). Triangles are grouped per object; each object entry
carries the glTF node name it was exported from, so visuals and collision stay bound.

``.mbhf`` (derived convenience): regular terrain height grid rasterised from the
*final* terrain-class collision triangles (maximum z where several overlap, NaN where
there is no terrain). It never replaces the triangles as the authority.

Readers bounds-check every count, index and size before allocating anything that
depends on it, and reject non-finite vertices.
"""

import json
import math
import struct

from . import COLLISION_FORMAT_VERSION, HEIGHTFIELD_FORMAT_VERSION
from .errors import LimitError, PackageError

COL_MAGIC = b"MBCOL\0\0\0"
HF_MAGIC = b"MBHF\0\0\0\0"
# magic, version, flags, V, T, O, J, bounds_min[3], bounds_max[3], reserved[2]  -> 64 bytes
COL_HEADER = struct.Struct("<8sIIIIII3f3f2I")
# magic, version, nx, ny, reserved, x0, y0, spacing  -> 48 bytes
HF_HEADER = struct.Struct("<8sIIIIddd")
FLAG_CCW_OUTWARD = 1
KNOWN_FLAGS = FLAG_CCW_OUTWARD

CLASSES = {"user": 0, "terrain": 1, "building": 2, "road": 3, "vegetation": 4, "water": 5, "prop": 6}
CLASS_NAMES = {v: k for k, v in CLASSES.items()}
TABLE_KEYS = ("index", "name", "mb_id", "class", "tri_start", "tri_count", "aabb")

MAX_TRIANGLES = 8_000_000
MAX_VERTICES = 12_000_000
MAX_OBJECTS = 1_000_000
MAX_TABLE_BYTES = 256 * 1024 * 1024
MAX_ABS_COORD_M = 1.0e6       # far beyond any map; keeps float32 meaningful
DEGENERATE_EPS = 1e-10        # |(b-a) x (c-a)|^2 at or below this is a zero-area triangle
AABB_TABLE_TOL_M = 1e-3

_F32 = struct.Struct("<f")


def f32(v):
    """Round a Python float to the nearest float32 (the stored precision)."""
    return _F32.unpack(_F32.pack(v))[0]


def strict_json(data, what):
    def no_constant(c):
        raise ValueError(f"non-finite number {c}")

    def no_dupes(pairs):
        out = {}
        for i, (k, v) in enumerate(pairs):
            if k in out:
                raise ValueError(f"duplicate key (member #{i} of an object)")   # never echo the key text
            out[k] = v
        return out
    try:
        return json.loads(data.decode("utf-8"), parse_constant=no_constant, object_pairs_hook=no_dupes)
    except (ValueError, UnicodeDecodeError, RecursionError) as e:
        raise PackageError(f"{what} is not valid strict UTF-8 JSON: {e}") from None


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


class ColObject:
    """One collision object: world-space map-frame vertices and CCW triangles (index triples)."""

    def __init__(self, name, mb_id, cls, vertices, triangles, extra=None):
        self.name = name
        self.mb_id = mb_id
        self.cls = cls
        self.vertices = vertices
        self.triangles = triangles
        self.extra = extra or {}


def _pad4(b, fill=b"\0"):
    return b + fill * (-len(b) % 4)


def write_collision(objects):
    """Serialise ``ColObject``s. Only vertices referenced by triangles are stored (as float32);
    header bounds and per-object AABBs are computed from the stored float32 values."""
    names = set()
    flat, idx, tri_obj, tri_cls, table = [], [], [], [], []
    nv = 0
    for oi, o in enumerate(objects):
        tag = f"collision object #{oi}"           # names are caller strings: never echoed in diagnostics
        if not isinstance(o.name, str) or not o.name:
            raise PackageError("collision object names must be non-empty strings")
        if o.name in names:
            raise PackageError(f"{tag}: duplicate collision object name")
        names.add(o.name)
        if not isinstance(o.mb_id, str) or not o.mb_id:
            raise PackageError(f"{tag} has no mb_id")
        if not isinstance(o.cls, str) or o.cls not in CLASSES:
            raise PackageError(f"{tag} has an unknown class; expected one of {sorted(CLASSES)}")
        tris = [tuple(t) for t in o.triangles]
        if not tris:
            raise PackageError(f"{tag} has no triangles")
        remap = {}
        start = len(tri_obj)
        lo = [math.inf] * 3
        hi = [-math.inf] * 3
        for t in tris:
            if len(t) != 3:
                raise PackageError(f"{tag}: triangles must have 3 indices")
            for vi in t:
                if not _is_int(vi) or not 0 <= vi < len(o.vertices):
                    raise PackageError(f"{tag}: triangle vertex index out of range (must be an integer in "
                                       f"[0, {len(o.vertices)}))")
                if vi not in remap:
                    p = o.vertices[vi]
                    if len(p) != 3 or not all(_is_num(c) and abs(c) <= MAX_ABS_COORD_M for c in p):
                        raise PackageError(f"non-finite or out-of-range vertex in {tag}")
                    q = (f32(p[0]), f32(p[1]), f32(p[2]))
                    for k in range(3):
                        lo[k] = min(lo[k], q[k])
                        hi[k] = max(hi[k], q[k])
                    remap[vi] = nv
                    nv += 1
                    flat.extend(q)
            idx.extend((remap[t[0]], remap[t[1]], remap[t[2]]))
            tri_obj.append(oi)
            tri_cls.append(CLASSES[o.cls])
        entry = {"index": oi, "name": o.name, "mb_id": o.mb_id, "class": o.cls, "tri_start": start,
                 "tri_count": len(tri_obj) - start, "aabb": lo + hi}
        for k, v in o.extra.items():
            if k not in entry:
                entry[k] = v
        table.append(entry)
    nt = len(tri_obj)
    if nt > MAX_TRIANGLES or nv > MAX_VERTICES or len(objects) > MAX_OBJECTS:
        raise LimitError(f"collision has {nt} triangles / {nv} vertices / {len(objects)} objects; limits "
                         f"{MAX_TRIANGLES}/{MAX_VERTICES}/{MAX_OBJECTS}")
    if nv:
        bmin = [min(flat[k::3]) for k in range(3)]
        bmax = [max(flat[k::3]) for k in range(3)]
    else:
        bmin = bmax = [0.0, 0.0, 0.0]
    try:
        tjson = _pad4(json.dumps(table, separators=(",", ":"), ensure_ascii=False,
                                 allow_nan=False).encode("utf-8"))
    except ValueError as e:
        raise PackageError(f"collision object table is not finite JSON: {e}") from None
    if len(tjson) > MAX_TABLE_BYTES:
        raise LimitError("collision object table too large")
    out = bytearray(COL_HEADER.pack(COL_MAGIC, COLLISION_FORMAT_VERSION, FLAG_CCW_OUTWARD, nv, nt,
                                    len(objects), len(tjson), *bmin, *bmax, 0, 0))
    out += struct.pack(f"<{len(flat)}f", *flat)
    out += struct.pack(f"<{len(idx)}I", *idx)
    out += struct.pack(f"<{nt}I", *tri_obj)
    out += _pad4(bytes(tri_cls))
    out += tjson
    return bytes(out)


class Collision:
    def __init__(self, vertices, indices, tri_object, tri_class, objects, bounds, flags):
        self.vertices = vertices      # [(x, y, z)] float32 values
        self.indices = indices        # flat tuple, 3 per triangle
        self.tri_object = tri_object
        self.tri_class = tri_class    # bytes
        self.objects = objects        # parsed object table
        self.bounds = bounds
        self.flags = flags

    @property
    def triangle_count(self):
        return len(self.indices) // 3

    def triangle(self, t):
        v = self.vertices
        i = self.indices
        return v[i[3 * t]], v[i[3 * t + 1]], v[i[3 * t + 2]]

    def object_triangles(self, entry):
        s = entry["tri_start"]
        return [self.triangle(t) for t in range(s, s + entry["tri_count"])]

    def class_triangles(self, cls):
        cid = CLASSES[cls]
        return [self.triangle(t) for t in range(self.triangle_count) if self.tri_class[t] == cid]


def collision_size(nv, nt, tlen):
    return COL_HEADER.size + 12 * nv + 12 * nt + 4 * nt + nt + (-nt % 4) + tlen


def read_collision(data, max_triangles=MAX_TRIANGLES, max_vertices=MAX_VERTICES):
    """Parse and fully bounds-check an ``.mbcol`` file; raises PackageError."""
    if len(data) < COL_HEADER.size:
        raise PackageError("collision: file too short for the 64-byte header")
    (magic, ver, flags, nv, nt, no, tlen, x0, y0, z0, x1, y1, z1, r0, r1) = COL_HEADER.unpack_from(data, 0)
    if magic != COL_MAGIC:
        raise PackageError("collision: bad magic")
    if ver != COLLISION_FORMAT_VERSION:
        raise PackageError(f"collision: unsupported version {ver}")
    if not flags & FLAG_CCW_OUTWARD:
        raise PackageError("collision: flags bit0 (CCW outward winding) is not set")
    if flags & ~KNOWN_FLAGS:
        raise PackageError(f"collision: unknown flag bits 0x{flags & ~KNOWN_FLAGS:x}")
    if r0 or r1:
        raise PackageError("collision: reserved header fields must be 0")
    if nv > max_vertices or nt > max_triangles or no > MAX_OBJECTS or tlen > MAX_TABLE_BYTES:
        raise PackageError("collision: header counts exceed limits")
    if tlen % 4:
        raise PackageError("collision: object table length is not padded to 4 bytes")
    if no > nt:
        raise PackageError("collision: more objects than triangles (every object needs a triangle)")
    expected = collision_size(nv, nt, tlen)
    if len(data) != expected:
        raise PackageError(f"collision: size {len(data)} does not match the size computed from the header "
                           f"({expected})")
    bounds = ((x0, y0, z0), (x1, y1, z1))
    if not all(math.isfinite(c) for p in bounds for c in p):
        raise PackageError("collision: non-finite bounds")
    o = COL_HEADER.size
    flat = struct.unpack_from(f"<{3 * nv}f", data, o)
    o += 12 * nv
    if not all(math.isfinite(c) for c in flat):
        raise PackageError("collision: non-finite vertex")
    if nv:
        actual = (tuple(min(flat[k::3]) for k in range(3)), tuple(max(flat[k::3]) for k in range(3)))
    else:
        actual = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    if actual != bounds:
        raise PackageError(f"collision: header bounds {bounds} do not match the vertices {actual}")
    verts = list(zip(flat[0::3], flat[1::3], flat[2::3]))
    idx = struct.unpack_from(f"<{3 * nt}I", data, o)
    o += 12 * nt
    if idx and max(idx) >= nv:
        raise PackageError("collision: triangle vertex index out of range")
    tri_obj = struct.unpack_from(f"<{nt}I", data, o)
    o += 4 * nt
    tri_cls = bytes(data[o:o + nt])
    if any(data[o + nt:o + nt + (-nt % 4)]):
        raise PackageError("collision: class padding bytes must be 0")
    o += nt + (-nt % 4)
    if tri_obj and max(tri_obj) >= no:
        raise PackageError("collision: triangle object index out of range")
    if any(c not in CLASS_NAMES for c in set(tri_cls)):
        raise PackageError("collision: unknown class id")
    raw = bytes(data[o:o + tlen])
    body = raw.rstrip(b"\0")
    if b"\0" in body:
        raise PackageError("collision: object table contains NUL bytes before its padding")
    table = strict_json(body, "collision: object table")
    if not isinstance(table, list) or len(table) != no:
        raise PackageError("collision: object table count does not match the header")
    # Diagnostics name entries by table index only: names and other strings from the file are never echoed.
    names = set()
    total = 0
    for k, e in enumerate(table):
        tag = f"collision: object entry {k}"
        if not isinstance(e, dict) or any(key not in e for key in TABLE_KEYS):
            raise PackageError(f"{tag} lacks {list(TABLE_KEYS)}")
        name = e["name"]
        if e["index"] != k or not _is_int(e["index"]):
            raise PackageError(f"{tag} has an index other than {k}")
        if not isinstance(name, str) or not name or name in names:
            raise PackageError(f"{tag} has a missing or duplicate name")
        names.add(name)
        if not isinstance(e["mb_id"], str) or not e["mb_id"]:
            raise PackageError(f"{tag} has no mb_id")
        if not isinstance(e["class"], str) or e["class"] not in CLASSES:
            raise PackageError(f"{tag} has an unknown class; expected a string, one of {sorted(CLASSES)}")
        s, c = e["tri_start"], e["tri_count"]
        if not (_is_int(s) and _is_int(c) and s >= 0 and c >= 1 and s + c <= nt):
            raise PackageError(f"{tag} has a bad triangle range")
        if tri_obj[s:s + c].count(k) != c:
            raise PackageError(f"{tag}: its triangles are not contiguous in [tri_start, tri_start + tri_count)")
        if tri_cls[s:s + c].count(CLASSES[e["class"]]) != c:
            raise PackageError(f"{tag}: per-triangle class ids differ from its class {e['class']!r}")
        total += c
        aabb = e["aabb"]
        if not (isinstance(aabb, list) and len(aabb) == 6 and all(_is_num(v) for v in aabb)):
            raise PackageError(f"{tag} has a malformed aabb")
        pts = [verts[i] for i in idx[3 * s:3 * (s + c)]]
        want = [min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts),
                max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts)]
        if any(abs(a - b) > AABB_TABLE_TOL_M for a, b in zip(aabb, want)):
            raise PackageError(f"{tag}: aabb does not match its triangles")
    if total != nt:
        raise PackageError("collision: object triangle ranges do not cover every triangle")
    return Collision(verts, idx, tri_obj, tri_cls, table, bounds, flags)


def is_degenerate(a, b, c, eps=DEGENERATE_EPS):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return cx * cx + cy * cy + cz * cz <= eps


def count_degenerate(triangles, eps=DEGENERATE_EPS):
    """triangles: iterable of (a, b, c) points; counts near-zero-area triangles."""
    return sum(1 for a, b, c in triangles if is_degenerate(a, b, c, eps))


def degenerate_triangle_count(col, eps=DEGENERATE_EPS):
    return count_degenerate((col.triangle(t) for t in range(col.triangle_count)), eps)


# --- heightfield --------------------------------------------------------------

MAX_HF_POINTS = 4_000_000

# Cumulative budget for grid points visited while rasterising (each triangle visits every point of its
# clipped XY bounding box). A legitimate terrain mesh visits about 2-8 points per grid point: each cell is
# covered by roughly one triangle, a triangle's bounding box is about twice its area, and points on shared
# edges are visited by every adjacent triangle (measured worst case on generated terrain: 7.9). 16 per
# point gives 2x headroom over that, so a 1 km^2 terrain at the finest grid MAX_HF_POINTS allows stays
# well inside it, while N overlapping area-spanning triangles (N * nx * ny visits) fail once N > 16.
# HF_VISIT_SLACK covers tiny grids where per-triangle rounding dominates.
HF_VISITS_PER_POINT = 16
HF_VISIT_SLACK = 4096


def heightfield_visit_budget(nx, ny):
    return HF_VISITS_PER_POINT * nx * ny + HF_VISIT_SLACK


def heightfield_layout(area_half, spacing):
    """(x0, y0, nx, ny) of the grid covering the area rectangle; raises LimitError if too large."""
    if not (_is_num(spacing) and spacing > 0):
        raise PackageError("heightfield spacing must be a positive finite number")
    hx, hy = area_half
    nx = int(math.floor(2 * hx / spacing + 1e-9)) + 1
    ny = int(math.floor(2 * hy / spacing + 1e-9)) + 1
    if nx * ny > MAX_HF_POINTS:
        raise LimitError(f"heightfield {nx}x{ny} exceeds {MAX_HF_POINTS} points; use a coarser spacing")
    return -hx, -hy, nx, ny


def rasterize_heightfield(triangles, x0, y0, spacing, nx, ny):
    """Maximum z of the triangles at each grid point (row j: y = y0 + j*spacing; column i: x = x0 + i*spacing)."""
    if nx * ny > MAX_HF_POINTS:
        raise LimitError("heightfield too large")
    z = [[math.nan] * nx for _ in range(ny)]
    budget = heightfield_visit_budget(nx, ny)
    visited = 0
    for a, b, c in triangles:
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-12:
            continue
        i0 = max(0, int(math.ceil((min(a[0], b[0], c[0]) - x0) / spacing - 1e-9)))
        i1 = min(nx - 1, int(math.floor((max(a[0], b[0], c[0]) - x0) / spacing + 1e-9)))
        j0 = max(0, int(math.ceil((min(a[1], b[1], c[1]) - y0) / spacing - 1e-9)))
        j1 = min(ny - 1, int(math.floor((max(a[1], b[1], c[1]) - y0) / spacing + 1e-9)))
        if i1 < i0 or j1 < j0:
            continue
        visited += (i1 - i0 + 1) * (j1 - j0 + 1)
        if visited > budget:
            raise LimitError(f"heightfield rasterisation exceeds its work budget of {budget} grid-point visits "
                             f"({HF_VISITS_PER_POINT} per point of the {nx}x{ny} grid + {HF_VISIT_SLACK}); "
                             "the terrain triangles overlap far more than a terrain surface can")
        for j in range(j0, j1 + 1):
            py = y0 + j * spacing
            row = z[j]
            for i in range(i0, i1 + 1):
                px = x0 + i * spacing
                l1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / det
                l2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / det
                l3 = 1.0 - l1 - l2
                if l1 < -1e-7 or l2 < -1e-7 or l3 < -1e-7:
                    continue
                h = l1 * a[2] + l2 * b[2] + l3 * c[2]
                if math.isnan(row[i]) or h > row[i]:
                    row[i] = h
    return z


def write_heightfield(z, x0, y0, spacing):
    ny = len(z)
    nx = len(z[0]) if ny else 0
    if nx < 2 or ny < 2 or nx * ny > MAX_HF_POINTS or any(len(row) != nx for row in z):
        raise PackageError("heightfield: grid must be rectangular, at least 2x2 and within limits")
    if not (_is_num(x0) and _is_num(y0) and _is_num(spacing) and spacing > 0):
        raise PackageError("heightfield: origin and spacing must be finite (spacing > 0)")
    vals = [v for row in z for v in row]
    if any(math.isinf(v) for v in vals):
        raise PackageError("heightfield: infinite value (NaN is the only allowed no-terrain marker)")
    out = bytearray(HF_HEADER.pack(HF_MAGIC, HEIGHTFIELD_FORMAT_VERSION, nx, ny, 0, x0, y0, spacing))
    out += struct.pack(f"<{nx * ny}f", *vals)
    return bytes(out)


def read_heightfield(data):
    if len(data) < HF_HEADER.size:
        raise PackageError("heightfield: file too short for the 48-byte header")
    magic, ver, nx, ny, reserved, x0, y0, spacing = HF_HEADER.unpack_from(data, 0)
    if magic != HF_MAGIC:
        raise PackageError("heightfield: bad magic")
    if ver != HEIGHTFIELD_FORMAT_VERSION:
        raise PackageError(f"heightfield: unsupported version {ver}")
    if reserved:
        raise PackageError("heightfield: reserved header field must be 0")
    if nx < 2 or ny < 2 or nx * ny > MAX_HF_POINTS:
        raise PackageError("heightfield: implausible dimensions")
    if not (math.isfinite(x0) and math.isfinite(y0) and math.isfinite(spacing) and spacing > 0):
        raise PackageError("heightfield: non-finite origin or non-positive spacing")
    if len(data) != HF_HEADER.size + 4 * nx * ny:
        raise PackageError("heightfield: size does not match nx * ny")
    vals = struct.unpack_from(f"<{nx * ny}f", data, HF_HEADER.size)
    if any(math.isinf(v) for v in vals):
        raise PackageError("heightfield: infinite value")
    return {"nx": nx, "ny": ny, "x0": x0, "y0": y0, "spacing": spacing,
            "z": [list(vals[j * nx:(j + 1) * nx]) for j in range(ny)]}
