# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Minimal glTF 2.0 binary (GLB) reader and writer.

The writer produces simple, valid GLB files from :class:`MeshData` (used for tests,
synthetic samples and headless pipelines without Blender). The reader is used by the
package validator to compute the world-space triangles of every node, so visuals can be
cross-checked against the collision file. It is defensive: every count, index, offset and
size is checked against the actual bytes before use, and any malformed input raises
:class:`PackageError` (never another exception type).
"""

from __future__ import annotations

import json
import math
import struct
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, NotRequired, TypeAlias, TypedDict, TypeGuard, cast

from .collision import strict_json
from .errors import PackageError
from .geodesy import map_to_gltf
from .mesh import DECOR_MATERIAL

if TYPE_CHECKING:
    from .mesh import MeshData

Vec3: TypeAlias = "tuple[float, float, float]"
Vec2: TypeAlias = "tuple[float, float]"
Matrix: TypeAlias = "list[list[float]]"
# Any: the glTF JSON a package GLB is read from is untrusted; read_glb validates it key by key
Gltf: TypeAlias = "dict[str, Any]"
# (rgb, roughness, metallic) or, textured, (rgb, roughness, metallic, png bytes)
MaterialSpec: TypeAlias = "tuple[Sequence[float], float, float] | tuple[Sequence[float], float, float, bytes]"


class GlbNodeSpec(TypedDict):
    """A node handed to :func:`write_glb`; ``location``/``rotation_z``/``scale`` default to the identity."""
    name: str
    mesh: MeshData
    location: NotRequired[Sequence[float]]
    rotation_z: NotRequired[float]
    scale: NotRequired[float | Sequence[float]]
    extras: NotRequired[Mapping[str, str]]


# The glTF document pieces the writer emits (key order is the serialised order)
class _GltfAsset(TypedDict):
    version: str
    generator: str
    extras: NotRequired[Mapping[str, object]]  # caller-supplied JSON-serialisable extras


class _GltfScene(TypedDict):
    nodes: list[int]


class _GltfBuffer(TypedDict):
    byteLength: int


class _GltfBufferView(TypedDict):
    buffer: int
    byteOffset: int
    byteLength: int
    target: NotRequired[int]


class _GltfAccessor(TypedDict):
    bufferView: int
    componentType: int
    count: int
    type: str
    min: NotRequired[list[float]]
    max: NotRequired[list[float]]


class _GltfTextureInfo(TypedDict):
    index: int
    texCoord: int


class _GltfPbr(TypedDict):
    baseColorFactor: list[float]
    metallicFactor: float
    roughnessFactor: float
    baseColorTexture: NotRequired[_GltfTextureInfo]


class _GltfMaterial(TypedDict):
    name: str
    pbrMetallicRoughness: _GltfPbr


class _GltfSampler(TypedDict):
    magFilter: int
    minFilter: int
    wrapS: int
    wrapT: int


class _GltfImage(TypedDict):
    bufferView: int
    mimeType: str


class _GltfTexture(TypedDict):
    sampler: int
    source: int


class _GltfPrimitive(TypedDict):
    attributes: dict[str, int]
    indices: int
    material: int
    mode: int
    extras: NotRequired[dict[str, bool]]


class _GltfMesh(TypedDict):
    name: str
    primitives: list[_GltfPrimitive]


class _GltfNode(TypedDict):
    name: str
    mesh: int
    translation: list[float]
    rotation: NotRequired[list[float]]
    scale: NotRequired[list[float]]
    extras: NotRequired[Mapping[str, str]]


class _GltfDocument(TypedDict):
    asset: _GltfAsset
    scenes: list[_GltfScene]
    scene: int
    nodes: list[_GltfNode]
    meshes: list[_GltfMesh]
    accessors: list[_GltfAccessor]
    bufferViews: list[_GltfBufferView]
    materials: list[_GltfMaterial]
    buffers: list[_GltfBuffer]
    samplers: NotRequired[list[_GltfSampler]]
    images: NotRequired[list[_GltfImage]]
    textures: NotRequired[list[_GltfTexture]]


GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942
MAX_GLB_BYTES = 1024 ** 3
MAX_VISUAL_TRIANGLES = 8_000_000
MAX_NODES = 1_000_000
MAX_DEPTH = 64
QUAT_UNIT_TOL = 1e-3
MAX_TEXTURE_BYTES = 4 * 1024 * 1024   # total embedded image bytes
MAX_TEXTURE_SIDE = 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# --- writer -----------------------------------------------------------------

def _f32(vals: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(vals)}f", *vals)


def _finite3(p: Sequence[object]) -> TypeGuard[Vec3]:
    return len(p) == 3 and all(isinstance(c, (int, float)) and math.isfinite(c) for c in p)


def node_scale(scale: float | Sequence[float]) -> tuple[float, ...]:
    """Map-frame scale (number or (sx, sy, sz)) -> tuple (sx, sy, sz)."""
    if isinstance(scale, (int, float)):
        return (float(scale),) * 3
    s = tuple(float(v) for v in scale)
    if len(s) != 3:
        raise PackageError("scale must be a number or a 3-tuple")
    return s


def write_glb(nodes: Sequence[GlbNodeSpec], materials: Mapping[str, MaterialSpec],
              generator: str = "map-builder", extras: Mapping[str, object] | None = None) -> bytes:
    """nodes: list of dicts {name, mesh: MeshData, location, rotation_z, scale, extras}.

    ``location``/``rotation_z`` (about +Z)/``scale`` (number or per-axis map-frame tuple) are the
    map-frame object transform; they become the node TRS in glTF axes (gltf = (x, z, -y)).
    Shared MeshData instances (same object) become one glTF mesh.
    materials: {name: (rgb, roughness, metallic[, png_bytes])}. ``png_bytes`` makes the material
    textured: it is embedded once (identical bytes share one image) as ``baseColorTexture``, and the
    primitives of that material get ``TEXCOORD_0`` from ``MeshData.face_uvs`` (every face of such a
    primitive must have UVs). Without textures the output has no images/textures/samplers/UVs.
    """
    gl: _GltfDocument = {"asset": {"version": "2.0", "generator": generator}, "scenes": [{"nodes": []}], "scene": 0,
          "nodes": [], "meshes": [], "accessors": [], "bufferViews": [], "materials": [], "buffers": []}
    if extras:
        gl["asset"]["extras"] = extras
    binbuf = bytearray()
    mat_index: dict[str, int] = {}
    image_index: dict[bytes, int] = {}

    def png_of(name: str) -> bytes | None:
        spec = materials.get(name, ((0.8, 0.8, 0.8), 0.9, 0.0))
        return spec[3] if len(spec) > 3 else None

    def texture(png: object) -> int:
        if not isinstance(png, (bytes, bytearray)):
            raise PackageError("glb: a material texture must be PNG bytes")
        png = bytes(png)
        if png not in image_index:
            if "samplers" not in gl:
                gl["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
                gl["images"], gl["textures"] = [], []
            gl["images"].append({"bufferView": add_view(png, None), "mimeType": "image/png"})
            gl["textures"].append({"sampler": 0, "source": len(gl["images"]) - 1})
            image_index[png] = len(gl["textures"]) - 1
        return image_index[png]

    def material(name: str) -> int:
        if name not in mat_index:
            rgb, rough, metal = materials.get(name, ((0.8, 0.8, 0.8), 0.9, 0.0))[:3]
            pbr: _GltfPbr = {"baseColorFactor": [rgb[0], rgb[1], rgb[2], 1.0], "metallicFactor": metal,
                             "roughnessFactor": rough}
            png = png_of(name)
            if png is not None:
                pbr["baseColorTexture"] = {"index": texture(png), "texCoord": 0}
            mat_index[name] = len(gl["materials"])
            gl["materials"].append({"name": name, "pbrMetallicRoughness": pbr})
        return mat_index[name]

    def add_view(data: bytes | bytearray, target: int | None) -> int:
        while len(binbuf) % 4:
            binbuf.append(0)
        view: _GltfBufferView = {"buffer": 0, "byteOffset": len(binbuf), "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        gl["bufferViews"].append(view)
        binbuf.extend(data)
        return len(gl["bufferViews"]) - 1

    def add_accessor(view: int, ctype: int, count: int, typ: str,
                     bounds: tuple[list[float], list[float]] | None = None) -> int:
        a: _GltfAccessor = {"bufferView": view, "componentType": ctype, "count": count, "type": typ}
        if bounds is not None:
            a["min"], a["max"] = bounds
        gl["accessors"].append(a)
        return len(gl["accessors"]) - 1

    mesh_ids: dict[int, int] = {}

    def mesh_index(md: MeshData) -> int:
        key = id(md)
        if key in mesh_ids:
            return mesh_ids[key]
        if not all(_finite3(v) for v in md.vertices):
            raise PackageError(f"glb: mesh #{len(gl['meshes'])} has a non-finite vertex")   # names not echoed
        prims: list[_GltfPrimitive] = []
        by_mat: dict[int, list[int]] = {}
        for f, mi in enumerate(md.face_materials):
            by_mat.setdefault(mi, []).append(f)
        if md.face_uvs is not None and len(md.face_uvs) != len(md.faces):
            raise PackageError(f"glb: mesh #{len(gl['meshes'])} face_uvs must be parallel to faces")
        for mi, flist in sorted(by_mat.items()):
            pos: list[float] = []
            col: list[float] = []
            nrm: list[float] = []
            uv: list[float] = []
            textured = png_of(md.materials[mi]) is not None
            for f in flist:
                face = md.faces[f]
                c = md.face_colors[f]
                fuv = md.face_uvs[f] if textured and md.face_uvs is not None else None
                if textured and (fuv is None or len(fuv) != len(face)
                                 or not all(len(q) == 2 and all(isinstance(x, (int, float)) and math.isfinite(x)
                                                                 for x in q) for q in fuv)):
                    raise PackageError(f"glb: mesh #{len(gl['meshes'])}: a face of a textured material lacks "
                                       "finite UVs")
                for k in range(1, len(face) - 1):
                    tri = [map_to_gltf(md.vertices[i]) for i in (face[0], face[k], face[k + 1])]
                    a, b, cc = tri
                    u = [b[i] - a[i] for i in range(3)]
                    v = [cc[i] - a[i] for i in range(3)]
                    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
                    ln = math.sqrt(sum(x * x for x in n))
                    n = [x / ln for x in n] if ln > 0 else [0.0, 1.0, 0.0]
                    for p in tri:
                        pos.extend(p)
                        col.extend(c)
                        nrm.extend(n)
                    if fuv is not None:  # textured: validated above
                        for ci in (0, k, k + 1):
                            uv.extend(fuv[ci])
            cnt = len(pos) // 3
            if cnt == 0:
                continue
            xs, ys, zs = pos[0::3], pos[1::3], pos[2::3]
            pa = add_accessor(add_view(_f32(pos), 34962), 5126, cnt, "VEC3",
                              ([min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]))
            na = add_accessor(add_view(_f32(nrm), 34962), 5126, cnt, "VEC3")
            ca = add_accessor(add_view(_f32(col), 34962), 5126, cnt, "VEC3")
            idx = struct.pack(f"<{cnt}I", *range(cnt))
            ia = add_accessor(add_view(idx, 34963), 5125, cnt, "SCALAR")
            attrs = {"POSITION": pa, "NORMAL": na, "COLOR_0": ca}
            if textured:
                attrs["TEXCOORD_0"] = add_accessor(add_view(_f32(uv), 34962), 5126, cnt, "VEC2")
            prim: _GltfPrimitive = {"attributes": attrs, "indices": ia,
                                    "material": material(md.materials[mi]), "mode": 4}
            if md.materials[mi] == DECOR_MATERIAL:
                prim["extras"] = {"mb_decor": True}
            prims.append(prim)
        gl["meshes"].append({"name": md.name, "primitives": prims})
        mesh_ids[key] = len(gl["meshes"]) - 1
        return mesh_ids[key]

    for ni, n in enumerate(nodes):
        rz = float(n.get("rotation_z", 0.0))
        sx, sy, sz = node_scale(n.get("scale", 1.0))
        loc = tuple(n.get("location", (0.0, 0.0, 0.0)))
        if not (_finite3(loc) and math.isfinite(rz) and all(math.isfinite(v) for v in (sx, sy, sz))):
            raise PackageError(f"glb: node #{ni} has a non-finite transform")
        node: _GltfNode = {"name": n["name"], "mesh": mesh_index(n["mesh"]),
                           "translation": list(map_to_gltf(loc))}
        if rz:
            # rotation about map +Z == rotation about glTF +Y by the same angle
            node["rotation"] = [0.0, math.sin(rz / 2), 0.0, math.cos(rz / 2)]
        if (sx, sy, sz) != (1.0, 1.0, 1.0):
            node["scale"] = [sx, sz, sy]  # glTF axes (x, z, -y): magnitudes along x, up, south
        node_extras = n.get("extras")
        if node_extras:
            node["extras"] = node_extras
        gl["nodes"].append(node)
        gl["scenes"][0]["nodes"].append(len(gl["nodes"]) - 1)
    while len(binbuf) % 4:
        binbuf.append(0)
    gl["buffers"].append({"byteLength": len(binbuf)})
    js = json.dumps(gl, separators=(",", ":"), allow_nan=False).encode("utf-8")
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binbuf)
    return (struct.pack("<III", GLB_MAGIC, 2, total) + struct.pack("<II", len(js), CHUNK_JSON) + js
            + struct.pack("<II", len(binbuf), CHUNK_BIN) + bytes(binbuf))


# --- reader -----------------------------------------------------------------

def _mat_mul(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Matrix:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _num_list(v: object, n: int, what: str) -> list[float]:
    if not (isinstance(v, list) and len(v) == n
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v)):
        raise PackageError(f"glb: {what} must be {n} finite numbers")
    return v


def _trs(node: Mapping[str, object]) -> Matrix:
    has_trs = any(k in node for k in ("translation", "rotation", "scale"))
    if "matrix" in node:
        if has_trs:
            raise PackageError("glb: node has both matrix and TRS")
        m = _num_list(node["matrix"], 16, "node matrix")
        if m[3] != 0 or m[7] != 0 or m[11] != 0 or m[15] != 1:
            raise PackageError("glb: node matrix is not affine")
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]  # column-major
    t = _num_list(node.get("translation", [0, 0, 0]), 3, "translation")
    x, y, z, w = _num_list(node.get("rotation", [0, 0, 0, 1]), 4, "rotation")
    if abs(math.sqrt(x * x + y * y + z * z + w * w) - 1.0) > QUAT_UNIT_TOL:
        raise PackageError("glb: rotation quaternion is not unit length")
    s = _num_list(node.get("scale", [1, 1, 1]), 3, "scale")
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[0][0] * s[0], r[0][1] * s[1], r[0][2] * s[2], t[0]],
            [r[1][0] * s[0], r[1][1] * s[1], r[1][2] * s[2], t[1]],
            [r[2][0] * s[0], r[2][1] * s[1], r[2][2] * s[2], t[2]],
            [0, 0, 0, 1]]


def det3(m: Sequence[Sequence[float]]) -> float:
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


class GlbNode:
    def __init__(self, index: int, name: str, extras: dict[str, object],
                 matrix: Matrix, triangles: list[tuple[Vec3, Vec3, Vec3]],
                 decor_triangles: list[tuple[Vec3, Vec3, Vec3]] | None = None) -> None:
        self.index: int = index
        self.name: str = name
        self.extras: dict[str, object] = extras
        self.matrix: Matrix = matrix
        # world-space glTF coords [(a, b, c)], front faces CCW (negative-determinant rule applied)
        self.triangles: list[tuple[Vec3, Vec3, Vec3]] = triangles
        # same space and winding rule, from ``MB Decor`` primitives only; never bound to collision
        self.decor_triangles: list[tuple[Vec3, Vec3, Vec3]] = decor_triangles or []


_CT: dict[int, tuple[str, int]] = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_NC: dict[str, int] = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_INDEX_TYPES: tuple[int, ...] = (5121, 5123, 5125)


def _is_index(v: object, n: int) -> TypeGuard[int]:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v < n


def _chunks(data: bytes) -> tuple[bytes, bytes | None]:
    if len(data) < 20:
        raise PackageError("glb: too short")
    magic, ver, length = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC or ver != 2:
        raise PackageError("glb: not a glTF 2.0 binary")
    if length != len(data):
        raise PackageError("glb: length header mismatch")
    o = 12
    chunks: list[tuple[int, bytes]] = []
    while o < len(data):
        if o + 8 > len(data):
            raise PackageError("glb: truncated chunk header")
        clen, ctype = struct.unpack_from("<II", data, o)
        o += 8
        if clen % 4 or o + clen > len(data):
            raise PackageError("glb: chunk is misaligned or overruns the file")
        chunks.append((ctype, data[o:o + clen]))
        o += clen
    if not chunks or chunks[0][0] != CHUNK_JSON:
        raise PackageError("glb: the first chunk must be JSON")
    binc: bytes | None = None
    if len(chunks) > 1 and chunks[1][0] == CHUNK_BIN:
        binc = bytes(chunks[1][1])
    if any(c[0] in (CHUNK_JSON, CHUNK_BIN) for c in chunks[1 + (binc is not None):]):
        raise PackageError("glb: unexpected extra JSON/BIN chunk")
    return bytes(chunks[0][1]), binc


def read_glb(data: bytes, max_bytes: int = MAX_GLB_BYTES,
             max_triangles: int = MAX_VISUAL_TRIANGLES) -> tuple[Gltf, list[GlbNode]]:
    """-> (gltf json, [GlbNode]) for every node reachable from the default scene."""
    if len(data) > max_bytes:
        raise PackageError("glb: file exceeds size limit")
    try:
        return _read_glb(data, max_triangles)
    except PackageError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, AttributeError, OverflowError, struct.error,
            RecursionError, MemoryError) as e:
        raise PackageError(f"glb: malformed ({type(e).__name__})") from None


def _read_glb(data: bytes, max_triangles: int) -> tuple[Gltf, list[GlbNode]]:
    js, binc = _chunks(data)
    gl = cast("Gltf", strict_json(js.rstrip(b" "), "glb: JSON chunk"))   # shape checked just below
    if not isinstance(gl, dict) or not isinstance(gl.get("asset"), dict) or gl["asset"].get("version") != "2.0":
        raise PackageError("glb: asset.version must be 2.0")
    if gl.get("extensionsRequired"):
        n = len(gl["extensionsRequired"]) if isinstance(gl["extensionsRequired"], list) else 1
        raise PackageError(f"glb: required extensions are not allowed ({n} listed)")   # names not echoed
    buffers = gl.get("buffers", [])
    if not isinstance(buffers, list) or len(buffers) > 1:
        raise PackageError("glb: at most one (GLB-stored) buffer is allowed")
    for b in buffers:
        if "uri" in b:
            raise PackageError("glb: external or data-URI buffers are not allowed in packages")
        if not _is_index(b.get("byteLength"), (len(binc) if binc is not None else 0) + 1) or (
                binc is not None and len(binc) - b["byteLength"] > 3):
            raise PackageError("glb: buffer byteLength does not match the BIN chunk")
    if buffers and binc is None:
        raise PackageError("glb: buffer declared without a BIN chunk")
    for im in gl.get("images", []):
        if isinstance(im, dict) and "uri" in im:
            raise PackageError("glb: external image URIs are not allowed in packages; embed textures")
    binc = binc or b""
    blen = buffers[0]["byteLength"] if buffers else 0
    views = gl.get("bufferViews", [])
    accessors = gl.get("accessors", [])
    if not isinstance(views, list) or not isinstance(accessors, list):
        raise PackageError("glb: bufferViews/accessors must be arrays")
    textured = _check_textures(gl, binc, blen, views, bool(buffers))
    budget: dict[str, int] = {"tris": 0}

    def read_flat(ai: object, want: Literal["position", "index", "uv"]) -> tuple[int, Sequence[float]]:
        """The accessor's components (flat) and the component count per element."""
        if not _is_index(ai, len(accessors)):
            raise PackageError("glb: bad accessor index")
        a = accessors[ai]
        if "sparse" in a:
            raise PackageError("glb: sparse accessors are not supported")
        ct = _CT.get(a.get("componentType"))
        nc = _NC.get(a.get("type"))
        if ct is None or nc is None:
            raise PackageError("glb: bad accessor type")
        fmt, size = ct
        if want == "position" and (a["componentType"] != 5126 or nc != 3 or a.get("normalized")):
            raise PackageError("glb: POSITION must be float32 VEC3")
        if want == "index" and (a["componentType"] not in _INDEX_TYPES or nc != 1):
            raise PackageError("glb: indices must be unsigned integer scalars")
        if want == "uv" and (a["componentType"] != 5126 or nc != 2 or a.get("normalized")):
            raise PackageError("glb: TEXCOORD_0 must be float32 VEC2")
        count = a.get("count")
        if not _is_index(count, len(binc) // (size * nc) + 1) or count < 1:
            raise PackageError("glb: accessor count is invalid or exceeds the buffer")
        if not _is_index(a.get("bufferView"), len(views)):
            raise PackageError("glb: accessor without a valid bufferView")
        v = views[a["bufferView"]]
        if v.get("buffer", 0) != 0 or not buffers:
            raise PackageError("glb: only buffer 0 (the BIN chunk) is supported")
        voff, vlen, aoff = v.get("byteOffset", 0), v.get("byteLength"), a.get("byteOffset", 0)
        if not (_is_index(voff, blen + 1) and _is_index(vlen, blen + 1) and voff + vlen <= blen
                and _is_index(aoff, vlen + 1) and aoff % size == 0):
            raise PackageError("glb: bufferView/accessor range is outside the buffer")
        elem = size * nc
        stride = v.get("byteStride", 0) or elem
        if not isinstance(stride, int) or stride < elem or stride > 252 or stride % 4 and "byteStride" in v:
            raise PackageError("glb: invalid byteStride")
        if aoff + stride * (count - 1) + elem > vlen:
            raise PackageError("glb: accessor overruns its bufferView")
        start = voff + aoff
        flat: Sequence[float]
        if stride == elem:
            flat = struct.unpack_from(f"<{count * nc}{fmt}", binc, start)
        else:
            strided: list[float] = []
            for k in range(count):
                strided.extend(struct.unpack_from(f"<{nc}{fmt}", binc, start + k * stride))
            flat = strided
        return nc, flat

    def read_indices(ai: object) -> list[int]:
        _, flat = read_flat(ai, "index")
        return cast("list[int]", list(flat))   # an unsigned integer scalar accessor was checked

    def read_vectors(ai: object, want: Literal["position", "uv"]) -> list[tuple[float, ...]]:
        nc, flat = read_flat(ai, want)
        return [tuple(flat[k:k + nc]) for k in range(0, len(flat), nc)]

    nodes_js = gl.get("nodes", [])
    meshes = gl.get("meshes", [])
    if not isinstance(nodes_js, list) or len(nodes_js) > MAX_NODES or not isinstance(meshes, list):
        raise PackageError("glb: nodes/meshes must be arrays within limits")
    for node in nodes_js:
        if not isinstance(node, dict):
            raise PackageError("glb: node must be an object")
        if "skin" in node or "weights" in node:
            raise PackageError("glb: skins and morph weights are not allowed in static maps")
    scenes = gl.get("scenes")
    if scenes:
        si = gl.get("scene", 0)
        if not _is_index(si, len(scenes)):
            raise PackageError("glb: bad default scene index")
        roots = scenes[si].get("nodes", [])
    else:
        roots = list(range(len(nodes_js)))
    result: list[GlbNode] = []
    ident: Matrix = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    stack: list[tuple[object, Matrix, int]] = [(n, ident, 0) for n in reversed(roots)]
    visited: set[int] = set()
    mesh_cache: dict[int, MeshTriangles] = {}
    decor = _decor_material_indices(gl)
    while stack:
        ni, parent, depth = stack.pop()
        if depth > MAX_DEPTH or not _is_index(ni, len(nodes_js)) or ni in visited:
            raise PackageError("glb: invalid node hierarchy (bad index, cycle, shared child or too deep)")
        visited.add(ni)
        node = nodes_js[ni]
        m = _mat_mul(parent, _trs(node))
        tris: list[tuple[Vec3, Vec3, Vec3]] = []
        decor_tris: list[tuple[Vec3, Vec3, Vec3]] = []
        if "mesh" in node:
            mi = node["mesh"]
            if not _is_index(mi, len(meshes)):
                raise PackageError("glb: bad mesh index")
            if mi in mesh_cache:  # instanced mesh: its triangles count again
                budget["tris"] += mesh_cache[mi].count
                if budget["tris"] > max_triangles:
                    raise PackageError(f"glb: more than {max_triangles} visual triangles")
            else:
                mesh_cache[mi] = _mesh_triangles(meshes[mi], read_vectors, read_indices, budget, max_triangles,
                                                 textured, len(gl.get("materials", ())), decor)
            flip = det3(m) < 0  # glTF: negative determinant means clockwise front faces

            def place(p: Vec3, m: Matrix = m) -> Vec3:
                return (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2] + m[0][3],
                        m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2] + m[1][3],
                        m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2] + m[2][3])

            for local, placed in ((mesh_cache[mi].solid, tris), (mesh_cache[mi].decor, decor_tris)):
                for a, b, c in local:
                    wa, wb, wc = place(a), place(b), place(c)
                    placed.append((wa, wc, wb) if flip else (wa, wb, wc))
        name = node.get("name", f"node{ni}")
        if not isinstance(name, str):
            raise PackageError("glb: node name must be a string")
        extras = node.get("extras", {})
        result.append(GlbNode(ni, name, extras if isinstance(extras, dict) else {}, m, tris, decor_tris))
        children = node.get("children", [])
        if not isinstance(children, list):
            raise PackageError("glb: node children must be an array")
        for c in reversed(children):
            stack.append((c, m, depth + 1))
    return gl, result


