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
estimate (buildings) or the exact final count (roads; the count itself streams
terrain triangles and stops as soon as it exceeds the remaining budget). Exceeding
them is a hard :class:`LimitError` naming the feature, so a
plan is never silently incomplete. Per-feature limits (ring vertices,
triangulation work) instead reject just that feature and report it in
``invalid_features``.
"""

import hashlib
import math
import random
import re
import struct

from . import bridges, dsm, passages, roofs, tunnels
from .errors import LimitError, MapBuilderError
from .mesh import MeshData
from .structures import StageContext, finalize_probes
from .triangulate import DEFAULT_MAX_WORK, TriangulationError, dedupe_ring, triangulate, validate_rings
from .triangulate import _Work as _TopologyWork

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
        # manifest passage_probes entries ({id, kind, feature, path_map, radius_m}); emitted by the bridge stage
        self.passage_probes = []

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

    def remaining(self):
        """(vertices, triangles) still available, excluding any pending reservation."""
        self.release()
        return self.max_vertices - self.vertices, self.max_triangles - self.triangles

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


TERRAIN_EDGE_TOL_M = 1e-3  # footprints/points may exceed the terrain extent by at most this much


def terrain_extent(grid):
    """(x0, y0, x1, y1) of the terrain mesh."""
    return grid.x0, grid.y0, grid.x0 + (grid.nx - 1) * grid.spacing, grid.y0 + (grid.ny - 1) * grid.spacing


def inside_terrain(grid, x, y, tol=TERRAIN_EDGE_TOL_M):
    x0, y0, x1, y1 = terrain_extent(grid)
    return x0 - tol <= x <= x1 + tol and y0 - tol <= y <= y1 + tol


def footprint_terrain_range(grid, rings):
    """(min, max) of the terrain surface over a footprint (outer ring + holes, holes excluded).

    The terrain is piecewise planar, so its extremes over the footprint lie at ring
    vertices, grid nodes strictly inside the footprint, or where ring edges cross
    grid lines and cell diagonals; all of those are evaluated."""
    zs = [p[2] for p in footprint_terrain_samples(grid, rings)]
    return min(zs), max(zs)


def footprint_terrain_samples(grid, rings):
    """(x, y, terrain z) at every candidate point of :func:`footprint_terrain_range`: ring
    vertices, ring crossings of grid lines and cell diagonals, and grid nodes inside the
    footprint. Any function that is linear on each terrain triangle (e.g. terrain minus a
    planar roof underside) takes its extremes over the footprint at these points."""
    s, gx0, gy0 = grid.spacing, grid.x0, grid.y0
    zs = [(p[0], p[1], terrain_height(grid, p[0], p[1])) for r in rings for p in r]
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
                        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                        zs.append((x, y, terrain_height(grid, x, y)))
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
                zs.append((gx0 + i * s, y, h[j][i]))
    return zs


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

    ``height`` is the total height. Without an explicit ``height`` tag, the
    storey-derived height (building:levels x 3 m) is the eave height and a known
    roof source (roof:height / roof:levels) is added on top; see :func:`_building_height`."""
    h, min_h, roof_h, prov, eave_based = _building_height(tags)
    if eave_based:
        h += roof_h or 0.0
    return h, min_h, roof_h, prov


