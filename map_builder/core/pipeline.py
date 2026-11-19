"""End-to-end pipeline glue shared by the Blender add-on and headless tools.

Nothing here substitutes data on failure: every acquisition, generation or export error is
raised to the caller (no flat terrain, no empty feature set, no partial package). The one exception is
the optional second Overpass request that only widens the DSM correction mask: if it fails, the content
(fetched by the normal request) stands and the correction is skipped with a warning.
"""

import copy
import hashlib
import json
import math

from . import dsm
from .cache import DiskCache, NullCache
from .collision import (CLASSES, ColObject, heightfield_layout, is_degenerate, rasterize_heightfield,
                        read_collision, write_collision, write_heightfield)
from .dem import COPERNICUS_BASE_URL, fetch_copernicus, grid_layout, load_local_elevation
from .errors import CoverageError, FormatError, LimitError, NetworkError, PackageError
from .generate import MATERIALS, PlanOptions, build_plan
from .glb import node_scale, write_glb
from .http import HttpClient, redact
from .osm import (DEFAULT_OVERPASS_URL, OSM_ATTRIBUTION, OSM_FETCH_MARGIN_M, OSM_LICENSE, classify, fetch_overpass,
                  load_osm_file)
from .package import assemble, passage_probe_problems, write_package

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
        # licence/attribution the user declares for a local OSM-format file that is NOT OpenStreetMap data
        # (e.g. a hand-written synthetic fixture); None = the file is OpenStreetMap data under ODbL
        "osm_license": None,
        # DSM terrain correction (core/dsm.py): None = auto (on for the Copernicus surface model, off for a
        # local elevation file), True = on, False = off
        "dsm_correction": None,
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
        if self.osm_license is not None:
            if self.osm_source != "file":
                raise ValueError("osm_license applies only to a local OSM-format file; Overpass data is "
                                 "OpenStreetMap (ODbL)")
            if not (isinstance(self.osm_license, str) and self.osm_license.strip()):
                raise ValueError("osm_license must be a non-empty licence/attribution statement")
        self.terrain_spacing = float(self.terrain_spacing)
        if not (math.isfinite(self.terrain_spacing) and self.terrain_spacing > 0):
            raise ValueError("terrain_spacing must be a positive finite number")
        if self.heightfield_spacing is not None:
            self.heightfield_spacing = float(self.heightfield_spacing)
            if not (math.isfinite(self.heightfield_spacing) and self.heightfield_spacing > 0):
                raise ValueError("heightfield_spacing must be a positive finite number")
        if self.dsm_correction is not None and not isinstance(self.dsm_correction, bool):
            raise ValueError("dsm_correction must be None (auto), True or False")
        self.plan_options = self.plan_options or PlanOptions()

    def __repr__(self):
        shown = {k: getattr(self, k) for k in self.FIELDS if k != "plan_options"}
        shown["overpass_url"] = redact(self.overpass_url)
        shown["copernicus_url"] = redact(self.copernicus_url)
        return f"Settings({shown})"


