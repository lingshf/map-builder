# Map package format: `map-builder.package` 2.0.0

This is the contract between map-builder (the producer) and any runtime (the consumer).
Format and schema versions follow semver: a consumer must reject an unknown **major**
version and must ignore unknown fields. Major version 2 (this document) added the `bridge`,
`tunnel` and `structure` collision classes with per-kind winding rules, `.mbcol` v2 and
`passage_probes`; 1.x packages are rejected and must be regenerated.

## Container

The package is a ZIP with the `.mbmap` extension. Members use relative POSIX paths only. These
are forbidden:

* absolute paths, `..` components, backslashes, drive letters, empty or `.` segments
* duplicates, symlinks, encrypted entries
* unlisted files

Consumers must enforce the same bounds the reference validator uses:

| Limit | Value |
|---|---|
| Entries | ≤ 64 |
| Total uncompressed size | ≤ 1.5 GiB |
| Manifest | ≤ 32 MiB |
| Compression ratio per entry | ≤ 200 |

| Member | Role | Required |
|---|---|---|
| `manifest.json` | manifest, UTF-8 JSON, no NaN/Infinity | yes |
| `visual/map.glb` | `visual`: glTF 2.0 binary, self-contained (no external URIs, no required extensions) | yes |
| `collision/map.mbcol` | `collision`: authoritative static collision | yes |
| `NOTICES.txt` | `notices`: attribution and licence text, which must be shown or shipped | yes |
| `report.json` | `report`: generation and export diagnostics, unsupported features, edits | no |
| `collision/terrain.mbhf` | `heightfield`: convenience grid derived from terrain collision | no |

## Integrity and identity

* `files[]` lists `{path, role, media_type, sha256, bytes}` for every member except the
  manifest.
* `package_id = "sha256:" + SHA-256(exact bytes of manifest.json in the archive)`. It is not
  stored inside the manifest; consumers compute it from the raw member bytes, with no JSON
  re-serialisation, so any language gets the same value.
* `package_id` identifies the manifest only. It binds the payload **only after verification**.
  Before a consumer uses any member or accepts the package's `package_id`, it **must**:
  * check that the archive members other than `manifest.json` map one-to-one onto `files[]`
    paths (nothing missing, unlisted or duplicated);
  * check that each member's uncompressed byte count equals `bytes`;
  * check that its SHA-256 equals `sha256`.
  If any check fails, the package is invalid, whatever its `package_id`.
* Because the verified manifest contains each file hash, `package_id` binds the visuals,
  collision, georeference and provenance to one immutable identity. **Replays and recordings
  should store `package_id`** and refuse to replay against any other package.
* Re-exporting identical content gives identical file hashes. `created_utc` is part of the
  manifest, so each export has its own `package_id`.

## Frames, axes and units

All coordinates are in metres.

* **Map frame**, used by collision, the heightfield, the manifest and Blender world space:
  right-handed, **+X east, +Y north, +Z up**.
  * The origin is the area centre on the WGS84 ellipsoid (h = 0). x and y are the east and
    north components of ECEF→ENU at the origin, with no scale factor and no earth-curvature
    correction. This is adequate for areas of about 1–2 km. Areas must stay within
    |lat| ≤ 84°, and an area plus a 1 km margin must not cross the antimeridian.
  * `z = H − georeference.z_offset_m`, where H is the height above
    `georeference.vertical_datum`, for example `EGM2008` for Copernicus.
* **glTF:** `gltf = (x, z, −y)`, so +X east, +Y up, +Z south. This is a proper rotation, so
  winding is preserved. Every node's full TRS and its parent hierarchy apply. As the glTF
  specification requires, a node whose world matrix has a negative determinant renders with
  reversed winding.
* **Unity** (left-handed, Y-up), when the glTF importer negates X (glTFast and UnityGLTF do
  this): `unity = (−x, z, −y)`, so +X west, +Y up, +Z south. This is a reflection: triangle
  index order must be reversed to keep front faces. Verify this importer behaviour with
  `orientation_probes`; do not assume it.
* **Winding:** `.mbcol` triangles are counter-clockwise when seen from their front side, in
  the right-handed map frame. The rule depends on the class **kind** (see "Collision classes"):
  solids are closed with positive signed volume (front = outside), surfaces face up (+Z), and
  tubes face inward into the free space they enclose.
