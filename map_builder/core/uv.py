"""World-scaled UV assignment for textured export (S3-TEX-UV-CORE, D57/D59).

UVs are assigned after generation, from the final mesh only, so ``generate.py`` and ``roofs.py`` are not
involved. UV = metres / tile size (``core/textures.py``). Each mesh gets one tile offset
``o = tile * floor(origin / tile)`` per axis (``origin`` = the mesh's world origin), subtracted before scaling,
so UVs stay small (float32-safe) and are continuous across the shared edges of one mesh.

========================  =====================================  ==========================
Material                  U                                      V
========================  =====================================  ==========================
MB Facade, walls          cumulative perimeter distance along    (z - wall base z) / tile;
                          the footprint ring from ring vertex 0  the base is the datum z = 0
MB Facade, gable ends     the U of the wall below them           (z - wall base z) / tile
MB Facade, other faces    world X (the buried foundation cap)    world Y
MB Roof / MB Roof Flat    along the slope's eave (horizontal)    up-slope distance, one basis and
                                                                 datum per connected coplanar slope
MB Terrain, MB Road       world X                                world Y
MB Concrete, MB Tunnel    box projection, dominant normal axis   box projection
others                    untextured: no UVs
========================  =====================================  ==========================

Seams (UVs differ across a shared edge): one per footprint ring at ring vertex 0 (U jumps by the perimeter),
the ring bottom edges against the foundation cap, the hips and ridges between roof planes, and the edges where a
box-projected face changes its dominant axis. Only geometry is read; the mesh is assumed to be placed by a pure
translation (``origin``), which is what the generator emits for every textured material.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import TypeAlias

from . import textures
from .mesh import UV, MeshData, Vec3

TOL = 1e-6
UNTEXTURED = ("MB Probe", "MB Foliage", "MB Bark", "MB Default")

WallSegment: TypeAlias = "tuple[float, float, float, float, float, float]"   # ax, ay, bx, by, cumulative U, length
RoofFace: TypeAlias = "tuple[int, list[Vec3], Vec3, float]"   # material index, points, normal, tile
FaceUV: TypeAlias = "tuple[UV, ...] | None"


def _normal(pts: Sequence[Sequence[float]]) -> Vec3 | None:
    """Unit normal of a polygon by Newell's method, or None for a degenerate one."""
    nx = ny = nz = 0.0
    for k, p in enumerate(pts):
        q = pts[(k + 1) % len(pts)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    return None if ln < 1e-12 else (nx / ln, ny / ln, nz / ln)


# Mean linear albedo of each committed texture (re-derived by tests/test_uv.py). The texture already carries
# the material's colour, so the per-face COLOR_0 (palette / building:colour / landcover) is divided by it:
# the textured face averages to the colour it had untextured, with the texture's detail on top, instead of
# being darkened by a second multiplication. Channels that would exceed 1 are clamped (COLOR_0 is <= 1).
TEXTURE_MEAN_ALBEDO = {
    "MB Facade": (0.55, 0.503, 0.424),
    "MB Roof": (0.257, 0.045, 0.02),
    "MB Roof Flat": (0.263, 0.248, 0.22),
    "MB Road": (0.042, 0.042, 0.045),
    "MB Terrain": (0.161, 0.196, 0.05),
    "MB Concrete": (0.389, 0.379, 0.35),
    "MB Tunnel": (0.389, 0.379, 0.35),
}


def compensated_color(material: str, color: Sequence[float]) -> tuple[float, ...]:
    """COLOR_0 for a face of a textured ``material`` (see :data:`TEXTURE_MEAN_ALBEDO`)."""
    mean = TEXTURE_MEAN_ALBEDO[material]
    return tuple(min(1.0, c / m) for c, m in zip(color, mean))


def tile_offset(origin: Sequence[float], tile: float) -> tuple[float, ...]:
    return tuple(tile * math.floor(c / tile) for c in origin)


def _wall_segments(mesh: MeshData) -> tuple[list[WallSegment], dict[int, tuple[float, float]], float | None]:
    """Wall ring segments (ax, ay, bx, by, cumulative U at a, length), the face -> (U at a, U at b) of each wall
    quad, and the wall base z, read from the leading run of facade wall quads ``(rb[k], rb[j], rt[j], rt[k])``
    the generator emits. ``([], {}, None)`` if none."""
    try:
        facade = mesh.materials.index("MB Facade")
    except ValueError:
        return [], {}, None
    v = mesh.vertices
    segs: list[WallSegment] = []
    quads: dict[int, tuple[float, float]] = {}
    base: float | None = None
    ring_start: int | None = None
    prev_end: int | None = None
    cum = 0.0
    for fi, (f, m) in enumerate(zip(mesh.faces, mesh.face_materials)):
        if m != facade or len(f) != 4:
            break
        a, b, c, d = f
        if not (a % 2 == 0 and d == a + 1 and c == b + 1 and v[a][:2] == v[d][:2] and v[b][:2] == v[c][:2]
                and v[d][2] >= v[a][2]):
            break
        if ring_start is None or prev_end != a:
            ring_start, cum = a, 0.0
        length = math.hypot(v[b][0] - v[a][0], v[b][1] - v[a][1])
        segs.append((v[a][0], v[a][1], v[b][0], v[b][1], cum, length))
        quads[fi] = (cum, cum + length)
        cum += length
        base = v[a][2] if base is None else min(base, v[a][2])
        prev_end = None if b == ring_start else b
    # the generator's local z = 0 is the base datum and the walls sink below it into the ground; V counts from
    # the datum, or from the wall bottom when the volume is elevated
    return segs, quads, (None if base is None else max(base, 0.0))


def _wall_u(segs: Sequence[WallSegment], pts: Sequence[Vec3], n: Vec3) -> list[float] | None:
    """U (metres) of each point of a vertical face with horizontal normal ``n``, measured along the single wall
    segment that is parallel to the face and contains all of its points; None if there is no such segment.
    Choosing the segment per face (not per point) keeps a corner on the segment that owns the face. A gable
    triangle whose apex lies beyond its base segment (a collinear split of the wall run) is owned by the segment
    that contains its base, and the apex is projected along the same supporting line."""
    for strict in (True, False):
        for ax, ay, bx, by, cum, length in segs:
            if length < TOL:
                continue
            dx, dy = (bx - ax) / length, (by - ay) / length
            if abs(dx * n[0] + dy * n[1]) > 1e-4:
                continue
            low = min(p[2] for p in pts)
            us = []
            for p in pts:
                t = (p[0] - ax) * dx + (p[1] - ay) * dy
                off = abs(-(p[0] - ax) * dy + (p[1] - ay) * dx)
                inside = -1e-4 <= t <= length + 1e-4
                if off > 1e-4 or not (inside or (not strict and p[2] > low + 1e-6)):
                    break
                us.append(cum + t)
            else:
                return us
    return None


def _box_uv(p: Vec3, n: Vec3) -> UV:
    ax = max(range(3), key=lambda i: abs(n[i]))
    i, j = [(1, 2), (0, 2), (0, 1)][ax]
    return p[i], p[j]


def assign_uvs(mesh: MeshData, origin: Vec3 = (0.0, 0.0, 0.0)) -> MeshData:
    """Set ``mesh.face_uvs`` (one (u, v) per corner for faces of textured materials, ``None`` otherwise).

    ``origin`` is the mesh's world origin (the object location). Meshes without a textured material keep
    ``face_uvs = None``. Returns the mesh."""
    names = mesh.materials
    tile = [textures.tile_size(n) if n in textures.TEXTURES else None for n in names]
    if all(t is None for t in tile):
        mesh.face_uvs = None
        return mesh
    segs, quads, base_z = _wall_segments(mesh) if "MB Facade" in names else ([], {}, None)
    roof_faces: dict[int, RoofFace] = {}
    uvs: list[FaceUV] = []
    for fi, (f, mi) in enumerate(zip(mesh.faces, mesh.face_materials)):
        name, t = names[mi], tile[mi]
        pts = [mesh.vertices[i] for i in f]
        n = _normal(pts) or (0.0, 0.0, 1.0)
        if t is None:
            uvs.append(None)
            continue
        off = tile_offset(origin, t)
        world = [(p[0] + origin[0] - off[0], p[1] + origin[1] - off[1], p[2] + origin[2] - off[2]) for p in pts]
        if name == "MB Facade" and abs(n[2]) < 1e-3 and base_z is not None:
            us: Sequence[float] | None
            if fi in quads:
                ua, ub = quads[fi]
                us = (ua, ub, ub, ua)
            else:
                us = _wall_u(segs, pts, n)
            if us is not None:
                uvs.append(tuple((u / t, (p[2] - base_z) / t) for u, p in zip(us, pts)))
                continue
        if name in ("MB Roof", "MB Roof Flat"):
            roof_faces[fi] = (mi, pts, n, t)
            uvs.append(None)
            continue
        if name in ("MB Terrain", "MB Road") or (name == "MB Facade"):
            uvs.append(tuple((w[0] / t, w[1] / t) for w in world))
        else:
            uvs.append(tuple((lambda uv: (uv[0] / t, uv[1] / t))(_box_uv(w, n)) for w in world))
    _roof_uvs(roof_faces, uvs)
    mesh.face_uvs = uvs
    return mesh


COPLANAR_DOT = 1.0 - 1e-6   # about 0.08 degrees between adjacent faces of one slope


def _roof_slopes(roof_faces: dict[int, RoofFace]) -> Iterable[list[int]]:
    """Group roof faces into slopes: faces of one material that share an edge (same endpoint positions) and are
    coplanar within :data:`COPLANAR_DOT`. Connectivity, not rounded plane keys, so a slope triangulated into many
    faces whose normals differ by float noise is still one slope."""
    parent = {fi: fi for fi in roof_faces}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    edges: dict[tuple[int, frozenset[tuple[float, ...]]], list[int]] = {}
    for fi, (mi, pts, n, _) in roof_faces.items():
        keys = [tuple(round(c, 5) for c in p) for p in pts]
        for k in range(len(keys)):
            edge = (mi, frozenset((keys[k], keys[(k + 1) % len(keys)])))
            for other in edges.setdefault(edge, []):
                on = roof_faces[other][2]
                if sum(a * b for a, b in zip(n, on)) >= COPLANAR_DOT:
                    parent[find(fi)] = find(other)
            edges[edge].append(fi)
    groups: dict[int, list[int]] = {}
    for fi in roof_faces:
        groups.setdefault(find(fi), []).append(fi)
    return groups.values()


def _roof_uvs(roof_faces: dict[int, RoofFace], uvs: list[FaceUV]) -> None:
    """One basis and datum per slope: U along the eave (horizontal), V up the slope, both from the slope's
    mean normal and its minimum corner."""
    for faces in _roof_slopes(roof_faces):
        sx = sy = sz = 0.0
        for fi in faces:
            n = roof_faces[fi][2]
            sx, sy, sz = sx + n[0], sy + n[1], sz + n[2]
        ln = math.sqrt(sx * sx + sy * sy + sz * sz)
        n = (sx / ln, sy / ln, sz / ln)
        h = math.hypot(n[0], n[1])
        if h < 1e-6:
            e, s = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
        else:
            e = (-n[1] / h, n[0] / h, 0.0)
            s = (-n[2] * n[0] / h, -n[2] * n[1] / h, h)
        proj = {fi: ([sum(a * b for a, b in zip(e, p)) for p in roof_faces[fi][1]],
                     [sum(a * b for a, b in zip(s, p)) for p in roof_faces[fi][1]]) for fi in faces}
        u0 = min(min(cu) for cu, _ in proj.values())
        v0 = min(min(cv) for _, cv in proj.values())
        for fi in faces:
            t = roof_faces[fi][3]
            cu, cv = proj[fi]
            uvs[fi] = tuple(((a - u0) / t, (b - v0) / t) for a, b in zip(cu, cv))


def textured_copy(mesh: MeshData, origin: Vec3 = (0.0, 0.0, 0.0)) -> MeshData:
    """A copy of ``mesh`` for the visual export: UVs assigned and COLOR_0 compensated for textured faces.
    The plan's mesh (shared with collision and the Blender scene) is not modified."""
    out = MeshData(mesh.name)
    out.vertices, out.faces = mesh.vertices, mesh.faces
    out.face_materials, out.materials = mesh.face_materials, mesh.materials
    out.face_colors = [compensated_color(mesh.materials[m], c) if mesh.materials[m] in TEXTURE_MEAN_ALBEDO else c
                       for m, c in zip(mesh.face_materials, mesh.face_colors)]
    return assign_uvs(out, origin)


def textured_materials(meshes: Iterable[MeshData]) -> list[str]:
    """Names of the textured materials used by ``meshes``."""
    return sorted({n for m in meshes for n in m.materials if n in textures.TEXTURES})
