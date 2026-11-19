"""Turn classified features + elevation into an editable scene plan.

The plan is plain data (no bpy). The Blender layer instantiates it; tests use
it directly. Every generated object records provenance: which values were
*measured/provided* by a source and which were *inferred* defaults. When a
source value cannot be used as given, provenance keeps the source value, the
built value and the reason separately (``<key>_source``, ``<key>_m``,
``<key>_reason``); the built value is then labelled ``fallback:``.

Terrain heights everywhere (buildings, roads, vegetation) come from
:func:`terrain_height`, which evaluates exactly the piecewise-planar surface of
the emitted terrain mesh.

Resource bounds (see :class:`PlanOptions`): cumulative scene vertex/triangle
budgets are checked *before* each object is allocated, from an upper-bound
estimate. Exceeding them is a hard :class:`LimitError` naming the feature, so a
plan is never silently incomplete. Per-feature limits (ring vertices,
triangulation work) instead reject just that feature and report it in
``invalid_features``.
"""

import hashlib
import math
import random
import re

from .errors import LimitError, MapBuilderError
from .mesh import MeshData
from .triangulate import DEFAULT_MAX_WORK, TriangulationError, dedupe_ring, triangulate

LEVEL_HEIGHT_M = 3.0
FOUNDATION_SINK_M = 0.3
ROAD_LIFT_M = 0.12
MIN_WALL_M = 0.5
MAX_RING_VERTICES = 2000
# ~1 km2 at the finest 1 m terrain spacing is ~1M vertices / 2M triangles of terrain alone.
MAX_SCENE_VERTICES = 3_000_000
MAX_SCENE_TRIANGLES = 4_000_000

MATERIALS = {
    # name: (base colour linear rgb, roughness, metallic)
    "MB Terrain": ((0.8, 0.8, 0.8), 0.95, 0.0),
    "MB Facade": ((0.8, 0.8, 0.8), 0.85, 0.0),
    "MB Roof": ((0.8, 0.8, 0.8), 0.7, 0.0),
    "MB Road": ((0.8, 0.8, 0.8), 0.9, 0.0),
    "MB Bark": ((0.8, 0.8, 0.8), 0.9, 0.0),
    "MB Foliage": ((0.8, 0.8, 0.8), 0.8, 0.0),
}

LANDCOVER_COLORS = {
    None: (0.28, 0.26, 0.20),
    "grass": (0.16, 0.32, 0.08),
    "forest": (0.07, 0.20, 0.05),
    "water": (0.05, 0.14, 0.24),
    "sand": (0.62, 0.55, 0.38),
}
FACADE_PALETTE = [(0.62, 0.58, 0.52), (0.70, 0.66, 0.60), (0.55, 0.42, 0.34), (0.75, 0.73, 0.70),
                  (0.48, 0.47, 0.46), (0.66, 0.55, 0.42)]
ROOF_PALETTE = [(0.30, 0.12, 0.08), (0.22, 0.22, 0.24), (0.40, 0.20, 0.12), (0.35, 0.35, 0.36)]
NAMED_COLORS = {"white": (0.9, 0.9, 0.9), "black": (0.03, 0.03, 0.03), "grey": (0.4, 0.4, 0.4),
                "gray": (0.4, 0.4, 0.4), "red": (0.5, 0.06, 0.04), "brown": (0.3, 0.15, 0.07),
                "yellow": (0.8, 0.65, 0.2), "beige": (0.75, 0.65, 0.48), "green": (0.1, 0.3, 0.1),
                "blue": (0.08, 0.15, 0.4), "orange": (0.7, 0.3, 0.05), "silver": (0.6, 0.6, 0.62)}
ROAD_WIDTHS = {"motorway": 12.0, "trunk": 10.0, "primary": 8.0, "secondary": 7.0, "tertiary": 6.0,
               "motorway_link": 5.0, "trunk_link": 5.0, "primary_link": 5.0, "secondary_link": 5.0,
               "residential": 5.0, "unclassified": 5.0, "living_street": 4.5, "service": 3.5,
               "pedestrian": 4.0, "track": 3.0, "footway": 2.0, "path": 1.5, "cycleway": 2.0,
               "steps": 2.0, "bridleway": 2.0}
FOOT = {"footway", "path", "cycleway", "steps", "bridleway", "pedestrian", "track"}


class InvalidFeature(MapBuilderError):
    """A feature that cannot be generated as given; reported in ``invalid_features``."""


def stable_hash(text):
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def short_name(fid):
    # "osm:way/123#1" -> "way_123_1"
    return re.sub(r"[^A-Za-z0-9]+", "_", fid.split(":", 1)[-1]).strip("_")


def parse_length(value):
    """OSM length -> metres, or None. Accepts '12', '12 m', '12.5m', "40'", "10'6\"", '30 ft'.

    Values that overflow to a non-finite float return None."""
    if value is None:
        return None
    v = value.strip().lower().replace(",", ".")
    out = None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(m|meter|meters|metre|metres)?", v)
    if m:
        out = float(m.group(1))
    elif re.fullmatch(r"(\d+(?:\.\d+)?)\s*(ft|feet)", v):
        out = float(re.match(r"\d+(?:\.\d+)?", v).group(0)) * 0.3048
    else:
        m = re.fullmatch(r"(\d+)'(?:\s*(\d+(?:\.\d+)?)\")?", v)
        if m:
            out = float(m.group(1)) * 0.3048 + float(m.group(2) or 0) * 0.0254
    return out if out is not None and math.isfinite(out) else None


