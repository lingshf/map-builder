# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""S5-F3 step 2 evidence: same-camera renders of the I-90 crossing of a package's visual GLB.

  blender -b --factory-startup --python render_i90.py -- PACKAGE.mbmap OUT_PREFIX

Writes OUT_PREFIX-oblique.png (everything, seen from above the south-east bank) and OUT_PREFIX-plan.png
(top-down orthographic with the bridges hidden, so the bank strips under the decks show). Cycles on the CPU, flat
materials: bank orange, water blue, bridges grey, terrain green, everything else white. The cameras are fixed, so
two packages render from exactly the same viewpoint.
"""
from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

import bpy
from mathutils import Vector

TARGET = Vector((-640.0, 40.0, 6.0))          # map metres: the I-90 decks over the bank of osm:relation/2315576
OBLIQUE_EYE = Vector((-565.0, -85.0, 45.0))
PLAN_HEIGHT_M = 120.0
PLAN_SPAN_M = 260.0
RESOLUTION = (1600, 1000)
RENDER_SAMPLES = 16
SKY = (0.6, 0.7, 0.8)
SUN_ROTATION = (0.6, 0.2, 0.8)
COLOURS = {"bank": (0.95, 0.55, 0.1, 1.0), "water": (0.1, 0.35, 0.8, 1.0), "bridge": (0.55, 0.55, 0.55, 1.0),
           "terrain": (0.35, 0.6, 0.3, 1.0)}
OTHER_COLOUR = (0.9, 0.9, 0.9, 1.0)


def import_visual(package: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with zipfile.ZipFile(package) as z, tempfile.TemporaryDirectory() as scratch:
        glb = Path(scratch) / "map.glb"
        glb.write_bytes(z.read("visual/map.glb"))
        bpy.ops.import_scene.gltf(filepath=str(glb))


def kind(obj: bpy.types.Object) -> str:
    name = obj.name.lower()
    return next((k for k in COLOURS if name.startswith(k)), "other")


def material(colour: tuple[float, float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.new(f"evidence_{colour}")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = colour
    return mat


def colour_objects() -> None:
    materials = {k: material(c) for k, c in COLOURS.items()}
    other = material(OTHER_COLOUR)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            obj.data.materials.clear()
            obj.data.materials.append(materials.get(kind(obj), other))


def setup_render() -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"     # CPU: headless Blender has no OpenGL for Workbench or Eevee
    scene.cycles.device = "CPU"
    scene.cycles.samples = RENDER_SAMPLES
    scene.world = bpy.data.worlds.new("evidence_sky")
    scene.world.color = SKY
    sun = bpy.data.objects.new("evidence_sun", bpy.data.lights.new("evidence_sun", "SUN"))
    sun.rotation_euler = SUN_ROTATION
    scene.collection.objects.link(sun)
    scene.render.resolution_x, scene.render.resolution_y = RESOLUTION
    scene.render.image_settings.file_format = "PNG"


def aim(camera: bpy.types.Object, eye: Vector) -> None:
    camera.location = eye
    camera.rotation_euler = (TARGET - eye).to_track_quat("-Z", "Y").to_euler()


def render(camera_data: bpy.types.Camera, eye: Vector, out: Path) -> None:
    camera = bpy.data.objects.new("evidence_camera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    aim(camera, eye)
    bpy.context.scene.camera = camera
    bpy.context.scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(camera)


def oblique(out: Path) -> None:
    data = bpy.data.cameras.new("oblique")
    data.lens = 24.0
    render(data, OBLIQUE_EYE, out)


def plan(out: Path) -> None:
    for obj in bpy.context.scene.objects:
        if kind(obj) == "bridge":
            obj.hide_render = True
    data = bpy.data.cameras.new("plan")
    data.type = "ORTHO"
    data.ortho_scale = PLAN_SPAN_M
    render(data, TARGET + Vector((0.0, 0.0, PLAN_HEIGHT_M)), out)


def main(argv: list[str]) -> int:
    package, prefix = Path(argv[0]), argv[1]
    import_visual(package)
    colour_objects()
    setup_render()
    oblique(Path(f"{prefix}-oblique.png"))
    plan(Path(f"{prefix}-plan.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:]))
