# S5-PERF-WATER: cheaper water and shore masks, byte-identical output

Owner: dev · sprint S5 · runs **after S5-PERF-GATE** (D152, D154) · performance task: byte identity applies (D97)

## Problem (REL-v0.5.0 close check, D151)

On Pittsburgh (textured), Blender Generate does **+13.0 %** more Python primitive calls than v0.4.0:
34.12 M → 38.54 M. All of it is in the water stage:

* #72 water surfaces ≈ +7.4 %;
* #77 shore ramps and masks ≈ +5.2 %, almost entirely `core/overlap.py` (`_edges`, `_in_box`, `_edge_in_box`) and
  `core/shore.py`.

`osm.point_in_ring` calls rose from 58.9 k to 80.3 k. Per-revision counts are in
[../reviews/data/REL-v0.5.0-close-profile.json](../reviews/data/REL-v0.5.0-close-profile.json).

The likely cause is candidate filtering: every emitted ramp triangle is tested edge by edge against every mask
polygon whose padded bbox it meets.

## Change

* Index the protected masks (footprints, road ribbons, bridge abutments) and the wet body pieces once per water
  stage, per edge or per cell, so each triangle tests only nearby edges.
* Add exact early rejections before the exact area test: bbox-disjoint, and triangle fully on one side of an edge.
  They may only skip work the exact test would answer "no" to.
* Do not loosen, shrink or sample any predicate. The S4-COL-FLOAT-2 AC2 and AC3 predicates stay the decision.
* Optionally, cache `point_in_ring` per (body, cell) inside `_inside_pieces`.

## Acceptance criteria

The gate is **D153 (S5-PERF-GATE, merged before this task)**. The base is main at this PR's merge-base, measured
with the same checker. The historical 6.5 % and 3.8 % time shares are context only, not a gate.

1. **Byte identity (D97).** The sample, Munich and Pittsburgh are whole-archive byte-identical to the base, on both
   the CLI and Blender, under the pinned settings. Validator verdicts and messages are unchanged.
2. **D153 gate:** F1–F5 pass on both presets and all three series.
3. **Absolute work target, deterministic.** On Pittsburgh, for the Blender Generate and CLI series:
   * the `_water_stage` stage total (counters and calls, nested `shore_ramps` included) is **≤ 60 %** of the base
     value;
   * `overlap_edge_tests` and `ring_edge_tests` inside `_water_stage` are each **≤ 50 %** of the base;
   * no other stage grows by more than 1 %, so padding or moving work elsewhere cannot satisfy this AC.

   The PR posts the base and head work vectors.
4. **Predicate equivalence.** On a seeded corpus of ≥ 10 000 triangle–mask pairs (boundary contact, slivers and
   holes over-represented), the indexed path and the existing exact path give the same answer for every pair. The
   test runs in ≤ 5 s.

## Tests

* The AC4 equivalence test, in `tests/test_overlap.py` (new) or `tests/test_shore_ramps.py`.
* The existing shore, water and replay tests pass unchanged.
* Do not duplicate S4-COL-FLOAT-2 cases.

## Conflict domain

`core/overlap.py`, `core/shore.py` (mask callbacks only), `core/water.py` (`_inside_pieces`, the mask helpers), the
water-stage mask construction in `core/generate.py`, `tests/test_overlap.py`, `tests/test_shore_ramps.py`.

No sample change (byte identity). It does not run at the same time as S4-F8 (B), S5-PERF-GATE (counter lines in the
same files) or S5-STYLE-WATER.

Scope note: the S5-STYLE runtime and frame-time budgets (D139) are a separate browser measurement. They are not
generation work counts and are not part of this task.
