"""SYNTHETIC test data generator.

Everything produced here is invented geometry placed at an arbitrary
coordinate; it is NOT real OpenStreetMap or elevation data and carries no
third-party licence. It exists so tests and samples are reproducible offline.
"""

import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from map_builder.core.geodesy import LocalFrame  # noqa: E402

ORIGIN = (47.0, 8.0)
AREA_W, AREA_H = 400.0, 300.0


def dem_height(x, y):
    """Synthetic terrain: tilted plane + asymmetric bump (metres above datum)."""
    return 400.0 + 0.05 * x + 0.02 * y + 6.0 * math.exp(-((x - 80) ** 2 + (y + 40) ** 2) / 4000.0)


def write_dem_asc(path, frame=None, cell_deg=0.0001, margin_m=150.0):
    frame = frame or LocalFrame(*ORIGIN)
    s, w = frame.to_geographic(-AREA_W / 2 - margin_m, -AREA_H / 2 - margin_m)
    n, e = frame.to_geographic(AREA_W / 2 + margin_m, AREA_H / 2 + margin_m)
    ncols = int(math.ceil((e - w) / cell_deg)) + 1
    nrows = int(math.ceil((n - s) / cell_deg)) + 1
    lines = [f"ncols {ncols}", f"nrows {nrows}", f"xllcenter {w:.7f}", f"yllcenter {s:.7f}",
             f"cellsize {cell_deg}", "NODATA_value -9999"]
    for r in range(nrows):
        lat = s + (nrows - 1 - r) * cell_deg
        row = []
        for c in range(ncols):
            lon = w + c * cell_deg
            x, y = frame.to_local(lat, lon)
            row.append(f"{dem_height(x, y):.3f}")
        lines.append(" ".join(row))
    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(lines) + "\n")
    return path


class OsmBuilder:
    def __init__(self, frame=None):
        self.frame = frame or LocalFrame(*ORIGIN)
        self.nodes = []
        self.ways = []
        self.relations = []
        self._id = 1000

    def _next(self):
        self._id += 1
        return self._id

    def node(self, x, y, tags=None):
        nid = self._next()
        lat, lon = self.frame.to_geographic(x, y)
        self.nodes.append((nid, lat, lon, tags or {}))
        return nid

    def way(self, pts, tags=None, closed=False):
        ids = [self.node(x, y) for x, y in pts]
        if closed:
            ids.append(ids[0])
        wid = self._next()
        self.ways.append((wid, ids, tags or {}))
        return wid

    def multipolygon(self, outer, inners, tags, outer_tags=None):
        o = self.way(outer, outer_tags, closed=True)
        ins = [self.way(i, closed=True) for i in inners]
        rid = self._next()
        self.relations.append((rid, [("way", o, "outer")] + [("way", i, "inner") for i in ins],
                               dict(tags, type="multipolygon")))
        return rid

    def xml(self):
        from xml.sax.saxutils import quoteattr
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<osm version="0.6" generator="map-builder SYNTHETIC test fixture">',
               '<meta osm_base="2026-01-01T00:00:00Z"/>']

        def tags(t):
            return "".join(f"<tag k={quoteattr(k)} v={quoteattr(v)}/>" for k, v in t.items())
        for nid, lat, lon, t in self.nodes:
            out.append(f'<node id="{nid}" lat="{lat:.9f}" lon="{lon:.9f}">{tags(t)}</node>')
        for wid, ids, t in self.ways:
            out.append(f'<way id="{wid}">' + "".join(f'<nd ref="{i}"/>' for i in ids) + tags(t) + "</way>")
        for rid, members, t in self.relations:
            out.append(f'<relation id="{rid}">' + "".join(
                f'<member type="{ty}" ref="{ref}" role="{role}"/>' for ty, ref, role in members) + tags(t)
                + "</relation>")
        out.append("</osm>")
        return "\n".join(out)


def rect(cx, cy, w, h, angle_deg=0.0):
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + c * dx - s * dy, cy + s * dx + c * dy))
    return pts


