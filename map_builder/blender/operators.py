# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""Operators: Generate (new collection, report Text), Export (validated package), Validate.

Failure policy (all three operators): a cancelled operator changes nothing in the scene. The problem is
shown with ``self.report`` (status bar / Info editor) and the full list is printed to the system console;
the report Text ('MapBuilder Report') is written only after a successful operation, so the last good
report is never overwritten by a failure.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

import bpy

from ..core.errors import MapBuilderError
from ..core.generate import PlanOptions
from ..core.geodesy import Area
from ..core.package import validate_package
from ..core.pipeline import Settings, generate_plan
from . import export as mb_export
from .scene_build import build_scene, write_report_text
from .sources import (SettingsInputError, format_report, migrate_legacy_bbox, migrate_legacy_centre, needs_network, parse_degrees,
                      redact_diagnostics, reject_credentials, settings_kwargs, UiValues)

if TYPE_CHECKING:
    import bpy.types

    from .props import MB_Settings

REPORT_TEXT = "MapBuilder Report"


def _abspath(p: str) -> str:
    return os.path.abspath(bpy.path.abspath(p)) if p else ""


def fail(op: bpy.types.Operator, headline: str, problems: Sequence[object] = ()) -> set[str]:
    """Report a cancelled operation without touching the scene: console gets every problem, the operator
    report the headline plus the first problem."""
    problems = redact_diagnostics([str(p) for p in problems])
    headline = redact_diagnostics([headline])[0]
    print(f"Map Builder: {headline}" + "".join(f"\n  - {p}" for p in problems))
    more = f" (+{len(problems) - 1} more, see the system console)" if len(problems) > 1 else ""
    op.report({"ERROR"}, f"{headline}: {problems[0]}{more}" if problems else headline)
    return {"CANCELLED"}


def ui_values(s: MB_Settings) -> UiValues:
    return {"elevation_source": s.elevation_source, "elevation_file": _abspath(s.elevation_file),
            "elevation_crs": s.elevation_crs, "elevation_vertical_datum": s.elevation_vertical_datum,
            "elevation_license": s.elevation_license, "terrain_spacing": s.terrain_spacing,
            "osm_source": s.osm_source, "osm_file": _abspath(s.osm_file),
            "overpass_endpoint": s.overpass_endpoint, "cache_dir": _abspath(s.cache_dir),
            "package_name": s.package_name, "dsm_correction": s.dsm_correction}


def make_settings(s: MB_Settings) -> Settings:
    kw = settings_kwargs(ui_values(s), os.environ)
    kw["plan_options"] = PlanOptions(buildings=s.buildings, roads=s.roads, trees=s.trees, scatter=s.scatter,
                                     max_trees=s.max_trees, seed=s.seed, style=s.style)
    return Settings(**kw)


def make_area(s: MB_Settings) -> Area:
    if s.area_mode == "BBOX":
        migrate_legacy_bbox(s)
        return Area.from_bbox(*(parse_degrees(getattr(s, f"bbox_{edge}_deg"), edge.capitalize())
                               for edge in ("south", "west", "north", "east")))
    migrate_legacy_centre(s)
    return Area(parse_degrees(s.centre_lat, "Latitude"), parse_degrees(s.centre_lon, "Longitude"), s.width, s.height)


def online_access_problem(values: Mapping[str, object]) -> str | None:
    """Error text if a network source is selected while Blender's online access is disabled."""
    if needs_network(values) and not getattr(bpy.app, "online_access", True):
        names = [n for n, on in (("Copernicus elevation", values["elevation_source"] == "copernicus"),
                                 ("Overpass features", values["osm_source"] == "overpass")) if on]
        return (f"Online access is disabled in Blender (Preferences > System > Network, or --offline-mode), "
                f"but {' and '.join(names)} need the network. Enable online access or choose local files. "
                "Nothing was generated.")
    return None


