# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""Scene settings of the Map Builder panel.

Nothing here may hold a credential: these properties are saved into the .blend file. There is
deliberately no free-text endpoint field (an endpoint path or query can embed a token); a private
Overpass endpoint comes from the MAP_BUILDER_OVERPASS_URL environment variable at Generate time
(see sources.py). Every free-text/path property has an ``update`` callback that clears a credential-like
value (core credential policy) as soon as it is set, so it is not saved; the panel then shows which
field was cleared (never the value). Generate/Export re-check the values, which also catches values
written as raw custom properties (no update callback).
"""

# No ``from __future__ import annotations`` here: Blender evaluates the class annotations below to find the properties.
# mypy: disable-error-code="valid-type"
from collections.abc import Callable
from typing import TYPE_CHECKING

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from ..core.geodesy import DEFAULT_MAX_SIDE_M, MIN_SIDE_M
from .sources import ENV_OVERPASS_URL, FIELD_LABELS, has_credential, migrate_legacy_bbox, migrate_legacy_centre

if TYPE_CHECKING:
    import bpy.types


def _is_map_collection(self: "MB_Settings", coll: "bpy.types.Collection") -> bool:
    return "mb_map" in coll


def _scrub(prop: str) -> Callable[["MB_Settings", "bpy.types.Context"], None]:
    """``update`` callback clearing a credential-like value of ``prop`` before it can be saved."""
    def update(self: "MB_Settings", context: "bpy.types.Context") -> None:
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
    # the centre and the bbox edges are text, not FloatProperty: Blender stores floats as float32 (centimetre to
    # decimetre error at 40-50 N), which
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
    centre_migrated: BoolProperty(name="Legacy centre migrated", default=False, options={"HIDDEN"})
    width: FloatProperty(name="Width (m)", description="East-west extent in metres", default=1000.0,
                         min=MIN_SIDE_M, max=DEFAULT_MAX_SIDE_M)
    height: FloatProperty(name="Height (m)", description="North-south extent in metres", default=1000.0,
                          min=MIN_SIDE_M, max=DEFAULT_MAX_SIDE_M)
    bbox_south_deg: StringProperty(name="South", description="Bounding box south edge (degrees, full precision)", default="")
    bbox_west_deg: StringProperty(name="West", description="Bounding box west edge (degrees, full precision)", default="")
    bbox_north_deg: StringProperty(name="North", description="Bounding box north edge (degrees, full precision)", default="")
    bbox_east_deg: StringProperty(name="East", description="Bounding box east edge (degrees, full precision)", default="")
    # legacy float32 bbox of older .blend files: registered (so the saved value stays readable), hidden, migrated
    # into the ``bbox_*_deg`` text fields on load and at Generate
    bbox_south: FloatProperty(name="South (legacy)", min=-85.0, max=85.0, precision=6, options={"HIDDEN"})
    bbox_west: FloatProperty(name="West (legacy)", min=-180.0, max=180.0, precision=6, options={"HIDDEN"})
    bbox_north: FloatProperty(name="North (legacy)", min=-85.0, max=85.0, precision=6, options={"HIDDEN"})
    bbox_east: FloatProperty(name="East (legacy)", min=-180.0, max=180.0, precision=6, options={"HIDDEN"})
    bbox_migrated: BoolProperty(name="Legacy bbox migrated", default=False, options={"HIDDEN"})

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
    style: EnumProperty(name="Style", items=[
        ("stylized", "Stylized", "Stylized palette and faceted look (default)"),
        ("classic", "Classic", "Pre-S5 classic look (byte-identical baseline mode)"),
    ], default="stylized")
    textures: BoolProperty(name="Textures", default=True,
                           description="Procedural CC0 textures: UV-mapped materials on Generate and embedded "
                                       "textures with TEXCOORD_0 on Export (off: the untextured package layout)")

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
def _migrate_on_load(*_: object) -> None:
    for scene in bpy.data.scenes:
        migrate_legacy_centre(scene.map_builder)
        migrate_legacy_bbox(scene.map_builder)


def register() -> None:
    bpy.utils.register_class(MB_Settings)
    bpy.types.Scene.map_builder = PointerProperty(type=MB_Settings)
    if _migrate_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_migrate_on_load)


def unregister() -> None:
    if _migrate_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_migrate_on_load)
    del bpy.types.Scene.map_builder
    bpy.utils.unregister_class(MB_Settings)
