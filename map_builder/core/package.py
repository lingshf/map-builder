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

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile
import time
import zipfile
import zlib
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from os import PathLike
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Required, TypedDict, TypeGuard, cast

from . import (COLLISION_FORMAT_VERSION, GENERATOR_NAME, GENERATOR_VERSION, HEIGHTFIELD_FORMAT_VERSION,
               PACKAGE_SCHEMA, PACKAGE_SCHEMA_VERSION)
from .collision import (CLASS_KINDS, CLASSES, DEGENERATE_EPS, KIND_SOLID, KIND_TUBE, MAX_ABS_COORD_M,
                        degenerate_triangle_count, is_degenerate, rasterize_heightfield, read_collision,
                        read_heightfield, strict_json)
from .errors import JsonValue, LimitError, PackageError
from .geodesy import gltf_to_map, map_to_gltf, map_to_unity_x_negated
from .glb import glb_image_sha256s, read_glb
from .query import capsule_hits

if TYPE_CHECKING:
    from .collision import Collision, CollisionEntry
    from .geodesy import Area
    from .glb import GlbNode

Vec3 = tuple[float, float, float]
Tri = tuple[Sequence[float], Sequence[float], Sequence[float]]
Cell = tuple[int, int, int]
Num = float | Fraction            # coordinates are floats, or exact Fractions for portal-cap centroids
class PassageProbe(TypedDict):
    id: str
    kind: Literal["bridge", "tunnel", "elevated"]
    feature: str
    path_map: list[list[float]]
    radius_m: float


class HeightfieldInfo(TypedDict):
    nx: int
    ny: int
    x0: float
    y0: float
    spacing_m: float
    nan_cells: int
    rule: str


# manifest ``objects[]`` entry (the key ``class`` is a keyword, hence the functional form)
ObjectEntry = TypedDict("ObjectEntry", {"name": str, "mb_id": str, "class": str, "collision": bool,
                                        "provenance": dict[str, object]})
class FileEntry(TypedDict):
    path: str
    role: str
    media_type: str
    sha256: str
    bytes: int


class OrientationProbe(TypedDict):
    node: str
    point_map: list[float]
    point_gltf: list[float]
    point_unity_x_negated: list[float]
    triangle_map: list[list[float]]
    normal_map: list[float]
    normal_unity_x_negated: list[float]


class GeneratorInfo(TypedDict):
    name: str
    version: str
    blender: str | None


