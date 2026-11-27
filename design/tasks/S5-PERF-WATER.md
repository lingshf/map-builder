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
5. **Frame-time proxy: sensitivity control and D139 result (D186a, moved from #100).** #100 measured exactly
   150.0 ms on both sides. The page times `requestAnimationFrame` intervals, which headless Chromium paces, so a
   render regression below the pacing floor is invisible. This AC makes the proxy measure render work and proves it.
   * **Measure render work, not intervals.** In `tools/demo/viewer/frame_time_proxy.html`, each measured frame
     records `t0 = performance.now()`, then `renderer.render(scene, camera)` repeated `passes` times, then a forced
     GPU sync (a 1 × 1 `gl.readPixels` after `gl.finish()`), then `t1`. The result gains `median_render_ms`
     (the median of `t1 − t0`) and `passes`. `median_ms` (the interval) stays, as information only.
   * **`passes` parameter.** A URL parameter `passes` (integer ≥ 1, default 1). The runner
     `tools/demo/style_frame_time_proxy.py` adds `--head-passes N` (default 1), which applies only to the head
     side in alternating mode. The runner reports `ratio = median(head median_render_ms) / median(base
     median_render_ms)` over the pairs.
   * **Fixed setup:** the Pittsburgh **stylized** package built at the PR head with the G0 settings, preset
     `pittsburgh`, camera `overview`, 1280 × 720, 60 warm-up + 300 measured frames, 3 alternating pairs, the
     existing SwiftShader flags; one host and one session for all runs below.
   * **C1, A/A control:** the same package as base and head, `--head-passes 1`. Pass: `|ratio − 1| ≤ 0.03`.
   * **C2, known increase:** the same package as base and head, `--head-passes 2` (about +100 % render work).
     Pass: `ratio ≥ 1.10`, so the proxy flags a regression larger than the D139 +10 % floor.
   * **D139 result:** base = the Pittsburgh stylized package built at this PR's merge-base, head = the PR head,
     `--head-passes 1`. Pass: `ratio ≤ 1.10`. (AC1 makes the GLBs byte-identical, so this is expected near 1.00;
     the PR posts it anyway, as the first established D139 proxy number for S5.)
   * If C1 or C2 fails, the proxy is **not established**: the PR does not merge on AC5. It reports the numbers to
     Design, which then approves a replacement proxy or a different control. It does not report a D139 pass.
   * The PR posts the raw JSON of every run (C1, C2, the D139 pair), the GLB SHA-256s and the renderer string.

## Tests

* The AC4 equivalence test, in `tests/test_overlap.py` (new) or `tests/test_shore_ramps.py`, with the containment
  cases named.
* If any cache is kept, a test where a cached cell straddles the body edge must give the exact answer.
* The existing shore, water and replay tests pass unchanged. Do not duplicate S4-COL-FLOAT-2 cases.
* AC5: in `tests/test_style_frame_time_proxy.py`, the runner builds a URL carrying `passes`, applies `--head-passes` to the head side only, and computes `ratio` and the C1, C2 and D139 verdicts from canned result JSON. No browser runs in CI; the test takes ≤ 5 s. The browser runs are PR evidence.

## Conflict domain

`core/overlap.py`, `core/shore.py` (mask callbacks only), `core/water.py` (`_inside_pieces`, the mask helpers), the
water-stage mask construction in `core/generate.py`, `tests/test_overlap.py`, `tests/test_shore_ramps.py`; for AC5 only,
`tools/demo/viewer/frame_time_proxy.html`, `tools/demo/style_frame_time_proxy.py` and
`tests/test_style_frame_time_proxy.py` (no product code).

No sample change (byte identity). It does not run at the same time as S4-F8 (B), S5-PERF-GATE (counter lines in the
same files) or S5-STYLE-WATER.

Scope note: the D139 frame-time proxy is a browser measurement, not a generation work count; it was added to this
task as AC5 by D186a (amended in #104 after the dev started). AC1–AC4 are unchanged.
