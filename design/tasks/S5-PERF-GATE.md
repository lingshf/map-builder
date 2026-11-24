# S5-PERF-GATE: deterministic performance gating (D153)

Owner: dev (tooling) · sprint S5 · runs **after S4-F8 and S5-STYLE-BASE, before S5-STYLE-PALETTE** (D156)

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

**Work vector.** Each series has a work vector made of two parts.

1. **Explicit operation counters at counted sites.** These live in the module-level `perf_counters` registry in
   `map_builder/core/`. When disabled they cost nothing: one module-flag check and an integer increment, no I/O.
   The list is closed and pinned, so adding or removing a counter is itself a gated change. Each counter counts
   **only at its named sites**:

| Counter | Unit | Counted sites |
|---|---|---|
| `tri_emitted[class]` | collision triangles appended | `generate.py` mesh assembly |
| `ring_edge_tests` | ring edges visited | `osm.point_in_ring`, `osm.ring_self_intersects`, `osm._segments_intersect` |
| `clip_steps` | input vertices processed | `generate._clip_halfplane`, `water._clip_half`, `overlap._clip_against_edge` |
| `overlap_pairs` | triangle–mask pairs given to the exact test | `core/overlap.py` entry points |
| `overlap_edge_tests` | edges tested inside the exact test | `core/overlap.py` |
| `candidate_pairs` | triangle–mask pairs produced by candidate filtering | water-stage mask lookups |
| `grid_cells` | grid cells visited | `collision.rasterize_heightfield`, the DEM/DSM grid passes, the `build_terrain` cell loop |
| `deflate_in_bytes` | bytes passed **into** every compressor call, including retries and fallback paths | every `zlib`/`zipfile` compression call site |
| `bytes_written[member]` | bytes written per package member | package writer |
| `validator_pairs` | candidate pairs examined | `package.match_one_to_one`, `match_winding` |
| `bpy_mesh_vertices` | vertices passed in (Blender only) | `mesh_from_data` |

2. **Python primitive calls**, counted by `cProfile` and used only for counting, in the same run.

**Coverage limit, stated plainly.** Counters see work only at their counted sites. New work at an **uncounted
site** does not move any counter: for example inline arithmetic, a new loop that calls no counted function, or
native work outside the listed calls. Such work may show in call counts, and otherwise only in CPU time. That is
why F5 exists, and why any PR that changes uncounted work must say so (F6).

**Zero and not applicable.** Every counter is reported for every series. Zero is a valid value, for example
`bpy_mesh_vertices` in the CLI series or `overlap_pairs` on a package with no water. A counter that is
**structurally inapplicable** to a series is listed as `n/a` in a fixed table in the tool, and only those may be
absent. Any other missing counter fails F1.

**Attribution (non-overlapping).** Each count goes to the **innermost** active stage of this fixed stack:

`acquire` > `build_plan` > { `_water_stage` > `shore_ramps`, `build_terrain`, buildings/roofs, roads, bridges,
tunnels } > `build_scene` (Blender) > package write > `validate_package`

* Nested stages are subtracted from their parents.
* Work outside every named stage (setup, operator overhead, teardown) goes to a fixed `other` stage.
* Stage sums plus `other` must equal the series total, or the run fails F1.

## Baseline and versions (coordinator ruling)

* **Counters land first, isolated.** S5-PERF-GATE adds the counters in **one output-neutral commit** `C`: the
  registry plus the increments, packages byte-identical with counters off. The tool `tools/perf/work_count.py`
  goes in a separate commit.
* **Base for every comparison.** The base is the PR's merge-base with `C` cherry-applied. The checker builds it in a
  temporary worktree it creates itself, and that worktree is never pushed. The head already contains `C` once
  S5-PERF-GATE has merged; before that, the head is measured with `C` applied too.
* **If `C` does not apply cleanly** to the base or the head, that is F1. There is no hand-merging; the PR author
  rebases.
* **The first PR (S5-PERF-GATE itself)** is verified in three steps. Each must pass on the sample, Munich and
  Pittsburgh across all three series:
  * `C` with counters off is byte-identical to the merge-base;
  * two runs of merge-base+`C` give identical vectors;
  * the AC3 negative cases fail as specified.
* **Checker pinning.** Product comparisons use the checker and `C` at the **commit recorded in the roadmap**
  (D153), not the head's. A PR that changes the checker or the counters is a checker change. It is judged on the
  three steps above, plus every negative case still failing and the no-op still passing. Design reviews it before
  any product PR uses the new version.
