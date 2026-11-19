"""OpenStreetMap acquisition and feature classification.

Online via an Overpass API endpoint, or offline from a local ``.osm`` XML file
(for reproducibility). OSM data is (c) OpenStreetMap contributors, ODbL 1.0.
"""

import math
import xml.parsers.expat

from .errors import FormatError, LimitError

OSM_ATTRIBUTION = "(c) OpenStreetMap contributors, available under the Open Database License (ODbL) 1.0"
OSM_LICENSE = {
    "id": "ODbL-1.0",
    "name": "Open Database License 1.0",
    "url": "https://opendatacommons.org/licenses/odbl/1-0/",
    "copyright_url": "https://www.openstreetmap.org/copyright",
    "permits_offline_derivation": True,
    "permits_redistribution": True,
}
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_DATASET_ID = "openstreetmap-overpass-xml"
MAX_OSM_BYTES = 64 * 1024 * 1024
OSM_FETCH_MARGIN_M = 30.0   # normal Overpass fetch extent: the area plus this on each side
MAX_ELEMENTS = 2_000_000          # top-level node/way/relation/... elements
MAX_TOTAL_ELEMENTS = 20_000_000   # all XML elements, including <tag>/<nd>/<member>
MAX_DEPTH = 16
_PARSE_CHUNK = 1024 * 1024
_MAX_REMARK_CHARS = 1024


def overpass_query(s, w, n, e, timeout_s=90):
    """Overpass QL for everything :func:`classify` uses, so that an Overpass import and a local
    XML import of the same data classify alike.

    Simple 3D Buildings ``type=building`` relations usually carry no building tags, so they are
    selected explicitly: those in the bbox, and the parents of the selected building /
    building:part ways and relations (a relation whose own members fall outside the bbox still
    owns the parts inside it). Their member relations (building multipolygon outlines, part
    relations) are added, and the final ``>`` recursion brings in every member way and node.
    The query text is part of the cache key, so changing it never reuses stale cached data."""
    b = f"{s:.7f},{w:.7f},{n:.7f},{e:.7f}"
    return (
        f"[out:xml][timeout:{timeout_s}][maxsize:{MAX_OSM_BYTES}];\n(\n"
        f"  way[\"building\"]({b});\n  relation[\"building\"]({b});\n"
        f"  way[\"building:part\"]({b});\n  relation[\"building:part\"]({b});\n"
        f"  way[\"highway\"]({b});\n  way[\"railway\"]({b});\n"
        f"  way[\"landuse\"]({b});\n  relation[\"landuse\"]({b});\n"
        f"  way[\"natural\"]({b});\n  relation[\"natural\"]({b});\n"
        f"  way[\"leisure\"]({b});\n  relation[\"leisure\"]({b});\n"
        f"  way[\"waterway\"]({b});\n  way[\"man_made\"=\"bridge\"]({b});\n"
        f"  node[\"natural\"=\"tree\"]({b});\n"
        ")->.feat;\n(\n"
        f"  relation[\"type\"=\"building\"]({b});\n"
        "  rel(bw.feat)[\"type\"=\"building\"];\n  rel(br.feat)[\"type\"=\"building\"];\n"
        ")->.bldg;\n"
        "(.feat; .bldg; rel(r.bldg););\n(._;>;);\nout body qt;\n"
    )


def _validated_overpass(body, description):
    """Parse an Overpass response; any <remark> (timeout/size/runtime error) means partial data."""
    data = parse_osm_xml(body, description=description)
    if data.remarks:
        raise FormatError(f"{description}: Overpass returned an incomplete result (server remark such as "
                          "timeout or size limit); try a smaller area or later")
    return data


def fetch_overpass(area, client, url=DEFAULT_OVERPASS_URL, cache=None, allow_cache_override=False,
                   cache_dataset_id=None, margin_m=OSM_FETCH_MARGIN_M):
    """Fetches the area plus ``margin_m`` on each side (wider than :data:`OSM_FETCH_MARGIN_M` only for DSM
    mask candidates near the grid edge, see :func:`classify` ``content_bbox``; generated content is still
    selected against the area). ``cache`` is used only for the default public endpoint unless ``allow_cache_override`` is set
    by a caller that knows the alternative endpoint's terms permit caching. Caching an override also
    requires a caller-chosen, credential-free ``cache_dataset_id``: endpoint paths (which may embed
    credentials) never appear in cache keys, metadata, diagnostics or provenance."""
    import urllib.parse
    from .cache import check_cache_dataset_id
    from .http import redact
    is_default = isinstance(url, str) and url.strip().rstrip("/") == DEFAULT_OVERPASS_URL.rstrip("/")
    if is_default:
        endpoint = DEFAULT_OVERPASS_URL  # fixed public label
        cache_scope = DEFAULT_OVERPASS_URL
    else:
        endpoint = redact(url)  # origin only
        cache_scope = None
        if not allow_cache_override:
            cache = None
        elif cache is not None:
            if cache_dataset_id is None:
                raise ValueError("allow_cache_override requires an explicit, credential-free cache_dataset_id")
            cache_scope = "override:" + check_cache_dataset_id(cache_dataset_id, url)
    s, w, n, e = area.geographic_bbox(margin_m=margin_m)
    q = overpass_query(s, w, n, e)
    description = f"overpass:{endpoint}"
    key = f"{OSM_DATASET_ID}|{cache_scope}\n{q}"
    data = None
    if cache:
        body = cache.get("osm", key)
        if body is not None:
            try:
                data = _validated_overpass(body, description)
            except (FormatError, LimitError):
                data = None  # unusable cached entry: refetch and overwrite
    from_cache = data is not None
    if data is None:
        body = client.fetch(url, method="POST", data=urllib.parse.urlencode({"data": q}).encode("ascii"),
                            headers={"Content-Type": "application/x-www-form-urlencoded"}, max_bytes=MAX_OSM_BYTES)
        data = _validated_overpass(body, description)
        if cache:
            cache.put("osm", key, body, {"source": cache_scope, "dataset": OSM_DATASET_ID})
    data.source = {"provider": "overpass", "endpoint": endpoint, "from_cache": from_cache, "query": q}
    return data


class OsmData:
    def __init__(self):
        self.nodes = {}       # id -> (lat, lon, tags)
        self.ways = {}        # id -> (node ids, tags)
        self.relations = {}   # id -> (members [(type, ref, role)], tags)
        self.timestamp = None
        self.generator = None
        self.remarks = []     # <remark> texts anywhere in the document (Overpass partial-result signal)
        self.source = {}


def _reject_dtd(*_args):
    raise FormatError("DTD/entities are not allowed in OSM XML")


