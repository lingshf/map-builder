# S5-PERF-GATE: deterministic performance gating (D153)

Owner: dev (tooling) · sprint S5 · runs **after S4-F8 and before S5-PERF-WATER** (D154)

## Problem

D147 judges performance on CPU time (`time.process_time`, 5 alternating rounds). On the shared host, identical
product code (53c54d3 vs 6fc2f02) measured, per series, in the same round:

| Series | Same-code ratio range |
|---|---|
| CLI whole Generate | 0.67–1.19× |
| Blender Generate | 0.65–1.23× |
| Blender Generate+Export | 0.84–1.29× |

A +5 % gate cannot be resolved on this host
([../reviews/REL-v0.5.0-close.md](../reviews/REL-v0.5.0-close.md)). Python call counts were deterministic and
located the v0.5.0 increase (D151). Call counts alone can still be gamed, though:

* inline arithmetic in a loop adds work without adding calls;
* repeating a native operation (deflate, `struct.pack`, list sort) adds work without changing call counts or output
  size.

The gate therefore counts **operations**, not just calls.

## The metric (pinned)

**Work vector.** For each series, the work vector is the following set of counters.

1. **Explicit operation counters in the hot loops.** Implemented as a module-level `perf_counters` registry in
   `map_builder/core/` that costs nothing when disabled: an integer increment behind one module flag, and no I/O.
   This is a closed, pinned list; adding or removing a counter is itself a gated change:

| Counter | Counted unit |
|---|---|
| `tri_emitted[class]` | collision triangles appended by `generate.py` |
| `ring_edge_tests` | edges visited in `osm.point_in_ring`, `osm.ring_self_intersects` and `osm._segments_intersect` callers |
| `clip_steps` | vertices processed in `generate._clip_halfplane`, `water._clip_half` and `overlap._clip_against_edge` |
| `overlap_pairs` / `overlap_edge_tests` | triangle–mask pairs tested, and edges tested inside `core/overlap.py` |
| `grid_cells_rasterised` | cells in `collision.rasterize_heightfield` and the DEM/DSM grid passes |
| `deflate_in_bytes` | cumulative bytes passed **into** zlib/deflate (every call, including retries), not output size |
| `glb_bytes_written`, `mbcol_bytes_written` | bytes written per member |
| `validator_pairs` | `package.match_one_to_one` and `match_winding` candidate pairs examined |
| `bpy_mesh_vertices` | vertices passed to `mesh_from_data` (Blender only) |

2. **Python primitive calls**, from the same run.

**Attribution (non-overlapping).** Counters and calls are attributed to the **innermost** active stage from this
fixed stack:

`acquire` > `build_plan` > { `_water_stage` > `shore_ramps`, `build_terrain`, buildings/roofs, roads, bridges,
tunnels } > `build_scene` (Blender) > package write > `validate_package`

Nested stages are subtracted from their parents, so each count lands in exactly one stage. The sum over stages
must equal the series total, and the tool fails if it doesn't.

**Pins:**

* Checker: `tools/perf/work_count.py` taken from **the head being judged**, run unchanged against both base and
  head trees. Its own changes are judged on a no-op product change.
* Interpreter: CLI on the host's installed CPython, the exact version recorded and the same for both revisions.
  Blender: 4.2.23 with its bundled Python.
* Profiler backend: `cProfile` for call counts only, never timing.
* Inputs: frozen caches (Pittsburgh `d503067d…`, Munich `2f1bcdff…`), offline guard, seed 1, DSM on, textured,
  `created_utc` pinned.
* Run boundaries, the same three series as D91:
  * CLI whole Generate: acquisition through package write and strict validation;
  * Blender Generate;
  * Blender Generate+Export.

## Failure rules

A revision **fails** the gate if any of these holds. Each check runs per series, for Munich and Pittsburgh.

* **F1, completeness.** A run errors, the package is not `VALID`, an expected counter or stage is missing, or two
  runs of the same revision differ in any counter or call count. Determinism is required: one run, plus one
  confirmation run.
* **F2, series total.** Any operation counter's series total is **> +5.0 %** over the base (so exactly +5.0 %
  passes), unless the PR lists new geometry that explains it under D35 and the coordinator records an exception.
  The same rule applies to the total primitive calls.
* **F3, stage.** Any single stage's counter or call total is **> +10.0 %** over the base and **> 1 %** of the
  series total. This catches a doubled stage that is too small to move the series by 5 %.
* **F4, redistribution, review gate.** Work moving between stages or counters is not a pass by itself. The PR
  must list every stage and counter that grew by > 5 %, with the reason, and the reviewer must accept them
  explicitly.
* **F5, CPU sanity, review gate.** D147 CPU medians come from 5 alternating rounds. If CPU > +15 % while F2 and F3
  pass, the PR must explain the unmeasured work (native or inline). The reviewer either accepts it or requires a
  new counter.

## Acceptance criteria

1. **Determinism:** two runs on the same revision give identical counters, calls and stage attribution for both
   presets and all three series, and the stage sums equal the totals.
2. **Reproduction:** on the REL-v0.5.0 data, the tool reproduces the D151 attribution. Blender Generate calls are
   about +13 % vs v0.4.0, all in `_water_stage` and `shore_ramps`
   ([../reviews/data/REL-v0.5.0-close-profile.json](../reviews/data/REL-v0.5.0-close-profile.json)).
3. **Negative cases.** Each is a scratch branch that is never merged, and each must **fail**:
   * an inline arithmetic loop in `build_terrain` with no new calls fails F3 through `clip_steps` or
     `grid_cells_rasterised`;
   * deflating each member twice, with identical output bytes and call counts, fails F2 through `deflate_in_bytes`;
   * doubling `_water_stage`'s work fails F3 on that stage, even though the series grows by less than 5 %.
4. **Clean pass:** a no-op change passes F1–F5.
5. **Counter overhead:** with counters disabled, the packages are byte-identical and total calls equal the base.
   With counters enabled, wall time is ≤ 3× the base. Nothing runs in PR CI.
6. **Docs:** Design updates the roadmap D91/D106/D147 text and the specs that cite them in a follow-up design PR
   (D125), naming D153 as the gate.

## Tests (≤ 5 s each)

* Counter registry: off by default, increments only when enabled, and resets per run.
* Attribution on a tiny synthetic plan: nested stages are subtracted, and stage sums equal the totals.
* No timing assertions.

## Conflict domain

`tools/perf/work_count.py` (new); `map_builder/core/perf_counters.py` (new); one-line counter increments in the
listed hot functions of `core/osm.py`, `core/generate.py`, `core/water.py`, `core/overlap.py`, `core/collision.py`,
`core/package.py` and `blender/scene_build.py`; `tests/test_work_count.py` (new).

No output change: AC5 requires byte identity. It does not run at the same time as S4-F8 (B), which may edit
`generate.py` or `collision.py`.