def acquire(area, settings, client=None, progress=None):
    """Returns (ElevationGrid, Classified, sources list). Raises on any failure (except the DSM mask request,
    see below); never substitutes data.
    The terrain grid limit is checked first, before any file or network access. The heightfield limit
    belongs to package export (see :func:`build_package`); acquisition and plans produce no heightfield."""
    x0, y0, nx, ny = grid_layout(area, settings.terrain_spacing)
    client = client or HttpClient()
    cache = DiskCache(settings.cache_dir) if settings.cache_dir else NullCache()
    if settings.elevation_source == "file":
        grid = load_local_elevation(area, settings.elevation_file, settings.terrain_spacing, settings.elevation_crs,
                                    settings.elevation_vertical_datum, settings.elevation_license, progress)
    else:
        grid = fetch_copernicus(area, client, settings.terrain_spacing, cache, settings.copernicus_url, progress,
                                allow_cache_override=settings.allow_cache_override,
                                cache_dataset_id=settings.elevation_cache_dataset_id)
    mask_data = mask_query = None
    if settings.osm_source == "file":
        osm = load_osm_file(settings.osm_file)
    else:
        # The content is always the normal query (area + OSM_FETCH_MARGIN_M): the same query text and cache
        # key with the correction on or off, so the generated scene is the same either way. When the DSM
        # correction is enabled, a second request (the same query with a wider bbox) fetches every DSM mask
        # candidate the grid can use (selected against the grid extent, osm.classify mask_extent): the grid
        # may overshoot the area on the +x/+y sides by up to one spacing, plus the widest mask reach, a bridge
        # centreline up to dsm.BRIDGE_CANDIDATE_MARGIN_M away. Its elements that the normal response lacks are
        # mask candidates only (classify mask_data). If that request fails, the content stands and the
        # correction is skipped with a warning (Classified.mask_unavailable).
        fetch = dict(allow_cache_override=settings.allow_cache_override,
                     cache_dataset_id=settings.osm_cache_dataset_id)
        osm = fetch_overpass(area, client, settings.overpass_url, cache, margin_m=OSM_FETCH_MARGIN_M, **fetch)
        enabled, _ = dsm.resolve(settings.dsm_correction, grid.provenance)
        if enabled:
            overshoot = max(0.0, x0 + (nx - 1) * settings.terrain_spacing - area.half[0],
                            y0 + (ny - 1) * settings.terrain_spacing - area.half[1])
            margin = max(OSM_FETCH_MARGIN_M, float(math.ceil(overshoot + dsm.BRIDGE_CANDIDATE_MARGIN_M)))
            mask_query = {"purpose": "DSM terrain correction mask candidates only (nothing generated from it)",
                          "margin_m": margin}
            try:
                mask_data = fetch_overpass(area, client, settings.overpass_url, cache, margin_m=margin, **fetch)
            except (NetworkError, CoverageError, FormatError, LimitError) as exc:
                mask_query["error"] = str(exc)
            else:
                src = mask_data.source
                if "query" in src:
                    mask_query["query_sha256"] = hashlib.sha256(src["query"].encode("utf-8")).hexdigest()
                if "from_cache" in src:
                    mask_query["from_cache"] = src["from_cache"]
                mask_query["osm_base_timestamp"] = mask_data.timestamp
    s = grid.spacing
    classified = classify(osm, area, mask_extent=(grid.x0, grid.y0, grid.x0 + (grid.nx - 1) * s,
                                                  grid.y0 + (grid.ny - 1) * s), mask_data=mask_data,
                          max_mask_work=settings.plan_options.max_mask_validation_work)
    osm_entry = osm_source_entry(osm, settings.osm_license)
    if mask_query is not None:
        osm_entry["dsm_mask_query"] = mask_query
        if "error" in mask_query:
            classified.mask_unavailable = (f"the DSM mask request (OSM area + {mask_query['margin_m']:g} m) failed: "
                                           f"{mask_query['error']}")
    return grid, classified, [dict(grid.provenance), osm_entry]


def osm_source_entry(osm, declared_license=None):
    """Source entry for the features. ``declared_license``: the user's statement for a local OSM-format
    file that is not OpenStreetMap data (then no OpenStreetMap/ODbL attribution is claimed)."""
    if declared_license is None:
        src = {"kind": "features", "provider": osm.source.get("provider"), "product": "OpenStreetMap",
               "license": OSM_LICENSE, "attribution": OSM_ATTRIBUTION, "osm_base_timestamp": osm.timestamp}
    else:
        src = {"kind": "features", "provider": osm.source.get("provider"),
               "product": "user-declared OSM-format data (not OpenStreetMap)",
               "license": {"id": "user-declared", "name": declared_license}, "attribution": declared_license,
               "osm_base_timestamp": osm.timestamp}
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


