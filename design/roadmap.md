# map-builder v2 roadmap

Owner: Design role. Status of every task is in [tasks/README.md](tasks/README.md); this file
holds the approach, the sprints/releases and the decision record.

## Goal

v2: **a drone can fly under bridges, through tunnels and beneath elevated building parts** of a
real ~1 × 1 km map, and the simulator Core can verify that from the package alone
(`passage_probes` checked against `.mbcol`). Roof shapes get richer on the way. The package
format stays 2.x (format 2.0 already carries the `bridge`/`tunnel`/`structure` classes, the
tube rule and passage probes).

## Approach

1. **Generate structures, not exceptions.** Bridge decks, tunnel tubes and passages become real
   collision objects of the kinds the format already defines:
   * bridge deck (and piers) → class `bridge`, kind *solid* (closed, positive volume);
   * tunnel → class `tunnel`, kind *tube* (inward, open at its portals);
   * tunnel portal headwalls → class `structure`, kind *solid*;
   * elevated parts and building passages → class `building` (solids that leave free space).
2. **Every generated passage carries a probe.** The generator emits a `passage_probes[]` entry
   for each passage it creates and checks it against the plan's own collision before emitting
   (plan-time check, shared helper). A probe that the generator knows is blocked is not
   emitted; it is reported in `report.json` instead (D21). The validator re-checks after
   export, so Blender edits that block a passage surface as warnings.
3. **Clearance comes from corrected ground.** Bridge clearance and tunnel cover are measured
   against the DSM-corrected terrain from PR #11 (D15).
4. **One seam, then parallel features (D18).** `core/generate.py` (≈1.8 k lines) and
   `core/osm.py` are hot spots. S1-SEAMS adds a thin seam: classification routes
   bridge/tunnel/passage features into their own lists, `build_plan` calls one stage function
   per structure kind, and a shared sweep/probe helper lives in its own module. Feature
   tasks then live mostly in their own modules (`core/bridges.py`, `core/tunnels.py`,
   `core/passages.py`, `core/roofs.py`) and touch `generate.py` only at their hook.
5. **No format bump unless semantics change (D12, D19).** Emitting classes and probes the
   format already defines is not a semantic change. New `report.json` keys are additive and
   documented in PACKAGE_FORMAT.md; they do not bump `schema_version`.
6. **Keep it simple (SOLID without over-engineering).** Plain functions per structure kind
   with one shared helper module; no plugin registry, no class hierarchy for "structures".
7. **Agile, but cheap demos (D17, D28).** Two sprints, each ending in one user-checkable GitHub
   pre-release. The demo is one reusable command (S1-DEMOKIT) built once. A sprint closes with
   an RC PR by the release manager (CHANGELOG, user docs, flows, demo, notes), then the Design
   milestone review + test audit, the coordinator retro and the tag. No release per task.

## Sprints and releases

| Release | When | Content the user can try | Assets |
|---|---|---|---|
| `v0.1.0` (REL-v0.1.0) | after #11 merges | first full release: v1 + format 2.0 + DSM correction + release workflow (D29) | zip, sample `.mbmap` + `.glb`, renders, viewer, CHANGELOG, user docs, notes with "How to try it" |
| `v0.2.0` | end of **S1** (REL-v0.2.0 + S1-REVIEW) | **fly under bridges and through tunnels**: decks, piers, tunnel tubes, portals, probes | zip, real-data demo `.mbmap` + `.glb`, panel screenshot, before/after renders, three.js viewer, release notes with "How to try it" |
| `v0.3.0` | end of **S2** (REL-v0.3.0 + S2-REVIEW, end of v2) | elevated parts / building passages, roof shapes, full real-data v2 demo | same as v0.2.0 + `docs/DEMO.md` with performance numbers |

