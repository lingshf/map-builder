# S5-STYLE-REVIEW: checklist and camera set (prepared before the review)

Owner: design · task [S5-STYLE-REVIEW](../tasks/S5-STYLE.md#s5-style-review-design-milestone-review-gono-go) ·
decisions D137, D139–D141, D153, D156, D157, D163, D166, D170, D185–D194

This is the run sheet for the GO/NO-GO. It is fixed **before** the review, so the review can start as soon as
S5-PERF-WATER merges (D156). The review itself is a separate PR, `design/reviews/S5-STYLE-REVIEW.md`, which
fills in every row below with a verdict (pass / fail / information) and a link to its evidence.

## Gate to start

* S5-PERF-WATER is merged into main. Let **H** be the main commit at that point; the review pins H and does not
  move it.
* In scope: S5-STYLE-BASE (#85, fba2509), S5-F3 (#97, 8ce3d28), S5-F4 (#94, e780e02), S5-PERF-GATE (#91, 796d72b),
  S5-STYLE-PALETTE (#100, 4cb17fb), S5-STYLE-WATER (#103, 852a137), S5-PERF-WATER (H).
* The reference slot is waived for #100 and #103 (D187); R1 carries the judgment.
* Out of scope: S5-DECOR, deferred out of v0.6.0 (D185; draft #101 stays a draft). S5-F1, S5-F2 and
  DOC-USER-STRUCT are outside the M-S5 baseline (D170).

## Revisions and settings

| Role | Revision | Use |
|---|---|---|
| Visual **before** | `v0.5.0` = `6535f3845089cbeeb872e387ee477a3e42eecd6d` (the tag, #75), classic (the only mode there) | left column of every sheet: the **package** is built at this commit |
| Visual **after** | H, stylized (the default) | right column of every sheet |
| Render inputs (both sides) | H | the camera JSON, render recipe and region file of H are used for **both** columns (see Pinned render inputs) |
| After, classic | H with `--style classic` (Blender: the style property set to classic) | classic identity, plus the Factoria classic-vs-stylized pair (D157) |
| G0 and classic-identity base | 8ce3d28 (the D181 rebaseline target, classic) | byte checks |
| Per-PR budget bases | each PR's own merge-base (the per-PR rule in S5-STYLE.md) | taken from the PR evidence, not re-measured |

* **Build settings (G0 pinned):** the frozen caches from the D163 custody (Factoria: the D177 cache `065ca7fd…56ac` on both sides, per D190, because the D157 cache is lost;
  record the MANIFEST hashes you verified), seed 1, DSM on, offline, `created_utc = "2026-11-20T00:00:00Z"`, and the
  same export options on both sides.
* **Pinned render inputs.** v0.5.0 has no style presets, no re-framed ponds camera and no style render recipe.
  Each revision therefore only **builds its package**. Both columns are rendered by H's tools from H's files:
  `tools/demo/style_render_recipe.py`, `tools/demo/demo_bundle.py`, every preset JSON in the camera table, and
  `tools/demo/palette_regions_factoria.json`. The review extracts them from H once into one render tree, records
  the SHA-256 of each file, and passes the before and after packages to that same tree. Fixed render settings:
  `--engine CYCLES --samples 64 --seed 1` (no `--denoise`), 1280 × 720, with the lighting the recipe defines (one
  sun plus world ambient, D140 step 2). If headless EEVEE works, it may replace Cycles only if **both** columns
  use it; the review states the engine.
* The D140 limit of ≤ 2 min for all cameras is recorded as information only, because it applies to EEVEE.
* **Reference slot (D187, coordinator ruling in #104 R2):** the reference crop is not available as a file, so the
  R1 sheets are **two columns, before | after**, with no reference. The recipe cannot emit that today: its
  `--reference` is required, and its sheet step always draws three columns. It also skips sheets and the palette
  report when Blender's Python has no Pillow, which is the case for the pinned Blender 4.2.23. The review
  therefore uses the doc-only fallback below and changes no product code. If the coordinator supplies the crop
  as a file before the review, R1 judges it side by side with the two-column sheet.
* **Executable render run (fallback; PowerShell, from the H checkout).** `$H` is the full H SHA, `$W` a scratch
  directory outside the repo, and `$B`/`$A` hold the before and after `.mbmap` of each G0 package. System Python
  3.11 or newer with Pillow is required; record `py -c "import PIL; print(PIL.__version__)"`.
  1. Render tree: `New-Item -ItemType Directory "$W\tree" -Force; git archive --format=tar $H tools/demo map_builder | tar -x -C "$W\tree"`
     (`demo_bundle.py` imports `map_builder`, so `tools/demo` alone does not run). Then record
     `Get-ChildItem -Recurse -File "$W\tree\tools\demo" | Get-FileHash -Algorithm SHA256`.
  2. Placeholder (it only satisfies the required flag): `py -c "from PIL import Image; Image.new('RGB', (1280, 720)).save(r'$W\placeholder.png')"`.
  3. Per preset `P` in the camera table, with that preset's G0 package `G`:
     `& C:\tools\blender-4.2.23-windows-x64\blender.exe -b --factory-startup --python "$W\tree\tools\demo\style_render_recipe.py" -- --preset "$W\tree\tools\demo\presets\$P.json" --before "$B\$G.mbmap" --after "$A\$G.mbmap" --reference "$W\placeholder.png" --palette-regions "$W\tree\tools\demo\palette_regions_factoria.json" --out "$W\out\$P" --engine CYCLES --samples 64 --seed 1`.
     Keep `render-<camera>-before.png`, `render-<camera>-after.png` and `timing.json`. Delete any
     `contact-sheet-*.png` the recipe writes (they contain the placeholder) and never attach them.
  4. Two-column sheets and the ΔE report: save the script below as `$W\compose_two_column.py`, record its
     SHA-256, and run `py "$W\compose_two_column.py" "$W\tree" "$W\out\$P" "$W\tree\tools\demo\presets\$P.json" "$W\tree\tools\demo\palette_regions_factoria.json"`
     per preset. Pass any further region file a PR added (see Palette report) in an extra run with that file as
     the fourth argument. Output: `sheet2-<camera>.png` and `palette-<camera>.json` for cameras that have regions.
     The script reuses the recipe's own `_load_regions` and `_palette_report`, so ΔE is computed exactly as in
     #100.

  ```python
  import json, os, sys
  from PIL import Image, ImageDraw
  tree, out, preset, regions_file = sys.argv[1:5]
  sys.path.insert(0, os.path.join(tree, "tools", "demo"))
  import style_render_recipe as r  # bpy is imported only inside _render, so this runs outside Blender
  regions = r._load_regions(regions_file)
  for cam in [c["name"] for c in json.load(open(preset, encoding="utf-8"))["cameras"]]:
      before = Image.open(os.path.join(out, f"render-{cam}-before.png")).convert("RGB")
      after = Image.open(os.path.join(out, f"render-{cam}-after.png")).convert("RGB")
      assert before.size == after.size, cam
      (w, h), pad, label_h = before.size, 12, 28
      sheet = Image.new("RGB", (w * 2 + pad * 3, h + label_h + pad * 2), (28, 30, 36))
      draw = ImageDraw.Draw(sheet)
      for i, (label, img) in enumerate((("before (v0.5.0)", before), ("after (H)", after))):
          x = pad + i * (w + pad)
          draw.text((x, pad), label, fill=(235, 235, 235))
          sheet.paste(img, (x, pad + label_h))
      sheet.save(os.path.join(out, f"sheet2-{cam}.png"))
      mine = [g for g in regions if g.camera == cam]
      if mine:
          r._palette_report(os.path.join(out, f"render-{cam}-after.png"), mine, os.path.join(out, f"palette-{cam}.json"))
  ```

  Dry run of steps 1, 2 and 4 at main 852a137 with synthetic before/after PNGs (Design, #104 R2): three
  `sheet2-*.png` sheets and the three Factoria `palette-*.json` reports were produced.
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
| G4 | Classic vs stylized members on H | member diff | only `visual/map.glb`, the manifest `files[]` hashes and `package_id`, `asset_notices`/NOTICES, and `report.json` `style` differ. A member's `files[].hash` and `files[].bytes` may change together; the sample NOTICES 1867 → 1015 is intended (D192) |
| G5 | Absolute budgets on H, stylized | GLB inspection, 4 packages × 2 paths | materials ≤ 8 (the #100 QA rejection found 9); 0 embedded texture bytes; no glTF extensions; visual triangles per node equal to classic |
| G6 | Per-PR budgets | the D139 table of #100, #103 and PERF-WATER, each against its merge-base | every floor met, or a recorded decision covers the miss |
| G7 | D153 work gate | the PR evidence of #100, #103 and PERF-WATER | F1–F3 pass; F4 and F6 answered; F5 CPU disclosed |
| G8 | PERF-WATER output | the PERF-WATER PR | byte-identical output on all packages and paths, and its spec ACs closed in the PR. The AC3 counter shortfall is accepted (D188); the `may_touch` oracle check is evidence only (D189) |
| G9 | Frame-time proxy (D186a) | the PERF-WATER PR, [AC5](../tasks/S5-PERF-WATER.md) | AC5 as specified there: the proxy times render work (`median_render_ms`); C1 A/A on the Pittsburgh stylized package has `abs(ratio − 1) ≤ 0.03`; C2 (`--head-passes 2`, about +100 % render work) has `ratio ≥ 1.10`; the D139 pair (merge-base vs head, Pittsburgh stylized, overview) has `ratio ≤ 1.10`. If C1 or C2 failed, G9 fails (proxy not established) |
| G10 | Parity and determinism | `tools/style_check.py` parity; two builds of the same preset | CLI and Blender vertex colours and materials equal per node; two builds byte-identical. The Munich façade parity failure is pre-existing (v0.5.0, D181, H in both styles) and non-gating; it is a next-sprint bug (D191) |
| G11 | CI readers on the committed sample | CI on H | green. CI reads only the committed classic `examples/synthetic_sample.mbmap` and fixtures, so this row does not cover stylized output; G14 does |
| G14 | Readers on a **fresh stylized** sample | at H, build the sample with the CI build command (`.github/workflows/ci.yml`, "Build and validate the SYNTHETIC fixture package": `tools/mbmap_cli.py build` on `tests/fixtures/synthetic_area.osm` and `synthetic_dem.asc`) plus `--created-utc 2026-11-20T00:00:00Z` and the default style (stylized); confirm the style in `report.json`; record the archive SHA-256 | the **same file** passes all five: glTF-Validator 2.0.0-dev.3.10 (D66, `tools/gltf_validate.js`) on its `visual/map.glb` with 0 errors; the current Python validator (`tools/mbmap_cli.py validate`) `VALID`; the current C# reader (`examples/csharp/MbmapReader`) `OK`; the frozen v0.3.0 Python validator `VALID` and C# reader `OK` (`git archive v0.3.0`, as in CI), with no warnings beyond those they give on the committed sample. Raw outputs are attached |
| G12 | Full headless Blender suite (D166) | `tests/blender/run_integration.py` on H | `OK: 0 failure(s)` |
| G13 | Floating audit (WATER AC2) | `tools/floating_audit.py` on H, 4 packages × 2 paths | `water_above_bank` 0 and `water_buried` 0; max shore step ≤ 1.5 m + 1 mm |

### R: visual judgment (D137 order: looks good, low cost, fidelity)

| Row | Check | How it is judged | Pass rule |
|---|---|---|---|
| R1 | **Reference vs head** (D187) | Every after-render is judged against the S5-STYLE target table (sRGB swatches) and the user's direction: saturated, bright, readable from drone height, and a low-poly cartoon look. The palette ΔE report supports the judgment. The coordinator-held image is used if supplied (see Reference slot). | One verdict per priority, in D137 order: (1) looks good, (2) low cost (rows G5, G6 and G9), (3) fidelity (landcover keeps its class; objects stay in place, which G1 proves). A fail on (1) is NO-GO only if it is named against a specific camera and swatch. |
| R2 | **Faceting** (D186b) | Cameras 4, 5, 7, 8, 10, 12 and 17, after vs before. The method PALETTE picked (dropped `NORMAL` or unwelding) is named. | Faces read as flat, low-poly facets. No smooth-shading leftovers, no black or inverted faces, no seams that read as cracks, no shading acne on terrain or roofs. Anything found is named per camera and becomes an S5-Fn task. |
| R3 | **D163 ponds verdict** (D186f) | Camera 3 (the re-framed `factoria-ponds` from #100), rendered at H. | The southern Mercer Slough ponds (47.584–47.586° N, about +560 to +780 m northing) are visible as water, not a grey foreground: open water plus a shore band inside the frame, and the `water-shore` region falls on water. Since #109 (D194) that window is rows 408–413 on the water-adjacent bank ramp; the old D163 window, rows 419–424, must read sand. Design records its own verdict, and the review links an **independent QA verdict of accepted** on this camera at H. That QA verdict is required: it closes S5-STYLE-BASE `done` and is a GO precondition. A Design verdict alone, or a pending QA request, is not enough. |
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

* **GO** requires: every G row passes (G1–G14); R1 to R3 have verdicts with no named NO-GO finding; the
  independent QA verdict for R3 is **accepted** and linked (D186f); T1 to T4 pass.
* **Pending** (neither GO nor NO-GO): every other row passes, but the R3 QA verdict is not yet given. The review
  reports pending and asks QA. When QA accepts, the review becomes GO and S5-STYLE-BASE `done` closes. A QA
  rejection of the camera is a NO-GO with an S5-Fn camera task.
* **NO-GO** names each failing row, its evidence, and an S5-Fn fix task (id, conflict domain, and ACs), as for
  S4-REVIEW.
* After a GO, M-S5 continues with M-S5-RETRO (D169). S5-DECOR does not block it (D185).
