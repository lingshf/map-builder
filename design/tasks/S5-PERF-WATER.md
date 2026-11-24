# S5-PERF-WATER: cheaper water and shore masks, byte-identical output

Owner: dev · sprint S5, after S4-F8 (D152) · performance task: byte identity applies (D97)

## Problem (REL-v0.5.0 close check, D151)

On Pittsburgh (textured), Blender Generate does **+13.0 %** more deterministic work (Python primitive calls) than
v0.4.0: 34.12 M → 38.54 M. All of it is in the water stage:

* #72 water surfaces ≈ +7.4 %;
* #77 shore ramps and masks ≈ +5.2 %, almost entirely `core/overlap.py` (`_edges`, `_in_box`, `_edge_in_box`,
  about 200 k calls each) plus `core/shore.py`.

`generate._water_stage` takes **6.5 %** of Blender Generate in a single profiled run (shore ramps 2.8 %) and 3.7 %
of the CLI. `osm.point_in_ring` calls rose from 58.9 k to 80.3 k, from the water and shore masks
(`water._inside_pieces` and the wet-region tests). The analysis is in
[../reviews/REL-v0.5.0-close.md](../reviews/REL-v0.5.0-close.md).

The likely cause is candidate filtering. Each emitted ramp triangle is tested against every footprint, road
segment, abutment and body piece whose padded bbox it meets, edge by edge. There is no per-edge spatial index and
no early whole-polygon rejection.

## Change

* Index the protected masks (footprints, road ribbons, bridge abutments) and the wet body pieces once per water
  stage. The index stores per-edge or per-cell candidates, built on the existing `_Buckets` or a uniform grid, so
  each emitted triangle only checks edges near it.
* Add cheap exact rejections before the exact area test:
  * bbox-disjoint → no overlap;
  * triangle fully on one side of a ring edge → no overlap for that edge.

  These must be **exact**: they may only skip work that the exact test would answer "no".
* Do not loosen, shrink or sample any predicate. The exact positive-area test of S4-COL-FLOAT-2 AC2 and AC3 stays
  the decision.
* Optionally, cache `point_in_ring` results per (body, cell) where `_inside_pieces` asks repeatedly.

## Acceptance criteria

1. **Byte identity (D97).** The sample, Munich and Pittsburgh packages are whole-archive byte-identical to the base,
   on both the CLI and Blender, under the pinned settings. Validator verdicts and messages are unchanged.
2. **Work target, deterministic (D153).** On Pittsburgh textured, the water stage (cumulative under
   `generate._water_stage`) is **≤ 3.8 %** of Blender Generate. 3.8 % is its share after #72 and before #77. The
   PR reports call counts and the stage share for base and head. Blender Generate total calls are ≤ the base.
3. **Time sanity.** CPU time under D147/D153, posted for information. No series may regress beyond the D153
   sanity band.
4. **Predicate equivalence test.** On a randomised but seeded corpus, the indexed path returns the same answer as
   the existing exact path for every triangle–mask pair. The corpus has ≥ 10 000 pairs, with boundary contact,
   slivers and holes over-represented. The test runs in ≤ 5 s.

## Tests

* The AC4 equivalence test, in `tests/test_overlap.py` (new) or `tests/test_shore_ramps.py`.
* The existing shore, water and replay tests pass unchanged.
* Do not duplicate S4-COL-FLOAT-2 cases.

## Conflict domain

`core/overlap.py`, `core/shore.py` (mask callbacks only), `core/water.py` (`_inside_pieces`, the mask helpers), the
mask construction in the water stage of `core/generate.py`, `tests/test_overlap.py`. No sample change (byte
identity). It does not run at the same time as S4-F8 (B) or S5-STYLE-WATER, which share `generate.py` and `water.py`.