class LicenseInfo(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str


class SourceEntry(TypedDict, total=False):
    kind: Required[str]
    provider: Required[str]
    license: Required[LicenseInfo]
    attribution: Required[str]
    product: str
    notes: str
    processing: str
    vertical_datum: str


class AssetNotice(TypedDict):
    name: str
    attribution: str
    license: LicenseInfo
    sha256: list[str]


class CollisionInfo(TypedDict):
    path: str
    format: str
    version: int
    frame: str
    winding: str
    triangle_count: int
    vertex_count: int
    bounds_min: list[float]
    bounds_max: list[float]
    classes: dict[str, int]
    class_kinds: dict[str, str | None]
    authority: str


class HeightfieldManifest(HeightfieldInfo):
    path: str
    format: str
    version: int
    authority: str


class Manifest(TypedDict):
    """The manifest of a package that passed ``_check_manifest`` (the checker validates the raw JSON, key by
    key, before any other code indexes it)."""
    schema: str
    schema_version: str
    name: str
    created_utc: str
    generator: GeneratorInfo
    georeference: dict[str, object]
    area: dict[str, object]
    axes: dict[str, object]
    files: Sequence[FileEntry]
    visual: dict[str, str]
    collision: CollisionInfo
    heightfield: HeightfieldManifest | None
    objects: Sequence[ObjectEntry]
    orientation_probes: Sequence[OrientationProbe]
    passage_probes: list[PassageProbe]
    sources: Sequence[SourceEntry]
    edits: Mapping[str, int]
    notices: str
    report: str | None
    warnings_count: int
    asset_notices: NotRequired[list[AssetNotice]]


class WindingStats(TypedDict):
    considered: int
    degenerate: int
    same: int
    reversed: int
    ambiguous: int
    unmatched: int
    unchecked: int
    comparisons: int
    work: int
    work_exhausted: bool
    reversed_examples: list[list[list[float]]]


class OneToOneStats(TypedDict):
    matched: int
    reversed: int
    unmatched: int
    visual_only: int
    work_exhausted: bool


PACKAGE_EXTENSION = ".mbmap"
MANIFEST = "manifest.json"
MAX_ENTRIES = 64
MAX_TOTAL_UNCOMPRESSED = 1536 * 1024 * 1024
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_RATIO = 200
MAX_NAME_LEN = 255

# path -> (role, media_type, required)
MEMBERS: dict[str, tuple[str, str, bool]] = {
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
AXES: dict[str, object] = {
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
MAX_WINDING_CANDIDATES = 32       # corresponding candidates compared per collision triangle; more = ambiguous
# Work budget for the per-triangle matchers: candidate visits (including candidates pruned because no vertex
# correspondence fits) per collision triangle on average, plus a constant. Exported meshes visit about one
# candidate per triangle; the budget only stops adversarial piles of coincident triangles.
MATCH_WORK_PER_TRIANGLE = 64
MATCH_WORK_SLACK = 4096
PROBE_MIN_ABS_XY_M = 1.0
PROBE_MIRROR_CLEARANCE_M = 0.5
PROBE_MIN_NORMAL_XZ = 0.05
PROBE_MATCH_M = 0.05
PROBE_MIN_DOT = 0.99
PROBE_MAX = 3
HEIGHTFIELD_TOL_M = 1e-3
PASSAGE_KINDS = ("bridge", "tunnel", "elevated")
PASSAGE_PROBE_MAX = 256
PASSAGE_PATH_MIN, PASSAGE_PATH_MAX = 2, 64
PASSAGE_RADIUS_MAX_M = 10.0
PASSAGE_QUERY_BUDGET = 2_000_000    # object/triangle visits shared by all passage probes of one package

_MB_ID = re.compile(r"(osm:(node|way|relation)/-?\d+(#\d+)?|osm:way/-?\d+:headwall[01]|terrain:grid|scatter:.+#\d+)")
_SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")


def is_utc_timestamp(s: object) -> bool:
    """True for a real calendar instant written as YYYY-MM-DDTHH:MM:SS[.fff]Z (ASCII digits)."""
    if not isinstance(s, str) or not _UTC.fullmatch(s):
        return False
    try:
        datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True
# One credential policy for every string in the manifest (values and keys) and report.json, applied by the
# writer before emitting and by the validator: URL userinfo, credential-named query/form parameters,
# HTTP Authorization-style headers and bearer/basic credentials.
_CREDENTIAL_NAMES = (r"api[_-]?key|apikey|key|access[_-]?key|token|access[_-]?token|refresh[_-]?token|id[_-]?token"
                     r"|auth|password|passwd|pwd|secret|client[_-]?secret|signature|sig|x-amz-[a-z-]+")
_SECRET = re.compile(r"(?i)((?:^|[^a-z0-9_-])(?:" + _CREDENTIAL_NAMES + r")=)"
                     r"|([a-z][a-z0-9+.-]*://[^/\s@?#]*@)"
                     r"|(\b(?:proxy-)?authorization\s*[:=])|(\bx-api-key\s*[:=])"
                     r"|(\bbearer\s+[a-z0-9._~+/-]{8,})|((?-i:\bBasic)\s+[A-Za-z0-9+/]{12,}={0,2})")
# dict keys naming a credential: a non-empty string value under such a key is a secret
_SECRET_KEY = re.compile(r"(?i)(?:x-)?(?:api[_-]?key|apikey|access[_-]?key|secret[_-]?key|token|access[_-]?token"
                         r"|refresh[_-]?token|id[_-]?token|auth|authorization|password|passwd|pwd|secret"
                         r"|client[_-]?secret|signature|credentials?)")
_SAFE_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")


def manifest_bytes(manifest: Mapping[str, object]) -> bytes:
    return json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")


def package_id_of(manifest_data: bytes) -> str:
    """Package identity from the raw manifest.json bytes."""
    return "sha256:" + hashlib.sha256(manifest_data).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_member_name(name: object) -> bool:
    """Relative POSIX path: no absolute path, ``..``, backslash, drive letter, empty or ``.`` segment."""
    if not isinstance(name, str) or not name or len(name) > MAX_NAME_LEN:
        return False
    if "\\" in name or ":" in name or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in name):
        return False
    if name.startswith("/"):
        return False
    return all(part not in ("", ".", "..") for part in name.split("/"))


def _num(v: object) -> TypeGuard[float]:
    """A real number (int or float, not bool) with a finite float value. Integers are bounded exactly before
    any float conversion, so an oversized integer (e.g. 10**400) is rejected instead of raising OverflowError."""
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return -sys.float_info.max <= v <= sys.float_info.max
    return isinstance(v, float) and math.isfinite(v)


def _vec(v: object, n: int = 3) -> bool:
    return isinstance(v, list) and len(v) == n and all(_num(c) for c in v)


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def passage_probe_problems(probes: object) -> list[str]:
    """Structural problems of a manifest ``passage_probes`` value (docs/PACKAGE_FORMAT.md "Passage probes"),
    as index-only messages that never echo strings from the input. Extra keys in an entry are ignored."""
    if not isinstance(probes, list) or len(probes) > PASSAGE_PROBE_MAX:
        return [f"passage_probes must be an array of at most {PASSAGE_PROBE_MAX}"]
    problems: list[str] = []
    seen: dict[str, int] = {}
    for i, p in enumerate(probes):
        tag = f"passage_probes[{i}]"
        if not isinstance(p, dict):
            problems.append(f"{tag} must be an object")
            continue
        pid = p.get("id")
        if not (isinstance(pid, str) and pid):
            problems.append(f"{tag}.id must be a non-empty string")
        elif pid in seen:
            problems.append(f"{tag}.id repeats the id of passage_probes[{seen[pid]}]")
        else:
            seen[pid] = i
        if p.get("kind") not in PASSAGE_KINDS:
            problems.append(f"{tag}.kind must be one of {list(PASSAGE_KINDS)}")
        if not (isinstance(p.get("feature"), str) and p["feature"]):
            problems.append(f"{tag}.feature must be a non-empty mb_id string")
        path = p.get("path_map")
        if not (isinstance(path, list) and PASSAGE_PATH_MIN <= len(path) <= PASSAGE_PATH_MAX
                and all(_vec(q) and all(abs(c) <= MAX_ABS_COORD_M for c in q) for q in path)):
            problems.append(f"{tag}.path_map must be {PASSAGE_PATH_MIN}..{PASSAGE_PATH_MAX} finite [x, y, z] "
                            f"points in the map frame with |coordinate| <= {MAX_ABS_COORD_M:g}")
        rad = p.get("radius_m")
        if not (_num(rad) and 0.0 < rad <= PASSAGE_RADIUS_MAX_M):
            problems.append(f"{tag}.radius_m must be a number in (0, {PASSAGE_RADIUS_MAX_M:g}]")
    return problems


def _cross(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> Vec3:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


def _unit(v: Sequence[float]) -> Vec3 | None:
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return None if n == 0 else (v[0] / n, v[1] / n, v[2] / n)


_PERMUTATIONS: tuple[tuple[int, int, int], ...] = ((0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1), (2, 1, 0), (1, 0, 2))   # 3 cyclic, then 3 reversed


def _key_label(path: str, k: object, i: int) -> str:
    """Path step for a dict key that never echoes untrusted key text."""
    return f"{path}.{k}" if isinstance(k, str) and _SAFE_KEY.fullmatch(k) else f"{path}[key #{i}]"


def find_secrets(obj: object, path: str = "$") -> list[str]:
    """Locations of credential-like strings (see ``_SECRET``) anywhere in ``obj``: string values, dict keys,
    and non-empty strings stored under credential-named keys. Locations are built from field names that are
    plain identifiers and from indices, so they never echo the offending text. Iterative (depth-first, in
    document order), so arbitrarily nested parsed JSON cannot exhaust the interpreter stack; linear in the
    size of ``obj``."""
    hits: list[str] = []
    stack: list[tuple[object, str]] = [(obj, path)]
    while stack:
        obj, path = stack.pop()
        if isinstance(obj, dict):
            children: list[tuple[object, str]] = []
            for i, (k, v) in enumerate(obj.items()):
                where = _key_label(path, k, i)
                if isinstance(k, str) and _SECRET.search(k):
                    hits.append(f"{path}[key #{i}]")
                if isinstance(k, str) and _SECRET_KEY.fullmatch(k) and isinstance(v, str) and v.strip():
                    hits.append(where)
                    continue
                children.append((v, where))
            stack.extend(reversed(children))
        elif isinstance(obj, (list, tuple)):
            stack.extend((obj[i], f"{path}[{i}]") for i in range(len(obj) - 1, -1, -1))
        elif isinstance(obj, str) and _SECRET.search(obj):
            hits.append(path)
    return hits


def secrets_message(where: str, hits: Sequence[str]) -> str:
    return (f"{where}: credential-like value(s) at {hits[:5]}{' ...' if len(hits) > 5 else ''}; expected no URL "
            "userinfo, credential query parameters (key, token, apikey, access_token, signature, password, "
            "secret, ...), Authorization headers or bearer/basic credentials")


# --- manifest ------------------------------------------------------------------

def build_manifest(name: str, area: Area, sources: Sequence[Mapping[str, object]], vertical_datum: str,
                   files: Sequence[FileEntry], collision_info: CollisionInfo,
                   heightfield_info: HeightfieldManifest | None, objects: Sequence[ObjectEntry],
                   probes: Sequence[OrientationProbe], edits_counts: Mapping[str, int], warnings_count: int,
                   has_report: bool = True, blender_version: str | None = None, created_utc: str | None = None,
                   passage_probes: Iterable[PassageProbe] | None = None,
                   schema_version: str = PACKAGE_SCHEMA_VERSION,
                   asset_notices: Iterable[Mapping[str, object]] = ()) -> Manifest:
    frame = area.frame
    manifest: Manifest = {
        "schema": PACKAGE_SCHEMA,
        "schema_version": schema_version,
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
        "passage_probes": copy.deepcopy(list(passage_probes or [])),
        "sources": cast("Sequence[SourceEntry]", sources),
        "edits": edits_counts,
        "notices": "NOTICES.txt",
        "report": "report.json" if has_report else None,
        "warnings_count": warnings_count,
    }
    if asset_notices:   # optional (schema 2.1); omitted when empty so 2.0 manifests are unchanged
        manifest["asset_notices"] = cast("list[AssetNotice]", copy.deepcopy(list(asset_notices)))
    return manifest


LICENSE_TEXT_KEYS = ("id", "name", "text")   # a source licence declares at least one of these
LICENSE_NOTICE_KEYS = ("id", "name", "text", "url")   # each one declared must appear in NOTICES.txt


def asset_notice_problems(notices: object) -> list[str]:
    """Shape problems of a manifest ``asset_notices`` value (empty list = fine)."""
    if not isinstance(notices, list):
        return ["asset_notices must be an array"]
    out: list[str] = []
    for i, a in enumerate(notices):
        lic = a.get("license") if isinstance(a, dict) else None
        if not (isinstance(a, dict) and isinstance(a.get("name"), str) and a["name"]
                and isinstance(a.get("attribution"), str) and a["attribution"] and isinstance(lic, dict)):
            out.append(f"asset_notices[{i}] needs name, attribution (non-empty strings) and license {{...}}")
            continue
        if (not all(isinstance(lic.get(k), str) for k in LICENSE_NOTICE_KEYS if k in lic)
                or not any(lic.get(k) for k in LICENSE_TEXT_KEYS)):
            out.append(f"asset_notices[{i}].license must declare a licence identifier, name or text "
                       f"({'/'.join(LICENSE_TEXT_KEYS)}) and an optional url, all strings")
        h = a.get("sha256")
        if not (isinstance(h, list) and h and all(isinstance(x, str) and re.fullmatch(r"[0-9a-f]{64}", x)
                                                   for x in h)):
            out.append(f"asset_notices[{i}].sha256 must be a non-empty array of 64 lowercase hex digits")
    return out


def notices_text(sources: Iterable[Mapping[str, object]],
                 asset_notices: Iterable[Mapping[str, object]] = ()) -> str:
    lines = ["Map package data notices", "========================", "",
             "This package contains visual and collision geometry derived from the sources below.",
             "Procedural details (materials, inferred heights/roofs, scattered vegetation) are generated",
             "by map-builder and are not measurements. See report.json and manifest objects[].provenance.", ""]
    for s in sources:
        lic = cast("LicenseInfo", s.get("license") or {})
        lines.append(f"- {s.get('product', s.get('provider'))}")
        if s.get("attribution"):
            lines.append(f"  Attribution: {s['attribution']}")
        if lic.get("name"):
            lines.append(f"  Licence: {lic['name']}")
        if lic.get("id"):
            lines.append(f"  Licence identifier: {lic['id']}")
        if lic.get("url"):
            lines.append(f"  Licence URL: {lic['url']}")
        if lic.get("text"):
            lines.append("  Licence text:")
            lines.append(lic["text"])
        if s.get("notes"):
            lines.append(f"  Notes: {s['notes']}")
        if s.get("processing"):
            lines.append(f"  Processing: {s['processing']}")
    lines.append("")
    if asset_notices:
        lines += ["Assets", "------", "", "Embedded texture assets (visual/map.glb):", ""]
        for a in asset_notices:
            lic = cast("LicenseInfo", a.get("license") or {})
            lines.append(f"- {a.get('name')}")
            if a.get("attribution"):
                lines.append(f"  Attribution: {a['attribution']}")
            if lic.get("name"):
                lines.append(f"  Licence: {lic['name']}")
            if lic.get("id"):
                lines.append(f"  Licence identifier: {lic['id']}")
            if lic.get("url"):
                lines.append(f"  Licence URL: {lic['url']}")
            if lic.get("text"):
                lines.append("  Licence text:")
                lines.append(lic["text"])
            for h in cast("Iterable[JsonValue]", a.get("sha256") or []):
                lines.append(f"  SHA-256: {h}")
        lines.append("")
    if any(cast("LicenseInfo", s.get("license") or {}).get("id") == "ODbL-1.0" for s in sources):
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

def _cell(p: Sequence[float], s: float) -> Cell:
    return (math.floor(p[0] / s), math.floor(p[1] / s), math.floor(p[2] / s))


def _near(grid: Mapping[Cell, Sequence[Sequence[float]]], p: Sequence[float], s: float, radius: float) -> bool:
    cx, cy, cz = _cell(p, s)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for q in grid.get((cx + dx, cy + dy, cz + dz), ()):
                    if _dist(p, q) <= radius:
                        return True
    return False


def _object_vertex_grid(col: Collision, entry: CollisionEntry) -> dict[Cell, list[Vec3]]:
    s, c = entry["tri_start"], entry["tri_count"]
    grid: dict[Cell, list[Vec3]] = {}
    for vi in set(col.indices[3 * s:3 * (s + c)]):
        p = col.vertices[vi]
        grid.setdefault(_cell(p, PROBE_MIRROR_CLEARANCE_M), []).append(p)
    return grid


def node_probe(col: Collision, entry: CollisionEntry) -> OrientationProbe | None:
    """First qualifying (vertex, triangle) of a collision object in triangle order, or None."""
    grid: dict[Cell, list[Vec3]] | None = None
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


def select_orientation_probes(col: Collision, max_probes: int = PROBE_MAX) -> list[OrientationProbe]:
    """Up to three probes, one per node: non-terrain nodes first (table order), then terrain."""
    order = ([e for e in col.objects if e["class"] != "terrain"] + [e for e in col.objects if e["class"] == "terrain"])
    probes: list[OrientationProbe] = []
    for e in order:
        if len(probes) >= max_probes:
            break
        p = node_probe(col, e)
        if p is not None:
            probes.append(p)
    return probes


def unity_import(gltf_triangles: Iterable[Tri]) -> list[tuple[Vec3, Vec3, Vec3]]:
    """Simulate a glTF importer that negates X (glTFast/UnityGLTF): positions (-x, y, z) and reversed index
    order. Returns Unity-space triangles in imported index order."""
    out: list[tuple[Vec3, Vec3, Vec3]] = []
    for a, b, c in gltf_triangles:
        ua, ub, uc = ((-p[0], p[1], p[2]) for p in (a, b, c))
        out.append((ua, uc, ub))
    return out


def verify_probe_in_unity(probe: OrientationProbe, unity_triangles: Sequence[Tri],
                          tol: float = PROBE_MATCH_M) -> str | None:
    """The consumer-side probe check of docs/PACKAGE_FORMAT.md against Unity-space triangles (imported
    index order). Returns None if it passes, otherwise the reason."""
    pu = probe["point_unity_x_negated"]
    if not any(_dist(pu, q) <= tol for t in unity_triangles for q in t):
        return "no vertex of the node within 5 cm of point_unity_x_negated"
    want = [map_to_unity_x_negated(q) for q in probe["triangle_map"]]
    nu = probe["normal_unity_x_negated"]
    found = False
    for t in unity_triangles:
        # one-to-one: some permutation pairs each wanted vertex with a distinct imported vertex within tol
        if not any(all(_dist(want[i], t[perm[i]]) <= tol for i in range(3)) for perm in _PERMUTATIONS):
            continue
        found = True
        n = _unit(_cross(*t))  # Unity Vector3.Cross(b - a, c - a), imported index order
        if n is not None and n[0] * nu[0] + n[1] * nu[1] + n[2] * nu[2] > PROBE_MIN_DOT:
            return None
    if not found:
        return "no imported triangle matches triangle_map within 5 cm"
    return "imported triangle front face does not match normal_unity_x_negated (winding or handedness wrong)"


# --- per-triangle winding match ------------------------------------------------------------

def _centroid(t: Tri) -> Vec3:
    return ((t[0][0] + t[1][0] + t[2][0]) / 3, (t[0][1] + t[1][1] + t[2][1]) / 3, (t[0][2] + t[1][2] + t[2][2]) / 3)


def _centroid_cells(tri: Tri, tol: float) -> list[Cell]:
    """Cells (size 2*tol) that can hold the centroid of a triangle whose vertices are each within tol."""
    cs = 2.0 * tol
    cen = _centroid(tri)
    lo = _cell((cen[0] - tol, cen[1] - tol, cen[2] - tol), cs)
    hi = _cell((cen[0] + tol, cen[1] + tol, cen[2] + tol), cs)
    return [(ix, iy, iz) for ix in range(lo[0], hi[0] + 1) for iy in range(lo[1], hi[1] + 1)
            for iz in range(lo[2], hi[2] + 1)]


def _correspondence(tri: Tri, v: Tri, tol: float) -> tuple[float, float]:
    """(best same-orientation, best reversed) total vertex distance over the vertex correspondences whose
    every pair is within ``tol``; ``inf`` where no correspondence of that orientation fits."""
    d = [[_dist(tri[i], v[j]) for j in range(3)] for i in range(3)]
    best = [math.inf, math.inf]
    for k, perm in enumerate(_PERMUTATIONS):
        dd = (d[0][perm[0]], d[1][perm[1]], d[2][perm[2]])
        if max(dd) <= tol:
            best[k >= 3] = min(best[k >= 3], sum(dd))
    return best[0], best[1]


def _match_budget(n: int, max_work: int | None) -> int:
    return MATCH_WORK_PER_TRIANGLE * n + MATCH_WORK_SLACK if max_work is None else max_work


def match_winding(collision_triangles: Iterable[Tri], visual_triangles: Iterable[Tri], tol: float = WINDING_TOL_M,
                  max_candidates: int = MAX_WINDING_CANDIDATES, max_work: int | None = None) -> WindingStats:
    """Match each non-degenerate collision triangle to visual triangles (same frame) whose three vertices
    are each within ``tol``. Bounded: visual triangles are hashed by centroid in cells of 2*tol, so each
    query visits at most 8 cells. Candidates with no vertex correspondence within ``tol`` are pruned first;
    more than ``max_candidates`` corresponding candidates count as ambiguous. Every candidate visit counts
    against ``max_work`` (default ``MATCH_WORK_PER_TRIANGLE`` per collision triangle + ``MATCH_WORK_SLACK``);
    once it is exhausted the remaining triangles are counted as ``unchecked`` and ``work_exhausted`` is set,
    which callers must report as such (it is not a tie)."""
    collision_triangles = list(collision_triangles)
    cs = 2.0 * tol
    grid: dict[Cell, list[Tri]] = {}
    for v in visual_triangles:
        grid.setdefault(_cell(_centroid(v), cs), []).append(v)
    st: WindingStats = {"considered": 0, "degenerate": 0, "same": 0, "reversed": 0, "ambiguous": 0, "unmatched": 0,
          "unchecked": 0, "comparisons": 0, "work": 0, "work_exhausted": False, "reversed_examples": []}
    budget = _match_budget(len(collision_triangles), max_work)
    for tri in collision_triangles:
        if st["work_exhausted"]:
            st["unchecked"] += 1
            continue
        if is_degenerate(*tri, DEGENERATE_EPS):
            st["degenerate"] += 1
            continue
        best_same = best_rev = math.inf
        n = 0
        overflow = False
        for cell in _centroid_cells(tri, tol):
            for v in grid.get(cell, ()):
                st["work"] += 1
                if st["work"] > budget:
                    st["work_exhausted"] = True
                    break
                same, rev = _correspondence(tri, v, tol)
                if same == math.inf and rev == math.inf:
                    continue          # no vertex correspondence: cannot be this triangle's visual
                n += 1
                if n > max_candidates:
                    overflow = True
                    break
                st["comparisons"] += 1
                best_same = min(best_same, same)
                best_rev = min(best_rev, rev)
            if overflow or st["work_exhausted"]:
                break
        if st["work_exhausted"]:
            st["unchecked"] += 1
            continue
        st["considered"] += 1
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


def match_one_to_one(collision_triangles: Iterable[Tri], visual_triangles: Iterable[Tri],
                     tol: float = WINDING_TOL_M, max_work: int | None = None) -> OneToOneStats:
    """Exporter-side binding (stricter than the consumer diagnostic of :func:`match_winding`): pair every
    collision triangle with a *distinct* visual triangle whose vertices are each within ``tol`` in the same
    cyclic order (any order for a degenerate collision triangle, which has no orientation), and leave no
    visual triangle unpaired.

    A maximum bipartite matching over those candidate sets, so the result does not depend on triangle order:
    a greedy closest-first pass pairs the unambiguous majority (exports come from the same evaluated meshes,
    so pairs coincide to float32 precision), then Kuhn augmenting paths (iterative) are searched from each
    collision triangle left free; such a search only walks the component of overlapping candidates it
    starts in. One budget, ``max_work`` (see :func:`match_winding`), covers candidate visits while building
    the sets and edge visits while augmenting; when it runs out ``work_exhausted`` is set and the counts
    are incomplete (callers must refuse, not pass).

    Returns {"matched", "reversed", "unmatched", "visual_only", "work_exhausted"}: ``reversed`` counts
    unpaired collision triangles that have no same-winding candidate but a reversed one; ``visual_only``
    counts visual triangles left unpaired."""
    collision_triangles = list(collision_triangles)
    visual_triangles = list(visual_triangles)
    cs = 2.0 * tol
    grid: dict[Cell, list[int]] = {}
    for k, v in enumerate(visual_triangles):
        grid.setdefault(_cell(_centroid(v), cs), []).append(k)
    st: OneToOneStats = {"matched": 0, "reversed": 0, "unmatched": 0, "visual_only": 0, "work_exhausted": False}
    budget = _match_budget(len(collision_triangles), max_work)
    work = 0
    cands: list[list[int]] = []            # per collision triangle: [(distance, visual index)], closest first
    reversed_only: list[bool] = []
    for tri in collision_triangles:
        degenerate = is_degenerate(*tri, DEGENERATE_EPS)
        scored: list[tuple[float, int]] = []
        rev_seen = False
        for cell in _centroid_cells(tri, tol):
            for k in grid.get(cell, ()):
                work += 1
                if work > budget:
                    st["work_exhausted"] = True
                    return st
                same, rev = _correspondence(tri, visual_triangles[k], tol)
                d = min(same, rev) if degenerate else same
                if d < math.inf:
                    scored.append((d, k))
                elif rev < math.inf:
                    rev_seen = True
        scored.sort()
        cands.append([k for _, k in scored])
        reversed_only.append(rev_seen and not scored)
    owner = [-1] * len(visual_triangles)          # visual index -> collision index
    mate = [-1] * len(collision_triangles)        # collision index -> visual index
    for u, row in enumerate(cands):               # fast path: closest free candidate
        for k in row:
            if owner[k] < 0:
                owner[k], mate[u] = u, k
                break
    for root in range(len(cands)):
        if mate[root] >= 0 or not cands[root]:
            continue
        # iterative DFS for an augmenting path: alternate free edge (u -> k), matched edge (k -> owner[k])
        seen: set[int] = set()
        stack = [(root, 0)]
        via: dict[int, int] = {}                                  # visual k -> collision u it was reached from
        end = -1
        while stack and end < 0:
            u, i = stack[-1]
            if i >= len(cands[u]):
                stack.pop()
                continue
            stack[-1] = (u, i + 1)
            work += 1
            if work > budget:
                st["work_exhausted"] = True
                return st
            k = cands[u][i]
            if k in seen:
                continue
            seen.add(k)
            via[k] = u
            if owner[k] < 0:
                end = k
            else:
                stack.append((owner[k], 0))
        k = end
        while k >= 0:                             # flip the path back to the root
            u = via[k]
            prev = mate[u]
            owner[k], mate[u] = u, k
            k = prev
    for u, k in enumerate(mate):
        if k >= 0:
            st["matched"] += 1
        elif reversed_only[u]:
            st["reversed"] += 1
        else:
            st["unmatched"] += 1
    st["visual_only"] = owner.count(-1)
    return st


# --- independent collision orientation ------------------------------------------------------

WELD_TOL_M = 1e-4                 # building shell vertices closer than this are one vertex (float32 noise)


def _weld_ids(tris: Iterable[Tri], tol: float = WELD_TOL_M) -> list[tuple[int, ...]]:
    """Welded vertex id triples. Each distinct position joins the first representative within ``tol`` in
    the 27 surrounding cells of size ``tol``, or becomes one. Representatives are kept more than ``tol``
    apart, so a cell holds only a few of them and every lookup is bounded."""
    exact: dict[Sequence[float], int] = {}
    reps: dict[Cell, list[tuple[Sequence[float], int]]] = {}
    out: list[tuple[int, ...]] = []
    nrep = 0
    for t in tris:
        ids: list[int] = []
        for p in t:
            i = exact.get(p)
            if i is None:
                cx, cy, cz = _cell(p, tol)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            for q, j in reps.get((cx + dx, cy + dy, cz + dz), ()):
                                if i is None and _dist(p, q) <= tol:
                                    i = j
                if i is None:
                    i = nrep
                    nrep += 1
                    reps.setdefault((cx, cy, cz), []).append((p, i))
                exact[p] = i
            ids.append(i)
        out.append(tuple(ids))
    return out


def _find(parent: list[int], a: int) -> int:
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a


def _union(parent: list[int], a: int, b: int) -> None:
    a, b = _find(parent, a), _find(parent, b)
    if a != b:
        parent[max(a, b)] = min(a, b)


def _shells(ids: Sequence[tuple[int, ...]]) -> list[list[int]] | None:
    """Split a building's triangles (welded id triples) into shells: triangles joined across manifold
    edges (one use in each direction). If a component is not closed on its own, which only happens at
    non-manifold edges (e.g. two shells sharing a face), returns None: the shells cannot be separated
    unambiguously, and a merged group's volume would let an outward shell mask an inverted one. Triangles
    with no edge of non-zero length (collapsed to a point) belong to no shell. Otherwise returns lists of
    triangle indices, in first-triangle order."""
    edges: dict[tuple[int, int], list[tuple[int, bool]]] = {}                                  # undirected edge -> [(triangle, forward)]
    for t, (a, b, c) in enumerate(ids):
        if a == b or b == c or c == a:
            continue                            # collapsed to an edge or point: its edge uses cancel out
        for p, q in ((a, b), (b, c), (c, a)):
            edges.setdefault((min(p, q), max(p, q)), []).append((t, p < q))
    parent = list(range(len(ids)))
    for uses in edges.values():
        if len(uses) == 2 and uses[0][1] != uses[1][1]:
            _union(parent, uses[0][0], uses[1][0])
    balance: dict[tuple[int, tuple[int, int]], int] = {}                                # (component, undirected edge) -> forward minus backward
    for e, uses in edges.items():
        for t, fwd in uses:
            key = (_find(parent, t), e)
            balance[key] = balance.get(key, 0) + (1 if fwd else -1)
    open_comps = {c for (c, _), n in balance.items() if n}
    if open_comps:
        return None
    groups: dict[int, list[int]] = {}
    for t in range(len(ids)):
        if len(set(ids[t])) == 3:
            groups.setdefault(_find(parent, t), []).append(t)
    return list(groups.values())


_EPS = 2.0 ** -53


def _signed_volume(tris: Sequence[Sequence[Sequence[Num]]]) -> float:
    """Signed volume of a closed triangle shell whose sign is exact: coordinates are floats or exact
    ``Fraction`` values (portal-cap centroids). A float sum with an error bound is used unless the result
    is within that bound of zero; then the volume is recomputed exactly, so rounding can never make a
    flat shell look like it encloses volume (or flip the sign of a thin one)."""
    r = tris[0][0]                              # a local origin keeps the products small
    terms: list[float] = []
    mag = 0.0
    for a, b, c in tris:
        ax, ay, az, bx, by, bz, cx, cy, cz = (
            (float(Fraction(v) - Fraction(o)) if type(v) is Fraction or type(o) is Fraction
             else cast("float", v) - cast("float", o))   # neither is a Fraction here: plain float arithmetic
            for p in (a, b, c) for v, o in zip(p, r))
        terms.append(ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx))
        mag += (abs(ax) * (abs(by * cz) + abs(bz * cy)) + abs(ay) * (abs(bz * cx) + abs(bx * cz))
                + abs(az) * (abs(bx * cy) + abs(by * cx)))
    vol = math.fsum(terms)
    if abs(vol) > 32.0 * _EPS * mag:            # generous bound on translation, product and sum rounding
        return vol / 6.0
    rf = [Fraction(v) for v in r]
    exact = Fraction(0)
    for a, b, c in tris:
        fax, fay, faz, fbx, fby, fbz, fcx, fcy, fcz = (Fraction(v) - o for p in (a, b, c) for v, o in zip(p, rf))
        exact += fax * (fby * fcz - fbz * fcy) + fay * (fbz * fcx - fbx * fcz) + faz * (fbx * fcy - fby * fcx)
    if exact == 0:
        return 0.0
    out = float(exact / 6)
    return out if out != 0.0 else math.copysign(5e-324, exact)


def _directed_edges(ids: Iterable[tuple[int, ...]]) -> dict[tuple[int, int], int]:
    edges: dict[tuple[int, int], int] = {}
    for a, b, c in ids:
        for p, q in ((a, b), (b, c), (c, a)):
            if p != q:
                edges[(p, q)] = edges.get((p, q), 0) + 1
    return edges


def _solid_problems(k: int, cls: str, tris: Sequence[Tri]) -> list[str]:
    """Orientation problems of one solid-kind collision object (index ``k`` in the object table)."""
    tag = f"collision: {cls} object #{k}"
    ids = _weld_ids(tris)
    edges = _directed_edges(ids)
    unbalanced = sum(1 for (p, q), n in edges.items()
                     if edges.get((q, p), 0) != n and ((q, p) not in edges or (p, q) < (q, p)))
    if unbalanced:
        return [f"{tag} is not a closed, consistently oriented solid ({unbalanced} open or inconsistently "
                "wound edge(s)); solids (building, bridge, structure) must be closed with CCW-outward faces"]
    shells: list[tuple[list[Tri], float]] = []
    parts = _shells(ids)
    if parts is None:
        return [f"{tag} has non-manifold edges that do not split into independently closed shells, so its "
                "orientation cannot be verified; solids must be closed 2-manifold shells (faces or edges "
                "shared between shells are not supported)"]
    for ts in parts:
        st = [tris[t] for t in ts]
        shells.append((st, _signed_volume(st)))
    problems: list[str] = []
    n = len(shells)
    for s, (st, vol) in enumerate(shells):
        if vol > 0.0 or all(is_degenerate(*t) for t in st):
            continue                            # outward, or only zero-area faces: nothing to orient
        problems.append(f"{tag}: shell {s} of {n} has signed volume {vol:.6g} m^3; every shell must have "
                        "positive volume (faces CCW seen from outside). Inverted shells and enclosed "
                        "cavities are not supported")
    if not any(vol > 0.0 for _st, vol in shells):
        problems.append(f"{tag} has no closed shell with positive volume (collapsed or flattened, e.g. by a zero "
                        f"scale); a {cls} collision object must be a solid")
    return problems


def _tube_problems(k: int, cls: str, tris: Sequence[Tri]) -> list[str]:
    """Orientation problems of one tube-kind collision object (index ``k`` in the object table).

    After welding (as for solids), every directed edge must be matched by its reverse equally often,
    except boundary edges (used once, never reversed). Boundary edges must form simple closed loops (the
    portals: every boundary vertex has exactly one outgoing and one incoming boundary edge). Each loop is
    capped with a triangle fan around its centroid, wound like the adjacent faces (a cap face uses each
    boundary edge reversed), which closes the surface; every resulting shell must then have a negative
    signed volume (faces point inward, toward the free space). Every shell must be open: a shell with no
    portal loop (a sealed inward box) is an error. Linear in the triangle count."""
    tag = f"collision: {cls} object #{k}"
    ids = _weld_ids(tris)
    pos: dict[int, Sequence[float]] = {}
    for t, tri in zip(ids, tris):
        for i, pt in zip(t, tri):
            pos.setdefault(i, pt)
    edges = _directed_edges(ids)
    bad = boundary_multi = 0
    nxt: dict[int, int] = {}
    incoming: dict[int, int] = {}
    branching = 0
    for (p, q), n in edges.items():
        m = edges.get((q, p), 0)
        if m:
            bad += m != n and p < q
            continue
        if n != 1:
            boundary_multi += 1
            continue
        if p in nxt:
            branching += 1
        nxt[p] = q
        incoming[q] = incoming.get(q, 0) + 1
    if bad or boundary_multi:
        return [f"{tag} is not a consistently oriented tube ({bad} inconsistently wound edge(s), {boundary_multi} "
                "boundary edge(s) used more than once); tube faces must be consistently wound, CCW facing inward"]
    branching += (sum(1 for v, c in incoming.items() if c != 1) + sum(1 for v in nxt if v not in incoming)
                  + sum(1 for v in incoming if v not in nxt))
    if branching:
        return [f"{tag}: its boundary edges do not form simple closed loops ({branching} boundary vertex/vertices "
                "without exactly one incoming and one outgoing boundary edge); a tube may be open only at "
                "closed portal loops"]
    capped_ids = list(ids)
    capped: list[Sequence[Sequence[Num]]] = list(tris)
    seen: set[int] = set()
    loops = 0
    next_id = max((i for t in ids for i in t), default=-1) + 1
    for start in nxt:
        if start in seen:
            continue
        loop: list[int] = []
        v = start
        while v not in seen:            # each boundary vertex has one successor: the walk is a simple cycle
            seen.add(v)
            loop.append(v)
            v = nxt[v]
        if v != start:                  # cannot happen when every vertex has one in and one out edge
            return [f"{tag}: its boundary edges do not form simple closed loops"]
        loops += 1
        n = len(loop)
        cen = tuple(sum(Fraction(pos[i][a]) for i in loop) / n for a in range(3))     # exact (see _signed_volume)
        cid = next_id
        next_id += 1
        for j in range(n):
            p, q = loop[j], loop[(j + 1) % n]          # boundary edge p -> q; the cap uses q -> p
            capped_ids.append((q, p, cid))
            capped.append((pos[q], pos[p], cen))
    parts = _shells(capped_ids)
    if parts is None:
        return [f"{tag} has non-manifold edges that do not split into independently closed shells once its "
                f"{loops} portal loop(s) are capped, so its orientation cannot be verified"]
    problems: list[str] = []
    n = len(parts)
    vols: list[float] = []
    first_cap = len(ids)
    for s, ts in enumerate(parts):
        if not any(t >= first_cap for t in ts):
            problems.append(f"{tag}: shell {s} of {n} is sealed (it has no portal loop); every tube shell must be "
                            "open at one or more portals")
            continue
        st = [capped[t] for t in ts]
        vol = _signed_volume(st)
        vols.append(vol)
        if vol < 0.0:
            continue
        problems.append(f"{tag}: shell {s} of {n} (portal loops capped) has signed volume {vol:.6g} m^3; every "
                        "tube shell must have negative volume (faces CCW seen from the free space inside; a "
                        "shell of only zero-area faces encloses nothing and is an error too)")
    if len(vols) == n and not any(v < 0.0 for v in vols):      # (sealed shells are reported above)
        problems.append(f"{tag} has no shell with negative volume once its portals are capped (collapsed or "
                        "flattened); a tube collision object must enclose free space")
    return problems


def collision_orientation_problems(col: Collision) -> list[str]:
    """Checks the final collision on its own, per docs/PACKAGE_FORMAT.md "Winding" (agreement with the
    visuals does not prove orientation: both could be inverted). Returns a list of error strings, which
    name objects by table index only (never by their names from the file). The rule follows the class
    kind (``collision.CLASS_KINDS``):

    * solid (building, bridge, structure): a closed solid with consistently oriented edges (every directed
      edge, after welding positions within ``WELD_TOL_M``, is matched by its reverse equally often;
      zero-length edges of degenerate triangles are ignored, degenerate triangles are otherwise kept so
      slivers still close the surface). Each connected shell (see :func:`_shells`) is checked on its own,
      so an outward shell cannot hide a separate inverted one: every shell must have positive signed
      volume. Enclosed cavities (inward-facing inner shells) are not supported and are errors; courtyards
      are holes of their own shell, not cavities. Generated buildings, all roof shapes, courtyards and
      raised parts, are closed outward shells by construction. The work is linear in the triangle count.
    * surface (terrain, road, water): every non-degenerate triangle faces up (normal z > 0).
    * tube (tunnel): see :func:`_tube_problems`.
    Other classes (vegetation, props, user) carry no orientation requirement in the contract."""
    problems: list[str] = []
    for k, e in enumerate(col.objects):
        cls = e["class"]
        kind = CLASS_KINDS.get(cls)
        if kind is None:
            continue
        tris = col.object_triangles(e)
        if kind == KIND_SOLID:
            problems += _solid_problems(k, cls, tris)
        elif kind == KIND_TUBE:
            problems += _tube_problems(k, cls, tris)
        else:
            down = sum(1 for t in tris if not is_degenerate(*t) and _cross(*t)[2] <= 0.0)
            if down:
                problems.append(f"collision: {cls} object #{k} has {down} non-degenerate triangle(s) whose "
                                "normal does not point up (z <= 0); open surfaces must face +Z")
    return problems


# --- writing --------------------------------------------------------------------------

def _zinfo(name: str, data: bytes = b"") -> zipfile.ZipInfo:
    """Deterministic entry. Deflated unless deflate would compress ``data`` beyond the validator's MAX_RATIO
    (e.g. a constant heightfield): such members are stored, so every written entry passes the ratio check."""
    zi = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))  # deterministic archive
    zi.compress_type = zipfile.ZIP_DEFLATED
    if data:
        co = zlib.compressobj(6, zlib.DEFLATED, -15)   # the raw deflate stream zipfile writes at level 6
        size = len(co.compress(data)) + len(co.flush())
        if len(data) > MAX_RATIO * size:
            zi.compress_type = zipfile.ZIP_STORED
    zi.external_attr = (stat.S_IFREG | 0o644) << 16
    return zi