def _building_height(tags):
    """Returns (height, min_height, roof_height_or_None, provenance dict, eave_based).

    OSM semantics: ``height`` is the total height (roof included); building:levels
    excludes roof levels. So if ``height`` is used, ``eave_based`` is False and the roof
    is taken from within it; if the height comes from building:levels, ``eave_based`` is
    True, the returned height is the *eave* height and the roof is built on top of it.
    Type defaults are total heights.

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
    eave_based = False
    if roof_h is not None:
        prov["roof_height"] = "measured:osm roof:height"
    elif roof_levels is not None:
        roof_h = roof_levels * LEVEL_HEIGHT_M
        prov["roof_height"] = "inferred:roof:levels x 3 m"
    if h is not None:
        prov["height"] = "measured:osm height"
    elif levels is not None:
        h = levels * LEVEL_HEIGHT_M
        eave_based = True
        prov["height"] = "inferred:building:levels x 3 m to the eave, roof height added on top"
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
    return h, min_h, roof_h, prov, eave_based


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
    off = [p for r in rings for p in r if not inside_terrain(terrain, p[0], p[1])]
    if off:
        ex = terrain_extent(terrain)
        raise InvalidFeature(
            f"footprint extends beyond the terrain extent (x {ex[0]:g}..{ex[2]:g}, y {ex[1]:g}..{ex[3]:g} m; "
            f"{len(off)} vertex/vertices outside, e.g. ({off[0][0]:.2f}, {off[0][1]:.2f})); not generated")
    cx, cy = poly.centroid()
    pts2 = [(p[0] - cx, p[1] - cy) for r in rings for p in r]
    offsets = []
    o = 0
    for r in rings:
        offsets.append(list(range(o, o + len(r))))
        o += len(r)
    tris = triangulate(pts2, offsets[0], offsets[1:], max_work=max_work)
    outer = rings[0]

    height, min_h, roof_src, prov, eave_based = _building_height(tags)
    roof_src_label = prov.get("roof_height")
    roof_shape_tag = tags.get("roof:shape")
    local_outer = [(p[0] - cx, p[1] - cy) for p in outer]
    roof_dir = parse_number(tags.get("roof:direction"))
    plan = roofs.plan_roof(roof_shape_tag, local_outer, poly.holes, prov, tags.get("roof:orientation"), roof_dir)
    roof_shape = plan.shape_built
    if (roof_src is not None and roof_src <= 1e-6 and (roof_shape_tag in ("hipped", "pyramidal") or plan.skeleton)
            and (roof_shape == roof_shape_tag or plan.skeleton)
            and prov.get("roof_height", "").startswith("inferred:roof:levels")):
        # roof:levels=0 on a hipped/pyramidal roof gives no height: use the default roof height (D77)
        roof_src = None
        prov["roof_levels"] = f"ignored:roof:levels={tags.get('roof:levels')} (default roof height for a {roof_shape} roof)"

    # Roof height actually built; a source value that cannot be used is kept separately.
    xs, ys = [p[0] for p in outer], [p[1] for p in outer]
    short_side = min(max(xs) - min(xs), max(ys) - min(ys))
    wall_span = height - min_h
    reason = None
    if roof_shape == "flat":
        roof_h = 0.0
        reason = f"roof built flat (roof:shape={roof_shape_tag or 'flat'})"
    elif eave_based:
        # storey-derived eave: the roof sits on top of it, so it never eats into the walls
        if roof_src is None:
            roof_h = max(1.0, min(0.3 * short_side, 6.0))
            prov["roof_height"] = ("inferred:0.3 x footprint short side (1-6 m), added above the "
                                   "storey-derived eave")
        else:
            roof_h = roof_src
            if roof_h <= 1e-6:
                prov["roof_shape"] = f"fallback:flat (roof height 0 leaves no {roof_shape} roof)"
                roofs.drop_ridge_claims(prov)
                roof_shape, roof_h, plan = "flat", 0.0, roofs.flat_plan()
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
            roofs.drop_ridge_claims(prov)
            roof_shape, roof_h, plan = "flat", 0.0, roofs.flat_plan()
    if roof_src is not None and abs(roof_h - roof_src) > 1e-9:
        prov["roof_height_source"] = f"{roof_src_label} = {roof_src:g} m"
        prov["roof_height"] = f"fallback:{roof_h:g} m built ({reason})"
        prov["roof_height_reason"] = reason
    if eave_based:
        height += roof_h  # building:levels gave the eave; the total includes the roof built on top
    prov["roof_height_m"] = round(roof_h, 2)

    if plan.skeleton:
        across = False
        if roof_shape == "hipped" and tags.get("roof:orientation") is not None:
            prov["roof_orientation"] = (f"ignored:roof:orientation={tags['roof:orientation']} "
                                        "(every footprint edge slopes on a skeleton roof)")
    else:
        across = roofs.resolve_orientation(roof_shape, tags, prov, outer, roof_dir)

    top = height  # relative to the base datum
    wall_top_flat = top - roof_h
    elevated = min_h > 0
    base_z = min_h if elevated else -FOUNDATION_SINK_M

    skillion_z = roofs.skillion_surface(roof_shape, rings, roof_dir, top, roof_h, prov)

    samples = footprint_terrain_samples(terrain, rings)
    g_min = min(p[2] for p in samples)
    g_max = max(p[2] for p in samples)
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
        # The extrema test (highest terrain vs lowest eave) only fast-accepts. The roof
        # underside (eave plane, or the sloped plane of a skillion) and the terrain are both
        # linear on each terrain triangle within the footprint, so their difference takes
        # its extremes at the footprint sample points: compare them there, point by point.
        for x, y, z in samples:
            under = skillion_z((x, y)) if skillion_z else wall_top_flat
            if z - g_min >= under:
                raise InvalidFeature(
                    f"terrain inside footprint reaches eave/roof (at ({x:.2f}, {y:.2f}) it rises {z - g_min:.2f} m "
                    f"above the base datum; the roof underside there is at {under:.2f} m); no grading policy in v1")
        prov["terrain_clearance"] = ("terrain rises above the lowest eave but stays below the roof underside at every "
                                     "point of the footprint")
    if elevated and relief >= min_h:
        prov["terrain_warning"] = (f"terrain inside the footprint rises {relief:.2f} m above the base datum, into "
                                   f"the underside of the elevated volume at {min_h:.2f} m")

    if reserve is not None:
        roof_v, roof_t = roofs.roof_budget(plan, n_ring, len(tris))
        reserve(2 * n_ring + roof_v, 2 * n_ring + len(tris) + roof_t)

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

    mesh = MeshData(f"bld_{short_name(feature.id)}")
    split = []

    def add_face(idx, mat, col):
        split.append(roofs.add_planar_face(mesh, idx, mat, col))
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

    flat_bot = [i for rb in ring_idx_bottom for i in rb]
    for (a, b, c) in tris:
        add_face((flat_bot[a], flat_bot[c], flat_bot[b]), "MB Facade", facade)  # downward
    local_rings = [[(p[0] - cx, p[1] - cy) for p in r] for r in rings]
    roofs.build_roof(mesh, local_rings[0], local_rings[1:], wall_top_flat, roof_h, plan, tags, prov,
                     top_idx=ring_idx_top, tris=tris, add_face=add_face, roof_col=roof_col, facade=facade,
                     across=across, direction=roof_dir)
    if any(split):
        prov["roof_faces"] = (f"{sum(split)} non-planar face(s) (footprint not an exact rectangle) split into "
                              "triangles along the shorter diagonal")
    prov["roof_shape_built"] = plan.shape_built
    if plan.skeleton:
        prov["roof_construction"] = ("straight skeleton (a sloped face on every footprint edge)" if not plan.ends else
                                     f"straight skeleton, vertical gable wall on {len(plan.ends)} footprint edges")
    prov["height_m"] = round(height, 2)
    prov["eave_height_m"] = round(wall_top_flat, 2)
    if elevated:
        prov["elevated"] = (f"volume starts {min_h:.1f} m above the base datum; the space beneath is free "
                            "(an 'elevated' passage probe is emitted when it is at least 2.6 m high)")
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


def landcover_ring_problem(feature, max_work=DEFAULT_MAX_WORK):
    """None if the landcover polygon's rings form a valid polygon with holes, else the reason.

    Uses the same topology rules as building footprints (:func:`validate_rings`): simple
    rings, CCW outer, CW holes strictly inside it, no contacts between rings. The check is
    bounded by ``max_work`` geometric tests; a polygon that cannot be validated within it is
    reported too (never used unchecked)."""
    return ring_topology_problem(feature.geometry, max_work)


def ring_topology_problem(poly, max_work=DEFAULT_MAX_WORK, max_ring_vertices=None, _work=None):
    """None if ``poly``'s rings (outer plus holes) form a valid polygon with holes (:func:`validate_rings`,
    the rules :func:`build_building` triangulates with), else the reason. ``max_ring_vertices`` optionally
    bounds the total ring vertices first, as for building footprints. ``_work``: optional work counter
    (limit ``max_work``) whose count the caller reads afterwards."""
    rings = [dedupe_ring(poly.outer)] + [dedupe_ring(h) for h in poly.holes]
    if max_ring_vertices is not None:
        n_ring = sum(len(r) for r in rings)
        if n_ring > max_ring_vertices:
            return f"{n_ring} ring vertices exceed the per-footprint limit of {max_ring_vertices}"
    pts = [p for r in rings for p in r]
    offsets = []
    o = 0
    for r in rings:
        offsets.append(range(o, o + len(r)))
        o += len(r)
    work = _work if _work is not None else _TopologyWork(max_work)
    try:
        validate_rings(pts, offsets[0], offsets[1:], _work=work)
    except TriangulationError as e:
        if work.n > work.limit:
            return f"ring topology could not be validated within the work budget ({work.limit} geometric tests)"
        return f"invalid ring topology: {e}"
    return None


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


POLYLINE_DEDUP_TOL_M = 1e-3   # points closer than this are one point (the sweep path, and the bridge approach checks)


def _dedupe_indices(pts, tol=POLYLINE_DEDUP_TOL_M):
    """Indices of the points ``_dedupe_polyline`` keeps."""
    kept = []
    for k, p in enumerate(pts):
        if not kept or math.dist(p, pts[kept[-1]]) > tol:
            kept.append(k)
    return kept


def _dedupe_polyline(pts, tol=POLYLINE_DEDUP_TOL_M):
    return [(float(pts[k][0]), float(pts[k][1])) for k in _dedupe_indices(pts, tol)]


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


def _piece_rows(grid, piece):
    """Row range (j0, j1) of terrain cells the convex ``piece``'s bbox spans (empty if j0 > j1)."""
    x0, x1, y0, y1 = _bbox(piece)
    _, _, j0, j1 = _cell_range(grid, x0, x1, y0, y1)
    return j0, j1


