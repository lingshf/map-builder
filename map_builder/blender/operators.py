"""Operators: Generate (new collection, report Text), Export (validated package), Validate.

Failure policy (all three operators): a cancelled operator changes nothing in the scene. The problem is
shown with ``self.report`` (status bar / Info editor) and the full list is printed to the system console;
the report Text ('MapBuilder Report') is written only after a successful operation, so the last good
report is never overwritten by a failure.
"""

import math
import os

import bpy

from ..core.errors import MapBuilderError
from ..core.generate import PlanOptions
from ..core.geodesy import Area
from ..core.package import validate_package
from ..core.pipeline import Settings, generate_plan
from . import export as mb_export
from .scene_build import build_scene, write_report_text
from .sources import (SettingsInputError, format_report, needs_network, redact_diagnostics, reject_credentials,
                      settings_kwargs)

REPORT_TEXT = "MapBuilder Report"


def _abspath(p):
    return os.path.abspath(bpy.path.abspath(p)) if p else ""


def fail(op, headline, problems=()):
    """Report a cancelled operation without touching the scene: console gets every problem, the operator
    report the headline plus the first problem."""
    problems = redact_diagnostics([str(p) for p in problems])
    headline = redact_diagnostics([headline])[0]
    print(f"Map Builder: {headline}" + "".join(f"\n  - {p}" for p in problems))
    more = f" (+{len(problems) - 1} more, see the system console)" if len(problems) > 1 else ""
    op.report({"ERROR"}, f"{headline}: {problems[0]}{more}" if problems else headline)
    return {"CANCELLED"}


def ui_values(s):
    return {"elevation_source": s.elevation_source, "elevation_file": _abspath(s.elevation_file),
            "elevation_crs": s.elevation_crs, "elevation_vertical_datum": s.elevation_vertical_datum,
            "elevation_license": s.elevation_license, "terrain_spacing": s.terrain_spacing,
            "osm_source": s.osm_source, "osm_file": _abspath(s.osm_file),
            "overpass_endpoint": s.overpass_endpoint, "cache_dir": _abspath(s.cache_dir),
            "package_name": s.package_name, "dsm_correction": s.dsm_correction}


def make_settings(s):
    kw = settings_kwargs(ui_values(s), os.environ)
    kw["plan_options"] = PlanOptions(buildings=s.buildings, roads=s.roads, trees=s.trees, scatter=s.scatter,
                                     max_trees=s.max_trees, seed=s.seed)
    return Settings(**kw)


def make_area(s):
    if s.area_mode == "BBOX":
        return Area.from_bbox(s.bbox_south, s.bbox_west, s.bbox_north, s.bbox_east)
    return Area(parse_degrees(s.lat, "Latitude"), parse_degrees(s.lon, "Longitude"), s.width, s.height)


def parse_degrees(text, label):
    """The centre coordinate typed in the UI as a double (Area validates the range)."""
    try:
        value = float(text.strip().replace(",", "."))
    except ValueError:
        raise SettingsInputError(f"{label} must be a number in degrees, e.g. 40.437") from None
    if not math.isfinite(value):
        raise SettingsInputError(f"{label} must be a finite number")
    return value


def online_access_problem(values):
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

    def execute(self, context):
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
            root = build_scene(context, plan, sources, name)
        except (MapBuilderError, SettingsInputError, ValueError, OSError) as e:
            return fail(self, "Generation failed; nothing was created", [str(e)])
        finally:
            wm.progress_end()
        s.export_collection = root
        write_report_text(REPORT_TEXT, format_report(f"Generated collection '{root.name}' "
                                                     f"({len(plan.objects)} objects)", sources, plan.report))
        rep = plan.report
        n_unsup, n_inv, n_warn = (len(rep.get(k) or []) for k in ("unsupported_features", "invalid_features",
                                                                  "warnings"))
        self.report({"WARNING" if (n_unsup or n_inv or n_warn) else "INFO"},
                    f"Created '{root.name}': {len(plan.objects)} objects; {n_unsup} unsupported, {n_inv} invalid "
                    f"feature(s), {n_warn} warning(s); see Text '{REPORT_TEXT}'")
        return {"FINISHED"}


class MB_OT_export(bpy.types.Operator):
    bl_idname = "map_builder.export"
    bl_label = "Export Map Package"
    bl_description = "Export the edited map (final evaluated geometry, modifiers applied) as a validated " \
                     ".mbmap package; on failure the previous package is kept"

    def execute(self, context):
        s = context.scene.map_builder
        name = s.package_name.strip() or "map"
        try:
            reject_credentials({"package_name": s.package_name, "export_path": s.export_path},
                               "Nothing was exported")
            manifest, result, report, edits = mb_export.export_map(
                context, s.export_path, name, s.heightfield_spacing, root=s.export_collection)
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

    def execute(self, context):
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


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
