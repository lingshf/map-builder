# Validation

How map-builder is verified against [PACKAGE_FORMAT.md](PACKAGE_FORMAT.md). There are three layers:
pure-Python unit/acceptance tests (CI), the CLI on the committed SYNTHETIC fixture (CI), and a headless
Blender integration run (manual, not in CI).

## Validation matrix

`A.` = `tests/test_acceptance.py` (end-to-end, committed fixtures, < 5 s). Other files are under `tests/`.

| Requirement | Evidence |
|---|---|
| Fixture → CLI → `.mbmap` → `validate_package` VALID | `A.FixturePackageTest.test_cli_build_is_valid`; `test_package.CliTest`; CI CLI step |
| GLB node == collision object, per object, as triangle sets with winding (independent of the validator) | `A.FixturePackageTest` (gabled, hipped, courtyard, terrain); validator: `test_package.BindingTest`, `WindingTest` |
| Roof shape from `roof:shape` (measured) or flat (inferred); non-flat roof survives to the package | `A.test_non_flat_roofs_match_collision`; `test_scene_generation.PlanTest.test_roof_shapes_and_fallbacks`, `RoofProvenanceTest` |
| Courtyards are holes (vertical ray through the courtyard hits no building in GLB or collision) | `A.test_courtyard_hole_is_preserved`; `test_scene_generation.PlanTest.test_courtyard_roof_keeps_hole`, `OsmTest.test_courtyard_multipolygon` |
| Terrain on a slope matches the DEM (±0.2 m); heightfield == max z of terrain collision | `A.test_terrain_on_slope_matches_dem_and_heightfield`; `test_terrain_sources.LocalElevationTest` |
| ENU axes, glTF `(x, z, −y)`, Unity `(−x, z, −y)` reflection and winding flip | `A.test_axes_and_handedness_on_geographic_package` (real package); `test_geodesy.test_axis_conventions_on_asymmetric_point`; `test_package.AxesTest`, `ProbeTest` |
| Serialized orientation probes are present and agree with the GLB and collision triangles; the Unity probe check passes only with the winding reversal | `A.test_orientation_probes_match_glb_and_collision_in_unity` |
| Buildings are closed, outward, positive-volume shells | validator (`test_package.ValidatorTest`, `BindingTest`); `A.test_mirrored_building_keeps_outward_positive_volume` |
| Blender edits: move / uniform scale / negative scale (mirror) / delete / duplicate → collision follows final transforms | `A.BakeEditsAcceptanceTest`; `test_blender_bake.BakeExportTest`, `BakeTransformTest.test_mirrored_matrix_keeps_outward_winding` |
| Duplicate gets a distinct id; deleted object absent from collision, GLB and manifest | `A.test_duplicate_is_distinct_and_at_its_own_transform`, `A.test_deleted_building_is_absent_everywhere`; `test_blender_bake.test_edited_scene_exports_valid_package_with_identities` |
| Determinism: independent builds, same `created_utc` → same bytes and `package_id` | `A.DeterminismTest.test_independent_builds_have_identical_identity_and_bytes`; `test_package.PlanPackageTest.test_reproducible_identity` |
| Sampled single-byte changes in each hashed payload member (every `files[]` entry) → SHA-256 mismatch. `manifest.json` has no member hash; it is covered by the manifest-derived `package_id` | `A.DeterminismTest.test_single_byte_change_in_any_member_fails_with_hash_error`, `test_independent_builds_have_identical_identity_and_bytes`; `test_package.ValidatorTest.test_hash_mismatch` |
| Failed write keeps the previous package byte-identical | `test_package.PlanPackageTest.test_failed_export_keeps_previous_package`; `test_blender_bake.BakeExportTest.test_failed_export_keeps_previous_package` |
| Terrain grid limit enforced before any file or network access (`fetch_copernicus`, `load_local_elevation` and `pipeline.acquire`); heightfield limit, overflow and 2×2 minimum enforced at the start of `build_package` (plan generation needs no heightfield) | `A.ResourceBoundsTest`, `A.HeightfieldPreflightScopeTest`; `test_geodesy.test_area_bounds`; `test_package.ValidatorTest.test_resource_bounds` |
| Malformed packages, path safety, zip bombs, credential policy | `test_package.ValidatorTest`, `ReviewFixesTest`, `ReviewRound2Test` |
| DEM HTTP/auth/coverage/NoData/GeoTIFF failures never become flat ground | `test_terrain_sources` (`CopernicusTest`, `LocalElevationTest`, `TiffBoundsTest`, …) |

