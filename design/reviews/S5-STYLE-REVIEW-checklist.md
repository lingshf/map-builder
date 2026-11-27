# S5-STYLE-REVIEW: checklist and camera set (prepared before the review)

Owner: design · task [S5-STYLE-REVIEW](../tasks/S5-STYLE.md#s5-style-review-design-milestone-review-gono-go) ·
decisions D137, D139–D141, D153, D156, D157, D163, D166, D170, D185–D187

This is the run sheet for the GO/NO-GO. It is fixed **before** the review, so the review can start as soon as
S5-PERF-WATER merges (D156). The review itself is a separate PR, `design/reviews/S5-STYLE-REVIEW.md`, which
fills in every row below with a verdict (pass / fail / information) and a link to its evidence.

## Gate to start

* S5-PERF-WATER is merged into main. Let **H** be the main commit at that point; the review pins H and does not
  move it.
* In scope: S5-STYLE-BASE (#85, fba2509), S5-F3 (#97, 8ce3d28), S5-F4 (#94, e780e02), S5-PERF-GATE (#91, 796d72b),
  S5-STYLE-PALETTE (#100, 4cb17fb), S5-STYLE-WATER (#103, 852a137), S5-PERF-WATER (H).
* Out of scope: S5-DECOR, deferred out of v0.6.0 (D185; draft #101 stays a draft). S5-F1, S5-F2 and
  DOC-USER-STRUCT are outside the M-S5 baseline (D170).

## Revisions and settings

| Role | Revision | Use |
|---|---|---|
| Visual **before** | `v0.5.0` (7b417db), classic (the only mode there) | left column of every sheet |
| Visual **after** | H, stylized (the default) | right column of every sheet |
| After, classic | H with `--style classic` (Blender: the style property set to classic) | classic identity, plus the Factoria classic-vs-stylized pair (D157) |
| G0 and classic-identity base | 8ce3d28 (the D181 rebaseline target, classic) | byte checks |
| Per-PR budget bases | each PR's own merge-base (the per-PR rule in S5-STYLE.md) | taken from the PR evidence, not re-measured |

* **Build settings (G0 pinned):** the frozen caches from the D163 custody (Factoria: the D157 cache, per D183;
  record the MANIFEST hashes you verified), seed 1, DSM on, offline, `created_utc = "2026-11-20T00:00:00Z"`, and the
  same export options on both sides.
* **Render settings:** `tools/demo/style_render_recipe.py` with the same engine, samples and seed for before and
  after. This host has no OpenGL, so the engine is Cycles CPU (the recipe default) unless EEVEE works headless;
  the review states the engine that was used. Each render is 1280 × 720. The D140 limit of ≤ 2 min for all cameras is
  recorded as information only, because it applies to EEVEE.
* **Reference slot (D187):** the reference crop is not available as a file. The sheets are therefore
  **before | after** only, and the reference judgment is row R1 below. If the coordinator supplies the crop as a
  file before the review, it goes into the reference slot, and R1 also judges it side by side.
* Sheets, renders and raw logs are attached to the review PR, not committed. Only small JSON or Markdown data may
  go under `design/reviews/data/`, as for S4-REVIEW.

## Camera set (every D140 camera)

D140 means the demokit presets of the four G0 packages, plus the five style cameras. Every camera is rendered
before and after. The 18 cameras are:

| # | Preset file (`tools/demo/presets/`) | Camera | What it is judged for |
|---|---|---|---|
| 1 | `bellevue-factoria.json` | `overview` | main visual example (D157): overall palette and readability from drone height |
| 2 | `bellevue-factoria.json` | `factoria-interchange` | style camera: roads, ramps and trees |
| 3 | `bellevue-factoria.json` | `factoria-ponds` | style camera and the **D163 ponds verdict** (row R3) |
| 4 | `munich-altstadt.json` | `overview` | buildings and roofs palette |
| 5 | `munich-altstadt.json` | `elevated-under` | elevated part: faceting, and no dark or inverted faces |
| 6 | `munich-altstadt.json` | `passage` | building passage: shading in a confined view |
| 7 | `munich-altstadt.json` | `roofs` | roof colours and faceting |
| 8 | `style-munich-roofscape.json` | `roofscape` | style camera: roofscape faceting (row R2) |
| 9 | `pittsburgh.json` | `overview` | sizing case: overall look, water and banks |
| 10 | `pittsburgh.json` | `dsm-ground` | terrain colours by landcover and slope (cliff faces) |
| 11 | `pittsburgh.json` | `bridge-under` | open water, shore band and sand under the deck (WATER, D186e) |
| 12 | `pittsburgh.json` | `tunnel-portal` | portal and hillside faceting |
| 13 | `style-pittsburgh-river-bend.json` | `river-bend` | style camera: open and shallow water, and the sand banks (D186e) |
| 14 | `synthetic.json` | `overview` | sample package: overall look |
| 15 | `synthetic.json` | `street` | sample: roads, footpaths and buildings at street level |
| 16 | `synthetic.json` | `top` | sample: plan view of the landcover colours |
| 17 | `style-sample-forest-edge.json` | `forest-edge` | style camera: tree tint variants, foliage facing and faceting |
| 18 | Factoria, H classic vs H stylized | `overview` and `factoria-interchange` | the D157 classic-vs-stylized pair shown to the user |

`sf-fidi.json` is not a G0 package and has no frozen cache, so it is excluded. #100 rendered 12 of these cameras.
Cameras 8, 13, 14, 15 and 16 are new in this review, and 17 was the only sample camera in #100.

**Palette report (D140 step 4):** fixed regions from `tools/demo/palette_regions_factoria.json`, which covers
cameras 1–3, plus any region file the PRs added for other presets. ΔE2000 is information only, and values above 15
are flagged. The review lists the flagged regions and says whether each is a palette problem or a region
misplacement.

## Checklist

### G: gates (any fail is NO-GO)

| Row | Check | Evidence | Pass rule |
|---|---|---|---|
| G1 | G0 on H vs 8ce3d28 | `tools/style_check.py`; 4 packages × 2 paths × 2 modes = 16 | 16/16 ok: `.mbcol` and `.mbhf` bytes, georeference, probes, blocked and dropped lists |
| G2 | G0 negative cases still fail | `tests/test_style_check.py` on H | each listed negative case fails |
| G3 | Classic identity (D141) | whole archive, H `--style classic` vs 8ce3d28, 4 packages × 2 paths | byte-identical, 8/8. The #100 QA rejection failed here on Blender (classic material factors), so the Blender column is required |
| G4 | Classic vs stylized members on H | member diff | only `visual/map.glb`, the manifest `files[]` hashes and `package_id`, `asset_notices`/NOTICES, and `report.json` `style` differ |
| G5 | Absolute budgets on H, stylized | GLB inspection, 4 packages × 2 paths | materials ≤ 8 (the #100 QA rejection found 9); 0 embedded texture bytes; no glTF extensions; visual triangles per node equal to classic |
| G6 | Per-PR budgets | the D139 table of #100, #103 and PERF-WATER, each against its merge-base | every floor met, or a recorded decision covers the miss |
| G7 | D153 work gate | the PR evidence of #100, #103 and PERF-WATER | F1–F3 pass; F4 and F6 answered; F5 CPU disclosed |
| G8 | PERF-WATER output | the PERF-WATER PR | byte-identical output on all packages and paths, and its spec ACs closed in the PR |
| G9 | Frame-time proxy sensitivity (D186a) | the PERF-WATER PR | the 150 ms proxy sensitivity proof is present and shows the proxy detects the stated change; the D139 proxy row then reads pass or fail, not "not established" |
| G10 | Parity and determinism | `tools/style_check.py` parity; two builds of the same preset | CLI and Blender vertex colours and materials equal per node; two builds byte-identical |
| G11 | Validators and readers | CI on H; a glTF-Validator run on the stylized sample | glTF-Validator (D66), the Python validator, the C# reader and the frozen v0.3.0 readers accept it |
| G12 | Full headless Blender suite (D166) | `tests/blender/run_integration.py` on H | `OK: 0 failure(s)` |
| G13 | Floating audit (WATER AC2) | `tools/floating_audit.py` on H, 4 packages × 2 paths | `water_above_bank` 0 and `water_buried` 0; max shore step ≤ 1.5 m + 1 mm |

### R: visual judgment (D137 order: looks good, low cost, fidelity)

| Row | Check | How it is judged | Pass rule |
|---|---|---|---|
| R1 | **Reference vs head** (D187) | Every after-render is judged against the S5-STYLE target table (sRGB swatches) and the user's direction: saturated, bright, readable from drone height, and a low-poly cartoon look. The palette ΔE report supports the judgment. The coordinator-held image is used if supplied (see Reference slot). | One verdict per priority, in D137 order: (1) looks good, (2) low cost (rows G5, G6 and G9), (3) fidelity (landcover keeps its class; objects stay in place, which G1 proves). A fail on (1) is NO-GO only if it is named against a specific camera and swatch. |
| R2 | **Faceting** (D186b) | Cameras 4, 5, 7, 8, 10, 12 and 17, after vs before. The method PALETTE picked (dropped `NORMAL` or unwelding) is named. | Faces read as flat, low-poly facets. No smooth-shading leftovers, no black or inverted faces, no seams that read as cracks, no shading acne on terrain or roofs. Anything found is named per camera and becomes an S5-Fn task. |
| R3 | **D163 ponds verdict** | Camera 3 (the re-framed `factoria-ponds` from #100). | The southern Mercer Slough ponds are visible as water, not a grey foreground: open water plus a shore band inside the frame, and the `water-shore` palette region falls on water. If QA has already given an accepted verdict, link it. Otherwise the review records its own verdict and asks QA for one, because D163 needs a QA verdict to close S5-STYLE-BASE `done`. |
| R4 | Water and shore (D186e) | Cameras 9, 11 and 13. | Open water reads cyan; a light shore band blends into sand; water and bank edges show no gaps. Colour only: G1 holds. |
| R5 | Trees | Cameras 2 and 17. | Tint variants are deterministic, and the lit, mid and shadow faces are distinguishable. The shape is unchanged (D145). |
| R6 | Buildings and roads | Cameras 4, 6, 7, 15 and 2. | Pastel walls and saturated roofs, with tagged colours pulled into the palette. Roads are light warm grey; footways and paths are sand. |
| R7 | Main example (D157) | Camera 18 pair, classic vs stylized. | A short statement for the user on how Factoria reads against the three priorities. |

### N: carry-overs recorded, not gating

| Row | Item | Record |
|---|---|---|
| N1 | Grass paleness (D186c) | Note the observed grass ΔE values. Non-blocking; an S5-Fn tuning item if the reviewer proposes one. |
| N2 | Rock (D186d) | Not judged. Deferred to S5-F2. |
| N3 | Cumulative S5 drift | Every D139 row on H vs the BASE classic baseline and vs PALETTE's stylized baseline. Information only. |
| N4 | Untextured and stylized timing | Report D147 CPU medians (F5) as disclosed in the PRs. Information only (D153). |

### T: test audit (D134)

| Row | Check | Pass rule |
|---|---|---|
| T1 | New tests from #100, #103 and PERF-WATER | each ≤ 5 s, no wall-clock asserts, no case duplicated across the water, shore and floating-audit test files |
| T2 | Persisted vs evidence | real-data audits and replays are PR evidence, not persisted tests |
| T3 | PR CI time on H | ≤ 10 min |
| T4 | Coverage of the S5 rules | palette rules (slope threshold, bank band, road classes, pulled tagged colour, tree tint), classic sample identity, the Blender style-option default, and the G0 negative cases each have at least one test |

## Verdict

* **GO** requires: every G row passes; R1 to R3 have verdicts with no named NO-GO finding; T1 to T4 pass.
* **NO-GO** names each failing row, its evidence, and an S5-Fn fix task (id, conflict domain, and ACs), as for
  S4-REVIEW.
* After a GO, M-S5 continues with M-S5-RETRO (D169). S5-DECOR does not block it (D185).