def _check_textures(gl: Gltf, binc: bytes, blen: int, views: list[object], has_buffer: bool) -> set[int]:
    """Validate images, samplers, textures and material bindings (PNG headers only, no decode).
    Returns the set of material indices that carry a baseColorTexture."""
    images = gl.get("images", [])
    textures = gl.get("textures", [])
    samplers = gl.get("samplers", [])
    materials = gl.get("materials", [])
    if not all(isinstance(x, list) for x in (images, textures, samplers, materials)):
        raise PackageError("glb: images/textures/samplers/materials must be arrays")
    total = 0
    for i, im in enumerate(images):
        if not isinstance(im, dict):
            raise PackageError(f"glb: image #{i} must be an object")
        if "uri" in im:
            raise PackageError("glb: external image URIs are not allowed in packages; embed textures")
        if im.get("mimeType") != "image/png":
            raise PackageError(f"glb: image #{i} must have mimeType image/png")
        v = im.get("bufferView")   # raw JSON index, validated below
        view = views[v] if has_buffer and _is_index(v, len(views)) else None
        if not isinstance(view, dict):
            raise PackageError(f"glb: image #{i} bufferView is missing or out of range")
        voff, vlen = view.get("byteOffset", 0), view.get("byteLength")
        if view.get("buffer", 0) != 0 or not (_is_index(voff, blen + 1) and _is_index(vlen, blen + 1)
                                              and voff + vlen <= blen and voff + vlen <= len(binc)):
            raise PackageError(f"glb: image #{i} bufferView points outside the BIN chunk")
        total += vlen
        if total > MAX_TEXTURE_BYTES:
            raise PackageError(f"glb: embedded images exceed {MAX_TEXTURE_BYTES} bytes in total")
        data = binc[voff:voff + vlen]
        if len(data) < 33 or data[:8] != PNG_SIGNATURE or data[8:16] != b"\x00\x00\x00\rIHDR":
            raise PackageError(f"glb: image #{i} is not a PNG (signature or IHDR mismatch)")
        w, h = struct.unpack_from(">II", data, 16)
        for side in (w, h):
            if side < 1 or side > MAX_TEXTURE_SIDE or side & (side - 1):
                raise PackageError(f"glb: image #{i} is {w}x{h}; each side must be a power of two "
                                   f"<= {MAX_TEXTURE_SIDE}")
    for i, s in enumerate(samplers):
        if not isinstance(s, dict):
            raise PackageError(f"glb: sampler #{i} must be an object")
    for i, t in enumerate(textures):
        if not isinstance(t, dict):
            raise PackageError(f"glb: texture #{i} must be an object")
        if not _is_index(t.get("source"), len(images)):
            raise PackageError(f"glb: texture #{i} source is missing or out of range")
        if "sampler" in t and not _is_index(t["sampler"], len(samplers)):
            raise PackageError(f"glb: texture #{i} sampler is out of range")
    textured: set[int] = set()
    for i, m in enumerate(materials):
        pbr = m.get("pbrMetallicRoughness") if isinstance(m, dict) else None
        bct = pbr.get("baseColorTexture") if isinstance(pbr, dict) else None
        if bct is None:
            continue
        if not isinstance(bct, dict) or not _is_index(bct.get("index"), len(textures)):
            raise PackageError(f"glb: material #{i} baseColorTexture.index is missing or out of range")
        tc = bct.get("texCoord", 0)
        if not isinstance(tc, int) or isinstance(tc, bool) or tc != 0:
            raise PackageError(f"glb: material #{i} baseColorTexture.texCoord must be 0")
        textured.add(i)
    return textured


