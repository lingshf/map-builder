# S3-REVIEW: sprint 3 milestone review and test audit

Spec: [../tasks/S3-REVIEW.md](../tasks/S3-REVIEW.md) (D63). Run on main **872a536**: #41–#50, #53 and
the typing PRs #51/#52/#54. #54 merged during the review; the unit suite and G6 were run after it.
Reviewer: design (product owner).

## Verdict

**GO for REL-v0.4.0, with no v0.4.0 blockers.**

* The roof target is met against the D82 re-baseline (29/67, floor 29), not against the original ≥ 40.
  That shortfall is a disclosed limitation, as the 5/67 roof result was for v0.3.0 (D52).
* Textures, the 2.1 format and the consumer checks all pass on real data through both the CLI and headless
  Blender paths.
* The gaps below are tagged *later* (S3-F1…S3-F12). REL-v0.4.0 carries four release-note items
  (see [§4](#4-proposed-rel-v040-notes)).

| # | Check | Verdict |
|---|---|---|
| 1 | Roofs | **met against the D82 re-baseline** (29/67). Not met against the original ≥ 40. One sub-point is only partially met: 4 analytic gables have no named reason (S3-F1). |
| 2 | Textures | **met** |
| 3 | Consumer | **met** |
| 4 | Test audit | **met** (no new test > 5 s, no wall-clock gates, G6 within budget). One pre-existing test is over 5 s (S3-F3). |
| 5 | Design conformance | **met** |
| 6 | Retro notes | [§5](#5-retro-notes) |

## Method and frozen inputs

* Builds used the frozen v0.3.0 RC acquisitions for Munich Altstadt and Pittsburgh, with no downloads.
  The Blender cache file count was unchanged (16) after the runs.
* Settings followed `docs/DEMO.md`: seed 1, DSM on, terrain 10 m, heightfield 2 m, and a fixed `created_utc`.
* `git archive v0.3.0`, rebuilt from those inputs, reproduced the released package IDs exactly:
  Munich `2caff942…0eea64` and Pittsburgh `094fb730…846d16`. The v0.3.0 comparisons are therefore like for like.
* Environment: Windows, Python 3.12, Blender 4.2.23 LTS (portable, D9), and Cycles CPU for the renders.
  Timings are medians of 3 (real data) or 6 interleaved runs (fixture), with no other load.

## 1. Acceptance

### 1.1 Roofs (D61, D82, D64)

The count comes from `tests.test_roofs_munich` over all 67 tagged non-flat roofs of the frozen Munich snapshot.
It is geometry-based on the emitted triangles.

| Shape | Tagged | Counted |
|---|---|---|
| gabled | 52 | 17 |
| hipped | 12 | 11 |
| skillion | 1 | 1 |
| pyramidal | 1 | 0 |
| quadruple_saltbox | 1 | 0 |
| **total** | **67** | **29** (floor 29, D82) |

The 38 roofs that are not counted, by recorded reason:

| Count | Outcome | Named reason |
|---|---|---|
| 21 | gabled → hipped | gable end not representable: the ridge meets the gable edge outside it |
| 9 | gabled → hipped | gable end not representable: sliver gable end (`GABLE_MIN_HEIGHT_RATIO`) |
| 4 | gabled, built analytically | **none**. These are the frozen v0.3.0 near-rectangle gables that fail the checker's `planar` test; their provenance says only `measured:osm roof:shape` (S3-F1). |
| 1 | hipped → flat | footprint has a courtyard (hole) |
| 1 | quadruple_saltbox → flat | shape not modelled |
| 1 | gabled → flat | roof height 0 |
| 1 | pyramidal → flat | concave footprint (S3-F10) |

* The roof checks (overlap, gap, slopes, ridges, vertical ends) pass on every built case, as part of the
  700-test suite.
* The frozen v0.3.0 replay does not inflate (D76).
* The 30 gable-to-hipped fallbacks pass the hipped checks (D82).

**Spot renders** (Cycles CPU, Munich, textures on). The after renders are from main and the before renders
from v0.3.0. They are saved outside the repo for the coordinator to publish, as `render-<view>-{before,after}.png`.

| View | Footprint | Expected after | Seen |
|---|---|---|---|
| `gabled-skeleton` | way 91268712, L-shaped, gabled | skeleton gable | yes |
| `hipped-skeleton` | way 79401262, U-shaped, hipped | skeleton hips | yes |
| `gabled-fallback` | way 91268710, gabled | named fallback to hipped | yes |
| `overview`, `roofs` | whole area | context views | yes |

In all after renders the complex footprints carry continuous sloped roofs, where v0.3.0 had flat or box roofs.

### 1.2 Textures (D56–D60, D65)

| Package | Path | Validation | C# reader | Probes |
|---|---|---|---|---|
| Munich | CLI | VALID, 0 errors | OK | 3/3 PASS |
| Munich | headless Blender | VALID, 0 errors | OK | 3/3 PASS |
| Pittsburgh | CLI | VALID, 0 errors | OK | 13/13 PASS |
| Pittsburgh | headless Blender | VALID, 0 errors | OK | 13/13 PASS |

* There was 1 warning in each case: degenerate `.mbcol` triangles, 58–76 per area. This warning class
  existed before S3.
* The CLI and Blender probe counts now agree (3/3 and 13/13). S3-PARITY found the gap and #47 fixed it (D69),
  which closes the v3 parity item from D52.

**GLB:**

* Embedded images: 5 PNGs, 511,404 bytes in total.
* `extensionsRequired`: none.
* `TEXCOORD_0` on 546 of 548 primitives (Munich) and 2,315 of 2,317 (Pittsburgh).
* Materials: 7 (Munich) and 8 (Pittsburgh), keyed by parameter digest (D88).
* `asset_notices` lists the 5 image SHA-256s with licence CC0-1.0, and `NOTICES.txt` has an "Assets"
  section (D65/D86).

**three.js viewer:**

* The Munich bundle (`map.glb` = package `bc06f0cbd4fb`) was served locally and captured with headless Edge
  using SwiftShader WebGL.
* Facade, roof, grass and asphalt textures are visible, and all 3 probes are listed as PASS.
* The capture is saved outside the repo as `viewer-munich.png`.

**Size (D60: texture set ≤ 2 MiB; GLB growth ≤ +35 % plus texture bytes):**

| | v0.3.0 / untextured GLB | Textured GLB | Growth excluding image bytes | Package |
|---|---|---|---|---|
| Pittsburgh | 12,220,712 | 15,005,532 | +18.6 % | 4,258,810 → 5,346,074 |
| Munich (same geometry, `--no-textures`) | 3,235,604 | 4,378,796 | +19.5 % (+23.1 % against v0.3.0, which includes the new roof geometry) | 894,578 → 1,587,709 |

* The texture set is 6 PNGs, 654,263 bytes.
* The PNGs are deflated again inside the zip, which costs time and saves nothing (S3-F5).

**Licence in the zip:**

* `blender --command extension build` produced `map_builder-0.3.0.zip` (873,675 bytes).
* The zip contains `assets/textures/LICENSE-textures.txt` and all 6 PNGs.
* `tests.test_textures.ExtensionZipTest` passes with `MB_EXTENSION_ZIP` set (3 tests), matching `release.yml`.

### 1.3 Consumer (drone-flight-simulator)

* **2.0-only reader path.** The frozen v0.3.0 Python validator and the frozen v0.3.0 C# reader accept all 4
  textured 2.1 packages (VALID / OK, every probe PASS, 0 BLOCKED). They ignore `asset_notices` and the
  images, as documented in D57/D65.
* **Collision unchanged.** `.mbcol` is byte-identical with textures on and off in both areas.
  * Pittsburgh `.mbcol` and the heightfield are byte-identical to v0.3.0.
  * Munich `.mbcol` differs from v0.3.0 only by the new roof triangles. Its heightfield is identical.
* The Pittsburgh `--no-textures` GLB is byte-identical to v0.3.0; the manifest differs only in `schema_version`.
  D60's "reproduces the v0.3.0 layout" holds.
* Simulator impact is unchanged from the plan: optional textures for Unity (glTFast via the D66 proxy), and
  more roof triangles in `.mbcol` for Munich-like areas. No reader change is required.

## 2. Test audit

The full suite, with `-W error::ResourceWarning` and nothing else running: **700 tests, OK (1 skipped),
116.1 s.**

Slowest tests:

| Time | Test | Origin |
|---|---|---|
| 5.47 s | `test_bridges.CrossingTest.test_clearance_over_a_road_at_45_degrees_agrees_with_rays_on_the_exported_meshes` | S1 (#21/#32), pre-existing (S3-F3) |
| 3.34 s | `test_dsm_correction.HarmonicFillTest.test_largest_grid_is_reproduced_in_bounded_time` | v2 |
| 3.03 s | `test_package.TexturedPackageTest.test_each_negative_fixture_fails_with_its_rule` | **S3, slowest new test** |
| 2.68 s | `test_package.PipelineTest.test_cache_override_pass_through` | v1 |
| 2.38 s | `test_dsm_correction.ReviewRound1Test.test_many_holes_rasterise_in_bounded_memory` | v2 |
| 1.75 s | `test_textures.GeneratorTest.test_regenerated_bytes_equal_committed_files` | S3 |
| 1.66 s | `test_csharp_parity.CsharpCapsuleParityTest.test_shared_budget_boundary_matches_python` | v2 |

* **No new test is over 5 s.** The only test over 5 s predates S3 and is environment-sensitive; S2-REVIEW
  recorded 5.16–7.07 s on the reviewer's machine.
* **No wall-clock gates.** The only clock in tests is the injected `FakeClock` in
  `test_terrain_sources` (DeadlineTest). The S3 performance claims are recorded in PRs (D85/D87) and not
  asserted in tests.
* **Hygiene.** `test_demo_bundle.py:51` leaks a file handle (`json.load(open(...))`). It emits a
  ResourceWarning that `-W error::ResourceWarning` does **not** turn into a failure, because the warning is
  raised in a finalizer ("Exception ignored") (S3-F2).
* **Typing #54** merged on 872a536 during the review. The suite above ran on it. The committed sample is
  byte-identical to a fresh build (below), so #54 has no behaviour change (D79).

**G6: fixture build against v0.3.0.** CLI synthetic fixture, 6 interleaved runs, medians:

| Build | Median | Against v0.3.0 |
|---|---|---|
| v0.3.0 | 1.003 s | — |
| main `--no-textures` | 1.055 s | **+5.2 %** |
| main, textured (default) | 1.204 s | +20.0 % |

* The textured overshoot is the fixed per-package PNG cost (embedding and deflating 5 images), which
  dominates a 400×300 m fixture. It does not gate (D81/D87).
* The Pittsburgh CLI build, as the real-data measure: v0.3.0 19.26 s, main `--no-textures` 19.31 s
  (+0.3 %), main textured 22.61 s (+17.4 %).
* Headless Blender Generate with textures: Munich 4.64 s, Pittsburgh 17.87 s. The D85 whole-Generate gate
  was +8.8 % in #53.
* Byte identity:
  * The main textured fixture build is **byte-identical** to the committed `examples/synthetic_sample.mbmap`.
  * Main `--no-textures` differs from v0.3.0 only in `manifest.json` (schema 2.1.0 against 2.0.0).

## 3. Design conformance

* **Skeleton isolation (D55).** `core/skeleton.py` imports only `math`, `dataclasses`, `errors` and
  `triangulate`, so it has no OSM or Blender dependency.
* **The roof track stayed in its lane.** Since v0.3.0, `generate.py` was changed only by #48 and #50, in the
  roof section. The preflight `plan_roof` runs before reservation and the skeleton faces are triangulated
  explicitly (D64).
* **UVs are post-hoc (D59).** `core/uv.py` (`assign_uvs`, `textured_copy`, `textured_materials`; about
  250 lines) runs after generation. The texture track did not touch `generate.py` or `roofs.py`.
* **No over-engineering.**
  * `core/textures.py` is a fixed table.
  * Export material identity is the D88 parameter digest (`blender/export.py` `_material_key`).
  * There is no material registry, no plug-in system and no speculative extension handling.
  * SOLID is satisfied at the module level: one responsibility per new module, and the dependencies point
    inward (core ← blender).
* **Harness ownership (D64).** Only #49 regenerated the sample. The roof tasks kept it byte-identical.

## 4. Gaps and S3-Fn tasks

None of these is a v0.4.0 blocker.

| id | Gap | Severity | Tag | Suggested conflict domain |
|---|---|---|---|---|
| S3-F1 | 4 analytic near-rectangle gables fail the checker's `planar` test and carry no named reason in provenance, so the "every fallback named" check is only partially met. Fix the warp (see S3-F7) or record the reason. | low | later (disclose in REL) | `core/roofs.py` |
| S3-F2 | ResourceWarning leak in `test_demo_bundle.py:51`; finalizer warnings escape `-W error`. | low | later | `tests/test_demo_bundle.py` |
| S3-F3 | `test_bridges` 45° crossing takes 5.5 s (pre-existing). Shrink its input. | low | later | `tests/test_bridges.py` |
| S3-F4 | `assign_uvs` is pure Python: `build_scene` is +62 % (0.97 → 1.70 s, Pittsburgh, D87). | medium | later | `core/uv.py` |
| S3-F5 | Store PNGs with ZIP_STORED in the package (they are already compressed). | low | later | `core/package.py` |
| S3-F6 | bbox float32 precision (D74). | low | later | `blender/` centre/bbox |
| S3-F7 | Largest-triangle reference-plane warp in the planarity handling. | low | later | `core/roofs.py`, `tests/roof_checks.py` |
| S3-F8 | 9007 near-axis fixture sensitivity. | low | later | roof fixtures and tests |
| S3-F9 | Loose legacy reservation bounds. | low | later | `core/generate.py` (roof section) |
| S3-F10 | S4 roofs: vertical cuts across chamfered or angled gable ends, mixed gable + hip ends (D82), and pyramidal roofs on concave footprints via the skeleton. | medium | later (S4) | `core/roofs.py`, `core/skeleton.py` |
| S3-F11 | "MB Default" material name gets a digest suffix. | low | later | `blender/export.py` |
| S3-F12 | `.mbcol` degenerate-triangle warnings (58–76 per area), pre-existing; consider dropping zero-area triangles at bake. | low | later | `core/collision.py`, `blender/bake.py` |

<a id="4-proposed-rel-v040-notes"></a>
**Notes for REL-v0.4.0** (no new tasks):

1. Bump `GENERATOR_VERSION` to 0.4.0 through the D50 drift guard. Main still says 0.3.0, and the built zip
   is `map_builder-0.3.0.zip`.
2. Release notes:
   * State the roofs as **29/67 built as tagged** (from 5/67), per shape, against the original ≥ 40 (D82).
     Name the 4 unreasoned analytic gables (S3-F1).
   * Give the texture size numbers from §1.2.
   * State that `.mbcol` is unaffected by textures.
3. Attach the textured Munich and Pittsburgh `.mbmap` from both evidence paths (D53.1). Include the viewer
   capture and the before/after roof renders.
4. Re-run the frozen-input comparison in the RC. The v0.3.0 package IDs above are the reference.

## 5. Retro notes

* **The geometric checker plus the frozen replay held.** The shared `roof_checks` judge emitted triangles:
  merged coplanar facets (D80), slope counts (D71), triangle-order invariance (D73) and independent overlap
  and gap checks (D64). Run against a frozen v0.3.0 replay, they caught 8 valid hipped roofs rejected by an
  over-tight signature (D76). They also rejected 2 v0.3.0 gables as non-planar (D70) without any loosening.
  This is D39 again, applied to roofs.
* **Re-baselining honestly beat chasing the number.** D82 re-baselined to the exact measured 29, with the
  rest named and deferred. That is better than relaxing the checker to reach 40.
* **Fixed costs distort tiny fixtures.** The PNG embedding cost is constant, so +20 % on the fixture is
  +6.6 % whole-Generate on Pittsburgh (D87). Performance gates should be measured on the whole Generate
  (D85) and on real data.
* **Identity by parameters (D88).** Keying export materials by a digest of their exact parameters, not a
  display name, makes material identity independent of naming. This pairs with D86: textures, materials and
  NOTICES must agree.
* **Parallel typing worked** (D79/D83). It was annotation-only, avoided the hot files and used local mypy.
  Three PRs landed alongside feature work without conflicts or byte changes.
* **New: `-W error::ResourceWarning` gives incomplete assurance.** Leaks found in finalizers are printed and
  not raised (S3-F2). Use context managers in tests. A future CI hardening could fail on the
  "Exception ignored" output.
