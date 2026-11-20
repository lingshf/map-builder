# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Offline release evidence. Run in factory-startup Blender; see README.md."""

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import map_builder
from map_builder.blender.scene_build import build_scene, write_report_text
from map_builder.blender.sources import format_report
from map_builder.core.collision import read_collision
from map_builder.core.geodesy import Area
from map_builder.core.package import validate_package
from map_builder.core.pipeline import Settings, generate_plan


def export_sample(settings, out, name):
    settings.export_path = str(out / f"{name}.mbmap")
    if bpy.ops.map_builder.export() != {"FINISHED"}:
        raise RuntimeError(f"Export failed: {name}")
    result = validate_package(settings.export_path)
    if not result.ok:
        raise RuntimeError(result.summary())
    with zipfile.ZipFile(settings.export_path) as package:
        manifest_bytes = package.read("manifest.json")
        manifest = json.loads(manifest_bytes)
        (out / f"{name}.glb").write_bytes(package.read("visual/map.glb"))
        (out / f"{name}-report.json").write_bytes(package.read("report.json"))
    return {
        "package_id": "sha256:" + hashlib.sha256(manifest_bytes).hexdigest(),
        "schema_version": manifest["schema_version"],
        "objects": len(manifest["objects"]),
        "validation": result.summary(),
        "warnings": result.warnings,
    }


def render(scene, camera, out, name, eye, target, scale):
    camera.location = eye
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = scale
    scene.render.filepath = str(out / name)
    bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New throwaway directory; must not exist")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = out / "inputs"
    inputs.mkdir()
    for name in ("synthetic_area.osm", "synthetic_dem.asc"):
        shutil.copyfile(REPO / "tests" / "fixtures" / name, inputs / name)

    map_builder.register()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    s = bpy.context.scene.map_builder
    s.lat, s.lon, s.width, s.height = 47.0, 8.0, 400.0, 300.0
    s.elevation_source, s.elevation_file = "file", str(inputs / "synthetic_dem.asc")
    s.elevation_crs, s.elevation_vertical_datum = "EPSG:4326", "SYNTHETIC"
    s.elevation_license = "SYNTHETIC test data (no licence required)"
    s.osm_source, s.osm_file = "file", str(inputs / "synthetic_area.osm")
    s.package_name = "synthetic_preview"
    s.terrain_spacing, s.heightfield_spacing = 10.0, 2.0
    # The UI lacks an OSM licence override. Use the same pipeline with the explicit
    # fixture attribution rather than mislabelling invented data as OpenStreetMap.
    settings = Settings(
        elevation_source="file", elevation_file=s.elevation_file,
        elevation_crs=s.elevation_crs, elevation_vertical_datum=s.elevation_vertical_datum,
        elevation_license=s.elevation_license, osm_source="file", osm_file=s.osm_file,
        osm_license="SYNTHETIC hand-written OSM-format fixture, not OpenStreetMap data; no licence required",
        terrain_spacing=10.0,
    )
    plan, sources = generate_plan(Area(47.0, 8.0, 400.0, 300.0), settings)
    root = build_scene(bpy.context, plan, sources, s.package_name)
    s.export_collection = root
    write_report_text("MapBuilder Report", format_report("SYNTHETIC release demo", sources, plan.report))
    summary = {"data": "SYNTHETIC, not a real place", "before": export_sample(s, out, "before")}

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1200, 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.65, 0.75, 0.9, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7
    sun = bpy.data.objects.new("Demo Sun", bpy.data.lights.new("Demo Sun", "SUN"))
    scene.collection.objects.link(sun)
    sun.data.energy = 3.0
    sun.rotation_euler = (0.4, -0.5, -0.5)
    camera = bpy.data.objects.new("Demo Camera", bpy.data.cameras.new("Demo Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = "ORTHO"
    render(scene, camera, out, "overview.png", (420, -500, 530), (0, 0, 15), 540)

    building = max((ob for ob in root.all_objects if ob.get("mb_class") == "building"),
                   key=lambda ob: ob.dimensions.x * ob.dimensions.y * ob.dimensions.z)
    center = sum((building.matrix_world @ Vector(corner) for corner in building.bound_box), Vector()) / 8
    eye = center + Vector((100, -130, 110))
    render(scene, camera, out, "edit-before.png", eye, center, 150)
    old_scale = tuple(building.scale)
    building.scale.z *= 1.8
    bpy.context.view_layer.update()
    summary["edit"] = {"mb_id": building["mb_id"], "scale_before": old_scale,
                       "scale_after": tuple(building.scale)}
    summary["after"] = export_sample(s, out, "after")
    heights = []
    for name in ("before", "after"):
        with zipfile.ZipFile(out / f"{name}.mbmap") as package:
            collision = read_collision(package.read("collision/map.mbcol"))
        entry = next(ob for ob in collision.objects if ob["mb_id"] == building["mb_id"])
        heights.append(entry["aabb"][5] - entry["aabb"][2])
    if abs(heights[1] - heights[0] * 1.8) > 1e-4:
        raise RuntimeError("Exported collision does not reflect the building's 1.8x height edit")
    summary["edit"]["collision_heights_m"] = heights
    render(scene, camera, out, "edit-after.png", eye, center, 150)
    if summary["before"]["package_id"] == summary["after"]["package_id"]:
        raise RuntimeError("The edited package must have a different identity")

    # Also exercise a GLB import in an isolated scene, preserving the editable map.
    map_scene = scene
    imported_scene = bpy.data.scenes.new("GLB inspection")
    bpy.context.window.scene = imported_scene
    if bpy.ops.import_scene.gltf(filepath=str(out / "after.glb")) != {"FINISHED"}:
        raise RuntimeError("GLB import failed")
    imported_meshes = sum(ob.type == "MESH" for ob in imported_scene.objects)
    if imported_meshes != summary["after"]["objects"]:
        raise RuntimeError("Imported GLB mesh count differs from the package")
    summary["glb_import_meshes"] = imported_meshes
    bpy.context.window.scene = map_scene
    bpy.data.scenes.remove(imported_scene)
    bpy.ops.object.select_all(action="DESELECT")
    building.select_set(True)
    bpy.context.view_layer.objects.active = building
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "editable-demo.blend"))
    (out / "evidence.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("DEMO_OK " + str(out))


if __name__ == "__main__":
    main()
