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