* **Two-sided intersection:** triangles are **two-sided** for intersection, ray casts and
  capsule/sweep queries. A consumer must not cull back faces in collision queries. The winding
  only gives the **contact normal**: outward for solids, up for surfaces, and inward into the
  free space for tubes.

### Collision classes

| id | class | kind | winding rule |
|---|---|---|---|
| 0 | `user` | — | none |
| 1 | `terrain` | surface | normal Z > 0 |
| 2 | `building` | solid | closed, positive volume |
| 3 | `road` | surface | normal Z > 0 |
| 4 | `vegetation` | — | none |
| 5 | `water` | surface | normal Z > 0 |
| 6 | `prop` | — | none |
| 7 | `bridge` | solid | closed, positive volume |
| 8 | `tunnel` | tube | inward tube (below) |
| 9 | `structure` | solid | closed, positive volume |

The generator does not emit `bridge`, `tunnel` or `structure` yet (they are listed as
unsupported features in `report.json`), but the format, the validator and the reference
readers accept them. `manifest.collision.classes` maps names to ids and
`manifest.collision.class_kinds` maps names to `"solid"`, `"surface"`, `"tube"` or `null`;
both must equal the tables above.

**Tube rule.** Vertices are welded exactly as for the solid rule. Every directed edge must be
matched by its reverse, except boundary edges (edges whose reverse is absent). Each boundary
edge may occur once, and the boundary edges must form simple closed loops (the portals). Each
loop is capped with a triangle fan around the loop centroid, oriented consistently with the
adjacent faces. Every resulting closed shell must contain at least one cap, that is, every
tube shell must be open at one or more portals; a sealed shell (for example an inward-facing
closed box) is an error. Every shell, after capping, must have a **negative** signed volume, so
its faces point inward; there is no exemption for a shell made only of degenerate (zero-area)
triangles, whose volume is zero. Any violation is an error; diagnostics name the object only
by `#index`.

### Orientation probes

`orientation_probes[]` has at most three probes, one per selected node. The generator
selects up to three nodes that have a qualifying vertex, preferring non-terrain nodes and
falling back to terrain. Real terrain almost always qualifies. If no node qualifies, for
example perfectly flat symmetric geometry, the list is empty and the validator records the
warning `orientation probes unavailable`. A consumer must then treat importer orientation as
**unverified**. It should refuse the map, or verify the importer separately, for example
with the synthetic sample package. Each probe is:

```jsonc
{"node": "…",                                    // glTF node / collision object name
 "point_map": [x, y, z], "point_gltf": [...], "point_unity_x_negated": [...],
 "triangle_map": [[x,y,z], [x,y,z], [x,y,z]],    // one collision triangle of the node, CCW front
 "normal_map": [nx, ny, nz], "normal_unity_x_negated": [...]}
```

* `point_*` is an actual world-space vertex of the node, with |x| ≥ 1 m and |y| ≥ 1 m. The
  node has no vertex within 0.5 m of its X-mirror (−x, y, z). An importer that skips or
  doubles the reflection therefore cannot match it by symmetry.
* `triangle_map` contains `point_map` and has a unit front-face normal `normal_map`, where
  |nx| ≥ 0.05 or |nz| ≥ 0.05.

After import, a consumer must:
1. find a vertex of the named node, in world space, within 5 cm of `point_unity_x_negated`;
2. find the imported triangle whose vertices match `triangle_map` mapped to Unity, within
   5 cm, and require `dot(normalize(Cross(b − a, c − a)), normal_unity_x_negated) > 0.99`.
   This uses Unity's left-handed cross product in imported index order, so it verifies
   winding and front faces.

If either check fails, the importer or the conversion is wrong; refuse the map.

## Visual/collision binding

* Every glTF node with triangles has a collision object of the **same name**. Every collision
  object has a glTF node.