def parse_osm_xml(data, description="<osm>", max_elements=MAX_ELEMENTS, max_depth=MAX_DEPTH,
                  max_total_elements=MAX_TOTAL_ELEMENTS):
    """Streaming, bounded OSM XML parser (expat).

    DTDs and entity declarations are rejected by the parser itself (whatever the
    document encoding), and element count/depth limits are enforced while parsing.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    if len(data) > MAX_OSM_BYTES:
        raise LimitError(f"{description}: OSM data exceeds {MAX_OSM_BYTES} bytes")
    out = OsmData()
    state = {"depth": 0, "top": 0, "total": 0, "cur": None, "remark": None}

    def start(name, attrs):
        depth = state["depth"] = state["depth"] + 1
        if depth > max_depth:
            raise LimitError(f"{description}: OSM XML nesting deeper than {max_depth}")
        state["total"] += 1
        if state["total"] > max_total_elements:
            raise LimitError(f"{description}: more than {max_total_elements} XML elements")
        if depth == 1:
            if name != "osm":
                raise FormatError(f"{description}: not OSM XML (root <{name[:40]}>)")
            out.generator = attrs.get("generator")
        elif depth == 2:
            state["top"] += 1
            if state["top"] > max_elements:
                raise LimitError(f"{description}: more than {max_elements} OSM elements")
            if name in ("node", "way", "relation"):
                state["cur"] = (name, attrs, {}, [])
            elif name == "meta":
                out.timestamp = attrs.get("osm_base")
        elif depth == 3 and state["cur"] is not None:
            cur = state["cur"]
            if name == "tag":
                cur[2][attrs.get("k")] = attrs.get("v")
            elif name == "nd" and cur[0] == "way":
                cur[3].append(attrs.get("ref"))
            elif name == "member" and cur[0] == "relation":
                cur[3].append((attrs.get("type"), attrs.get("ref"), attrs.get("role") or ""))
        if name == "remark":
            out.remarks.append("")
            state["remark"] = depth

    def end(name):
        depth = state["depth"]
        state["depth"] = depth - 1
        if state["remark"] == depth and name == "remark":
            state["remark"] = None
        if depth == 2 and state["cur"] is not None and state["cur"][0] == name:
            _finish(out, state["cur"], description)
            state["cur"] = None

    def text(s):
        if state["remark"] is not None and len(out.remarks[-1]) < _MAX_REMARK_CHARS:
            out.remarks[-1] = (out.remarks[-1] + s)[:_MAX_REMARK_CHARS]

    p = xml.parsers.expat.ParserCreate()
    p.SetParamEntityParsing(xml.parsers.expat.XML_PARAM_ENTITY_PARSING_NEVER)
    p.StartDoctypeDeclHandler = _reject_dtd
    p.EntityDeclHandler = _reject_dtd
    p.UnparsedEntityDeclHandler = _reject_dtd
    p.NotationDeclHandler = _reject_dtd
    p.ExternalEntityRefHandler = _reject_dtd
    p.StartElementHandler = start
    p.EndElementHandler = end
    p.CharacterDataHandler = text
    try:
        for i in range(0, len(data), _PARSE_CHUNK):
            p.Parse(data[i:i + _PARSE_CHUNK], False)
        p.Parse(b"", True)
    except xml.parsers.expat.ExpatError as e:
        raise FormatError(f"{description}: invalid OSM XML: {xml.parsers.expat.ErrorString(e.code)} "
                          f"at line {e.lineno}") from None
    except ValueError:
        raise FormatError(f"{description}: unsupported OSM XML encoding (use UTF-8)") from None
    except FormatError as e:
        if str(e).startswith("DTD/"):
            raise FormatError(f"{description}: {e}") from None
        raise
    return out


def _finish(out, cur, description):
    kind, attrs, tags, items = cur
    try:
        if kind == "node":
            lat, lon = float(attrs.get("lat")), float(attrs.get("lon"))
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
            out.nodes[int(attrs.get("id"))] = (lat, lon, tags)
        elif kind == "way":
            out.ways[int(attrs.get("id"))] = ([int(r) for r in items], tags)
        else:
            out.relations[int(attrs.get("id"))] = ([(t, int(r), role) for t, r, role in items], tags)
    except (TypeError, ValueError):
        raise FormatError(f"{description}: malformed <{kind} id={str(attrs.get('id'))[:20]}>") from None


def load_osm_file(path):
    import hashlib
    import os
    size = os.path.getsize(path)
    if size > MAX_OSM_BYTES:
        raise LimitError(f"{path}: OSM file exceeds {MAX_OSM_BYTES} bytes")
    with open(path, "rb") as f:
        body = f.read()
    data = parse_osm_xml(body, description=os.path.basename(path))
    data.source = {"provider": "local-file", "file_name": os.path.basename(path),
                   "sha256": hashlib.sha256(body).hexdigest(), "file_generator": data.generator}
    return data


# --- geometry helpers --------------------------------------------------------

def ring_area(ring):
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _clean_ring(pts):
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > 1e-4 or abs(p[1] - out[-1][1]) > 1e-4:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= 1e-4 and abs(out[0][1] - out[-1][1]) <= 1e-4:
        out.pop()
    return out


def _segments_intersect(p1, p2, p3, p4):
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 * d2 < 0 and d3 * d4 < 0


def ring_self_intersects(ring):
    n = len(ring)
    if n > 3000:
        return False  # too expensive; triangulation will catch gross failures
    for i in range(n):
        a1, a2 = ring[i], ring[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _segments_intersect(a1, a2, ring[j], ring[(j + 1) % n]):
                return True
    return False


class Polygon:
    """One outer ring (CCW) with zero or more holes (CW), map-frame metres."""

    def __init__(self, outer, holes=()):
        self.outer = outer
        self.holes = list(holes)

    def area(self):
        return ring_area(self.outer) + sum(ring_area(h) for h in self.holes)

    def centroid(self):
        xs = [p[0] for p in self.outer]
        ys = [p[1] for p in self.outer]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    def bbox(self):
        xs = [p[0] for p in self.outer]
        ys = [p[1] for p in self.outer]
        return min(xs), min(ys), max(xs), max(ys)

    def contains(self, x, y):
        if not point_in_ring(x, y, self.outer):
            return False
        return not any(point_in_ring(x, y, h) for h in self.holes)


def _assemble_rings(way_lists):
    """Join open member ways into closed rings. Returns (rings, ok)."""
    segs = [list(w) for w in way_lists if len(w) >= 2]
    rings = []
    ok = True
    while segs:
        cur = segs.pop(0)
        guard = 0
        while cur[0] != cur[-1]:
            guard += 1
            if guard > 10000:
                ok = False
                break
            for k, s in enumerate(segs):
                if s[0] == cur[-1]:
                    cur.extend(s[1:])
                elif s[-1] == cur[-1]:
                    cur.extend(reversed(s[:-1]))
                elif s[-1] == cur[0]:
                    cur[:0] = s[:-1]
                elif s[0] == cur[0]:
                    cur[:0] = list(reversed(s[1:]))
                else:
                    continue
                segs.pop(k)
                break
            else:
                ok = False
                break
        if cur[0] == cur[-1] and len(cur) >= 4:
            rings.append(cur)
        else:
            ok = False
    return rings, ok


class Feature:
    def __init__(self, fid, kind, tags, geometry):
        self.id = fid          # e.g. "osm:way/123"
        self.kind = kind       # building | building_part | road | area | tree
        self.tags = tags
        self.geometry = geometry


class Classified:
    def __init__(self):
        self.buildings = []
        self.roads = []
        self.areas = []
        self.trees = []
        self.unsupported = []   # dicts {id, reason, tags subset}
        self.invalid = []       # dicts {id, reason}
        self.warnings = []      # strings, copied into the report's ``warnings``
        self.outside = 0
        self.replaced_outlines = []  # building outlines superseded by their building:part features
        # The superseded outlines are kept (not discarded) so generation can fall back to them
        # when their parts are rejected: outline id -> Feature, outline id -> [part ids] and
        # part id -> [outline id] (at most one: the declared outline of a ``type=building``
        # relation, else the smallest outline containing the part).
        self.outline_features = {}
        self.outline_parts = {}
        self.outline_for = {}
        # Footprint overlaps that are kept as mapped: dicts {part, outline, kind} for a
        # building:part whose footprint overlaps a building outline it neither belongs to nor lies
        # within. Classification cannot know whether the generated solids intersect (that depends
        # on terrain and on the roof actually built), so generation checks the emitted meshes'
        # map-frame Z extents and warns only then. Bounded by the part/outline pair limit.
        self.overlap_candidates = []
        # Not generated, kept for the DSM terrain correction mask (core/dsm.py). Selected against the mask
        # extent (the DEM grid extent; default the area) expanded by each feature's mask buffer, so that
        # features just outside the area still mask the edge samples: highway/railway ways tagged bridge=*
        # (other than "no"), clipped to the extent + dsm.BRIDGE_CANDIDATE_MARGIN_M (kind "bridge"; those in
        # the area are still reported in ``unsupported``), surface building footprints (surface_mask_eligible,
        # the predicate generation applies in the area) whose centroid lies outside the area (counted in
        # ``outside``) with a bbox within the extent + the building buffer, and
        # natural=tree nodes outside the area within the extent + the tree radius (``mask_trees``).
        # ``mask_areas``: forest/wood polygons that are in the input only because of the DSM fetch margin
        # (classify ``content_bbox``); never used for terrain colouring, scatter or any generated content.
        self.bridges = []
        self.outside_buildings = []
        self.mask_trees = []
        self.mask_areas = []


ROAD_EXCLUDE = {"proposed", "construction", "abandoned", "razed", "platform", "elevator", "corridor"}


MIN_HOLE_AREA_M2 = 0.01  # inner rings below this are degenerate: the feature is reported, never filled


def _unsupported_reason(tags):
    """Shared v1 support check, applied before a way/relation enters any road, building or area list."""
    if tags.get("bridge") and tags.get("bridge") != "no":
        return "bridge (under-bridge flight and elevated decks are not supported in v1; omitted)"
    mm = tags.get("man_made")
    if mm == "bridge":
        return "man_made=bridge (under-bridge flight and elevated decks are not supported in v1; omitted)"
    if mm == "tunnel":
        return "man_made=tunnel (tunnels/passages are not supported in v1; omitted)"
    for key in ("building", "building:part"):
        if tags.get(key) == "bridge":
            return f"{key}=bridge (bridge structures are not supported in v1; omitted)"
    t = tags.get("tunnel")
    if t and t != "no":
        return f"tunnel={t} (tunnels/passages are not supported in v1; omitted)"
    if tags.get("covered") == "yes":
        return "covered=yes (covered passage not supported in v1; omitted)"
    try:
        if int(tags.get("layer", "0")) < 0:
            return "layer<0 (below-ground feature not supported in v1; omitted)"
    except ValueError:
        pass
    if tags.get("location") in ("underground", "underwater"):
        return f"location={tags['location']} (not supported in v1; omitted)"
    return None


def surface_mask_eligible(tags):
    """True if a building footprint or forest polygon with ``tags`` is a surface feature that may enter the
    DSM terrain correction mask. It is the same predicate (:func:`_unsupported_reason`) that keeps a feature
    in the area out of generation (underground, ``layer<0``, tunnels, covered, bridges...), applied to the
    mask candidates on both sides of the area boundary, so a below-ground footprint never lowers terrain."""
    return _unsupported_reason(tags) is None


def _bbox_hit_test(data, content_bbox):
    """Predicate over lists of node-id lists: True if any listed node lies in ``content_bbox`` (south, west,
    north, east) or any segment between consecutive listed nodes crosses it (Overpass's bbox semantics for
    ways; a relation is selected by its member ways). Always True when ``content_bbox`` is None."""
    if content_bbox is None:
        return lambda node_lists: True
    s, w, n, e = content_bbox

    def hits(node_lists):
        for nids in node_lists:
            ll = [(data.nodes[x][1], data.nodes[x][0]) for x in nids if x in data.nodes]
            if any(w <= p[0] <= e and s <= p[1] <= n for p in ll):
                return True
            if any(_clip_segment(a, b, w, s, e, n) is not None for a, b in zip(ll, ll[1:])):
                return True
        return False
    return hits


def _content_ids(data, content_bbox):
    """(relation ids, way ids) of ``data`` that the normal-extent query (:func:`overpass_query` with
    ``content_bbox``) would also return, or None when ``content_bbox`` is None (everything is content).

    Mirrors the query: a relation is selected when one of its member ways (or nodes) touches the bbox, a
    ``type=building`` relation also when a member relation does, and the members of selected
    ``type=building`` relations are added (``rel(r.bldg)``); the downward recursion then brings in every
    member way of a selected relation, so such a way is content even if it lies outside the bbox."""
    if content_bbox is None:
        return None
    hits = _bbox_hit_test(data, content_bbox)
    way_hit = {}

    def way_hits(wid):
        if wid not in way_hit:
            w = data.ways.get(wid)
            way_hit[wid] = w is not None and hits([w[0]])
        return way_hit[wid]

    def direct(members):
        return any((t == "way" and way_hits(r)) or (t == "node" and r in data.nodes and hits([[r]]))
                   for t, r, _role in members)
    rels = {rid for rid, (members, _tags) in data.relations.items() if direct(members)}
    bldg = [rid for rid, (members, tags) in data.relations.items() if tags.get("type") == "building"
            and (rid in rels or any(t == "relation" and r in rels for t, r, _role in members))]
    rels.update(bldg)
    for rid in bldg:
        rels.update(r for t, r, _role in data.relations[rid][0] if t == "relation" and r in data.relations)
    ways = {wid for wid in data.ways if way_hits(wid)}
    for rid in rels:
        ways.update(r for t, r, _role in data.relations[rid][0] if t == "way")
    return rels, ways


def classify(data, area, max_features=50_000, max_part_pair_checks=None, max_association_work=None,
             mask_extent=None, content_bbox=None):
    """Classified features of ``data`` for ``area``. ``mask_extent`` (x0, y0, x1, y1 in the map frame,
    default the area rectangle) is the terrain grid extent used to select the DSM mask candidates
    (``bridges``, ``outside_buildings``, ``mask_trees``, ``mask_areas``); generated features are always
    selected against the area. Every kept feature, mask candidates included, counts toward ``max_features``.

    ``content_bbox`` (south, west, north, east), when ``data`` was fetched with a wider DSM margin than the
    normal acquisition extent, is that normal extent: features the normal-extent query would not return
    (:func:`_content_ids`) are in the input only because of the margin. Margin-only building footprints and
    forest/wood polygons become DSM mask candidates only (``outside_buildings``/``mask_areas``), never
    landcover colouring, scatter, report counts (``outside``, ``invalid``, ``unsupported``) or any generated
    content, so the generated scene does not depend on whether the correction widened the fetch. None (a
    local file, or no wider fetch): everything is content."""
    from .dsm import BRIDGE_CANDIDATE_MARGIN_M, BUILDING_BUFFER_M, TREE_RADIUS_M
    if mask_extent is None:
        mask_extent = (-area.half[0], -area.half[1], area.half[0], area.half[1])
    content_ids = _content_ids(data, content_bbox)
    in_content = {}  # polygon feature id -> in the normal-extent input
    bridge_rect = _expand(mask_extent, BRIDGE_CANDIDATE_MARGIN_M)
    building_rect = _expand(mask_extent, BUILDING_BUFFER_M)
    tree_rect = _expand(mask_extent, TREE_RADIUS_M)
    if max_part_pair_checks is None:
        max_part_pair_checks = MAX_PART_PAIR_CHECKS
    if max_association_work is None:
        max_association_work = MAX_ASSOCIATION_WORK
    frame = area.frame
    proj_cache = {}

    def proj(nid):
        p = proj_cache.get(nid)
        if p is None:
            nd = data.nodes.get(nid)
            if nd is None:
                return None
            p = frame.to_local(nd[0], nd[1])
            proj_cache[nid] = p
        return p

    def way_points(nids):
        pts = [proj(n) for n in nids]
        if any(p is None for p in pts):
            return None
        return pts

    out = Classified()
    used_as_member = set()
    polygons = {}  # feature id -> [Polygon]
    rel_outer_ways = {}  # area family -> way ids that are outers of an area relation with geometry
    suppressed_outers = {}  # way id -> (family or None for any, reason): outers of rejected multipolygons

    def make_polygons(fid, outers, inners):
        polys = []
        for o in outers:
            o = _clean_ring(o)
            if len(o) >= 3 and ring_self_intersects(o):
                out.invalid.append({"id": fid, "reason": "self-intersecting ring"})
                return []
            if len(o) < 3 or abs(ring_area(o)) < 0.5:
                out.invalid.append({"id": fid, "reason": "degenerate ring (fewer than 3 distinct points or "
                                                         "area < 0.5 m2)"})
                continue
            if ring_area(o) < 0:
                o.reverse()
            polys.append(Polygon(o))
        for h in inners:
            h = _clean_ring(h)
            if len(h) < 3 or abs(ring_area(h)) < MIN_HOLE_AREA_M2:
                # dropping the hole would emit the footprint solid: skip the whole feature instead
                out.invalid.append({"id": fid, "reason": f"degenerate inner ring (fewer than 3 distinct points or "
                                                         f"area < {MIN_HOLE_AREA_M2:g} m2); skipped rather than "
                                                         "filling the hole"})
                return []
            if ring_area(h) > 0:
                h.reverse()
            # nested rings (outer, inner, outer, inner): the hole belongs to the smallest enclosing outer
            owners = [p for p in polys if point_in_ring(h[0][0], h[0][1], p.outer)]
            if owners:
                min(owners, key=lambda p: abs(ring_area(p.outer))).holes.append(h)
            else:
                # dropping the hole would fill a courtyard: skip the whole feature instead
                out.invalid.append({"id": fid, "reason": "inner ring lies outside every outer ring; "
                                                         "skipped rather than filling the hole"})
                return []
        for p in polys:
            if ring_self_intersects(p.outer) or any(ring_self_intersects(h) for h in p.holes):
                out.invalid.append({"id": fid, "reason": "self-intersecting ring"})
                return []
        return polys

    # Declared ownership from type=building relations: part id -> {(relation id, outline id or None)}.
    # Every stored (part, outline) pair is checked geometrically later, so the total counts against
    # the same pair budget as spatial candidates (LimitError before anything is stored).
    declared = {}
    n_declared = 0
    # Relations (multipolygons)
    for rid, (members, tags) in data.relations.items():
        if tags.get("type") not in ("multipolygon", "building"):
            continue
        fid = f"osm:relation/{rid}"
        if tags.get("type") == "building":
            # Simple 3D Buildings relation: groups an outline (way or building multipolygon)
            # with its building:part ways/relations. Geometry comes from the members themselves.
            outl = sorted({f"osm:{t}/{r}" for t, r, role in members
                           if role == "outline" and t in ("way", "relation")})
            prts = sorted({f"osm:{t}/{r}" for t, r, role in members
                           if role == "part" and t in ("way", "relation")})
            n_declared += max(1, len(outl)) * len(prts)
            if n_declared > max_part_pair_checks:
                raise LimitError(f"{fid}: type=building relations declare more than {max_part_pair_checks} "
                                 "building:part/outline pairs; choose a smaller area")
            for p in prts:
                declared.setdefault(p, set()).update((fid, o) for o in (outl or [None]))
            continue
        outer_ways, inner_ways, outer_ids = [], [], []
        missing_outer = missing_inner = False
        for typ, ref, role in members:
            if typ != "way":
                continue
            used_as_member.add(ref)
            w = data.ways.get(ref)
            if w is None:
                if role == "inner":
                    missing_inner = True
                else:
                    missing_outer = True
                continue
            if role == "inner":
                inner_ways.append(w[0])
            else:
                outer_ways.append(w[0])
                outer_ids.append(ref)
        orings, ok1 = _assemble_rings(outer_ways)
        irings, ok2 = _assemble_rings(inner_ways)
        fam = _area_family(tags)
        has_inner = bool(inner_ways) or missing_inner
        polys = []
        if missing_inner or not ok2:
            # Emitting the outer without its hole would fill a courtyard: skip and report.
            out.invalid.append({"id": fid, "reason": "multipolygon has a missing or unclosed inner ring; "
                                                     "skipped rather than filling the hole"})
        elif (missing_outer or not ok1) and not orings:
            out.invalid.append({"id": fid, "reason": "multipolygon has missing or unclosed member ways"})
        else:
            if missing_outer or not ok1:
                out.invalid.append({"id": fid, "reason": "multipolygon has missing or unclosed member ways"})
            o_pts = [way_points(r) for r in orings]
            i_pts = [way_points(r) for r in irings]
            if any(p is None for p in o_pts + i_pts):
                out.invalid.append({"id": fid, "reason": "multipolygon references missing nodes"})
            else:
                polys = make_polygons(fid, o_pts, i_pts)
                polygons[fid] = (polys, tags)
                in_content[fid] = content_ids is None or rid in content_ids[0]
        if fam and polys:
            rel_outer_ways.setdefault(fam, set()).update(outer_ids)
        elif fam:
            # Rejected relation: a standalone solid copy of its outer would cover the courtyard.
            for wid in outer_ids:
                suppressed_outers.setdefault(wid, (fam, f"outer member of rejected multipolygon {fid}; "
                                                        "footprint not generated rather than filling its hole"))
        elif has_inner:
            # Old-style tagging (area tags on the outer way, untagged relation): the way alone has no holes.
            for wid in outer_ids:
                suppressed_outers.setdefault(wid, (None, f"outer member of multipolygon {fid} with inner rings "
                                                         "but no area tags on the relation (old-style tagging "
                                                         "unsupported); footprint not generated rather than "
                                                         "filling its hole"))

    for wid, (nids, tags) in data.ways.items():
        fid = f"osm:way/{wid}"
        closed = len(nids) >= 4 and nids[0] == nids[-1]
        is_area_tagged = any(k in tags for k in ("building", "building:part", "landuse", "leisure")) or (
            tags.get("natural") in ("water", "wood", "scrub", "grassland", "heath", "wetland", "beach", "sand",
                                    "bare_rock"))
        as_area = closed and is_area_tagged and tags.get("area") != "no"
        if as_area and wid in rel_outer_ways.get(_area_family(tags), ()):
            # Already represented (with its holes) by a multipolygon of the same class: a standalone
            # solid copy would fill the courtyard. Other roles of the way (e.g. highway) still apply.
            as_area = False
        elif as_area and wid in suppressed_outers:
            sfam, reason = suppressed_outers[wid]
            if sfam is None or sfam == _area_family(tags):
                # Never fill a courtyard; report instead of silently dropping. Other roles still apply.
                as_area = False
                out.invalid.append({"id": fid, "reason": reason})
        if as_area:
            pts = way_points(nids)
            if pts is None:
                out.invalid.append({"id": fid, "reason": "way references missing nodes"})
                continue
            polygons[fid] = (make_polygons(fid, [pts], []), tags)
            in_content[fid] = content_ids is None or wid in content_ids[1]
        elif "highway" in tags or "railway" in tags or "waterway" in tags:
            pts = way_points(nids)
            if pts is None:
                out.invalid.append({"id": fid, "reason": "way references missing nodes"})
                continue
            if ("highway" in tags or "railway" in tags) and tags.get("bridge") and tags.get("bridge") != "no":
                bparts = _clip_polyline(pts, area, bridge_rect)
                for k, part in enumerate(bparts):
                    out.bridges.append(Feature(fid if len(bparts) == 1 else f"{fid}#{k}", "bridge", tags, part))
            if "highway" not in tags:
                kind = "railway" if "railway" in tags else "waterway"
                if _clip_polyline(pts, area):
                    out.unsupported.append({"id": fid, "reason": f"{kind} lines are not generated in v1",
                                            "tags": _subset(tags)})
                continue
            parts = _clip_polyline(pts, area)
            if not parts:
                continue
            # Bridges/tunnels/building passages are reported before any generic exclusion so that
            # e.g. highway=corridor + tunnel=building_passage is never silently dropped.
            reason = _unsupported_reason(tags)
            if reason:
                out.unsupported.append({"id": fid, "reason": reason, "tags": _subset(tags)})
                continue
            if tags["highway"] in ROAD_EXCLUDE:
                continue
            for k, part in enumerate(parts):
                out.roads.append(Feature(fid if len(parts) == 1 else f"{fid}#{k}", "road", tags, part))
        elif tags.get("man_made") in ("bridge", "tunnel"):
            out.unsupported.append({"id": fid, "reason": f"man_made={tags['man_made']} outline "
                                                         "(not supported in v1)", "tags": _subset(tags)})

    for fid, (polys, tags) in polygons.items():
        if not polys:
            continue
        cx, cy = polys[0].centroid()
        content = in_content.get(fid, True)
        if "building" in tags or "building:part" in tags:
            if not content or not area.contains(cx, cy):
                # Not generated. Counted as outside the area only if it is in the normal input extent;
                # a DSM mask candidate only if it is a surface feature (the inside-area predicate below).
                if content:
                    out.outside += 1
                if surface_mask_eligible(tags) and any(_rect_overlaps(p.bbox(), building_rect) for p in polys):
                    out.outside_buildings.extend(Feature(fid, "building", tags, p) for p in polys)
                continue
            reason = _unsupported_reason(tags)
            if reason:
                out.unsupported.append({"id": fid, "reason": reason, "tags": _subset(tags)})
                continue
            kind = "building_part" if "building:part" in tags and "building" not in tags else "building"
            for k, p in enumerate(polys):
                out.buildings.append(Feature(fid if len(polys) == 1 else f"{fid}#{k}", kind, tags, p))
        else:
            cls = area_class(tags)
            if cls and not content:
                # only fetched for the DSM margin: a mask candidate (forest/wood) and nothing else
                if cls == "forest" and surface_mask_eligible(tags):
                    for k, p in enumerate(polys):
                        out.mask_areas.append(Feature(fid if len(polys) == 1 else f"{fid}#{k}", "area",
                                                      dict(tags, _class=cls), p))
            elif cls:
                reason = _unsupported_reason(tags)
                if reason:
                    if any(_bbox_overlaps(p.bbox(), area) for p in polys):
                        out.unsupported.append({"id": fid, "reason": reason, "tags": _subset(tags)})
                    continue
                for k, p in enumerate(polys):
                    out.areas.append(Feature(fid if len(polys) == 1 else f"{fid}#{k}", "area", dict(tags, _class=cls), p))
            elif (content and tags.get("man_made") in ("bridge", "tunnel")
                  and any(_bbox_overlaps(p.bbox(), area) for p in polys)):
                out.unsupported.append({"id": fid, "reason": _unsupported_reason(tags), "tags": _subset(tags)})

    for nid, (lat, lon, tags) in data.nodes.items():
        if tags.get("natural") == "tree":
            # a tree in the area always lies in content_bbox; one outside it is a mask candidate only
            x, y = frame.to_local(lat, lon)
            if area.contains(x, y):
                out.trees.append(Feature(f"osm:node/{nid}", "tree", tags, (x, y)))
            elif tree_rect[0] <= x <= tree_rect[2] and tree_rect[1] <= y <= tree_rect[3]:
                out.mask_trees.append(Feature(f"osm:node/{nid}", "tree", tags, (x, y)))

    if content_ids is not None:
        # problems of margin-only features are not reported: the normal-extent input does not contain them
        margin_only = ({f"osm:relation/{r}" for r in data.relations if r not in content_ids[0]}
                       | {f"osm:way/{w}" for w in data.ways if w not in content_ids[1]})
        out.invalid = [e for e in out.invalid if e.get("id") not in margin_only]
        out.unsupported = [e for e in out.unsupported if e.get("id") not in margin_only]
    # Enforced before building:part matching: replaced outlines are retained (outline_features)
    # and so count, exactly like the parts and the other buildings still in ``out.buildings``.
    total = (len(out.buildings) + len(out.roads) + len(out.areas) + len(out.trees) + len(out.bridges)
             + len(out.outside_buildings) + len(out.mask_trees) + len(out.mask_areas))
    if total > max_features:
        raise LimitError(f"{total} features exceed the limit of {max_features}; choose a smaller area")
    _resolve_building_parts(out, max_pair_checks=max_part_pair_checks, max_work=max_association_work,
                            declared=declared)
    return out


# --- building:part / outline association -------------------------------------

PART_TOL_M = 0.05            # boundaries closer than this count as coincident/touching
MAX_PART_PAIR_CHECKS = 200_000       # bbox-overlapping (part, outline) pairs examined geometrically
MAX_ASSOCIATION_WORK = 10_000_000    # primitive geometric tests for the whole association
_PART_GRID_M = 32.0
_PART_GRID_MAX_CELLS = 256   # per axis


class _AssocWork:
    def __init__(self, limit):
        self.limit = limit
        self.n = 0

    def add(self, k=1):
        self.n += k
        if self.n > self.limit:
            raise LimitError(f"building:part/outline association exceeds its work budget of {self.limit} "
                             "geometric tests; choose a smaller area")


def _seg_dist2(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    ex, ey = a[0] + t * dx - p[0], a[1] + t * dy - p[1]
    return ex * ex + ey * ey


def _locate(pt, poly, tol, work):
    """1 strictly inside ``poly`` (farther than ``tol`` from its boundary), 0 on its boundary, -1 outside."""
    rings = [poly.outer] + poly.holes
    work.add(2 * sum(len(r) for r in rings))
    t2 = tol * tol
    for r in rings:
        for i in range(len(r)):
            if _seg_dist2(pt, r[i - 1], r[i]) <= t2:
                return 0
    if not point_in_ring(pt[0], pt[1], poly.outer) or any(point_in_ring(pt[0], pt[1], h) for h in poly.holes):
        return -1
    return 1


def _contact_params(a, b, edges, tol, work):
    """Sorted parameters in [0, 1] splitting segment ab at every contact with ``edges`` (proper
    crossings, and the projections of edge vertices lying within ``tol`` of ab)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t2 = tol * tol
    ts = {0.0, 1.0}
    x0, x1 = min(a[0], b[0]) - tol, max(a[0], b[0]) + tol
    y0, y1 = min(a[1], b[1]) - tol, max(a[1], b[1]) + tol
    work.add(len(edges))
    for c, d in edges:
        if max(c[0], d[0]) < x0 or min(c[0], d[0]) > x1 or max(c[1], d[1]) < y0 or min(c[1], d[1]) > y1:
            continue
        for q in (c, d):
            t = ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / l2
            if 0.0 < t < 1.0:
                ex, ey = a[0] + t * dx - q[0], a[1] + t * dy - q[1]
                if ex * ex + ey * ey <= t2:
                    ts.add(t)
        ex, ey = d[0] - c[0], d[1] - c[1]
        den = dx * ey - dy * ex
        if den != 0:
            t = ((c[0] - a[0]) * ey - (c[1] - a[1]) * ex) / den
            u = ((c[0] - a[0]) * dy - (c[1] - a[1]) * dx) / den
            if 0.0 < t < 1.0 and 0.0 <= u <= 1.0:
                ts.add(t)
    return sorted(ts)