def _piece_row_cells(grid, piece, j):
    """Column range (i0, i1) of the cells in row ``j`` whose square meets convex ``piece``, or None."""
    s = grid.spacing
    ya, yb = grid.y0 + j * s, grid.y0 + (j + 1) * s
    strip = _clip_halfplane(piece, (0.0, ya), (1.0, ya))
    if len(strip) >= 3:
        strip = _clip_halfplane(strip, (1.0, yb), (0.0, yb))
    if len(strip) < 3:
        return None
    xs = [p[0] for p in strip]
    i0, i1, _, _ = _cell_range(grid, min(xs), max(xs), ya, ya)
    return (i0, i1) if i0 <= i1 else None


def _piece_cells(grid, piece):
    """Terrain cells (i, j) whose square meets convex ``piece`` (row strips, not the bbox)."""
    j0, j1 = _piece_rows(grid, piece)
    for j in range(j0, j1 + 1):
        rng = _piece_row_cells(grid, piece, j)
        if rng:
            for i in range(rng[0], rng[1] + 1):
                yield i, j


def _convex_difference(a, b):
    """Interior-disjoint convex CCW pieces covering convex CCW ``a`` minus convex CCW ``b``.

    For each edge of ``b`` in turn, the part of the remainder strictly outside that edge
    is one output piece and the part inside it is the new remainder (which ends up as
    a & b and is dropped). Pieces with no area are omitted."""
    out = []
    rest = a
    n = len(b)
    for k in range(n):
        p, q = b[k], b[(k + 1) % n]
        if math.dist(p, q) <= 1e-12:
            continue
        outside = _clip_halfplane(rest, q, p)
        if len(outside) >= 3 and _area2(outside) > _MIN_AREA2:
            out.append(outside)
        rest = _clip_halfplane(rest, p, q)
        if len(rest) < 3 or _area2(rest) <= _MIN_AREA2:
            break
    return out


_MIN_AREA2 = 1e-9  # twice the area (m2) below which a road polygon/triangle is a numerical sliver


ROAD_PRIORITY = ("motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link",
                 "primary_link", "secondary_link", "tertiary_link", "residential", "unclassified",
                 "living_street", "service", "pedestrian", "track", "cycleway", "bridleway", "footway", "steps",
                 "path")


def road_priority(feature):
    """Ownership sort key of an at-grade road (smaller wins where roads overlap): highway
    class importance, then the wider ribbon, then the feature id (stable tie-break)."""
    hw = feature.tags.get("highway")
    rank = ROAD_PRIORITY.index(hw) if hw in ROAD_PRIORITY else len(ROAD_PRIORITY)
    return rank, -road_width(feature.tags)[0], feature.id


class RoadOwnership:
    """Ground already claimed by emitted higher-priority at-grade roads, per terrain triangle.

    Roads are built in :func:`road_priority` order; each subtracts the claimed polygons
    from its own ribbon in every terrain triangle, so no two road objects share area."""

    def __init__(self):
        self.cells = {}  # (j, i, upper) -> [(bbox, convex polygon, feature id)]

    def subtract(self, key, polys, work):
        """(remaining interior-disjoint convex polygons, {owner id: area removed m2})."""
        owned = self.cells.get(key)
        if not owned:
            return polys, {}
        removed = {}
        out = []
        for q in polys:
            pieces = [q]
            for ob, o, fid in owned:
                nxt = []
                for p in pieces:
                    work.add(len(o))
                    pb = _bbox(p)
                    if (pb[1] <= ob[0] or ob[1] <= pb[0] or pb[3] <= ob[2] or ob[3] <= pb[2]
                            or not _convex_overlap(p, o, eps=1e-12)):
                        nxt.append(p)
                        continue
                    diff = _convex_difference(p, o)
                    lost = (_area2(p) - sum(_area2(d) for d in diff)) / 2.0
                    if lost > 0:
                        removed[fid] = removed.get(fid, 0.0) + lost
                    nxt.extend(diff)
                pieces = nxt
                if not pieces:
                    break
            out.extend(pieces)
        return out, removed

    def add(self, key, polys, fid):
        cell = self.cells.setdefault(key, [])
        for q in polys:
            cell.append((_bbox(q), q, fid))


class RoadBudgetExceeded(LimitError):
    """The road's running welded-vertex or triangle count passed the remaining scene budget."""


class _RibbonWelder:
    """Incremental form of the final road triangles, shared by the budget count and the mesh emitter.

    ``add(i, j, upper, polygons)`` takes the polygons of one terrain triangle. Polygons are
    fanned; a triangle is kept only if it has area both before and after welding (vertices
    whose coordinates agree to ``tol_digits`` decimals are merged, keeping the first
    position). ``verts`` are (x, y, i, j, upper) - the terrain triangle that first produced
    them, whose plane gives the height (heights agree on shared edges) - and ``tris`` are
    index triples, so the counts are exactly the emitted mesh.

    With ``max_vertices``/``max_triangles``, :class:`RoadBudgetExceeded` is raised as soon as
    a running count exceeds them (counts only grow, so the final mesh would exceed them
    too; a final count exactly equal to the limit is accepted)."""

    def __init__(self, tol_digits=6, max_vertices=None, max_triangles=None, fid=None):
        self.tol_digits = tol_digits
        self.max_vertices = max_vertices
        self.max_triangles = max_triangles
        self.fid = fid
        self.index = {}
        self.verts = []
        self.tris = []

    def _exceeded(self):
        raise RoadBudgetExceeded(
            f"{self.fid}: road ribbon needs more than the remaining scene budget ({self.max_vertices} vertices / "
            f"{self.max_triangles} triangles left; counting stopped at {len(self.verts)} vertices / "
            f"{len(self.tris)} triangles); choose a smaller area, coarser terrain or raise the limit")

    def add(self, i, j, upper, polys):
        index, verts, tris, td = self.index, self.verts, self.tris, self.tol_digits
        mv = self.max_vertices
        for q in polys:
            for k in range(1, len(q) - 1):
                tri = (q[0], q[k], q[k + 1])
                if _area2(tri) <= _MIN_AREA2:  # sliver from clipping; zero area, nothing visible is lost
                    continue
                keys = [(round(p[0], td), round(p[1], td)) for p in tri]
                if len(set(keys)) < 3:
                    continue
                pos = [verts[index[key]][:2] if key in index else p for key, p in zip(keys, tri)]
                if _area2(pos) <= _MIN_AREA2:  # re-check on the welded positions (moved by <= 1e-6 m)
                    continue
                ids = []
                for key, p in zip(keys, pos):
                    v = index.get(key)
                    if v is None:
                        if mv is not None and len(verts) >= mv:
                            self._exceeded()
                        v = index[key] = len(verts)
                        verts.append((p[0], p[1], i, j, upper))
                    ids.append(v)
                if self.max_triangles is not None and len(tris) >= self.max_triangles:
                    self._exceeded()
                tris.append(tuple(ids))


