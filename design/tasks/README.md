# v2 task table

Maintained by the Design role. Approach, sprints and decisions: [../roadmap.md](../roadmap.md).
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
| [REL-v0.4.0](REL-v0.4.0.md) | S3 | release manager | S3-REVIEW and its blocker S3-Fn tasks | version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.4.0/`, `docs/releases/v0.4.0.md` | RC in review (S3-REVIEW GO #55; no S3-Fn blockers) | RC PR (pending) |
| S3-F1 | later | dev | — | `core/roofs.py` | later — analytic near-rectangle gables: planar failure has no named reason (4 Munich roofs) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F2 | later | dev | — | `tests/test_demo_bundle.py` | later — ResourceWarning leak in a test (finalizer escapes `-W error`) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F3 | later | dev | — | `tests/test_bridges.py` | later — shrink the 5.5 s 45° bridge-crossing test ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F4 | later | dev | — | `core/uv.py` | later — `assign_uvs` pure-Python cost (Pittsburgh `build_scene` stage +62 % textured, D85; +75 % untextured, D87) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F5 | later | dev | — | `core/package.py` | later — ZIP_STORED for PNGs in the package ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F6 | later | dev | — | `blender/` centre/bbox | later — bbox float32 precision (D74) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F7 | later | dev | — | `core/roofs.py`, `tests/roof_checks.py` | later — largest-triangle reference-plane warp ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F8 | later | dev | — | roof fixtures/tests | later — 9007 near-axis fixture sensitivity ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F9 | later | dev | — | `core/generate.py` (roof section) | later — loose legacy reservation bounds ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F10 | later | dev | — | `core/roofs.py`, `core/skeleton.py` | later — S4 roofs: chamfered/angled and mixed gable ends; pyramidal on concave footprints ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F11 | later | dev | — | `blender/export.py` | later — "MB Default" material digest suffix ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |
| S3-F12 | later | dev | — | `core/collision.py`, `blender/bake.py` | later — `.mbcol` degenerate-triangle warnings (pre-existing) ([S3-REVIEW §4](../reviews/S3-REVIEW.md#4-gaps-and-s3-fn-tasks)) | |

Sample and harness ownership (D64): only S3-TEX-UV-CORE changes `examples/synthetic_sample.mbmap`
and the default schema version; roof tasks keep the sample byte-identical and add their synthetic cases as
scratch OSM in `tests/blender/checks_roofs.py`; v0.3.0 comparisons use frozen inputs (the committed Munich roof
snapshot, the unchanged sample input, a recorded acquisition SHA-256).

Parallel safety: the roof track owns `core/roofs.py` and the building roof section of `generate.py` and the texture track never edits it or
`generate.py` (D59); `core/glb.py` is only in S3-TEX-FORMAT; `blender/bake.py` only in
S3-TEX-BLENDER (and S3-PARITY's optional fix, serialised). Every S3 task touching probes
(S3-PARITY) runs the Pittsburgh check in Python and C# in its PR (D47).

Sprint close order (D28): **RC PR (REL) → demo → design review (Sx-REVIEW) → coordinator retro
→ tag/Release**; see [SPRINT_CLOSE.md](SPRINT_CLOSE.md). REL tasks run alone.

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
   → **S3-REVIEW** → **REL-v0.4.0** → close check → retro → tag `v0.4.0` (D63)

`core/generate.py` appears in several hard domains, but in different functions/hunks
(roof section, building loop, bridge hook, tunnel hook). The pairs listed as parallel above
were checked for hunk overlap; anything else touching `generate.py` must be serialised.

## Definition of Done (every code task, D28)

Each task doc keeps its own acceptance criteria and performance considerations; a task is done
only when all of the following hold:

1. **Acceptance criteria tested:** every criterion maps to an automated test or a recorded run
   linked in the PR.
2. **CI green on the final head** (Python 3.11 + 3.12 unit tests, CLI build + validate of the
   synthetic fixture `VALID`, C# reader on the committed sample). Local evidence may support a
   review, never a merge (D38).
3. **No wall-clock or p95 gates in the PR suite**; performance is measured and quoted in the
   PR, not asserted in CI.
4. **New tests ≤ 5 s each** (no Blender, no network in PR CI).
5. **PR body** contains: CI time, a **behavior-change table** (before / after / why, including
   the sample and report changes) and a **"User-visible changes"** section (used by the
   release manager for CHANGELOG and `docs/user/`; "none" if none).
6. **Reviewer `VERDICT: APPROVED` comment on the exact head** (gpt-6.2-sol, D5, D33).
7. **Merge only through the coordinator's gate** (D34, D47): approval on the exact head and
   green CI, then the coordinator authorizes. Applies to every PR, design and docs-only
   included. Squash-merge, delete branch (D6).
8. **The PR that merges a task updates that task's row** in this table (status and PR).
9. **Probes / work accounting:** a task that touches passage probes or query work accounting
   runs the real Pittsburgh package (D26 preset) through the Python validator **and** the C#
   reader in the PR and attaches both results (D47).
10. **Complex geometry tasks write their acceptance cases first:** real-data excerpts (OSM
    ids from the demo area) plus counterexamples, committed as tests before the
    implementation.

Also expected where relevant:

* `examples/synthetic_sample.mbmap` regenerated with the command in `examples/README.md` if the
  output changed (D20); `tests/test_examples.py` green.
* Headless Blender 4.2.23 run (`tests/blender/run_integration.py`) `OK: 0 failure(s)` when the
  task touches generation or Blender code; result appended to `docs/VALIDATION.md`.
* PACKAGE_FORMAT.md, README Limits, UNITY_CORE_HANDOFF.md and VALIDATION.md updated for the
  behaviour the task changes.
* No release, demo render, CHANGELOG or version bump in feature PRs (release manager, D28).
