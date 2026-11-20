"""Start-up script for a NON-background Blender (software OpenGL via Mesa llvmpipe): shows the Map Builder
sidebar panel next to the package's map and saves a real screenshot of the Blender window.

    blender --factory-startup --python tools/demo/panel_shot.py -- --glb map.glb --out panel.png \
        --lat 47 --lon 8 --width 400 --height 300 [--name synthetic_sample]

Started by run_demo.py --panel; exits Blender when done (exit code 0 only if the file was written).
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Euler

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--lat", type=float, required=True)
ap.add_argument("--lon", type=float, required=True)
ap.add_argument("--width", type=float, required=True)
ap.add_argument("--height", type=float, required=True)
ap.add_argument("--name", default="map")
ARGS = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
state = {"ticks": 0, "shot": False}


def view3d():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                return win, area
    return None, None


def setup():
    import map_builder
    map_builder.register()
    s = bpy.context.scene.map_builder
    s.area_mode = "CENTER"
    s.centre_lat, s.centre_lon, s.width, s.height = repr(ARGS.lat), repr(ARGS.lon), ARGS.width, ARGS.height
    s.package_name = ARGS.name
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    bpy.ops.import_scene.gltf(filepath=ARGS.glb)
    for ob in bpy.data.objects:
        ob.select_set(False)
        if ob.type == "MESH" and ob.data.color_attributes:
            ob.data.color_attributes.active_color = ob.data.color_attributes[0]
    # only the Map Builder tab in the sidebar, so it is the one shown
    for cls in list(bpy.types.Panel.__subclasses__()):
        if (getattr(cls, "bl_space_type", "") == "VIEW_3D" and getattr(cls, "bl_region_type", "") == "UI"
                and getattr(cls, "bl_category", "") not in ("Map Builder", "")):
            try:
                bpy.utils.unregister_class(cls)
            except Exception:  # noqa: BLE001 - a panel that cannot be removed just stays
                pass
    win, area = view3d()
    space = area.spaces[0]
    space.show_region_ui = True
    space.shading.type = "SOLID"
    space.shading.color_type = "VERTEX"
    space.clip_end = 5000
    r3d = space.region_3d
    r3d.view_perspective = "PERSP"
    r3d.view_location = (0, 0, 10)
    r3d.view_distance = max(ARGS.width, ARGS.height) * 1.3
    r3d.view_rotation = Euler((math.radians(55), 0, math.radians(30)), "XYZ").to_quaternion()
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.screen.screen_full_area()
    win.cursor_warp(win.width - 5, 5)


def tick():
    state["ticks"] += 1
    if state["ticks"] == 1:
        setup()
        return 0.5
    if state["ticks"] == 2:
        win, area = view3d()
        ui = next(r for r in area.regions if r.type == "UI")
        x, y = ui.x + ui.width - 13, ui.y + ui.height - 90
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
        win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
        win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=win.width // 2, y=win.height // 2)
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()
    if state["ticks"] < 7:
        return 0.5
    win, area = view3d()
    try:
        with bpy.context.temp_override(window=win, area=area):
            bpy.ops.screen.screenshot(filepath=ARGS.out, check_existing=False)
    except Exception as e:  # noqa: BLE001 - reported, then exit non-zero
        print("screenshot failed:", e)
    ok = os.path.isfile(ARGS.out)
    print("PANEL_OK" if ok else "PANEL_FAILED")
    sys.stdout.flush()
    os._exit(0 if ok else 1)


bpy.app.timers.register(tick, first_interval=1.0)
