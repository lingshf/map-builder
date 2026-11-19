"""Pure (bpy-free) baking of evaluated Blender geometry into package geometry.

The Blender layer (``export.py``) reads each exported object's depsgraph-evaluated mesh (modifiers
applied), its loop triangles and its world matrix, and hands them to :func:`bake_object`. Everything
from there on is plain Python and unit-tested without Blender (tests/test_blender_bake.py).

GLB generation decision
-----------------------
The visual GLB is written by :func:`map_builder.core.glb.write_glb` from exactly the same world-space
triangles that go to collision, NOT by ``bpy.ops.export_scene.gltf``:

* The core exporter refuses to publish unless each node's visual and collision triangles correspond
  one-to-one with the same winding (``write_package`` validates in strict mode). Building both from one
  list of world-space triangles makes that correspondence hold by construction: same vertices (the same
  float64 values rounded once to float32 in both files), same triangulation, same index order.
* The Blender glTF exporter adds independent variance that could break the binding: its own
  triangulation of n-gons, axis conversion (``export_yup``), how it splits/merges primitives, applying
  modifiers only with ``export_apply``, and the negative-determinant (mirrored) rule. A mirrored object
  would be written as a node with a negative-determinant TRS whose winding the consumer must flip; this
  module instead bakes the world matrix into the vertices and reverses the triangle order when
  det(M) < 0, so visuals and collision carry the same CCW-outward triangles and every glTF node has an
  identity transform (no negative determinant anywhere in the GLB).
* It also selects/activates nothing, so export never touches the user's selection or active object.

Costs, accepted for v1: visuals are flat-shaded (face normals) with PBR factors (base colour, roughness,
metallic) per material plus per-triangle vertex colours (COLOR_0) from a colour attribute; textures, UVs,
custom normals and node networks beyond a Principled BSDF are not exported (reported as warnings).
Instanced meshes (e.g. trees sharing one mesh) are written once per object.
"""

import math

from ..core import GENERATOR_VERSION
from ..core.collision import MAX_ABS_COORD_M, ColObject, count_degenerate
from ..core.errors import MapBuilderError
from ..core.glb import write_glb
from ..core.mesh import MeshData
from ..core.pipeline import export_package, resolve_identities

DEFAULT_MATERIAL = "MB Default"
DEFAULT_MATERIAL_SPEC = ((0.8, 0.8, 0.8), 0.9, 0.0)
WHITE = (1.0, 1.0, 1.0)
MIN_AXIS_SCALE = 1e-6        # a world-matrix column shorter than this is a zero scale on that axis
MIN_DET_RATIO = 1e-9         # |det| / product of column lengths below this: singular (flattening) transform
AFFINE_TOL = 1e-6


class ExportError(MapBuilderError):
    """Blocking problems found before anything is written; the previous package is kept."""

    def __init__(self, errors):
        super().__init__("export blocked (previous package kept):\n- " + "\n- ".join(errors))
        self.errors = list(errors)


class BakedObject:
    """World-space (map frame) triangles of one exported object, CCW seen from outside."""

    def __init__(self, name, mb_id, mb_class, vertices, triangles, tri_materials, tri_colors, provenance=None,
                 mirrored=False):
        self.name = name
        self.mb_id = mb_id
        self.mb_class = mb_class
        self.vertices = vertices
        self.triangles = triangles
        self.tri_materials = tri_materials
        self.tri_colors = tri_colors
        self.provenance = provenance or {}
        self.mirrored = mirrored
        self.unused_vertices = 0


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def transform_problem(matrix):
    """None if ``matrix`` (4x4, row-major nested sequence) is a usable world matrix, else the reason."""
    try:
        rows = [[float(c) for c in r] for r in matrix]
    except (TypeError, ValueError):
        return "world matrix is not numeric"
    if len(rows) != 4 or any(len(r) != 4 for r in rows):
        return "world matrix is not 4x4"
    if not all(math.isfinite(c) for r in rows for c in r):
        return "world matrix has non-finite values (NaN or infinity in location, rotation or scale)"
    if any(abs(rows[3][k] - (0.0, 0.0, 0.0, 1.0)[k]) > AFFINE_TOL for k in range(4)):
        return "world matrix is not affine (projective transforms are not supported)"
    cols = [math.sqrt(sum(rows[r][c] ** 2 for r in range(3))) for c in range(3)]
    if min(cols) < MIN_AXIS_SCALE:
        return ("zero scale: the world transform collapses an axis (check the object's and its parents' "
                "scale); collision cannot be built from flattened geometry")
    if abs(det3(rows)) < MIN_DET_RATIO * cols[0] * cols[1] * cols[2]:
        return "singular world transform (a shear or parent scale collapses the object to a plane or line)"
    return None


