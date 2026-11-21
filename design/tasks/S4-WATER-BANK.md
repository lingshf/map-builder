# S4-WATER-BANK: no water-coloured terrain around a built water surface

Owner: dev · sprint S4 · **v0.5.0 blocker** (S4-F1, D123) · after S4-WATER-SURFACE (#72)

## Problem (found in S4-REVIEW)

S4-WATER-SURFACE gives every built water body a flat `water:<id>` mesh, clipped to the OSM shoreline, on a
carved bed. `build_terrain` (`core/generate.py:768–800`) still paints each terrain cell with
`LANDCOVER_COLORS["water"]` when the cell centre is inside a water polygon (`a.tags["_class"] == "water"`).
Cells that straddle the shoreline are carved to the bed, so the parts that lie outside the clipped water mesh show
as blue terrain triangles on the bank.

On the Pittsburgh bridge-under render this reads as a blue 10 m saw-tooth above the flat water. It is a smaller
form of the "mat" the user complained about. The #70 spec did not cover the terrain colour.

Evidence: `design/reviews/S4-REVIEW.md` §1.3 and the crop `design/reviews/img/S4-F1-pittsburgh-bank.png`.

## Change

* **Built bodies.** Use the final model returned by `_water_stage`: the built bodies are exactly
  `WaterModel.active()` (the `core.water.Body` objects whose `Body.built` is true, i.e. outcome `built(...)`).
  Do not rebuild that set from `report.json` or from the area list.
* **Precedence (coordinator ruling): built beats fallback.** When a cell centre lies inside the polygon
  (`Body.polygon`) of **any** body in `WaterModel.active()`, every water-class area is ignored when choosing that
  cell's colour, even when a fallback body or another water area also covers the cell. The built water mesh covers
  that area. The cell takes the highest-priority **non-water** landcover, or the default when there is none.
* **Fallback-only cells.** A cell inside water-class areas of which none lies inside an active body keeps today's
  water colour, because it has no surface mesh. Its outcome row (for example `fallback(no shore samples)` or
  `fallback(carve invariant)`) already names it.
* **Coverage.** `coverage` still counts the cell for every area that contains it, so the landcover coverage
  report stays unchanged.
* **Plumbing.** `build_plan` passes the active bodies' polygons (or ids plus polygons) from the `_water_stage`
  result into `build_terrain` as one optional argument, for example `built_water: Sequence[Polygon] = ()`, with a
  bbox prefilter (the existing `_Buckets`). Do not add a new class or a second terrain pass.
* **Riverbank bodies.** Riverbank bodies (`kind == "riverbank"`) are not in `areas`, so they never paint a cell
  on their own. When built, they still take precedence over an overlapping fallback area by the rule above.

## Acceptance criteria

Fixed inputs for AC1–AC3: the sample fixture, and the frozen RC #56 caches for Munich and Pittsburgh (identified by
their acquisition SHA-256). Settings follow `docs/DEMO.md` (seed 1, DSM on), offline, with
`created_utc = "2026-11-20T00:00:00Z"` (the value used in `design/bench/cli_time.py`). The base is main at the
commit the PR branches from (d38d4e8 or later), built with the same inputs.

1. **No water-coloured terrain under a built body.** On the sample, Munich and Pittsburgh, through both the CLI
   and headless Blender:
   * no terrain face carrying `LANDCOVER_COLORS["water"]` has its cell centre inside the polygon of a body in
     `WaterModel.active()`;
   * every terrain face that still carries the water colour lies only inside fallback bodies, each listed in
     `report.json` `water_bodies` with a `fallback(...)` outcome.
2. **Byte checks, CLI and Blender paths, each against the same path on the base:**
   * `collision/map.mbcol` and `collision/terrain.mbhf` are **byte-identical** members for the sample, Munich and
     Pittsburgh, on the CLI path and on the Blender path;
   * the **whole Munich `.mbmap` archive** is byte-identical on the CLI path and on the Blender path (Munich has
     no water body);
   * for the sample and Pittsburgh only the visual members may change: the GLB vertex colours, and therefore the
     manifest member hashes and `package_id`. The PR lists every changed member per package and path.
3. **Reports unchanged.** `water_bodies`, the landcover coverage, the probes and passages, and the degenerate
   list are equal to the base on both paths.
4. **Evidence (PR evidence, not committed).** Before/after crops of the Pittsburgh bridge-under camera (demokit)
   are attached to the PR. They show the bank in landcover or default colour, and the S4-TEX-WATER AC1 river-colour
   rule still holds on the overview (B > G inside the river region, which is now the water mesh). `docs/demo/` is
   REL-only (REL-v0.5.0 regenerates the renders); do not commit crops there.
5. **Sample** regenerated only under the D103 merge-time slot; the PR lists the byte change.
6. **Performance (D91, D106).** Normal D106 timing: 3 alternating rounds (base, head, base, head, …) per revision
   and preset, both presets, using `design/bench/cli_time.py` (CLI whole Generate, offline) and
   `design/bench/bl_time.py` (Blender Generate+Export, socket guard). Median of the per-round medians; each whole
   path stays within **+5 %** of the base. The PR links the raw runs and the aggregation. There is no
   single-pair exception.

## Tests (≤ 5 s added, no wall-clock asserts)

* `tests/test_water.py`, on a synthetic grid with:
  * one built body and one forced fallback body: assert AC1 on the emitted terrain faces;
  * **an overlap regression:** a fallback water area that overlaps a built body. Cells inside the built body's
    polygon do not get the water colour; cells covered only by the fallback area keep it. The coverage counts
    for both areas are unchanged from today;
  * a cell inside both a built body and a park takes the park colour;
  * a built riverbank body overlapping a fallback water area suppresses the water colour in the overlap.
* The existing sample and Pittsburgh water checks (`tools/water_check.py`) still pass unchanged.
* **Blender, persisted:** extend `tests/blender/checks_water.py` with AC1 on the sample through the Blender
  path. `tests/blender/run_integration.py` discovers `checks_*.py` modules automatically, so the runner does not
  change.
* **Blender, manual evidence:** the AC1–AC3 checks on Munich and Pittsburgh need the frozen caches, so they are
  run by hand and their output (commands, member hashes, counts) is posted in the PR. They are not persisted.

## Performance considerations

One point-in-polygon test per active body candidate per cell, behind the bbox prefilter, plus today's per-area
test. The cost is O(cells × candidates) and small next to the water stage. It is measured per AC6.

## Conflict domain

`core/generate.py` (`build_terrain`, the terrain call in `build_plan`), `tests/test_water.py`,
`tests/blender/checks_water.py`; soft: sample slot (D103). No `docs/demo/` changes (crops are PR evidence).
Disjoint from REL-v0.5.0 until REL starts. REL waits for this task.