**Headless Blender** (`tests/blender/run_integration.py`, 74 checks) additionally covers the real
add-on: generation from the committed fixtures (ids, classes, report Text, rollback on a forced failure),
credential rejection in UI fields, export of an edited scene (move/rotate/scale, delete, duplicate, user
cube, Bevel and Array modifiers, mirrored building, terrain vertex edit) with collision == evaluated world
triangles, scene left unchanged by export, collection/visibility/linked-library rules, material warnings,
blocked exports (curve, zero scale, open building, credential-like names) keeping the previous package,
offline mode refusing Overpass, and no credential in the `.blend` or package.

## How to run

Unit and acceptance tests (Python 3.11+; no Blender, no network):

```
py -3.12 -W error::ResourceWarning -m unittest discover -s tests -t .
py -3.12 -m unittest tests.test_acceptance -v
```

CLI on the SYNTHETIC fixture (also run in CI):

```
py -3.12 tools\mbmap_cli.py build --osm tests\fixtures\synthetic_area.osm --dem tests\fixtures\synthetic_dem.asc --datum SYNTHETIC --dem-license "SYNTHETIC test data (no licence required)" --osm-license "SYNTHETIC test fixture (hand-written OSM-format XML, not OpenStreetMap data; no licence required)" --lat 47.0 --lon 8.0 --width 400 --height 300 --name synthetic_sample --out $env:TEMP\s.mbmap
py -3.12 tools\mbmap_cli.py validate $env:TEMP\s.mbmap
```

Headless Blender 4.2 (manual; expects `OK: 0 failure(s)`):

```
$b = "C:\tools\blender-4.2.23-windows-x64\blender.exe"
& $b --background --factory-startup --python tests\blender\run_integration.py -- "$env:TEMP\mb_it"
```

Committed sample and C# reference reader (also run in CI). `tests/test_examples.py` checks that
`examples/synthetic_sample.mbmap` validates and equals a fresh `--created-utc` build; see
[examples/README.md](../examples/README.md):

```
dotnet run -c Release --project examples\csharp\MbmapReader -- examples\synthetic_sample.mbmap
```

## Recorded results