def _boundary_locations(rings, poly, tol, work):
    """Yield the location (see :func:`_locate`) w.r.t. ``poly`` of every vertex of ``rings`` and of the
    midpoint of every piece of their edges between consecutive contacts with ``poly``'s boundary.
    Each such piece lies entirely inside, on or outside ``poly``, so this decides where the whole
    boundary lies (a crossing or an exit through a vertex always yields a piece outside)."""
    edges = [(r[i - 1], r[i]) for r in [poly.outer] + poly.holes for i in range(len(r))]
    for ring in rings:
        n = len(ring)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            yield _locate(a, poly, tol, work)
            ts = _contact_params(a, b, edges, tol, work)
            for t0, t1 in zip(ts, ts[1:]):
                tm = (t0 + t1) / 2.0
                yield _locate((a[0] + tm * (b[0] - a[0]), a[1] + tm * (b[1] - a[1])), poly, tol, work)


def interior_point(rings):
    """A point strictly inside the region bounded by ``rings`` (even-odd rule; an outer ring and its
    holes), or None if degenerate. Unlike the vertex centroid it never falls in a notch or a hole:
    it is the middle of the widest interior span on the horizontal line halfway across the
    largest gap between distinct vertex heights (that line passes through no vertex)."""
    ys = sorted({p[1] for r in rings for p in r})
    if len(ys) < 2:
        return None
    k = max(range(len(ys) - 1), key=lambda i: ys[i + 1] - ys[i])
    y = (ys[k] + ys[k + 1]) / 2.0
    xs = []
    for r in rings:
        for i in range(len(r)):
            (ax, ay), (bx, by) = r[i - 1], r[i]
            if (ay > y) != (by > y):
                xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
    xs.sort()
    spans = [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]
    if not spans:
        return None
    x0, x1 = max(spans, key=lambda s: s[1] - s[0])
    return (x0 + x1) / 2.0, y


