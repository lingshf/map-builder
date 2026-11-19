"""Map package (``.mbmap``): manifest, hashing, atomic write and validation.

The authoritative contract is docs/PACKAGE_FORMAT.md. A package is a ZIP archive::

    manifest.json                 versioned contract
    visual/map.glb                glTF 2.0 binary, presentation only
    collision/map.mbcol           authoritative static collision (map frame)
    collision/terrain.mbhf        derived terrain height grid (optional)
    NOTICES.txt                   attribution / licence notices
    report.json                   generation + export diagnostics (optional)

``package_id`` = "sha256:" + SHA-256 of the exact ``manifest.json`` bytes stored in the
archive. It binds the payload only after every member has been verified against ``files[]``.
"""

import copy
import hashlib
import json
import math
import os
import re
import stat
import tempfile
import time
import zipfile
import zlib

from . import (COLLISION_FORMAT_VERSION, GENERATOR_NAME, GENERATOR_VERSION, HEIGHTFIELD_FORMAT_VERSION,
               PACKAGE_SCHEMA, PACKAGE_SCHEMA_VERSION)
from .collision import (CLASSES, DEGENERATE_EPS, degenerate_triangle_count, is_degenerate, rasterize_heightfield,
                        read_collision, read_heightfield, strict_json)
from .errors import PackageError
from .geodesy import gltf_to_map, map_to_gltf, map_to_unity_x_negated
from .glb import read_glb

PACKAGE_EXTENSION = ".mbmap"
MANIFEST = "manifest.json"
MAX_ENTRIES = 64
MAX_TOTAL_UNCOMPRESSED = 1536 * 1024 * 1024
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_RATIO = 200
MAX_NAME_LEN = 255

# path -> (role, media_type, required)
MEMBERS = {
    "visual/map.glb": ("visual", "model/gltf-binary", True),
    "collision/map.mbcol": ("collision", "application/vnd.map-builder.mbcol", True),
    "NOTICES.txt": ("notices", "text/plain; charset=utf-8", True),
    "report.json": ("report", "application/json", False),
    "collision/terrain.mbhf": ("heightfield", "application/vnd.map-builder.mbhf", False),
}
ROLE_PATHS = {v[0]: k for k, v in MEMBERS.items()}

HORIZONTAL_DATUM = "WGS84 (EPSG:4326)"
HEIGHT_FORMULA = "H = z + z_offset_m"
PROJECTION = ("local tangent plane at the origin: x, y = east, north components of ECEF->ENU of the point "
              "on the WGS84 ellipsoid (h = 0); no scale factor, no earth-curvature correction")
MAP_FROM_GLTF = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
MAP_FROM_UNITY = [[-1, 0, 0], [0, 0, -1], [0, 1, 0]]
AXES = {
    "map": "right-handed; +X east, +Y north, +Z up; metres",
    "gltf": "gltf = (x, z, -y): +X east, +Y up, +Z south; proper rotation, winding preserved",
    "unity_x_negated": ("unity = (-x, z, -y): +X west, +Y up, +Z south (glTF importer negating X); a "
                        "reflection, so triangle index order is reversed; verify with orientation_probes"),
    "map_from_gltf": MAP_FROM_GLTF,
    "map_from_unity": MAP_FROM_UNITY,
}
REPORT_KEYS = ("counts", "unsupported_features", "invalid_features", "warnings")
EDIT_KEYS = ("duplicated", "user_added", "removed")
PROBES_UNAVAILABLE = "orientation probes unavailable"

# binding / probe tolerances (docs/PACKAGE_FORMAT.md)
AABB_TOL_M = 0.01
AABB_TOL_REL = 1e-5
WINDING_TOL_M = 0.005
WINDING_MIN_MATCHED = 0.99
WINDING_TIE_M = 1e-9
MAX_WINDING_CANDIDATES = 32
PROBE_MIN_ABS_XY_M = 1.0
PROBE_MIRROR_CLEARANCE_M = 0.5
PROBE_MIN_NORMAL_XZ = 0.05
PROBE_MATCH_M = 0.05
PROBE_MIN_DOT = 0.99
PROBE_MAX = 3
HEIGHTFIELD_TOL_M = 1e-3

_MB_ID = re.compile(r"(osm:(node|way|relation)/\d+|terrain:grid|scatter:.+#\d+)")
_SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z")
_SECRET = re.compile(r"(?i)([?&;](api[_-]?key|key|token|access[_-]?token|auth|password|passwd|secret|signature|sig"
                     r"|x-amz-[a-z-]+)=)|(://[^/\s@]*@)|(\bbearer\s+[a-z0-9._~+/-]{8,})")


def manifest_bytes(manifest):
    return json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")


