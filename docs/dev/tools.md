# Developer tools

How to run the verification tools on packages. This page is about usage; the design each tool checks is in the
[architecture overview](../architecture/README.md#water-and-shores), and the decisions are in the
[decision record](../../design/roadmap.md#decision-record).

All commands run from the repository root. The tools import `map_builder` from the checkout. Real-data packages
are built **offline** from the frozen caches (see [frozen inputs](#frozen-inputs)). Unless a line says otherwise,
exit code **0** means pass, **1** means a finding or failure, and **2** means it did not run completely.

| Tool | Checks | Needs |
|---|---|---|
| [`tools/floating_audit.py`](#floating-audit) | Collision, heightfield and visual surfaces agree everywhere (floating or buried collision, water and bank gaps) | `numpy` |
| [`tools/water_replay.py`](#water-replay) | Every base → head query difference is listed and explained; Python and C# agree | .NET 8 for the C# half |
| [`tools/water_check.py`](#water-check) | Carve invariant and wet-probe clearance on an emitted package | a pre-carve base package if wet probes exist |
| [`tools/style_check.py`](#style-check) | S5 G0 flight-data equality, identity, style budgets, CLI/Blender parity, palette | — |
| `tools/perf/` | D153 deterministic work gate | **pending**: arrives with S5-PERF-GATE (#91) |
| [`design/bench/`](#benchmarks-designbench) | D91 timing harnesses (CPU and wall time) and the offline guard | Blender 4.2.23 for the Blender series |

## Floating audit

```powershell
py -3.12 tools\floating_audit.py PACKAGE.mbmap --json audit.json
```

Options:

* `--cell` (default 1.0 m);
* `--threshold` (default 0.2 m);
* `--hf-tol` (default 0.05 m, heightfield against collision);
* `--min-area`;
* `--png-dir DIR` with `--crops N` for heatmaps;
* `--quiet`.

**How it works.** One downward ray per grid cell centre. For each cell it compares the **first** hit of the
`.mbcol` collision, the `.mbhf` heightfield (at its own nodes only) and the visual GLB. Findings are grouped into
4-connected regions, each with an area, a maximum offset and the object or class involved.

| Finding | Meaning | Gate |
|---|---|---|
| `floating_collision` | collision above the visual surface by more than the threshold | fails |
| `buried_collision` | visual above collision (the drone would enter a visible surface) | fails |
| `mismatch:<category>`, `ground_above_terrain:<c>`, `hf_vs_collision`, `hf_vs_visual` | per-category disagreements | fail |
| `water_above_bank:<col\|vis>` | the gap between the water sheet and the terrain, in a ring outside the wet area, is above the threshold **and** above 1.5 m + 0.05 m (`SHORE_STEP_TOL_M`) | fails; contract 0 |
| `water_shore_step:<col\|vis>` | the same gap, but within 1.5 m + 0.05 m: the designed carve step | information |
| `water_buried:<col\|vis>` | terrain above the water surface by more than the threshold | fails; contract 0 |
| `hf_below_ground:<c>` | the heightfield is below a collision ground surface; for water this is the designed bed (D117) | information |

The 0.05 m tolerance belongs to the audit's labelling. It is **not** a design bound; see
[S5-F3](../../design/tasks/S5-F3.md) for the 1.5 m + 1 mm rule. Edge-ambiguity classes are also reported (D159).
The tool also prints each water body's level, bed depth and bank gap. **Exit codes:** 0 when no failing kind is
found, 1 otherwise, 2 on a read error.

## Water replay

```powershell
py -3.12 tools\water_replay.py BASE.mbmap HEAD.mbmap --diffs diffs.json
```

Options:

* `--seed` (default 20260101), `--rays` (default 2000), `--capsules` (default 100);
* `--allow-drop ID=REASON`, `--allow-new ID=REASON`, `--allow-blocked ID=REASON`, each repeatable;
* `--show N` (default 12);
* `--no-csharp`.

**How it works.**

* **(a) Fixed-query replay.** The queries are frozen on BASE: the ray and capsule grid, the centroid rays of
  degenerate triangles, the passage-probe paths, and one downward ray per HEAD water object. They are evaluated on
  both packages in Python and in the C# reader. Every difference gets a label that must match the object, class and
  direction actually hit:
  * `new water hit`;
  * `bed moved`;
  * `road lowered`;
  * `deck raised`;
  * `bank ramp` (§7);
  * anything else is `unlisted` and fails.
* **(b) Regenerated-passage replay.** The passage sets are compared exactly; changes are allowed only through the
  `--allow-*` options.

**Exit codes:** 0 when every group ran and nothing failed; 1 on any failure; 2 when C# did not run (`--no-csharp` or
no reader), never 0.

## Water check

```powershell
py -3.12 tools\water_check.py PACKAGE.mbmap --pre-carve BASE_WITHOUT_WATER.mbmap
```

Option: `--min-clearance` (default 0.62 m = `ROAD_LIFT_M` + 0.5).

It checks two things on the **emitted** package; CLI and Blender builds are handled the same way:

* **Carve invariant:** wherever a terrain triangle and a water triangle overlap in plan, the terrain is not above the
  water. The tool prints the maximum per body.
* **Wet-probe clearance:** every `:under` probe whose capsule footprint touches water clears both the pre-carve
  ground and the water surface by `--min-clearance`.

`--pre-carve` is a package built from the same inputs without water, at the base commit.

**Exit codes:** 0 when nothing is violated; 1 on a violation; 2 when wet probes exist but `--pre-carve` is missing.

## Style check

```powershell
py -3.12 tools\style_check.py g0 --base BASE.mbmap --head HEAD.mbmap
py -3.12 tools\style_check.py classic-identity --base BASE.mbmap --head HEAD.mbmap
py -3.12 tools\style_check.py mode-diff --classic CLASSIC.mbmap --stylized STYLIZED.mbmap
py -3.12 tools\style_check.py metrics PACKAGE.mbmap
py -3.12 tools\style_check.py parity --cli CLI.mbmap --blender BLENDER.mbmap
py -3.12 tools\style_check.py palette-regions --image RENDER.png --regions REGIONS.json [--output OUT.json]
```

| Subcommand | Checks | Exit |
|---|---|---|
| `g0` | The [G0 flight-data gate](../../design/tasks/S5-STYLE.md#g0-the-flight-data-gate-every-s5-task-no-waivers): `.mbcol` and `.mbhf` byte-identical, and the georeference, passage probes and blocked and dropped lists equal | 0 / 1 |
| `classic-identity` | Whole-archive byte identity (D141) | 0 / 1 |
| `mode-diff` | Member diff between classic and stylized | 0 (report) |
| `metrics` | Style budget rows: materials, draw submissions, triangles and vertices, texture bytes, GLB size (D139) | 0 (report) |
| `parity` | Per-node material and colour parity between CLI and Blender | 0 / 1 |
| `palette-regions` | ΔE2000 of fixed screen regions against the target palette (information, D140) | 0 (report) |

The output is JSON on stdout.

## Benchmarks (`design/bench/`)

The harnesses used for D91 and D106 timing, and the D147 CPU method. Every harness installs `offline_guard.py`,
which fails the run if any DNS lookup or socket connect is attempted. Inputs are fresh copies of the
[frozen caches](#frozen-inputs).

| Script | Use |
|---|---|
| `cli_time.py` | CLI whole Generate, median of 3: `MB_CACHES=<dir> MB_OUT=<dir> MB_TAG=<tag> PYTHONPATH=<tree> py cli_time.py munich pittsburgh` |
| `bl_time.py` | Blender Generate and Export, median of 3: `blender --background --factory-startup --online-mode --python-exit-code 1 --python bl_time.py -- <tree> <tag> <cache dir> <out dir>` |
| `cpu_cli.py` | One CPU-time run (D147) per process: `py cpu_cli.py <tree> <tag> <cache dir> <out dir> <munich\|pittsburgh> [prof]` |
| `cpu_bl.py` | One CPU-time Blender run: `blender ... --python cpu_bl.py -- <tree> <tag> <cache dir> <out dir> [prof]` |
| `water_ac.py`, `water_ac_pkg.py` | S4-REVIEW scratch measurements, kept for reproduction |
| `offline_guard.py` | Imported by the harnesses; not run directly |

The performance **gate** is D153 (the work vector, `tools/perf/`, pending #91). Before that tool lands, CPU time is
the D147 sanity measure. Alternate base and head runs (D106), and never run two builds at once.

## Frozen inputs

The frozen Munich, Pittsburgh and Bellevue-Factoria caches are kept outside the repository by the Team Leader, with
a SHA-256 manifest ([team charter §7](../../design/team-charter.md#7-protected-state)). Always copy them fresh for a
run; never edit them in place. CI never needs them.
