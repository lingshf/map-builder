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
MAX_ELEMENTS = 2_000_000          # top-level node/way/relation/... elements
MAX_TOTAL_ELEMENTS = 20_000_000   # all XML elements, including <tag>/<nd>/<member>
MAX_DEPTH = 16
_PARSE_CHUNK = 1024 * 1024
_MAX_REMARK_CHARS = 1024


def overpass_query(s, w, n, e, timeout_s=90):
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
        ");\n(._;>;);\nout body qt;\n"
    )


def _validated_overpass(body, description):
    """Parse an Overpass response; any <remark> (timeout/size/runtime error) means partial data."""
    data = parse_osm_xml(body, description=description)
    if data.remarks:
        raise FormatError(f"{description}: Overpass returned an incomplete result (server remark such as "
                          "timeout or size limit); try a smaller area or later")
    return data


def fetch_overpass(area, client, url=DEFAULT_OVERPASS_URL, cache=None, allow_cache_override=False,
                   cache_dataset_id=None):
    """``cache`` is used only for the default public endpoint unless ``allow_cache_override`` is set
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
    s, w, n, e = area.geographic_bbox(margin_m=30.0)
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
        self.outside = 0
        self.replaced_outlines = []  # building outlines superseded by their building:part features


ROAD_EXCLUDE = {"proposed", "construction", "abandoned", "razed", "platform", "elevator", "corridor"}


def _unsupported_reason(tags):
    if tags.get("bridge") and tags.get("bridge") != "no":
        return "bridge (under-bridge flight and elevated decks are not supported in v1; omitted)"
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


def classify(data, area, max_features=50_000):
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
            if len(h) < 3 or abs(ring_area(h)) < 0.05:
                continue
            if ring_area(h) > 0:
                h.reverse()
            for p in polys:
                if p.contains(*h[0]) or point_in_ring(h[0][0], h[0][1], p.outer):
                    p.holes.append(h)
                    break
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

    # Relations (multipolygons)
    for rid, (members, tags) in data.relations.items():
        if tags.get("type") not in ("multipolygon", "building"):
            continue
        fid = f"osm:relation/{rid}"
        if tags.get("type") == "building":
            continue  # building relations group parts; parts are handled as ways
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
        elif "highway" in tags or "railway" in tags or "waterway" in tags:
            pts = way_points(nids)
            if pts is None:
                out.invalid.append({"id": fid, "reason": "way references missing nodes"})
                continue
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
        elif tags.get("man_made") == "bridge":
            out.unsupported.append({"id": fid, "reason": "man_made=bridge outline (bridges not supported in v1)",
                                    "tags": _subset(tags)})

    for fid, (polys, tags) in polygons.items():
        if not polys:
            continue
        cx, cy = polys[0].centroid()
        if "building" in tags or "building:part" in tags:
            if not area.contains(cx, cy):
                out.outside += 1
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
            if cls:
                reason = _unsupported_reason(tags)
                if reason:
                    if any(_bbox_overlaps(p.bbox(), area) for p in polys):
                        out.unsupported.append({"id": fid, "reason": reason, "tags": _subset(tags)})
                    continue
                for k, p in enumerate(polys):
                    out.areas.append(Feature(fid if len(polys) == 1 else f"{fid}#{k}", "area", dict(tags, _class=cls), p))

    for nid, (lat, lon, tags) in data.nodes.items():
        if tags.get("natural") == "tree":
            x, y = frame.to_local(lat, lon)
            if area.contains(x, y):
                out.trees.append(Feature(f"osm:node/{nid}", "tree", tags, (x, y)))

    _resolve_building_parts(out)
    total = len(out.buildings) + len(out.roads) + len(out.areas) + len(out.trees)
    if total > max_features:
        raise LimitError(f"{total} features exceed the limit of {max_features}; choose a smaller area")
    return out


def _resolve_building_parts(out):
    """Simple 3D Buildings: an outline that contains parts is replaced by its parts."""
    parts = [b for b in out.buildings if b.kind == "building_part"]
    if not parts:
        return
    keep = []
    for b in out.buildings:
        if b.kind == "building":
            x0, y0, x1, y1 = b.geometry.bbox()
            has_part = False
            for p in parts:
                cx, cy = p.geometry.centroid()
                if x0 <= cx <= x1 and y0 <= cy <= y1 and b.geometry.contains(cx, cy):
                    has_part = True
                    break
            if has_part:
                out.replaced_outlines.append(b.id)
                continue
        keep.append(b)
    out.buildings = keep


def _area_family(tags):
    """Class used to decide whether a way and a multipolygon describe the same area feature."""
    if "building" in tags or "building:part" in tags:
        return "building"
    return area_class(tags)


def _bbox_overlaps(bbox, area):
    hx, hy = area.half
    x0, y0, x1, y1 = bbox
    return x1 >= -hx and x0 <= hx and y1 >= -hy and y0 <= hy


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


def _clip_polyline(pts, area):
    """Clip a polyline to the area rectangle; returns list of parts (>=2 pts)."""
    hx, hy = area.half
    parts = []
    cur = []
    for a, b in zip(pts, pts[1:]):
        seg = _clip_segment(a, b, -hx, -hy, hx, hy)
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
