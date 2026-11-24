# S5-PERF-GATE: deterministic performance gating (D153)

Owner: dev (tooling) · sprint S5, after S5-PERF-WATER, before S5-STYLE-BASE (D153)

## Problem

D147 judges performance on CPU time (`time.process_time`, 5 alternating rounds). On the shared host, identical code
(53c54d3 and 6fc2f02, which differ only in `design/`) measured **0.65–1.19×** of itself in the same round. The
host is 71–77 % busy with other workloads, and CPU time inflates under SMT and turbo contention. The +5 % gate
therefore cannot be resolved. In the REL-v0.5.0 close check, the release dev and Design measured 1.139× and 0.948×
for the same CLI series ([../reviews/REL-v0.5.0-close.md](../reviews/REL-v0.5.0-close.md)).

Python primitive call counts from cProfile were **deterministic**: the same code gives the same count across runs.
They located the whole v0.5.0 increase (D151).

## Change

Add `tools/perf/work_count.py` (a dev-owned tool; D125 keeps dev PRs out of `design/`), which runs one whole path and reports a deterministic work vector:

* **CLI whole Generate:** acquisition, plan, package write and strict validation, as `cli_time.py`.
* **Blender Generate** and **Blender Generate+Export:** measured inside Blender, as `bl_time.py`.

For each, it reports:

1. Total Python primitive calls, from `cProfile` or `sys.setprofile` counting only, with no timing.
2. Per-stage primitive calls for the named stage functions: acquire, `build_plan`, `_water_stage`, `build_terrain`,
   buildings and roofs, roads, `build_scene`, the package writer and `validate_package`.
3. A bounded op counter for hot native-heavy steps where Python calls under-count the work: bytes deflated, and
   triangles and vertices emitted per class. These come from the package report or the GLB and `.mbcol` headers.
4. CPU time, in the same run, as a sanity value.

The new gate, which replaces the D147 pass/fail rule once this merges:

* **Pass/fail:** each of the three series' total calls is ≤ **+5 %** of the base, and the op counters are ≤ +5 %
  unless the PR lists the new geometry that explains them (the D35 rule). The calls are deterministic, so one run
  per revision is enough. Two runs confirm determinism, and the gate fails if they differ.
* **Sanity:** CPU time, 5 alternating rounds (D147). It is informational. If CPU is above +15 % while calls are
  ≤ +5 %, the PR must explain it; the usual cause is native work that calls don't capture. It is a review flag,
  not an automatic fail.
* **Release floors:** the same vector against v0.4.0 (18f0822) and later tags, both measured with this tool on the
  same interpreter.

## Acceptance criteria

1. Two runs of `tools/perf/work_count.py` on the same revision give identical call counts and op counters, for both presets
   and all three series.
2. On the REL-v0.5.0 data, the tool reproduces the D151 attribution: Blender Generate calls about +13 % vs
   v0.4.0, with the increase in `_water_stage`. The reproduced figures are posted in the PR.
3. It detects a deliberate regression in a scratch branch, never merged: a loop that doubles `build_terrain` work
   shows ≥ +5 % on the series that include it and names the stage.
4. Overhead: counting adds ≤ 3× to wall time and runs once per revision. Nothing runs in PR CI.
5. Design updates the roadmap D91, D106 and D147 text and the S4/S5 specs that cite them in a follow-up design PR,
   based on this PR's evidence (D125), naming D153 as the gate.

## Tests

* A unit test of the counter on a tiny synthetic plan: counts are stable across two calls, and the per-stage
  attribution sums to the total. ≤ 5 s.
* No timing assertions.

## Conflict domain

`tools/perf/work_count.py` (new), `tests/test_work_count.py` (new). No product code and no `design/` edits.