def _ribbon_triangles(faces, tol_digits=6):
    """(vertices, triangles) of :class:`_RibbonWelder` for a list of (i, j, upper, polygons)."""
    w = _RibbonWelder(tol_digits)
    for i, j, upper, polys in faces:
        w.add(i, j, upper, polys)
    return w.verts, w.tris


def _ribbon_faces(grid, pieces, groups, work):
    """Yield (i, j, upper, X0, Y0, polygons) per terrain triangle the ribbon touches, in
    (row, column, lower/upper) order.

    ``polygons`` are interior-disjoint convex CCW polygons inside that terrain triangle
    whose union is the ribbon there: pieces that overlap (``groups`` are the components
    of the piece-overlap graph, refined per terrain triangle) are replaced by their union.

    Cells are found one terrain row at a time, so only one row of cell lists is held and a
    consumer that stops early (e.g. on a budget overrun) has not paid for the rest."""
    s = grid.spacing
    rows = [_piece_rows(grid, p) for p in pieces]
    order = sorted((pi for pi in range(len(pieces)) if rows[pi][0] <= rows[pi][1]), key=lambda pi: rows[pi][0])
    if not order:
        return
    j_end = max(rows[pi][1] for pi in order)
    active = []
    nxt = 0
    for j in range(rows[order[0]][0], j_end + 1):
        while nxt < len(order) and rows[order[nxt]][0] <= j:
            active.append(order[nxt])
            nxt += 1
        active = [pi for pi in active if rows[pi][1] >= j]
        if not active:
            continue
        cells = {}
        for pi in sorted(active):
            rng = _piece_row_cells(grid, pieces[pi], j)
            if rng is None:
                continue
            for i in range(rng[0], rng[1] + 1):
                work.add()
                cells.setdefault(i, []).append(pi)
        Y0 = grid.y0 + j * s
        for i in sorted(cells):
            X0 = grid.x0 + i * s
            c00, c10, c11, c01 = (X0, Y0), (X0 + s, Y0), (X0 + s, Y0 + s), (X0, Y0 + s)
            for upper, tri in ((False, (c00, c10, c11)), (True, (c00, c11, c01))):
                by_group = {}
                for pi in cells[i]:
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


SLIVER_ULPS = 4  # a face whose xy width is within this many float32 ulps of its coordinates is rounding noise


def _f32(v):
    return struct.unpack("<f", struct.pack("<f", v))[0]


def _f32_ulp(m):
    """Spacing of float32 values at magnitude ``m``."""
    return 2.0 ** (math.frexp(max(m, 1e-30))[1] - 24)


def drop_unstorable_slivers(local, tris, loc):
    """Draped ribbons are stored as float32 world positions (the collision/visual precision). A
    needle-thin face (clip residue on a steep slope) is up-facing in double precision but can lose
    its orientation in that rounding while staying non-degenerate in 3D, and the package validator
    then rejects the surface.

    The plan reaches storage on two paths, and both are checked: the core exporter (CLI) rounds once,
    ``f32(local + loc)``; the Blender add-on stores the mesh's local coordinates and the object location
    as float32 (``Mesh.vertices``, ``Object.location``) and bakes ``f32(f32(local) + f32(loc))``. The two
    roundings can disagree on a needle face, so a face is judged by whichever storage turns it.

    Returns ``(tris, dropped)``: ``tris`` without the faces whose stored normal is not up
    (z <= 0) on either path and whose xy width (2 * area / longest edge) is at most ``SLIVER_ULPS``
    float32 ulps of its world coordinates, i.e. the face is thinner than the storage can represent.
    ``dropped`` lists their ``(width_m, area_m2)``. A wider face that fails is a real fold: ``(None, None)``."""
    from .collision import is_degenerate
    lf = [_f32(v) for v in loc]
    stores = ([(_f32(x + loc[0]), _f32(y + loc[1]), _f32(z + loc[2])) for x, y, z in local],
              [(_f32(_f32(x) + lf[0]), _f32(_f32(y) + lf[1]), _f32(_f32(z) + lf[2])) for x, y, z in local])
    keep = []
    dropped = []
    for t in tris:
        la, lb, lc = (local[i] for i in t)
        area2 = (lb[0] - la[0]) * (lc[1] - la[1]) - (lb[1] - la[1]) * (lc[0] - la[0])
        if area2 <= 0:
            return None, None
        turned = None
        for W in stores:
            a, b, c = (W[i] for i in t)
            nz = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if nz <= 0 and not is_degenerate(a, b, c):
                turned = (a, b, c)
                break
        if turned is not None:
            longest = max(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in ((la, lb), (lb, lc), (lc, la)))
            width = area2 / longest
            ulp = _f32_ulp(max(abs(w) for p in turned for w in p[:2]))
            if width > SLIVER_ULPS * ulp:
                return None, None
            dropped.append((width, area2 / 2))
            continue
        keep.append(t)
    return keep, dropped

