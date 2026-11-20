# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Plain mesh container shared by generation, export and tests."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

Vec3 = tuple[float, float, float]
UV = tuple[float, float]


class MeshData:
    """Polygon mesh in object-local coordinates (map-frame axes).

    ``faces`` are tuples of vertex indices, CCW when seen from outside.
    ``face_materials`` indexes into ``materials`` (material spec names) and
    ``face_colors`` holds an (r, g, b) linear colour per face.
    ``face_uvs`` is ``None`` (no UVs) or a list parallel to ``faces`` whose entries are either
    ``None`` or one (u, v) pair per face corner (glTF convention, v down from the image top).
    UVs are per corner, so faces sharing a vertex may carry different UVs.
    """

    grid_layout: tuple[int, int, float, float, float]   # (nx, ny, x0, y0, spacing); set on the terrain mesh only

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.vertices: list[Vec3] = []
        self.faces: list[tuple[int, ...]] = []
        self.face_materials: list[int] = []
        self.face_colors: list[tuple[float, ...]] = []
        self.materials: list[str] = []
        self.face_uvs: list[tuple[UV, ...] | None] | None = None

    def material_index(self, name: str) -> int:
        if name not in self.materials:
            self.materials.append(name)
        return self.materials.index(name)

    def add_vertex(self, x: float, y: float, z: float) -> int:
        self.vertices.append((float(x), float(y), float(z)))
        return len(self.vertices) - 1

    def add_face(self, idx: Sequence[int], material: str, color: Sequence[float],
                 uvs: Sequence[Sequence[float]] | None = None) -> None:
        """``uvs``: optional (u, v) per corner of ``idx``."""
        if uvs is not None and len(uvs) != len(idx):
            raise ValueError("uvs must have one (u, v) per face corner")
        if uvs is not None and self.face_uvs is None:
            self.face_uvs = [None] * len(self.faces)
        self.faces.append(tuple(idx))
        self.face_materials.append(self.material_index(material))
        self.face_colors.append(tuple(color))
        if self.face_uvs is not None:
            self.face_uvs.append(None if uvs is None else tuple((float(u), float(v)) for u, v in uvs))

    def triangles(self) -> Iterator[tuple[int, int, int]]:
        """Fan-triangulated faces. Every face with more than 3 vertices that the generator
        emits is planar (within 1e-6 m) and convex; non-planar candidates are emitted as
        explicit triangles instead (see generate._add_planar_face), so the fan never
        changes the surface."""
        for f in self.faces:
            for k in range(1, len(f) - 1):
                yield (f[0], f[k], f[k + 1])


def transform_point(p: Sequence[float], location: Sequence[float] = (0.0, 0.0, 0.0),
                    rotation_z: float = 0.0, scale: float = 1.0) -> Vec3:
    import math
    c, s = math.cos(rotation_z), math.sin(rotation_z)
    x, y, z = p[0] * scale, p[1] * scale, p[2] * scale
    return (c * x - s * y + location[0], s * x + c * y + location[1], z + location[2])