* **Historical floors.** Comparisons against v0.4.0 or earlier tags (which have no counters) are **informational
  only**, made by applying `C` to the tag where it applies, or with call counts and CPU time otherwise. They are
  not gates (coordinator ruling). Release-candidate floors for future releases compare against the previous
  release **tag + `C`** under the same rules.

## Failure rules

These checks run per series, for Munich and Pittsburgh, the **gating presets**. The sample and Bellevue-Factoria
are evidence-only (visuals and G0, D157) and are not part of this gate.

**The revision fails if:**

* **F1, completeness.** A run errors, a package is not `VALID`, a required counter or stage is missing, the stage
  sums do not match, `C` does not apply, or two runs of one revision differ in any counter or call count.
* **F2, series total.** Any counter's series total or the total primitive calls are **> +5.0 %** over the base.
  Exactly +5.0 % passes. The exception is new geometry listed under D35 with a coordinator exception.
* **F3, stage.** For any stage and any counter (or calls), the stage value is **> +10.0 %** over the same stage and
  counter on the base, **and** the increase is **> 1 %** of that **same counter's** series total on the base.

**Review gates, not automatic fails:**

* **F4, redistribution.** The PR lists every stage or counter that grew by > 5 %, with the reason, and the reviewer
  accepts or rejects each one explicitly.
* **F5, CPU sanity.** D147 CPU medians over 5 alternating rounds are posted. If any series is **> +5 %** on CPU
  while F2 and F3 pass, the PR must account for it: either name the uncounted work, or show that it is noise with
  a same-code control pair from the same session. The reviewer decides.
* **F6, uncounted work.** A PR that adds or changes loops or native calls at uncounted sites must list them. The
  reviewer either accepts the CPU evidence (F5) or requires a new counter, which is a checker change.

## Acceptance criteria

1. **Determinism:** two runs on the same revision give identical vectors and attribution for both presets and all
   three series. The stage sums plus `other` equal the totals.
2. **Output neutrality:** with counters off, commit `C` keeps the sample, Munich and Pittsburgh whole-archive
   byte-identical (CLI and Blender), and the total primitive calls equal the merge-base's.
3. **Negative cases.** Each is a scratch branch that is never merged:
   * **Counted, F3:** run every `build_terrain` cell twice through the counted cell loop. `grid_cells` in
     `build_terrain` doubles, and F3 must fail on that stage and counter.
   * **Counted, F2:** deflate every member twice, passing through the counted compressor sites, with identical
     output bytes. `deflate_in_bytes` doubles, and F2 must fail. A second variant forces the fallback or retry
     compression path, and must also fail, which proves that path is counted.
   * **Counted, F3 on a small stage:** double the overlap exact tests in `_water_stage`. `overlap_edge_tests`
     doubles in that stage, so F3 must fail even though the series grows by less than 5 %.
   * **Uncounted (coverage limit):** add an inline arithmetic loop inside `build_terrain` that calls nothing
     counted. The counters **do not change, and F1–F3 pass.** The case must surface in F5, which posts the CPU
     delta, and F6, which lists the uncounted loop. The test asserts exactly that: counters unchanged, F5 and F6
     triggered.
4. **No-op:** a no-op change passes F1–F3 and triggers no F4, F5 or F6.
5. **Overhead:** with counters on, wall time is ≤ 3× the base. Nothing runs in PR CI.
6. **Docs:** after merge, Design records the pinned checker and `C` commit in D153, and updates the D91/D106/D147
   text and the specs that cite them (D125).

## Tests (≤ 5 s each)

* Counter registry: off by default, increments only when enabled, resets per run.
* Attribution on a tiny synthetic plan: nested stages are subtracted, `other` collects the rest, and sums equal
  totals.
* The `n/a` table: a missing inapplicable counter passes, and any other missing counter fails F1.
* No timing assertions.

## Conflict domain

* `tools/perf/work_count.py` (new) and `map_builder/core/perf_counters.py` (new).
* One-line increments at the listed sites in `core/osm.py`, `core/generate.py`, `core/water.py`,
  `core/overlap.py`, `core/collision.py` and `core/package.py` (compressor sites), and `blender/scene_build.py`.
* `tests/test_work_count.py` (new).

No output change (AC2). It does not run at the same time as S4-F8 case (B), which edits `generate.py` or
`collision.py`.
