"""Turn classified features + elevation into an editable scene plan.

The plan is plain data (no bpy). The Blender layer instantiates it; tests use
it directly. Every generated object records provenance: which values were
*measured/provided* by a source and which were *inferred* defaults.
"""

import hashlib
import math
import random
import re

from .mesh import MeshData
from .triangulate import TriangulationError, triangulate

LEVEL_HEIGHT_M = 3.0
FOUNDATION_SINK_M = 0.3
ROAD_LIFT_M = 0.12
ROAD_SEGMENT_M = 4.0

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


def stable_hash(text):
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def short_name(fid):
    # "osm:way/123#1" -> "way_123_1"
    return re.sub(r"[^A-Za-z0-9]+", "_", fid.split(":", 1)[-1]).strip("_")


def parse_length(value):
    """OSM length -> metres, or None. Accepts '12', '12 m', '12.5m', "40'", "10'6\"", '30 ft'."""
    if value is None:
        return None
    v = value.strip().lower().replace(",", ".")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(m|meter|meters|metre|metres)?", v)
    if m:
        return float(m.group(1))
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(ft|feet)", v)
    if m:
        return float(m.group(1)) * 0.3048
    m = re.fullmatch(r"(\d+)'(?:\s*(\d+(?:\.\d+)?)\")?", v)
    if m:
        return int(m.group(1)) * 0.3048 + float(m.group(2) or 0) * 0.0254
    return None


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


# --- Buildings --------------------------------------------------------------

def building_height(tags):
    """Returns (height, min_height, roof_height_or_None, provenance dict)."""
    prov = {}
    h = parse_length(tags.get("height"))
    levels = parse_number(tags.get("building:levels"))
    roof_levels = parse_number(tags.get("roof:levels"))
    roof_h = parse_length(tags.get("roof:height"))
    if roof_h is not None:
        prov["roof_height"] = "measured:osm roof:height"
    elif roof_levels is not None and roof_levels >= 0:
        roof_h = roof_levels * LEVEL_HEIGHT_M
        prov["roof_height"] = "inferred:roof:levels x 3 m"
    if h is not None and 0.5 <= h <= 1000:
        prov["height"] = "measured:osm height"
    elif levels is not None and 0 < levels <= 300:
        h = levels * LEVEL_HEIGHT_M + (roof_h or 0.0)
        prov["height"] = "inferred:building:levels x 3 m (+ roof)"
    else:
        btype = tags.get("building", tags.get("building:part", "yes"))
        h = {"house": 7.0, "detached": 7.0, "semidetached_house": 7.0, "bungalow": 4.5, "garage": 3.0,
             "garages": 3.0, "shed": 2.5, "hut": 2.5, "carport": 2.5, "roof": 4.0}.get(btype, 9.0)
        prov["height"] = f"inferred:default for building={btype}"
    min_h = parse_length(tags.get("min_height"))
    if min_h is not None:
        prov["min_height"] = "measured:osm min_height"
    else:
        ml = parse_number(tags.get("building:min_level"))
        if ml is not None and ml > 0:
            min_h = ml * LEVEL_HEIGHT_M
            prov["min_height"] = "inferred:building:min_level x 3 m"
    min_h = min_h or 0.0
    if min_h >= h:
        min_h = 0.0
        prov["min_height"] = "ignored:min_height >= height"
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