def build_synthetic_osm(frame=None):
    b = OsmBuilder(frame)
    ids = {}
    # Asymmetric L-shaped building, measured height 12 m (orientation check object).
    ids["L"] = b.way([(50, 20), (90, 20), (90, 35), (65, 35), (65, 80), (50, 80)],
                     {"building": "yes", "height": "12"}, closed=True)
    # Courtyard building via multipolygon (outer 40x40, inner 16x16), 4 levels.
    ids["court"] = b.multipolygon(rect(-100, -60, 40, 40), [rect(-100, -60, 16, 16)[::-1]],
                                  {"building": "apartments", "building:levels": "4"})
    ids["gabled"] = b.way(rect(-50, 80, 10, 16, 20), {"building": "house", "roof:shape": "gabled",
                                                      "height": "8", "roof:height": "3"}, closed=True)
    ids["hipped"] = b.way(rect(-20, 80, 12, 18), {"building": "house", "roof:shape": "hipped"}, closed=True)
    ids["pyramid"] = b.way(rect(10, 80, 10, 10), {"building": "yes", "roof:shape": "pyramidal",
                                                  "building:levels": "2"}, closed=True)
    ids["skillion"] = b.way(rect(140, 80, 12, 8), {"building": "shed", "roof:shape": "skillion",
                                                   "roof:direction": "90", "height": "5", "roof:height": "1.5"},
                            closed=True)
    ids["dome"] = b.way(rect(140, -80, 14, 14), {"building": "yes", "roof:shape": "dome", "height": "10"},
                        closed=True)
    ids["elevated"] = b.way(rect(150, 20, 10, 10), {"building:part": "yes", "min_height": "6", "height": "12"},
                            closed=True)
    ids["bowtie"] = b.way([(-150, 100), (-130, 120), (-130, 100), (-150, 120)], {"building": "yes"}, closed=True)
    ids["outside"] = b.way(rect(400, 400, 10, 10), {"building": "yes"}, closed=True)
    ids["primary"] = b.way([(-260, -10), (0, -5), (260, 0)], {"highway": "primary", "lanes": "2"})
    ids["residential"] = b.way([(20, -170), (20, -20), (25, 160)], {"highway": "residential", "width": "6"})
    ids["bridge"] = b.way([(-80, 120), (-60, 130)], {"highway": "footway", "bridge": "yes", "layer": "1"})
    ids["tunnel"] = b.way([(-80, -120), (-40, -120)], {"highway": "service", "tunnel": "yes", "layer": "-1"})
    ids["forest"] = b.way([(100, -140), (190, -140), (190, -100), (100, -100)], {"landuse": "forest"}, closed=True)
    ids["park"] = b.way([(-190, 20), (-130, 20), (-130, 60), (-190, 60)], {"leisure": "park"}, closed=True)
    ids["water"] = b.way([(-60, -140), (-20, -140), (-20, -110), (-60, -110)], {"natural": "water"}, closed=True)
    for k, (x, y) in enumerate(((0, 40), (120, 40), (-160, -120))):
        ids[f"tree{k}"] = b.node(x, y, {"natural": "tree", "height": "11"} if k == 0 else {"natural": "tree"})
    return b, ids


def write_synthetic_fixtures(directory):
    os.makedirs(directory, exist_ok=True)
    b, ids = build_synthetic_osm()
    osm = os.path.join(directory, "synthetic_area.osm")
    with open(osm, "w", encoding="utf-8") as f:
        f.write(b.xml())
    dem = write_dem_asc(os.path.join(directory, "synthetic_dem.asc"))
    return osm, dem, ids


def synthetic_inputs(directory, spacing=10.0):
    """Returns (area, grid, classified, ids, sources) built from the SYNTHETIC fixtures."""
    from map_builder.core.geodesy import Area
    from map_builder.core.pipeline import Settings, acquire
    osm, dem, ids = write_synthetic_fixtures(directory)
    area = Area(*ORIGIN, AREA_W, AREA_H)
    settings = Settings(elevation_source="file", elevation_file=dem, elevation_vertical_datum="SYNTHETIC",
                        elevation_license="SYNTHETIC test data (no licence required)", osm_source="file",
                        osm_file=osm, terrain_spacing=spacing)
    grid, classified, sources = acquire(area, settings)
    return area, grid, classified, ids, sources


if __name__ == "__main__":
    print(write_synthetic_fixtures(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__),
                                                                                      "fixtures")))