def write_package(path: str | PathLike[str], members: Mapping[str, bytes],
                  manifest: Mapping[str, object]) -> ValidationResult:
    """Atomically write and validate a package. The archive is written to a temporary file next to
    ``path``, fsynced, validated (in the exporter's strict mode), and only then moved over ``path`` with
    ``os.replace``; on any failure the temporary file is removed and a previous export at ``path`` is left
    untouched."""
    path = os.path.abspath(path)
    if not path.lower().endswith(PACKAGE_EXTENSION):
        raise PackageError(f"package path must end with {PACKAGE_EXTENSION}")
    secrets = find_secrets(manifest, "manifest")
    if secrets:
        raise PackageError("refusing to write the package: " + secrets_message("manifest", secrets))
    data = manifest_bytes(manifest)
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".mbmap-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            with zipfile.ZipFile(fh, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                z.writestr(_zinfo(MANIFEST, data), data)
                for name in sorted(members):
                    z.writestr(_zinfo(name, members[name]), members[name])
            fh.flush()
            os.fsync(fh.fileno())
        result = validate_package(tmp, strict=True)
        if result.errors:
            raise PackageError("package failed validation; previous export kept:\n- " + "\n- ".join(result.errors))
        os.replace(tmp, path)
        return result
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def file_entry(path: str, data: bytes) -> FileEntry:
    role, media_type, _ = MEMBERS[path]
    return {"path": path, "role": role, "media_type": media_type, "sha256": sha256(data), "bytes": len(data)}