def det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def bake_object(name, local_vertices, triangles, matrix, tri_materials=None, tri_colors=None, mb_id=None,
                mb_class=None, provenance=None):
    """Bake an evaluated mesh into world space.

    ``local_vertices``: [(x, y, z)] object-space positions of the evaluated mesh; ``triangles``: index
    triples in the mesh's own order (CCW outward in object space); ``matrix``: 4x4 world matrix rows.
    A mirroring matrix (det < 0) reverses each triangle so front faces stay CCW outward in world space.
    Raises ExportError naming the object for non-finite input, out-of-range indices, a zero-scale or
    singular transform, or coordinates beyond the collision format's range."""
    problem = transform_problem(matrix)
    if problem:
        raise ExportError([f"{name}: {problem}"])
    m = [[float(c) for c in r] for r in matrix]
    n = len(local_vertices)
    world = []
    for p in local_vertices:
        x, y, z = p
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            raise ExportError([f"{name}: evaluated mesh has non-finite vertex coordinates (NaN or infinity)"])
        q = (m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
             m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
             m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3])
        if not all(math.isfinite(c) and abs(c) <= MAX_ABS_COORD_M for c in q):
            raise ExportError([f"{name}: world-space vertex is non-finite or beyond {MAX_ABS_COORD_M:g} m"])
        world.append(q)
    tris = []
    for t in triangles:
        a, b, c = (int(i) for i in t)
        if not (0 <= a < n and 0 <= b < n and 0 <= c < n):
            raise ExportError([f"{name}: triangle vertex index out of range (invalid mesh; run Mesh > Clean Up)"])
        tris.append((a, b, c))
    mirrored = det3(m) < 0
    if mirrored:
        tris = [(a, c, b) for a, b, c in tris]
    # keep only vertices that triangles use (loose vertices/edges have no surface)
    used = sorted({i for t in tris for i in t})
    unused = n - len(used)
    if unused:
        remap = {old: new for new, old in enumerate(used)}
        world = [world[i] for i in used]
        tris = [(remap[a], remap[b], remap[c]) for a, b, c in tris]
    k = len(tris)
    mats = list(tri_materials) if tri_materials is not None else [DEFAULT_MATERIAL] * k
    cols = [tuple(float(v) for v in c) for c in tri_colors] if tri_colors is not None else [WHITE] * k
    if len(mats) != k or len(cols) != k:
        raise ExportError([f"{name}: per-triangle material/colour lists do not match the triangle count"])
    if not all(len(c) == 3 and all(math.isfinite(v) for v in c) for c in cols):
        raise ExportError([f"{name}: non-finite vertex colour"])
    baked = BakedObject(name, mb_id, mb_class, world, tris, mats, cols, provenance, mirrored)
    baked.unused_vertices = unused
    return baked


def degenerate_count(obj):
    v = obj.vertices
    return count_degenerate((v[a], v[b], v[c]) for a, b, c in obj.triangles)


def outside_area(obj, area, margin_m=1.0):
    """True if any vertex lies outside the area rectangle (plus margin) in XY."""
    hx, hy = area.half
    return any(abs(p[0]) > hx + margin_m or abs(p[1]) > hy + margin_m for p in obj.vertices)


def export_name_clashes(entries):
    """Blocking errors for distinct objects that would share an export name.

    ``entries``: [(export name, unambiguous label)] with one entry per *distinct* object (the caller
    deduplicates by object identity, not by name). Blender lets a linked library object and a local
    object share ``name`` (their ``name_full`` differs by the library); export names bind glTF nodes to
    collision objects and derive identities (docs/PACKAGE_FORMAT.md), so such a clash blocks the export
    instead of dropping or silently renaming one of them."""
    by_name = {}
    for name, label in entries:
        by_name.setdefault(name, []).append(label)
    return [f"{len(labels)} objects share the export name {name!r}: " + ", ".join(repr(x) for x in sorted(labels))
            + "; export names must be unique (they bind glTF nodes to collision objects and form identities). "
              "Rename the local object, or make the linked one local and rename it"
            for name, labels in sorted(by_name.items()) if len(labels) > 1]


# Principled BSDF inputs the package carries (Base Color as a constant or a colour attribute, Roughness and
# Metallic as constants) or already reports on their own (Alpha: transparency).
PRINCIPLED_HANDLED = frozenset({"Base Color", "Roughness", "Metallic", "Alpha"})
# (input, effect) whose non-zero value or link is a visible effect the package cannot carry
PRINCIPLED_WEIGHTS = (("Subsurface Weight", "subsurface scattering"), ("Transmission Weight", "transmission"),
                      ("Coat Weight", "coat"), ("Sheen Weight", "sheen"), ("Anisotropic", "anisotropic specular"),
                      ("Thin Film Thickness", "thin film"))