def build_road(feature, terrain, z_offset, reserve=None, max_work=DEFAULT_MAX_WORK, ownership=None, limit=None):
    """Returns (mesh, location, provenance), or (None, None, {"reason": ...}) if no valid ribbon exists.

    The footprint is the union of one rectangle per segment and a bevel triangle at
    every join; overlapping parts are merged so no two faces overlap. Faces are split at
    terrain grid lines and diagonals so each lies on one terrain plane, ``ROAD_LIFT_M``
    above it, facing up (+Z). Nothing is emitted outside the terrain extent.

    With ``ownership`` (a :class:`RoadOwnership`), ground already claimed by
    higher-priority roads is removed from this ribbon per terrain triangle, and the
    remaining ribbon is claimed once the road is built. If nothing remains, the result
    has ``"covered_by"`` set (the road is fully represented by those roads).

    The final triangle list and welded vertices are computed first (no mesh allocated);
    ``reserve(vertices, triangles)`` is then called with exactly the counts the mesh
    will have. With ``limit`` = (vertices, triangles) remaining in the scene budget, the
    counting itself is bounded: it streams terrain triangles and raises
    :class:`RoadBudgetExceeded` (a LimitError) as soon as the running welded-vertex or
    triangle count exceeds the limit (a mesh exactly at the limit is accepted). Raises
    InvalidFeature if the clip/union work exceeds ``max_work``."""
    width, wprov = road_width(feature.tags)
    pts = _dedupe_polyline(list(feature.geometry))
    if len(pts) < 2:
        return None, None, {"reason": "road collapses to fewer than 2 distinct points (1 mm tolerance); "
                                      "no ribbon generated"}
    half = width / 2.0
    pieces = _road_pieces(pts, half)
    work = _RibbonWork(max_work)
    groups = _overlap_groups(pieces, work=work)
    faces = []
    removed = {}
    lim_v, lim_t = limit if limit is not None else (None, None)
    welder = _RibbonWelder(max_vertices=lim_v, max_triangles=lim_t, fid=feature.id)
    # Streamed: each terrain triangle's polygons are welded and counted as soon as they are
    # produced, so a ribbon over the remaining budget stops at the first face that exceeds it.
    for i, j, upper, _X0, _Y0, polys in _ribbon_faces(terrain, pieces, groups, work):
        if ownership is not None:
            polys, rem = ownership.subtract((j, i, upper), polys, work)
            for fid, a in rem.items():
                removed[fid] = removed.get(fid, 0.0) + a
        if polys:
            welder.add(i, j, upper, polys)
            if ownership is not None:
                faces.append((i, j, upper, polys))
    verts, tris = welder.verts, welder.tris
    if not tris:
        if removed:
            owners = sorted(removed)
            return None, None, {"reason": "road ribbon lies entirely on higher-priority at-grade road(s) "
                                          f"{_id_list(owners)}; no faces of its own (represented by them)",
                                "covered_by": owners}
        return None, None, {"reason": "road ribbon lies outside the terrain extent; no ribbon generated"}
    gx0, gy0, gx1, gy1 = terrain_extent(terrain)
    clipped = any(b[0] < gx0 or b[1] > gx1 or b[2] < gy0 or b[3] > gy1 for b in (_bbox(p) for p in pieces))

    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    z0 = terrain_height(terrain, *pts[0]) - z_offset + ROAD_LIFT_M
    s = terrain.spacing
    local = []
    for x, y, i, j, upper in verts:
        h = _plane_height(terrain.heights, i, j, upper, (x - (gx0 + i * s)) / s, (y - (gy0 + j * s)) / s)
        local.append((x - cx, y - cy, h - z_offset + ROAD_LIFT_M - z0))
    tris, dropped = drop_unstorable_slivers(local, tris, (cx, cy, z0))
    if dropped is None:
        return None, None, {"reason": "road ribbon would contain folded faces; not generated"}
    if dropped:
        # Ownership (below) still claims the pre-filter polygons: the gap is thinner than the storage can
        # represent, so claiming it keeps lower-priority roads from re-covering it with their own slivers.
        used = sorted({v for t in tris for v in t})
        remap = {v: k for k, v in enumerate(used)}
        local = [local[v] for v in used]
        tris = [tuple(remap[v] for v in t) for t in tris]
        if not tris:
            return None, None, {"reason": "road ribbon has only sliver faces; not generated"}
    if reserve is not None:
        reserve(len(local), len(tris))
    mesh = MeshData(f"road_{short_name(feature.id)}")
    color = (0.12, 0.12, 0.12) if feature.tags.get("highway") not in FOOT else (0.35, 0.32, 0.28)
    for v in local:
        mesh.add_vertex(*v)
    for t in tris:
        mesh.add_face(t, "MB Road", color)
    if ownership is not None:
        for i, j, upper, polys in faces:
            ownership.add((j, i, upper), polys, feature.id)
    prov = {"width": wprov, "width_m": round(width, 2),
            "vertical": f"draped on the terrain mesh (+{ROAD_LIFT_M:g} m), split at terrain cell edges and diagonals",
            "joins": "bevel",
            "footprint": "union of segment rectangles and join bevels; overlapping parts merged, no overlapping faces"}
    if removed:
        owners = sorted(removed)
        prov["overlap"] = (f"{sum(removed.values()):.2f} m2 shared with higher-priority at-grade road(s) "
                           f"{_id_list(owners)} left to them (ownership: road class, width, feature id)")
    if dropped:
        prov["slivers_dropped"] = (f"{len(dropped)} face(s) thinner than float32 storage (max width "
                                    f"{max(w for w, _ in dropped):.1e} m, {sum(a for _, a in dropped):.1e} m2) omitted")
    if clipped:
        prov["terrain_edge"] = "ribbon trimmed at the terrain edge"
    return mesh, (cx, cy, z0), prov


def _id_list(ids, limit=10):
    shown = ", ".join(ids[:limit])
    return shown if len(ids) <= limit else f"{shown} and {len(ids) - limit} more"


OVERLAP_Z_TOL_M = 1e-6  # Z ranges sharing less than this count as disjoint (stacked solids)


def object_z_range(spec):
    """(min, max) map-frame Z of an emitted object's mesh: vertices with the object's transform
    applied (rotation is about Z, so only scale and location affect Z)."""
    zs = [v[2] for v in spec.mesh.vertices]
    a, b = min(zs) * spec.scale + spec.location[2], max(zs) * spec.scale + spec.location[2]
    return min(a, b), max(a, b)


def _check_building_overlaps(plan, candidates, built_specs):
    """Warn about kept footprint overlaps (``Classified.overlap_candidates``) whose emitted solids
    share a vertical range: both objects were generated and their map-frame Z extents overlap.
    Pairs with one side not generated, or stacked solids (disjoint Z), are not reported.
    This is a conservative screen: overlapping whole-object Z extents may still clear each other
    within the shared footprint (e.g. under a sloped roof), so the report says "may intersect"."""
    zr = {}
    hits = {}
    for c in candidates:
        pid, oid = c.get("part"), c.get("outline")
        sp, so = built_specs.get(pid), built_specs.get(oid)
        if sp is None or so is None:
            continue
        for fid, s in ((pid, sp), (oid, so)):
            if fid not in zr:
                zr[fid] = object_z_range(s)
        (plo, phi), (olo, ohi) = zr[pid], zr[oid]
        if plo < ohi - OVERLAP_Z_TOL_M and olo < phi - OVERLAP_Z_TOL_M:
            hits.setdefault(pid, []).append(oid)
            plan.report.setdefault("building_overlaps", []).append(
                {"part": pid, "outline": oid, "kind": c.get("kind"),
                 "part_z_m": [round(plo, 2), round(phi, 2)], "outline_z_m": [round(olo, 2), round(ohi, 2)]})
    for pid, oids in hits.items():
        plan.report["warnings"].append(
            f"{pid}: building:part overlaps building outline(s) {_id_list(oids)} without lying within them, "
            f"and their generated solids share a vertical range (map-frame Z {zr[pid][0]:.2f}..{zr[pid][1]:.2f} m "
            f"vs {', '.join(f'{zr[o][0]:.2f}..{zr[o][1]:.2f} m' for o in oids[:10])}); both are kept as mapped "
            "(the part does not replace them), so their solids may intersect (conservative check: "
            "footprint overlap plus whole-object Z extents, not an exact solid intersection test)")


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
                 max_ring_vertices=MAX_RING_VERTICES, max_triangulation_work=DEFAULT_MAX_WORK,
                 max_mask_validation_work=None, bridge_piers=True):
        self.bridge_piers = bridge_piers
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
        # cumulative ring-topology tests for the DSM mask (None: dsm.MASK_VALIDATION_WORK_BUDGET)
        self.max_mask_validation_work = max_mask_validation_work


TERRAIN_SURFACE = "piecewise planar, cells split along the (i,j)-(i+1,j+1) diagonal"
DSM_CORRECTED_SURFACE = "inferred:DSM corrected (buildings/trees/forest/bridges masked); " + TERRAIN_SURFACE


