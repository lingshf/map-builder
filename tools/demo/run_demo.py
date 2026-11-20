# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""One-command demo kit: renders, viewer bundle and summary for a Map Builder package.

    blender -b --factory-startup --python-exit-code 1 --python tools/demo/run_demo.py -- \
        --preset synthetic --after examples/synthetic_sample.mbmap [--before old.mbmap] --out demo-out

Cycles CPU only (EEVEE/Workbench need OpenGL, which headless dev machines lack). ``--bundle-only`` skips the
renders and also runs under plain Python (``py -3 tools/demo/run_demo.py --bundle-only ...``).
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile
from collections.abc import Sequence
from types import ModuleType
from typing import TYPE_CHECKING

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demo_bundle as db  # noqa: E402

if TYPE_CHECKING:
    from bpy.types import Object, Scene

PANEL_LIMIT = ("`panel.png` not produced: no Mesa (llvmpipe) Blender copy configured, and background Blender has "
               "no window or OpenGL context (see tools/demo/README.md, \"Panel screenshot\")")
PANEL_DONE = "`panel.png`: the real Map Builder sidebar in Blender's UI (software OpenGL via Mesa llvmpipe)"
ENV_MESA = "MB_DEMO_BLENDER_MESA"


def find_mesa_blender(flag: str | None) -> str | None:
    """Path of the separate Blender copy that has Mesa's opengl32.dll next to blender.exe, or None."""
    path = flag or os.environ.get(ENV_MESA)
    if path and os.path.isfile(path) and os.path.isfile(os.path.join(os.path.dirname(path), "opengl32.dll")):
        return path
    return None


def run_panel(blender: str, pkg: db.Package, preset: db.Preset, out_dir: str) -> tuple[bool, str]:
    """Screenshot of the add-on panel via panel_shot.py in a windowed Blender; (ok, note)."""
    import subprocess
    area = preset["area"]
    png = os.path.join(out_dir, "panel.png")
    if os.path.exists(png):
        os.remove(png)
    with tempfile.TemporaryDirectory() as td:
        glb = os.path.join(td, "map.glb")
        with open(glb, "wb") as f:
            f.write(pkg["glb"])
        cmd = [blender, "--factory-startup", "--enable-event-simulate", "--python",
               os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel_shot.py"), "--",
               "--glb", glb, "--out", png, "--lat", str(area["lat"]), "--lon", str(area["lon"]),
               "--width", str(area["width_m"]), "--height", str(area["height_m"]),
               "--name", str(pkg["manifest"].get("name", "map"))]
        try:
            subprocess.run(cmd, timeout=180, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, f"`panel.png` not produced: Mesa Blender failed ({type(e).__name__})"
    if os.path.isfile(png):
        return True, PANEL_DONE
    return False, "`panel.png` not produced: the Mesa Blender run did not write a screenshot"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", required=True, help="preset name in tools/demo/presets or a path to a .json")
    ap.add_argument("--after", required=True, help="current .mbmap")
    ap.add_argument("--before", default=None, help="previous .mbmap (adds -before renders)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bundle-only", action="store_true", help="skip renders (viewer, probes, summary only)")
    ap.add_argument("--panel", action="store_true",
                    help="also write panel.png using the Mesa Blender copy (--mesa-blender or $%s)" % "MB_DEMO_BLENDER_MESA")
    ap.add_argument("--mesa-blender", default=None, help="blender.exe of a separate copy with Mesa opengl32.dll")
    return ap.parse_args(argv)


def _clear_scene(bpy: ModuleType) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _setup_render(bpy: ModuleType, scene: Scene) -> None:
    scene.render.engine = "CYCLES"
    c = scene.cycles
    c.device = "CPU"
    c.samples = db.SAMPLES
    c.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = db.RENDER_SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("sky")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(40)
    sky.sun_rotation = math.radians(150)
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 2.0
    sky.sun_disc = False
    ob = bpy.data.objects.new("sun", sun)
    scene.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(40), 0, math.radians(150))


def _use_vertex_colors(bpy: ModuleType) -> None:
    """The GLB carries colour in COLOR_0; feed the (default) colour attribute into Base Color."""
    for mat in bpy.data.materials:
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) if nt else None
        if bsdf is None or bsdf.inputs["Base Color"].is_linked:
            continue
        vc = nt.nodes.new("ShaderNodeVertexColor")
        nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])


def _look_at(cam_ob: Object, eye: Sequence[float], target: Sequence[float]) -> None:
    from mathutils import Vector
    cam_ob.location = Vector(eye)
    d = Vector(target) - Vector(eye)
    cam_ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render_package(pkg: db.Package, preset: db.Preset, suffix: str, out_dir: str) -> list[str]:
    import bpy
    _clear_scene(bpy)
    scene = bpy.context.scene
    with tempfile.TemporaryDirectory() as td:
        glb = os.path.join(td, "map.glb")
        with open(glb, "wb") as f:
            f.write(pkg["glb"])
        bpy.ops.import_scene.gltf(filepath=glb)
    _use_vertex_colors(bpy)
    _setup_render(bpy, scene)
    cam = bpy.data.cameras.new("cam")
    cam_ob = bpy.data.objects.new("cam", cam)
    scene.collection.objects.link(cam_ob)
    scene.camera = cam_ob
    cam.clip_end = 5000
    names: list[str] = []
    for c in preset["cameras"]:
        cam.lens = c.get("lens_mm", 35)
        _look_at(cam_ob, c["eye"], c["target"])
        name = f"render-{c['name']}-{suffix}.png"
        scene.render.filepath = os.path.join(out_dir, name)
        bpy.ops.render.render(write_still=True)
        names.append(name)
        print("rendered", name)
    return names


def main(argv: Sequence[str]) -> None:
    a = parse_args(argv)
    preset = db.load_preset(a.preset)
    os.makedirs(a.out, exist_ok=True)
    stale = os.path.join(a.out, "panel.png")
    if os.path.exists(stale):
        os.remove(stale)
    after = db.read_package(a.after)
    before = db.read_package(a.before) if a.before else None
    if not a.bundle_only:
        render_package(after, preset, "after", a.out)
        if before is not None:
            render_package(before, preset, "before", a.out)
    expected = db.render_names(preset, before is not None) if not a.bundle_only else []
    probes = db.probe_results(after)
    db.write_viewer(a.out, after, probes)
    note = "Panel screenshot: " + PANEL_LIMIT
    if a.panel:
        mesa = find_mesa_blender(a.mesa_blender)
        if mesa:
            ok, note = run_panel(mesa, after, preset, a.out)
            if ok:
                expected = expected + ["panel.png"]
        else:
            print("--panel: no Mesa Blender copy found; skipping panel.png", file=sys.stderr)
    text = db.summary_md(preset, after, probes, expected, note, before)
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("demo written to", a.out)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