* The validator checks, per object:
  * that the glTF-derived AABB matches the collision AABB within 1 cm + 1e-5 × object size
  * per-triangle winding agreement. Visual triangles are taken after the glTF world
    transform and its negative-determinant winding rule, and then mapped to the map frame.
    Each non-degenerate collision triangle is matched to a visual triangle with the same
    three vertices (each within 5 mm). For each candidate, the validator chooses the vertex
    correspondence with the lowest total distance; ties between opposite orientations count
    as ambiguous and are skipped. A best correspondence that is a reversed cyclic order is an
    error. If fewer than 99 % of an object's collision triangles find an unambiguous match,
    the validator issues a warning.
    Candidates are first pruned to those with a vertex correspondence; the candidate cap and
    a per-object work budget apply after that. Triangles left unchecked because the budget ran
    out are reported in that warning, not counted as ambiguous.
  * visual triangles with no collision counterpart (visible but not collidable). This is a
    warning.
  * the collision winding rules above, checked on the collision alone, by class kind: solids
    (`building`, `bridge`, `structure`) must be closed (each directed edge matched by its
    reverse), and each connected shell must have a positive signed volume. Enclosed cavities
    (inward-facing inner shells) in solids are not supported. Non-degenerate surface triangles
    (`terrain`, `road`, `water`) must have normal Z > 0. Tubes (`tunnel`) follow the tube rule.
    A violation is an error. Degenerate triangles are only a warning.
  * the passage probes (below) against the final collision.
  * the credential policy (no URL user-info, credential query keys, Authorization or Bearer
    values, or credential-named keys), applied recursively to the manifest, `report.json`,
    the collision object table and the glTF JSON. Diagnostics name entries by index or fixed
    format value and never echo strings taken from the package.
  * the orientation probes (points, triangles and normals) against the visual mesh.
* The reference exporter is stricter than the validator. It refuses to publish unless each
  node's visual and collision triangles correspond one-to-one with the same winding. The
  correspondence is a bounded order-independent matching; if the budget runs out, the export
  fails with "cannot verify binding" instead of passing.
* Collision is exported from the same evaluated meshes and world matrices as the visuals.
  Visual LOD or simplification done by a consumer **must not** change collision.

## `manifest.json` (abridged)

```jsonc
{
  "schema": "map-builder.package", "schema_version": "2.0.0",
  "name": "…", "created_utc": "…",
  "generator": {"name": "map-builder", "version": "0.1.0", "blender": "4.2.23 LTS" | null},
  "georeference": {"origin": {"lat_deg", "lon_deg"}, "horizontal_datum": "WGS84 (EPSG:4326)",
                   "projection": "…", "vertical_datum": "EGM2008", "z_offset_m": 386,
                   "height_formula": "H = z + z_offset_m", "units": "metre"},
  "area": {"width_m", "height_m", "local_rect_m": [x0, y0, x1, y1],
           "geographic_bbox_deg": {"south", "west", "north", "east"}},
  "axes": {…},                 // machine-readable map_from_gltf / map_from_unity matrices
  "files": [{"path", "role", "media_type", "sha256", "bytes"}],
  "visual": {"path": "visual/map.glb", …},
  "collision": {"path", "format": "mbcol", "version": 2, "frame": "map", "winding": "ccw_outward",
                "triangle_count", "vertex_count", "bounds_min", "bounds_max", "classes": {…},
                "class_kinds": {…}},
  "heightfield": {"path", "nx", "ny", "x0", "y0", "spacing_m", "nan_cells", …} | null,
  "objects": [{"name", "mb_id", "class", "collision": true, "provenance": {…}}],
  "orientation_probes": [{"node", "point_map", "point_gltf", "point_unity_x_negated",
                          "triangle_map", "normal_map", "normal_unity_x_negated"}],
  "passage_probes": [{"id", "kind": "bridge"|"tunnel"|"elevated", "feature": "<mb_id>",
                      "path_map": [[x, y, z], …], "radius_m"}],
  "sources": [{"kind": "elevation"|"features", "provider", "license": {…}, "attribution", …}],
  "edits": {"duplicated": n, "user_added": n, "removed": n},
  "notices": "NOTICES.txt", "report": "report.json", "warnings_count": n
}
```

### Passage probes

`passage_probes[]` is always present (it may be empty) and holds at most 256 probes. A probe
declares a capsule that a consumer's character or vehicle must be able to pass through, for
example along a bridge deck, through a tunnel or under an elevated part:

```jsonc
{"id": "…",                                   // unique within the package
 "kind": "bridge" | "tunnel" | "elevated",
 "feature": "<mb_id>",                        // must equal some objects[].mb_id
 "path_map": [[x, y, z], …],                  // 2..64 points, map frame, finite, |coord| ≤ 1e6 m
 "radius_m": r}                               // 0 < r ≤ 10
```

The capsule is the set of points within `radius_m` of the polyline `path_map`. It is
**blocked** if any collision triangle (two-sided) lies within `radius_m` of the path; the
comparison allows `radius_m + 1e-9` m, so exact contact is never lost to rounding. The
validator treats a malformed probe or an unknown `feature` as an error. It re-checks every
probe against the final collision and reports a blocked probe as a **warning**, naming the
probe by index and the first blocking collision object by `#k`. The check has a fixed work
budget of 2,000,000 object/triangle visits shared by all probes of the package (one unit per
object per path segment, plus one per triangle tested); if it runs out, the remaining probes
are reported as unchecked in a warning. Degenerate (collapsed or collinear) triangles are
measured through their edges.
Consumers should re-run the probes against their own imported collision as acceptance tests.
When an export drops a probe because its `feature` object was part of the generation plan
(its `generated_ids`) but no longer exists, the probe id is listed in `report.json`
`passage_probes_dropped`. The exporter refuses a malformed probe, or one whose `feature`
names neither an exported object nor a plan feature, with an error instead of dropping it.

### Object identity (`mb_id`)

| Form | Meaning |
|---|---|
| `osm:way/123`, `osm:relation/45`, `osm:node/9` | Generated from that OSM element. Local `.osm` files may use negative ids for unsaved edits, e.g. `osm:way/-7`. |
| `osm:relation/45#k` | Part `k` of an OSM element that was split into several objects (for example, a multipolygon with several outer rings). |
| `terrain:grid` | The terrain. |
| `scatter:<area id>#k` | A procedurally scattered tree. |
| `<id>~<object name>` | A user duplicate of a generated object. The first object in name order keeps the plain id. |
| `user:<object name>` | An object the user added, with no generated identity. |

Identities are unique within a package. Generated ids that are missing from an export are
counted in `edits.removed` and listed in `report.json`.

### Provenance

* `provenance` values that start with `measured:` come from source data, for example the OSM
  `height` tag.
* Values that start with `inferred:` or `fallback:` are defaults chosen by map-builder.
* Numeric tags outside sane ranges (levels > 200, lengths > 1000 m, non-finite values) are
  not used; they are listed in the object's `rejected_tags` provenance and in `warnings`.
* Building heights follow OSM semantics. An explicit `height` is the total height and the
  roof is built within it. Without `height`, `building:levels` × 3 m is the **eave** height
  (`height` = `inferred:building:levels x 3 m to the eave, roof height added on top`). The roof
  rise is then added above it: from `roof:height`, from `roof:levels` × 3 m, or
  `inferred:0.3 x footprint short side (1-6 m), added above the storey-derived eave`.
  `height_m` is the total height and `eave_height_m` the eave (lowest wall top).
* Buildings are rejected when the terrain reaches the roof underside, that is, the eave plane,
  or the sloped plane of a skillion roof. The check compares both surfaces at the same XY
  positions over the whole footprint. When the terrain rises above the lowest eave but still
  clears the underside everywhere, `terrain_clearance` records that.
* Roads: all generated roads are at grade, and no two road objects share ground. Where roads
  overlap, the area belongs to the higher-priority road:
  1. the road class (`motorway` … `path`);
  2. then the wider ribbon;
  3. then the feature id.

  A road that loses area records it in `overlap` (m² and the owning road ids). A road with no
  area left is not generated; it is listed in `warnings` and counted in
  `counts.roads_fully_covered`. Ribbons are trimmed at the terrain edge (`terrain_edge`,
  `counts.roads_trimmed_at_terrain_edge`).
* Nothing is generated outside the terrain extent. Building footprints and OSM trees outside
  it (1 mm tolerance) are listed in `invalid_features`. Procedural scatter is placed only on
  terrain. Landcover only colours terrain cells. If the terrain does not cover the scene area,
  `warnings` says so.