def assemble(name: str, area: Area, sources: Sequence[Mapping[str, object]], glb_bytes: bytes,
             collision_bytes: bytes,
             objects: Sequence[ObjectEntry], heightfield: tuple[bytes, Mapping[str, object]] | None = None,
             report: Mapping[str, object] | None = None, edits: Mapping[str, object] | None = None,
             blender_version: str | None = None, created_utc: str | None = None,
             passage_probes: Iterable[PassageProbe] | None = None,
             schema_version: str = PACKAGE_SCHEMA_VERSION,
             asset_notices: Iterable[Mapping[str, object]] = ()
             ) -> tuple[dict[str, bytes], Manifest, list[OrientationProbe]]:
    """Members + manifest for :func:`write_package`.

    ``objects``: manifest object entries ({name, mb_id, class, collision, provenance}).
    ``heightfield``: (mbhf bytes, info dict) or None. ``report``: dict (plan report + diagnostics).
    ``edits``: {"duplicated": [...], "user_added": [...], "removed": [...]} lists (report.json);
    the manifest stores their counts. ``passage_probes``: manifest ``passage_probes`` entries (default none;
    the key is always written). ``schema_version``: written to the manifest (default the current constant;
    must have the supported major). ``asset_notices``: optional texture provenance entries
    ({name, attribution, license, sha256[]}); written to the manifest and the NOTICES.txt "Assets"
    section. Returns (members, manifest, probes).
    """
    mt = _SEMVER.fullmatch(schema_version) if isinstance(schema_version, str) else None
    if not mt or mt.group(1) != PACKAGE_SCHEMA_VERSION.split(".")[0]:
        raise PackageError(f"schema_version must be MAJOR.MINOR.PATCH with major "
                           f"{PACKAGE_SCHEMA_VERSION.split('.')[0]}")
    asset_notices = list(asset_notices or [])
    bad = asset_notice_problems(asset_notices)
    if bad:
        raise PackageError("invalid asset_notices: " + "; ".join(bad))
    elevation = [s for s in sources if s.get("kind") == "elevation"]
    if not elevation or not elevation[0].get("vertical_datum"):
        raise PackageError("no elevation source with a vertical datum; refusing to write a package whose "
                           "heights are not georeferenced")
    col = read_collision(collision_bytes)
    bad = passage_probe_problems(list(passage_probes or []))
    if bad:
        raise PackageError("invalid passage probes: " + "; ".join(bad))
    probes = select_orientation_probes(col)
    rep: dict[str, object] = dict(report or {})
    for k in REPORT_KEYS:
        rep.setdefault(k, {} if k == "counts" else [])
    warnings = list(cast("Iterable[object]", rep["warnings"]))
    rep["warnings"] = warnings
    if not probes and PROBES_UNAVAILABLE not in warnings:
        warnings.append(PROBES_UNAVAILABLE)
    rep["export"] = dict(cast("Mapping[str, object]", rep.get("export") or {}), orientation_probes=len(probes))
    edit_lists: dict[str, list[object]] = {}
    for k in EDIT_KEYS:
        edit_lists[k] = list(cast("Iterable[object]", (edits or {}).get(k, [])))
    rep["edits"] = edit_lists
    secrets = find_secrets({"sources": sources, "report": rep, "objects": objects, "name": name,
                                "asset_notices": asset_notices})
    if secrets:
        raise PackageError("refusing to write the package: " + secrets_message("package", secrets))
    try:
        report_bytes = json.dumps(rep, indent=1, sort_keys=True, ensure_ascii=False,
                                  allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as e:
        raise PackageError(f"report is not finite JSON: {e}") from None
    members = {"visual/map.glb": glb_bytes, "collision/map.mbcol": collision_bytes,
               "NOTICES.txt": notices_text(sources, asset_notices).encode("utf-8"), "report.json": report_bytes}
    hf_info: HeightfieldManifest | None = None
    if heightfield is not None:
        hf_bytes, hf_meta = heightfield
        members["collision/terrain.mbhf"] = hf_bytes
        hf_info = cast("HeightfieldManifest", dict(
            hf_meta, path="collision/terrain.mbhf", format="mbhf", version=HEIGHTFIELD_FORMAT_VERSION,
            authority="derived from the final terrain-class collision triangles; triangles are authoritative"))
    files = [file_entry(p, members[p]) for p in sorted(members)]
    collision_info: CollisionInfo = {"path": "collision/map.mbcol", "format": "mbcol",
                                     "version": COLLISION_FORMAT_VERSION,
                      "frame": "map", "winding": "ccw_outward", "triangle_count": col.triangle_count,
                      "vertex_count": len(col.vertices),
                      "bounds_min": list(col.bounds[0]), "bounds_max": list(col.bounds[1]),
                      "classes": dict(CLASSES), "class_kinds": dict(CLASS_KINDS),
                      "authority": "authoritative static collision; exported from the same final meshes and "
                                   "world transforms as visual/map.glb"}
    manifest = build_manifest(name, area, sources, cast("str", elevation[0]["vertical_datum"]), files,
                              collision_info, hf_info,
                              objects, probes, {k: len(v) for k, v in edit_lists.items()}, len(warnings),
                              blender_version=blender_version, created_utc=created_utc,
                              passage_probes=passage_probes, schema_version=schema_version,
                              asset_notices=asset_notices)
    secrets = find_secrets(manifest, "manifest")
    if secrets:
        raise PackageError("refusing to write the package: " + secrets_message("manifest", secrets))
    return members, manifest, probes


# --- validation ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.manifest: Manifest | None = None
        self.package_id: str | None = None
        self.collision: Collision | None = None
        self.winding: dict[str, WindingStats] = {}
        self.strict = False

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        s = "VALID" if self.ok else "INVALID"
        lines = [f"{s}: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"]
        if self.package_id and self.ok:
            lines.append(f"package_id {self.package_id}")
        lines += [f"ERROR: {e}" for e in self.errors]
        lines += [f"warning: {w}" for w in self.warnings]
        return "\n".join(lines)


_ZIP_ERRORS = (zipfile.BadZipFile, zlib.error, EOFError, OSError, ValueError, RuntimeError, NotImplementedError,
               OverflowError, MemoryError)


def _member_label(name: str, i: int) -> str:
    """A zip entry or listed path in diagnostics: the contract's own member paths verbatim, anything else
    by position only (raw strings from the package are never echoed)."""
    return repr(name) if name == MANIFEST or name in MEMBERS else f"#{i}"


def validate_package(path: str | PathLike[str], strict: bool = False) -> ValidationResult:
    """Validate a package file; never raises for malformed input (errors are collected).

    ``strict`` is the exporter's mode (used by :func:`write_package`): on top of the consumer checks, each
    node's visual and collision triangles must correspond one-to-one with the same winding.
    ``package_id`` is published only if the package is valid; after any error it is None.

    Diagnostics never echo strings taken from the package (entry and object names, JSON keys, exception
    text that may quote them): they refer to entries by index or by the contract's fixed member paths."""
    r = ValidationResult()
    r.strict = strict
    try:
        with zipfile.ZipFile(path, "r") as z:
            _validate_zip(z, r)
    except _ZIP_ERRORS as e:
        # zipfile messages can quote entry names from the archive; only the OS reason (no file name) is kept
        reason = f" ({e.strerror})" if isinstance(e, OSError) and isinstance(e.strerror, str) else ""
        r.errors.append(f"not a readable package: {type(e).__name__}{reason}")
    except PackageError as e:
        r.errors.append(str(e))
    if r.errors:
        r.package_id = None
    return r


def _validate_zip(z: zipfile.ZipFile, r: ValidationResult) -> None:
    infos = z.infolist()
    if len(infos) > MAX_ENTRIES:
        r.errors.append(f"too many entries ({len(infos)} > {MAX_ENTRIES})")
        return
    names: dict[str, zipfile.ZipInfo] = {}
    lowered: set[str] = set()
    position: dict[str, int] = {}
    total = 0
    for i, zi in enumerate(infos):
        oname = zi.orig_filename
        tag = f"entry {_member_label(oname, i)}"
        if not safe_member_name(oname) or oname != zi.filename:
            r.errors.append(f"unsafe entry name ({tag})")
        if oname.lower() in lowered:
            r.errors.append(f"duplicate entry ({tag}; names differ at most in case)")
        lowered.add(oname.lower())
        names[oname] = zi
        position.setdefault(oname, i)
        mode = (zi.external_attr >> 16) & 0o170000
        if zi.is_dir() or (mode and mode != stat.S_IFREG):
            r.errors.append(f"{tag} is not a regular file (directory or symlink)")
        if zi.flag_bits & 0x1:
            r.errors.append(f"{tag} is encrypted")
        if zi.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            r.errors.append(f"{tag} uses unsupported compression {zi.compress_type}")
        total += zi.file_size
        if zi.file_size and (zi.compress_size == 0 or zi.file_size / zi.compress_size > MAX_RATIO):
            r.errors.append(f"{tag} compression ratio exceeds {MAX_RATIO}")
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

    def read(name: str) -> bytes:
        zi = names[name]
        with z.open(zi) as f:
            data = f.read(zi.file_size + 1)
        if len(data) != zi.file_size:
            raise PackageError(f"entry {_member_label(name, position[name])}: uncompressed size differs from its "
                               "zip header")
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
    man = cast("Manifest", m)   # indexed only after _check_manifest has validated the raw JSON
    r.manifest = man
    if not _check_version(m, r):
        return
    _check_manifest(m, r)
    if r.errors:
        return
    # files[] <-> archive members, one-to-one, then sizes and hashes
    listed = {f["path"]: (j, f) for j, f in enumerate(man["files"])}
    members = set(names) - {MANIFEST}

    def file_tag(p: str) -> str:
        return f"files[{listed[p][0]}]" + (f" ({p})" if p in MEMBERS else "")
    for p in sorted(members - set(listed), key=position.__getitem__):
        r.errors.append(f"unlisted file in package: entry {_member_label(p, position[p])}")
    for p in sorted(set(listed) - members, key=lambda q: listed[q][0]):
        r.errors.append(f"listed file missing from package: {file_tag(p)}")
    if r.errors:
        return
    blobs: dict[str, bytes] = {}
    for p, (j, f) in listed.items():
        tag = file_tag(p)
        if f["bytes"] != names[p].file_size:
            r.errors.append(f"{tag}: size {names[p].file_size} != manifest bytes {f['bytes']}")
            continue
        data = read(p)
        if f["sha256"] != sha256(data):
            r.errors.append(f"{tag}: SHA-256 mismatch")
            continue
        blobs[f["role"]] = data
    if r.errors:
        return
    _validate_payloads(man, blobs, r)
    if not r.errors:
        r.package_id = package_id_of(raw)   # only now does it bind the verified payload


def _check_version(m: Mapping[str, JsonValue], r: ValidationResult) -> bool:
    if m.get("schema") != PACKAGE_SCHEMA:
        r.errors.append(f"manifest: schema must be {PACKAGE_SCHEMA!r}")
        return False
    v = m.get("schema_version")
    mt = _SEMVER.fullmatch(v) if isinstance(v, str) else None
    if not mt:
        r.errors.append("manifest: schema_version must be a MAJOR.MINOR.PATCH string")
        return False
    if mt.group(1) != PACKAGE_SCHEMA_VERSION.split(".")[0]:
        r.errors.append(f"manifest: unsupported schema major version {mt.group(1)} (expected "
                        f"{PACKAGE_SCHEMA_VERSION.split('.')[0]})")
        return False
    return True


def _check_manifest(m: Mapping[str, JsonValue], r: ValidationResult) -> None:
    err = r.errors.append

    # Any: the locals below are untrusted JSON values; each is checked by the following need(...) before use, and
    # the checks tolerate any JSON type (a precise type would need isinstance branches that change what is reported)
    def need(cond: object, msg: str) -> object:
        if not cond:
            err("manifest: " + msg)
        return cond

    need(isinstance(m.get("name"), str) and m["name"], "name must be a non-empty string")
    need(is_utc_timestamp(m.get("created_utc")),
         "created_utc must be an ISO-8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    g: Any = m.get("generator")
    need(isinstance(g, dict) and isinstance(g.get("name"), str) and isinstance(g.get("version"), str)
         and (g.get("blender") is None or isinstance(g.get("blender"), str)),
         "generator must be {name, version, blender: string|null}")
    geo: Any = m.get("georeference")
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
    a: Any = m.get("area")
    if need(isinstance(a, dict), "area missing"):
        need(_num(a.get("width_m")) and a["width_m"] > 0 and _num(a.get("height_m")) and a["height_m"] > 0,
             "area.width_m/height_m must be positive")
        need(_vec(a.get("local_rect_m"), 4), "area.local_rect_m must be 4 numbers")
        bb = a.get("geographic_bbox_deg")
        need(isinstance(bb, dict) and all(_num(bb.get(k)) for k in ("south", "west", "north", "east")),
             "area.geographic_bbox_deg must have south/west/north/east")
    ax: Any = m.get("axes")
    need(isinstance(ax, dict) and ax.get("map_from_gltf") == MAP_FROM_GLTF and ax.get("map_from_unity") == MAP_FROM_UNITY,
         f"axes.map_from_gltf must be {MAP_FROM_GLTF} and axes.map_from_unity {MAP_FROM_UNITY}")
    files: Any = m.get("files")
    if need(isinstance(files, list), "files must be an array"):
        seen_paths: set[str] = set()
        seen_roles: set[str] = set()
        for i, f in enumerate(files):
            loc = f"files[{i}]"
            if not (isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("role"), str)
                    and isinstance(f.get("media_type"), str) and isinstance(f.get("sha256"), str)
                    and re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) and isinstance(f.get("bytes"), int)
                    and not isinstance(f["bytes"], bool) and f["bytes"] >= 0):
                err(f"manifest: {loc} must be {{path, role, media_type: strings, sha256: 64 lowercase hex digits, "
                    "bytes: count}")
                continue
            p = f["path"]
            if not safe_member_name(p) or p == MANIFEST:
                err(f"manifest: {loc}.path must be a safe relative member path other than {MANIFEST!r}")
                continue
            if p.lower() in seen_paths:
                err(f"manifest: {loc}.path lists a member path twice")
            seen_paths.add(p.lower())
            if p in MEMBERS:
                role, media_type, _ = MEMBERS[p]
                if f["role"] != role:
                    err(f"manifest: {loc} ({p}) must have role {role!r}")
                elif f["media_type"] != media_type:
                    r.warnings.append(f"{loc} ({p}): media_type is not the expected {media_type!r}")
                if role in seen_roles:
                    err(f"manifest: role {role!r} listed twice")
                seen_roles.add(role)
            else:
                if f["role"] in ROLE_PATHS:
                    err(f"manifest: {loc}: role {f['role']!r} must use path {ROLE_PATHS[f['role']]!r}")
                else:
                    r.warnings.append(f"{loc}: unknown package member ignored")
        for p, (role, _, required) in MEMBERS.items():
            if required and role not in seen_roles:
                err(f"manifest: required member {p} (role {role!r}) not listed")
    vis: Any = m.get("visual")
    need(isinstance(vis, dict) and vis.get("path") == "visual/map.glb", "visual.path must be 'visual/map.glb'")
    c: Any = m.get("collision")
    if need(isinstance(c, dict), "collision missing"):
        expect = {"path": "collision/map.mbcol", "format": "mbcol", "version": COLLISION_FORMAT_VERSION,
                  "frame": "map", "winding": "ccw_outward", "classes": CLASSES, "class_kinds": CLASS_KINDS}
        for k, v in expect.items():
            need(c.get(k) == v, f"collision.{k} must be {v!r}")
        need(isinstance(c.get("triangle_count"), int) and isinstance(c.get("vertex_count"), int),
             "collision.triangle_count/vertex_count missing")
        need(_vec(c.get("bounds_min")) and _vec(c.get("bounds_max")), "collision.bounds_min/max missing")
    hf: Any = m.get("heightfield", None)
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
    objs: Any = m.get("objects")
    if need(isinstance(objs, list) and objs, "objects must be a non-empty array"):
        for i, o in enumerate(objs):
            if not (isinstance(o, dict) and isinstance(o.get("name"), str) and isinstance(o.get("mb_id"), str)
                    and isinstance(o.get("class"), str) and o["class"] in CLASSES and o.get("collision") is True
                    and isinstance(o.get("provenance"), dict)):
                err(f"manifest: objects[{i}] must be {{name, mb_id: strings, class: one of {sorted(CLASSES)}, "
                    "collision: true, provenance: object}")
    need(isinstance(m.get("orientation_probes"), list) and len(cast("list[JsonValue]", m["orientation_probes"])) <= PROBE_MAX,
         f"orientation_probes must be an array of at most {PROBE_MAX}")
    for msg in passage_probe_problems(m.get("passage_probes")):
        err("manifest: " + msg)
    srcs: Any = m.get("sources")
    if need(isinstance(srcs, list) and srcs, "sources must be a non-empty array"):
        for i, s in enumerate(srcs):
            if not (isinstance(s, dict) and s.get("kind") in ("elevation", "features")
                    and isinstance(s.get("provider"), str) and s["provider"]
                    and isinstance(s.get("license"), dict) and s["license"]
                    and isinstance(s.get("attribution"), str)):
                err(f"manifest: sources[{i}] needs kind (elevation|features), provider, license {{...}} and "
                    "attribution")
                break
            lic = s["license"]
            if (not all(isinstance(lic.get(k), str) for k in LICENSE_NOTICE_KEYS if k in lic)
                    or not any(lic.get(k) for k in LICENSE_TEXT_KEYS)):
                err(f"manifest: sources[{i}].license must declare a licence identifier, name or text "
                    f"({'/'.join(LICENSE_TEXT_KEYS)}) and an optional url, all strings")
                break
        else:
            if not any(s["kind"] == "elevation" for s in srcs):
                err("manifest: no elevation source (vertical datum provenance missing)")
    ed: Any = m.get("edits")
    if "asset_notices" in m:
        for msg in asset_notice_problems(m["asset_notices"]):
            err("manifest: " + msg)
    need(isinstance(ed, dict) and all(isinstance(ed.get(k), int) and not isinstance(ed.get(k), bool)
                                      and ed[k] >= 0 for k in EDIT_KEYS),
         "edits must be {duplicated, user_added, removed} counts")
    wc: Any = m.get("warnings_count")
    need(isinstance(wc, int) and not isinstance(wc, bool) and wc >= 0, "warnings_count must be a count")
    secrets = find_secrets(m, "manifest")
    if secrets:
        err(secrets_message("manifest", secrets))