PRINCIPLED_NORMALS = (("Normal", "normal/bump map (Normal input)"), ("Coat Normal", "coat normal/bump map"),
                      ("Tangent", "custom tangent (Tangent input)"))


def principled_omissions(inputs):
    """Effects of a Principled BSDF that the export omits, in a fixed order.

    ``inputs``: {socket name: (is_linked, default value)} of the enabled inputs (Blender 4.x names; a
    value is a float or a colour/vector tuple). Reported: emission (colour x strength non-zero, or either
    input linked), non-zero or linked subsurface/transmission/coat/sheen/anisotropic/thin-film weights,
    linked Normal/Coat Normal/Tangent, and any other linked input outside :data:`PRINCIPLED_HANDLED`."""
    out, covered = [], set(PRINCIPLED_HANDLED)

    def linked(name):
        return bool(inputs.get(name, (False, None))[0])

    def number(name):
        v = inputs.get(name, (False, 0.0))[1]
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    covered.update(("Emission Color", "Emission Strength"))
    color = inputs.get("Emission Color", (False, (0.0, 0.0, 0.0)))[1]
    try:
        glow = number("Emission Strength") * max(float(c) for c in tuple(color)[:3])
    except (TypeError, ValueError):
        glow = 0.0
    if linked("Emission Color") or linked("Emission Strength") or glow != 0.0:
        out.append("emission")
    for name, effect in PRINCIPLED_WEIGHTS:
        covered.add(name)
        if linked(name) or number(name) != 0.0:
            out.append(effect)
    for name, effect in PRINCIPLED_NORMALS:
        covered.add(name)
        if linked(name):
            out.append(effect)
    out += [f"{name} driven by nodes" for name in sorted(inputs) if name not in covered and linked(name)]
    return out


def _provenance(obj, mb_id, edits_dup):
    if mb_id.startswith("user:"):
        return {"source": "user-added in Blender (no generated identity)"}
    prov = dict(obj.provenance or {})
    src = edits_dup.get(obj.name)
    if src is not None:
        prov["edit"] = f"duplicate of {src} made in Blender"
    return prov


def package_parts(baked, generated_ids, materials):
    """(glb bytes, [ColObject], object_info, edits) from baked objects. Identities follow
    docs/PACKAGE_FORMAT.md via :func:`resolve_identities`; each glTF node and its collision object are
    built from the same world-space triangles (identity node transform)."""
    if not baked:
        raise ExportError(["nothing to export: no visible mesh objects with faces in the map collection"])
    resolved, edits = resolve_identities([(b.name, b.mb_id, b.mb_class) for b in baked], generated_ids)
    by_name = {b.name: b for b in baked}
    dup = {d["object"]: d["source_id"] for d in edits["duplicated"]}
    mats = {DEFAULT_MATERIAL: DEFAULT_MATERIAL_SPEC}
    mats.update(materials or {})
    nodes, cols, info = [], [], {}
    for name, mb_id, cls in resolved:
        b = by_name[name]
        if not b.triangles:
            raise ExportError([f"{name}: no triangles to export"])
        md = MeshData(name)
        md.vertices = b.vertices
        for t, mat, col in zip(b.triangles, b.tri_materials, b.tri_colors):
            md.add_face(t, mat if mat in mats else DEFAULT_MATERIAL, col)
        nodes.append({"name": name, "mesh": md, "extras": {"mb_id": mb_id, "mb_class": cls}})
        cols.append(ColObject(name, mb_id, cls, b.vertices, b.triangles))
        info[name] = {"provenance": _provenance(b, mb_id, dup)}
    glb = write_glb(nodes, mats, generator=f"map-builder {GENERATOR_VERSION} (Blender add-on)")
    return glb, cols, info, edits


def export_baked(path, name, area, sources, baked, generated_ids, materials, report, blender_version=None,
                 heightfield_spacing=None, created_utc=None, passage_probes=()):
    """Write the package atomically (core ``write_package``: a failed write keeps the previous file).
    ``passage_probes`` come from the plan; a probe whose feature mb_id is among ``generated_ids`` (the
    original plan) but no longer among the exported objects is dropped and its id listed in report.json
    ``passage_probes_dropped``; a malformed probe (including None, an explicit JSON null in the scene
    metadata) or one naming an unknown feature raises PackageError.
    Returns (manifest, ValidationResult, edits)."""
    glb, cols, info, edits = package_parts(baked, generated_ids, materials)
    manifest, result = export_package(path, name, area, sources, glb, cols, report, edits=edits,
                                      blender_version=blender_version, heightfield_spacing=heightfield_spacing,
                                      object_info=info, created_utc=created_utc, passage_probes=passage_probes,
                                      plan_ids=generated_ids)
    return manifest, result, edits
