# Map package format: `map-builder.package` 1.0.0

This is the contract between map-builder (the producer) and any runtime (the consumer).
Format and schema versions follow semver: a consumer must reject an unknown **major**
version and must ignore unknown fields.

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
* **Winding:** `.mbcol` triangles are counter-clockwise when seen from outside, in the
  right-handed map frame. Building solids are closed, and their signed volume is positive.
  Open surfaces such as terrain and roads face up (+Z).

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
  * the orientation probes (points, triangles and normals) against the visual mesh.
* Collision is exported from the same evaluated meshes and world matrices as the visuals.
  Visual LOD or simplification done by a consumer **must not** change collision.

## `manifest.json` (abridged)

```jsonc
{
  "schema": "map-builder.package", "schema_version": "1.0.0",
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
  "collision": {"path", "format": "mbcol", "version": 1, "frame": "map", "winding": "ccw_outward",
                "triangle_count", "vertex_count", "bounds_min", "bounds_max", "classes": {…}},
  "heightfield": {"path", "nx", "ny", "x0", "y0", "spacing_m", "nan_cells", …} | null,
  "objects": [{"name", "mb_id", "class", "collision": true, "provenance": {…}}],
  "orientation_probes": [{"node", "point_map", "point_gltf", "point_unity_x_negated",
                          "triangle_map", "normal_map", "normal_unity_x_negated"}],
  "sources": [{"kind": "elevation"|"features", "provider", "license": {…}, "attribution", …}],
  "edits": {"duplicated": n, "user_added": n, "removed": n},
  "notices": "NOTICES.txt", "report": "report.json", "warnings_count": n
}
```

### Object identity (`mb_id`)

| Form | Meaning |
|---|---|
| `osm:way/123`, `osm:relation/45`, `osm:node/9` | Generated from that OSM element. |
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
* `report.json` lists:
  * `unsupported_features`: bridges (including `man_made=bridge` and `building=bridge`), tunnels, elevated parts
  * `invalid_features`: for example self-intersecting footprints, degenerate inner rings,
    buildings where the terrain reaches the roof underside, and footprints or trees outside
    the terrain extent
  * counts and warnings

## `collision/map.mbcol` v1 (little-endian)

| Offset | Type | Field |
|---|---|---|
| 0 | char[8] | magic `"MBCOL\0\0\0"` |
| 8 | u32 | version = 1 |
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
| … | u8[T] (+ pad to 4) | class id per triangle: 0 user, 1 terrain, 2 building, 3 road, 4 vegetation, 5 water, 6 prop |
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
are authoritative**; the grid cannot represent overhangs or non-terrain objects.

## Reference implementation

* `map_builder/core/package.py`: `validate_package`, `write_package`.
* `map_builder/core/collision.py`: `.mbcol` and `.mbhf` readers and writers.
* `tools/mbmap_cli.py validate <file>`: validates a package from the command line.
