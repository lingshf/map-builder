# v2 task table

Maintained by the Design role. Approach, sprints and decisions: [../roadmap.md](../roadmap.md).
Status values: `blocked` (dependency open), `ready`, `in progress`, `review`, `done`.

Every task doc lists its acceptance criteria, performance considerations, expected tests and
its **conflict domain**. Only run tasks in parallel whose hard conflict domains are disjoint.
*Soft* domains (`examples/synthetic_sample.mbmap`, append-only rows in
`tests/fixtures/synthetic_area.osm`, the "Recorded results" table of `docs/VALIDATION.md`,
each task's own bullet in README Limits / PACKAGE_FORMAT unsupported list) are resolved by
rebasing and regenerating (D20), so they do not block parallel work; the coordinator merges one
PR at a time. Releases happen only in the sprint-review tasks (D17).

| id | sprint | dependencies | conflict domain (hard) | status | PR |
|---|---|---|---|---|---|
| [DSM](https://github.com/lingshf/map-builder/pull/11) | pre | — | `core/dsm.py`, `core/osm.py`, `core/generate.py`, `core/pipeline.py`, Blender props/ui/sources, CLI | in progress (old process) | #11 |
| [S1-RELEASE-WF](S1-RELEASE-WF.md) | S1 | — (v0.1.0 tag after #11) | `.github/workflows/release.yml` (new), `docs/releases/` (new) | ready | |
| [S1-DEMOKIT](S1-DEMOKIT.md) | S1 | — | `tools/demo/` (new), `tests/test_demo_bundle.py` | ready | |
| [S1-SEAMS](S1-SEAMS.md) | S1 | #11 | `core/osm.py` (`_unsupported_reason`, `Classified`, routing), `core/generate.py` (`ScenePlan`, `build_plan` stage hooks), new `core/structures.py`, stub `core/bridges.py` / `core/tunnels.py` / `core/passages.py`, `blender/scene_build.py`, `tests/blender/*` (split into modules) | blocked | |
| [S1-BRIDGE](S1-BRIDGE.md) | S1 | S1-SEAMS | `core/bridges.py`, `core/generate.py` (bridge hook only), `tests/test_bridges.py`, `tests/blender/checks_bridges.py` | blocked | |
| [S1-TUNNEL](S1-TUNNEL.md) | S1 | S1-SEAMS | `core/tunnels.py`, `core/generate.py` (tunnel hook only), `tests/test_tunnels.py`, `tests/blender/checks_tunnels.py` | blocked | |
| [S1-PIERS](S1-PIERS.md) | S1 | S1-BRIDGE | `core/bridges.py`, `tests/test_bridges.py` | blocked | |
| [sprint-1-review](sprint-1-review.md) | S1 | RELEASE-WF, DEMOKIT, SEAMS, BRIDGE, PIERS, TUNNEL, D26 (user) | version files, `docs/releases/v0.2.0.md`, `design/reviews/` | blocked | |
| [S2-ROOF](S2-ROOF.md) | S2 (may start in S1) | #11 | `core/generate.py` (roof section of `build_building` only), new `core/roofs.py`, `tests/test_roofs.py` | blocked | |
| [S2-ELEV](S2-ELEV.md) | S2 | S1-SEAMS | `core/passages.py`, `core/generate.py` (building loop in `build_plan` only), `tests/test_passages.py`, `tests/blender/checks_passages.py` | blocked | |
| [sprint-2-review](sprint-2-review.md) | S2 | ELEV, ROOF, sprint-1-review | version files, `docs/releases/v0.3.0.md`, `docs/DEMO.md` (new), `design/reviews/` | blocked | |

Common sprint-review definition (demo + design review + test audit + release):
[SPRINT_REVIEW.md](SPRINT_REVIEW.md).

## Dependency order and parallel waves (max 3 devs)

1. Wave 1 (now): **S1-RELEASE-WF** ∥ **S1-DEMOKIT**; after #11 merges: v0.1.0 tag (in
   RELEASE-WF), then **S1-SEAMS** ∥ **S2-ROOF** (early lane)
2. Wave 2: **S1-BRIDGE** ∥ **S1-TUNNEL** ∥ (ROOF if still open, else **S2-ELEV**)
3. Wave 3: **S1-PIERS** ∥ **S2-ELEV** → **sprint-1-review** (v0.2.0; any S2 task already merged
   is simply part of main and ships with it)
4. Wave 4: remaining S2 work → **sprint-2-review** (v0.3.0, end of v2)

`core/generate.py` appears in several hard domains, but in different functions/hunks
(roof section, building loop, bridge hook, tunnel hook). The pairs listed as parallel above
were checked for hunk overlap; anything else touching `generate.py` must be serialised.

## Common definition of done (every code task)

* Unit tests: `py -3.12 -W error::ResourceWarning -m unittest discover -s tests -t .` green on
  3.11 and 3.12 (CI).
* CLI build + validate of the synthetic fixture is `VALID` (CI); new warnings explained in the PR.
* `examples/synthetic_sample.mbmap` regenerated with the command in `examples/README.md` if the
  output changed; `tests/test_examples.py` and the C# reader CI step green.
* Headless Blender 4.2.23 run (`tests/blender/run_integration.py`) `OK: 0 failure(s)` when the
  task touches generation or Blender code; result appended to `docs/VALIDATION.md`.
* Docs: PACKAGE_FORMAT.md (unsupported list, report keys), README Limits, UNITY_CORE_HANDOFF.md
  and VALIDATION.md matrix updated for the behaviour the task changes.
* PR quotes the fixture build time before/after and the unit-test time added.
* No release, demo render or version bump per task (D17).
* Review by gpt-6.2-sol (D5), summary comment on the PR, squash-merge, delete branch (D6).