def dsm_obstacles(classified, areas=None, extent=None, max_ring_vertices=MAX_RING_VERTICES,
                  max_work=DEFAULT_MAX_WORK, excluded=None, work_budget=None, stats=None):
    """Mask inputs for :func:`dsm.apply_correction` from classified features, whether or not they are
    generated: every building footprint (outlines replaced by building:part features and footprints whose
    centroid lies outside the area included; holes kept), OSM trees (``mask_trees`` outside the area
    included), forest/wood landcover (plus the margin-only ``mask_areas``, which are never generated), and
    bridge ways with the road width the generator would use for them.

    Only valid polygons are used, since an invalid ring set (e.g. a hole crossing its outer ring) would
    mask points outside the feature: ``areas`` are the already validated landcover areas (default: the
    classified areas checked with :func:`landcover_ring_problem`), and building footprints and
    ``mask_areas`` must pass :func:`ring_topology_problem` (buildings with the generator's
    ``max_ring_vertices``), each within ``max_work``. If ``extent`` (x0, y0, x1, y1, the terrain grid) is
    given, features whose bbox lies farther from it than their mask buffer are dropped up front.
    ``excluded`` (a dict) receives the per-kind counts of footprints/areas excluded for invalid geometry.

    The validation done here for the mask is charged to one cumulative budget, ``work_budget`` geometric
    tests (default :data:`dsm.MASK_VALIDATION_WORK_BUDGET`), checked as it goes: each candidate may use at
    most what is left, and :class:`dsm.MaskWorkExceeded` is raised as soon as it is used up. Identical
    geometries (e.g. relations sharing their rings) are validated and masked once. ``stats`` (a dict)
    receives ``validation_work``, the geometric tests used, including those classify spent assembling the
    margin-only candidates (``classified.mask_work``; ``mask_work_exceeded`` raises at once).

    Footprints and forests listed in ``classified.mask_suppressed`` (ways whose footprint, with its holes,
    a multipolygon using them as an outer supplies) are left out, so a solid copy never fills a courtyard."""
    from .osm import _expand, _rect_overlaps
    if excluded is None:
        excluded = {}
    if work_budget is None:
        work_budget = dsm.MASK_VALIDATION_WORK_BUDGET
    used = [getattr(classified, "mask_work", 0)]
    suppressed = getattr(classified, "mask_suppressed", ())
    if areas is None:
        areas = [a for a in classified.areas if not landcover_ring_problem(a, max_work)]
        bad = sum(1 for a in classified.areas if a.tags.get("_class") == "forest") - sum(
            1 for a in areas if a.tags.get("_class") == "forest")
        if bad:
            excluded["forest_areas"] = bad
    near = (lambda bbox, m: True) if extent is None else (lambda bbox, m: _rect_overlaps(bbox, _expand(extent, m)))

    def geometry_key(poly):
        return (tuple(map(tuple, poly.outer)),) + tuple(tuple(map(tuple, h)) for h in poly.holes)

    def problem(poly, ring_vertices):
        remaining = work_budget - used[0]
        if remaining <= 0:
            raise dsm.MaskWorkExceeded(f"DSM mask validation needs more than {work_budget} ring topology tests "
                                       "(the mask validation work budget)")
        limit = min(max_work, remaining)
        work = _TopologyWork(limit)
        p = ring_topology_problem(poly, limit, ring_vertices, _work=work)
        used[0] += min(work.n, limit)
        if p and work.n > limit and limit < max_work:
            raise dsm.MaskWorkExceeded(f"DSM mask validation needs more than {work_budget} ring topology tests "
                                       "(the mask validation work budget)")
        return p

    try:
        exceeded = getattr(classified, "mask_work_exceeded", None)
        if exceeded or used[0] > work_budget:
            raise dsm.MaskWorkExceeded(exceeded or f"DSM mask validation needs more than {work_budget} ring "
                                                   "topology tests (the mask validation work budget)")
        buildings, seen, keys, bad = [], set(), {}, 0
        for f in (list(classified.buildings) + list(getattr(classified, "outline_features", {}).values())
                  + list(getattr(classified, "outside_buildings", ()))):
            key = (f.id, id(f.geometry))
            if key in seen:
                continue
            seen.add(key)
            if f.id.split("#")[0] in suppressed or not near(f.geometry.bbox(), dsm.BUILDING_BUFFER_M):
                continue
            gk = geometry_key(f.geometry)
            if gk not in keys:
                keys[gk] = problem(f.geometry, max_ring_vertices)
                if not keys[gk]:
                    buildings.append([f.geometry.outer] + list(f.geometry.holes))
            if keys[gk]:
                bad += 1
        if bad:
            excluded["buildings"] = bad
        trees = [tuple(f.geometry) for f in list(classified.trees) + list(getattr(classified, "mask_trees", ()))
                 if near((f.geometry[0], f.geometry[1]) * 2, dsm.TREE_RADIUS_M)]
        forests, keys, bad = [], {}, 0
        for a in areas:   # validated by the caller (they also colour the terrain): not charged again
            if (a.tags.get("_class") == "forest" and a.id.split("#")[0] not in suppressed
                    and near(a.geometry.bbox(), 0.0)):
                gk = geometry_key(a.geometry)
                if gk not in keys:
                    keys[gk] = None
                    forests.append([a.geometry.outer] + list(a.geometry.holes))
        for a in getattr(classified, "mask_areas", ()):
            if a.tags.get("_class") == "forest" and near(a.geometry.bbox(), 0.0):
                gk = geometry_key(a.geometry)
                if gk not in keys:
                    keys[gk] = problem(a.geometry, None)
                    if not keys[gk]:
                        forests.append([a.geometry.outer] + list(a.geometry.holes))
                if keys[gk]:
                    bad += 1
        if bad:
            excluded["forest_areas"] = excluded.get("forest_areas", 0) + bad
    finally:
        if stats is not None:
            stats["validation_work"] = used[0]
    bridges = []
    widths = {}   # fragments of one way share its tags: its width is parsed once, not per fragment
    for f in getattr(classified, "bridges", ()):
        key = id(f.tags)
        if key not in widths:
            widths[key] = (f.tags, road_width(f.tags)[0])   # the tags kept alive so the id stays unique
        pts, width = list(f.geometry), widths[key][1]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if near((min(xs), min(ys), max(xs), max(ys)), width / 2.0 + dsm.BRIDGE_BUFFER_M):
            bridges.append((pts, width))
    return buildings, trees, forests, bridges


