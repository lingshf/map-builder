# S5-PERF-WATER: cheaper water and shore masks, byte-identical output

Owner: dev · sprint S5 · runs **after S5-STYLE-WATER** (D152, D156; both edit the water stage, and the style is user-visible) · performance task: byte identity applies (D97)

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
  stage, per edge or per cell, so each triangle reaches only nearby candidates.
* **Containment-safe filtering.** A prefilter, whether bbox, grid or edge index, may skip a triangle–mask pair only
  when the two are **provably disjoint**. A triangle that lies wholly inside a mask touches no mask edge, so an
  edge-only index would miss it. The filter must therefore also find containing masks, for example with a
  point-in-mask test of one triangle vertex against every mask whose bbox contains the triangle.
* Exact early rejections (bbox-disjoint, or triangle wholly on the outer side of a ring edge) may only skip work
  that the exact test would answer "no" to.
* **Caches are keyed by exact geometry.** Cache a containment or overlap answer only under a key that determines it
  exactly, such as the exact query point, or the exact triangle and mask identity. A `(body, cell)` cache is allowed
  only where the cell is proven entirely inside or entirely outside the body; the PR shows that proof, otherwise
  it does not cache.
* Do not loosen, shrink or sample any predicate. The S4-COL-FLOAT-2 AC2 and AC3 predicates stay the decision.

## Acceptance criteria

* **Gate:** D153 (S5-PERF-GATE, merged earlier). The order is D156, which supersedes D152 and D154.
* **Base:** main at this PR's merge-base with the pinned counter commit applied.
* D152's "≤ 3.8 % of Blender Generate" time share is **superseded by AC3** as the target. It stays as context.
  Time shares are not a gate.

1. **Byte identity (D97).** The sample, Munich and Pittsburgh are whole-archive byte-identical to the base, on both
   the CLI and Blender, with the pinned settings. Validator verdicts and messages are unchanged. Consequently every
   **output counter** is an invariant equal to the base: `tri_emitted[*]`, `bytes_written[*]`, `deflate_in_bytes`
   and `bpy_mesh_vertices`.
2. **D153 gate:** F1–F3 pass, and F4–F6 are answered, on both presets and all three series.
3. **Work targets per unit.** Each unit is measured inside `_water_stage` (with `shore_ramps` included) on
   Pittsburgh, for the Blender Generate and CLI series, head / base:

| Unit | Target |
|---|---|
| Inclusive primitive calls in `_water_stage` | ≤ 60 % |
| `overlap_edge_tests` | ≤ 50 % |
| `overlap_pairs` (pairs reaching the exact test) | ≤ 50 % |
| `ring_edge_tests` | ≤ 50 % |
| `clip_steps` | ≤ 100 % (must not grow; the clip output is fixed by AC1) |
| `candidate_pairs` | reported; must be ≥ `overlap_pairs` and ≤ the base's `overlap_pairs` |

   * **Index-build work counts inside `_water_stage`.** Its calls are inclusive. Any loop it adds at an uncounted
     site is listed under F6.
   * **No other stage** grows by more than 1 % in any counter or in calls.
   * The PR posts both work vectors in full.
4. **Filtered = unfiltered.** On every fixture (the sample, Munich and Pittsburgh water stages, plus a seeded
   synthetic corpus of ≥ 10 000 triangle–mask pairs), the filtered path and the exact path without filtering
   return the same decision for every pair. The synthetic corpus must include:
   * triangles wholly inside a mask;
   * masks wholly inside a triangle;
   * boundary contact only;
   * slivers;
   * holes.

   The test runs in ≤ 5 s on the synthetic corpus. The real-fixture comparison is PR evidence.

## Tests

* The AC4 equivalence test, in `tests/test_overlap.py` (new) or `tests/test_shore_ramps.py`, with the containment
  cases named.
* If any cache is kept, a test where a cached cell straddles the body edge must give the exact answer.
* The existing shore, water and replay tests pass unchanged. Do not duplicate S4-COL-FLOAT-2 cases.

## Conflict domain

`core/overlap.py`, `core/shore.py` (mask callbacks only), `core/water.py` (`_inside_pieces`, the mask helpers), the
water-stage mask construction in `core/generate.py`, `tests/test_overlap.py`, `tests/test_shore_ramps.py`.

No sample change (byte identity). It does not run at the same time as S4-F8 (B), S5-PERF-GATE (counter lines in the
same files) or S5-STYLE-WATER.

Scope note: the S5-STYLE runtime and frame-time budgets (D139) are a separate browser measurement. They are not
generation work counts and are not part of this task.
