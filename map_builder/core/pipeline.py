"""End-to-end pipeline glue shared by the Blender add-on and headless tools.

Nothing here substitutes data on failure: every acquisition, generation or export error is
raised to the caller (no flat terrain, no empty feature set, no partial package).
"""

import copy
import hashlib
import json
import math

from .cache import DiskCache, NullCache
from .collision import (CLASSES, ColObject, heightfield_layout, is_degenerate, rasterize_heightfield,
                        read_collision, write_collision, write_heightfield)
from .dem import COPERNICUS_BASE_URL, fetch_copernicus, grid_layout, load_local_elevation
from .errors import PackageError
from .generate import MATERIALS, PlanOptions, build_plan
from .glb import node_scale, write_glb
from .http import HttpClient, redact
from .osm import DEFAULT_OVERPASS_URL, OSM_ATTRIBUTION, OSM_LICENSE, classify, fetch_overpass, load_osm_file
from .package import assemble, write_package

ELEVATION_SOURCES = ("copernicus", "file")
OSM_SOURCES = ("overpass", "file")


class Settings:
    """Acquisition/generation settings. Unknown keywords are rejected (a typo must not silently fall back
    to a default data source)."""

    FIELDS = {
        "elevation_source": "copernicus",       # copernicus | file
        "elevation_file": "",
        "elevation_crs": "EPSG:4326",
        "elevation_vertical_datum": "user-declared (unknown)",
        "elevation_license": "",
        "osm_source": "overpass",               # overpass | file
        "osm_file": "",
        "overpass_url": DEFAULT_OVERPASS_URL,
        "copernicus_url": COPERNICUS_BASE_URL,
        "terrain_spacing": 10.0,
        "cache_dir": "",
        # caching a non-default endpoint needs both the caller's assertion that its terms permit caching and
        # a credential-free dataset id (endpoint URLs never become cache identity)
        "allow_cache_override": False,
        "elevation_cache_dataset_id": None,
        "osm_cache_dataset_id": None,
        "heightfield_spacing": None,
        "plan_options": None,
    }

    def __init__(self, **kw):
        unknown = set(kw) - set(self.FIELDS)
        if unknown:
            raise TypeError(f"unknown settings: {sorted(unknown)}")
        for k, v in self.FIELDS.items():
            setattr(self, k, kw.get(k, v))
        if self.elevation_source not in ELEVATION_SOURCES:
            raise ValueError(f"elevation_source must be one of {ELEVATION_SOURCES}")
        if self.osm_source not in OSM_SOURCES:
            raise ValueError(f"osm_source must be one of {OSM_SOURCES}")
        if self.elevation_source == "file" and not self.elevation_file:
            raise ValueError("elevation_source 'file' needs elevation_file")
        if self.osm_source == "file" and not self.osm_file:
            raise ValueError("osm_source 'file' needs osm_file")
        self.terrain_spacing = float(self.terrain_spacing)
        if not (math.isfinite(self.terrain_spacing) and self.terrain_spacing > 0):
            raise ValueError("terrain_spacing must be a positive finite number")
        if self.heightfield_spacing is not None:
            self.heightfield_spacing = float(self.heightfield_spacing)
            if not (math.isfinite(self.heightfield_spacing) and self.heightfield_spacing > 0):
                raise ValueError("heightfield_spacing must be a positive finite number")
        self.plan_options = self.plan_options or PlanOptions()

    def __repr__(self):
        shown = {k: getattr(self, k) for k in self.FIELDS if k != "plan_options"}
        shown["overpass_url"] = redact(self.overpass_url)
        shown["copernicus_url"] = redact(self.copernicus_url)
        return f"Settings({shown})"


def acquire(area, settings, client=None, progress=None):
    """Returns (ElevationGrid, Classified, sources list). Raises on any failure; never substitutes data.
    The terrain grid limit is checked first, before any file or network access. The heightfield limit
    belongs to package export (see :func:`build_package`); acquisition and plans produce no heightfield."""
    grid_layout(area, settings.terrain_spacing)
    client = client or HttpClient()
    cache = DiskCache(settings.cache_dir) if settings.cache_dir else NullCache()
    if settings.elevation_source == "file":
        grid = load_local_elevation(area, settings.elevation_file, settings.terrain_spacing, settings.elevation_crs,
                                    settings.elevation_vertical_datum, settings.elevation_license, progress)
    else:
        grid = fetch_copernicus(area, client, settings.terrain_spacing, cache, settings.copernicus_url, progress,
                                allow_cache_override=settings.allow_cache_override,
                                cache_dataset_id=settings.elevation_cache_dataset_id)
    if settings.osm_source == "file":
        osm = load_osm_file(settings.osm_file)
    else:
        osm = fetch_overpass(area, client, settings.overpass_url, cache,
                             allow_cache_override=settings.allow_cache_override,
                             cache_dataset_id=settings.osm_cache_dataset_id)
    classified = classify(osm, area)
    return grid, classified, [dict(grid.provenance), osm_source_entry(osm)]


