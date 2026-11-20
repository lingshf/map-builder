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
| [REL-v0.3.0](REL-v0.3.0.md) | S2 | release manager | ELEV, ROOF, v0.2.0 tagged (done) | version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.3.0/`, `docs/releases/v0.3.0.md`, `docs/DEMO.md` | blocked | |
| TEST-HYGIENE | S1 | dev | — | `tests/test_dsm_correction.py`, `tests/test_scene_generation.py`, `tests/test_package.py`, `tools/demo/presets/pittsburgh.json` | done | #23 |
| PERF-PROBE-INDEX | S1 | dev | — | `core/query.py`, `core/structures.py` | closed (D44/D45) | #25 |
| FIX-CS-PROBE-PARITY | S1 | dev | — | `examples/csharp/MbmapReader/`, `core/package.py` (`mb_id` regex), `tests/test_csharp_parity.py`, `.github/workflows/ci.yml` | done (D46) | #27 |
| [S1-F1](S1-F1.md) | S2 | dev | — | `core/bridges.py` (approach detection) | ready | |
| [S1-F2](S1-F2.md) | S2 | dev | — | `tests/test_terrain_sources.py` | ready | |
| [S2-REVIEW](S2-REVIEW.md) | S2 | design | REL-v0.3.0 RC merged | `design/` only | blocked | |

Sprint close order (D28): **RC PR (REL) → demo → design review (Sx-REVIEW) → coordinator retro
→ tag/Release**; see [SPRINT_CLOSE.md](SPRINT_CLOSE.md). REL tasks run alone.

## Dependency order and parallel waves (max 3 devs)

1. Wave 1 (now): **S1-DEMOKIT**; after #11 merges: **REL-v0.1.0** (alone), then **S1-SEAMS** ∥
   **S2-ROOF** (early lane) ∥ DEMOKIT if still open
2. Wave 2: **S1-BRIDGE** ∥ **S1-TUNNEL** ∥ (ROOF if still open, else **S2-ELEV**)
3. Wave 3: **S1-PIERS** ∥ **S2-ELEV** → **REL-v0.2.0** → **S1-REVIEW** → retro → tag `v0.2.0` (**released**)
   (any S2 task already merged is simply part of main and ships with it)
4. Wave 4: remaining S2 → **REL-v0.3.0** → **S2-REVIEW** → retro → tag `v0.3.0` (end of v2)

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
