# Unity / Core handoff

This is the guide for consuming a `.mbmap` package, written first for lingshf/drone-flight-simulator
as it migrates to Unity 6 LTS + URP. The normative contract is
[PACKAGE_FORMAT.md](PACKAGE_FORMAT.md); this document explains how to apply it and does not repeat
the byte layouts. If the two disagree, PACKAGE_FORMAT.md wins.

[examples/csharp/MbmapReader](../examples/csharp/MbmapReader) is a dependency-free C# reference
reader: C# 8, netstandard2.1-compatible APIs, plus System.Text.Json. It implements everything in
sections 1–3 below and runs as a self-test against
[examples/synthetic_sample.mbmap](../examples/synthetic_sample.mbmap).

## Roles

| Layer | Uses | Authority |
|---|---|---|
| **Core** (netstandard2.1, 250 Hz physics) | `collision/map.mbcol`, optional `collision/terrain.mbhf`, georeference | **Authoritative** for flight and collision |
| **Unity** (presentation only) | `visual/map.glb` via a glTF importer (e.g. glTFast; the version is the consumer's choice) | Rendering only. Unity Colliders/PhysX are **not** the authority and must not be generated from the GLB for gameplay. |
| UI / legal | `NOTICES.txt`, `manifest.json` `sources[]` | Attribution must be shipped and shown |
| Tools | `report.json` | Diagnostics only; never needed at runtime |

## 1. Loading sequence

1. Open the zip. Apply the container rules in PACKAGE_FORMAT.md › Container: safe relative
   names, no duplicates, regular files only, size and ratio limits.
2. Read the raw bytes of `manifest.json`. Parse them as strict JSON, rejecting duplicate keys,
   and check that `schema == "map-builder.package"` and that the major version of
   `schema_version` is supported (see section 6).
3. Check that the members other than the manifest map **one-to-one** onto `files[]`. For each
   member, verify the uncompressed `bytes` and its `sha256`. Any mismatch means the package is
   invalid.
4. Only then accept `package_id = "sha256:" + hex(SHA-256(raw manifest bytes))`. **Store
   `package_id` in every replay or recording, and refuse to replay against a different one.**
5. Core: parse `.mbcol` (and `.mbhf` if present) with every bounds check from the spec.
   Cross-check the header counts against `manifest.collision` and the heightfield header
   against `manifest.heightfield`.
6. Unity: load `visual/map.glb` with the importer, from the verified bytes in memory, not by
   re-reading the file. Then run the orientation probes (section 3) and refuse the map if they
   fail. An empty `orientation_probes` list means "orientation unverified": refuse the map, or
   verify the importer once with the synthetic sample.
7. Show `NOTICES.txt` / `sources[].attribution` wherever the product displays credits.

## 2. Frames and mapping

| Frame | Axes | From map `(x, y, z)` |
|---|---|---|
| Map / Core ENU (`.mbcol`, `.mbhf`, manifest) | right-handed, +X east, +Y north, +Z up | identity |
| glTF | right-handed, +X east, +Y up, +Z south | `(x, z, −y)`, a rotation, so winding is kept |
| Unity, with an importer that negates X (glTFast, UnityGLTF) | left-handed, +X west, +Y up, +Z south | `(−x, z, −y)`, a reflection |

* The Map → Unity mapping is a reflection, so **reverse the index order** of every triangle
  (`(a, b, c) → (a, c, b)`) when Core geometry is shown or compared in Unity. The importer
  already does this for the GLB.
* Unity → map is `(x, y, z)_map = (−u.x, −u.z, u.y)`.
* The existing Core uses the same ENU axes (X east, Y north, Z up), so no axis conversion is
  needed between `.mbcol` and Core. Only the Core ↔ Unity presentation boundary needs the
  mapping above, and it must be the **same** function used for the GLB.
* Heights: `H = z + georeference.z_offset_m`, above `georeference.vertical_datum`. The origin is
  `georeference.origin` (WGS84). Map x/y are local ENU metres, with no projection scale factor.

## 3. Orientation self-test (probes)

`manifest.orientation_probes[]` has up to three probes, each `{node, point_map, point_gltf,
point_unity_x_negated, triangle_map, normal_map, normal_unity_x_negated}`. They are chosen so
that a missing or doubled reflection cannot match by symmetry. After import, for each probe:

1. In world space, the GameObject/mesh named `node` must have a vertex within **5 cm** of
   `point_unity_x_negated`.
2. Map `triangle_map` to Unity. Find the imported triangle whose three vertices match it
   within 5 cm, and take its vertices `a, b, c` in **imported index order**. Then
   `dot(normalize(Vector3.Cross(b − a, c − a)), normal_unity_x_negated)` must be **> 0.99**.

A failure means the importer or the conversion differs from the contract; refuse the map. Core
can run the same probe checks against `.mbcol` in the map frame (`point_map`, `triangle_map`,
`normal_map`). The reference reader does both, and also proves that the test is sensitive: it
rejects an import that skips the winding flip and one that skips the X negation.

## 4. Adapting Core

Core **cannot load an arbitrary triangle mesh today**. It has a terrain height grid and
building prism colliders. `.mbcol` contains arbitrary triangles: terrain, closed building
shells (including roofs, mirrored, scaled or user-modelled geometry), roads draped on terrain,
vegetation and props. Options:

* **A. Static triangle-mesh collider (recommended).** Load all `.mbcol` triangles once and build
  a BVH or uniform grid over them. Provide a ray/segment cast and a swept-sphere or
  capsule-vs-triangle contact query for the drone. This handles everything in the package,
  including edited and user-modelled geometry. The cost is a new narrow phase and
  BVH-building code in Core.
* **B. Heightfield + buildings.** Use `.mbhf` as the terrain height grid. It holds the highest
  terrain-class (class 1) triangle per sample, with NaN outside the terrain. Collide buildings
  against their `.mbcol` triangles, per object (`objects[]` gives each object's triangle range
  and AABB, a natural broad phase). Approximating buildings as prisms **loses accuracy** for
  roofs, mirrored or edited shapes and non-prismatic models; if used, treat it only as a
  temporary step and measure the error. Note also that the heightfield resamples the terrain
  triangles, so between samples it is not the exact terrain surface.

None of this is implemented yet. Once a consumer-side adapter translates `.mbhf` samples
(including no-data cells) into the Core's terrain representation, the existing
prism/height-grid Core could use it as a terrain grid (with a resampling caveat) and use
object AABBs for a broad phase. Even then it could not collide exactly with
terrain triangles, sloped or complex roofs, roads, vegetation or user geometry.

Rules either way:

* Collision comes **only** from `.mbcol`/`.mbhf`, never from GLB triangles. Visual LOD, mesh
  simplification or culling in Unity **must not** change collision.
* Use `objects[].class` / the per-triangle class for gameplay (e.g. landing on terrain vs
  crashing into buildings), but collide with every class unless the design says otherwise.
* `objects[].name` is the glTF node name (the 1:1 binding). `mb_id` is the stable identity
  across edits and re-exports.
* Triangles are **two-sided** for every collision query (ray, segment, capsule, sweep): do not
  cull back faces. The winding gives only the contact normal, which depends on the class kind:
  outward for solids, up (+Z) for surfaces, and inward into the free space for tubes.
* Format 2.0 adds the `bridge`, `tunnel` and `structure` classes, but map-builder does not
  generate bridges and tunnels yet: they are omitted and listed in `report.json`. Elevated building
  parts and building passages are generated and emit `elevated` / `tunnel` passage probes.
  Core and Unity can implement the mapping below now.

### Class ids and kinds

| id | class | kind | Core mapping (suggested) |
|---|---|---|---|
| 0 | user | — | static mesh, no winding guarantee |
| 1 | terrain | surface | ground; landing allowed |
| 2 | building | solid | crash on contact |
| 3 | road | surface | ground; landing allowed |
| 4 | vegetation | — | static mesh, no winding guarantee |
| 5 | water | surface | water outcome |
| 6 | prop | — | static mesh, no winding guarantee |
| 7 | bridge | solid | crash on contact; the deck top is the landing side |
| 8 | tunnel | tube | inward-facing walls; flyable inside, crash on the walls |
| 9 | structure | solid | crash on contact |

`manifest.collision.class_kinds` gives the kind per class name. Ids 10–255 are reserved: a 2.x
reader rejects them, as the reference readers do. A tube's front faces point into its free
space, so a contact normal from a tunnel wall points towards the inside of the tunnel. The
heightfield is terrain-only (NaN where terrain is cut) and cannot represent bridges, tunnels or
elevated volumes, so option B cannot fly under or through them.

### Passage probes as acceptance tests

`manifest.passage_probes[]` (see PACKAGE_FORMAT.md) lists capsules that must be free of
collision, for example a path along a bridge deck or through a tunnel. The map-builder validator
already re-checks them and warns when one is blocked. A consumer should run the same capsule
check against its **own** loaded collision (after import, with two-sided triangles) and treat a
blocked probe as a failed acceptance test for that map. The C# reference reader shows a
brute-force version with an AABB prefilter.

## 5. Legacy `.flightmap`

The legacy `.flightmap` schema1 is a reference only. `.mbmap` is not a superset of it, and there
is no converter. Core should add a `.mbmap` loader alongside it, not translate between the two.

## 6. Versioning and compatibility

* `schema_version` (the package) and the `.mbcol`/`.mbhf` header `version` fields follow semver
  intent. **Reject an unknown major** (the package) or an unknown binary version. **Ignore
  unknown JSON fields.** A minor version may add optional fields or members, but never changes
  the meaning of existing ones.
* `.mbcol` flags: bit 0 is required. Reject any unknown bit, and any non-zero reserved field.
* A replay is valid only against the exact `package_id` it recorded. Regenerating a map, even
  with the same content but a new `created_utc`, produces a new `package_id`.
* A consumer that pins a reader version should test it against the committed synthetic sample.
  Package-format changes in map-builder update PACKAGE_FORMAT.md, the Python validator and the
  sample together.

## 7. Remaining consumer-side work (checklist)

Nothing below exists yet in the simulator; map-builder supplies only the format, the
validator, the sample and the reference reader.

- [ ] Core: a `.mbmap` loader (container rules, files[] hashes, `package_id`), ported from or
      based on `MbmapReader.cs` (netstandard2.1 + System.Text.Json package).
- [ ] Core: a triangle-mesh static collider with a BVH and drone contact queries (option A), or
      the heightfield + per-building triangles interim (option B), with measured accuracy.
- [ ] Core: decide how classes map to gameplay outcomes (landing, crash, water), per the
      class/kind table above.
- [ ] Core: two-sided triangle queries, and a passage-probe capsule check run as a load-time
      acceptance test.
- [ ] Core: store `package_id` in replays and refuse a mismatch.
- [ ] Core: performance at 250 Hz for about 5k–1M triangles (no budget is promised by
      map-builder).
- [ ] Unity: choose and pin the glTF importer (glTFast version) and load from verified
      in-memory bytes.
- [ ] Unity: an orientation-probe self-test at load time, refusing the map on failure
      (including when there are no probes).
- [ ] Unity: a single Core↔Unity mapping function `(−x, z, −y)` with the winding flip, shared
      by any debug collision rendering.
- [ ] Unity/URP: materials for flat-shaded vertex-colour/PBR-factor meshes (no textures or UVs
      in v1).
- [ ] UI: show NOTICES.txt / attributions.
- [ ] Tests: run the reader and the simulator loader against `examples/synthetic_sample.mbmap`
      and against a tampered copy.
- [ ] Not generated yet, so out of scope for now: under-bridge, tunnel or elevated flying (the
      format is ready); streaming and very large areas.