def osm_source_entry(osm):
    src = {"kind": "features", "provider": osm.source.get("provider"), "product": "OpenStreetMap",
           "license": OSM_LICENSE, "attribution": OSM_ATTRIBUTION, "osm_base_timestamp": osm.timestamp}
    for k, v in osm.source.items():
        if k == "query":
            src["query_sha256"] = hashlib.sha256(v.encode("utf-8")).hexdigest()
        elif k != "provider":
            src[k] = v
    return src


def plan_sources_json(sources):
    return json.dumps(sources, sort_keys=True)


def resolve_identities(entries, generated_ids=None):
    """entries: [(object_name, mb_id | None, mb_class | None)] -> (resolved [(name, mb_id, class)], edits).

    docs/PACKAGE_FORMAT.md "Object identity": objects are processed in name order. The first object
    carrying a generated id keeps it; later copies get ``<id>~<object name>`` (duplicated). Objects
    without an id, or with one that is not a generated id, are user additions ``user:<object name>``.
    Generated ids that are no longer present are removals. Unknown classes become ``user``.
    ``generated_ids``: ids of the generated scene (None: every non-empty id counts as generated).
    """
    names = [e[0] for e in entries]
    if len(set(names)) != len(names):
        raise PackageError("object names must be unique (they bind glTF nodes to collision objects)")
    generated = None if generated_ids is None else set(generated_ids)
    seen = set()
    resolved = []
    edits = {"duplicated": [], "user_added": [], "removed": []}
    for name, mb_id, cls in sorted(entries, key=lambda e: e[0]):
        if not isinstance(name, str) or not name:
            raise PackageError("object names must be non-empty strings")
        cls = cls if cls in CLASSES else "user"
        if not mb_id or not isinstance(mb_id, str) or (generated is not None and mb_id not in generated):
            mb_id = f"user:{name}"
            edits["user_added"].append(name)
        elif mb_id in seen:
            edits["duplicated"].append({"object": name, "source_id": mb_id})
            mb_id = f"{mb_id}~{name}"
        else:
            seen.add(mb_id)
        resolved.append((name, mb_id, cls))
    ids = [r[1] for r in resolved]
    if len(set(ids)) != len(ids):
        raise PackageError("object identities are not unique after resolution")
    edits["removed"] = sorted((generated or set()) - seen)
    return resolved, edits


def object_transform(location=(0.0, 0.0, 0.0), rotation_z=0.0, scale=1.0):
    """(point -> world point, mirrored) for the map-frame object transform T * Rz * S. It is the same
    transform :func:`write_glb` stores as the node TRS, so collision and visuals share world matrices."""
    sx, sy, sz = node_scale(scale)
    c, s = math.cos(rotation_z), math.sin(rotation_z)
    lx, ly, lz = location

    def apply(p):
        x, y, z = p[0] * sx, p[1] * sy, p[2] * sz
        return (c * x - s * y + lx, s * x + c * y + ly, z + lz)
    return apply, sx * sy * sz < 0


def collision_object(name, mb_id, cls, mesh, location=(0.0, 0.0, 0.0), rotation_z=0.0, scale=1.0):
    """World-space collision from the final mesh and its transform. A mirroring transform (negative
    determinant) reverses winding, exactly like the glTF rule, so front faces stay CCW outward."""
    apply, mirrored = object_transform(location, rotation_z, scale)
    verts = [apply(v) for v in mesh.vertices]
    tris = [(a, c, b) if mirrored else (a, b, c) for a, b, c in mesh.triangles()]
    return ColObject(name, mb_id, cls, verts, tris)