| Date | Layer | Result |
|---|---|---|
| 2026-11-18 | Unit + acceptance (Python 3.12, Windows) | 290 tests OK (21 in `test_acceptance.py`) |
| 2026-11-18 | CLI build + validate | `VALID: 0 error(s), 1 warning(s)` (warning: 2 degenerate collision triangles) |
| 2026-11-18 | Headless Blender 4.2.23 LTS (Windows x64) | 74 PASS, `OK: 0 failure(s)`; 77 objects, 5131 collision triangles |
| PR #7 | Unit + acceptance (Python 3.12, Windows) | 295 tests OK (adds `test_examples.py`) |
| PR #7 | C# reader (.NET 8, Windows) on `examples/synthetic_sample.mbmap` | `OK`: 5 members hash-verified, 3 probes PASS with both negative controls rejected, heightfield vs terrain max \|dz\| 1e-6 m; tampered copy → `INVALID: collision/map.mbcol: SHA-256 mismatch`, exit 1 |
| format 2.0.0 | Unit + acceptance (Python 3.12, Windows) | 322 tests OK (adds `test_query.py`, class-kind, tube-rule and passage-probe tests) |
| format 2.0.0 | CLI validate of the regenerated sample | `VALID: 0 error(s), 1 warning(s)` (2 degenerate collision triangles); 74 objects, 4945 triangles, no passage probes |
| format 2.0.0 | C# reader (.NET 8, Windows) on `examples/synthetic_sample.mbmap` | `OK`: schema 2.0.0, mbcol v2, 3 orientation probes PASS, `passage none`, capsule controls BLOCKED/PASS as expected; tampered copy → `INVALID: collision/map.mbcol: SHA-256 mismatch`, exit 1 |
| format 2.0.0 review | Unit + acceptance (Python 3.12, Windows) | 329 tests OK (adds degenerate-triangle, nearly-parallel capsule, extreme ray direction, sealed-tube and probe-filter regressions) |
| format 2.0.0 review | C# reader (.NET 8, Windows) | sample `OK` with capsule self-test controls (synthetic box, collapsed triangle, nearly parallel 100 km edge, budget) as expected; a scratch package with three passage probes (one blocked only by a collapsed triangle) gives the same PASS/BLOCKED results as the Python validator |
| format 2.0.0 review round 2 | Unit + acceptance (Python 3.12, Windows) | 335 tests OK (adds grazing-ray subnormal determinant, shallow crossing of a collapsed edge, null/oversized probe metadata incl. `export_map` with a stub `bpy`, and all-degenerate capped tube shell regressions) |
| format 2.0.0 review round 2 | C# reader (.NET 8, Windows) on `examples/synthetic_sample.mbmap` | `OK`; capsule controls (adds the shallow crossing and the grazing segment) all as expected |
| DSM correction | Unit + acceptance (Python 3.12, Windows) | 359 tests OK (adds `test_dsm_correction.py`, synthetic: building/tree/forest/bridge-ribbon mask, raised block and tree bump lowered and never raised, unmasked points bit-for-bit, 5 % guard, auto/on/off per source, report/provenance/`processing` note, CLI flags, 250k-point grid) |
| DSM correction | Sample regenerated (local file, auto = off) and C# reader | `VALID: 0 error(s), 1 warning(s)`; 74 objects, 4945 triangles unchanged; only `report.json` gains `terrain_correction` (`reason: local file (opt-in off)`), new `package_id` `sha256:8ab22b98…`; C# reader `OK`; Blender 4.2.23 integration `OK: 0 failure(s)` |
| DSM harmonic fill | Unit + acceptance (Python 3.12, Windows) | 364 tests OK. The BFS + smoothing fill is replaced by a multigrid harmonic fill. New synthetic tests: a 4 % slope under a 480 m masked square is reproduced (max error 0.0000 m at 30 m spacing and 0.0022 m at 2 m; the old fill lowered it by up to about 10–15 m); a raised 20 m block is lowered to the plane (error 0.0002 m / 0.0022 m); saddle and plane boundaries satisfy the maximum principle; small, odd and thin grids match a reference solve; the largest grid (632 × 632 at 1.5 m, 360 000 masked points) has an error of 0.0013 m in about 5 s (the old fill took about 7.8 s with a 19.8 m error). Sample unchanged (local file, auto = off) |

## Not validated

* The live Copernicus DEM and Overpass services: CI uses fakes and the committed SYNTHETIC fixtures only.
* The online acquisition path inside Blender (only the offline refusal is exercised).
* Loading packages on the consumer side (Unity importer or the simulator core); the Unity mapping is
  checked only by simulating the documented importer convention (in Python and in the C# reference
  reader), not with glTFast in Unity.
* Byte-identical sample builds across operating systems: verified on Windows only. The sample test
  falls back to a 1e-4 tolerance comparison if platform maths differ.
* Performance, memory use and frame rate (FPS) of generated maps.
* Real-world data quality (OSM completeness, DEM accuracy, vertical datum correctness).
