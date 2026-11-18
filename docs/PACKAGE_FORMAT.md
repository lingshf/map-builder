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
* Because the manifest contains each file hash, `package_id` binds the visuals, collision,
  georeference and provenance to one immutable identity. **Replays and recordings should store
  `package_id`** and refuse to replay against any other package.
* Re-exporting identical content gives identical file hashes. `created_utc` is part of the
  manifest, so each export has its own `package_id`.

## Frames, axes and units

All coordinates are in metres.

* **Map frame**, used by collision, the heightfield, the manifest and Blender world space:
  right-handed, **+X east, +Y north, +Z up**.
  * The origin is the area centre on the WGS84 ellipsoid (h = 0). x and y are the east and
    north components of ECEF→ENU at the origin, with no scale factor and no earth-curvature
    correction. This is adequate for areas of about 1–2 km.
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

`orientation_probes[]` gives the AABB centre of up to three non-terrain objects. Each probe
has the centre in map, glTF and Unity (X-negated) coordinates. After import, a consumer must
check that the named node's bounds centre lands at `unity_x_negated`, within 5 cm.

## Visual/collision binding

* Every glTF node with triangles has a collision object of the **same name**. Every collision
  object has a glTF node.
* The validator checks, per object:
  * that the glTF-derived AABB matches the collision AABB within 1 cm + 1e-5 × object size
  * that the signed-volume sign (winding) agrees
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
  "orientation_probes": [{"node", "map_aabb_center", "gltf", "unity_x_negated"}],
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
* `report.json` lists:
  * `unsupported_features`: bridges, tunnels, elevated parts
  * `invalid_features`: for example self-intersecting footprints
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
