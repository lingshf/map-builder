# Developer tools

How to run the verification tools on packages. This page is about usage; the design each tool checks is in the
[architecture overview](../architecture/README.md#water-and-shores), and the decisions are in the
[decision record](../../design/roadmap.md#decision-record).

All commands run from the repository root in PowerShell. The tools import `map_builder` from the checkout.
Real-data packages are built **offline** from the frozen caches (see [frozen inputs](#frozen-inputs)). Exit codes
differ per tool; each section states them.

| Tool | Checks | Needs |
|---|---|---|
| [`tools/floating_audit.py`](#floating-audit) | Collision, heightfield and visual surfaces agree everywhere (floating or buried collision, water and bank gaps) | `numpy`; Pillow for `--png-dir` |
| [`tools/water_replay.py`](#water-replay) | Every base → head query difference is listed and explained; Python and C# agree | .NET 8 SDK for the C# half |
| [`tools/water_check.py`](#water-check) | Carve invariant and wet-probe clearance on an emitted package | a pre-carve base package if the package has any `:under` probe |
| [`tools/style_check.py`](#style-check) | S5 G0 flight-data equality, identity, style budgets, CLI/Blender parity, palette | Pillow for `palette-regions` |
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
* `--png-dir DIR` with `--crops N` for heatmaps (needs Pillow);
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
| `hf_below_ground:water` | the heightfield is below the water surface: the designed bed (D117) | information |
| `hf_below_ground:<c>` for any other category | the heightfield is below a terrain or road collision surface | fails |
| `hf_coverage` | a heightfield node exists where the terrain collision has none, or the reverse | information |
| `edge_ambiguous_collision_visual` | a would-be `buried_collision` cell at a collision triangle edge, where a ray shifted by ±1e-4 m reaches the visual height (D159) | information |

The 0.05 m tolerance belongs to the audit's labelling. It is **not** a design bound; see
[S5-F3](../../design/tasks/S5-F3.md) for the 1.5 m + 1 mm rule. The informational kinds are exactly
`INFO_KINDS` in the source; every other kind fails. The tool also prints each water body's level, bed depth and bank
gap. This table is the canonical explanation of the audit categories; other pages link here.

**Exit codes:** 0 when no failing kind is found; 1 otherwise; 2 when the audit raises any error (a missing or
unreadable package, for example).

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

The C# half runs the shared reader build (`dotnet` plus the reader DLL from `tests/csharp_build.py`).

**Exit codes:**

* 0: every group ran, C# included, and nothing failed;
* 1: any failure. Failures take precedence over a skipped C# half. A C# reader that cannot run (no `dotnet` on
  `PATH`, a build or run error) also stops the tool with an error and exit 1; it is **not** turned into 2;
* 2: only when an otherwise passing run used `--no-csharp`. A Python-only pass is never 0.

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

`--pre-carve` is a package built from the same inputs without water, at the base commit. It is required as soon as
the package has **any** `:under` probe, before the tool knows whether a probe touches water. The committed sample
has `:under` probes but no wet ones: it reports zero wet under-probes with a base and exits 2 without one.

**Exit codes:** 0 when nothing is violated; 1 on a violation (or a corrupt package); 2 when the package has a
`:under` probe and `--pre-carve` is missing.

## Style check

```powershell
py -3.12 tools\style_check.py g0 --base BASE.mbmap --head HEAD.mbmap
py -3.12 tools\style_check.py classic-identity --base BASE.mbmap --head HEAD.mbmap
py -3.12 tools\style_check.py mode-diff --classic CLASSIC.mbmap --stylized STYLIZED.mbmap
py -3.12 tools\style_check.py metrics PACKAGE.mbmap
py -3.12 tools\style_check.py parity --cli CLI.mbmap --blender BLENDER.mbmap
py -3.12 tools\style_check.py palette-regions --image RENDER.png --regions REGIONS.json --output OUT.json
```

| Subcommand | Checks | Exit |
|---|---|---|
| `g0` | The [G0 flight-data gate](../../design/tasks/S5-STYLE.md#g0-the-flight-data-gate-every-s5-task-no-waivers): `.mbcol` and `.mbhf` byte-identical, and the georeference, passage probes and blocked and dropped lists equal | 0 / 1 |
| `classic-identity` | Whole-archive byte identity (D141) | 0 / 1 |
| `mode-diff` | Member diff between classic and stylized | 0 (report) |
| `metrics` | Style budget rows (D139): materials, draw submissions, triangles, vertices, and `render_memory_bytes`, a **proxy**: the GLB buffer views referenced by drawn primitives plus embedded image bytes. The packaged sizes are separate: `texture_bytes`, `glb_bytes`, `package_bytes` | 0 (report) |
| `parity` | Per-node material and colour parity between CLI and Blender | 0 / 1 |
| `palette-regions` | ΔE2000 of fixed screen regions against the target palette (information, D140); needs Pillow | 0 (report) |

The output is JSON on stdout. `--output` is optional and also writes it to a file. The minimal `REGIONS.json`
for `palette-regions`; `x`, `y`, `w` and `h` are fractions of the image size from the top-left corner, and
`camera` and `label` are copied to the output:

```json
{"regions": [{"camera": "ponds", "label": "water", "x": 0.40, "y": 0.55, "w": 0.10, "h": 0.08, "target_hex": "#3c6e8c"}]}
```

## Benchmarks (`design/bench/`)

The harnesses used for D91 and D106 timing, and the D147 CPU method. Every harness installs `offline_guard.py`,
which fails the run if any DNS lookup or socket connect is attempted, and copies its input cache fresh for each run.
Only `munich` and `pittsburgh` are supported: the Blender scripts pick the preset from the cache path.

Setup (PowerShell, repository root; the cache path is the Team Leader's custody location, see
[frozen inputs](#frozen-inputs)):

```powershell
$caches = 'C:\Users\shaoling\.copilot\session-state\4b9ee088-73ed-46c9-9dfd-7c02a71d624c\files\frozen-caches'
$blender = 'C:\tools\blender-4.2.23-windows-x64\blender.exe'
$tree = (Get-Location).Path
$out = "$env:TEMP\mb-bench"; New-Item -ItemType Directory -Force $out | Out-Null
$env:MB_CACHES = $caches; $env:MB_OUT = $out; $env:MB_TAG = 'head'; $env:PYTHONPATH = $tree
```

| Script | Input | Command |
|---|---|---|
| `cli_time.py`: CLI whole Generate, median of 3 | `MB_CACHES` is the **parent** directory holding `cache-munich` and `cache-pittsburgh` | `py -3.12 design\bench\cli_time.py munich pittsburgh` |
| `bl_time.py`: Blender Generate and Export, median of 3 | one **preset cache directory** | `& $blender --background --factory-startup --online-mode --python-exit-code 1 --python design\bench\bl_time.py -- $tree head "$caches\cache-munich" $out` |
| `cpu_cli.py`: one CPU-time run (D147) per process | one preset cache directory | `py -3.12 design\bench\cpu_cli.py $tree head "$caches\cache-munich" $out munich` (append `prof` for a cProfile dump) |
| `cpu_bl.py`: one CPU-time Blender run per process | one preset cache directory | `& $blender --background --factory-startup --online-mode --python-exit-code 1 --python design\bench\cpu_bl.py -- $tree head "$caches\cache-munich" $out` (append `prof` after `$out`) |

**Process success is not package validity for `bl_time.py`.** It exits 0 even when a run's package fails
validation, and records `runs[].ok` in `res-<tag>-<preset>.json`; check every `ok`. `cli_time.py` and `cpu_cli.py`
assert validation; `cpu_bl.py` asserts that both operators finished.

`water_ac.py` and `water_ac_pkg.py` are S4-REVIEW scratch measurements kept for history, with no maintained recipe.
`offline_guard.py` is imported by the harnesses and is not run directly.

The measurement method (alternating base and head, one build at a time, medians and CPU time) is defined in the
[decision record](../../design/roadmap.md#decision-record) under D91, D106 and D147 and is not restated here. The
performance **gate** is D153 (`tools/perf/`, pending #91).

## Frozen inputs

The frozen Munich, Pittsburgh and Bellevue-Factoria caches are kept outside the repository by the Team Leader, with
a SHA-256 manifest ([team charter §7](../../design/team-charter.md#7-protected-state)). Always copy them fresh for a
run; never edit them in place. CI never needs them.