def part_within_outline(part, outline, tol=PART_TOL_M, work=None):
    """True if footprint ``part`` (a Polygon) lies within ``outline`` (a Polygon): its boundary
    (outer ring and holes) lies inside or on the outline - within the outer ring, outside every
    hole, coincident/touching boundaries allowed within ``tol`` - and no outline hole (courtyard)
    lies inside the part."""
    work = work or _AssocWork(MAX_ASSOCIATION_WORK)
    px0, py0, px1, py1 = part.bbox()
    ox0, oy0, ox1, oy1 = outline.bbox()
    if px0 < ox0 - tol or py0 < oy0 - tol or px1 > ox1 + tol or py1 > oy1 + tol:
        return False
    if any(s < 0 for s in _boundary_locations([part.outer] + part.holes, outline, tol, work)):
        return False
    # The boundary is within the outline, so each courtyard is either entirely inside or entirely
    # outside the part: one interior point of it decides.
    for h in outline.holes:
        q = interior_point([h])
        work.add(len(h))
        if q is not None and _locate(q, part, tol, work) > 0:
            return False
    return True


def footprints_overlap(a, b, tol=PART_TOL_M, work=None):
    """True if the interiors of Polygons ``a`` and ``b`` overlap by more than ``tol`` (touching or
    shared edges do not count)."""
    work = work or _AssocWork(MAX_ASSOCIATION_WORK)
    if any(s > 0 for s in _boundary_locations([a.outer] + a.holes, b, tol, work)):
        return True
    if any(s > 0 for s in _boundary_locations([b.outer] + b.holes, a, tol, work)):
        return True
    # Neither boundary enters the other's interior: overlap only if one lies inside the other.
    for x, y in ((a, b), (b, a)):
        q = interior_point([x.outer] + x.holes)
        work.add(len(x.outer))
        if q is not None and _locate(q, y, tol, work) > 0:
            return True
    return False