def _is_convex(ring):
    n = len(ring)
    for k in range(n):
        a, b, c = ring[k - 1], ring[k], ring[(k + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-9:
            return False
    return True


def build_building(feature, terrain, z_offset, seed=0):
    """Returns (MeshData in object-local coords, location, provenance) or raises TriangulationError."""
    poly = feature.geometry
    tags = feature.tags
    height, min_h, roof_h, prov = building_height(tags)
    rings = [poly.outer] + poly.holes
    ground = [terrain.sample(x, y) for r in rings for (x, y) in r]
    g_min, g_max = min(ground), max(ground)
    cx, cy = poly.centroid()
    origin = (cx, cy, g_min - z_offset)
    top = height  # relative to g_min
    roof_shape = tags.get("roof:shape", "flat")
    prov["roof_shape"] = "measured:osm roof:shape" if "roof:shape" in tags else "inferred:flat"
    prov["ground"] = "terrain minimum under footprint"
    if g_max - g_min > 0:
        prov["ground_slope_m"] = round(g_max - g_min, 2)

    short_side = min(poly.bbox()[2] - poly.bbox()[0], poly.bbox()[3] - poly.bbox()[1])
    if roof_shape != "flat" and roof_h is None:
        roof_h = max(1.0, min(0.3 * short_side, 6.0))
        prov["roof_height"] = "inferred:0.3 x footprint short side (1-6 m)"
    if roof_shape == "flat":
        roof_h = 0.0
    roof_h = min(roof_h or 0.0, 0.6 * (height - min_h))

    supported = {"flat", "skillion", "pyramidal", "gabled", "hipped"}
    if roof_shape not in supported:
        prov["roof_shape"] = f"fallback:flat (roof:shape={roof_shape} not modelled in v1)"
        roof_shape, roof_h = "flat", 0.0
    if poly.holes and roof_shape not in ("flat", "skillion"):
        prov["roof_shape"] = f"fallback:flat (roof:shape={roof_shape} with courtyard)"
        roof_shape, roof_h = "flat", 0.0
    if roof_shape in ("gabled", "hipped") and not _rect_check(poly.outer):
        if _is_convex(poly.outer):
            prov["roof_shape"] = f"fallback:pyramidal (roof:shape={roof_shape} on non-rectangular footprint)"
            roof_shape = "pyramidal"
        else:
            prov["roof_shape"] = f"fallback:flat (roof:shape={roof_shape} on non-rectangular footprint)"
            roof_shape, roof_h = "flat", 0.0
    if roof_shape == "pyramidal" and not _is_convex(poly.outer):
        prov["roof_shape"] = "fallback:flat (pyramidal roof on concave footprint)"
        roof_shape, roof_h = "flat", 0.0

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

    elevated = min_h > 0
    base_z = min_h if elevated else -FOUNDATION_SINK_M
    wall_top_flat = top - roof_h

    def local(p):
        return (p[0] - cx, p[1] - cy)

    skillion_z = None
    if roof_shape == "skillion":
        direction = parse_number(tags.get("roof:direction"))
        if direction is None:
            prov["roof_direction"] = "inferred:0 (north-facing slope)"
            direction = 0.0
        d = (math.sin(math.radians(direction)), math.cos(math.radians(direction)))
        proj = [p[0] * d[0] + p[1] * d[1] for r in rings for p in r]
        smin, smax = min(proj), max(proj)
        span = max(smax - smin, 1e-6)

        def skillion_z(p):
            s = p[0] * d[0] + p[1] * d[1]
            return top - roof_h * (s - smin) / span

    mesh = MeshData(f"bld_{short_name(feature.id)}")
    pts2 = []
    ring_idx_bottom, ring_idx_top = [], []
    for r in rings:
        rb, rt = [], []
        for p in r:
            lx, ly = local(p)
            zt = skillion_z(p) if skillion_z else wall_top_flat
            rb.append(mesh.add_vertex(lx, ly, base_z))
            rt.append(mesh.add_vertex(lx, ly, zt))
            pts2.append((lx, ly))
        ring_idx_bottom.append(rb)
        ring_idx_top.append(rt)
    for rb, rt in zip(ring_idx_bottom, ring_idx_top):
        n = len(rb)
        for k in range(n):
            j = (k + 1) % n
            mesh.add_face((rb[k], rb[j], rt[j], rt[k]), "MB Facade", facade)

    # 2-D index mapping for triangulation: pts2 index == position in vertex order / 2
    offsets = []
    o = 0
    for r in rings:
        offsets.append(list(range(o, o + len(r))))
        o += len(r)
    tris = triangulate(pts2, offsets[0], offsets[1:])
    flat_top = [i for rt in ring_idx_top for i in rt]
    flat_bot = [i for rb in ring_idx_bottom for i in rb]
    for (a, b, c) in tris:
        mesh.add_face((flat_bot[a], flat_bot[c], flat_bot[b]), "MB Facade", facade)  # downward
    if roof_shape in ("flat", "skillion"):
        for (a, b, c) in tris:
            mesh.add_face((flat_top[a], flat_top[b], flat_top[c]), "MB Roof", roof_col)
    elif roof_shape == "pyramidal":
        apex = mesh.add_vertex(0.0, 0.0, top)
        rt = ring_idx_top[0]
        for k in range(len(rt)):
            mesh.add_face((rt[k], rt[(k + 1) % len(rt)], apex), "MB Roof", roof_col)
    else:  # gabled / hipped on rectangle a,b,c,d (CCW)
        rt = ring_idx_top[0]
        V = mesh.vertices
        a, b, c, d = rt
        if math.dist(V[a][:2], V[b][:2]) < math.dist(V[b][:2], V[c][:2]):
            a, b, c, d = b, c, d, a  # make a-b a long side
        m1 = tuple((V[b][i] + V[c][i]) / 2 for i in range(2))
        m2 = tuple((V[d][i] + V[a][i]) / 2 for i in range(2))
        if roof_shape == "hipped":
            short = math.dist(V[b][:2], V[c][:2])
            long_ = math.dist(m1, m2)
            t = min(0.5 * short / max(long_, 1e-6), 0.49)
            r1 = (m1[0] + (m2[0] - m1[0]) * t, m1[1] + (m2[1] - m1[1]) * t)
            r2 = (m2[0] + (m1[0] - m2[0]) * t, m2[1] + (m1[1] - m2[1]) * t)
        else:
            r1, r2 = m1, m2
        R1 = mesh.add_vertex(r1[0], r1[1], top)
        R2 = mesh.add_vertex(r2[0], r2[1], top)
        mesh.add_face((a, b, R1, R2), "MB Roof", roof_col)
        mesh.add_face((c, d, R2, R1), "MB Roof", roof_col)
        end_mat, end_col = ("MB Roof", roof_col) if roof_shape == "hipped" else ("MB Facade", facade)
        mesh.add_face((b, c, R1), end_mat, end_col)
        mesh.add_face((d, a, R2), end_mat, end_col)
    prov["roof_shape_built"] = roof_shape
    prov["height_m"] = round(height, 2)
    if elevated:
        prov["elevated"] = (f"volume starts {min_h:.1f} m above ground; the space beneath is NOT modelled "
                            "as traversable in v1")
    return mesh, origin, prov


# --- Terrain ----------------------------------------------------------------

class _Buckets:
    def __init__(self, items, cell=50.0):
        self.cell = cell
        self.map = {}
        for it, (x0, y0, x1, y1) in items:
            for i in range(int(math.floor(x0 / cell)), int(math.floor(x1 / cell)) + 1):
                for j in range(int(math.floor(y0 / cell)), int(math.floor(y1 / cell)) + 1):
                    self.map.setdefault((i, j), []).append(it)

    def query(self, x, y):
        return self.map.get((int(math.floor(x / self.cell)), int(math.floor(y / self.cell))), ())


LANDCOVER_PRIORITY = {"water": 4, "forest": 3, "sand": 2, "grass": 1}


def build_terrain(grid, z_offset, areas):
    mesh = MeshData("terrain")
    buckets = _Buckets([(a, a.geometry.bbox()) for a in areas])
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
                c = a.tags["_class"]
                if (cls is None or LANDCOVER_PRIORITY[c] > LANDCOVER_PRIORITY[cls]) and a.geometry.contains(cx, cy):
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


def _densify(pts, step):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        n = max(1, int(math.ceil(d / step)))
        for k in range(1, n + 1):
            out.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    dedup = [out[0]]
    for p in out[1:]:
        if math.dist(p, dedup[-1]) > 1e-3:
            dedup.append(p)
    return dedup


def build_road(feature, terrain, z_offset):
    width, wprov = road_width(feature.tags)
    pts = _densify(feature.geometry, ROAD_SEGMENT_M)
    if len(pts) < 2:
        return None, None, None
    half = width / 2.0
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    mesh = MeshData(f"road_{short_name(feature.id)}")
    color = (0.12, 0.12, 0.12) if feature.tags.get("highway") not in FOOT else (0.35, 0.32, 0.28)
    z0 = None
    left, right = [], []
    for k, p in enumerate(pts):
        if k == 0:
            dx, dy = pts[1][0] - p[0], pts[1][1] - p[1]
            nx_, ny_ = -dy, dx
            scale = 1.0
        elif k == len(pts) - 1:
            dx, dy = p[0] - pts[k - 1][0], p[1] - pts[k - 1][1]
            nx_, ny_ = -dy, dx
            scale = 1.0
        else:
            d1 = (p[0] - pts[k - 1][0], p[1] - pts[k - 1][1])
            d2 = (pts[k + 1][0] - p[0], pts[k + 1][1] - p[1])
            l1, l2 = math.hypot(*d1), math.hypot(*d2)
            n1 = (-d1[1] / l1, d1[0] / l1)
            n2 = (-d2[1] / l2, d2[0] / l2)
            nx_, ny_ = n1[0] + n2[0], n1[1] + n2[1]
            ln = math.hypot(nx_, ny_)
            if ln < 1e-6:
                nx_, ny_ = n1
                scale = 1.0
            else:
                nx_, ny_ = nx_ / ln, ny_ / ln
                cosang = nx_ * n1[0] + ny_ * n1[1]
                scale = min(1.0 / max(cosang, 1e-3), 2.0)
        ln = math.hypot(nx_, ny_) or 1.0
        nx_, ny_ = nx_ / ln * half * scale, ny_ / ln * half * scale
        lp = (p[0] + nx_, p[1] + ny_)
        rp = (p[0] - nx_, p[1] - ny_)
        zl = terrain.sample(*lp) - z_offset + ROAD_LIFT_M
        zr = terrain.sample(*rp) - z_offset + ROAD_LIFT_M
        zc = terrain.sample(*p) - z_offset + ROAD_LIFT_M
        zl, zr = max(zl, zc), max(zr, zc)
        if z0 is None:
            z0 = zc
        left.append(mesh.add_vertex(lp[0] - cx, lp[1] - cy, zl - z0))
        right.append(mesh.add_vertex(rp[0] - cx, rp[1] - cy, zr - z0))
    for k in range(len(pts) - 1):
        mesh.add_face((right[k], right[k + 1], left[k + 1]), "MB Road", color)
        mesh.add_face((right[k], left[k + 1], left[k]), "MB Road", color)
    return mesh, (cx, cy, z0), {"width": wprov, "width_m": round(width, 2),
                               "vertical": "draped on terrain (+0.12 m)"}


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


def scatter_points(feature, density, rng, limit):
    poly = feature.geometry
    x0, y0, x1, y1 = poly.bbox()
    step = math.sqrt(1.0 / density)
    pts = []
    y = y0 + step / 2
    while y < y1 and len(pts) < limit:
        x = x0 + step / 2
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
    def __init__(self, buildings=True, roads=True, trees=True, scatter=True, max_trees=2000, seed=0,
                 max_objects=20_000):
        self.buildings = buildings
        self.roads = roads
        self.trees = trees
        self.scatter = scatter
        self.max_trees = max_trees
        self.seed = seed
        self.max_objects = max_objects


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

    plan.objects.append(ObjectSpec("terrain", "terrain:grid", "terrain", "Terrain",
                                   mesh=build_terrain(terrain, z_offset, classified.areas),
                                   provenance={"elevation": terrain.provenance.get("provider"),
                                               "spacing_m": terrain.spacing}))
    footprints = []
    if opts.buildings:
        for f in classified.buildings:
            try:
                mesh, origin, prov = build_building(f, terrain, z_offset, opts.seed)
            except TriangulationError as e:
                plan.report["invalid_features"].append({"id": f.id, "reason": f"triangulation failed: {e}"})
                continue
            for k, v in prov.items():
                if isinstance(v, str) and v.startswith(("inferred", "fallback")):
                    plan.inferred(f"building.{k}")
            if "elevated" in prov:
                plan.report["unsupported_features"].append(
                    {"id": f.id, "reason": "elevated volume (min_height/building:min_level): generated as a "
                                           "closed solid; flying beneath it is not supported in v1",
                     "tags": {k: v for k, v in f.tags.items() if k in ("min_height", "building:min_level")}})
            plan.objects.append(ObjectSpec(mesh.name, f.id, "building", "Buildings", mesh=mesh, location=origin,
                                           provenance=prov))
            footprints.append((f.geometry, f.geometry.bbox()))
            if f.geometry.holes:
                plan.count("buildings_with_courtyards")
            plan.count("buildings")
    road_segments = []
    if opts.roads:
        for f in classified.roads:
            mesh, origin, prov = build_road(f, terrain, z_offset)
            if mesh is None:
                continue
            if prov["width"].startswith("inferred"):
                plan.inferred("road.width")
            plan.objects.append(ObjectSpec(mesh.name, f.id, "road", "Roads", mesh=mesh, location=origin,
                                           provenance=prov))
            w = prov["width_m"]
            for a, b in zip(f.geometry, f.geometry[1:]):
                road_segments.append((a, b, w / 2 + 1.0))
            plan.count("roads")
    if opts.trees:
        plan.shared_meshes["tree_generic"] = tree_mesh()
        fp_buckets = _Buckets(footprints)
        seg_buckets = _Buckets([((a, b, r), (min(a[0], b[0]) - r, min(a[1], b[1]) - r,
                                             max(a[0], b[0]) + r, max(a[1], b[1]) + r)) for a, b, r in road_segments],
                               cell=25.0)

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
        for f in classified.trees:
            if n_trees >= opts.max_trees:
                plan.report["warnings"].append(f"tree limit {opts.max_trees} reached; remaining trees skipped")
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
            plan.objects.append(ObjectSpec(f"tree_{short_name(f.id)}", f.id, "vegetation", "Vegetation",
                                           mesh_key="tree_generic",
                                           location=(x, y, terrain.sample(x, y) - z_offset),
                                           rotation_z=rng.random() * 2 * math.pi, scale=h / TREE_UNIT_HEIGHT,
                                           provenance=prov))
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
                for k, (x, y) in enumerate(scatter_points(f, dens, rng, remaining)):
                    if not area.contains(x, y) or blocked(x, y):
                        continue
                    s = 0.75 + rng.random() * 0.5
                    plan.objects.append(ObjectSpec(f"tree_s{stable_hash(f.id) % 1000000:06d}_{k}",
                                                   f"scatter:{f.id}#{k}", "vegetation", "Vegetation",
                                                   mesh_key="tree_generic",
                                                   location=(x, y, terrain.sample(x, y) - z_offset),
                                                   rotation_z=rng.random() * 2 * math.pi, scale=s,
                                                   provenance={"position": f"inferred:procedural scatter in {f.id} ({cls})",
                                                               "height": "inferred:procedural"}))
                    n_trees += 1
            if capped:
                plan.report["warnings"].append(f"tree limit {opts.max_trees} reached; scatter truncated")
        plan.count("trees", n_trees)
    if len(plan.objects) > opts.max_objects:
        from .errors import LimitError
        raise LimitError(f"{len(plan.objects)} objects exceed limit {opts.max_objects}")
    plan.report["counts"]["objects"] = len(plan.objects)
    plan.report["z_offset_m"] = z_offset
    # Ensure unique object names (Blender truncates at 63 bytes; keep ours shorter).
    seen = {}
    for o in plan.objects:
        base = o.name[:56]
        n = seen.get(base, 0)
        seen[base] = n + 1
        o.name = base if n == 0 else f"{base}.{n:03d}"
    return plan