| Sprint | Tasks | Exit criteria |
|---|---|---|
| S1 | RELEASE-WF (done, #13), REL-v0.1.0, DEMOKIT, SEAMS, BRIDGE, TUNNEL, PIERS, REL-v0.2.0, S1-REVIEW | fixture and demo-area bridges/tunnels generated, probes PASS (Python + C#), validator VALID, headless Blender PASS, review written, `v0.2.0` published |
| S2 | ELEV, ROOF (may start in S1), REL-v0.3.0, S2-REVIEW | elevated/passage probes PASS; new roof shapes closed and bound; real-data build ≤ 120 s; end-of-v2 review go/no-go; `v0.3.0` published |

```mermaid
flowchart LR
  PR11[PR 11 DSM] --> V010[REL-v0.1.0]
  RWF[S1-RELEASE-WF done] --> V010
  PR11 --> SEAMS[S1-SEAMS]
  PR11 --> ROOF[S2-ROOF]
  SEAMS --> BRIDGE[S1-BRIDGE]
  SEAMS --> TUNNEL[S1-TUNNEL]
  SEAMS --> ELEV[S2-ELEV]
  BRIDGE --> PIERS[S1-PIERS]
  DEMO[S1-DEMOKIT] --> R1[REL-v0.2.0]
  V010 --> R1
  PIERS --> R1
  TUNNEL --> R1
  R1 --> SR1[S1-REVIEW] --> T1[retro + tag v0.2.0]
  T1 --> R2[REL-v0.3.0]
  ELEV --> R2
  ROOF --> R2
  R2 --> SR2[S2-REVIEW] --> T2[retro + tag v0.3.0]
```

### Suggested waves (max 3 devs)

| Wave | Tasks in parallel | Why disjoint |
|---|---|---|
| 1 | S1-DEMOKIT (now); after #11: REL-v0.1.0 alone, then S1-SEAMS, S2-ROOF | DEMOKIT adds new files only (`tools/demo/`); ROOF touches only the roof section of `build_building` (+ `core/roofs.py`), SEAMS routing, hooks and new modules |
| 2 | S1-BRIDGE, S1-TUNNEL, (S2-ROOF or S2-ELEV) | each lives in its own module and its own `build_plan` hook |
| 3 | S1-PIERS, S2-ELEV → REL-v0.2.0 → S1-REVIEW → retro → tag | PIERS only extends `core/bridges.py`; REL runs alone |
| 4 | remaining S2 → REL-v0.3.0 → S2-REVIEW → retro → tag | REL runs alone |

**Soft conflicts** (shared but mechanically resolvable, D20): `examples/synthetic_sample.mbmap`
(regenerate after rebase), `tests/fixtures/synthetic_area.osm` (append-only), the
"Recorded results" table in `docs/VALIDATION.md` (append-only) and the Limits section of
`README.md` / the unsupported list in `docs/PACKAGE_FORMAT.md` (each task edits only its own
bullet). The coordinator merges one PR at a time; the next PR rebases and regenerates the
sample.

## Cross-cutting performance targets

| Item | Target |
|---|---|
| PR CI wall time | ≤ 10 min (today ≈ 40 s); each task may add ≤ 15 s of unit-test time; release workflow runs only on tags |
| Synthetic fixture build (CLI) | ≤ +20 % wall time vs. the pre-task baseline, measured and quoted in the PR |
| Real 1 × 1 km build (excluding download) | ≤ 120 s on the dev machine, CPython 3.12 |
| Scene budget | unchanged (`MAX_SCENE_VERTICES` 3 M, `MAX_SCENE_TRIANGLES` 4 M); new objects reserve before allocating |
| Passage probes | ≤ 256 per package (format); plan-time check uses `query.capsule_hits` with object-AABB pruning and stays inside the validator's 2 M visit budget for the whole package |
| Determinism | same inputs + `--created-utc` → byte-identical package (existing guarantee) |
| Headless Blender | manual, ≤ 5 min per run; not in CI (D9) |
| Sprint demo | one command, ≤ 30 min unattended CPU rendering per sprint review |

## Decision record

Who: **U** = user, **C** = coordinator, **De** = design, **Dev** = earlier dev process
(confirmed by the coordinator).

| # | Decision | Who | Status |
|---|---|---|---|
| D1 | Standalone Blender 4.2 LTS add-on + headless CLI; outputs GLB + versioned `.mbmap` | U | final |
| D2 | No Google Maps / 3D Tiles extraction; only OSM (ODbL) + Copernicus GLO-30 | U | final |
| D3 | v1 area ≈ 1 × 1 km (50–2000 m side), no streaming/LOD | U | final |
| D4 | Collision authority is the simulator Core (250 Hz) via neutral `.mbcol`; Unity colliders not authoritative | U | final |
| D5 | QA/review uses a different model family from Dev (gpt-6.2-sol) | U | final |
| D6 | One branch + one PR per feature; squash-merge after review + CI; delete branch | U | final |
| D7 | Terrain/OSM ingestion split into its own PR (#2) | Dev | done |
| D8 | GLB/package/collision (#4) and validation (#6) separate PRs | Dev | done |
| D9 | Portable Blender 4.2.23 at `C:\tools\` for headless integration tests (manual, not CI) | Dev | final |
| D10 | Licence provisionally GPL-3.0-or-later | Dev | provisional (see D13) |
| D11 | v1 real-data demo: SF FiDi 800 × 800 m | U | done |
| D12 | v2 = bridges, tunnels, elevated parts, roof shapes, DSM correction, one PR each; bump package format if semantics change | U | final |
| D13 | Licence confirmation deferred by the user | U | open (user) |
| D14 | Package format 2.0 PR (#10) before bridges | C | done |
| D15 | DSM correction before bridges; clearance measured from corrected ground | C | final |
| D16 | PR #11 finished under the old process; the new team process starts from bridges | C | final |
| D17 | Agile delivery with few releases (user: "按照敏捷流程开发…最好是有一个release" and "注意不要太频繁，以免影响进度"): two sprints, S1 = bridges + tunnels → `v0.2.0`, S2 = elevated parts/passages + roofs + real-data demo → `v0.3.0`; no release per task; one reusable demo script built in S1; sprint close kept small (see D28); release workflow tag-triggered only | U + C | final (user may change) |
| D18 | Add one seam PR (S1-SEAMS) before the structure features so bridges, tunnels and passages can be built in parallel in their own modules | De | proposed |
| D19 | Emitting `bridge`/`tunnel`/`structure` and probes is not a format change; stay on 2.0.0; new `report.json` keys are additive and documented, no bump. Generator/extension version follows the sprint releases (0.2.0, 0.3.0), bumped only in sprint-review tasks | De | proposed |
| D20 | The binary sample `examples/synthetic_sample.mbmap` is a regenerated artefact: on rebase conflicts, regenerate with the documented command, never hand-merge. Feature tests use their own in-code synthetic terrain/OSM; the shared fixture is append-only | De | proposed |
| D21 | The generator never emits a probe it knows is blocked; it lists it in `report.json` `passage_probes_blocked` with the blocking `mb_id` instead | De | proposed |
| D22 | Bridge deck profile: linear between at-grade end heights, raised where needed to `layer` × 5.0 m clearance over corrected ground, ramps ≤ 8 % grade; deck 1.0 m thick (inferred) | De | proposed |
| D23 | Tunnels cut the terrain mesh only where it intersects the tube interior (no trench); gaps between the cut and the tube are closed by portal headwalls/skirts (`structure`), verified by a ray "leak" test, never left open | De | proposed |
| D24 | Building passages (`tunnel=building_passage`, `covered=yes` highways through a building) split the building into a lower part (footprint minus corridor) and an elevated upper part, reusing the existing elevated-volume code; ids use the `#k` part suffix | De | proposed |
| D25 | Scope: highway bridges/tunnels only in v2. Railway, waterway (`culvert`) and `building=bridge`/`man_made=bridge` outlines stay in `unsupported_features` | C (proposed by De) | final — decided by coordinator, user may change |
| D26 | v2 sprint demo area: Pittsburgh, Fort Pitt Bridge + Fort Pitt Tunnel (≈ 40.437 N, 80.016 W, 1200 × 1000 m) | C (proposed by De) | final — decided by coordinator, user may change |
| D27 | S1-RELEASE-WF (#13) AC1 "panel appears" is satisfied by a headless panel-registration assert after install-file + enable (`MB_PT_main` in `VIEW_3D`/`UI`, category *Map Builder*); the visual sidebar screenshot comes from S1-DEMOKIT `--panel`, checked at REL-v0.2.0 | C | final |
| D28 | Team per agile-ai-team (user: "访问 lingshf/agents repo，安装最新skill。然后按照agile-ai-team 规划"): a release manager owns `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/<ver>/`, `docs/releases/<ver>.md` and proposes tag commits; Design owns `design/`. Sprint close order: RC PR → demo → Design milestone review + test audit → coordinator retro → tag/Release. Definition of Done in `design/tasks/README.md` | U + C | final (user may change) |
| D29 | `v0.1.0` is a full first release of everything on main (v1, format 2.0, #11 DSM, #13 release workflow) with CHANGELOG, user docs, flows, demo and notes; supersedes the "tag + zip only" baseline in D17 | C | final (user may change) |

## Decisions that need the user

1. **D13 licence.** Still deferred; nothing in v2 depends on it. Releases carry the provisional
   GPL-3.0-or-later notice.

D25 (scope) and D26 (demo area) were decided by the coordinator on the user's behalf; the user
may change them at any time.

## Non-goals for v2

Streaming/LOD, textures/UVs, straight-skeleton roofs on arbitrary footprints, cable/suspension
bridge superstructure, multi-level interchanges beyond `layer` clearance, interior rooms.
