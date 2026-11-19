"""Plain mesh container shared by generation, export and tests."""


class MeshData:
    """Polygon mesh in object-local coordinates (map-frame axes).

    ``faces`` are tuples of vertex indices, CCW when seen from outside.
    ``face_materials`` indexes into ``materials`` (material spec names) and
    ``face_colors`` holds an (r, g, b) linear colour per face.
    """

    def __init__(self, name):
        self.name = name
        self.vertices = []
        self.faces = []
        self.face_materials = []
        self.face_colors = []
        self.materials = []

    def material_index(self, name):
        if name not in self.materials:
            self.materials.append(name)
        return self.materials.index(name)

    def add_vertex(self, x, y, z):
        self.vertices.append((float(x), float(y), float(z)))
        return len(self.vertices) - 1

    def add_face(self, idx, material, color):
        self.faces.append(tuple(idx))
        self.face_materials.append(self.material_index(material))
        self.face_colors.append(tuple(color))

    def triangles(self):
        """Fan-triangulated faces. Every face with more than 3 vertices that the generator
        emits is planar (within 1e-6 m) and convex; non-planar candidates are emitted as
        explicit triangles instead (see generate._add_planar_face), so the fan never
        changes the surface."""
        for f in self.faces:
            for k in range(1, len(f) - 1):
                yield (f[0], f[k], f[k + 1])


def transform_point(p, location=(0.0, 0.0, 0.0), rotation_z=0.0, scale=1.0):
    import math
    c, s = math.cos(rotation_z), math.sin(rotation_z)
    x, y, z = p[0] * scale, p[1] * scale, p[2] * scale
    return (c * x - s * y + location[0], s * x + c * y + location[1], z + location[2])
