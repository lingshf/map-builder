# REL-v0.6.0: release candidate for sprint 5 (stylized look)

Owner: release manager · sprint S5 · after S5-STYLE-REVIEW GO (850a772, D194) · D17, D28, D32, D50, D53, D98, D100, D126, D128, D133, D185, D191

Carried from [REL-v0.5.0](REL-v0.5.0.md) and the common [sprint close](SPRINT_CLOSE.md) definition, adapted to the
sprint-5 deliverable. The RC is [#111](https://github.com/lingshf/map-builder/pull/111).

## Scope

* version 0.6.0 through the D50 drift guard;
* CHANGELOG, user docs and flows (the new **Content > Style** option and the CLI `--style` flag);
* `docs/demo/v0.6.0/`: classic-vs-stylized sheets from identical cameras (two columns, no reference, D187), the
  Blender panel screenshot and the viewer captures;
* `docs/releases/v0.6.0.md`.

## Acceptance criteria

1. **Builds (D53.1).** Stylized (default) builds of Munich, Pittsburgh and Bellevue-Factoria through the CLI **and**
   headless Blender are VALID. The only allowed warnings are degenerate-triangle warnings for triangles kept under
   D98, with counts per package and path. The C# reader passes the same passage probes (Munich 3/3, Pittsburgh 11/11,
   Factoria 43/43). Build time is the median of 3 (D32).
2. **Gates.** The RC's product code equals the S5-STYLE-REVIEW GO revision (850a772) apart from the version files;
   otherwise every [checklist](../reviews/S5-STYLE-REVIEW-checklist.md) gate (G1–G14, R, T) is re-run on the RC head.
   G10 (Munich façade parity) is non-gating under D191 and disclosed.
3. **Release notes** state:
   * the default look change, how to get the classic look (`--style classic`, Content > Style), and that flight
     data (`.mbcol`, `.mbhf`, georeference) is identical between styles (G0);
   * the GLB size and material counts against v0.5.0, and the stylized GLB's missing `NORMAL` attribute (flat shading);
   * that `package_id` changes with the style, and the format version and its stability policy link (D101);
   * the known looks limits found by STYLE-REVIEW and the deferred items: S5-DECOR (D185), #106 (D191), the
     PERF-WATER AC3 counters (D188), and the carried degenerates (D98/D111);
   * the licence split (D13) and OSM/Copernicus attribution.
4. **Extension reproducibility (D100).** The extension zip built in CI from the tag matches a local clean build from
   the same commit.
5. **Release assets.** The assets are the extension zip, the stylized Munich, Pittsburgh and Bellevue-Factoria
   `.mbmap` (CLI) and their `.glb`, the renders, the viewer zip and `NOTICES.txt` (SPRINT_CLOSE). Every shipped package
   is built from the tag and is VALID with the Python validator and the C# reader (probes as in AC1). At least one
   matches a frozen-input rebuild. The tag-time SHA-256 of every asset is in the release body. Evidence builds made
   before the version bump are labelled as such.
6. **Demo (D17, SPRINT_CLOSE).** `docs/demo/v0.6.0/` contains:
   * `panel.png`: the Map Builder panel with **Content > Style** visible;
   * 2–3 feature examples, each with input area, command and before|after renders from identical cameras;
   * `viewer-munich.png` and `viewer-pittsburgh.png`: the bundled three.js viewer showing the stylized GLBs, plus the
     viewer bundle (shipped as the release viewer zip);
   * a `summary.md` per preset or an equivalent summary in the demo README, and `evidence.json` with the commit,
     build command, caches and per-package hashes;
   * the demo README and the release notes link the panel screenshot, the sheets and the viewer captures.

   **Demo check (SPRINT_CLOSE step 2):** the demo commands and assets reproduce on the RC merge.
7. **Floating collision (D126).** `tools/floating_audit.py` on every RC build (CLI and Blender) and on every shipped
   tag-built package: 0 floating,
   0 `water_above_bank` and 0 `water_buried` regions above 0.2 m.
8. **Typing (D128).** mypy is clean and CI-enforced on the RC head.
9. **Final RC (D133).** No `design/` hunk in the RC (D125). It merges through the D133 gate (exact-head approval,
   green CI, mergeability, coordinator authorization) after the PO review is ACCEPT. Tagging and publishing stay a
   separate user decision.

## Conflict domain

Version files (`map_builder/__init__.py`, `map_builder/core/__init__.py`, `map_builder/blender_manifest.toml`),
`CHANGELOG.md`, `README.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.6.0/`, `docs/releases/v0.6.0.md`,
`docs/DEMO.md`, `docs/PACKAGE_FORMAT.md`, `docs/VALIDATION.md`, `examples/README.md`, and the D103 sample slot
(`examples/synthetic_sample.mbmap`).
Runs alone, after S5-STYLE-REVIEW GO.
