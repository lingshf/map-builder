# S5-F3 step 1 evidence: Bellevue-Factoria water and bank audit

Read-only investigation for `design/tasks/S5-F3.md`. It makes no product or tool edits.

## Build

* The preset is classic Bellevue-Factoria (D157): seed 1, DSM on, terrain 10 m, heightfield 2 m, textures on,
  offline.
* The cache was re-acquired online and frozen as the new reference (D177), because the #85 frozen cache was not
  available. Per-file and combined SHA-256 are in `cache-bellevue-factoria-MANIFEST-sha256.txt`, with combined
  `065ca7fd…56ac`. The `.bin` payloads are the reference data. The `.json` sidecars carry `stored_unix`, so the
  combined hash cannot match #85's `34d3509d…7bb7`.
* Packages:

  | Build | SHA-256 | Notes |
  |---|---|---|
  | CLI | `A9013073…ABB02` | |
  | Blender | `E76AE039…5EE9` | |
  | Instrumented rebuild | `A9013073…ABB02` | the CLI build with `shore._place_strip` wrapped, see below |

  The instrumented rebuild is byte-identical to the CLI build.
* The CLI and Blender `tools/floating_audit.py` reports are identical. Both reproduce #85 exactly:

  | Finding | Count |
  |---|---|
  | `water_above_bank` | 4 |
  | `water_shore_step` | 119, max 1.548 m |
  | `hf_below_ground:water` | 5 |
  | Triangles, col and vis | 218,232 each |

## Files

| File | Content |
|---|---|
| `summary.md` | Every region, both surfaces: bbox, centre, max offset, bodies, outside owners, ring steps, grid top objects, Python/C# disagreements, class and reason. The class-D detail adds the four Z values per cell and the blocked strips. |
| `classes.json` | Region id to class and reason. |
| `cells.csv.gz` | Every cell of every region, on both surfaces: collision top hit (z, `mb_id`, class), visual top hit, sheet z, outside z, outside owner and offset. |
| `rays.csv.gz` | The Python and C# rays (centre and the ±0.5 m grid at 0.1 m spacing, 121 per region), each with its hit object and z. |
| `evidence.json.gz` | The raw evidence that the files above are generated from. |
| `factoria_cli.audit.json.gz` | The audit report (`--json`). |
| `blocked_strips.json` | Every bank strip `shore._place_strip` skipped (220 strips), with the reason and the line or footprint mask hit. |
| `plan-i90.svg`, `plan-i90.png` | A plan view of the class-D cells with the skipped bank strips around them. |
| `png/` | Audit heatmaps and crops on the collision surface. The visual crops are identical. |
| `scripts/` | The harness: build, instrumented rebuild, evidence and report. |

## Reproduce

`<caches>` holds `cache-bellevue-factoria/`. `<root>` is a map-builder checkout of main 796d72b.

```
set PYTHONHASHSEED=0
py -3.12 scripts/build_factoria.py cli --root <root> --cache <caches> --out <dir>/factoria_cli.mbmap
blender -b --factory-startup --python scripts/build_factoria.py -- blender --root <root> --cache <caches> --out <dir>/factoria_blender.mbmap
py -3.12 tools/floating_audit.py <dir>/factoria_cli.mbmap --json <dir>/factoria_cli.audit.json
py -3.12 scripts/blocked_strips.py --root <root> --cache <caches> --out <dir>/factoria_instrumented.mbmap --json <dir>/blocked_strips.json
py -3.12 scripts/s5f3_evidence.py --root <root> --pkg <dir>/factoria_cli.mbmap --audit <dir>/factoria_cli.audit.json --blocked <dir>/blocked_strips.json --out <ev>
py -3.12 scripts/s5f3_report.py --evidence <ev>/evidence.json --blocked <dir>/blocked_strips.json --out <ev>
```

The C# rays use `tools/water_replay.py` (`csharp_rays`, .NET 10).

# Step 2 evidence: D178, banks continue under elevated decks

The fix is in 2328c93. "Before" is d17b5be (main 796d72b plus the step-1 evidence; the code is identical to
main). Every build is offline from the frozen caches, seed 1, DSM on.

## Files

| File | Content |
|---|---|
| `step2/ac2.json` | AC2: `tools/floating_audit.py` on the after-builds of Factoria, Munich and Pittsburgh (CLI and Blender) and on the sample (CLI and the headless Blender build). `water_above_bank` + `water_buried` regions and the max `water_shore_step`. |
| `step2/<preset>_<path>.diff.json`, `step2/diffs.json` | Member-level before → after diff: archive identity, changed members, changed collision objects and GLB nodes, changed `.mbhf` nodes with their bbox and max dz, pinned manifest and report keys, and the changed water-body report lines. |
| `step2/*.audit.json.gz` | The audit reports: after-builds unprefixed, before-builds `before_`. |
| `step2/*.water_check.txt` | `tools/water_check.py --pre-carve` (the #77 carve invariant and wet-probe clearance), before and after. |
| `step2/<preset>_cli.replay.txt`, `*.replay-diffs.json` | `tools/water_replay.py` before → after with Python and C# on every query (§7). |
| `step2/headless.txt` | The D166 headless integration run on 2328c93. |
| `perf/gate.json`, `perf/compare-*.json` | The D153 gate: `tools.perf.work_count compare` for Munich and Pittsburgh, all three series, two peers per side and five alternating CPU rounds. |
| `perf/split-<preset>.json`, `perf/attribution-*.json.gz` | Per-strip attribution of the `shore_ramps` work (`scripts/perf_attribution.py`), for the D179 waiver. |
| `png/i90-{before,after}-{oblique,plan}.png` | Same-camera renders of the I-90 crossing (`scripts/render_i90.py`); the plan view hides the bridges. |

## Reproduce

`<work>` holds the frozen caches (`frozen-caches/`), the builds (`builds/`) and the results (`step2/`).
`<base>` is a checkout of d17b5be.

```
scripts/build_all.ps1 -HeadRoot <root> -BaseRoot <base> -Caches <work>/frozen-caches -Work <work> -Blender <blender.exe>
py -3.12 scripts/precarve.py --root <root> --cache <work>/frozen-caches --preset <preset> --out <work>/builds/precarve_<preset>.mbmap
py -3.12 tools/water_check.py <package> --pre-carve <work>/builds/precarve_<preset>.mbmap
blender --background --factory-startup --python tests/blender/run_integration.py -- <work>/headless
py -3.12 scripts/step2.py --root <root> --work <work> --sample-blender <work>/headless/it.mbmap
py -3.12 tools/water_replay.py <work>/builds/before_<preset>_cli.mbmap <work>/builds/after_<preset>_cli.mbmap --diffs <file>
py -3.12 scripts/perf_attribution.py record --root <tree> --cache <work>/frozen-caches --preset pittsburgh --out <dir>
py -3.12 scripts/perf_attribution.py compare <base.json> <head.json> --out <split.json>
blender -b --factory-startup --python scripts/render_i90.py -- <package> <absolute out prefix>
```