def filter_passage_probes(probes, mb_ids, plan_ids=()):
    """Split passage probes into (kept, dropped_ids).

    ``mb_ids`` are the exported objects; ``plan_ids`` are the mb_ids of the original generation plan (the
    ``generated_ids`` recorded when the plan was built or loaded into Blender). A probe whose ``feature`` is
    in ``plan_ids`` but no longer among ``mb_ids`` (the feature was deleted in Blender) is dropped and
    reported by its id. Every other probe must be well formed (:func:`package.passage_probe_problems`) and
    reference an exported object; otherwise PackageError is raised, since a probe that never referenced a
    plan feature is a bug, not an edit. ``probes`` must be a list (the manifest/metadata value) or a tuple
    (a Python default such as ``()``); anything else, including None (a JSON null), is malformed. The
    messages never echo probe strings."""
    probes = list(probes) if isinstance(probes, tuple) else probes
    bad = passage_probe_problems(probes)
    if bad:
        raise PackageError("invalid passage probes: " + "; ".join(bad))
    mb_ids, plan_ids = set(mb_ids), set(plan_ids or ())
    kept, dropped = [], []
    for i, p in enumerate(probes):
        feature = p["feature"]
        if feature in mb_ids:
            kept.append(copy.deepcopy(p))
        elif feature in plan_ids:
            dropped.append(p["id"])
        else:
            raise PackageError(f"passage_probes[{i}].feature names neither an exported object nor a feature of "
                               "the generation plan")
    return kept, dropped


def export_package(path, name, area, sources, glb_bytes, col_objects, report, edits=None, blender_version=None,
                   heightfield_spacing=None, object_info=None, created_utc=None, passage_probes=(), plan_ids=()):
    """Write a validated package atomically. ``col_objects`` must come from the same final meshes and world
    transforms as ``glb_bytes``; ``object_info[name]['provenance']`` is copied to the manifest.
    ``passage_probes`` (plan probes) are filtered by :func:`filter_passage_probes` against ``plan_ids`` (the
    original plan's mb_ids); the ids of dropped probes go to report.json ``passage_probes_dropped``."""
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
    probes_kept, report["passage_probes_dropped"] = filter_passage_probes(passage_probes,
                                                                          (o.mb_id for o in col_objects), plan_ids)
    members, manifest, probes = assemble(name, area, sources, glb_bytes, collision_bytes, objects, heightfield=hf,
                                         report=report, edits=edits, blender_version=blender_version,
                                         created_utc=created_utc, passage_probes=probes_kept)
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
                          heightfield_spacing=heightfield_spacing, object_info=info, created_utc=created_utc,
                          passage_probes=getattr(plan, "passage_probes", []), plan_ids=generated_ids)


def elevation_correction_note(correction):
    """Text for the elevation source entry (``processing``) when the DSM correction was applied, else None."""
    if not (correction or {}).get("applied"):
        return None
    masked, total = correction["masked_points"], correction["total_points"]
    lowered = correction.get("lowered_points", 0)
    if not lowered:
        return (f"DSM terrain correction ran (map-builder, derived; raw source data unchanged) but lowered no "
                f"points: {masked} of {total} terrain points lie under buildings, trees, forest or bridge decks "
                "and none was above the interpolated surrounding ground; the terrain equals the source. See "
                "report.json terrain_correction.")
    return (f"DSM terrain correction applied by map-builder (derived; raw source data unchanged): {lowered} of "
            f"{total} terrain points ({masked} masked under buildings, trees, forest and bridge decks) were "
            f"lowered toward the surrounding ground (max {correction['max_lowering_m']:g} m, mean over the masked "
            f"points {correction['mean_lowering_m']:g} m); an approximation, not a bare-earth DTM. See report.json "
            "terrain_correction.")


def generate_plan(area, settings, client=None, progress=None):
    grid, classified, sources = acquire(area, settings, client, progress)
    plan = build_plan(area, grid, classified, settings.plan_options, dsm_correction=settings.dsm_correction)
    note = elevation_correction_note(plan.report.get("terrain_correction"))
    if note:
        for src in sources:
            if src.get("kind") == "elevation":
                src["processing"] = note
    return plan, sources


def build_package(area, settings, path, name, client=None, progress=None, created_utc=None):
    """acquire -> plan -> validated package. Returns (manifest, ValidationResult).
    The heightfield layout (size limit and 2x2 minimum) is checked before any file or network access."""
    if settings.heightfield_spacing:
        heightfield_layout(area.half, settings.heightfield_spacing)
    plan, sources = generate_plan(area, settings, client, progress)
    return plan_to_package(plan, path, name, sources, heightfield_spacing=settings.heightfield_spacing,
                           created_utc=created_utc)
