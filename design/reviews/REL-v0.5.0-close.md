# REL-v0.5.0 close review (Design)

**Verdict: GO** on #75 exact head `cd1112c4caad918f64d76605dd6a0c92df03ebf0`
([comment](https://github.com/lingshf/map-builder/pull/75#issuecomment-7124840492)).

| Item | Value |
|---|---|
| Merged | 6535f38 |
| Earlier verdict | NO-GO on e08d3e1 ([comment](https://github.com/lingshf/map-builder/pull/75#issuecomment-7124504830)) |
| Tag and publication | Not done. These are the user's decision. |

Plan: C0–C6 (REL-v0.5.0 AC1–AC8, SPRINT_CLOSE). Decisions D149–D153 are in the
[roadmap](../roadmap.md#sprint-4-decisions).

## 1. Results

Product code, tests and the committed sample are identical from 3c741f2 to cd1112c (the later commits change docs
only). Package builds and tests from 3c741f2 therefore apply to the merged head.

* **Inputs:** frozen caches Pittsburgh (combined hash `d503067d…`) and Munich (`2f1bcdff…`), offline guard
  (0 network attempts), seed 1, DSM on, `created_utc` pinned.
* **Interpreter:** Python **3.14.4**, because 3.12 is not installed on this host. Every comparison used this one
  interpreter, so the ratios stand.

| Check | Result |
|---|---|
| C0 preconditions | PASS on cd1112c. CI is green (Python 3.11 and 3.12, C#; about 1m33s–1m52s), mergeable, with no `design/` changes (D125). mypy 2.4.1 is clean on 48 files and enforced on the CI 3.12 leg. Version 0.5.0 is in all three version files. On e08d3e1 this check **failed**: CI was red because the sample was not regenerated after the version bump. |
| C1 provenance | PASS. Fresh CLI builds reproduce the notes' SHA-256 byte-for-byte: Munich `49C42B79…`, Pittsburgh `BE4374B0…` (`package_id` `3124bbee…`). The committed sample equals a fresh deterministic build. |
| C2 validity and flight data | PASS on the sample, Munich and Pittsburgh, through the CLI and Blender: `VALID` with 1 warning each (degenerate triangles Munich 57/56, Pittsburgh 73/69, matching the notes); C# reader `OK`; 0 floating, 0 `water_above_bank`, 0 `water_buried`. The only buried region is S4-F8 (`osm:way/537242388`, 1 m², −8.77 m, Pittsburgh CLI), disclosed under D149. `water_shore_step` is information only: Pittsburgh 104 regions and the sample 4, maximum 1.500 m. |
| C3 v0.4.0 floors (D147, D150) | PASS under **D151**; see §2. |
| C4 notes | PASS on cd1112c after two fix rounds: the stale degenerate counts were corrected, the uncontrolled wall-time comparison and the "faster/cheaper" claims removed, a dangling reference removed, the CPU-time and call-count methods separated, D151 and S4-F8 disclosed, and the zip cell set to "added at publication (D100)". Non-blocking: the CPU-time bullet omits Blender Generate's 1.20×, but the call-count bullet discloses that cost. |
| C5 test audit (D134) | PASS. 866 tests pass in CI. The closeout modules (`test_shore_ramps`, `test_floating_audit`, `test_water_replay`, `test_water`) run 95 tests in 3.4 s, the slowest 0.64 s. No new test over 5 s and no wall-clock asserts. Every test over 5 s predates the closeout (#2, #3, #4, and `test_col_degen` C#, which is the known S4-F7). |
| C6 extension (D100) | PASS. Two clean builds from fresh clones of one commit are byte-identical (`1A58D0AB…`, 886,813 B). `extension validate` passes. A clean install into an isolated user directory loads (0, 5, 0), and the panel registers. **Finding:** `tools/build_extension.sh` stamps file times with the HEAD commit time, so the zip hash changes with every commit even when the contents are identical (e08d3e1, 3c741f2 and 5a67c4a all differ, in timestamps only). A zip hash can therefore never be listed in the notes of the same commit; AC3 is verified at publication. |

## 2. C3 attribution (Pittsburgh, textured)

Method:

* `design/bench/cpu_cli.py` and `design/bench/cpu_bl.py` (D147 CPU time, one run per process);
* 7 points × 5 rounds, with the point order rotated and reversed on alternate rounds;
* cProfile on 4 of the points.

Raw data: [data/REL-v0.5.0-close-cpu.jsonl](data/REL-v0.5.0-close-cpu.jsonl).

The seven points:

| Point | Commit | What it is |
|---|---|---|
| v0.4.0 | 18f0822 | v0.4.0 |
| 70d93c7 | 70d93c7 | before water surfaces |
| d38d4e8 | d38d4e8 | #72 water surfaces |
| 53c54d3 | 53c54d3 | RC's original base |
| 6fc2f02 | 6fc2f02 | same product code as 53c54d3 (noise control) |
| db9db44 | db9db44 | #77 shore ramps |
| e08d3e1 | e08d3e1 | RC head |

Paired medians against v0.4.0 in the same round. The rightmost column is the RC head.

| Series | 70d93c7 | d38d4e8 | 53c54d3 | 6fc2f02 | db9db44 | e08d3e1 |
|---|---|---|---|---|---|---|
| CLI whole Generate | 0.954 | 0.951 | 1.004 | 1.010 | 1.000 | **0.948** |
| Blender Generate | 0.978 | 0.991 | 1.244 | 1.184 | 1.214 | **1.202** |
| Blender Generate+Export | 0.897 | 0.864 | 0.970 | 1.059 | 1.000 | **0.991** |

**Noise floor.** 53c54d3 and 6fc2f02 have identical product code. Their same-round ratios were 0.67–1.19 (CLI)
and 0.65–1.23 (Blender Generate). v0.4.0's own CLI CPU time ranged from 28.3 s to 43.4 s. The host was 71–77 %
busy with other workloads. **CPU time cannot resolve ±5 % here** (follow-up: D153).

**Deterministic work** (Python primitive calls, the same on every run):

| | v0.4.0 | d38d4e8 (#72) | 53c54d3 | e08d3e1 |
|---|---|---|---|---|
| CLI whole Generate | 86.72 M | 89.01 M | 89.02 M | 91.40 M (+5.4 %) |
| Blender Generate | 34.12 M | 36.63 M | 36.65 M | 38.54 M (**+13.0 %**) |

* **#72 (water surfaces):** about +7.4 % on Blender Generate.
* **#73, #74, #76:** about 0.
* **#77 (shore ramps):** about +5.2 %, almost all `core/overlap.py` and `core/shore.py`.
* **#81 (mypy):** 0.
* The water stage is 6.5 % of Blender Generate (2.8 % of that is shore ramps) and 3.7 % of the CLI.
* The top 15 functions on the RC are the same functions with the same call counts as on 53c54d3. The one
  exception is `osm.point_in_ring` (58.9 k → 80.3 k), from the water masks.

**Classification:**

* **(a) Legitimate new geometry, under the D35 precedent:** the Blender Generate increase, all in the water stage.
* **(b) Measurement error:** the CLI discrepancy (the release dev measured 1.139×, Design 0.948×) and the old
  "16.0 s vs 20.0 s" claim.
* **(c) Real regression:** none found.

Coordinator decision **D151** accepts (a) as a disclosed exception. **D152** files S5-PERF-WATER.

## 3. Coordinator retro (recorded for the coordinator)

* **The merge gate held.** No PR merged without green CI on its exact head and coordinator authorisation. The
  approval exceptions are recorded (D146) and were not repeated without a record.
* **#77 needed six coordinator-authorised follow-up commits** (881c269 … b890bae), not the one D135 allowed. The
  heuristic overlap tests kept failing review, first by sampling, then by shrinking, then by missing a third body.
  **Lesson:** a spec states the exact geometric predicate up front: what counts as overlap or contact, and the
  tolerance, with a test on each side. Review then checks against that predicate instead of discovering it. S4-F8
  AC5 and S5-PERF-WATER AC4 apply this.
* **#81 (typing):** output-identity checks (byte-identical packages) only cover branches the fixtures reach. A type
  "fix" in an untested branch can change behaviour unseen. **Lesson:** a typing PR needs a control-flow audit. For
  each narrowed or `assert`-ed value, the PR states whether the old branch was reachable and which test or package
  covers it.
* **The RC handoff claimed green CI while it was red** (e08d3e1: the sample was not regenerated). **Lesson:** the
  coordinator, and the close check (C0), read CI on the exact head; a handoff statement is not evidence.
* **Measurement:** D147 replaced wall time with CPU time but still could not resolve ±5 % on a shared host.
  Deterministic counts did (D153).

## 4. Follow-ups and sprint 5 order (D149, D152, D153)

**S4-F8** → **S5-PERF-WATER** → **S5-PERF-GATE** (D153) → **S5-STYLE-BASE** → PALETTE → WATER → S5-STYLE-REVIEW,
then S5-DECOR last.

| Task | Why | Spec |
|---|---|---|
| S4-F8 | exact collision; investigate the buried singleton | [../tasks/S4-F8.md](../tasks/S4-F8.md) |
| S5-PERF-WATER | water stage back to ≤ 3.8 % of Blender Generate, byte-identical | [../tasks/S5-PERF-WATER.md](../tasks/S5-PERF-WATER.md) |
| S5-PERF-GATE | deterministic performance gate | [../tasks/S5-PERF-GATE.md](../tasks/S5-PERF-GATE.md) |
| (non-blocking) | add Blender Generate's 1.20× CPU figure to the notes at publication | release manager |