class MB_OT_generate(bpy.types.Operator):
    bl_idname = "map_builder.generate"
    bl_label = "Generate Map"
    bl_description = "Load terrain and OpenStreetMap data and create a NEW editable map collection " \
                     "(existing content is never changed or deleted)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        s = context.scene.map_builder
        name = s.package_name.strip() or "map"
        problem = online_access_problem(ui_values(s))
        if problem:
            return fail(self, problem)
        wm = context.window_manager
        wm.progress_begin(0, 100)
        try:
            area = make_area(s)
            settings = make_settings(s)
            plan, sources = generate_plan(area, settings, progress=lambda f: wm.progress_update(int(f * 90)))
            root = build_scene(context, plan, sources, name, s.textures and s.style == "classic", style=s.style)
        except (MapBuilderError, SettingsInputError, ValueError, OSError) as e:
            return fail(self, "Generation failed; nothing was created", [str(e)])
        finally:
            wm.progress_end()
        s.export_collection = root
        write_report_text(REPORT_TEXT, format_report(f"Generated collection '{root.name}' "
                                                     f"({len(plan.objects)} objects)", sources, plan.report))
        rep = plan.report
        n_unsup = len(rep.get("unsupported_features") or [])
        n_inv = len(rep.get("invalid_features") or [])
        n_warn = len(rep.get("warnings") or [])
        self.report({"WARNING" if (n_unsup or n_inv or n_warn) else "INFO"},
                    f"Created '{root.name}': {len(plan.objects)} objects; {n_unsup} unsupported, {n_inv} invalid "
                    f"feature(s), {n_warn} warning(s); see Text '{REPORT_TEXT}'")
        return {"FINISHED"}


class MB_OT_export(bpy.types.Operator):
    bl_idname = "map_builder.export"
    bl_label = "Export Map Package"
    bl_description = "Export the edited map (final evaluated geometry, modifiers applied) as a validated " \
                     ".mbmap package; on failure the previous package is kept"

    def execute(self, context: bpy.types.Context) -> set[str]:
        s = context.scene.map_builder
        name = s.package_name.strip() or "map"
        try:
            reject_credentials({"package_name": s.package_name, "export_path": s.export_path},
                               "Nothing was exported")
            manifest, result, report, edits = mb_export.export_map(
                context, s.export_path, name, s.heightfield_spacing, root=s.export_collection,
                textures=s.textures and s.style == "classic")
        except (MapBuilderError, ValueError, OSError) as e:
            errors = getattr(e, "errors", None) or [str(e)]
            return fail(self, f"Export failed (previous package kept): {len(errors)} problem(s)", errors)
        write_report_text(REPORT_TEXT, format_report(
            f"Exported {mb_export.resolve_path(s.export_path)}\n{result.summary()}",
            manifest.get("sources", []), report))
        level = "WARNING" if (report["blender_export"]["warnings"] or result.warnings) else "INFO"
        self.report({level}, f"Exported {len(manifest['objects'])} objects ({len(edits['removed'])} removed, "
                             f"{len(edits['duplicated'])} duplicated, {len(edits['user_added'])} user-added); "
                             f"{result.summary()}")
        return {"FINISHED"}


class MB_OT_validate(bpy.types.Operator):
    bl_idname = "map_builder.validate"
    bl_label = "Validate Package"
    bl_description = "Validate an existing .mbmap package (hashes, schema, visual/collision consistency)"

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            path = mb_export.resolve_path(context.scene.map_builder.export_path)
        except MapBuilderError as e:
            return fail(self, "Validation not run", [str(e)])
        result = validate_package(path)
        if not result.ok:
            return fail(self, f"Package is invalid: {result.summary().splitlines()[0]}", result.errors)
        write_report_text(REPORT_TEXT, f"VALIDATE {path}\n{result.summary()}\n\nerrors:\n"
                          + "\n".join(result.errors) + "\n\nwarnings:\n" + "\n".join(result.warnings) + "\n")
        self.report({"INFO"}, result.summary())
        return {"FINISHED"}


classes = (MB_OT_generate, MB_OT_export, MB_OT_validate)


def register() -> None:
    for c in classes:
        bpy.utils.register_class(c)


def unregister() -> None:
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