def package_id_of(manifest_data):
    """Package identity from the raw manifest.json bytes."""
    return "sha256:" + hashlib.sha256(manifest_data).hexdigest()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_member_name(name):
    """Relative POSIX path: no absolute path, ``..``, backslash, drive letter, empty or ``.`` segment."""
    if not isinstance(name, str) or not name or len(name) > MAX_NAME_LEN:
        return False
    if "\\" in name or ":" in name or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in name):
        return False
    if name.startswith("/"):
        return False
    return all(part not in ("", ".", "..") for part in name.split("/"))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec(v, n=3):
    return isinstance(v, list) and len(v) == n and all(_num(c) for c in v)


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _cross(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


def _unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return None if n == 0 else (v[0] / n, v[1] / n, v[2] / n)


def find_secrets(obj, path="$"):
    """Paths of string values that look like credentials (URL userinfo, key/token query parameters)."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            hits += find_secrets(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            hits += find_secrets(v, f"{path}[{i}]")
    elif isinstance(obj, str) and _SECRET.search(obj):
        hits.append(path)
    return hits


# --- manifest ------------------------------------------------------------------

def build_manifest(name, area, sources, vertical_datum, files, collision_info, heightfield_info, objects,
                   probes, edits_counts, warnings_count, has_report=True, blender_version=None, created_utc=None):
    frame = area.frame
    return {
        "schema": PACKAGE_SCHEMA,
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "name": name,
        "created_utc": created_utc or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION, "blender": blender_version},
        "georeference": {
            "origin": {"lat_deg": frame.lat0, "lon_deg": frame.lon0},
            "horizontal_datum": HORIZONTAL_DATUM,
            "projection": PROJECTION,
            "vertical_datum": vertical_datum,
            "z_offset_m": frame.z_offset,
            "height_formula": HEIGHT_FORMULA,
            "units": "metre",
        },
        "area": area.to_dict(),
        "axes": copy.deepcopy(AXES),
        "files": files,
        "visual": {"path": "visual/map.glb", "format": "glTF 2.0 binary",
                   "role": "presentation only; visual LOD/simplification must never alter collision"},
        "collision": collision_info,
        "heightfield": heightfield_info,
        "objects": objects,
        "orientation_probes": probes,
        "sources": sources,
        "edits": edits_counts,
        "notices": "NOTICES.txt",
        "report": "report.json" if has_report else None,
        "warnings_count": warnings_count,
    }


def notices_text(sources):
    lines = ["Map package data notices", "========================", "",
             "This package contains visual and collision geometry derived from the sources below.",
             "Procedural details (materials, inferred heights/roofs, scattered vegetation) are generated",
             "by map-builder and are not measurements. See report.json and manifest objects[].provenance.", ""]
    for s in sources:
        lic = s.get("license", {})
        lines.append(f"- {s.get('product', s.get('provider'))}")
        if s.get("attribution"):
            lines.append(f"  Attribution: {s['attribution']}")
        if lic:
            lines.append(f"  Licence: {lic.get('name', lic.get('id'))} {lic.get('url', '')}".rstrip())
        if s.get("notes"):
            lines.append(f"  Notes: {s['notes']}")
    lines.append("")
    if any(s.get("license", {}).get("id") == "ODbL-1.0" for s in sources):
        lines += [
            "OpenStreetMap / ODbL: the geometry in this package is a Produced Work derived from the",
            "OpenStreetMap database. Credit '(c) OpenStreetMap contributors' visibly wherever the map is",
            "shown (e.g. credits screen). If you publicly distribute a Derivative Database (e.g. the",
            "extracted feature data, not merely this rendered/collision geometry) ODbL share-alike applies",
            "to that database. ODbL does not require your game/application code to be open source.",
            "This notice is not legal advice.",
        ]
    return "\n".join(lines) + "\n"


# --- orientation probes --------------------------------------------------------------

def _cell(p, s):
    return (math.floor(p[0] / s), math.floor(p[1] / s), math.floor(p[2] / s))


def _near(grid, p, s, radius):
    cx, cy, cz = _cell(p, s)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for q in grid.get((cx + dx, cy + dy, cz + dz), ()):
                    if _dist(p, q) <= radius:
                        return True
    return False


def _object_vertex_grid(col, entry):
    s, c = entry["tri_start"], entry["tri_count"]
    grid = {}
    for vi in set(col.indices[3 * s:3 * (s + c)]):
        p = col.vertices[vi]
        grid.setdefault(_cell(p, PROBE_MIRROR_CLEARANCE_M), []).append(p)
    return grid


def node_probe(col, entry):
    """First qualifying (vertex, triangle) of a collision object in triangle order, or None."""
    grid = None
    s = entry["tri_start"]
    for t in range(s, s + entry["tri_count"]):
        tri = col.triangle(t)
        if is_degenerate(*tri):
            continue
        n = _unit(_cross(*tri))
        if n is None or (abs(n[0]) < PROBE_MIN_NORMAL_XZ and abs(n[2]) < PROBE_MIN_NORMAL_XZ):
            continue
        for k in range(3):
            p = tri[k]
            if abs(p[0]) < PROBE_MIN_ABS_XY_M or abs(p[1]) < PROBE_MIN_ABS_XY_M:
                continue
            if grid is None:
                grid = _object_vertex_grid(col, entry)
            if _near(grid, (-p[0], p[1], p[2]), PROBE_MIRROR_CLEARANCE_M, PROBE_MIRROR_CLEARANCE_M):
                continue
            rot = tri[k:] + tri[:k]
            return {"node": entry["name"],
                    "point_map": list(p),
                    "point_gltf": list(map_to_gltf(p)),
                    "point_unity_x_negated": list(map_to_unity_x_negated(p)),
                    "triangle_map": [list(q) for q in rot],
                    "normal_map": list(n),
                    "normal_unity_x_negated": list(map_to_unity_x_negated(n))}
    return None


def select_orientation_probes(col, max_probes=PROBE_MAX):
    """Up to three probes, one per node: non-terrain nodes first (table order), then terrain."""
    order = ([e for e in col.objects if e["class"] != "terrain"] + [e for e in col.objects if e["class"] == "terrain"])
    probes = []
    for e in order:
        if len(probes) >= max_probes:
            break
        p = node_probe(col, e)
        if p is not None:
            probes.append(p)
    return probes


def unity_import(gltf_triangles):
    """Simulate a glTF importer that negates X (glTFast/UnityGLTF): positions (-x, y, z) and reversed index
    order. Returns Unity-space triangles in imported index order."""
    out = []
    for a, b, c in gltf_triangles:
        ua, ub, uc = ((-p[0], p[1], p[2]) for p in (a, b, c))
        out.append((ua, uc, ub))
    return out


def verify_probe_in_unity(probe, unity_triangles, tol=PROBE_MATCH_M):
    """The consumer-side probe check of docs/PACKAGE_FORMAT.md against Unity-space triangles (imported
    index order). Returns None if it passes, otherwise the reason."""
    pu = probe["point_unity_x_negated"]
    if not any(_dist(pu, q) <= tol for t in unity_triangles for q in t):
        return "no vertex of the node within 5 cm of point_unity_x_negated"
    want = [map_to_unity_x_negated(q) for q in probe["triangle_map"]]
    nu = probe["normal_unity_x_negated"]
    found = False
    for t in unity_triangles:
        if all(any(_dist(w, q) <= tol for q in t) for w in want) and all(any(_dist(w, q) <= tol for w in want)
                                                                          for q in t):
            found = True
            n = _unit(_cross(*t))  # Unity Vector3.Cross(b - a, c - a), imported index order
            if n is not None and n[0] * nu[0] + n[1] * nu[1] + n[2] * nu[2] > PROBE_MIN_DOT:
                return None
    if not found:
        return "no imported triangle matches triangle_map within 5 cm"
    return "imported triangle front face does not match normal_unity_x_negated (winding or handedness wrong)"


# --- per-triangle winding match ------------------------------------------------------------

def match_winding(collision_triangles, visual_triangles, tol=WINDING_TOL_M, max_candidates=MAX_WINDING_CANDIDATES):
    """Match each non-degenerate collision triangle to visual triangles (same frame) whose three vertices
    are each within ``tol``. Bounded: visual triangles are hashed by centroid in cells of 2*tol, so each
    query visits at most 8 cells, and at most ``max_candidates`` candidates are compared (more counts as
    ambiguous)."""
    cs = 2.0 * tol
    grid = {}
    for v in visual_triangles:
        c = ((v[0][0] + v[1][0] + v[2][0]) / 3, (v[0][1] + v[1][1] + v[2][1]) / 3, (v[0][2] + v[1][2] + v[2][2]) / 3)
        grid.setdefault(_cell(c, cs), []).append(v)
    st = {"considered": 0, "degenerate": 0, "same": 0, "reversed": 0, "ambiguous": 0, "unmatched": 0,
          "comparisons": 0, "reversed_examples": []}
    for tri in collision_triangles:
        if is_degenerate(*tri, DEGENERATE_EPS):
            st["degenerate"] += 1
            continue
        st["considered"] += 1
        a, b, c = tri
        cen = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3, (a[2] + b[2] + c[2]) / 3)
        lo = _cell((cen[0] - tol, cen[1] - tol, cen[2] - tol), cs)
        hi = _cell((cen[0] + tol, cen[1] + tol, cen[2] + tol), cs)
        best_same = best_rev = math.inf
        n = 0
        overflow = False
        for ix in range(lo[0], hi[0] + 1):
            for iy in range(lo[1], hi[1] + 1):
                for iz in range(lo[2], hi[2] + 1):
                    for v in grid.get((ix, iy, iz), ()):
                        n += 1
                        if n > max_candidates:
                            overflow = True
                            break
                        st["comparisons"] += 1
                        d = [[_dist(tri[i], v[j]) for j in range(3)] for i in range(3)]
                        for k in range(3):
                            same = (d[0][k], d[1][(k + 1) % 3], d[2][(k + 2) % 3])
                            rev = (d[0][k], d[1][(k - 1) % 3], d[2][(k - 2) % 3])
                            if max(same) <= tol:
                                best_same = min(best_same, sum(same))
                            if max(rev) <= tol:
                                best_rev = min(best_rev, sum(rev))
        if overflow:
            st["ambiguous"] += 1
        elif best_same == math.inf and best_rev == math.inf:
            st["unmatched"] += 1
        elif abs(best_same - best_rev) <= WINDING_TIE_M:
            st["ambiguous"] += 1
        elif best_rev < best_same:
            st["reversed"] += 1
            if len(st["reversed_examples"]) < 3:
                st["reversed_examples"].append([list(p) for p in tri])
        else:
            st["same"] += 1
    return st


# --- writing --------------------------------------------------------------------------

def _zinfo(name):
    zi = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))  # deterministic archive
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = (stat.S_IFREG | 0o644) << 16
    return zi


def write_package(path, members, manifest):
    """Atomically write and validate a package. The archive is written to a temporary file next to
    ``path``, fsynced, validated, and only then moved over ``path`` with ``os.replace``; on any failure the
    temporary file is removed and a previous export at ``path`` is left untouched."""
    path = os.path.abspath(path)
    if not path.lower().endswith(PACKAGE_EXTENSION):
        raise PackageError(f"package path must end with {PACKAGE_EXTENSION}")
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".mbmap-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            with zipfile.ZipFile(fh, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                z.writestr(_zinfo(MANIFEST), manifest_bytes(manifest))
                for name in sorted(members):
                    z.writestr(_zinfo(name), members[name])
            fh.flush()
            os.fsync(fh.fileno())
        result = validate_package(tmp)
        if result.errors:
            raise PackageError("package failed validation; previous export kept:\n- " + "\n- ".join(result.errors))
        os.replace(tmp, path)
        return result
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def file_entry(path, data):
    role, media_type, _ = MEMBERS[path]
    return {"path": path, "role": role, "media_type": media_type, "sha256": sha256(data), "bytes": len(data)}


def assemble(name, area, sources, glb_bytes, collision_bytes, objects, heightfield=None, report=None,
             edits=None, blender_version=None, created_utc=None):
    """Members + manifest for :func:`write_package`.

    ``objects``: manifest object entries ({name, mb_id, class, collision, provenance}).
    ``heightfield``: (mbhf bytes, info dict) or None. ``report``: dict (plan report + diagnostics).
    ``edits``: {"duplicated": [...], "user_added": [...], "removed": [...]} lists (report.json);
    the manifest stores their counts. Returns (members, manifest, probes).
    """
    elevation = [s for s in sources if s.get("kind") == "elevation"]
    if not elevation or not elevation[0].get("vertical_datum"):
        raise PackageError("no elevation source with a vertical datum; refusing to write a package whose "
                           "heights are not georeferenced")
    col = read_collision(collision_bytes)
    probes = select_orientation_probes(col)
    report = dict(report or {})
    for k in REPORT_KEYS:
        report.setdefault(k, {} if k == "counts" else [])
    report["warnings"] = list(report["warnings"])
    if not probes and PROBES_UNAVAILABLE not in report["warnings"]:
        report["warnings"].append(PROBES_UNAVAILABLE)
    report["export"] = dict(report.get("export") or {}, orientation_probes=len(probes))
    edits = {k: list((edits or {}).get(k, [])) for k in EDIT_KEYS}
    report["edits"] = edits
    secrets = find_secrets({"sources": sources, "report": report, "objects": objects, "name": name})
    if secrets:
        raise PackageError(f"refusing to write credential-like values into the package: {secrets[:5]}")
    try:
        report_bytes = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False,
                                  allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as e:
        raise PackageError(f"report is not finite JSON: {e}") from None
    members = {"visual/map.glb": glb_bytes, "collision/map.mbcol": collision_bytes,
               "NOTICES.txt": notices_text(sources).encode("utf-8"), "report.json": report_bytes}
    hf_info = None
    if heightfield is not None:
        hf_bytes, hf_meta = heightfield
        members["collision/terrain.mbhf"] = hf_bytes
        hf_info = dict(hf_meta, path="collision/terrain.mbhf", format="mbhf", version=HEIGHTFIELD_FORMAT_VERSION,
                       authority="derived from the final terrain-class collision triangles; triangles are "
                                 "authoritative")
    files = [file_entry(p, members[p]) for p in sorted(members)]
    collision_info = {"path": "collision/map.mbcol", "format": "mbcol", "version": COLLISION_FORMAT_VERSION,
                      "frame": "map", "winding": "ccw_outward", "triangle_count": col.triangle_count,
                      "vertex_count": len(col.vertices),
                      "bounds_min": list(col.bounds[0]), "bounds_max": list(col.bounds[1]),
                      "classes": dict(CLASSES),
                      "authority": "authoritative static collision; exported from the same final meshes and "
                                   "world transforms as visual/map.glb"}
    manifest = build_manifest(name, area, sources, elevation[0]["vertical_datum"], files, collision_info, hf_info,
                              objects, probes, {k: len(v) for k, v in edits.items()}, len(report["warnings"]),
                              blender_version=blender_version, created_utc=created_utc)
    return members, manifest, probes


# --- validation ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.manifest = None
        self.package_id = None
        self.collision = None
        self.winding = {}

    @property
    def ok(self):
        return not self.errors

    def summary(self):
        s = "VALID" if self.ok else "INVALID"
        lines = [f"{s}: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"]
        if self.package_id and self.ok:
            lines.append(f"package_id {self.package_id}")
        lines += [f"ERROR: {e}" for e in self.errors]
        lines += [f"warning: {w}" for w in self.warnings]
        return "\n".join(lines)


_ZIP_ERRORS = (zipfile.BadZipFile, zlib.error, EOFError, OSError, ValueError, RuntimeError, NotImplementedError,
               OverflowError, MemoryError)


def validate_package(path):
    """Validate a package file; never raises for malformed input (errors are collected)."""
    r = ValidationResult()
    try:
        with zipfile.ZipFile(path, "r") as z:
            _validate_zip(z, r)
    except _ZIP_ERRORS as e:
        r.errors.append(f"not a readable package: {type(e).__name__}: {e}")
    except PackageError as e:
        r.errors.append(str(e))
    return r


def _validate_zip(z, r):
    infos = z.infolist()
    if len(infos) > MAX_ENTRIES:
        r.errors.append(f"too many entries ({len(infos)} > {MAX_ENTRIES})")
        return
    names, lowered = {}, set()
    total = 0
    for zi in infos:
        raw = zi.orig_filename
        if not safe_member_name(raw) or raw != zi.filename:
            r.errors.append(f"unsafe entry name {raw!r}")
        if raw.lower() in lowered:
            r.errors.append(f"duplicate entry {raw!r}")
        lowered.add(raw.lower())
        names[raw] = zi
        mode = (zi.external_attr >> 16) & 0o170000
        if zi.is_dir() or (mode and mode != stat.S_IFREG):
            r.errors.append(f"entry {raw!r} is not a regular file (directory or symlink)")
        if zi.flag_bits & 0x1:
            r.errors.append(f"entry {raw!r} is encrypted")
        if zi.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            r.errors.append(f"entry {raw!r} uses unsupported compression {zi.compress_type}")
        total += zi.file_size
        if zi.file_size and (zi.compress_size == 0 or zi.file_size / zi.compress_size > MAX_RATIO):
            r.errors.append(f"entry {raw!r} compression ratio exceeds {MAX_RATIO}")
    if total > MAX_TOTAL_UNCOMPRESSED:
        r.errors.append(f"uncompressed size {total} exceeds {MAX_TOTAL_UNCOMPRESSED} bytes")
    if r.errors:
        return
    if MANIFEST not in names:
        r.errors.append("manifest.json missing")
        return
    if names[MANIFEST].file_size > MAX_MANIFEST_BYTES:
        r.errors.append(f"manifest.json exceeds {MAX_MANIFEST_BYTES} bytes")
        return

    def read(name):
        zi = names[name]
        with z.open(zi) as f:
            data = f.read(zi.file_size + 1)
        if len(data) != zi.file_size:
            raise PackageError(f"{name}: uncompressed size differs from its zip header")
        return data

    raw = read(MANIFEST)
    try:
        m = strict_json(raw, "manifest.json")
    except PackageError as e:
        r.errors.append(str(e))
        return
    if not isinstance(m, dict):
        r.errors.append("manifest.json must be a JSON object")
        return
    r.manifest = m
    if not _check_version(m, r):
        return
    r.package_id = package_id_of(raw)
    _check_manifest(m, r)
    if r.errors:
        return
    # files[] <-> archive members, one-to-one, then sizes and hashes
    listed = {f["path"]: f for f in m["files"]}
    members = set(names) - {MANIFEST}
    for p in sorted(members - set(listed)):
        r.errors.append(f"unlisted file in package: {p}")
    for p in sorted(set(listed) - members):
        r.errors.append(f"listed file missing from package: {p}")
    if r.errors:
        return
    blobs = {}
    for p, f in listed.items():
        if f["bytes"] != names[p].file_size:
            r.errors.append(f"{p}: size {names[p].file_size} != manifest bytes {f['bytes']}")
            continue
        data = read(p)
        if f["sha256"] != sha256(data):
            r.errors.append(f"{p}: SHA-256 mismatch")
            continue
        blobs[f["role"]] = data
    if r.errors:
        return
    _validate_payloads(m, blobs, r)


def _check_version(m, r):
    if m.get("schema") != PACKAGE_SCHEMA:
        r.errors.append(f"manifest: schema is {m.get('schema')!r}, expected {PACKAGE_SCHEMA!r}")
        return False
    v = m.get("schema_version")
    mt = _SEMVER.fullmatch(v) if isinstance(v, str) else None
    if not mt:
        r.errors.append(f"manifest: schema_version {v!r} is not MAJOR.MINOR.PATCH")
        return False
    if mt.group(1) != PACKAGE_SCHEMA_VERSION.split(".")[0]:
        r.errors.append(f"manifest: unsupported schema major version {v}")
        return False
    return True


def _check_manifest(m, r):
    err = r.errors.append

    def need(cond, msg):
        if not cond:
            err("manifest: " + msg)
        return cond

    need(isinstance(m.get("name"), str) and m["name"], "name must be a non-empty string")
    need(isinstance(m.get("created_utc"), str) and _UTC.fullmatch(m["created_utc"]),
         "created_utc must be an ISO-8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    g = m.get("generator")
    need(isinstance(g, dict) and isinstance(g.get("name"), str) and isinstance(g.get("version"), str)
         and (g.get("blender") is None or isinstance(g.get("blender"), str)),
         "generator must be {name, version, blender: string|null}")
    geo = m.get("georeference")
    if need(isinstance(geo, dict), "georeference missing"):
        o = geo.get("origin")
        need(isinstance(o, dict) and _num(o.get("lat_deg")) and _num(o.get("lon_deg"))
             and -84 <= o["lat_deg"] <= 84 and -180 <= o["lon_deg"] <= 180, "georeference.origin invalid")
        need(geo.get("horizontal_datum") == HORIZONTAL_DATUM, f"georeference.horizontal_datum must be "
                                                              f"{HORIZONTAL_DATUM!r}")
        need(isinstance(geo.get("projection"), str) and geo["projection"], "georeference.projection missing")
        need(isinstance(geo.get("vertical_datum"), str) and geo["vertical_datum"],
             "georeference.vertical_datum missing")
        need(_num(geo.get("z_offset_m")), "georeference.z_offset_m must be a finite number")
        need(geo.get("height_formula") == HEIGHT_FORMULA, f"georeference.height_formula must be {HEIGHT_FORMULA!r}")
        need(geo.get("units") == "metre", "georeference.units must be 'metre'")
    a = m.get("area")
    if need(isinstance(a, dict), "area missing"):
        need(_num(a.get("width_m")) and a["width_m"] > 0 and _num(a.get("height_m")) and a["height_m"] > 0,
             "area.width_m/height_m must be positive")
        need(_vec(a.get("local_rect_m"), 4), "area.local_rect_m must be 4 numbers")
        bb = a.get("geographic_bbox_deg")
        need(isinstance(bb, dict) and all(_num(bb.get(k)) for k in ("south", "west", "north", "east")),
             "area.geographic_bbox_deg must have south/west/north/east")
    ax = m.get("axes")
    need(isinstance(ax, dict) and ax.get("map_from_gltf") == MAP_FROM_GLTF and ax.get("map_from_unity") == MAP_FROM_UNITY,
         f"axes.map_from_gltf must be {MAP_FROM_GLTF} and axes.map_from_unity {MAP_FROM_UNITY}")
    files = m.get("files")
    if need(isinstance(files, list), "files must be an array"):
        seen_paths, seen_roles = set(), set()
        for f in files:
            if not (isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("role"), str)
                    and isinstance(f.get("media_type"), str) and isinstance(f.get("sha256"), str)
                    and re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) and isinstance(f.get("bytes"), int)
                    and not isinstance(f["bytes"], bool) and f["bytes"] >= 0):
                err(f"manifest: malformed files[] entry {str(f)[:200]}")
                continue
            p = f["path"]
            if not safe_member_name(p) or p == MANIFEST:
                err(f"manifest: files[] path {p!r} is unsafe or the manifest itself")
                continue
            if p.lower() in seen_paths:
                err(f"manifest: files[] lists {p!r} twice")
            seen_paths.add(p.lower())
            if p in MEMBERS:
                role, media_type, _ = MEMBERS[p]
                if f["role"] != role:
                    err(f"manifest: {p} must have role {role!r}, not {f['role']!r}")
                elif f["media_type"] != media_type:
                    r.warnings.append(f"{p}: media_type {f['media_type']!r} (expected {media_type!r})")
                if role in seen_roles:
                    err(f"manifest: role {role!r} listed twice")
                seen_roles.add(role)
            else:
                if f["role"] in ROLE_PATHS:
                    err(f"manifest: role {f['role']!r} must use path {ROLE_PATHS[f['role']]!r}, not {p!r}")
                else:
                    r.warnings.append(f"unknown package member {p!r} (role {f['role']!r}) ignored")
        for p, (role, _, required) in MEMBERS.items():
            if required and role not in seen_roles:
                err(f"manifest: required member {p} (role {role!r}) not listed")
    vis = m.get("visual")
    need(isinstance(vis, dict) and vis.get("path") == "visual/map.glb", "visual.path must be 'visual/map.glb'")
    c = m.get("collision")
    if need(isinstance(c, dict), "collision missing"):
        expect = {"path": "collision/map.mbcol", "format": "mbcol", "version": COLLISION_FORMAT_VERSION,
                  "frame": "map", "winding": "ccw_outward", "classes": CLASSES}
        for k, v in expect.items():
            need(c.get(k) == v, f"collision.{k} must be {v!r}")
        need(isinstance(c.get("triangle_count"), int) and isinstance(c.get("vertex_count"), int),
             "collision.triangle_count/vertex_count missing")
        need(_vec(c.get("bounds_min")) and _vec(c.get("bounds_max")), "collision.bounds_min/max missing")
    hf = m.get("heightfield", None)
    if hf is not None and need(isinstance(hf, dict), "heightfield must be an object or null"):
        need(hf.get("path") == "collision/terrain.mbhf", "heightfield.path must be 'collision/terrain.mbhf'")
        need(all(isinstance(hf.get(k), int) for k in ("nx", "ny", "nan_cells"))
             and all(_num(hf.get(k)) for k in ("x0", "y0", "spacing_m")),
             "heightfield needs nx, ny, x0, y0, spacing_m, nan_cells")
    if isinstance(files, list):
        listed_hf = any(isinstance(f, dict) and f.get("role") == "heightfield" for f in files)
        need(listed_hf == (hf is not None), "heightfield must be non-null exactly when the heightfield member "
                                            "is listed")
        listed_report = any(isinstance(f, dict) and f.get("role") == "report" for f in files)
        need(m.get("report") == ("report.json" if listed_report else None),
             "report must be 'report.json' when report.json is listed, otherwise null")
    need(m.get("notices") == "NOTICES.txt", "notices must be 'NOTICES.txt'")
    objs = m.get("objects")
    if need(isinstance(objs, list) and objs, "objects must be a non-empty array"):
        for o in objs:
            if not (isinstance(o, dict) and isinstance(o.get("name"), str) and isinstance(o.get("mb_id"), str)
                    and o.get("class") in CLASSES and o.get("collision") is True
                    and isinstance(o.get("provenance"), dict)):
                err(f"manifest: malformed objects[] entry {str(o)[:200]}")
    need(isinstance(m.get("orientation_probes"), list) and len(m["orientation_probes"]) <= PROBE_MAX,
         f"orientation_probes must be an array of at most {PROBE_MAX}")
    srcs = m.get("sources")
    if need(isinstance(srcs, list) and srcs, "sources must be a non-empty array"):
        for s in srcs:
            if not (isinstance(s, dict) and s.get("kind") in ("elevation", "features")
                    and isinstance(s.get("provider"), str) and s["provider"]
                    and isinstance(s.get("license"), dict) and s["license"]
                    and isinstance(s.get("attribution"), str)):
                err("manifest: every source needs kind (elevation|features), provider, license {...} and "
                    "attribution")
                break
        else:
            if not any(s["kind"] == "elevation" for s in srcs):
                err("manifest: no elevation source (vertical datum provenance missing)")
    ed = m.get("edits")
    need(isinstance(ed, dict) and all(isinstance(ed.get(k), int) and not isinstance(ed.get(k), bool)
                                      and ed[k] >= 0 for k in EDIT_KEYS),
         "edits must be {duplicated, user_added, removed} counts")
    wc = m.get("warnings_count")
    need(isinstance(wc, int) and not isinstance(wc, bool) and wc >= 0, "warnings_count must be a count")
    secrets = find_secrets({k: m.get(k) for k in ("sources", "objects", "name", "generator")})
    if secrets:
        err(f"manifest: credential-like values at {secrets[:5]}")


def _aabb(points):
    xs, ys, zs = zip(*points)
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def _validate_payloads(m, blobs, r):
    try:
        col = read_collision(blobs["collision"])
    except PackageError as e:
        r.errors.append(str(e))
        return
    r.collision = col
    ci = m["collision"]
    if ci["triangle_count"] != col.triangle_count or ci["vertex_count"] != len(col.vertices):
        r.errors.append("collision: triangle/vertex counts differ from the manifest")
    if any(abs(a - b) > 1e-6 for a, b in zip(ci["bounds_min"] + ci["bounds_max"], col.bounds[0] + col.bounds[1])):
        r.errors.append("collision: bounds differ from the manifest")
    deg = degenerate_triangle_count(col)
    if deg:
        r.warnings.append(f"collision has {deg} degenerate (zero-area) triangles")
    if not any(c == CLASSES["terrain"] for c in col.tri_class):
        r.warnings.append("collision has no terrain-class triangles")
    _check_objects(m, col, r)
    try:
        _, nodes = read_glb(blobs["visual"])
    except PackageError as e:
        r.errors.append(str(e))
        return
    _check_binding(m, col, nodes, r)
    if "heightfield" in blobs:
        _check_heightfield(m["heightfield"], blobs["heightfield"], col, r)
    _check_notices(m, blobs["notices"], r)
    if "report" in blobs:
        _check_report(m, blobs["report"], r)


def _check_objects(m, col, r):
    man = {}
    for o in m["objects"]:
        if o["name"] in man:
            r.errors.append(f"manifest: object {o['name']!r} listed twice")
        man[o["name"]] = o
    ids = {}
    for o in m["objects"]:
        if o["mb_id"] in ids:
            r.errors.append(f"duplicate object identity {o['mb_id']!r} ({ids[o['mb_id']]!r} and {o['name']!r})")
        ids[o["mb_id"]] = o["name"]
        base = o["mb_id"].split("~", 1)[0]
        if "~" in o["mb_id"]:
            if o["mb_id"] != f"{base}~{o['name']}" or not _MB_ID.fullmatch(base):
                r.warnings.append(f"object {o['name']!r}: duplicate identity {o['mb_id']!r} is not "
                                  "'<generated id>~<object name>'")
        elif o["mb_id"].startswith("user:"):
            if o["mb_id"] != f"user:{o['name']}":
                r.warnings.append(f"object {o['name']!r}: user identity {o['mb_id']!r} is not 'user:<object name>'")
        elif not _MB_ID.fullmatch(o["mb_id"]):
            r.warnings.append(f"object {o['name']!r}: unrecognised mb_id form {o['mb_id']!r}")
    table = {e["name"]: e for e in col.objects}
    for name in sorted(set(table) - set(man)):
        r.errors.append(f"collision object {name!r} missing from manifest objects")
    for name in sorted(set(man) - set(table)):
        r.errors.append(f"manifest object {name!r} has no collision object")
    for name in set(man) & set(table):
        if man[name]["mb_id"] != table[name]["mb_id"] or man[name]["class"] != table[name]["class"]:
            r.errors.append(f"object {name!r}: mb_id/class differ between manifest and collision")


def _check_binding(m, col, nodes, r):
    by_name = {}
    for n in nodes:
        if n.triangles:
            if n.name in by_name:
                r.errors.append(f"glb: duplicate node name {n.name!r}")
            by_name[n.name] = n
    table = {e["name"]: e for e in col.objects}
    for name in sorted(set(by_name) - set(table)):
        r.errors.append(f"glTF node {name!r} has triangles but no collision object (visible but not collidable)")
    for e in col.objects:
        node = by_name.get(e["name"])
        if node is None:
            r.errors.append(f"collision object {e['name']!r} has no glTF node with triangles of the same name")
            continue
        vis = [tuple(gltf_to_map(p) for p in t) for t in node.triangles]
        ctris = col.object_triangles(e)
        va = _aabb([p for t in vis for p in t])
        ca = _aabb([p for t in ctris for p in t])
        size = max(ca[3] - ca[0], ca[4] - ca[1], ca[5] - ca[2])
        tol = AABB_TOL_M + AABB_TOL_REL * size
        if any(abs(x - y) > tol for x, y in zip(va, ca)):
            r.errors.append(f"visual/collision AABB mismatch for {e['name']!r}: glTF {[round(v, 3) for v in va]} vs "
                            f"collision {[round(v, 3) for v in ca]}")
            continue
        st = match_winding(ctris, vis)
        r.winding[e["name"]] = st
        if st["reversed"]:
            r.errors.append(f"visual/collision winding mismatch for {e['name']!r}: {st['reversed']} collision "
                            f"triangle(s) match visual triangles with reversed winding, e.g. "
                            f"{st['reversed_examples'][0]}")
        elif st["considered"] and st["same"] < WINDING_MIN_MATCHED * st["considered"]:
            r.warnings.append(f"{e['name']!r}: only {st['same']}/{st['considered']} collision triangles have an "
                              f"unambiguous visual match ({st['ambiguous']} ambiguous, {st['unmatched']} unmatched)")
    _check_probes(m, col, by_name, r)


def _check_probes(m, col, by_name, r):
    probes = m["orientation_probes"]
    expected = select_orientation_probes(col)
    if not probes:
        r.warnings.append(PROBES_UNAVAILABLE)
        if expected:
            r.errors.append(f"orientation_probes is empty although node {expected[0]['node']!r} has a qualifying "
                            "vertex")
        return
    if len(probes) != len(expected):
        r.errors.append(f"orientation_probes has {len(probes)} probe(s); {len(expected)} node(s) qualify (max "
                        f"{PROBE_MAX})")
    table = {e["name"]: e for e in col.objects}
    seen = set()
    n_non_terrain = 0
    for k, p in enumerate(probes):
        tag = f"orientation probe {k}"
        keys = ("node", "point_map", "point_gltf", "point_unity_x_negated", "triangle_map", "normal_map",
                "normal_unity_x_negated")
        if not (isinstance(p, dict) and all(key in p for key in keys) and isinstance(p["node"], str)
                and all(_vec(p[key]) for key in keys[1:] if key != "triangle_map")
                and isinstance(p["triangle_map"], list) and len(p["triangle_map"]) == 3
                and all(_vec(q) for q in p["triangle_map"])):
            r.errors.append(f"{tag}: needs {list(keys)} with 3-vectors")
            continue
        node, pm, nm = p["node"], p["point_map"], p["normal_map"]
        tag = f"orientation probe {node!r}"
        if node in seen:
            r.errors.append(f"{tag}: more than one probe for the node")
        seen.add(node)
        entry = table.get(node)
        if entry is None or node not in by_name:
            r.errors.append(f"{tag}: node does not exist in both glTF and collision")
            continue
        n_non_terrain += entry["class"] != "terrain"
        if (_dist(p["point_gltf"], map_to_gltf(pm)) > 1e-6
                or _dist(p["point_unity_x_negated"], map_to_unity_x_negated(pm)) > 1e-6
                or _dist(p["normal_unity_x_negated"], map_to_unity_x_negated(nm)) > 1e-6):
            r.errors.append(f"{tag}: point_gltf/point_unity_x_negated/normal_unity_x_negated are not the "
                            "documented mappings of point_map/normal_map")
            continue
        if abs(math.sqrt(sum(c * c for c in nm)) - 1.0) > 1e-4 or (abs(nm[0]) < PROBE_MIN_NORMAL_XZ
                                                                     and abs(nm[2]) < PROBE_MIN_NORMAL_XZ):
            r.errors.append(f"{tag}: normal_map must be a unit vector with |nx| >= 0.05 or |nz| >= 0.05")
            continue
        if abs(pm[0]) < PROBE_MIN_ABS_XY_M or abs(pm[1]) < PROBE_MIN_ABS_XY_M:
            r.errors.append(f"{tag}: point_map must have |x| >= 1 m and |y| >= 1 m")
            continue
        tri = [tuple(q) for q in p["triangle_map"]]
        if not any(_dist(pm, q) <= 1e-6 for q in tri):
            r.errors.append(f"{tag}: triangle_map does not contain point_map")
            continue
        n = _unit(_cross(*tri))
        if n is None or sum(a * b for a, b in zip(n, nm)) <= PROBE_MIN_DOT:
            r.errors.append(f"{tag}: normal_map is not the CCW front-face normal of triangle_map")
            continue
        # against the authoritative collision: the triangle is one of the node's, same cyclic order
        ok = False
        for ct in col.object_triangles(entry):
            for s in range(3):
                if all(_dist(tri[i], ct[(i + s) % 3]) <= 1e-6 for i in range(3)):
                    ok = True
        if not ok:
            r.errors.append(f"{tag}: triangle_map is not a collision triangle of the node (in CCW order)")
            continue
        if _near(_object_vertex_grid(col, entry), (-pm[0], pm[1], pm[2]), PROBE_MIRROR_CLEARANCE_M,
                 PROBE_MIRROR_CLEARANCE_M):
            r.errors.append(f"{tag}: the node has a vertex within 0.5 m of the X-mirror of point_map")
            continue
        # against the visual mesh, exactly as a consumer would after an X-negating import
        reason = verify_probe_in_unity(p, unity_import(by_name[node].triangles))
        if reason:
            r.errors.append(f"{tag} fails against the visual mesh: {reason}")
    if n_non_terrain != sum(1 for e in expected if table[e["node"]]["class"] != "terrain"):
        r.errors.append("orientation_probes must prefer non-terrain nodes that have a qualifying vertex")


def _check_heightfield(info, data, col, r):
    try:
        hf = read_heightfield(data)
    except PackageError as e:
        r.errors.append(str(e))
        return
    nan_cells = sum(1 for row in hf["z"] for v in row if math.isnan(v))
    if (info["nx"], info["ny"], info["nan_cells"]) != (hf["nx"], hf["ny"], nan_cells) or any(
            abs(info[a] - hf[b]) > 1e-9 for a, b in (("x0", "x0"), ("y0", "y0"), ("spacing_m", "spacing"))):
        r.errors.append("heightfield: manifest nx/ny/x0/y0/spacing_m/nan_cells differ from the file")
        return
    want = rasterize_heightfield(col.class_triangles("terrain"), hf["x0"], hf["y0"], hf["spacing"], hf["nx"],
                                 hf["ny"])
    for j in range(hf["ny"]):
        for i in range(hf["nx"]):
            a, b = hf["z"][j][i], want[j][i]
            if math.isnan(a) != math.isnan(b) or (not math.isnan(a) and abs(a - b) > HEIGHTFIELD_TOL_M):
                r.errors.append(f"heightfield: value at row {j}, column {i} is not the maximum z of the terrain "
                                f"collision triangles ({a} vs {b})")
                return


def _check_notices(m, data, r):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        r.errors.append("NOTICES.txt is not UTF-8")
        return
    for s in m["sources"]:
        if s["attribution"] and s["attribution"] not in text:
            r.errors.append(f"NOTICES.txt lacks the attribution of source {s['provider']!r}")
        elif not s["attribution"]:
            r.warnings.append(f"source {s['provider']!r} has no attribution text")


def _check_report(m, data, r):
    try:
        rep = strict_json(data, "report.json")
    except PackageError as e:
        r.errors.append(str(e))
        return
    if not isinstance(rep, dict) or not isinstance(rep.get("counts"), dict) or not all(
            isinstance(rep.get(k), list) for k in REPORT_KEYS[1:]):
        r.errors.append(f"report.json must be an object with {list(REPORT_KEYS)}")
        return
    if m["warnings_count"] != len(rep["warnings"]):
        r.errors.append(f"warnings_count {m['warnings_count']} != {len(rep['warnings'])} warnings in report.json")
    ed = rep.get("edits")
    if ed is not None:
        if not (isinstance(ed, dict) and all(isinstance(ed.get(k), list) for k in EDIT_KEYS)):
            r.errors.append("report.json edits must list duplicated, user_added and removed")
        elif any(len(ed[k]) != m["edits"][k] for k in EDIT_KEYS):
            r.errors.append("report.json edits lists do not match the manifest edits counts")