* Landcover (water, forest, grass, sand) polygons are checked with the same ring-topology rules
  as building footprints (simple rings, holes strictly inside the outer ring, no contacts).
  A polygon that fails, or cannot be checked within the work budget, is listed in
  `invalid_features` and is used neither for terrain colouring nor for scatter.
* Building parts (Simple 3D Buildings): an outline is replaced by the `building:part` features
  that belong to it. The parts are built first.
  * Containment test: the part's boundary (outer ring and holes) must lie inside or on the
    outline's outer ring and outside all of its courtyards, and no courtyard may lie inside the
    part. Coincident or touching boundaries are allowed within 0.05 m. Centroids are never used.
  * Declared parts: a `type=building` relation names its `outline` (a way, or a building
    multipolygon relation) and its `part` members (ways or relations). Online imports fetch
    these relations even when they carry no building tags (those in the area, and the parent
    relations of the fetched building/building:part features), together with their member
    relations, ways and nodes, so an Overpass import classifies like a local `.osm` file with
    the same data. A declared part is
    checked against its declared outline only. If it lies within it, it belongs to that outline
    (if several declared outlines contain it, the smallest; the others get a `warnings` entry).
    If it does not (it crosses the outline boundary or lies in one of its courtyards), it is
    listed in `invalid_features` with the reason `building:part does not lie within its declared
    outline <outline ids> (building relation <relation ids>) ...`; the outline is kept, and the
    rejected part counts among its rejected parts below.
  * Declared outline unavailable: if no declared outline exists as a building outline (member
    missing from the data, outside the area, invalid or unsupported, or the relation has no
    `outline` member), the part is generated standalone with a `warnings` entry naming the
    relation. It is never matched spatially to an outline the relation does not name.
  * Undeclared parts are matched spatially: a part belongs to the smallest outline it lies
    within. A part lying in an outline's courtyard does not overlap that outline: it is a
    standalone part and is generated as such (the courtyard is empty space), with no diagnostic.
  * Overlaps: a part (declared or not) whose footprint overlaps an outline it neither belongs
    to nor lies within is kept, and so is the outline; the part never replaces it.
    Classification only records the pair (`overlap_candidates`, bounded by the pair limit
    below). After the buildings are generated, if both were emitted and the map-frame Z extents
    of their meshes (vertices with the object transform applied: terrain base, foundation,
    `min_height`, and the roof actually built, including inferred roof heights) overlap, a
    `warnings` entry names both as possibly intersecting, and `building_overlaps` lists
    `{part, outline, kind, part_z_m, outline_z_m}`. This is a conservative screen, not an
    exact solid intersection test: whole-object Z extents can overlap while the solids still
    clear each other inside the shared footprint (for example under a sloped roof), so
    consumers must not treat an entry as proof of intersection. Stacked solids with disjoint Z extents (for
    example a part from 6 m to 10 m over a 4 m building on flat ground, or a part on higher
    ground of a slope) are not a conflict and nothing is reported; neither is a pair where one
    side was not generated. Overlapping buildings are a property of the OSM data, so nothing
    is dropped. Touching footprints never count as overlapping.
  * Limits: retained (replaced) outlines count toward the feature limit, which is checked
    before matching. Candidate pairs come from a bounding-box grid plus the declared pairs;
    more than 200,000 part/outline pairs (declared pairs across all `type=building` relations
    are also counted while parsing, before they are stored), or more than 10,000,000 geometric
    tests, raise `LimitError`.
  * All parts generated: the outline is listed in `building_outlines_replaced_by_parts`.
  * No part generated: the outline is generated instead. It is listed in
    `building_outlines_restored` (`{id, rejected_parts}`), has the provenance
    `building_parts = fallback:outline generated because all of its building:part features
    (…) were rejected`, and gets a `warnings` entry. The rejected parts are in
    `invalid_features`. If the outline fails too, its `invalid_features` reason starts with
    `building outline (fallback after all of its building:part features … were rejected)`.
  * Some parts generated: the surviving parts are kept and the outline is **not** generated,
    so solids never overlap. The outline is listed in `building_outlines_replaced_by_parts`
    and in `building_outlines_partially_represented` (`{id, built_parts, rejected_parts}`),
    with a `warnings` entry; the rejected parts are in `invalid_features`.