def _aabb(points: Iterable[Sequence[float]]) -> list[float]:
    xs, ys, zs = zip(*points)
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def _payload_secrets(r: ValidationResult, where: str, obj: object) -> None:
    """The manifest's credential policy, applied to a parsed JSON payload member (never echoes values)."""
    hits = find_secrets(obj, "$")
    if hits:
        r.errors.append(secrets_message(where, hits))


def _validate_payloads(m: Manifest, blobs: Mapping[str, bytes], r: ValidationResult) -> None:
    try:
        col = read_collision(blobs["collision"])
    except PackageError as e:
        r.errors.append(str(e))
        return
    r.collision = col
    _payload_secrets(r, "collision/map.mbcol object table", col.objects)
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
    r.errors.extend(collision_orientation_problems(col))
    _check_objects(m, col, r)
    _check_passage_probes(m, col, r)
    try:
        gl, nodes = read_glb(blobs["visual"])
    except PackageError as e:
        r.errors.append(str(e))
        return
    _payload_secrets(r, "visual/map.glb JSON chunk", gl)
    _check_asset_provenance(m, glb_image_sha256s(blobs["visual"]), r)
    _check_binding(m, col, nodes, r)
    if "heightfield" in blobs:
        _check_heightfield(cast("HeightfieldManifest", m["heightfield"]), blobs["heightfield"], col, r)
    _check_notices(m, blobs["notices"], r)
    if "report" in blobs:
        _check_report(m, blobs["report"], r)


