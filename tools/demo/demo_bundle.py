"""Pure-Python parts of the demo kit (no Blender, no network): presets, package reading, probe results,
the static three.js viewer bundle, its zip and summary.md. Imported by run_demo.py and by the unit test."""

import json
import math
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from map_builder.core.collision import read_collision  # noqa: E402
from map_builder.core.package import package_id_of  # noqa: E402
from map_builder.core.query import capsule_hits  # noqa: E402

PRESET_DIR = os.path.join(HERE, "presets")
VIEWER_SRC = os.path.join(HERE, "viewer")
MAX_CAMERAS = 6
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
RENDER_SIZE = (1280, 720)
SAMPLES = 64
VIEWER_FILES = ("index.html", "viewer.js", "map.glb", "probes.json", "NOTICES.txt")


class DemoError(ValueError):
    pass


def _vec3(v, what):
    if (not isinstance(v, (list, tuple)) or len(v) != 3
            or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v)):
        raise DemoError(f"{what} must be three finite numbers")
    return [float(x) for x in v]


def validate_preset(p):
    if not isinstance(p, dict):
        raise DemoError("preset must be a JSON object")
    name = p.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise DemoError("preset name must match [a-z0-9][a-z0-9-]*")
    area = p.get("area")
    if not isinstance(area, dict):
        raise DemoError("preset area is required")
    for k, lo, hi in (("lat", -90, 90), ("lon", -180, 180), ("width_m", 1, 20000), ("height_m", 1, 20000)):
        v = area.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
            raise DemoError(f"area.{k} must be a number in [{lo}, {hi}]")
    cams = p.get("cameras")
    if not isinstance(cams, list) or not 1 <= len(cams) <= MAX_CAMERAS:
        raise DemoError(f"cameras must list 1..{MAX_CAMERAS} entries")
    seen = set()
    for c in cams:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not NAME_RE.fullmatch(c["name"]):
            raise DemoError("camera name must match [a-z0-9][a-z0-9-]*")
        if c["name"] in seen:
            raise DemoError(f"duplicate camera {c['name']}")
        seen.add(c["name"])
        _vec3(c.get("eye"), f"camera {c['name']} eye")
        _vec3(c.get("target"), f"camera {c['name']} target")
        lens = c.get("lens_mm", 35)
        if not isinstance(lens, (int, float)) or isinstance(lens, bool) or not 8 <= lens <= 300:
            raise DemoError(f"camera {c['name']} lens_mm must be in [8, 300]")
    return p


def load_preset(name_or_path):
    path = name_or_path if name_or_path.lower().endswith(".json") else os.path.join(PRESET_DIR, name_or_path + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            p = json.load(f)
    except OSError as e:
        raise DemoError(f"cannot read preset {name_or_path}: {e}")
    return validate_preset(p)


def read_package(path):
    """{'manifest', 'glb', 'collision', 'notices'} of a .mbmap (a zip); members are read by manifest path."""
    with zipfile.ZipFile(path) as z:
        raw = z.read("manifest.json")
        m = json.loads(raw.decode("utf-8"))
        return {"manifest": m, "package_id": package_id_of(raw), "glb": z.read(m["visual"]["path"]),
                "collision": z.read(m["collision"]["path"]),
                "notices": z.read(m.get("notices", "NOTICES.txt")).decode("utf-8")}


def probe_results(pkg):
    """Passage probes with a PASS/BLOCKED result against the package collision (same query as the validator)."""
    col = read_collision(pkg["collision"])
    out = []
    for p in pkg["manifest"].get("passage_probes", []):
        hits = capsule_hits(col, p["path_map"], p["radius_m"])
        out.append({"id": p["id"], "kind": p["kind"], "feature": p["feature"], "radius_m": p["radius_m"],
                    "path_map": p["path_map"],
                    # map (x, y, z) -> glTF/three (x, z, -y)
                    "path_gltf": [[x, z, -y] for x, y, z in p["path_map"]],
                    "result": "BLOCKED" if hits else "PASS",
                    "blocked_by": [col.objects[k]["name"] for k in hits[:5]]})
    return out


def probes_json(pkg):
    m = pkg["manifest"]
    return {"package_id": pkg["package_id"], "name": m.get("name"), "area": m.get("area"),
            "passage_probes": probe_results(pkg)}


def write_viewer(out_dir, pkg):
    """out_dir/viewer/ (+ viewer.zip): static three.js page, map.glb, probes.json, NOTICES.txt, vendor/.
    The zip listing is deterministic (sorted names, fixed timestamps)."""
    vdir = os.path.join(out_dir, "viewer")
    if os.path.isdir(vdir):
        shutil.rmtree(vdir)
    shutil.copytree(VIEWER_SRC, vdir)
    with open(os.path.join(vdir, "map.glb"), "wb") as f:
        f.write(pkg["glb"])
    with open(os.path.join(vdir, "probes.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(probes_json(pkg), f, indent=1, sort_keys=True)
        f.write("\n")
    with open(os.path.join(vdir, "NOTICES.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(pkg["notices"])
    zpath = os.path.join(out_dir, "viewer.zip")
    names = sorted(os.path.relpath(os.path.join(r, n), vdir).replace(os.sep, "/")
                   for r, _, files in os.walk(vdir) for n in files)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            zi = zipfile.ZipInfo("viewer/" + n, (2020, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(vdir, n), "rb") as f:
                z.writestr(zi, f.read())
    return zpath


def zip_listing(zpath):
    with zipfile.ZipFile(zpath) as z:
        return sorted(z.namelist())


def render_names(preset, with_before):
    names = []
    for c in preset["cameras"]:
        names.append(f"render-{c['name']}-after.png")
        if with_before:
            names.append(f"render-{c['name']}-before.png")
    return names


def summary_md(preset, pkg, probes, renders, panel_note, before_pkg=None):
    m = pkg["manifest"]
    lines = [f"# Demo summary: {preset['name']}", "",
             f"* package: `{m.get('name')}`, id `{pkg.get('package_id')}`, format {m.get('schema_version')}",
             f"* objects: {len(m.get('objects', []))}, collision triangles: "
             f"{m.get('collision', {}).get('triangle_count')}, orientation probes: "
             f"{len(m.get('orientation_probes', []))}, passage probes: {len(probes)}"]
    if before_pkg is not None:
        b = before_pkg["manifest"]
        lines.append(f"* before: id `{before_pkg.get('package_id')}`, objects: {len(b.get('objects', []))}, "
                     f"passage probes: {len(b.get('passage_probes', []))}")
    lines += ["", "## Images", ""]
    lines += [f"* `{r}`" for r in renders]
    lines += [f"* {panel_note}", "", "## Passage probes", ""]
    if probes:
        lines += ["| id | kind | feature | radius m | result |", "|---|---|---|---|---|"]
        lines += [f"| {p['id']} | {p['kind']} | {p['feature']} | {p['radius_m']} | {p['result']} |" for p in probes]
    else:
        lines.append("none in this package")
    lines += ["", "## Viewer", "",
              "`viewer/` (also `viewer.zip`): `py -3 -m http.server 8780 --directory viewer`, then open "
              "http://localhost:8780/", "", "Attribution: see `viewer/NOTICES.txt`.", ""]
    return "\n".join(lines)
