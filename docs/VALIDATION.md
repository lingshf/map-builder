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
| Buildings are closed, outward, positive-volume shells | validator (`test_package.ValidatorTest`, `BindingTest`); `A.test_mirrored_building_keeps_outward_positive_volume` |
| Blender edits: move / uniform scale / negative scale (mirror) / delete / duplicate → collision follows final transforms | `A.BakeEditsAcceptanceTest`; `test_blender_bake.BakeExportTest`, `BakeTransformTest.test_mirrored_matrix_keeps_outward_winding` |
| Duplicate gets a distinct id; deleted object absent from collision, GLB and manifest | `A.test_duplicate_is_distinct_and_at_its_own_transform`, `A.test_deleted_building_is_absent_everywhere`; `test_blender_bake.test_edited_scene_exports_valid_package_with_identities` |
| Determinism: independent builds, same `created_utc` → same bytes and `package_id` | `A.DeterminismTest.test_independent_builds_have_identical_identity_and_bytes`; `test_package.PlanPackageTest.test_reproducible_identity` |
| Any single-byte change in any member → SHA-256 mismatch | `A.DeterminismTest.test_single_byte_change_in_any_member_fails_with_hash_error`; `test_package.ValidatorTest.test_hash_mismatch` |
| Failed write keeps the previous package byte-identical | `test_package.PlanPackageTest.test_failed_export_keeps_previous_package`; `test_blender_bake.BakeExportTest.test_failed_export_keeps_previous_package` |
| Area/grid/heightfield limits enforced before any network access | `A.ResourceBoundsTest`; `test_geodesy.test_area_bounds`; `test_package.ValidatorTest.test_resource_bounds` |
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
py -3.12 tools\mbmap_cli.py build --osm tests\fixtures\synthetic_area.osm --dem tests\fixtures\synthetic_dem.asc --datum SYNTHETIC --dem-license "SYNTHETIC test data (no licence required)" --lat 47.0 --lon 8.0 --width 400 --height 300 --name synthetic_sample --out $env:TEMP\s.mbmap
py -3.12 tools\mbmap_cli.py validate $env:TEMP\s.mbmap
```

Headless Blender 4.2 (manual; expects `OK: 0 failure(s)`):

```
$b = "C:\tools\blender-4.2.23-windows-x64\blender.exe"
& $b --background --factory-startup --python tests\blender\run_integration.py -- "$env:TEMP\mb_it"
```

## Recorded results

| Date | Layer | Result |
|---|---|---|
| 2026-11-18 | Unit + acceptance (Python 3.12, Windows) | 285 tests OK (16 in `test_acceptance.py`) |
| 2026-11-18 | CLI build + validate | `VALID: 0 error(s), 1 warning(s)` (warning: 2 degenerate collision triangles) |
| 2026-11-18 | Headless Blender 4.2.23 LTS (Windows x64) | 74 PASS, `OK: 0 failure(s)`; 77 objects, 5131 collision triangles |

## Not validated

* The live Copernicus DEM and Overpass services: CI uses fakes and the committed SYNTHETIC fixtures only.
* The online acquisition path inside Blender (only the offline refusal is exercised).
* Loading packages on the consumer side (Unity importer or the simulator core); the Unity mapping is
  checked only by simulating the documented importer convention.
* Performance, memory use and frame rate (FPS) of generated maps.
* Real-world data quality (OSM completeness, DEM accuracy, vertical datum correctness).
