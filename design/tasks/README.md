# v2 task table

Maintained by the Design role. Approach and decisions: [../roadmap.md](../roadmap.md).
Status values: `blocked` (dependency open), `ready`, `in progress`, `review`, `done`.

Every task doc lists its acceptance criteria, performance considerations, expected tests and
its **conflict domain**. Only run tasks in parallel whose hard conflict domains are disjoint.
*Soft* domains (`examples/synthetic_sample.mbmap`, append-only rows in
`tests/fixtures/synthetic_area.osm`, the "Recorded results" table of `docs/VALIDATION.md`,
each task's own bullet in README Limits / PACKAGE_FORMAT unsupported list) are resolved by
rebasing and regenerating (D19), so they do not block parallel work; the coordinator merges one
PR at a time.

| id | milestone | dependencies | conflict domain (hard) | status | PR |
|---|---|---|---|---|---|
| [M1-DSM](https://github.com/lingshf/map-builder/pull/11) | M1 | — | `core/dsm.py`, `core/osm.py`, `core/generate.py`, `core/pipeline.py`, Blender props/ui/sources, CLI | in progress (old process) | #11 |
| [M2-SEAMS](M2-SEAMS.md) | M2 | #11 | `core/osm.py` (`_unsupported_reason`, `Classified`, routing), `core/generate.py` (`ScenePlan`, `build_plan` stage hooks), new `core/structures.py`, stub `core/bridges.py` / `core/tunnels.py` / `core/passages.py`, `blender/scene_build.py`, `tests/blender/run_integration.py` (split into modules) | blocked | |
| [M4-ROOF](M4-ROOF.md) | M4 | #11 | `core/generate.py` (roof section of `build_building` only), new `core/roofs.py`, `tests/test_roofs.py` | blocked | |
| [M3-BRIDGE](M3-BRIDGE.md) | M3 | M2-SEAMS | new `core/bridges.py`, `core/generate.py` (bridge hook only), `tests/test_bridges.py`, `tests/blender/checks_bridges.py` | blocked | |
| [M3-TUNNEL](M3-TUNNEL.md) | M3 | M2-SEAMS | new `core/tunnels.py`, `core/generate.py` (tunnel hook only), `tests/test_tunnels.py`, `tests/blender/checks_tunnels.py` | blocked | |
| [M4-ELEV](M4-ELEV.md) | M4 | M2-SEAMS | new `core/passages.py`, `core/generate.py` (building loop in `build_plan` only), `tests/test_passages.py`, `tests/blender/checks_passages.py` | blocked | |
| [M3-PIERS](M3-PIERS.md) | M3 | M3-BRIDGE | `core/bridges.py`, `tests/test_bridges.py` | blocked | |
| [M3-R](M3-R.md) | M3 | M3-BRIDGE, M3-TUNNEL, M3-PIERS | `design/` only (findings become new tasks) | blocked | |
| [M4-R](M4-R.md) | M4 | M4-ELEV, M4-ROOF | `design/` only | blocked | |
| [M5-DEMO](M5-DEMO.md) | M5 | M3-R, M4-R, D25 (user) | `docs/DEMO.md` (new), `docs/VALIDATION.md`, `README.md`, `map_builder/__init__.py` + `blender_manifest.toml` (version 0.2.0); demo artefacts outside the repo | blocked | |
| [M5-R](M5-R.md) | M5 | M5-DEMO | `design/` only | blocked | |

## Dependency order and parallel waves

1. Wave 1 (after #11 merges): **M2-SEAMS** ∥ **M4-ROOF**
2. Wave 2: **M3-BRIDGE** ∥ **M3-TUNNEL** ∥ **M4-ELEV**
3. Wave 3: **M3-PIERS**; reviews **M3-R** (after PIERS) and **M4-R** (after ELEV + ROOF)
4. Wave 4: **M5-DEMO** → **M5-R**

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
* Review by gpt-6.2-sol (D5), summary comment on the PR, squash-merge, delete branch (D6).