def _check_passage_probes(m: Manifest, col: Collision, r: ValidationResult) -> None:
    """Each probe's feature must name a manifest object; each probe capsule is re-checked against the final
    collision (a blocked probe is a warning: the free path the generator intended is obstructed). The probes
    share one query budget; running out is a warning, not an error. Names only indices, never strings."""
    probes = m["passage_probes"]
    ids = {o["mb_id"] for o in m["objects"]}
    for i, p in enumerate(probes):
        if p["feature"] not in ids:
            r.errors.append(f"passage_probes[{i}].feature does not match any manifest object mb_id")
    left = PASSAGE_QUERY_BUDGET
    for i, p in enumerate(probes):
        try:
            res = capsule_hits(col, p["path_map"], p["radius_m"], max_work=left, result=True)
        except LimitError:
            r.warnings.append(f"passage_probes: query budget of {PASSAGE_QUERY_BUDGET} unit(s) exhausted; probes "
                              f"{i}..{len(probes) - 1} were not checked")
            return
        left -= res.work
        if res.objects:
            more = f" (and {len(res.objects) - 1} more)" if len(res.objects) > 1 else ""
            r.warnings.append(f"passage probe {i} is blocked by collision object #{res.objects[0]}{more}")


def _check_objects(m: Manifest, col: Collision, r: ValidationResult) -> None:
    # names and identities are compared, never echoed: manifest objects by objects[i], collision by #k
    man: dict[str, tuple[int, ObjectEntry]] = {}
    for i, o in enumerate(m["objects"]):
        if o["name"] in man:
            r.errors.append(f"manifest: objects[{i}] repeats the name of objects[{man[o['name']][0]}]")
        man.setdefault(o["name"], (i, o))
    ids: dict[str, int] = {}
    for i, o in enumerate(m["objects"]):
        if o["mb_id"] in ids:
            r.errors.append(f"duplicate object identity: objects[{ids[o['mb_id']]}] and objects[{i}] share an mb_id")
        ids.setdefault(o["mb_id"], i)
        base = o["mb_id"].split("~", 1)[0]
        if o["mb_id"].startswith("user:"):
            if o["mb_id"] != f"user:{o['name']}":
                r.warnings.append(f"objects[{i}]: user identity mb_id is not 'user:<object name>'")
        elif "~" in o["mb_id"]:
            if o["mb_id"] != f"{base}~{o['name']}" or not _MB_ID.fullmatch(base):
                r.warnings.append(f"objects[{i}]: duplicate identity mb_id is not '<generated id>~<object name>'")
        elif not _MB_ID.fullmatch(o["mb_id"]):
            r.warnings.append(f"objects[{i}]: unrecognised mb_id form")
    table = {e["name"]: (k, e) for k, e in enumerate(col.objects)}
    for name in sorted(set(table) - set(man), key=lambda n: table[n][0]):
        r.errors.append(f"collision object #{table[name][0]} has no manifest object of the same name")
    for name in sorted(set(man) - set(table), key=lambda n: man[n][0]):
        r.errors.append(f"manifest objects[{man[name][0]}] has no collision object of the same name")
    for name in sorted(set(man) & set(table), key=lambda n: man[n][0]):
        (i, o), (k, e) = man[name], table[name]
        if o["mb_id"] != e["mb_id"] or o["class"] != e["class"]:
            r.errors.append(f"objects[{i}] / collision object #{k}: mb_id/class differ between manifest and "
                            "collision")