def heightfield_from_collision(col, area, spacing):
    """(mbhf bytes, manifest info) from the final terrain-class triangles as stored (float32), or None."""
    tris = col.class_triangles("terrain")
    if not tris:
        return None
    x0, y0, nx, ny = heightfield_layout(area.half, spacing)
    z = rasterize_heightfield(tris, x0, y0, spacing, nx, ny)
    holes = sum(1 for row in z for h in row if math.isnan(h))
    data = write_heightfield(z, x0, y0, spacing)
    return data, {"nx": nx, "ny": ny, "x0": x0, "y0": y0, "spacing_m": spacing, "nan_cells": holes,
                  "rule": "max z of the final terrain-class collision triangles at each grid point; NaN = no terrain"}


def heightfield_from_objects(col_objects, area, spacing):
    return heightfield_from_collision(read_collision(write_collision(col_objects)), area, spacing)


def export_package(path, name, area, sources, glb_bytes, col_objects, report, edits=None, blender_version=None,
                   heightfield_spacing=None, object_info=None, created_utc=None):
    """Write a validated package atomically. ``col_objects`` must come from the same final meshes and world
    transforms as ``glb_bytes``; ``object_info[name]['provenance']`` is copied to the manifest."""
    collision_bytes = write_collision(col_objects)
    col = read_collision(collision_bytes)
    hf = heightfield_from_collision(col, area, heightfield_spacing) if heightfield_spacing else None
    objects = []
    for o in col_objects:
        info = (object_info or {}).get(o.name, {})
        objects.append({"name": o.name, "mb_id": o.mb_id, "class": o.cls, "collision": True,
                        "provenance": dict(info.get("provenance") or {})})
    report = copy.deepcopy(dict(report or {}))
    report["export"] = {"objects": len(col_objects), "collision_triangles": col.triangle_count,
                        "collision_vertices": len(col.vertices),
                        "degenerate_triangles": sum(1 for t in range(col.triangle_count)
                                                    if is_degenerate(*col.triangle(t))),
                        "heightfield_nan_cells": hf[1]["nan_cells"] if hf else None}
    members, manifest, probes = assemble(name, area, sources, glb_bytes, collision_bytes, objects, heightfield=hf,
                                         report=report, edits=edits, blender_version=blender_version,
                                         created_utc=created_utc)
    result = write_package(path, members, manifest)
    return manifest, result


def plan_to_package(plan, path, name, sources, heightfield_spacing=None, generated_ids=None, created_utc=None):
    """Headless reference exporter (no Blender): plan geometry -> package. Visual nodes and collision
    objects are built from the same final meshes and the same transforms."""
    entries = [(o.name, o.mb_id, o.mb_class) for o in plan.objects]
    if generated_ids is None:
        generated_ids = [o.mb_id for o in plan.objects]
    resolved, edits = resolve_identities(entries, generated_ids)
    ident = {n: (i, c) for n, i, c in resolved}
    nodes, col_objects, info = [], [], {}
    for o in plan.objects:
        md = o.mesh if o.mesh is not None else plan.shared_meshes[o.mesh_key]
        mb_id, cls = ident[o.name]
        nodes.append({"name": o.name, "mesh": md, "location": o.location, "rotation_z": o.rotation_z,
                      "scale": o.scale, "extras": {"mb_id": mb_id, "mb_class": cls}})
        col_objects.append(collision_object(o.name, mb_id, cls, md, o.location, o.rotation_z, o.scale))
        info[o.name] = {"provenance": o.provenance}
    if plan.report.get("z_offset_m", plan.area.frame.z_offset) != plan.area.frame.z_offset:
        raise PackageError("plan z_offset_m differs from the area frame; regenerate the plan")
    glb_bytes = write_glb(nodes, MATERIALS, generator="map-builder headless")
    return export_package(path, name, plan.area, sources, glb_bytes, col_objects, plan.report, edits=edits,
                          heightfield_spacing=heightfield_spacing, object_info=info, created_utc=created_utc)


def generate_plan(area, settings, client=None, progress=None):
    grid, classified, sources = acquire(area, settings, client, progress)
    plan = build_plan(area, grid, classified, settings.plan_options)
    return plan, sources


def build_package(area, settings, path, name, client=None, progress=None, created_utc=None):
    """acquire -> plan -> validated package. Returns (manifest, ValidationResult).
    The heightfield layout (size limit and 2x2 minimum) is checked before any file or network access."""
    if settings.heightfield_spacing:
        heightfield_layout(area.half, settings.heightfield_spacing)
    plan, sources = generate_plan(area, settings, client, progress)
    return plan_to_package(plan, path, name, sources, heightfield_spacing=settings.heightfield_spacing,
                           created_utc=created_utc)