def _base_id(fid):
    """Feature id without the ``#k`` suffix given to the polygons of a multi-polygon feature."""
    return fid.split("#", 1)[0]


def _ids(ids, limit=10):
    """Up to ``limit`` ids joined for a message; O(limit) for lists and tuples (no full copy)."""
    if not isinstance(ids, (list, tuple)):
        ids = list(ids)
    return ", ".join(ids[:limit]) + (f", ... ({len(ids) - limit} more)" if len(ids) > limit else "")


def _resolve_building_parts(out, max_pair_checks=MAX_PART_PAIR_CHECKS, max_work=MAX_ASSOCIATION_WORK,
                            declared=None):
    """Simple 3D Buildings: an outline is replaced by the building:part features that belong to it.

    ``declared`` maps part ids to ``{(type=building relation id, outline id or None)}``.

    * Declared parts are validated against their declared outline(s) only, by footprint
      containment (:func:`part_within_outline`). A part within one of them belongs to it (the
      smallest if several); a part within none of them (crossing the boundary or lying in a
      courtyard) is rejected as invalid with a reason naming the declared outline(s), which are
      kept. If no declared outline is available as a building outline (member missing, outside
      the area, invalid or unsupported; or no outline member), the part is generated standalone
      and a warning says so: it is never matched spatially to an outline the relation does not name.
    * Undeclared parts are matched spatially: a part belongs to its *smallest* containing outline.
      A part lying in an outline's courtyard does not overlap it and is a standalone part.
    * A part (declared or not) whose footprint overlaps an outline it neither belongs to nor lies
      within is kept, never replaces that outline, and the outline is kept too. The pair is
      recorded in ``out.overlap_candidates`` (no warning here): generation warns if both are
      emitted and their meshes' map-frame Z extents overlap.

    A replaced outline leaves ``out.buildings`` but is kept in ``out.outline_features`` with the
    ids of its parts (``out.outline_parts`` / ``out.outline_for``, one outline per part), so the
    generator can fall back to it if none of those parts can be generated. Declared parts rejected
    here are listed under their (smallest) declared outline too and count as rejected; an outline
    all of whose parts were rejected here is simply kept.

    Work is bounded: candidate pairs (bbox grid plus declared pairs) are counted against
    ``max_pair_checks`` before any geometry; all geometric tests count against ``max_work``.
    Exceeding either raises :class:`LimitError`."""
    parts = [b for b in out.buildings if b.kind == "building_part"]
    outlines = [b for b in out.buildings if b.kind == "building"]
    if not parts:
        return
    declared = declared or {}
    tol = PART_TOL_M
    work = _AssocWork(max_work)
    by_base = {}
    for oi, o in enumerate(outlines):
        by_base.setdefault(_base_id(o.id), []).append(oi)
    # Per part: None (undeclared) or a declaration record shared by every component of the same
    # declared part, so multipolygon x multipolygon declarations are not expanded per component:
    # [declared outline indices (frozenset), outline ids, relation ids, smallest outline (lazy)].
    decl_of = []
    decl_cache = {}
    for part in parts:
        base = _base_id(part.id)
        d = declared.get(base)
        if d is None:
            decl_of.append(None)
            continue
        rec = decl_cache.get(base)
        if rec is None:
            oids = sorted({o for _, o in d if o is not None})
            ois = frozenset(oi for o in oids for oi in by_base.get(o, ()))
            work.add(len(ois) + 1)
            rec = decl_cache[base] = [ois, oids, sorted({r for r, _ in d}), None]
        decl_of.append(rec)
    candidates = [[] for _ in parts]
    n_pairs = 0
    if outlines:
        pboxes = [p.geometry.bbox() for p in parts]
        oboxes = [o.geometry.bbox() for o in outlines]
        gx0 = min(b[0] for b in pboxes) - tol
        gy0 = min(b[1] for b in pboxes) - tol
        gx1 = max(b[2] for b in pboxes) + tol
        gy1 = max(b[3] for b in pboxes) + tol
        cs = max(_PART_GRID_M, (gx1 - gx0) / _PART_GRID_MAX_CELLS, (gy1 - gy0) / _PART_GRID_MAX_CELLS)
        nmax = _PART_GRID_MAX_CELLS - 1

        def cell_range(bb):
            # Both parts and outlines are clamped to the parts' extent, which preserves overlaps.
            i0 = min(nmax, max(0, int((bb[0] - tol - gx0) // cs)))
            i1 = min(nmax, max(0, int((bb[2] + tol - gx0) // cs)))
            j0 = min(nmax, max(0, int((bb[1] - tol - gy0) // cs)))
            j1 = min(nmax, max(0, int((bb[3] + tol - gy0) // cs)))
            return i0, i1, j0, j1

        def overlap(a, b):
            return a[0] <= b[2] + tol and b[0] <= a[2] + tol and a[1] <= b[3] + tol and b[1] <= a[3] + tol

        grid = {}
        for oi, bb in enumerate(oboxes):
            if bb[2] < gx0 or bb[0] > gx1 or bb[3] < gy0 or bb[1] > gy1:
                continue  # cannot touch any part
            i0, i1, j0, j1 = cell_range(bb)
            work.add((i1 - i0 + 1) * (j1 - j0 + 1))
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    grid.setdefault((i, j), []).append(oi)
        # Phase 1: candidate pairs by bbox overlap, capped while enumerating, before any geometry.
        # Declared outlines are found through the same grid: one whose bbox does not overlap the
        # part cannot contain it, and phase 2 handles "declared but not within" from the record.
        for pi, bb in enumerate(pboxes):
            i0, i1, j0, j1 = cell_range(bb)
            seen = set()
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    cell = grid.get((i, j), ())
                    work.add(len(cell) + 1)
                    for oi in cell:
                        if oi not in seen and overlap(bb, oboxes[oi]):
                            seen.add(oi)
                            n_pairs += 1
                            if n_pairs > max_pair_checks:
                                raise LimitError(
                                    f"more than {max_pair_checks} overlapping building:part/outline pairs to "
                                    "check; choose a smaller area")
            candidates[pi] = sorted(seen)

    def size(oi):
        return abs(outlines[oi].geometry.area()), oi

    # Phase 2: declared validation / containment, then conflicts with other outlines.
    owner = {}       # part index -> outline index it belongs to (or is counted under, if rejected)
    rejected = set()
    for pi, part in enumerate(parts):
        g = part.geometry
        dec = decl_of[pi]
        within = set()
        if dec is not None:
            ois, oids, rels = dec[0], dec[1], dec[2]
            within = {oi for oi in candidates[pi]
                      if oi in ois and part_within_outline(g, outlines[oi].geometry, tol, work)}
            if within:
                owner[pi] = min(within, key=size)
                bases = {_base_id(outlines[oi].id) for oi in within}
                n_missed = len(oids) - len(bases)  # bases is a subset of oids
                if n_missed > 0:
                    shown = []
                    for o in oids:  # stops after at most len(bases) + 10 ids
                        work.add(1)
                        if o not in bases:
                            shown.append(o)
                            if len(shown) == 10:
                                break
                    more = f", ... ({n_missed - len(shown)} more)" if n_missed > len(shown) else ""
                    work.add(min(len(rels), 10))
                    out.warnings.append(
                        f"{part.id}: building:part is declared (building relation {_ids(rels)}) for outline(s) "
                        f"{', '.join(shown)}{more} too but does not lie within them; it belongs to "
                        f"{outlines[owner[pi]].id} only")
            elif ois:
                if dec[3] is None:
                    work.add(len(ois))
                    dec[3] = min(ois, key=size)
                owner[pi] = dec[3]
                rejected.add(pi)
                out.invalid.append({"id": part.id, "reason": (
                    f"building:part does not lie within its declared outline {_ids(oids)} (building relation "
                    f"{_ids(rels)}): it crosses the outline boundary or lies in a courtyard; part not "
                    "generated, outline kept")})
            else:
                what = f"outline {_ids(oids)} is" if oids else "relation has no outline member and"
                out.warnings.append(
                    f"{part.id}: building:part of building relation {_ids(rels)} whose declared {what} not "
                    "available as a building outline (missing, outside the area, invalid or unsupported); "
                    "the part is generated standalone and not matched to any other outline")
            exempt = ois
        else:
            within = {oi for oi in candidates[pi] if part_within_outline(g, outlines[oi].geometry, tol, work)}
            if within:
                owner[pi] = min(within, key=size)
            exempt = within
        if pi in rejected:
            continue
        for oi in candidates[pi]:
            if oi in exempt:
                continue
            o = outlines[oi]
            if dec is not None and part_within_outline(g, o.geometry, tol, work):
                continue  # nested inside an unrelated outline: no conflict
            if not footprints_overlap(g, o.geometry, tol, work):
                continue
            out.overlap_candidates.append({"part": part.id, "outline": o.id,
                                           "kind": "declared_part" if dec is not None else "part"})
    members = {}
    for pi in sorted(owner):
        members.setdefault(owner[pi], []).append(pi)
    replaced = {oi for oi, pis in members.items() if any(pi not in rejected for pi in pis)}
    rejected_ids = {parts[pi].id for pi in rejected}
    replaced_ids = set()
    for oi in sorted(replaced):
        o = outlines[oi]
        replaced_ids.add(id(o))
        out.replaced_outlines.append(o.id)
        out.outline_features[o.id] = o
        out.outline_parts[o.id] = [parts[pi].id for pi in members[oi]]
        for pi in members[oi]:
            out.outline_for[parts[pi].id] = [o.id]
    out.buildings = [b for b in out.buildings if id(b) not in replaced_ids
                     and not (b.kind == "building_part" and b.id in rejected_ids)]


def _area_family(tags):
    """Class used to decide whether a way and a multipolygon describe the same area feature."""
    if "building" in tags or "building:part" in tags:
        return "building"
    return area_class(tags)


def _bbox_overlaps(bbox, area):
    hx, hy = area.half
    return _rect_overlaps(bbox, (-hx, -hy, hx, hy))


def _rect_overlaps(bbox, rect):
    x0, y0, x1, y1 = bbox
    return x1 >= rect[0] and x0 <= rect[2] and y1 >= rect[1] and y0 <= rect[3]


def _expand(rect, margin):
    return rect[0] - margin, rect[1] - margin, rect[2] + margin, rect[3] + margin


def area_class(tags):
    if tags.get("natural") == "water" or tags.get("landuse") in ("reservoir", "basin") or "water" in tags:
        return "water"
    if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
        return "forest"
    if tags.get("leisure") in ("park", "garden") or tags.get("landuse") in (
            "grass", "meadow", "recreation_ground", "village_green", "cemetery") or tags.get("natural") in (
            "grassland", "scrub", "heath"):
        return "grass"
    if tags.get("natural") in ("sand", "beach", "bare_rock"):
        return "sand"
    return None


_KEEP_TAGS = ("highway", "bridge", "tunnel", "layer", "covered", "building", "building:part", "min_height",
              "building:min_level", "location", "railway", "waterway", "man_made")


def _subset(tags):
    return {k: v for k, v in tags.items() if k in _KEEP_TAGS}


def _clip_polyline(pts, area, rect=None):
    """Clip a polyline to the area rectangle (or ``rect`` = (x0, y0, x1, y1)); returns list of parts (>=2 pts)."""
    if rect is None:
        hx, hy = area.half
        rect = (-hx, -hy, hx, hy)
    parts = []
    cur = []
    for a, b in zip(pts, pts[1:]):
        seg = _clip_segment(a, b, *rect)
        if seg is None:
            if len(cur) >= 2:
                parts.append(cur)
            cur = []
            continue
        p, q = seg
        if cur and math.dist(cur[-1], p) < 1e-6:
            cur.append(q)
        else:
            if len(cur) >= 2:
                parts.append(cur)
            cur = [p, q]
    if len(cur) >= 2:
        parts.append(cur)
    return parts


def _clip_segment(a, b, x0, y0, x1, y1):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return (a[0] + t0 * dx, a[1] + t0 * dy), (a[0] + t1 * dx, a[1] + t1 * dy)
