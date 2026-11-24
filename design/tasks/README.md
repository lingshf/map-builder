# v2 task table

Maintained by the Design role. Approach, sprints and decisions: [../roadmap.md](../roadmap.md). This is the **single Backlog authority**; process, roles, cadence and permissions are in the [team charter](../team-charter.md).
Status values: `blocked` (dependency open), `ready`, `in progress`, `review`, `done`.

Every task doc lists its acceptance criteria, performance considerations, expected tests and
its **conflict domain**. Only run tasks in parallel whose hard conflict domains are disjoint.
*Soft* domains (`examples/synthetic_sample.mbmap`, append-only rows in
`tests/fixtures/synthetic_area.osm`, the "Recorded results" table of `docs/VALIDATION.md`,
each task's own bullet in README Limits / PACKAGE_FORMAT unsupported list) are resolved by
rebasing and regenerating (D20), so they do not block parallel work; the coordinator merges one
PR at a time. Releases happen only in the REL tasks (D17, D28).

| id | sprint | owner | dependencies | conflict domain (hard) | status | PR |
|---|---|---|---|---|---|---|
| [DSM](https://github.com/lingshf/map-builder/pull/11) | pre | dev (old process) | — | `core/dsm.py`, `core/osm.py`, `core/generate.py`, `core/pipeline.py`, Blender props/ui/sources, CLI | done | #11 |
| [S1-RELEASE-WF](S1-RELEASE-WF.md) | S1 | dev | — | `.github/workflows/release.yml`, `docs/releases/README.md` | done | #13 |
| [REL-v0.1.0](REL-v0.1.0.md) | S1 | release manager | #11, #13 | `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.1.0/`, `docs/releases/v0.1.0.md` | done | #16 |
| [S1-DEMOKIT](S1-DEMOKIT.md) | S1 | dev | — | `tools/demo/` (new), `tests/test_demo_bundle.py` | done | #14 |
| [S1-SEAMS](S1-SEAMS.md) | S1 | dev | #11 | `core/osm.py` (`_unsupported_reason`, `Classified`, routing), `core/generate.py` (`ScenePlan`, `build_plan` stage hooks), new `core/structures.py`, stub `core/bridges.py` / `core/tunnels.py` / `core/passages.py`, `blender/scene_build.py`, `tests/blender/*` (split into modules) | done | #19 |
| [S1-BRIDGE](S1-BRIDGE.md) | S1 | dev | S1-SEAMS | `core/bridges.py`, `core/generate.py` (bridge hook only), `tests/test_bridges.py`, `tests/blender/checks_bridges.py` | done | #21 |
| [S1-TUNNEL](S1-TUNNEL.md) | S1 | dev | S1-SEAMS | `core/tunnels.py`, `core/generate.py` (tunnel hook only), `tests/test_tunnels.py`, `tests/blender/checks_tunnels.py` | done | #22 |
| [S1-PIERS](S1-PIERS.md) | S1 | dev | S1-BRIDGE | `core/bridges.py`, `tests/test_bridges.py` | done | #26 |
| [REL-v0.2.0](REL-v0.2.0.md) | S1 | release manager | DEMOKIT, SEAMS, BRIDGE, PIERS, TUNNEL, REL-v0.1.0 | version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.2.0/`, `docs/releases/v0.2.0.md` | done (released `v0.2.0` on `4e0b0e2`) | #28 |
| [S1-REVIEW](S1-REVIEW.md) | S1 | design | REL-v0.2.0 RC | `design/` only | done | #29, [report](../reviews/S1-REVIEW.md) |
| [S2-ROOF](S2-ROOF.md) | S2 (may start in S1) | dev | #11 | `core/generate.py` (roof section of `build_building` only), new `core/roofs.py`, `tests/test_roofs.py` | done | #18 |
| [S2-ELEV](S2-ELEV.md) | S2 | dev | S1-SEAMS | `core/passages.py`, `core/generate.py` (building loop in `build_plan` only), `tests/test_passages.py`, `tests/blender/checks_passages.py` | done | #24 |
| [REL-v0.3.0](REL-v0.3.0.md) | S2 | release manager | ELEV, ROOF, v0.2.0 tagged, S1-F1, S1-F2 (all done), S2-REVIEW (D48), S2-F1, S2-F2, S2-F3, S2-F6 (all done) | version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.3.0/`, `docs/releases/v0.3.0.md`, `docs/DEMO.md` | done | #38, #39 |
| TEST-HYGIENE | S1 | dev | — | `tests/test_dsm_correction.py`, `tests/test_scene_generation.py`, `tests/test_package.py`, `tools/demo/presets/pittsburgh.json` | done | #23 |
| PERF-PROBE-INDEX | S1 | dev | — | `core/query.py`, `core/structures.py` | closed (D44/D45) | #25 |
| FIX-CS-PROBE-PARITY | S1 | dev | — | `examples/csharp/MbmapReader/`, `core/package.py` (`mb_id` regex), `tests/test_csharp_parity.py`, `.github/workflows/ci.yml` | done (D46) | #27 |
| [S1-F2](S1-F2.md) | S2 | dev | — | `tests/test_terrain_sources.py` | done (`c9fd1aa`) | #31 |
| [S1-F1](S1-F1.md) | S2 | dev | — | `core/bridges.py` (approach detection) | done (`2de9024`) | #32 |
| [S2-REVIEW](S2-REVIEW.md) | S2 | design | S1-F1, S1-F2; runs **before** REL-v0.3.0 (D48) | `design/` only | done | #33, [report](../reviews/S2-REVIEW.md) |
| [S2-F1](S2-F1.md) | S2 | dev | S2-REVIEW | `tests/test_terrain_sources.py` | done | #35 |
| [S2-F2](S2-F2.md) | S2 | dev | S2-REVIEW; area per D49 | `tools/demo/presets/<area>.json` (new), `tests/test_demo_bundle.py` (preset rows), new excerpt tests/fixtures | done | #36 |
| [S2-F3](S2-F3.md) | S2 | dev | S2-REVIEW | `tests/blender/checks_roofs.py` (new); soft: fixture OSM, sample, VALIDATION | done | #34 |
| S2-F6 | S2 | dev | REL-v0.3.0 finding (D51): headless Blender Pittsburgh export rejected a down-facing road sliver | `core/generate.py` (`drop_unstorable_slivers` only), `tests/test_scene_generation.py`, `tests/blender/checks_slivers.py` (new); soft: VALIDATION | done | #37 |
| S2-F5 | v3 | dev | — | `core/roofs.py` (gabled/hipped on non-rectangular footprints); soft: `tests/test_roofs.py` | superseded by S3-ROOF-CASES/SKELETON/HIPPED/GABLED (D54): REL-v0.3.0 found 62 of 67 tagged non-flat Munich roofs fall back (53 flat, 9 pyramidal), 46 of them gabled/hipped on non-rectangular footprints | |

## Sprint 3 (v0.4.0)

Scope D54; decisions D55–D88 in [../roadmap.md](../roadmap.md#v3-sprint-3-v040--non-rectangular-roofs-and-textures).

| id | sprint | owner | dependencies | conflict domain (hard; soft) | status | PR |
|---|---|---|---|---|---|---|
| [S3-ROOF-CASES](S3-ROOF-CASES.md) | S3 | dev | — | `tests/fixtures/munich_roofs.osm`, `munich_roofs_expected.json`, `roof_counterexamples.osm`, `tests/roof_checks.py`, `tests/test_roofs_munich.py` (all new), `tests/fixtures/README.md`; soft: `tests/test_skeleton.py` (whichever of CASES/SKELETON merges second switches it to the shared checker; CASES did, #43) | done | #43 (6dce54d) |
| [S3-SKELETON](S3-SKELETON.md) | S3 | dev | — | `core/skeleton.py`, `tests/test_skeleton.py` (new) | done | #41 (44cde70) |
| [S3-ROOF-HIPPED](S3-ROOF-HIPPED.md) | S3 | dev | S3-SKELETON, S3-ROOF-CASES | `core/roofs.py`, `core/generate.py` (building roof section ~446–580 only), `tests/test_roofs.py`, `tests/test_roofs_munich.py`, `tests/blender/checks_roofs.py`; soft: VALIDATION row | done | #48 (bce89c8) |
| [S3-ROOF-GABLED](S3-ROOF-GABLED.md) | S3 | dev | S3-ROOF-HIPPED | same as HIPPED (serialised) | done (D82 re-baseline 29/67) | #50 (9d22181) |
| [S3-TEX-FORMAT](S3-TEX-FORMAT.md) | S3 | dev | — | `core/glb.py`, `core/mesh.py`, `core/package.py` (schema-version writing, `asset_notices`, notices; sole S3 owner, D65), `tests/make_textured_fixture.py` (new), `examples/csharp/MbmapReader/**`, `docs/PACKAGE_FORMAT.md`, `tests/test_package.py`, `tests/test_csharp_parity.py`, `.github/workflows/ci.yml` (C# job); soft: `docs/UNITY_CORE_HANDOFF.md`. Not the schema constant or sample (D64) | done | #42 (f9fb660) |
| [S3-TEX-ASSETS](S3-TEX-ASSETS.md) | S3 | dev | — (third wave-5a lane after CASES) | `tools/textures/**`, `map_builder/assets/textures/**`, `core/textures.py`, `tests/test_textures.py` (all new); soft: README licence, `blender_manifest.toml` | done | #46 (cfae512) |
| [S3-TEX-UV-CORE](S3-TEX-UV-CORE.md) | S3 | dev | S3-TEX-FORMAT, S3-TEX-ASSETS | `core/uv.py`, `tests/test_uv.py` (new), `core/pipeline.py`, `tools/mbmap_cli.py`, `core/__init__.py` (schema 2.1.0), **`examples/synthetic_sample.mbmap` (sole S3 owner, D64)**, VALIDATION sample rows; soft: README CLI | done | #49 (740a147) |
| [S3-TEX-BLENDER](S3-TEX-BLENDER.md) | S3 | dev | S3-TEX-UV-CORE | `blender/scene_build.py`, `bake.py`, `export.py`, `sources.py`, `ui.py`, `props.py`, `operators.py`, `tests/blender/checks_textures.py` (new); soft: `tests/blender/run_integration.py` (one line) | done | #53 (54fc028) |
| [S3-PARITY](S3-PARITY.md) | S3 | dev | — (½ day, D62) | `tests/blender/checks_parity.py` (new); soft: `run_integration.py` (one line), optional VALIDATION note; only if fixing: `blender/bake.py` probe export (serialise with S3-TEX-BLENDER) | done (fix in S3-PARITY-FIX) | #45 (b3aaf63), #47 (9c99745) |
| S3-TYPING | S3 | dev | — (D79, D83) | annotations only; no behaviour change. The roof/#46 files were avoided only temporarily, while those PRs were open (D79); #54 annotated them afterwards | done | #51 (aa2a979), #52 (cc1d653), #54 (872a536) |
| [S3-REVIEW](S3-REVIEW.md) | S3 | design | all S3 dev tasks | `design/` only | done (GO, no v0.4.0 blockers) | #55 (e266a1b) |
| [REL-v0.4.0](REL-v0.4.0.md) | S3 | release manager | S3-REVIEW and its blocker S3-Fn tasks | version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.4.0/`, `docs/releases/v0.4.0.md` | done (released `v0.4.0` on `18f0822`; PO ACCEPT) | #56 |
| S3-F1 | later | dev | — | `core/roofs.py` | → S4-ROOF-NAMED — analytic near-rectangle gables: planar failure has no named reason (4 Munich roofs) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F2 | later | dev | — | `tests/test_demo_bundle.py` | → S4-TEST-HYGIENE — ResourceWarning leak in a test (finalizer escapes `-W error`) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F3 | later | dev | — | `tests/test_bridges.py` | → S4-TEST-HYGIENE — shrink the 5.5 s 45° bridge-crossing test ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F4 | later | dev | — | `core/uv.py` | → S4-PERF-UV — `assign_uvs` pure-Python cost (Pittsburgh `build_scene` stage +62 % textured, D85; +75 % untextured, D87) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F5 | later | dev | — | `core/package.py` | closed (D96: PNGs are inside the GLB) → S4-PERF-PKG single-pass deflate — ZIP_STORED for PNGs in the package ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F6 | later | dev | — | `blender/` centre/bbox | → S4-BLENDER-HYGIENE — bbox float32 precision (D74) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F7 | later | dev | — | `core/roofs.py`, `tests/roof_checks.py` | → S4-ROOF-NAMED — largest-triangle reference-plane warp ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F8 | later | dev | — | roof fixtures/tests | → S4-ROOF-NAMED — 9007 near-axis fixture sensitivity ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F9 | later | dev | — | `core/generate.py` (roof section) | → S4-ROOF-NAMED — loose legacy reservation bounds ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F10 | later | dev | — | `core/roofs.py`, `core/skeleton.py` | → S4-ROOF-ENDS — S4 roofs: chamfered/angled and mixed gable ends; pyramidal on concave footprints ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F11 | later | dev | — | `blender/export.py` | → S4-BLENDER-HYGIENE — "MB Default" material digest suffix ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F12 | later | dev | — | `core/collision.py`, `blender/bake.py` | → S4-COL-DEGEN — `.mbcol` degenerate-triangle warnings (pre-existing) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F13 | later | dev | — | textures | → S4-TEX-WATER — the river looks green with textures on (PO review of #56) | |

Sample and harness ownership (D64): only S3-TEX-UV-CORE changes `examples/synthetic_sample.mbmap`
and the default schema version; roof tasks keep the sample byte-identical and add their synthetic cases as
scratch OSM in `tests/blender/checks_roofs.py`; v0.3.0 comparisons use frozen inputs (the committed Munich roof
snapshot, the unchanged sample input, a recorded acquisition SHA-256).

Parallel safety: the roof track owns `core/roofs.py` and the building roof section of `generate.py` and the texture track never edits it or
`generate.py` (D59); `core/glb.py` is only in S3-TEX-FORMAT; `blender/bake.py` only in
S3-TEX-BLENDER (and S3-PARITY's optional fix, serialised). Every S3 task touching probes
(S3-PARITY) runs the Pittsburgh check in Python and C# in its PR (D47).

## Sprint 4 (v0.5.0)

Theme D93; decisions D94–D153 (D112 adds S4-WATER-SURFACE, D123 adds S4-WATER-BANK, D126 and D129 add S4-COL-FLOAT and S4-COL-FLOAT-2, D128 adds S4-MYPY), measured baselines and budgets in [../roadmap.md](../roadmap.md#v4-sprint-4-v050--quality-closeout-and-publishing-readiness).

| id | sprint | owner | dependencies | conflict domain (hard; soft) | status | PR |
|---|---|---|---|---|---|---|
| [S4-ROOF-SPIKE](S4-ROOF-SPIKE.md) | S4 | dev | — (½ day, D95) | none merged (scratch branch) | done (scratch, closed) | #60 |
| [S4-ROOF-NAMED](S4-ROOF-NAMED.md) | S4 | dev | — | `core/roofs.py`, `core/generate.py` (roof section, reservation), `tests/roof_checks.py` (reference plane), `tests/test_roofs*.py`, `munich_roofs_expected.json`; soft: sample slot (D103), VALIDATION | done | #62 (aea5fd9) |
| [S4-ROOF-ENDS](S4-ROOF-ENDS.md) | S4 | dev | S4-ROOF-SPIKE, S4-ROOF-NAMED, stretch recorded after the final-checker replay (D95) | `core/roofs.py`, `core/skeleton.py`, `core/generate.py` (roof section), `tests/test_roofs*.py`, `tests/test_skeleton.py`, `tests/blender/checks_roofs.py`; soft: sample slot, VALIDATION | done | #67 (d8100cd) |
| [S4-PERF-PKG](S4-PERF-PKG.md) | S4 | dev | — | `core/package.py` (writer, validator internals; byte- and message-identical, D97) | done | #63 (a20474a) |
| [S4-TEX-WATER](S4-TEX-WATER.md) | S4 | dev | — | `tools/textures/**`, `map_builder/assets/textures/terrain_*` + `LICENSE-textures.txt`, `core/textures.py`, `core/uv.py` (mean-albedo entry), `tests/test_textures.py`; soft: sample slot | done | #61 (fd104e7) |
| [S4-PERF-UV](S4-PERF-UV.md) | S4 | dev | S4-TEX-WATER | `core/uv.py` (byte-identical, D97) | done | #64 (a06acf5) |
| [S4-BLENDER-HYGIENE](S4-BLENDER-HYGIENE.md) | S4 | dev | — | `blender/export.py` (material naming), `blender/bake.py` (default material, bbox), bbox code in `blender/sources.py`/`props.py`, new Blender checks; soft: `run_integration.py` | done | #66 (7822d50) |
| [S4-COL-DEGEN](S4-COL-DEGEN.md) | S4 | dev | S4-BLENDER-HYGIENE | `core/collision.py`, `blender/bake.py`, `blender/export.py` (degenerate handling), collision tests; soft: sample slot, VALIDATION | done | #71 (70d93c7) |
| [S4-TEST-HYGIENE](S4-TEST-HYGIENE.md) | S4 | dev | — | `tests/test_csharp_parity.py`, `tests/test_demo_bundle.py`, `tests/test_bridges.py` (45° test), `NuGet.config` (new), MbmapReader `.csproj` (build props), `ci.yml` (C# job), test bootstrap | done | #65 (44337ad) |
| [S4-FORMAT-POLICY](S4-FORMAT-POLICY.md) | S4 | dev | **S4-TEST-HYGIENE** (hard: frozen C# fixture uses its build harness); S4-PERF-PKG only for a `package.py` edit | `docs/PACKAGE_FORMAT.md` and `docs/UNITY_CORE_HANDOFF.md` (new sections, stale 2.0.0 paragraph), `tests/test_format_policy.py` (new), C# test harness (use; edits serialised after TEST-HYGIENE) | done | #68 (268878a) |
| [S4-EXT-READY](S4-EXT-READY.md) | S4 | dev | — | `.github/workflows/release.yml`, `tests/test_manifest.py` (new), `docs/PLATFORM_SUBMISSION.md` (new), `blender_manifest.toml` (non-version fields) | done | #69 (4233995) |
| [S4-WATER-SURFACE](S4-WATER-SURFACE.md) | S4 (D112) | dev | S4-COL-DEGEN (shared `blender/bake.py`/`export.py`) | `core/water.py` (new), `core/osm.py` (`area_class`, `classify` waterways; no selector change), `core/generate.py` (terrain/landcover section, coverage), `core/bridges.py` (deck ground rule, piers, under-probe), `blender/scene_build.py`/`bake.py`/`export.py` (water objects), `tests/test_water.py` (new), `tests/test_bridges.py`, `docs/PACKAGE_FORMAT.md`, `docs/UNITY_CORE_HANDOFF.md`; soft: sample slot (D103), VALIDATION, `docs/demo/` | done | #72 (d38d4e8) |
| [S4-REVIEW](S4-REVIEW.md) | S4 | design | the pre-review lanes A–C: ROOF-SPIKE/NAMED/ENDS, PERF-PKG, BLENDER-HYGIENE, COL-DEGEN, WATER-SURFACE, TEX-WATER, PERF-UV, TEST-HYGIENE, FORMAT-POLICY, EXT-READY (WATER-BANK, COL-FLOAT, COL-FLOAT-2 and MYPY follow the review) | `design/` only | done (GO after S4-WATER-BANK, D123) | #73 |
| [S4-WATER-BANK](S4-WATER-BANK.md) | S4 (S4-F1, **v0.5.0 blocker**, D123) | dev | S4-WATER-SURFACE | `core/generate.py` (`build_terrain` colour choice, its call in `build_plan`), `tests/test_water.py`, `tests/blender/checks_water.py`; soft: sample slot (D103). Crops are PR evidence, no `docs/demo/` | done | #74 (7c24dc3) |
| S4-COL-FLOAT | S4 (**v0.5.0 blocker**, D126) | dev | S4-WATER-BANK | `core/generate.py` (road drape source), `tools/floating_audit.py` (new), `tools/water_replay.py`; soft: sample slot (D103), VALIDATION | done (no spec; criteria in the PR) | #76 (53c54d3) |
| [S4-COL-FLOAT-2](S4-COL-FLOAT-2.md) | S4 (**v0.5.0 blocker**, D126, D129) | dev | S4-COL-FLOAT | `core/shore.py`, `core/overlap.py` (new), `core/water.py`, `core/generate.py` (water stage, ramp objects), `core/package.py` (`_MB_ID`), `tools/floating_audit.py`, `tools/water_replay.py`, their tests, `docs/PACKAGE_FORMAT.md`, `docs/UNITY_CORE_HANDOFF.md`; soft: sample slot (D103), VALIDATION | done (merged under D135 coordinator verification, D146) | #77 (db9db44) |
| [S4-MYPY](S4-MYPY.md) | S4 (**v0.5.0 blocker**, D128) | dev | **S4-COL-FLOAT-2** (merged, db9db44) | `pyproject.toml` (`[tool.mypy]`), `.github/workflows/ci.yml` (mypy step), the files with mypy errors after #77 | ready | |
| S4-F2 | later (D124) | dev | S4-WATER-BANK | `core/water.py` (UVs), `map_builder/assets/textures/`, NOTICES | → S5-TEX-WATER: texture "MB Water" | |
| S4-F3 | later | dev | — | `core/water.py`, `core/osm.py` | → S5 water coverage: standalone `water=*`, riverbank multipolygons, coastline | |
| S4-F4 | later | dev | — | `core/generate.py` (landcover colours), `core/textures.py` | → S5: default tint for untagged ground (near-white since D99) | |
| S4-F5 | later or REL docs | dev | — | `docs/PACKAGE_FORMAT.md` | → stale C# line citations (+50 after #72) | |
| S4-F6 | later | dev | S4-F4 | `core/generate.py` (`build_terrain`) | → S5: landcover edge staircase (per-cell colours) | |
| S4-F7 | later | dev | — | `tests/test_col_degen.py` | → test hygiene: 6.1 s incl. C# build | |
| [S4-F8](S4-F8.md) | S5, first (D148, D149, D156; ∥ S5-STYLE-BASE) | dev | v0.5.0 merged (6535f38) | step 1 root cause; (A) `tools/floating_audit.py` + tests, or (B) the owning generator stage named by step 1 (building section of `core/generate.py` or `core/collision.py`) + tests; soft: sample slot only if it changes | done: audit-only visual/collision edge ambiguity; collision correct (D159; not the original case A) | #83 (93b8d9a) |
| [REL-v0.5.0](REL-v0.5.0.md) | S4 | release manager | S4-REVIEW, S4-WATER-BANK, S4-COL-FLOAT, S4-COL-FLOAT-2, S4-MYPY (D133) | version files (`map_builder/__init__.py`, `map_builder/core/__init__.py`, `blender_manifest.toml`), `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.5.0/`, `docs/releases/v0.5.0.md`, `docs/DEMO.md`, `docs/PACKAGE_FORMAT.md` (shared with COL-FLOAT-2), `docs/VALIDATION.md`, `examples/README.md`, the D103 sample slot (`examples/synthetic_sample.mbmap`) | done (GO at cd1112c; [close review](../reviews/REL-v0.5.0-close.md); tag and publication are the user's decision) | #75 (6535f38) |

Parallel safety: `core/roofs.py` belongs only to lane A (serialised); `core/package.py` only to S4-PERF-PKG
(then FORMAT-POLICY if needed); `core/uv.py` to TEX-WATER, then PERF-UV; `blender/bake.py` and `export.py` to
BLENDER-HYGIENE, then COL-DEGEN, then WATER-SURFACE (which also holds `core/generate.py` terrain and `core/bridges.py` alone); `tests/test_csharp_parity.py` and the C# harness to TEST-HYGIENE, then
FORMAT-POLICY. Perf tasks keep every package byte-identical (D97). **Sample slot (D103):** output-changing PRs
(TEX-WATER, COL-DEGEN, WATER-SURFACE, WATER-BANK, COL-FLOAT, COL-FLOAT-2, REL-v0.5.0, and ROOF-NAMED/ENDS only if the fixture's roofs change) regenerate
`examples/synthetic_sample.mbmap` only while holding the single exclusive merge-time slot from the coordinator
(rebase, regenerate, green CI and gate, merge, release); rebasing alone does not serialise writers. Tasks that touch probes or collision (S4-COL-DEGEN, S4-WATER-SURFACE) attach the
Pittsburgh Python and C# runs (D47).

v0.5.0 closeout (D133): `core/water.py`, the water stage of `core/generate.py` and `core/package.py` (`_MB_ID`)
belong to S4-COL-FLOAT-2 until #77 merges. S4-MYPY only triages (read-only) until then, then holds its files
alone. REL-v0.5.0 (#75) rebases, rebuilds every package and drops its `design/` hunk (D125) after S4-MYPY merges; it
shares `docs/PACKAGE_FORMAT.md` and the sample slot with COL-FLOAT-2, so the two never run at the same time.
Test budget for these tasks: D134.

## Sprint 5 (style)

Direction, budgets and ACs are in [S5-STYLE.md](S5-STYLE.md) (user request; D136–D145, D153, D156, D157). Every row passes the
G0 flight-data gate: `.mbcol` and `.mbhf` byte-identical; `manifest.georeference`, `manifest.passage_probes`,
`report.passage_probes_blocked` and `report.passage_probes_dropped` exactly equal. No S5 task has a geometry
exception (D145). The single start gate is #75 merged into main (D136). S5 shares files with #77, S4-MYPY and
the #75 sample slot, so those tasks never edit the shared files at the same time (overlap table in the spec).

| id | sprint | owner | dependencies | conflict domain (hard; soft) | status | PR |
|---|---|---|---|---|---|---|
| [S5-PERF-GATE](S5-PERF-GATE.md) | S5 (D153, D156) | dev | S4-F8 (shares `generate.py`/`collision.py` if S4-F8 is case B) and S5-STYLE-BASE (D156) | `tools/perf/work_count.py`, `core/perf_counters.py` (new), one-line counter increments in the listed hot functions (`osm`, `generate`, `water`, `overlap`, `collision`, `package`, `blender/scene_build`), `tests/test_work_count.py`; byte-identical output | blocked | |
| [S5-PERF-WATER](S5-PERF-WATER.md) | S5 (D152, D156) | dev | S5-STYLE-WATER (shared water stage); S5-PERF-GATE (gate and counters) | `core/overlap.py`, `core/shore.py` (mask callbacks), `core/water.py` (mask helpers), water-stage mask construction in `core/generate.py`, `tests/test_overlap.py`, `tests/test_shore_ramps.py`; byte-identical output | blocked | |
| [S5-STYLE-BASE](S5-STYLE.md#s5-style-base-baselines-metrics-g0-checker-and-acceptance-harness) | S5 | dev | #75 merged (done); runs in parallel with S4-F8 (D156; disjoint while S4-F8 is case A) | `tools/style_check.py`, `tests/test_style_check.py` (new), `tools/demo/` (style cameras, render recipe, frame-time proxy, `presets/bellevue-factoria.json` + frozen caches, D157) | in progress (D156) | |
| [S5-F3](S5-F3.md) | S5 (D161, correctness) | dev | step 1: none (read-only, parallel); class D fix: S5-PERF-GATE and a coordinator permission record | step 1: none; class D: `core/water.py`, `core/shore.py`, water stage of `core/generate.py`, tests, soft sample slot; class F: `tools/floating_audit.py`, `tests/test_floating_audit.py` only | ready (step 1) | |
| [S5-STYLE-PALETTE](S5-STYLE.md#s5-style-palette-style-option-default-stylized-palette-faceting-terrain-buildings-roads-and-trees) | S5 | dev | S5-STYLE-BASE, S5-PERF-GATE (D156; shared `generate.py`, `scene_build.py`) and S5-F3 (D161; collision correctness first) | `core/style.py` (new), `core/generate.py` (colour constants and colour choice only, trees included; no geometry), `core/glb.py` (normals/welding), `core/uv.py`/`core/textures.py` (mode switch), `tools/mbmap_cli.py` (flag), `blender/props.py`, `ui.py`, `scene_build.py` (option); soft: sample slot (D103, default becomes stylized, D141) | blocked | |
| [S5-STYLE-WATER](S5-STYLE.md#s5-style-water-cyan-water-terrain-side-shore-band-sandy-banks-colour-only) | S5 | dev | S5-STYLE-PALETTE (shared files); D143 (colour-only band); #75 merged (so #77 too) | `core/style.py` (water/band colours), water-stage and `bank:` colour code in `core/generate.py`, `core/water.py`/`core/shore.py` (colour only); soft: sample slot | blocked | |
| [S5-STYLE-REVIEW](S5-STYLE.md#s5-style-review-design-milestone-review-gono-go) | S5 | design | S5-STYLE-BASE, PALETTE, WATER, S5-PERF-WATER (D156) | `design/` only; explicit GO/NO-GO | blocked | |
| [S5-DECOR](S5-STYLE.md#s5-decor-visual-only-decoration--03-m-last-contingent) | S5 (last, D142) | dev | S5-STYLE-REVIEW GO; step 1a (frozen-reader fixture) and 1b (glTFast hide proof) pass, else stop and escalate | `core/decor.py` (new), `core/generate.py` (decor call), `core/glb.py` (primitive), `core/package.py` (exporter exemption), `docs/PACKAGE_FORMAT.md`, `docs/UNITY_CORE_HANDOFF.md`, `tests/test_decor.py`, format-policy fixtures | blocked | |
| S5-F1 | later | dev | explicit user approval | `core/generate.py` (`tree_mesh`), collision | deferred: tree shape change (changes `vegetation` collision; D145) | |
| S5-F2 | later | dev | data and collision-class review | new rock objects | deferred: rocks from OSM `natural=stone`/`bare_rock` | |

Sprint close order (D28): **RC PR (REL) → demo → design review (Sx-REVIEW) → coordinator retro
→ tag/Release**; see [SPRINT_CLOSE.md](SPRINT_CLOSE.md). REL tasks run alone.

## Knowledge gaps

From the Knowledge Lead coverage audit of main `873aa36` (2026-11-24); see the matrix in [docs/README.md](../../docs/README.md#coverage-matrix-four-goals).
Each row needs facts from its owner, integration by the Knowledge Lead, and a non-author review. Usage rows also need a QA rehearsal.

| id | sprint | owner (facts / integration) | dependencies | conflict domain (hard) | status | PR |
|---|---|---|---|---|---|---|
| DOC-ARCH | S5 | Developer + Product/Design / Knowledge Lead | — | `docs/architecture/README.md` | ready | |
| DOC-WATER-DESIGN | S5 | Product/Design (D112–D129) + Developer (code entries) / Knowledge Lead | DOC-ARCH (same page; serialise) | `docs/architecture/README.md` (water section) | ready | |
| DOC-DEV | S5 | Developer / Knowledge Lead | — | `docs/dev/README.md` (checks, CI) | ready | |
| DOC-DOD | S5 | Team Leader / Knowledge Lead | — | charter §4 single DoD; links from the Backlog and dev guide | done in the charter PR | #87 |
| DOC-TOOLS | S5 | Developer / Knowledge Lead | — | `docs/dev/` (new short tools section) | ready | |
| DOC-USER-STRUCT | next release | Delivery/Release / Knowledge Lead | release authorized | `docs/user/structures.md` (title/version) | blocked (release-owned, D28) | |
| DOC-PERF | S5 | Developer / Knowledge Lead | S5-PERF-GATE | `docs/dev/README.md` (performance section) | blocked | |

Details for each row:

* **DOC-ARCH:** refresh the architecture page from the audited head `44cde70` to current main.
  * Roofs, textures and UVs are delivered, not "planned".
  * Add the water stage to the pipeline diagram.
  * Update the code entries.
  * Trim the decision map to pointers.
  * AC: every stage in `generate.build_plan` and every `core/` module appears or is deliberately omitted; the
    owner verifies the facts; a non-author reviews.
* **DOC-WATER-DESIGN:** one authoritative explanation of the water design: the two grids, the carved bed, the
  levels, the bank colour, the shore ramps and cascades, and the masks. It covers data flow, code entries,
  invariants and the trade-offs: why ramps, not a skirt or a confined carve.
* **DOC-DEV:** update the developer guide's CI and local checks: the mypy step on the 3.12 leg, the format-policy and frozen-reader steps in the C# job,
  and the current interpreter versions. Also fix the stray control character in `docs/VALIDATION.md` line 117 (`\b` in place of the backtick before `build_plan`; release-owned file, so the fix goes in the next release-manager PR or with coordinator approval).
* **DOC-DOD:** done in #87: the team charter §4 is the single DoD; the other copies now only link to it.
* **DOC-TOOLS:** developer usage for `tools/floating_audit.py`, `tools/water_replay.py`, `tools/water_check.py` and
  `design/bench/`: what each checks, how to run it on frozen caches, and how to read the output. QA rehearses
  one run.
* **DOC-USER-STRUCT:** the title says v0.3.0, but the body cites v0.5.0.
* **DOC-PERF:** document the D153 gate's usage once the tool exists.

## Dependency order and parallel waves (max 3 devs)

1. Wave 1 (now): **S1-DEMOKIT**; after #11 merges: **REL-v0.1.0** (alone), then **S1-SEAMS** ∥
   **S2-ROOF** (early lane) ∥ DEMOKIT if still open
2. Wave 2: **S1-BRIDGE** ∥ **S1-TUNNEL** ∥ (ROOF if still open, else **S2-ELEV**)
3. Wave 3: **S1-PIERS** ∥ **S2-ELEV** → **REL-v0.2.0** → **S1-REVIEW** → retro → tag `v0.2.0` (**released**)
   (any S2 task already merged is simply part of main and ships with it)
4. Wave 4 (D48): **S2-REVIEW** (done first) → **S2-F1** ∥ **S2-F2** ∥ **S2-F3** → **REL-v0.3.0**
   (alone; also attaches the real-data `.mbmap`, S2-F4) → short S2 close check (design) → retro →
   tag `v0.3.0` (end of v2, **released**)
5. Wave 5 (sprint 3, D54): **S3-SKELETON** ∥ **S3-TEX-FORMAT** ∥ (**S3-ROOF-CASES** → **S3-TEX-ASSETS**)
   → **S3-ROOF-HIPPED** ∥ **S3-TEX-UV-CORE** ∥ **S3-PARITY** → **S3-ROOF-GABLED** ∥ **S3-TEX-BLENDER**
   → **S3-REVIEW** → **REL-v0.4.0** → close check → retro → tag `v0.4.0` (D63, **released**)
6. Wave 6 (sprint 4, D93): lanes **S4-ROOF-SPIKE** → **S4-ROOF-NAMED** → **S4-ROOF-ENDS** ∥ **S4-PERF-PKG**
   → **S4-BLENDER-HYGIENE** → **S4-COL-DEGEN** → **S4-WATER-SURFACE** (D112) ∥ **S4-TEX-WATER** → **S4-PERF-UV** → **S4-TEST-HYGIENE** →
   **S4-FORMAT-POLICY** (hard edge after TEST-HYGIENE) → **S4-EXT-READY** → **S4-REVIEW** → **S4-WATER-BANK** → **S4-COL-FLOAT**
      → **S4-COL-FLOAT-2** → **S4-MYPY** → **REL-v0.5.0** (rebase #75, rebuild) → close check → retro → tag 0.5.0 (D104, D133; publishing is a user decision)

`core/generate.py` appears in several hard domains, but in different functions/hunks
(roof section, building loop, bridge hook, tunnel hook). The pairs listed as parallel above
were checked for hunk overlap; anything else touching `generate.py` must be serialised.

## Definition of Done (every code task, D28)

The single canonical Definition of Done is in the [team charter §4](../team-charter.md#4-definition-of-done) (owned by the Team Leader). This section only keeps the anchor for older links.

