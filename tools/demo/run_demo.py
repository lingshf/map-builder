"""One-command demo kit: renders, viewer bundle and summary for a Map Builder package.

    blender -b --factory-startup --python-exit-code 1 --python tools/demo/run_demo.py -- \
        --preset synthetic --after examples/synthetic_sample.mbmap [--before old.mbmap] --out demo-out

Cycles CPU only (EEVEE/Workbench need OpenGL, which headless dev machines lack). ``--bundle-only`` skips the
renders and also runs under plain Python (``py -3 tools/demo/run_demo.py --bundle-only ...``).
"""

import argparse
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demo_bundle as db  # noqa: E402

PANEL_LIMIT = ("`panel.png` not produced: background Blender has no window or OpenGL context, so "
               "`bpy.ops.screen.screenshot` cannot capture the sidebar (known limit; the UI is not faked)")


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", required=True, help="preset name in tools/demo/presets or a path to a .json")
    ap.add_argument("--after", required=True, help="current .mbmap")
    ap.add_argument("--before", default=None, help="previous .mbmap (adds -before renders)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bundle-only", action="store_true", help="skip renders (viewer, probes, summary only)")
    return ap.parse_args(argv)


def _clear_scene(bpy):
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _setup_render(bpy, scene):
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


def _use_vertex_colors(bpy):
    """The GLB carries colour in COLOR_0; feed the (default) colour attribute into Base Color."""
    for mat in bpy.data.materials:
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) if nt else None
        if bsdf is None or bsdf.inputs["Base Color"].is_linked:
            continue
        vc = nt.nodes.new("ShaderNodeVertexColor")
        nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])


def _look_at(cam_ob, eye, target):
    from mathutils import Vector
    cam_ob.location = Vector(eye)
    d = Vector(target) - Vector(eye)
    cam_ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render_package(pkg, preset, suffix, out_dir):
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
    names = []
    for c in preset["cameras"]:
        cam.lens = c.get("lens_mm", 35)
        _look_at(cam_ob, c["eye"], c["target"])
        name = f"render-{c['name']}-{suffix}.png"
        scene.render.filepath = os.path.join(out_dir, name)
        bpy.ops.render.render(write_still=True)
        names.append(name)
        print("rendered", name)
    return names


def main(argv):
    a = parse_args(argv)
    preset = db.load_preset(a.preset)
    os.makedirs(a.out, exist_ok=True)
    after = db.read_package(a.after)
    before = db.read_package(a.before) if a.before else None
    if not a.bundle_only:
        render_package(after, preset, "after", a.out)
        if before is not None:
            render_package(before, preset, "before", a.out)
    expected = db.render_names(preset, before is not None) if not a.bundle_only else []
    db.write_viewer(a.out, after)
    note = "Panel screenshot: " + PANEL_LIMIT
    text = db.summary_md(preset, after, db.probe_results(after), expected, note, before)
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("demo written to", a.out)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
