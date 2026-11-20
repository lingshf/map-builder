"""Scene settings of the Map Builder panel.

Nothing here may hold a credential: these properties are saved into the .blend file. There is
deliberately no free-text endpoint field (an endpoint path or query can embed a token); a private
Overpass endpoint comes from the MAP_BUILDER_OVERPASS_URL environment variable at Generate time
(see sources.py). Every free-text/path property has an ``update`` callback that clears a credential-like
value (core credential policy) as soon as it is set, so it is not saved; the panel then shows which
field was cleared (never the value). Generate/Export re-check the values, which also catches values
written as raw custom properties (no update callback).
"""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from ..core.geodesy import DEFAULT_MAX_SIDE_M, MIN_SIDE_M
from .sources import ENV_OVERPASS_URL, FIELD_LABELS, has_credential, migrate_legacy_centre


def _is_map_collection(self, coll):
    return "mb_map" in coll


def _scrub(prop):
    """``update`` callback clearing a credential-like value of ``prop`` before it can be saved."""
    def update(self, context):
        label = FIELD_LABELS.get(prop, prop)
        if has_credential(getattr(self, prop)):
            setattr(self, prop, "")
            self.credential_notice = f"{label}: a credential-like value was cleared (it would be saved in the .blend)"
            print(f"Map Builder: {self.credential_notice}")
        elif getattr(self, prop) and self.credential_notice.startswith(f"{label}:"):
            self.credential_notice = ""
    return update


class MB_Settings(bpy.types.PropertyGroup):
    area_mode: EnumProperty(name="Area", items=[
        ("CENTER", "Centre + size", "WGS84 centre latitude/longitude and width/height in metres"),
        ("BBOX", "Bounding box", "South, west, north, east in WGS84 degrees"),
    ], default="CENTER")
    # the centre is text, not FloatProperty: Blender stores floats as float32 (centimetre error at 40 N), which
    # moves the area and changes terrain and probes against the CLI. ``lat``/``lon`` are the legacy float
    # properties of older .blend files: registered (so the saved value stays readable), hidden, migrated into
    # ``centre_lat``/``centre_lon`` on load and at Generate.
    centre_lat: StringProperty(name="Latitude", description="Area centre latitude (WGS84, degrees, full precision)",
                               default="")
    centre_lon: StringProperty(name="Longitude", description="Area centre longitude (WGS84, degrees, full precision)",
                               default="")
    lat: FloatProperty(name="Latitude (legacy)", default=0.0, min=-85.0, max=85.0, precision=6, options={"HIDDEN"})
    lon: FloatProperty(name="Longitude (legacy)", default=0.0, min=-180.0, max=180.0, precision=6,
                       options={"HIDDEN"})
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
    elevation_file: StringProperty(name="Elevation file", subtype="FILE_PATH", update=_scrub("elevation_file"))
    elevation_crs: StringProperty(name="CRS (.asc)", default="EPSG:4326", update=_scrub("elevation_crs"),
                                  description="CRS for ASCII grids (GeoTIFF CRS is read from the file)")
    elevation_vertical_datum: StringProperty(name="Vertical datum", default="",
                                             update=_scrub("elevation_vertical_datum"),
                                             description="Vertical datum of the local file (e.g. EGM2008)")
    elevation_license: StringProperty(name="Licence", default="", update=_scrub("elevation_license"),
                                      description="Licence/attribution of the local elevation file (required)")
    terrain_spacing: FloatProperty(name="Terrain spacing (m)", default=10.0, min=1.0, max=100.0)
    dsm_correction: EnumProperty(name="DSM correction", items=[
        ("AUTO", "Auto", "On for Copernicus GLO-30 (a surface model that includes buildings, trees and bridge "
                         "decks), off for a local elevation file"),
        ("ON", "On", "Lower the terrain under buildings, trees, forest and bridge decks toward the surrounding "
                     "ground (an approximation, not a bare-earth DTM)"),
        ("OFF", "Off", "Use the elevation as provided"),
    ], default="AUTO")

    osm_source: EnumProperty(name="Features", items=[
        ("overpass", "Overpass API (online)", "Download OpenStreetMap data (ODbL)"),
        ("file", "Local .osm file", "OSM XML file for reproducible builds"),
    ], default="overpass")
    osm_file: StringProperty(name="OSM file", subtype="FILE_PATH", update=_scrub("osm_file"))
    overpass_endpoint: EnumProperty(name="Endpoint", items=[
        ("default", "Public (overpass-api.de)", "The public Overpass API instance"),
        ("env", f"From ${ENV_OVERPASS_URL}", "Read the endpoint URL from this environment variable when "
                                             "generating; it is never saved in the .blend file"),
    ], default="default")
    cache_dir: StringProperty(name="Cache folder", subtype="DIR_PATH", update=_scrub("cache_dir"),
                              description="Optional download cache (public endpoints only, no credentials)")

    buildings: BoolProperty(name="Buildings", default=True)
    roads: BoolProperty(name="Roads", default=True)
    trees: BoolProperty(name="Trees", default=True)
    scatter: BoolProperty(name="Scatter vegetation", default=True,
                          description="Procedural (inferred) trees inside forests and parks")
    max_trees: IntProperty(name="Max trees", default=2000, min=0, max=20000)
    seed: IntProperty(name="Seed", default=1, min=0)

    package_name: StringProperty(name="Map name", default="my_map", update=_scrub("package_name"))
    export_collection: PointerProperty(name="Map collection", type=bpy.types.Collection, poll=_is_map_collection,
                                       description="Map collection to export (empty: the active or only map)")
    export_path: StringProperty(name="Package", subtype="FILE_PATH", default="//my_map.mbmap",
                                update=_scrub("export_path"))
    heightfield_spacing: FloatProperty(name="Heightfield spacing (m)", default=2.0, min=0.0, max=50.0,
                                       description="0 disables the derived terrain heightfield")
    credential_notice: StringProperty(name="Cleared field", default="",
                                      description="Which field had a credential-like value cleared (never "
                                                  "the value)")


@bpy.app.handlers.persistent
def _migrate_on_load(*_):
    for scene in bpy.data.scenes:
        migrate_legacy_centre(scene.map_builder)


def register():
    bpy.utils.register_class(MB_Settings)
    bpy.types.Scene.map_builder = PointerProperty(type=MB_Settings)
    if _migrate_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_migrate_on_load)


def unregister():
    if _migrate_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_migrate_on_load)
    del bpy.types.Scene.map_builder
    bpy.utils.unregister_class(MB_Settings)
