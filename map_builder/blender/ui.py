# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from .sources import ENV_OVERPASS_URL, attribution_lines

if TYPE_CHECKING:
    import bpy.types

ATTRIBUTION_LINES = (
    "Elevation: Copernicus DEM GLO-30 (ESA) when selected",
    "Features: (c) OpenStreetMap contributors, ODbL",
    "Details (materials, inferred heights, vegetation) are procedural",
)


class MB_PT_main(bpy.types.Panel):
    bl_label = "Map Builder"
    bl_idname = "MB_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Map Builder"

    def draw(self, context: bpy.types.Context) -> None:
        s = context.scene.map_builder
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        box = layout.box()
        box.label(text="Area (WGS84)", icon="WORLD")
        box.prop(s, "area_mode", expand=True)
        col = box.column(align=True)
        if s.area_mode == "BBOX":
            col.prop(s, "bbox_south")
            col.prop(s, "bbox_west")
            col.prop(s, "bbox_north")
            col.prop(s, "bbox_east")
        else:
            col.prop(s, "centre_lat")
            col.prop(s, "centre_lon")
            col.prop(s, "width")
            col.prop(s, "height")

        box = layout.box()
        box.label(text="Sources", icon="IMPORT")
        box.prop(s, "elevation_source")
        if s.elevation_source == "file":
            box.prop(s, "elevation_file")
            box.prop(s, "elevation_crs")
            box.prop(s, "elevation_vertical_datum")
            box.prop(s, "elevation_license")
        box.prop(s, "terrain_spacing")
        box.prop(s, "dsm_correction")
        box.prop(s, "osm_source")
        if s.osm_source == "file":
            box.prop(s, "osm_file")
        else:
            box.prop(s, "overpass_endpoint")
            if s.overpass_endpoint == "env":
                box.label(text=f"URL is read from ${ENV_OVERPASS_URL} (not saved)", icon="INFO")
        box.prop(s, "cache_dir")
        if s.credential_notice:
            box.label(text=s.credential_notice, icon="ERROR")
        online = getattr(bpy.app, "online_access", True)
        if not online and (s.elevation_source == "copernicus" or s.osm_source == "overpass"):
            box.label(text="Online access is disabled: use local files", icon="ERROR")

        box = layout.box()
        box.label(text="Content", icon="OUTLINER_COLLECTION")
        row = box.row(align=True)
        row.prop(s, "buildings", toggle=True)
        row.prop(s, "roads", toggle=True)
        row.prop(s, "trees", toggle=True)
        box.prop(s, "scatter")
        box.prop(s, "textures")
        box.prop(s, "max_trees")
        box.prop(s, "seed")
        box.prop(s, "package_name")
        box.operator("map_builder.generate", icon="WORLD")

        box = layout.box()
        box.label(text="Export", icon="EXPORT")
        box.prop(s, "export_collection")
        box.prop(s, "export_path")
        box.prop(s, "heightfield_spacing")
        row = box.row(align=True)
        row.operator("map_builder.export", icon="EXPORT")
        row.operator("map_builder.validate", icon="CHECKMARK")

        col = layout.column(align=True)
        for line in ATTRIBUTION_LINES:
            col.label(text=line)
        for line in attribution_lines(s.textures):
            col.label(text=line)


def register() -> None:
    bpy.utils.register_class(MB_PT_main)


def unregister() -> None:
    bpy.utils.unregister_class(MB_PT_main)