def _check_binding(m: Manifest, col: Collision, nodes: Sequence[GlbNode], r: ValidationResult) -> None:
    # glTF nodes are named by node index and collision objects by table index, never by their names
    by_name: dict[str, GlbNode] = {}
    for n in nodes:
        if n.triangles:
            if n.name in by_name:
                r.errors.append(f"glb: glTF node #{n.index} repeats the name of glTF node #{by_name[n.name].index}")
            by_name.setdefault(n.name, n)
    table = {e["name"]: k for k, e in enumerate(col.objects)}
    for name in sorted(set(by_name) - set(table), key=lambda n: by_name[n].index):
        r.errors.append(f"glTF node #{by_name[name].index} has triangles but no collision object of the same name "
                        "(visible but not collidable)")
    for k, e in enumerate(col.objects):
        tag = f"collision object #{k}"
        node = by_name.get(e["name"])
        if node is None:
            r.errors.append(f"{tag} has no glTF node with triangles of the same name")
            continue
        tag = f"collision object #{k} / glTF node #{node.index}"
        vis: list[Tri] = [(gltf_to_map(a), gltf_to_map(b), gltf_to_map(c)) for a, b, c in node.triangles]
        ctris = col.object_triangles(e)
        va = _aabb([p for t in vis for p in t])
        ca = _aabb([p for t in ctris for p in t])
        size = max(ca[3] - ca[0], ca[4] - ca[1], ca[5] - ca[2])
        tol = AABB_TOL_M + AABB_TOL_REL * size
        if any(abs(x - y) > tol for x, y in zip(va, ca)):
            r.errors.append(f"visual/collision AABB mismatch for {tag}: glTF {[round(v, 3) for v in va]} vs "
                            f"collision {[round(v, 3) for v in ca]}")
            continue
        st = match_winding(ctris, vis)
        r.winding[e["name"]] = st
        if st["reversed"]:
            r.errors.append(f"visual/collision winding mismatch for {tag}: {st['reversed']} collision "
                            f"triangle(s) match visual triangles with reversed winding, e.g. "
                            f"{st['reversed_examples'][0]}")
        elif st["considered"] and st["same"] < WINDING_MIN_MATCHED * st["considered"]:
            r.warnings.append(f"{tag}: only {st['same']}/{st['considered']} collision triangles have an "
                              f"unambiguous visual match ({st['ambiguous']} ambiguous, {st['unmatched']} unmatched)")
        if st["work_exhausted"]:
            r.warnings.append(f"{tag}: winding check stopped at its work budget; {st['unchecked']} "
                              "collision triangle(s) were not checked (not counted as ties)")
        if r.strict:
            one = match_one_to_one(ctris, vis)
            if one["work_exhausted"]:
                r.errors.append(f"export binding for {tag}: cannot verify binding: work budget exhausted before "
                                "the one-to-one visual/collision triangle correspondence was established")
            elif one["reversed"] or one["unmatched"] or one["visual_only"]:
                r.errors.append(f"export binding for {tag}: visual and collision triangles must correspond "
                                f"one-to-one with the same winding; {one['unmatched']} collision triangle(s) have "
                                f"no free visual counterpart, {one['reversed']} only a reversed one, and "
                                f"{one['visual_only']} visual triangle(s) have no collision counterpart")
        else:
            vst = match_winding(vis, ctris)
            if vst["unmatched"]:
                r.warnings.append(f"{tag}: {vst['unmatched']} visual triangle(s) have no collision "
                                  "counterpart (visible but not collidable)")
            if vst["work_exhausted"]:
                r.warnings.append(f"{tag}: visual-only triangle check stopped at its work budget; "
                                  f"{vst['unchecked']} visual triangle(s) were not checked")
    _check_probes(m, col, by_name, r)