def build_plan(area, terrain, classified, options=None, dsm_correction=None):
    """Scene plan from the elevation grid ``terrain`` and the classified features.

    ``dsm_correction``: None (auto: on for surface-model sources such as Copernicus GLO-30, off for local
    files), True or False. When applied, the corrected grid (see :mod:`dsm`) is used for the terrain mesh
    and everything placed on it; ``report['terrain_correction']`` always records the outcome. The classified
    content and its selection do not depend on the correction, but terrain-dependent eligibility does: a
    building whose roof a DSM spike pierces (terrain above the roof underside, rejected as invalid on the
    uncorrected grid) is generated when the correction lowers that spike. That is intended: recovering
    buildings wrongly rejected because of their own DSM surface is part of what the correction is for."""
    opts = options or PlanOptions()
    # Landcover ring topology is validated first: only valid polygons colour the terrain, drive scatter
    # and (forests) feed the DSM mask, so an invalid ring set never lowers terrain outside its feature.
    areas, area_invalid = [], []
    for a in classified.areas:
        problem = landcover_ring_problem(a, opts.max_triangulation_work)
        if problem:
            area_invalid.append({"id": a.id, "reason": f"{a.tags.get('_class')} area: {problem}; not used for "
                                                       "terrain colouring or scatter (nor the DSM mask)"})
        else:
            areas.append(a)
    enabled, _ = dsm.resolve(dsm_correction, terrain.provenance)
    excluded, mask_stats, skip = {}, {}, None
    unavailable = getattr(classified, "mask_unavailable", None)
    obstacles = ((), (), (), ())
    if enabled:
        bad_forests = sum(1 for e in area_invalid if e["reason"].startswith("forest area:"))
        if bad_forests:
            excluded["forest_areas"] = bad_forests
        try:
            if not unavailable:   # incomplete candidates (the DSM mask request failed): skipped below
                obstacles = dsm_obstacles(classified, areas, terrain_extent(terrain), opts.max_ring_vertices,
                                          opts.max_triangulation_work, excluded, opts.max_mask_validation_work,
                                          mask_stats)
        except dsm.MaskWorkExceeded as exc:
            skip = str(exc)
    terrain, correction, dsm_warning = dsm.apply_correction(terrain, dsm_correction, *obstacles,
                                                            excluded_invalid=excluded,
                                                            validation_work=mask_stats.get("validation_work"),
                                                            validation_skipped=skip, mask_unavailable=unavailable)
    zmin, _ = terrain.min_max()
    z_offset = math.floor(zmin)
    area.frame.z_offset = z_offset
    plan = ScenePlan(area.frame, area)
    plan.report["unsupported_features"] = list(classified.unsupported)
    plan.report["invalid_features"] = list(classified.invalid) + area_invalid
    plan.report["warnings"].extend(getattr(classified, "warnings", ()))
    plan.report["terrain_correction"] = correction
    if dsm_warning:
        plan.report["warnings"].append(dsm_warning)
    plan.count("buildings_outside_area", classified.outside)
    budget = SceneBudget(opts.max_vertices, opts.max_triangles)
    invalid = plan.report["invalid_features"]

    def add(spec):
        if len(plan.objects) >= opts.max_objects:
            raise LimitError(f"{spec.mb_id}: object limit {opts.max_objects} reached")
        plan.objects.append(spec)

    budget.reserve("terrain:grid", terrain.nx * terrain.ny, 2 * (terrain.nx - 1) * (terrain.ny - 1))
    coverage = {}
    tmesh = build_terrain(terrain, z_offset, areas, coverage)
    tmesh.grid_layout = (terrain.nx, terrain.ny, terrain.x0, terrain.y0, terrain.spacing)   # lets probes find triangles by cell
    budget.commit(tmesh)
    if correction["applied"]:
        plan.inferred("terrain.surface")
    add(ObjectSpec("terrain", "terrain:grid", "terrain", "Terrain", mesh=tmesh,
                   provenance={"elevation": terrain.provenance.get("provider"), "spacing_m": terrain.spacing,
                               "surface": DSM_CORRECTED_SURFACE if correction["applied"] else TERRAIN_SURFACE}))
    for a in areas:
        if not coverage.get(a.id):
            plan.report["unsupported_features"].append(
                {"id": a.id, "reason": f"{a.tags['_class']} area contains no terrain cell centre at "
                                       f"{terrain.spacing:g} m spacing; not represented in terrain colouring"})
    ex = terrain_extent(terrain)
    if (ex[0] > -area.width / 2 + TERRAIN_EDGE_TOL_M or ex[1] > -area.height / 2 + TERRAIN_EDGE_TOL_M
            or ex[2] < area.width / 2 - TERRAIN_EDGE_TOL_M or ex[3] < area.height / 2 - TERRAIN_EDGE_TOL_M):
        plan.report["warnings"].append(
            f"terrain extent (x {ex[0]:g}..{ex[2]:g}, y {ex[1]:g}..{ex[3]:g} m) does not cover the scene area; "
            "nothing is generated outside it (buildings and trees there are reported invalid, roads are trimmed, "
            "landcover only colours terrain cells)")

    footprints = []
    road_segments = []
    ctx = StageContext(area, terrain, z_offset, budget, opts, add, classified, road_segments)
    if opts.buildings:
        def build_one(f, extra_prov=None, reason_prefix=""):
            """Build one footprint; returns True if generated, else reports it in invalid_features."""
            pre = passages.take_prebuilt(ctx, f.id)
            try:
                if pre is not None:
                    mesh, origin, prov = pre
                    budget.reserve(f.id, len(mesh.vertices), sum(len(fc) - 2 for fc in mesh.faces))
                else:
                    mesh, origin, prov = build_building(
                        f, terrain, z_offset, opts.seed, max_ring_vertices=opts.max_ring_vertices,
                        max_work=opts.max_triangulation_work,
                        reserve=lambda v, t, fid=f.id: budget.reserve(fid, v, t))
            except TriangulationError as e:
                budget.release()
                invalid.append({"id": f.id, "reason": f"{reason_prefix}triangulation failed: {e}"})
                return False
            except InvalidFeature as e:
                budget.release()
                invalid.append({"id": f.id, "reason": f"{reason_prefix}{e}"})
                return False
            budget.commit(mesh)
            if extra_prov:
                prov.update(extra_prov)
            for k, v in prov.items():
                if isinstance(v, str) and v.startswith(("inferred", "fallback")) and not k.endswith("_source"):
                    plan.inferred(f"building.{k}")
            if "elevated" in prov and not getattr(f, "passage_upper", False):
                passages.elevated_probe(plan, ctx, f)
            if "terrain_warning" in prov:
                plan.report["warnings"].append(f"{f.id}: {prov['terrain_warning']}")
            if "rejected_tags" in prov:
                plan.report["warnings"].append(f"{f.id}: out-of-range tags ignored ({prov['rejected_tags']})")
            spec = ObjectSpec(mesh.name, f.id, "building", "Buildings", mesh=mesh, location=origin, provenance=prov)
            add(spec)
            built_specs[f.id] = spec
            footprints.append((f.geometry, f.geometry.bbox()))
            if f.geometry.holes:
                plan.count("buildings_with_courtyards")
            plan.count("buildings")
            return True

        built_specs = {}
        built = set()
        for f in classified.buildings:
            for piece in passages.split(plan, ctx, f):
                if build_one(piece, getattr(piece, "extra_prov", None)):
                    built.add(piece.id)
        # Outlines replaced by building:part features (Simple 3D Buildings). The parts were built
        # first; an outline none of whose parts survived is generated itself (otherwise the
        # building would vanish). If only some parts survived, the outline is NOT generated (it
        # would overlap the surviving parts): it is partially represented, which is reported.
        # ``outline_parts`` may also list parts already rejected by classify (not within their
        # declared outline); they are absent from ``classified.buildings`` and so count as rejected.
        outline_parts = getattr(classified, "outline_parts", {})
        outline_features = getattr(classified, "outline_features", {})
        replaced, restored, partial = [], [], []
        for oid in classified.replaced_outlines:
            pids = outline_parts.get(oid)
            if not pids or oid not in outline_features:
                replaced.append(oid)  # no fallback information (hand-built Classified): as before
                continue
            ok = [p for p in pids if p in built]
            rejected = [p for p in pids if p not in built]
            if ok and not rejected:
                replaced.append(oid)
            elif ok:
                replaced.append(oid)
                partial.append({"id": oid, "built_parts": ok, "rejected_parts": rejected})
                plan.report["warnings"].append(
                    f"{oid}: building outline only partially represented: building:part feature(s) "
                    f"{_id_list(rejected)} could not be generated (see invalid_features); the surviving part(s) "
                    f"{_id_list(ok)} are kept and the outline is not generated, to avoid overlapping solids")
            else:
                note = (f"fallback:outline generated because all of its building:part features "
                        f"({_id_list(pids)}) were rejected (see invalid_features)")
                if build_one(outline_features[oid], {"building_parts": note},
                             reason_prefix="building outline (fallback after all of its building:part features "
                                           f"{_id_list(pids)} were rejected): "):
                    restored.append({"id": oid, "rejected_parts": pids})
                    plan.report["warnings"].append(
                        f"{oid}: all building:part feature(s) {_id_list(pids)} were rejected (see "
                        "invalid_features); the building outline is generated instead")
        if replaced:
            plan.report["building_outlines_replaced_by_parts"] = replaced
        if restored:
            plan.report["building_outlines_restored"] = restored
        if partial:
            plan.report["building_outlines_partially_represented"] = partial
        _check_building_overlaps(plan, getattr(classified, "overlap_candidates", ()), built_specs)
    elif classified.replaced_outlines:
        plan.report["building_outlines_replaced_by_parts"] = list(classified.replaced_outlines)
    if opts.roads:
        # All roads are at grade; bridges and tunnels are routed to their own stages below.
        # are built in ownership order so overlapping ground belongs to exactly one road; the
        # objects are listed in the original feature order.
        ownership = RoadOwnership()
        road_specs = {}
        passage_roads = passages.handled_roads(ctx)
        road_notes = {f.id: note for f, note in passage_roads}
        road_feats = list(classified.roads) + [f for f, _ in passage_roads]
        order = {id(f): k for k, f in enumerate(road_feats)}
        for f in sorted(road_feats, key=road_priority):
            try:
                mesh, origin, prov = build_road(f, terrain, z_offset,
                                                reserve=lambda v, t, fid=f.id: budget.reserve(fid, v, t),
                                                max_work=opts.max_triangulation_work, ownership=ownership,
                                                limit=budget.remaining())
            except InvalidFeature as e:
                budget.release()
                invalid.append({"id": f.id, "reason": str(e)})
                continue
            if mesh is None:
                budget.release()
                if prov.get("covered_by"):
                    plan.report["warnings"].append(f"{f.id}: {prov['reason']}")
                    plan.count("roads_fully_covered")
                    w = road_width(f.tags)[0]
                    for a, b in zip(f.geometry, f.geometry[1:]):
                        road_segments.append((a, b, w / 2 + 1.0))
                else:
                    invalid.append({"id": f.id, "reason": prov["reason"]})
                continue
            budget.commit(mesh)
            if prov["width"].startswith("inferred"):
                plan.inferred("road.width")
            if "overlap" in prov:
                plan.count("roads_clipped_by_higher_priority")
            if f.id in road_notes:
                prov["passage"] = road_notes[f.id]
            if "terrain_edge" in prov:
                plan.count("roads_trimmed_at_terrain_edge")
            road_specs[order[id(f)]] = ObjectSpec(mesh.name, f.id, "road", "Roads", mesh=mesh, location=origin,
                                                  provenance=prov)
            w = prov["width_m"]
            for a, b in zip(f.geometry, f.geometry[1:]):
                road_segments.append((a, b, w / 2 + 1.0))
            plan.count("roads")
        for k in sorted(road_specs):
            add(road_specs[k])
    bridges.build(plan, ctx)
    tunnels.build(plan, ctx)
    passages.build(plan, ctx)
    ctx.flush_unsupported(plan)
    if opts.trees:
        tmpl = plan.shared_meshes["tree_generic"] = tree_mesh()
        tree_cost = (len(tmpl.vertices), mesh_triangle_count(tmpl))
        scene = (-area.width / 2, -area.height / 2, area.width / 2, area.height / 2)
        fp_buckets = _Buckets(footprints, bounds=scene)
        seg_buckets = _Buckets([((a, b, r), (min(a[0], b[0]) - r, min(a[1], b[1]) - r,
                                             max(a[0], b[0]) + r, max(a[1], b[1]) + r)) for a, b, r in road_segments],
                               cell=25.0, bounds=scene)

        keep_buckets = _Buckets([((a, b, r), (min(a[0], b[0]) - r, min(a[1], b[1]) - r,
                                              max(a[0], b[0]) + r, max(a[1], b[1]) + r)) for a, b, r in ctx.keepout],
                                cell=25.0, bounds=scene)

        def in_segment(buckets, x, y):
            for a, b, r in buckets.query(x, y):
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = dx * dx + dy * dy
                t = 0.0 if L == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L))
                if math.hypot(x - a[0] - t * dx, y - a[1] - t * dy) < r:
                    return True
            return False

        def blocked(x, y):
            for poly in fp_buckets.query(x, y):
                if poly.contains(x, y):
                    return True
            return in_segment(seg_buckets, x, y) or in_segment(keep_buckets, x, y)

        deck_blocked = bridges.tree_blocker(ctx)
        n_trees = 0
        for k_tree, f in enumerate(classified.trees):
            if n_trees >= opts.max_trees:
                plan.report["warnings"].append(f"tree limit {opts.max_trees} reached; "
                                               f"{len(classified.trees) - k_tree} remaining OSM trees skipped")
                break
            x, y = f.geometry
            if not inside_terrain(terrain, x, y):
                invalid.append({"id": f.id, "reason": "tree lies outside the terrain extent; not generated"})
                continue
            if in_segment(keep_buckets, x, y):
                invalid.append({"id": f.id, "reason": "tree stands in a tunnel portal or cut zone; not generated"})
                continue
            if deck_blocked(x, y):
                invalid.append({"id": f.id, "reason": "tree lies within a bridge deck footprint; not generated"})
                continue
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
            for f in sorted(areas, key=lambda a: a.id):
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
                    # procedural points are only placed where the scene has terrain
                    if not area.contains(x, y) or not inside_terrain(terrain, x, y, tol=0.0) or blocked(x, y):
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
    finalize_probes(plan, ctx)
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
