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

Evidence: `design/reviews/S4-REVIEW.md` §3, check 3, and the crop of the Pittsburgh bridge-under render.

## Change

* In `build_terrain`, an area whose id belongs to a body with an emitted water mesh (`WaterBody.built`) is
  ignored when choosing the cell colour. The cell takes the highest-priority **other** landcover, or the default
  when there is none. `coverage` still counts the cell for that area, so the coverage report stays unchanged.
* A body that falls back (`not built`, for example `fallback(no shore samples)` or `fallback(carve invariant)`)
  keeps today's painted cells, because it has no surface mesh. Its outcome row already names it.
* Pass the set of built-body ids from `build_plan` (`_water_stage` result) into `build_terrain`, for example as
  an optional `exclude_colour: frozenset[str]` argument. Do not add a new class or a second terrain pass.
* Riverbank bodies (`classified.riverbanks`) are not in `areas`, so they need no change. Say so in a test.

## Acceptance criteria

1. **No water-coloured terrain under a built body.** On the sample and Pittsburgh, through CLI and headless
   Blender: no terrain face carrying `LANDCOVER_COLORS["water"]` has its cell centre inside a body with an
   emitted water mesh. Every terrain face that still carries the water colour belongs to a fallback body
   listed in `report.json` `water_bodies`.
2. **Geometry unchanged.** `collision/map.mbcol` and `collision/terrain.mbhf` are byte-identical to main for the
   sample, Munich and Pittsburgh. Only the GLB vertex colours (and therefore `package_id`) change. Munich has no
   water area, so its package is **byte-identical**.
3. **Reports unchanged.** `water_bodies`, the landcover coverage, the probes and the degenerate list are equal
   to main.
4. **Evidence.** Before/after crops of the Pittsburgh bridge-under camera (demokit) show the bank in landcover or
   default colour, and the S4-TEX-WATER AC1 river-colour rule still holds on the overview (B > G inside the river
   region, which is now the water mesh).
5. **Sample** regenerated only under the D103 merge-time slot; the PR lists the byte change.

## Tests (≤ 5 s added, no wall-clock asserts)

* `tests/test_water.py`: a synthetic grid with one built body and one forced fallback body. Assert AC1 on the
  emitted terrain faces. Assert that a cell inside both a built water body and a park takes the park colour, and
  that a riverbank-only body changes nothing.
* The existing sample and Pittsburgh water checks (`tools/water_check.py`) still pass unchanged.

## Performance considerations

One set-membership test per area candidate per cell, so the cost is negligible. Whole Generate (D91) must stay
within +5 % on both presets and both paths. A same-host sanity pair is enough (D106) because the stage cost is
O(cells).

## Conflict domain

`core/generate.py` (`build_terrain`, the terrain call in `build_plan`), `tests/test_water.py`; soft: sample slot
(D103), `docs/demo/` crops. Disjoint from REL-v0.5.0 until REL starts. REL waits for this task.