def _check_probes(m: Manifest, col: Collision, by_name: Mapping[str, GlbNode], r: ValidationResult) -> None:
    probes = m["orientation_probes"]
    expected = select_orientation_probes(col)
    table = {e["name"]: (k, e) for k, e in enumerate(col.objects)}
    if not probes:
        r.warnings.append(PROBES_UNAVAILABLE)
        if expected:
            r.errors.append(f"orientation_probes is empty although collision object #{table[expected[0]['node']][0]} "
                            "has a qualifying vertex")
        return
    if len(probes) != len(expected):
        r.errors.append(f"orientation_probes has {len(probes)} probe(s); {len(expected)} node(s) qualify (max "
                        f"{PROBE_MAX})")
    seen: set[str] = set()
    n_non_terrain = 0
    for k, p in enumerate(probes):
        tag = f"orientation probe {k}"
        keys = ("node", "point_map", "point_gltf", "point_unity_x_negated", "triangle_map", "normal_map",
                "normal_unity_x_negated")
        raw: Mapping[str, object] = p   # the shape is checked here, key by key
        if not (isinstance(raw, dict) and all(key in raw for key in keys) and isinstance(raw["node"], str)
                and all(_vec(raw[key]) for key in keys[1:] if key != "triangle_map")
                and isinstance(raw["triangle_map"], list) and len(raw["triangle_map"]) == 3
                and all(_vec(q) for q in raw["triangle_map"])):
            r.errors.append(f"{tag}: needs {list(keys)} with 3-vectors")
            continue
        node, pm, nm = p["node"], p["point_map"], p["normal_map"]
        if node in seen:
            r.errors.append(f"{tag}: more than one probe for the node")
        seen.add(node)
        if node not in table or node not in by_name:
            r.errors.append(f"{tag}: node does not exist in both glTF and collision")
            continue
        ci, entry = table[node]
        tag = f"orientation probe {k} (collision object #{ci})"
        n_non_terrain += entry["class"] != "terrain"
        if (_dist(p["point_gltf"], map_to_gltf(cast("Vec3", pm))) > 1e-6
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
        reason = verify_probe_in_unity(cast(OrientationProbe, p), unity_import(by_name[node].triangles))   # shape checked above
        if reason:
            r.errors.append(f"{tag} fails against the visual mesh: {reason}")
    if n_non_terrain != sum(1 for e in expected if table[e["node"]][1]["class"] != "terrain"):
        r.errors.append("orientation_probes must prefer non-terrain nodes that have a qualifying vertex")


def _check_heightfield(info: HeightfieldManifest, data: bytes, col: Collision, r: ValidationResult) -> None:
    try:
        hf = read_heightfield(data)
    except PackageError as e:
        r.errors.append(str(e))
        return
    nan_cells = sum(1 for row in hf["z"] for v in row if math.isnan(v))
    if (info["nx"], info["ny"], info["nan_cells"]) != (hf["nx"], hf["ny"], nan_cells) or any(
            abs(a - b) > 1e-9 for a, b in ((info["x0"], hf["x0"]), (info["y0"], hf["y0"]),
                                           (info["spacing_m"], hf["spacing"]))):
        r.errors.append("heightfield: manifest nx/ny/x0/y0/spacing_m/nan_cells differ from the file")
        return
    try:
        want = rasterize_heightfield(col.class_triangles("terrain"), hf["x0"], hf["y0"], hf["spacing"], hf["nx"],
                                     hf["ny"])
    except LimitError as e:
        r.errors.append(f"heightfield: cannot be verified: {e}")
        return
    for j in range(hf["ny"]):
        for i in range(hf["nx"]):
            a, b = hf["z"][j][i], want[j][i]
            if math.isnan(a) != math.isnan(b) or (not math.isnan(a) and abs(a - b) > HEIGHTFIELD_TOL_M):
                r.errors.append(f"heightfield: value at row {j}, column {i} is not the maximum z of the terrain "
                                f"collision triangles ({a} vs {b})")
                return


def _check_asset_provenance(m: Manifest, image_hashes: Sequence[str], r: ValidationResult) -> None:
    listed = {h for a in m.get("asset_notices", []) for h in a["sha256"]}
    for i, h in enumerate(image_hashes):
        if h not in listed:
            r.errors.append(f"glb: texture without provenance: image #{i} (SHA-256 {h}) is not listed in "
                            "any asset_notices[].sha256")
    present = set(image_hashes)
    for k, a in enumerate(m.get("asset_notices", [])):
        for h in a["sha256"]:
            if h not in present:
                r.warnings.append(f"asset_notices[{k}] lists SHA-256 {h}, which is not an image in visual/map.glb")


def _check_notices(m: Manifest, data: bytes, r: ValidationResult) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        r.errors.append("NOTICES.txt is not UTF-8")
        return
    for k, a in enumerate(m.get("asset_notices", [])):
        if a["attribution"] not in text:
            r.errors.append(f"NOTICES.txt lacks the attribution of asset_notices[{k}]")
        lic = cast("Mapping[str, str]", a["license"])
        for key in LICENSE_NOTICE_KEYS:
            if lic.get(key) and lic[key] not in text:
                r.errors.append(f"NOTICES.txt lacks the licence {key} of asset_notices[{k}] "
                                f"(asset_notices[{k}].license.{key} must appear verbatim)")
    for k, s in enumerate(m["sources"]):
        if s["attribution"] and s["attribution"] not in text:
            r.errors.append(f"NOTICES.txt lacks the attribution of sources[{k}]")
        elif not s["attribution"]:
            r.warnings.append(f"sources[{k}] has no attribution text")
        lic = cast("Mapping[str, str]", s["license"])
        for key in LICENSE_NOTICE_KEYS:
            if lic.get(key) and lic[key] not in text:
                r.errors.append(f"NOTICES.txt lacks the licence {key} of sources[{k}] (sources[{k}].license.{key} "
                                "must appear verbatim)")


def _check_report(m: Manifest, data: bytes, r: ValidationResult) -> None:
    try:
        rep = strict_json(data, "report.json")
    except PackageError as e:
        r.errors.append(str(e))
        return
    _payload_secrets(r, "report.json", rep)
    if not isinstance(rep, dict) or not isinstance(rep.get("counts"), dict) or not all(
            isinstance(rep.get(k), list) for k in REPORT_KEYS[1:]):
        r.errors.append(f"report.json must be an object with {list(REPORT_KEYS)}")
        return
    warns = cast("list[JsonValue]", rep["warnings"])
    if m["warnings_count"] != len(warns):
        r.errors.append(f"warnings_count {m['warnings_count']} != {len(warns)} warnings in report.json")
    ed = rep.get("edits")
    if ed is not None:
        if not (isinstance(ed, dict) and all(isinstance(ed.get(k), list) for k in EDIT_KEYS)):
            r.errors.append("report.json edits must list duplicated, user_added and removed")
        elif any(len(cast("list[JsonValue]", ed[k])) != m["edits"][k] for k in EDIT_KEYS):
            r.errors.append("report.json edits lists do not match the manifest edits counts")
