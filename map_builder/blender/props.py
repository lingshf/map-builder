"""Scene settings of the Map Builder panel.

Nothing here may hold a credential: these properties are saved into the .blend file. There is
deliberately no free-text endpoint field (an endpoint path or query can embed a token); a private
Overpass endpoint comes from the MAP_BUILDER_OVERPASS_URL environment variable at Generate time
(see sources.py).
"""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from ..core.geodesy import DEFAULT_MAX_SIDE_M, MIN_SIDE_M
from .sources import ENV_OVERPASS_URL


def _is_map_collection(self, coll):
    return "mb_map" in coll


class MB_Settings(bpy.types.PropertyGroup):
    area_mode: EnumProperty(name="Area", items=[
        ("CENTER", "Centre + size", "WGS84 centre latitude/longitude and width/height in metres"),
        ("BBOX", "Bounding box", "South, west, north, east in WGS84 degrees"),
    ], default="CENTER")
    lat: FloatProperty(name="Latitude", description="Area centre latitude (WGS84, degrees)", default=0.0,
                       min=-85.0, max=85.0, precision=6)
    lon: FloatProperty(name="Longitude", description="Area centre longitude (WGS84, degrees)", default=0.0,
                       min=-180.0, max=180.0, precision=6)
    width: FloatProperty(name="Width (m)", description="East-west extent in metres", default=1000.0,
                         min=MIN_SIDE_M, max=DEFAULT_MAX_SIDE_M)
    height: FloatProperty(name="Height (m)", description="North-south extent in metres", default=1000.0,
                          min=MIN_SIDE_M, max=DEFAULT_MAX_SIDE_M)
    bbox_south: FloatProperty(name="South", min=-85.0, max=85.0, precision=6)
    bbox_west: FloatProperty(name="West", min=-180.0, max=180.0, precision=6)
    bbox_north: FloatProperty(name="North", min=-85.0, max=85.0, precision=6)
    bbox_east: FloatProperty(name="East", min=-180.0, max=180.0, precision=6)

    elevation_source: EnumProperty(name="Elevation", items=[
        ("copernicus", "Copernicus GLO-30 (online)", "Copernicus DEM GLO-30 from AWS Open Data; public, no account"),
        ("file", "Local file", "GeoTIFF (.tif) or ESRI ASCII grid (.asc) in EPSG:4326 or WGS84 UTM"),
    ], default="copernicus")
    elevation_file: StringProperty(name="Elevation file", subtype="FILE_PATH")
    elevation_crs: StringProperty(name="CRS (.asc)", default="EPSG:4326",
                                  description="CRS for ASCII grids (GeoTIFF CRS is read from the file)")
    elevation_vertical_datum: StringProperty(name="Vertical datum", default="",
                                             description="Vertical datum of the local file (e.g. EGM2008)")
    elevation_license: StringProperty(name="Licence", default="",
                                      description="Licence/attribution of the local elevation file (required)")
    terrain_spacing: FloatProperty(name="Terrain spacing (m)", default=10.0, min=1.0, max=100.0)

    osm_source: EnumProperty(name="Features", items=[
        ("overpass", "Overpass API (online)", "Download OpenStreetMap data (ODbL)"),
        ("file", "Local .osm file", "OSM XML file for reproducible builds"),
    ], default="overpass")
    osm_file: StringProperty(name="OSM file", subtype="FILE_PATH")
    overpass_endpoint: EnumProperty(name="Endpoint", items=[
        ("default", "Public (overpass-api.de)", "The public Overpass API instance"),
        ("env", f"From ${ENV_OVERPASS_URL}", "Read the endpoint URL from this environment variable when "
                                             "generating; it is never saved in the .blend file"),
    ], default="default")
    cache_dir: StringProperty(name="Cache folder", subtype="DIR_PATH",
                              description="Optional download cache (public endpoints only, no credentials)")

    buildings: BoolProperty(name="Buildings", default=True)
    roads: BoolProperty(name="Roads", default=True)
    trees: BoolProperty(name="Trees", default=True)
    scatter: BoolProperty(name="Scatter vegetation", default=True,
                          description="Procedural (inferred) trees inside forests and parks")
    max_trees: IntProperty(name="Max trees", default=2000, min=0, max=20000)
    seed: IntProperty(name="Seed", default=0, min=0)

    package_name: StringProperty(name="Map name", default="my_map")
    export_collection: PointerProperty(name="Map collection", type=bpy.types.Collection, poll=_is_map_collection,
                                       description="Map collection to export (empty: the active or only map)")
    export_path: StringProperty(name="Package", subtype="FILE_PATH", default="//my_map.mbmap")
    heightfield_spacing: FloatProperty(name="Heightfield spacing (m)", default=2.0, min=0.0, max=50.0,
                                       description="0 disables the derived terrain heightfield")


def register():
    bpy.utils.register_class(MB_Settings)
    bpy.types.Scene.map_builder = PointerProperty(type=MB_Settings)


def unregister():
    del bpy.types.Scene.map_builder
    bpy.utils.unregister_class(MB_Settings)