def parse_number(value):
    try:
        f = float(value.strip().replace(",", "."))
        return f if math.isfinite(f) else None
    except (AttributeError, ValueError):
        return None


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def parse_colour(value):
    if not value:
        return None
    v = value.strip().lower()
    if v in NAMED_COLORS:
        return NAMED_COLORS[v]
    m = re.fullmatch(r"#?([0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))
    return None


class ObjectSpec:
    def __init__(self, name, mb_id, mb_class, collection, mesh=None, mesh_key=None, location=(0.0, 0.0, 0.0),
                 rotation_z=0.0, scale=1.0, provenance=None):
        self.name = name
        self.mb_id = mb_id
        self.mb_class = mb_class
        self.collection = collection
        self.mesh = mesh
        self.mesh_key = mesh_key
        self.location = location
        self.rotation_z = rotation_z
        self.scale = scale
        self.provenance = provenance or {}


class ScenePlan:
    def __init__(self, frame, area):
        self.frame = frame
        self.area = area
        self.objects = []
        self.shared_meshes = {}
        self.report = {"counts": {}, "unsupported_features": [], "invalid_features": [], "warnings": [],
                       "inferred": {}}

    def count(self, key, n=1):
        self.report["counts"][key] = self.report["counts"].get(key, 0) + n

    def inferred(self, key):
        self.report["inferred"][key] = self.report["inferred"].get(key, 0) + 1


def mesh_triangle_count(mesh):
    return sum(len(f) - 2 for f in mesh.faces)


class SceneBudget:
    """Cumulative vertex/triangle budget. ``reserve`` an upper-bound estimate *before*
    allocating an object, then ``commit`` the built mesh to replace the estimate."""

    def __init__(self, max_vertices=MAX_SCENE_VERTICES, max_triangles=MAX_SCENE_TRIANGLES):
        self.max_vertices = max_vertices
        self.max_triangles = max_triangles
        self.vertices = 0
        self.triangles = 0
        self._pending = None

    def _check(self, fid, vertices, triangles, what):
        if self.vertices + vertices > self.max_vertices or self.triangles + triangles > self.max_triangles:
            raise LimitError(
                f"{fid}: {what} {vertices} vertices / {triangles} triangles would exceed the scene budget "
                f"({self.vertices}/{self.max_vertices} vertices, {self.triangles}/{self.max_triangles} "
                "triangles used); choose a smaller area, coarser terrain or raise the limit")

    def reserve(self, fid, vertices, triangles):
        self.release()
        self._check(fid, vertices, triangles, "needs up to")
        self.vertices += vertices
        self.triangles += triangles
        self._pending = (fid, vertices, triangles)

    def charge(self, fid, vertices, triangles):
        """Reserve an exact amount that needs no later commit."""
        self.release()
        self._check(fid, vertices, triangles, "needs")
        self.vertices += vertices
        self.triangles += triangles

    def release(self):
        if self._pending:
            _, v, t = self._pending
            self.vertices -= v
            self.triangles -= t
            self._pending = None

    def commit(self, mesh):
        fid = self._pending[0] if self._pending else mesh.name
        self.release()
        self.charge(fid, len(mesh.vertices), mesh_triangle_count(mesh))

    def to_dict(self):
        return {"vertices": self.vertices, "triangles": self.triangles, "max_vertices": self.max_vertices,
                "max_triangles": self.max_triangles}


# --- Terrain surface ----------------------------------------------------------

def _cell(grid, x, y):
    fx = min(max((x - grid.x0) / grid.spacing, 0.0), grid.nx - 1.0)
    fy = min(max((y - grid.y0) / grid.spacing, 0.0), grid.ny - 1.0)
    i = max(0, min(int(fx), grid.nx - 2))
    j = max(0, min(int(fy), grid.ny - 2))
    return i, j, fx - i, fy - j


def _plane_height(h, i, j, upper, tx, ty):
    """Height in cell (i, j): ``upper`` False -> triangle (v00, v10, v11), True -> (v00, v11, v01)."""
    h00 = h[j][i]
    h11 = h[j + 1][i + 1]
    if not upper:
        return h00 + tx * (h[j][i + 1] - h00) + ty * (h11 - h[j][i + 1])
    return h00 + ty * (h[j + 1][i] - h00) + tx * (h11 - h[j + 1][i])


def terrain_height(grid, x, y):
    """Exact height of the emitted terrain mesh at (x, y).

    The terrain mesh splits each cell along the (i, j)-(i+1, j+1) diagonal (see
    :func:`build_terrain`); this evaluates that triangle's plane. Positions
    outside the grid are clamped to its edge."""
    i, j, tx, ty = _cell(grid, x, y)
    return _plane_height(grid.heights, i, j, ty > tx, tx, ty)


def footprint_terrain_range(grid, rings):
    """(min, max) of the terrain surface over a footprint (outer ring + holes, holes excluded).

    The terrain is piecewise planar, so its extremes over the footprint lie at ring
    vertices, grid nodes strictly inside the footprint, or where ring edges cross
    grid lines and cell diagonals; all of those are evaluated."""
    s, gx0, gy0 = grid.spacing, grid.x0, grid.y0
    zs = [terrain_height(grid, p[0], p[1]) for r in rings for p in r]
    umax, vmax = grid.nx - 1, grid.ny - 1
    for r in rings:
        n = len(r)
        for k in range(n):
            a, b = r[k], r[(k + 1) % n]
            ua, va = (a[0] - gx0) / s, (a[1] - gy0) / s
            ub, vb = (b[0] - gx0) / s, (b[1] - gy0) / s
            for fa, fb, lo_lim, hi_lim in ((ua, ub, 0, umax), (va, vb, 0, vmax), (ua - va, ub - vb, -vmax, umax)):
                if fa == fb:
                    continue
                lo, hi = sorted((fa, fb))
                for m in range(max(math.ceil(lo), lo_lim), min(math.floor(hi), hi_lim) + 1):
                    t = (m - fa) / (fb - fa)
                    if 0.0 < t < 1.0:
                        zs.append(terrain_height(grid, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    ys = [p[1] for p in rings[0]]
    h = grid.heights
    for j in range(max(0, math.ceil((min(ys) - gy0) / s)), min(vmax, math.floor((max(ys) - gy0) / s)) + 1):
        y = gy0 + j * s
        xs = []
        for r in rings:
            n = len(r)
            for k in range(n):
                a, b = r[k], r[(k + 1) % n]
                if (a[1] > y) != (b[1] > y):
                    xs.append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
        xs.sort()
        for q in range(0, len(xs) - 1, 2):
            for i in range(max(0, math.ceil((xs[q] - gx0) / s)), min(umax, math.floor((xs[q + 1] - gx0) / s)) + 1):
                zs.append(h[j][i])
    return min(zs), max(zs)


# --- Buildings --------------------------------------------------------------

MAX_LEVELS = 200        # building:levels / roof:levels / building:min_level accepted from tags
MAX_HEIGHT_M = 1000.0   # height / min_height / roof:height accepted from tags


def _bounded_tag(tags, key, parser, lo, hi, rejected, lo_open=False):
    """Parsed value of ``tags[key]`` if it lies in [lo, hi] (or (lo, hi]); otherwise None,
    and the raw value is recorded in ``rejected`` (never silently ignored)."""
    raw = tags.get(key)
    if raw is None:
        return None
    v = parser(raw)
    shown = raw if len(raw) <= 32 else raw[:29] + "..."
    if v is None:
        rejected.append(f"{key}={shown!r} is not a finite number")
        return None
    if v > hi or v < lo or (lo_open and v == lo):
        rng = f"{'(' if lo_open else '['}{lo:g}, {hi:g}]"
        rejected.append(f"{key}={shown!r} outside the accepted range {rng}")
        return None
    return v


def building_height(tags):
    """Returns (height, min_height, roof_height_or_None, provenance dict).

    ``roof_height`` here is the *source* value (tag or roof:levels); the value
    actually built is decided in :func:`build_building`. Numeric tags are bounded
    (levels <= MAX_LEVELS, lengths <= MAX_HEIGHT_M); rejected values are listed in
    ``provenance["rejected_tags"]`` and the affected value falls back."""
    prov = {}
    rejected = []
    h = _bounded_tag(tags, "height", parse_length, 0.5, MAX_HEIGHT_M, rejected)
    levels = _bounded_tag(tags, "building:levels", parse_number, 0.0, MAX_LEVELS, rejected, lo_open=True)
    roof_levels = _bounded_tag(tags, "roof:levels", parse_number, 0.0, MAX_LEVELS, rejected)
    roof_h = _bounded_tag(tags, "roof:height", parse_length, 0.0, MAX_HEIGHT_M, rejected)
    height_rejected = bool(rejected) and rejected[0].startswith("height=")
    if roof_h is not None:
        prov["roof_height"] = "measured:osm roof:height"
    elif roof_levels is not None:
        roof_h = roof_levels * LEVEL_HEIGHT_M
        prov["roof_height"] = "inferred:roof:levels x 3 m"
    if h is not None:
        prov["height"] = "measured:osm height"
    elif levels is not None:
        h = levels * LEVEL_HEIGHT_M + (roof_h or 0.0)
        prov["height"] = "inferred:building:levels x 3 m (+ roof)"
    else:
        btype = tags.get("building", tags.get("building:part", "yes"))
        h = {"house": 7.0, "detached": 7.0, "semidetached_house": 7.0, "bungalow": 4.5, "garage": 3.0,
             "garages": 3.0, "shed": 2.5, "hut": 2.5, "carport": 2.5, "roof": 4.0}.get(btype, 9.0)
        prov["height"] = f"inferred:default for building={btype}"
    if height_rejected:
        prov["height_source"] = f"osm height = {tags['height'][:32]!r}"
        prov["height_reason"] = rejected[0]
        prov["height"] = "fallback:" + prov["height"].split(":", 1)[1]
    min_h = _bounded_tag(tags, "min_height", parse_length, 0.0, MAX_HEIGHT_M, rejected)
    if min_h is not None:
        prov["min_height"] = "measured:osm min_height"
    else:
        ml = _bounded_tag(tags, "building:min_level", parse_number, 0.0, MAX_LEVELS, rejected)
        if ml is not None and ml > 0:
            min_h = ml * LEVEL_HEIGHT_M
            prov["min_height"] = "inferred:building:min_level x 3 m"
    min_h = min_h or 0.0
    if min_h >= h:
        min_h = 0.0
        prov["min_height"] = "ignored:min_height >= height"
    if rejected:
        prov["rejected_tags"] = "; ".join(rejected)
    return h, min_h, roof_h, prov


def _rect_check(ring):
    """Return True if ring is a near-rectangle (4 vertices, ~90 deg corners)."""
    if len(ring) != 4:
        return False
    for k in range(4):
        a, b, c = ring[k - 1], ring[k], ring[(k + 1) % 4]
        v1 = (a[0] - b[0], a[1] - b[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 < 0.5 or n2 < 0.5:
            return False
        if abs((v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)) > math.sin(math.radians(15)):
            return False
    return True


PLANAR_TOL_M = 1e-6


def _add_planar_face(mesh, idx, mat, col, tol=PLANAR_TOL_M):
    """Add face ``idx``; a polygon with > 3 vertices that is not planar within ``tol`` metres
    is added as explicit triangles instead (a quad along its shorter diagonal, otherwise a
    fan), keeping the winding. Returns True if the face was split."""
    if len(idx) > 3:
        V = [mesh.vertices[i] for i in idx]
        n = len(V)
        nx_ = sum((V[k][1] - V[(k + 1) % n][1]) * (V[k][2] + V[(k + 1) % n][2]) for k in range(n))
        ny_ = sum((V[k][2] - V[(k + 1) % n][2]) * (V[k][0] + V[(k + 1) % n][0]) for k in range(n))
        nz_ = sum((V[k][0] - V[(k + 1) % n][0]) * (V[k][1] + V[(k + 1) % n][1]) for k in range(n))
        ln = math.sqrt(nx_ * nx_ + ny_ * ny_ + nz_ * nz_)
        c = [sum(v[d] for v in V) / n for d in range(3)]
        if ln <= 1e-12 or max(abs((v[0] - c[0]) * nx_ + (v[1] - c[1]) * ny_ + (v[2] - c[2]) * nz_) / ln
                              for v in V) > tol:
            if n == 4 and math.dist(V[1], V[3]) < math.dist(V[0], V[2]):
                tris = [(idx[1], idx[2], idx[3]), (idx[1], idx[3], idx[0])]
            else:
                tris = [(idx[0], idx[k], idx[k + 1]) for k in range(1, n - 1)]
            for t in tris:
                mesh.add_face(t, mat, col)
            return True
    mesh.add_face(idx, mat, col)
    return False


def _is_convex(ring):
    n = len(ring)
    for k in range(n):
        a, b, c = ring[k - 1], ring[k], ring[(k + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-9:
            return False
    return True


def build_building(feature, terrain, z_offset, seed=0, max_ring_vertices=MAX_RING_VERTICES,
                   max_work=DEFAULT_MAX_WORK, reserve=None):
    """Returns (MeshData in object-local coords, location, provenance).

    Raises TriangulationError (invalid rings, work budget) or InvalidFeature (limits)
    before any mesh is allocated. ``reserve(vertices, triangles)`` is called with an
    upper-bound estimate before allocation and may raise LimitError."""
    poly = feature.geometry
    tags = feature.tags
    rings = [dedupe_ring(poly.outer)] + [dedupe_ring(h) for h in poly.holes]
    n_ring = sum(len(r) for r in rings)
    if n_ring > max_ring_vertices:
        raise InvalidFeature(f"footprint has {n_ring} ring vertices; the per-footprint limit is {max_ring_vertices}")
    cx, cy = poly.centroid()
    pts2 = [(p[0] - cx, p[1] - cy) for r in rings for p in r]
    offsets = []
    o = 0
    for r in rings:
        offsets.append(list(range(o, o + len(r))))
        o += len(r)
    tris = triangulate(pts2, offsets[0], offsets[1:], max_work=max_work)
    outer = rings[0]

    height, min_h, roof_src, prov = building_height(tags)
    roof_src_label = prov.get("roof_height")
    roof_shape_tag = tags.get("roof:shape")
    roof_shape = roof_shape_tag or "flat"
    prov["roof_shape"] = "measured:osm roof:shape" if roof_shape_tag else "inferred:flat"

    supported = {"flat", "skillion", "pyramidal", "gabled", "hipped"}
    if roof_shape not in supported:
        prov["roof_shape"] = f"fallback:flat (roof:shape={roof_shape} not modelled in v1)"
        roof_shape = "flat"
    if poly.holes and roof_shape not in ("flat", "skillion"):
        prov["roof_shape"] = f"fallback:flat (roof:shape={roof_shape} with courtyard)"
        roof_shape = "flat"
    if roof_shape in ("gabled", "hipped") and not _rect_check(outer):
        if _is_convex(outer):
            prov["roof_shape"] = f"fallback:pyramidal (roof:shape={roof_shape} on non-rectangular footprint)"
            roof_shape = "pyramidal"
        else:
            prov["roof_shape"] = f"fallback:flat (roof:shape={roof_shape} on non-rectangular footprint)"
            roof_shape = "flat"
    if roof_shape == "pyramidal" and not _is_convex(outer):
        prov["roof_shape"] = "fallback:flat (pyramidal roof on concave footprint)"
        roof_shape = "flat"

    # Roof height actually built; a source value that cannot be used is kept separately.
    xs, ys = [p[0] for p in outer], [p[1] for p in outer]
    short_side = min(max(xs) - min(xs), max(ys) - min(ys))
    wall_span = height - min_h
    reason = None
    if roof_shape == "flat":
        roof_h = 0.0
        reason = f"roof built flat (roof:shape={roof_shape_tag or 'flat'})"
    elif roof_src is None:
        roof_h = min(max(1.0, min(0.3 * short_side, 6.0)), 0.6 * wall_span)
        prov["roof_height"] = "inferred:0.3 x footprint short side (1-6 m, at most 60% of the building height)"
    else:
        roof_h = roof_src
        limit = wall_span - MIN_WALL_M
        if roof_h > limit:
            roof_h = max(limit, 0.0)
            reason = (f"roof:height must leave at least {MIN_WALL_M:g} m of wall below the eave "
                      f"(building height {height:g} m, min_height {min_h:g} m)")
        if roof_h <= 1e-6:
            prov["roof_shape"] = f"fallback:flat (no room for a {roof_shape} roof)"
            roof_shape, roof_h = "flat", 0.0
    if roof_src is not None and abs(roof_h - roof_src) > 1e-9:
        prov["roof_height_source"] = f"{roof_src_label} = {roof_src:g} m"
        prov["roof_height"] = f"fallback:{roof_h:g} m built ({reason})"
        prov["roof_height_reason"] = reason
    prov["roof_height_m"] = round(roof_h, 2)

    across = False
    orient_tag = tags.get("roof:orientation")
    if roof_shape in ("gabled", "hipped"):
        if orient_tag in ("along", "across"):
            prov["roof_orientation"] = f"measured:osm roof:orientation={orient_tag}"
            across = orient_tag == "across"
        elif orient_tag is None:
            prov["roof_orientation"] = "inferred:along (ridge parallel to the longer side)"
        else:
            prov["roof_orientation"] = f"fallback:along (roof:orientation={orient_tag} not recognised)"
    elif orient_tag is not None:
        prov["roof_orientation"] = f"ignored:roof:orientation={orient_tag} (roof built {roof_shape})"

    top = height  # relative to the base datum
    wall_top_flat = top - roof_h
    elevated = min_h > 0
    base_z = min_h if elevated else -FOUNDATION_SINK_M

    g_min, g_max = footprint_terrain_range(terrain, rings)
    origin = (cx, cy, g_min - z_offset)
    prov["ground"] = "terrain minimum under footprint"
    prov["base_datum"] = ("minimum of the piecewise-planar terrain mesh over the footprint (ring vertices, interior "
                          "grid nodes, ring crossings of grid lines and cell diagonals); heights are measured from "
                          f"it and the foundation extends {FOUNDATION_SINK_M:g} m below it")
    relief = g_max - g_min
    if relief > 0:
        prov["ground_slope_m"] = round(relief, 2)
    derived = {"height": height, "min_height": min_h, "roof_height": roof_h, "base": base_z,
               "eave": wall_top_flat, "terrain_min": g_min, "terrain_max": g_max, "centroid_x": cx, "centroid_y": cy}
    bad = [k for k, v in derived.items() if not math.isfinite(v)]
    if bad or height > 2 * MAX_HEIGHT_M:
        raise InvalidFeature(f"derived building geometry is not finite/bounded ({', '.join(bad) or 'height'}); "
                             "not generated")
    if relief >= wall_top_flat:
        raise InvalidFeature(f"terrain inside footprint reaches eave/roof (rises {relief:.2f} m above the base "
                             f"datum, eave at {wall_top_flat:.2f} m); no grading policy in v1")
    if elevated and relief >= min_h:
        prov["terrain_warning"] = (f"terrain inside the footprint rises {relief:.2f} m above the base datum, into "
                                   f"the underside of the elevated volume at {min_h:.2f} m")

    if reserve is not None:
        reserve(2 * n_ring + 2, 2 * n_ring + 2 * len(tris) + 4)

    facade = parse_colour(tags.get("building:colour"))
    if facade:
        prov["facade_colour"] = "measured:osm building:colour"
    else:
        facade = FACADE_PALETTE[stable_hash(feature.id + str(seed)) % len(FACADE_PALETTE)]
    roof_col = parse_colour(tags.get("roof:colour"))
    if roof_col:
        prov["roof_colour"] = "measured:osm roof:colour"
    else:
        roof_col = ROOF_PALETTE[stable_hash(feature.id + "r" + str(seed)) % len(ROOF_PALETTE)]
        if roof_shape == "flat":
            roof_col = (0.3, 0.3, 0.31)

    skillion_z = None
    if roof_shape == "skillion":
        direction = parse_number(tags.get("roof:direction"))
        if direction is None:
            prov["roof_direction"] = "inferred:0 (north-facing slope)"
            direction = 0.0
        direction %= 360.0
        d = (math.sin(math.radians(direction)), math.cos(math.radians(direction)))
        proj = [p[0] * d[0] + p[1] * d[1] for r in rings for p in r]
        smin, smax = min(proj), max(proj)
        span = max(smax - smin, 1e-6)

        def skillion_z(p):
            s = p[0] * d[0] + p[1] * d[1]
            return top - roof_h * (s - smin) / span

    mesh = MeshData(f"bld_{short_name(feature.id)}")
    split = []

    def add_face(idx, mat, col):
        split.append(_add_planar_face(mesh, idx, mat, col))
    ring_idx_bottom, ring_idx_top = [], []
    for r in rings:
        rb, rt = [], []
        for p in r:
            lx, ly = p[0] - cx, p[1] - cy
            zt = skillion_z(p) if skillion_z else wall_top_flat
            rb.append(mesh.add_vertex(lx, ly, base_z))
            rt.append(mesh.add_vertex(lx, ly, zt))
        ring_idx_bottom.append(rb)
        ring_idx_top.append(rt)
    for rb, rt in zip(ring_idx_bottom, ring_idx_top):
        n = len(rb)
        for k in range(n):
            j = (k + 1) % n
            add_face((rb[k], rb[j], rt[j], rt[k]), "MB Facade", facade)

    flat_top = [i for rt in ring_idx_top for i in rt]
    flat_bot = [i for rb in ring_idx_bottom for i in rb]
    for (a, b, c) in tris:
        add_face((flat_bot[a], flat_bot[c], flat_bot[b]), "MB Facade", facade)  # downward
    if roof_shape in ("flat", "skillion"):
        for (a, b, c) in tris:
            add_face((flat_top[a], flat_top[b], flat_top[c]), "MB Roof", roof_col)
    elif roof_shape == "pyramidal":
        apex = mesh.add_vertex(0.0, 0.0, top)
        rt = ring_idx_top[0]
        for k in range(len(rt)):
            add_face((rt[k], rt[(k + 1) % len(rt)], apex), "MB Roof", roof_col)
    else:  # gabled / hipped on rectangle a,b,c,d (CCW); ridge runs parallel to a-b
        rt = ring_idx_top[0]
        V = mesh.vertices
        a, b, c, d = rt
        # along: a-b is a long side (ridge along the long axis); across: a-b is a short side.
        if (math.dist(V[a][:2], V[b][:2]) < math.dist(V[b][:2], V[c][:2])) != across:
            a, b, c, d = b, c, d, a
        m1 = tuple((V[b][i] + V[c][i]) / 2 for i in range(2))
        m2 = tuple((V[d][i] + V[a][i]) / 2 for i in range(2))
        if roof_shape == "hipped":
            end = math.dist(V[b][:2], V[c][:2])
            ridge_span = math.dist(m1, m2)
            t = min(0.5 * end / max(ridge_span, 1e-6), 0.49)
            r1 = (m1[0] + (m2[0] - m1[0]) * t, m1[1] + (m2[1] - m1[1]) * t)
            r2 = (m2[0] + (m1[0] - m2[0]) * t, m2[1] + (m1[1] - m2[1]) * t)
        else:
            r1, r2 = m1, m2
        R1 = mesh.add_vertex(r1[0], r1[1], top)
        R2 = mesh.add_vertex(r2[0], r2[1], top)
        add_face((a, b, R1, R2), "MB Roof", roof_col)
        add_face((c, d, R2, R1), "MB Roof", roof_col)
        end_mat, end_col = ("MB Roof", roof_col) if roof_shape == "hipped" else ("MB Facade", facade)
        add_face((b, c, R1), end_mat, end_col)
        add_face((d, a, R2), end_mat, end_col)
    if any(split):
        prov["roof_faces"] = (f"{sum(split)} non-planar face(s) (footprint not an exact rectangle) split into "
                              "triangles along the shorter diagonal")
    prov["roof_shape_built"] = roof_shape
    prov["height_m"] = round(height, 2)
    if elevated:
        prov["elevated"] = (f"volume starts {min_h:.1f} m above ground; the space beneath is NOT modelled "
                            "as traversable in v1")
    return mesh, origin, prov


# --- Terrain ----------------------------------------------------------------

class _Buckets:
    """Uniform-grid index of bboxes. With ``bounds`` (x0, y0, x1, y1) only the part of each
    bbox inside ``bounds`` is indexed (queries outside it return nothing), so the bucket
    count is bounded by the scene extent, not by the size of the OSM geometry."""

    def __init__(self, items, cell=50.0, bounds=None):
        self.cell = cell
        self.map = {}
        for it, (x0, y0, x1, y1) in items:
            if bounds is not None:
                x0, y0 = max(x0, bounds[0]), max(y0, bounds[1])
                x1, y1 = min(x1, bounds[2]), min(y1, bounds[3])
                if x0 > x1 or y0 > y1:
                    continue
            for i in range(int(math.floor(x0 / cell)), int(math.floor(x1 / cell)) + 1):
                for j in range(int(math.floor(y0 / cell)), int(math.floor(y1 / cell)) + 1):
                    self.map.setdefault((i, j), []).append(it)

    def query(self, x, y):
        return self.map.get((int(math.floor(x / self.cell)), int(math.floor(y / self.cell))), ())


LANDCOVER_PRIORITY = {"water": 4, "forest": 3, "sand": 2, "grass": 1}


def build_terrain(grid, z_offset, areas, coverage=None):
    """Terrain mesh; each cell is split along its (i, j)-(i+1, j+1) diagonal (see terrain_height).

    If ``coverage`` is a dict it receives, per area id, the number of cells whose
    centre lies inside that area."""
    mesh = MeshData("terrain")
    buckets = _Buckets([(a, a.geometry.bbox()) for a in areas],
                       bounds=(grid.x0, grid.y0, grid.x0 + (grid.nx - 1) * grid.spacing,
                               grid.y0 + (grid.ny - 1) * grid.spacing))
    for j in range(grid.ny):
        for i in range(grid.nx):
            mesh.add_vertex(grid.x0 + i * grid.spacing, grid.y0 + j * grid.spacing, grid.heights[j][i] - z_offset)
    nx = grid.nx
    for j in range(grid.ny - 1):
        for i in range(nx - 1):
            v00, v10 = j * nx + i, j * nx + i + 1
            v01, v11 = v00 + nx, v10 + nx
            cx = grid.x0 + (i + 0.5) * grid.spacing
            cy = grid.y0 + (j + 0.5) * grid.spacing
            cls = None
            for a in buckets.query(cx, cy):
                if not a.geometry.contains(cx, cy):
                    continue
                if coverage is not None:
                    coverage[a.id] = coverage.get(a.id, 0) + 1
                c = a.tags["_class"]
                if cls is None or LANDCOVER_PRIORITY[c] > LANDCOVER_PRIORITY[cls]:
                    cls = c
            col = LANDCOVER_COLORS[cls]
            mesh.add_face((v00, v10, v11), "MB Terrain", col)
            mesh.add_face((v00, v11, v01), "MB Terrain", col)
    return mesh


# --- Roads ------------------------------------------------------------------

def road_width(tags):
    w = parse_length(tags.get("width"))
    if w is not None and 0.5 <= w <= 60:
        return w, "measured:osm width"
    lanes = parse_number(tags.get("lanes"))
    if lanes is not None and 1 <= lanes <= 12:
        return lanes * 3.25, "inferred:lanes x 3.25 m"
    hw = tags.get("highway")
    return ROAD_WIDTHS.get(hw, 4.0), f"inferred:default for highway={hw}"


def _dedupe_polyline(pts, tol=1e-3):
    out = []
    for p in pts:
        if not out or math.dist(p, out[-1]) > tol:
            out.append((float(p[0]), float(p[1])))
    return out


def _area2(poly):
    a = 0.0
    n = len(poly)
    for k in range(n):
        a += poly[k][0] * poly[(k + 1) % n][1] - poly[(k + 1) % n][0] * poly[k][1]
    return a


def _road_pieces(pts, half):
    """Convex CCW polygons whose union is the ribbon footprint: one rectangle per segment
    (butt ends) plus a bevel triangle on the outer side of every join.

    Pieces are not folded, but they may overlap (inner side of a turn, U-turns,
    self-crossing polylines); :func:`_ribbon_faces` turns them into interior-disjoint
    faces."""
    pieces, normals = [], []
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        nx_, ny_ = -dy / ln * half, dx / ln * half
        normals.append((nx_, ny_))
        pieces.append([(a[0] - nx_, a[1] - ny_), (b[0] - nx_, b[1] - ny_), (b[0] + nx_, b[1] + ny_),
                       (a[0] + nx_, a[1] + ny_)])
    for k in range(1, len(pts) - 1):
        p, n1, n2 = pts[k], normals[k - 1], normals[k]
        turn = n1[0] * n2[1] - n1[1] * n2[0]
        if abs(turn) <= 1e-9 * half * half:
            continue  # straight on, or an exact reversal (butt end)
        s = -1.0 if turn > 0 else 1.0  # outer side of the turn
        tri = [p, (p[0] + s * n1[0], p[1] + s * n1[1]), (p[0] + s * n2[0], p[1] + s * n2[1])]
        if _area2(tri) < 0:
            tri = [tri[0], tri[2], tri[1]]
        if _area2(tri) > 1e-9:
            pieces.append(tri)
    return pieces


def _clip_halfplane(poly, a, b):
    """Keep the part of convex ``poly`` left of (or on) the directed line a->b."""
    out = []
    n = len(poly)
    for k in range(n):
        p, q = poly[k], poly[(k + 1) % n]
        sp = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        sq = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
        if sp >= 0:
            out.append(p)
        if (sp > 0 > sq) or (sp < 0 < sq):
            t = sp / (sp - sq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def _clip_convex(poly, tri):
    for k in range(3):
        poly = _clip_halfplane(poly, tri[k], tri[(k + 1) % 3])
        if len(poly) < 3:
            return []
    return poly


def _cell_range(grid, x0, x1, y0, y1):
    s = grid.spacing
    i0 = max(0, int(math.floor((x0 - grid.x0) / s)))
    i1 = min(grid.nx - 2, int(math.floor((x1 - grid.x0) / s)))
    j0 = max(0, int(math.floor((y0 - grid.y0) / s)))
    j1 = min(grid.ny - 2, int(math.floor((y1 - grid.y0) / s)))
    return i0, i1, j0, j1


def _bbox(poly):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return min(xs), max(xs), min(ys), max(ys)


_OVERLAP_EPS = 1e-7  # m; overlaps thinner than this count as touching


class _RibbonWork:
    """Bounds the clip/union work of one road ribbon (per-feature limit)."""

    def __init__(self, limit):
        self.limit = limit
        self.n = 0

    def add(self, k=1):
        self.n += k
        if self.n > self.limit:
            raise InvalidFeature(f"road ribbon exceeds the work budget ({self.limit} clip/union steps)")


def _convex_overlap(p, q, eps=_OVERLAP_EPS):
    """True if convex polygons ``p`` and ``q`` share interior thicker than ``eps`` (separating axes)."""
    for poly in (p, q):
        n = len(poly)
        for k in range(n):
            a, b = poly[k], poly[(k + 1) % n]
            ex, ey = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(ex, ey)
            if ln <= 1e-12:
                continue
            ux, uy = -ey / ln, ex / ln
            pp = [x * ux + y * uy for x, y in p]
            qq = [x * ux + y * uy for x, y in q]
            if max(pp) <= min(qq) + eps or max(qq) <= min(pp) + eps:
                return False
    return True


def _overlap_groups(polys, members=None, work=None):
    """Component id per polygon of the graph "interiors overlap" (x-sweep on bboxes + SAT).

    ``members`` restricts the graph to those indices (others keep their own id)."""
    idx = list(range(len(polys))) if members is None else list(members)
    parent = {k: k for k in idx}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    boxes = {k: _bbox(polys[k]) for k in idx}
    active = []
    for k in sorted(idx, key=lambda m: boxes[m][0]):
        bk = boxes[k]
        active = [a for a in active if boxes[a][1] > bk[0] + _OVERLAP_EPS]
        for a in active:
            if work is not None:
                work.add()
            ba = boxes[a]
            if ba[2] < bk[3] - _OVERLAP_EPS and bk[2] < ba[3] - _OVERLAP_EPS and _convex_overlap(polys[a], polys[k]):
                parent[find(a)] = find(k)
        active.append(k)
    return {k: find(k) for k in idx}


def _line_y(e, x):
    return e[1] + (x - e[0]) * (e[3] - e[1]) / (e[2] - e[0])


def _union_convex(polys, eps=1e-9):
    """Union of convex CCW polygons as interior-disjoint convex trapezoids.

    Vertical-slab decomposition: slab boundaries are every vertex x and every crossing
    of edges of different polygons, so inside a slab no two boundary lines cross and
    each polygon covers one interval between two of its edges. Overlapping intervals
    are merged; each merged interval is a trapezoid, and consecutive slabs bounded by
    the same two edges are joined into one trapezoid."""
    edges = []  # (x0, y0, x1, y1, polygon, edge) with x0 < x1; vertical edges lie on slab boundaries
    xs = []
    for pi, poly in enumerate(polys):
        n = len(poly)
        for k in range(n):
            a, b = poly[k], poly[(k + 1) % n]
            xs.append(a[0])
            if a[0] < b[0]:
                edges.append((a[0], a[1], b[0], b[1], pi, k))
            elif b[0] < a[0]:
                edges.append((b[0], b[1], a[0], a[1], pi, k))
    for u, e in enumerate(edges):
        for f in edges[u + 1:]:
            if f[4] == e[4]:
                continue
            lo, hi = max(e[0], f[0]), min(e[2], f[2])
            if hi <= lo:
                continue
            d_lo = _line_y(e, lo) - _line_y(f, lo)
            d_hi = _line_y(e, hi) - _line_y(f, hi)
            if (d_lo > 0 > d_hi) or (d_lo < 0 < d_hi):
                xs.append(lo + (hi - lo) * d_lo / (d_lo - d_hi))
    xs.sort()
    cuts = [xs[0]]
    for x in xs[1:]:
        if x - cuts[-1] > eps:
            cuts.append(x)
    out = []

    def trapezoid(lo, hi, x0, x1):
        pts = [(x0, _line_y(lo, x0)), (x1, _line_y(lo, x1)), (x1, _line_y(hi, x1)), (x0, _line_y(hi, x0))]
        clean = []
        for p in pts:
            if not clean or math.dist(p, clean[-1]) > 1e-9:
                clean.append(p)
        if len(clean) > 1 and math.dist(clean[0], clean[-1]) <= 1e-9:
            clean.pop()
        if len(clean) >= 3 and _area2(clean) > 1e-12:
            out.append(clean)

    runs = {}  # (lower edge id, upper edge id) -> (start x, lower edge, upper edge)
    for xa, xb in zip(cuts, cuts[1:]):
        xm = 0.5 * (xa + xb)
        span = {}
        for e in edges:
            if e[0] < xm < e[2]:
                span.setdefault(e[4], []).append((_line_y(e, xm), e))
        intervals = []
        for lst in span.values():
            if len(lst) >= 2:
                lo, hi = min(lst), max(lst)
                intervals.append([lo[0], hi[0], lo[1], hi[1]])
        intervals.sort(key=lambda iv: iv[0])
        merged = []
        for iv in intervals:
            if merged and iv[0] <= merged[-1][1] + eps:
                if iv[1] > merged[-1][1]:
                    merged[-1][1], merged[-1][3] = iv[1], iv[3]
            else:
                merged.append(iv)
        nxt = {}
        for iv in merged:
            key = (iv[2][4:], iv[3][4:])
            nxt[key] = runs.pop(key, None) or (xa, iv[2], iv[3])
        for x0, lo, hi in runs.values():
            trapezoid(lo, hi, x0, xa)
        runs = nxt
    for x0, lo, hi in runs.values():
        trapezoid(lo, hi, x0, cuts[-1])
    return out


def _piece_cells(grid, piece):
    """Terrain cells (i, j) whose square meets convex ``piece`` (row strips, not the bbox)."""
    s = grid.spacing
    x0, x1, y0, y1 = _bbox(piece)
    _, _, j0, j1 = _cell_range(grid, x0, x1, y0, y1)
    for j in range(j0, j1 + 1):
        ya, yb = grid.y0 + j * s, grid.y0 + (j + 1) * s
        strip = _clip_halfplane(piece, (0.0, ya), (1.0, ya))
        if len(strip) >= 3:
            strip = _clip_halfplane(strip, (1.0, yb), (0.0, yb))
        if len(strip) < 3:
            continue
        xs = [p[0] for p in strip]
        i0, i1, _, _ = _cell_range(grid, min(xs), max(xs), ya, ya)
        for i in range(i0, i1 + 1):
            yield i, j


def _piece_bound(group_size):
    """Upper bound on output triangles per (piece, terrain triangle) visit.

    A piece clipped to a terrain triangle has <= 7 vertices (<= 5 fan triangles). A
    union of c overlapping clipped pieces has <= 7c vertices and <= 14 crossings per pair,
    so <= 7c^2 slab boundaries, <= c trapezoids (2 triangles) per slab: <= 2c(7c^2 - 1)
    triangles, i.e. 2(7c^2 - 1) per member."""
    return 5 if group_size == 1 else 2 * (7 * group_size * group_size - 1)


def _ribbon_cheap_bound(grid, pieces, groups):
    sizes = {}
    for g in groups.values():
        sizes[g] = sizes.get(g, 0) + 1
    total = 0
    for k, piece in enumerate(pieces):
        i0, i1, j0, j1 = _cell_range(grid, *_bbox(piece))
        total += 2 * max(0, i1 - i0 + 1) * max(0, j1 - j0 + 1) * _piece_bound(sizes[groups[k]])
    return total


def _ribbon_faces(grid, pieces, groups, work):
    """Yield (i, j, upper, X0, Y0, polygons) per terrain triangle the ribbon touches.

    ``polygons`` are interior-disjoint convex CCW polygons inside that terrain triangle
    whose union is the ribbon there: pieces that overlap (``groups`` are the components
    of the piece-overlap graph, refined per terrain triangle) are replaced by their union."""
    s = grid.spacing
    cells = {}
    for pi, piece in enumerate(pieces):
        for i, j in _piece_cells(grid, piece):
            work.add()
            cells.setdefault((j, i), []).append(pi)
    for j, i in sorted(cells):
        X0, Y0 = grid.x0 + i * s, grid.y0 + j * s
        c00, c10, c11, c01 = (X0, Y0), (X0 + s, Y0), (X0 + s, Y0 + s), (X0, Y0 + s)
        for upper, tri in ((False, (c00, c10, c11)), (True, (c00, c11, c01))):
            by_group = {}
            for pi in cells[(j, i)]:
                work.add()
                q = _clip_convex(pieces[pi], tri)
                if len(q) >= 3 and _area2(q) > 1e-12:
                    by_group.setdefault(groups[pi], []).append(q)
            out = []
            for qs in by_group.values():
                if len(qs) == 1:
                    out.extend(qs)
                    continue
                local = _overlap_groups(qs, work=work)
                comps = {}
                for k, g in local.items():
                    comps.setdefault(g, []).append(qs[k])
                for comp in comps.values():
                    if len(comp) == 1:
                        out.extend(comp)
                    else:
                        work.add(50 * len(comp) ** 3)
                        out.extend(_union_convex(comp))
            if out:
                yield i, j, upper, X0, Y0, out


def build_road(feature, terrain, z_offset, reserve=None, max_work=DEFAULT_MAX_WORK):
    """Returns (mesh, location, provenance), or (None, None, {"reason": ...}) if no valid ribbon exists.

    The footprint is the union of one rectangle per segment and a bevel triangle at
    every join; overlapping parts are merged so no two faces overlap. Faces are split at
    terrain grid lines and diagonals so each lies on one terrain plane, ``ROAD_LIFT_M``
    above it, facing up (+Z).

    ``reserve(vertices, triangles)`` is called before allocation with a cheap upper
    bound; if that is refused, with the exact count from a counting pass (no mesh
    allocated). Raises InvalidFeature if the clip/union work exceeds ``max_work``."""
    width, wprov = road_width(feature.tags)
    pts = _dedupe_polyline(list(feature.geometry))
    if len(pts) < 2:
        return None, None, {"reason": "road collapses to fewer than 2 distinct points (1 mm tolerance); "
                                      "no ribbon generated"}
    half = width / 2.0
    pieces = _road_pieces(pts, half)
    groups = _overlap_groups(pieces, work=_RibbonWork(max_work))
    if reserve is not None:
        est_t = _ribbon_cheap_bound(terrain, pieces, groups)
        try:
            reserve(3 * est_t, est_t)
        except LimitError:
            # The cheap bound (bbox cells x worst case) can be far too pessimistic, e.g. for a
            # wide diagonal road: count exactly before rejecting.
            exact_t = sum(len(q) - 2 for *_, polys in _ribbon_faces(terrain, pieces, groups, _RibbonWork(max_work))
                          for q in polys)
            reserve(3 * exact_t, exact_t)
    gx1 = terrain.x0 + (terrain.nx - 1) * terrain.spacing
    gy1 = terrain.y0 + (terrain.ny - 1) * terrain.spacing
    clipped = any(b[0] < terrain.x0 or b[1] > gx1 or b[2] < terrain.y0 or b[3] > gy1
                  for b in (_bbox(p) for p in pieces))

    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    z0 = terrain_height(terrain, *pts[0]) - z_offset + ROAD_LIFT_M
    mesh = MeshData(f"road_{short_name(feature.id)}")
    color = (0.12, 0.12, 0.12) if feature.tags.get("highway") not in FOOT else (0.35, 0.32, 0.28)
    index = {}

    def vertex(p, hfn):
        key = (round(p[0], 6), round(p[1], 6))
        v = index.get(key)
        if v is None:
            v = index[key] = mesh.add_vertex(p[0] - cx, p[1] - cy, hfn(*p) - z_offset + ROAD_LIFT_M - z0)
        return v

    def emit(piece, hfn):
        for k in range(1, len(piece) - 1):
            tri = (piece[0], piece[k], piece[k + 1])
            if _area2(tri) <= 1e-9:  # sliver from clipping; zero area, nothing visible is lost
                continue
            idx = tuple(vertex(p, hfn) for p in tri)
            # re-check on the welded positions (welding moves points by <= 1e-6 m)
            if _area2([mesh.vertices[v][:2] for v in idx]) <= 1e-9:
                continue
            mesh.add_face(idx, "MB Road", color)

    s = terrain.spacing
    for i, j, upper, X0, Y0, polys in _ribbon_faces(terrain, pieces, groups, _RibbonWork(max_work)):
        def hfn(x, y, i=i, j=j, upper=upper, X0=X0, Y0=Y0):
            return _plane_height(terrain.heights, i, j, upper, (x - X0) / s, (y - Y0) / s)
        for q in polys:
            emit(q, hfn)
    if not mesh.faces:
        return None, None, {"reason": "road ribbon lies outside the terrain extent; no ribbon generated"}
    # Guarantee: never emit folded (downward-facing) faces.
    V = mesh.vertices
    for a, b, c in mesh.triangles():
        if (V[b][0] - V[a][0]) * (V[c][1] - V[a][1]) - (V[b][1] - V[a][1]) * (V[c][0] - V[a][0]) <= 0:
            return None, None, {"reason": "road ribbon would contain folded faces; not generated"}
    prov = {"width": wprov, "width_m": round(width, 2),
            "vertical": f"draped on the terrain mesh (+{ROAD_LIFT_M:g} m), split at terrain cell edges and diagonals",
            "joins": "bevel",
            "footprint": "union of segment rectangles and join bevels; overlapping parts merged, no overlapping faces"}
    if clipped:
        prov["terrain_edge"] = "ribbon trimmed at the terrain edge"
    return mesh, (cx, cy, z0), prov


# --- Vegetation -------------------------------------------------------------

def tree_mesh():
    m = MeshData("tree_generic")
    sides = 6
    trunk_r, trunk_h, crown_r, crown_b, crown_t = 0.25, 2.6, 2.2, 2.0, 8.0
    bark, leaf = (0.18, 0.11, 0.06), (0.06, 0.20, 0.05)
    b = [m.add_vertex(trunk_r * math.cos(2 * math.pi * k / sides), trunk_r * math.sin(2 * math.pi * k / sides), -0.2)
         for k in range(sides)]
    t = [m.add_vertex(trunk_r * math.cos(2 * math.pi * k / sides), trunk_r * math.sin(2 * math.pi * k / sides), trunk_h)
         for k in range(sides)]
    for k in range(sides):
        j = (k + 1) % sides
        m.add_face((b[k], b[j], t[j], t[k]), "MB Bark", bark)
    m.add_face(tuple(reversed(b)), "MB Bark", bark)
    sides = 8
    ring = [m.add_vertex(crown_r * math.cos(2 * math.pi * k / sides), crown_r * math.sin(2 * math.pi * k / sides),
                         crown_b + 1.2) for k in range(sides)]
    top = m.add_vertex(0.0, 0.0, crown_t)
    bottom = m.add_vertex(0.0, 0.0, crown_b)
    for k in range(sides):
        j = (k + 1) % sides
        m.add_face((ring[k], ring[j], top), "MB Foliage", leaf)
        m.add_face((ring[j], ring[k], bottom), "MB Foliage", leaf)
    return m


TREE_UNIT_HEIGHT = 8.0
SCATTER_DENSITY = {"forest": 1.0 / 60.0, "grass": 1.0 / 600.0}


def scatter_points(feature, density, rng, limit, bounds=None):
    """Jittered grid points inside ``feature``. With ``bounds`` (x0, y0, x1, y1) only grid
    rows/columns that can jitter into ``bounds`` are visited, so the work is bounded by the
    scene extent (a polygon entirely inside ``bounds`` gets the same points as without it)."""
    poly = feature.geometry
    x0, y0, x1, y1 = poly.bbox()
    step = math.sqrt(1.0 / density)
    k0 = c0 = 0
    if bounds is not None:
        # jitter is < 0.4 step; one step of margin keeps every reachable point
        k0 = max(0, math.ceil((bounds[1] - step - y0 - step / 2) / step))
        c0 = max(0, math.ceil((bounds[0] - step - x0 - step / 2) / step))
        x1, y1 = min(x1, bounds[2] + step), min(y1, bounds[3] + step)
    pts = []
    y = y0 + step / 2 + k0 * step
    while y < y1 and len(pts) < limit:
        x = x0 + step / 2 + c0 * step
        while x < x1 and len(pts) < limit:
            px = x + (rng.random() - 0.5) * step * 0.8
            py = y + (rng.random() - 0.5) * step * 0.8
            if poly.contains(px, py):
                pts.append((px, py))
            x += step
        y += step
    return pts


# --- Plan -------------------------------------------------------------------

class PlanOptions:
    """Generation switches and resource bounds.

    ``max_vertices``/``max_triangles``: cumulative scene budget (tree instances count
    individually), checked before each object is allocated; exceeding it raises
    LimitError naming the feature. ``max_ring_vertices`` and
    ``max_triangulation_work`` reject a single footprint (reported in
    ``invalid_features``)."""

    def __init__(self, buildings=True, roads=True, trees=True, scatter=True, max_trees=2000, seed=0,
                 max_objects=20_000, max_vertices=MAX_SCENE_VERTICES, max_triangles=MAX_SCENE_TRIANGLES,
                 max_ring_vertices=MAX_RING_VERTICES, max_triangulation_work=DEFAULT_MAX_WORK):
        self.buildings = buildings
        self.roads = roads
        self.trees = trees
        self.scatter = scatter
        self.max_trees = max_trees
        self.seed = seed
        self.max_objects = max_objects
        self.max_vertices = max_vertices
        self.max_triangles = max_triangles
        self.max_ring_vertices = max_ring_vertices
        self.max_triangulation_work = max_triangulation_work


def build_plan(area, terrain, classified, options=None):
    opts = options or PlanOptions()
    zmin, _ = terrain.min_max()
    z_offset = math.floor(zmin)
    area.frame.z_offset = z_offset
    plan = ScenePlan(area.frame, area)
    plan.report["unsupported_features"] = list(classified.unsupported)
    plan.report["invalid_features"] = list(classified.invalid)
    plan.count("buildings_outside_area", classified.outside)
    if classified.replaced_outlines:
        plan.report["building_outlines_replaced_by_parts"] = list(classified.replaced_outlines)
    budget = SceneBudget(opts.max_vertices, opts.max_triangles)
    invalid = plan.report["invalid_features"]

    def add(spec):
        if len(plan.objects) >= opts.max_objects:
            raise LimitError(f"{spec.mb_id}: object limit {opts.max_objects} reached")
        plan.objects.append(spec)

    budget.reserve("terrain:grid", terrain.nx * terrain.ny, 2 * (terrain.nx - 1) * (terrain.ny - 1))
    coverage = {}
    tmesh = build_terrain(terrain, z_offset, classified.areas, coverage)
    budget.commit(tmesh)
    add(ObjectSpec("terrain", "terrain:grid", "terrain", "Terrain", mesh=tmesh,
                   provenance={"elevation": terrain.provenance.get("provider"), "spacing_m": terrain.spacing,
                               "surface": "piecewise planar, cells split along the (i,j)-(i+1,j+1) diagonal"}))
    for a in classified.areas:
        if not coverage.get(a.id):
            plan.report["unsupported_features"].append(
                {"id": a.id, "reason": f"{a.tags['_class']} area contains no terrain cell centre at "
                                       f"{terrain.spacing:g} m spacing; not represented in terrain colouring"})

    footprints = []
    if opts.buildings:
        for f in classified.buildings:
            try:
                mesh, origin, prov = build_building(
                    f, terrain, z_offset, opts.seed, max_ring_vertices=opts.max_ring_vertices,
                    max_work=opts.max_triangulation_work, reserve=lambda v, t, fid=f.id: budget.reserve(fid, v, t))
            except TriangulationError as e:
                budget.release()
                invalid.append({"id": f.id, "reason": f"triangulation failed: {e}"})
                continue
            except InvalidFeature as e:
                budget.release()
                invalid.append({"id": f.id, "reason": str(e)})
                continue
            budget.commit(mesh)
            for k, v in prov.items():
                if isinstance(v, str) and v.startswith(("inferred", "fallback")) and not k.endswith("_source"):
                    plan.inferred(f"building.{k}")
            if "elevated" in prov:
                plan.report["unsupported_features"].append(
                    {"id": f.id, "reason": "elevated volume (min_height/building:min_level): generated as a "
                                           "closed solid; flying beneath it is not supported in v1",
                     "tags": {k: v for k, v in f.tags.items() if k in ("min_height", "building:min_level")}})
            if "terrain_warning" in prov:
                plan.report["warnings"].append(f"{f.id}: {prov['terrain_warning']}")
            if "rejected_tags" in prov:
                plan.report["warnings"].append(f"{f.id}: out-of-range tags ignored ({prov['rejected_tags']})")
            add(ObjectSpec(mesh.name, f.id, "building", "Buildings", mesh=mesh, location=origin, provenance=prov))
            footprints.append((f.geometry, f.geometry.bbox()))
            if f.geometry.holes:
                plan.count("buildings_with_courtyards")
            plan.count("buildings")
    road_segments = []
    if opts.roads:
        for f in classified.roads:
            try:
                mesh, origin, prov = build_road(f, terrain, z_offset,
                                                reserve=lambda v, t, fid=f.id: budget.reserve(fid, v, t),
                                                max_work=opts.max_triangulation_work)
            except InvalidFeature as e:
                budget.release()
                invalid.append({"id": f.id, "reason": str(e)})
                continue
            if mesh is None:
                budget.release()
                invalid.append({"id": f.id, "reason": prov["reason"]})
                continue
            budget.commit(mesh)
            if prov["width"].startswith("inferred"):
                plan.inferred("road.width")
            add(ObjectSpec(mesh.name, f.id, "road", "Roads", mesh=mesh, location=origin, provenance=prov))
            w = prov["width_m"]
            for a, b in zip(f.geometry, f.geometry[1:]):
                road_segments.append((a, b, w / 2 + 1.0))
            plan.count("roads")
    if opts.trees:
        tmpl = plan.shared_meshes["tree_generic"] = tree_mesh()
        tree_cost = (len(tmpl.vertices), mesh_triangle_count(tmpl))
        scene = (-area.width / 2, -area.height / 2, area.width / 2, area.height / 2)
        fp_buckets = _Buckets(footprints, bounds=scene)
        seg_buckets = _Buckets([((a, b, r), (min(a[0], b[0]) - r, min(a[1], b[1]) - r,
                                             max(a[0], b[0]) + r, max(a[1], b[1]) + r)) for a, b, r in road_segments],
                               cell=25.0, bounds=scene)

        def blocked(x, y):
            for poly in fp_buckets.query(x, y):
                if poly.contains(x, y):
                    return True
            for a, b, r in seg_buckets.query(x, y):
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = dx * dx + dy * dy
                t = 0.0 if L == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L))
                if math.hypot(x - a[0] - t * dx, y - a[1] - t * dy) < r:
                    return True
            return False

        n_trees = 0
        for k_tree, f in enumerate(classified.trees):
            if n_trees >= opts.max_trees:
                plan.report["warnings"].append(f"tree limit {opts.max_trees} reached; "
                                               f"{len(classified.trees) - k_tree} remaining OSM trees skipped")
                break
            x, y = f.geometry
            h = parse_length(f.tags.get("height"))
            prov = {"position": "measured:osm natural=tree"}
            if h is not None and 1 <= h <= 80:
                prov["height"] = "measured:osm height"
            else:
                h = TREE_UNIT_HEIGHT
                prov["height"] = "inferred:default 8 m"
            rng = random.Random(stable_hash(f.id) ^ opts.seed)
            budget.charge(f.id, *tree_cost)
            add(ObjectSpec(f"tree_{short_name(f.id)}", f.id, "vegetation", "Vegetation", mesh_key="tree_generic",
                           location=(x, y, terrain_height(terrain, x, y) - z_offset),
                           rotation_z=rng.random() * 2 * math.pi, scale=h / TREE_UNIT_HEIGHT, provenance=prov))
            n_trees += 1
        if opts.scatter:
            capped = False
            for f in sorted(classified.areas, key=lambda a: a.id):
                cls = f.tags["_class"]
                dens = SCATTER_DENSITY.get(cls)
                if dens is None or (cls == "grass" and f.tags.get("leisure") != "park"):
                    continue
                rng = random.Random(stable_hash(f.id) ^ opts.seed)
                remaining = opts.max_trees - n_trees
                if remaining <= 0:
                    capped = True
                    break
                for k, (x, y) in enumerate(scatter_points(f, dens, rng, remaining, bounds=scene)):
                    if not area.contains(x, y) or blocked(x, y):
                        continue
                    s = 0.75 + rng.random() * 0.5
                    sid = f"scatter:{f.id}#{k}"
                    budget.charge(sid, *tree_cost)
                    add(ObjectSpec(f"tree_s{stable_hash(f.id) % 1000000:06d}_{k}", sid, "vegetation", "Vegetation",
                                   mesh_key="tree_generic",
                                   location=(x, y, terrain_height(terrain, x, y) - z_offset),
                                   rotation_z=rng.random() * 2 * math.pi, scale=s,
                                   provenance={"position": f"inferred:procedural scatter in {f.id} ({cls})",
                                               "height": "inferred:procedural"}))
                    n_trees += 1
            if capped:
                plan.report["warnings"].append(f"tree limit {opts.max_trees} reached; scatter truncated")
        plan.count("trees", n_trees)
    plan.report["counts"]["objects"] = len(plan.objects)
    plan.report["z_offset_m"] = z_offset
    plan.report["budget"] = budget.to_dict()
    # Ensure unique object names (Blender truncates at 63 bytes; keep ours shorter).
    seen = {}
    for o in plan.objects:
        base = o.name[:56]
        n = seen.get(base, 0)
        seen[base] = n + 1
        o.name = base if n == 0 else f"{base}.{n:03d}"
    return plan