def glb_image_sha256s(data: bytes) -> list[str]:
    """SHA-256 hex digests of the embedded images (call only on a GLB that passed :func:`read_glb`)."""
    import hashlib
    js, binc = _chunks(data)
    gl = cast("Gltf", strict_json(js.rstrip(b" "), "glb: JSON chunk"))   # already validated by read_glb
    out: list[str] = []
    for im in gl.get("images", []):
        v = gl["bufferViews"][im["bufferView"]]
        off = v.get("byteOffset", 0)
        out.append(hashlib.sha256((binc or b"")[off:off + v["byteLength"]]).hexdigest())
    return out


class MeshTriangles(NamedTuple):
    """Local-space triangles of one mesh, split into the ``MB Decor`` primitives and all others."""
    solid: list[tuple[Vec3, Vec3, Vec3]]
    decor: list[tuple[Vec3, Vec3, Vec3]]

    @property
    def count(self) -> int:
        return len(self.solid) + len(self.decor)


def _decor_material_indices(gl: Gltf) -> set[int]:
    return {i for i, m in enumerate(gl.get("materials", ())) if isinstance(m, dict) and m.get("name") == DECOR_MATERIAL}


def _mesh_triangles(mesh: object, read_vectors: Callable[[object, Literal["position", "uv"]], list[tuple[float, ...]]],
                    read_indices: Callable[[object], list[int]], budget: dict[str, int], max_triangles: int,
                    textured: Collection[int] = frozenset(),
                    n_materials: int = 0,
                    decor: Collection[int] = frozenset()) -> MeshTriangles:
    """Local-space triangles of a mesh (mode 4 only; points/lines carry no triangles)."""
    if not isinstance(mesh, dict) or not isinstance(mesh.get("primitives"), list):
        raise PackageError("glb: mesh without primitives")
    out = MeshTriangles([], [])
    for p in mesh["primitives"]:
        mode = p.get("mode", 4)
        if mode in (5, 6):
            raise PackageError("glb: triangle strips/fans are not supported; use mode 4 (TRIANGLES)")
        if mode not in (0, 1, 2, 3, 4):
            raise PackageError("glb: invalid primitive mode (expected an integer 0-6)")
        if p.get("targets"):
            raise PackageError("glb: morph targets are not allowed in static maps")
        pm = p.get("material")
        if "material" in p and (type(pm) is not int or not 0 <= pm < n_materials):
            raise PackageError("glb: primitive material index out of range")
        if mode != 4:
            continue
        pos = read_vectors(p["attributes"]["POSITION"], "position")
        if not all(math.isfinite(c) for q in pos for c in q):
            raise PackageError("glb: non-finite POSITION")
        if pm in textured:
            if "TEXCOORD_0" not in p["attributes"]:
                raise PackageError("glb: a textured primitive is missing TEXCOORD_0")
            uvs = read_vectors(p["attributes"]["TEXCOORD_0"], "uv")
            if len(uvs) != len(pos):
                raise PackageError("glb: TEXCOORD_0 count differs from POSITION count")
            if not all(math.isfinite(c) for q in uvs for c in q):
                raise PackageError("glb: non-finite TEXCOORD_0")
        idx = read_indices(p["indices"]) if "indices" in p else list(range(len(pos)))
        if len(idx) % 3:
            raise PackageError("glb: triangle index count is not a multiple of 3")
        if idx and max(idx) >= len(pos):
            raise PackageError("glb: index out of range")
        budget["tris"] += len(idx) // 3
        if budget["tris"] > max_triangles:
            raise PackageError(f"glb: more than {max_triangles} visual triangles")
        (out.decor if pm in decor else out.solid).extend(
            (cast(Vec3, pos[idx[k]]), cast(Vec3, pos[idx[k + 1]]), cast(Vec3, pos[idx[k + 2]]))   # POSITION is VEC3
            for k in range(0, len(idx), 3))
    return out