* Scene budget: a road's exact vertex/triangle count is computed one terrain triangle at a
  time and stops as soon as it exceeds what remains of the budget (`LimitError` naming the
  road). A road that exactly fits is accepted.
* `report.json` lists:
  * `unsupported_features`: bridges (including `man_made=bridge` and `building=bridge`), tunnels, elevated parts
  * `invalid_features`: for example self-intersecting footprints, degenerate inner rings,
    buildings where the terrain reaches the roof underside, footprints or trees outside
    the terrain extent, landcover with invalid ring topology, and rejected building parts
  * `terrain_correction`: the DSM correction outcome (`applied`, `setting`, `reason`,
    `masked_points`, `lowered_points`, `total_points`, `max_lowering_m`, `mean_lowering_m`, and
    once the fill ran `fill_cycles`, `fill_residual_m`, `fill_converged`; mask parameters, feature
    counts, `excluded_invalid` and `rasterisation_work`). A fill that did not converge is not
    applied (`reason: fill did not converge`).
    Informative only; when applied, the elevation entry in `sources` also has an optional
    `processing` string (sources are an open object, so this is not a format change)
  * counts and warnings

## `collision/map.mbcol` v2 (little-endian)

The binary layout is identical to v1; only the version number and the class id set changed.
Readers accept version 2 only.

| Offset | Type | Field |
|---|---|---|
| 0 | char[8] | magic `"MBCOL\0\0\0"` |
| 8 | u32 | version = 2 |
| 12 | u32 | flags (bit0 = CCW outward winding) |
| 16 | u32 | vertex_count V |
| 20 | u32 | triangle_count T |
| 24 | u32 | object_count O |
| 28 | u32 | object_table_bytes J (padded to 4) |
| 32 | f32[3] | bounds_min (map frame) |
| 44 | f32[3] | bounds_max |
| 56 | u32[2] | reserved (0) |
| 64 | f32[3·V] | vertex positions, map frame, world space |
| … | u32[3·T] | triangle vertex indices |
| … | u32[T] | object index per triangle |
| … | u8[T] (+ pad to 4) | class id per triangle: 0 user, 1 terrain, 2 building, 3 road, 4 vegetation, 5 water, 6 prop, 7 bridge, 8 tunnel, 9 structure |
| … | u8[J] | UTF-8 JSON array, `\0`-padded: `{index, name, mb_id, class, tri_start, tri_count, aabb}` |

* Each object's triangles are contiguous: `[tri_start, tri_start + tri_count)`.
* The file size must equal the size computed from the header exactly.
* Readers must bounds-check every index and reject non-finite vertices.
* Vertices are float32. Positions within ±2 km keep millimetre precision.

## `collision/terrain.mbhf` v1 (little-endian, optional)

| Offset | Type | Field |
|---|---|---|
| 0 | char[8] | magic `"MBHF\0\0\0\0"` |
| 8 | u32 | version = 1 |
| 12 | u32 | nx |
| 16 | u32 | ny |
| 20 | u32 | reserved |
| 24 | f64 | x0 (map frame, west edge) |
| 32 | f64 | y0 (south edge) |
| 40 | f64 | spacing (m) |
| 48 | f32[nx·ny] | z, row-major: row j (y = y0 + j·spacing) outer, column i (x = x0 + i·spacing) inner; NaN = no terrain |

Each value is the maximum z of the *final* terrain-class collision triangles at that grid
point. The grid is a derived convenience, for example for a Core height-grid path. **Triangles
are authoritative.** The heightfield is **terrain-only**: it is NaN wherever terrain is absent
or cut (for example a future tunnel portal or cutting), and it cannot represent bridges,
tunnels, elevated volumes, overhangs or any other non-terrain object. A consumer that needs
those must use the `.mbcol` triangles.

## Reference implementation

* `map_builder/core/package.py`: `validate_package`, `write_package`.
* `map_builder/core/collision.py`: `.mbcol` and `.mbhf` readers and writers, `CLASSES`, `CLASS_KINDS`.
* `map_builder/core/query.py`: two-sided capsule and ray queries used for passage probes.
* `tools/mbmap_cli.py validate <file>`: validates a package from the command line.
