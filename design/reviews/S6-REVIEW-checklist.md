# S6-REVIEW: milestone checklist and verdict (M-S6)

Owner: design · task [S6-REVIEW](../tasks/S6.md#s6-review-milestone-review-gono-go) · decisions D137, D139, D140,
D198, D200–D210. Derived from the [S5 checklist](S5-STYLE-REVIEW-checklist.md); rows keep their
S5 numbers where the check is the same.

This is the milestone review on main (M-S6). It is not a release review; no release is cut by default (D202).

## Revisions and settings

| Role | Revision | Use |
|---|---|---|
| Review head **H** | `4e51412` (main after #123, D209) | GO revision |
| Gate and render revision | `fabab19` (main after #122, S6-STYLE-TUNE) | every gate and render below. `fabab19..4e51412` changes only one row of `tools/demo/palette_regions_pittsburgh.json`, so builds and renders are the same at H; the one affected ΔE row was recomputed with the H file |
| Visual **before** | `b04b769` (v0.6.0 merge), **stylized** | left column of every sheet (AC1) |
| G0 base | `b04b769`, per preset, path and style | G1 |
| G3 base, CLI classic | `b04b769` | G3 |
| G3 base, Blender classic | `656eab0` (S6-PARITY #119 merge, D207) | G3 |
| Budget base | `b04b769`, stylized, per preset and path | G6 (D139, as in STYLE-TUNE AC2) |

* **Build settings.** Frozen caches: the two surviving copies of the D163 custody set are identical (25 files), and
  Factoria matches [the D177/D190 MANIFEST](../evidence/S5-F3/cache-bellevue-factoria-MANIFEST-sha256.txt)
  (`065ca7fd…56ac`). Seed 1, offline, DSM on, spacing 10 m, heightfield 2 m,
  `created_utc=2026-11-20T00:00:00Z` (Blender: the S5 harness pin, see F4), Blender 4.2.23 at `C:\tools\`. 52 builds,
  all exit 0.
* **Render inputs.** `git archive fabab19 tools/demo map_builder` renders **both** columns
  (`tools/demo/style_render_recipe.py`, then `tools/demo/style_compare.py`, both from #118). Cycles CPU, 64 samples,
  seed 1, no denoise, 1280 × 720, CLI-path packages on both sides. Every output rendered in ≤ 41.6 s (D140 limit
  120 s, information only).
* **Evidence.** Sheets are attached to the review PR. The paired ΔE reports and the window ray check are in
  [`data/S6/`](data/S6/).

## Scope

In scope, all merged into H: #115 S6-CONSUMER-TRIAGE, #116 S6-TEX-WATER-CLOSE, #117 water guidance, #118
S6-DEMO-2COL, #119 S6-PARITY, #120 S6 bookkeeping, #121 DOC-TOOLS-F1, #122 S6-STYLE-TUNE, #123 D209 window fix.
Out of scope: S5-DECOR (deferred, D185); the sample preset in G10 (D208, S7-SAMPLE-PARITY; see F3).

## Camera set

The 18 rows of the [S5 camera table](S5-STYLE-REVIEW-checklist.md#camera-set-every-d140-camera), unchanged. Rows
1–17 are revision pairs (stylized b04b769 | stylized H). Row 18 is Factoria classic H | stylized H, information only
(AC1). All 17 pair sheets are in the [sheets comment](https://github.com/lingshf/map-builder/pull/124#issuecomment-7234634573), which
also carries row 18 `overview`; row 18 `factoria-interchange` (with an extra `factoria-ponds`) is in the
[row 18 comment](https://github.com/lingshf/map-builder/pull/124#issuecomment-7234671174).

## Checklist

### G: gates (any fail is NO-GO)

| Row | Check | Pass rule | Result |
|---|---|---|---|
| G1 | G0 on H vs b04b769 | 4 presets × 2 paths × 2 styles = 16 cells: `.mbcol` and `.mbhf` bytes, georeference, probes, blocked and dropped lists equal | **pass**, 16/16 exit 0 |
| G2 | G0 negative cases | `tests/test_style_check.py` | **pass**, 26 tests OK |
| G3 | Classic identity | whole archive, 4 presets × 2 paths; CLI vs b04b769, Blender vs 656eab0 (D207) | **pass**, 8/8 byte-identical |
| G4 | Classic vs stylized members | only `visual/map.glb`, `manifest.json`, `report.json`, `NOTICES.txt` differ | **pass**, the same four members on every preset and path |
| G5 | Absolute budgets, stylized | ≤ 8 materials, 0 texture bytes, no glTF extensions, triangles per node equal to classic | **pass**, 7–8 materials, 0 bytes, none, equal |
| G6 | D139 budgets (STYLE-TUNE AC2) | per preset and path vs b04b769 stylized: materials ≤ 8, draws ≤, triangles =, render memory ≤, GLB size ≤, frame-time proxy ≤ +10 % | **pass**, every static metric **equal** on 8/8. Frame-time proxy on all 8 preset/path cells, `overview` camera, render-time ratio head/base (medians in ms): sample CLI 1.000 (19.3/19.3), Blender 0.985 (19.5/19.2); Munich CLI 1.026 (30.3/31.1), Blender 1.010 (31.1/31.4); Pittsburgh CLI 0.999 (149.4/149.3), Blender 1.001 (153.3/153.5); Factoria CLI 0.998 (164.7/164.4), Blender 0.992 (173.7/172.3). Setup in [`data/S6/d139-frame-time-proxy.json`](data/S6/d139-frame-time-proxy.json) (Edge headless, SwiftShader, 3 alternating pairs + 3 repeats) |
| G10 | Parity and determinism | `style_check.py parity` exits 0 on Munich, Pittsburgh and Factoria × 2 styles (D208); two builds of each cell byte-identical | **pass**, 6/6 parity exit 0; determinism 16/16. The sample also exits 0 in both styles (information, F3) |
| G11 | CI on the gate revision | green | **pass**, [run 46106950695](https://github.com/lingshf/map-builder/actions/runs/46106950695) |
| G12 | Headless Blender suite | `OK: 0 failure(s)` | **pass**, 32 s |
| G13 | Floating audit | `water_above_bank` 0, `water_buried` 0, shore step ≤ 1.5 m + 1 mm, 4 presets × 2 paths | **pass**, 8/8; max step 1.500 m |
| G14 | Readers on a fresh stylized sample | the same file: glTF-Validator 0 errors; current Python `VALID` and C# `OK`; frozen v0.3.0 Python `VALID` and C# `OK`; no warning beyond the committed sample | **pass**, all five; warnings identical to the committed sample. Archive SHA-256 `e9e356ba…9b19cd`, `options.style` = stylized |
| G15 | D200 merge records | every S6 merge has a review whose body starts `VERDICT: APPROVED` with `commit_id` equal to the merged PR head | **pass**, 9/9 (table below) |

| PR | Merged head | D200 review |
|---|---|---|
| #115 | `ea58179` | [6095121988](https://github.com/lingshf/map-builder/pull/115#pullrequestreview-6095121988) |
| #116 | `d9a918b` | [6095143515](https://github.com/lingshf/map-builder/pull/116#pullrequestreview-6095143515) |
| #117 | `3cc4e25` | [6095161441](https://github.com/lingshf/map-builder/pull/117#pullrequestreview-6095161441) |
| #118 | `29196ae` | [6095301708](https://github.com/lingshf/map-builder/pull/118#pullrequestreview-6095301708) |
| #119 | `ecd7bd0` | [6095272431](https://github.com/lingshf/map-builder/pull/119#pullrequestreview-6095272431) |
| #120 | `f26a6c3` | [6095289487](https://github.com/lingshf/map-builder/pull/120#pullrequestreview-6095289487) |
| #121 | `c7c49ea` | [6095329111](https://github.com/lingshf/map-builder/pull/121#pullrequestreview-6095329111) |
| #122 | `2d433b6` | [6095753569](https://github.com/lingshf/map-builder/pull/122#pullrequestreview-6095753569) |
| #123 | `8d98403` | [6095936518](https://github.com/lingshf/map-builder/pull/123#pullrequestreview-6095936518) |

### R: visual judgment (D137 order: looks good, low cost, fidelity)

The rule for (a)–(d) is the [pinned region map](../tasks/S6.md#pinned-region-map-for-ad) (D204): contrast pairs reach
after ΔE2000 ≥ 15 and after > before; swatch rows end closer to their target (after ΔE < before ΔE). The windows are
the D210 set (the #122 rectangles plus the D209 shore window). All 22 windows of the 14 comparisons were ray-checked
on both revisions: all pixel-centre rays hit the window's own surface (roof windows
`MB Roof`, wall windows `MB Facade`, road windows `MB Road`, land and grass windows terrain, water windows
`MB Water`, the shore window the `bank:` ramp), see [`data/S6/raycheck-windows.json`](data/S6/raycheck-windows.json).

| Row | Obs. | Camera: window | Before → after ΔE2000 | Result |
|---|---|---|---|---|
| R-a | Munich roofs vs walls | 4 `overview`: roof-1/wall-1 | 25.80 → 33.45 | **pass** |
| | | 7 `roofs`: roof-1/wall-1, roof-2/wall-2 | 20.44 → 35.79; 26.81 → 42.13 | **pass** |
| | | 8 `roofscape`: roof-1/wall-1, roof-2/wall-2 | 13.26 → 26.68; 26.76 → 41.65 | **pass** |
| R-b | Pittsburgh water | 9 `overview`: water-open `#6dc0e7` | 16.94 → 8.77 | **pass** |
| | | 13 `river-bend`: water-open `#6dc0e7`; water-shore `#ceeef6` (D209 window) | 15.39 → 8.63; 10.74 → 10.17 | **pass** |
| R-c | Factoria roads vs land | 1 `overview`: road-1/land-1 | 5.99 → 21.39 | **pass** |
| | | 2 `factoria-interchange`: road-1/land-1, road-2/land-2 | 4.11 → 17.76; 5.97 → 20.66 | **pass** |
| R-d | Grass | 16 `top`: grass-mid `#96b671`, grass-light `#b9d17a` | 14.91 → 10.74; 15.94 → 12.37 | **pass** |
| | | 10 `dsm-ground`: grass-mid `#96b671` | 15.47 → 10.04 | **pass** |
| R-all | No regression elsewhere | 3, 5, 6, 11, 12, 14, 15, 17 | judged from the sheets | **pass** (Design): roads now read as a warm terracotta network on every camera; water is lighter with a continuous shore band (3, 11); the confined views 5 and 6 are unchanged, with no black, inverted or cracked faces; trees keep shape and tint variants (17) |
| R7 | Main example for the user | 18 Factoria classic H \| stylized H | information | Stylized Factoria reads calmer and its road network is easy to trace from drone height. Classic still has the stronger building read: its red roofs stand out, while stylized buildings are pale beige close to the ground colour (see F6) |

**Priority statement (AC3, D137).** (1) Looks good: all four observations improved by the pinned rule, and roads and
water read clearly; the remaining weakness is pale Factoria buildings (F6). (2) Low cost: every D139 metric is
equal to v0.6.0 and the frame-time ratio is 0.9993. (3) Fidelity: collision and heightfield bytes and the protected
manifest fields are identical to v0.6.0 (G1); classic archives are byte-identical to their baselines (G3); stylized
GLBs keep the same per-node triangle counts as classic and the same draws and triangle totals as v0.6.0 (G5, G6).
Stylized visual geometry bytes were not compared separately.

**QA (AC4).** Independent QA, criterion by criterion:

| Row | QA record |
|---|---|
| R-a, R-b open water, R-c, R-d (13 of the 14 numeric rows) | [accepted on fresh renders](https://github.com/lingshf/map-builder/pull/122#issuecomment-7234136774); all 14 rows reproduced numerically, but the same comment withheld acceptance of the shore row pending a window check, since closed by D209 |
| R-b shore (D209) | [#122 shore row accepted at 4e51412](https://github.com/lingshf/map-builder/pull/122#issuecomment-7234470759); [#118 AC2 window accepted at 4e51412](https://github.com/lingshf/map-builder/pull/118#issuecomment-7234470758) |
| R-all | [accepted, one verdict per camera](https://github.com/lingshf/map-builder/pull/122#issuecomment-7234623961): no new face defects or bank gaps; confined shading and tree forms and tints preserved |

### T: test audit

| Row | Check | Result |
|---|---|---|
| T1 | S6 tests ≤ 5 s each, no wall-clock asserts, no duplicates | **pass**: 37 tests added (#119 12, #118 16, #121 3, #122 6) plus one Blender check; the four files run 89 tests in 3.9 s, slowest 0.95 s; no wall-clock assert in added lines |
| T3 | PR CI time ≤ 10 min | **pass**, 1 min 48 s |
| T4 | New S6 rules each have a test | **pass**: D207 classic factor (`checks_textures`, #119), scene-frame parity and its negative cases (`test_style_check.py`), paired ΔE and Pillow-free compose (`test_style_compare.py`), new palette values (`test_style_palette.py`), `--json` write errors (`test_floating_audit.py`) |

### F: findings (none blocks GO)

| Id | Finding | Disposition |
|---|---|---|
| F1 | #122 moved nine D204 rectangles in `palette_regions_factoria.json` and `palette_regions_munich.json` (Factoria interchange road-1, land-1, road-2, land-2; Munich roofs roof-2; roofscape roof-1, wall-1, roof-2, wall-2) outside its conflict domain and without a D-number (D198). With the #118 rectangles, the interchange pairs fail D204 (0.45 → 0.41, 10.38 → 10.37) because those windows sat on edges or the wrong surface; with the #122 rectangles every window is ray-verified on its surface (see R). Closed by **D210** (Team Leader decided): the #122 rectangles plus the D209 shore window are the pinned M-S6 windows; any later move needs a D-number and a ray check on both revisions, every ray on the window's surface, before merge. Recorded in the roadmap and the S6 region map. |
| F2 | The river-bend `water-shore` window had 3 of 25 rays on terrain (QA). | Closed by D209 (#123). |
| F3 | #122 and D208 say the sample has no Blender build. The sample does build on the Blender path through the S5 harness (`configure_sample`), and its CLI/Blender parity exits 0 in both styles; G1, G3 and determinism include it. | Sprint 7 planning: re-scope S7-SAMPLE-PARITY to making that harness pair the committed G10 cell, rather than building a new pair. |
| F4 | The Blender export writes a wall-clock `created_utc` (`map_builder/blender/export.py` does not pass one, so `core/package.py` falls back to `time.gmtime()`). Evidence uses the S5 harness pin; #122 left it out. Not a regression (S5 used the same pin). | Sprint 7 candidate: a pinnable `created_utc` on the Blender export path, so determinism does not depend on a test stub. |
| F5 | The D163 cache custody path no longer exists; two copies survive and are identical. | M-S6-RETRO item: record one custody location. |
| F6 | Row 18: stylized Factoria buildings are pale and close to the ground colour; classic reads buildings better. | Sprint 7 candidate (looks good): building contrast for low-rise areas, judged on Factoria. |
| F7 | Evidence hygiene: the render driver captured the recipe exit code for the first row only; every row produced all outputs with no traceback. | Information. |

## Verdict

**GO** for M-S6 on review head `4e51412`. Every G row passes, (a)–(d) pass the pinned D204 rule and are QA-accepted, R-all is QA-accepted, and D209 is closed. No S6-Fn task is opened. The findings go to M-S6-RETRO and Sprint 7 planning: F1 is closed by D210; F3, F4 and F6 are Sprint 7 candidates; F5 is a retro item. No release is cut (D202).
