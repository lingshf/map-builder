"""Headless map-builder CLI (no Blender): build a package from local files, or validate a package.

  py -3.12 tools/mbmap_cli.py validate examples/synthetic_sample.mbmap
  py -3.12 tools/mbmap_cli.py build --osm area.osm --dem dem.tif --dem-crs EPSG:32632 \
      --datum EGM2008 --dem-license "..." --lat 47.0 --lon 8.0 --width 400 --height 300 --out out.mbmap

``build`` uses the same core pipeline as the Blender add-on but exports the *generated* plan, not a
user-edited Blender scene. Use the add-on for edited maps.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from map_builder.core.errors import MapBuilderError  # noqa: E402
from map_builder.core.geodesy import Area  # noqa: E402
from map_builder.core.generate import PlanOptions  # noqa: E402
from map_builder.core.package import is_utc_timestamp, validate_package  # noqa: E402
from map_builder.core.pipeline import Settings, build_package  # noqa: E402

_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate a .mbmap package")
    v.add_argument("package")
    b = sub.add_parser("build", help="build a package from a local OSM file and a local elevation file")
    b.add_argument("--osm", required=True)
    b.add_argument("--dem", required=True, help="GeoTIFF or ESRI ASCII grid")
    b.add_argument("--dem-crs", default="EPSG:4326", help="CRS of an .asc grid (GeoTIFFs carry their own)")
    b.add_argument("--datum", required=True, help="vertical datum of the elevation values, e.g. EGM2008")
    b.add_argument("--dem-license", required=True, help="licence/attribution of the elevation data")
    b.add_argument("--osm-license", default=None,
                   help="only if the --osm file is NOT OpenStreetMap data (e.g. a synthetic fixture): its "
                        "licence/attribution statement; by default the file is credited as OpenStreetMap (ODbL)")
    b.add_argument("--lat", type=float, required=True)
    b.add_argument("--lon", type=float, required=True)
    b.add_argument("--width", type=float, default=1000)
    b.add_argument("--height", type=float, default=1000)
    b.add_argument("--spacing", type=float, default=10.0, help="terrain grid spacing in metres")
    b.add_argument("--heightfield", type=float, default=2.0, help="heightfield spacing (0 = none)")
    b.add_argument("--seed", type=int, default=1)
    b.add_argument("--dsm-correction", action=argparse.BooleanOptionalAction, default=None,
                   help="DSM terrain correction: lower the terrain under buildings, trees, forest and bridge decks "
                        "toward the surrounding ground (default: auto = off for a local elevation file, which "
                        "--dsm-correction opts in; use it for surface models such as Copernicus GLO-30)")
    b.add_argument("--name", default="map")
    b.add_argument("--created-utc", default=None, metavar="YYYY-MM-DDTHH:MM:SSZ",
                   help="fixed manifest created_utc (default: now); with the same inputs the package is "
                        "byte-identical, including package_id")
    b.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build" and a.created_utc is not None and not (_UTC.fullmatch(a.created_utc)
                                                                and is_utc_timestamp(a.created_utc)):
        ap.error("--created-utc must be an ISO-8601 UTC timestamp like 2026-01-01T00:00:00Z")
    try:
        if a.cmd == "validate":
            r = validate_package(a.package)
        else:
            area = Area(a.lat, a.lon, a.width, a.height)
            s = Settings(elevation_source="file", elevation_file=a.dem, elevation_crs=a.dem_crs,
                         elevation_vertical_datum=a.datum, elevation_license=a.dem_license, osm_source="file",
                         osm_file=a.osm, osm_license=a.osm_license, terrain_spacing=a.spacing,
                         heightfield_spacing=a.heightfield or None, dsm_correction=a.dsm_correction,
                         plan_options=PlanOptions(seed=a.seed))
            m, r = build_package(area, s, a.out, a.name,
                                 progress=lambda frac: print(f"terrain {frac:.0%}", file=sys.stderr, end="\r"),
                                 created_utc=a.created_utc)
            print(f"wrote {a.out}  package_id={r.package_id}  objects={len(m['objects'])}  "
                  f"probes={len(m['orientation_probes'])}")
    except (MapBuilderError, OSError, ValueError) as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(r.summary())
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
