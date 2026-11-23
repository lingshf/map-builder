# REL-v0.5.0: release candidate for sprint 4

Owner: release manager · sprint S4 · after S4-REVIEW, S4-WATER-BANK, S4-COL-FLOAT, S4-COL-FLOAT-2 and S4-MYPY · D28, D32, D50, D53, D104, D126, D128, D130

## Scope

Same shape as REL-v0.4.0:

* version 0.5.0 through the D50 drift guard;
* CHANGELOG, user docs and flows;
* `docs/demo/v0.5.0/`, with before/after renders against v0.4.0 for roofs, the river (colour and the S4-WATER-SURFACE flat surface, Pittsburgh demokit cameras) and one collision probe;
* `docs/releases/v0.5.0.md`.

## Acceptance criteria

1. Real-data builds of Munich and Pittsburgh through the CLI **and** headless Blender, VALID (D53.1). The only
   allowed warnings are degenerate-triangle warnings for triangles kept under D98, each listed in the
   S4-COL-DEGEN report and disclosed in the release notes; counts are below the v0.4.0 baseline.
   The probe gates match S4-REVIEW checks 2 and 3: the D98 hit equivalence holds on S4-COL-DEGEN's own base →
   head comparison (D111). Every S4-WATER-SURFACE fixed-query difference is in its listed change set (new
   `water` hits, moved bed, raised decks, extended piers or walls). Every base passage id survives
   unless it is listed as dropped with its reason, and every survivor is passable on its regenerated path. Any other warning, or an unlisted degenerate, blocks the RC. The C# reader passes the same probes. Build time is the median of 3 (D32).
2. The release notes state:
   * the roof count against the floor and the stretch, per shape, with the remaining named reasons;
   * the degenerate-triangle counts before and after per package and path, and the kept triangles (D98);
   * the water fix: the neutral texture (S4-TEX-WATER) and the flat water surfaces on carved beds (S4-WATER-SURFACE, D112),
     with the new class-5 `water` hits in `.mbcol` and the note that `.mbhf` shows the riverbed (D117);
   * the performance numbers against v0.4.0 (D91);
   * that the format is unchanged at 2.1.0, with a link to the stability policy (draft, D101);
   * the extension reproducibility;
   * the user actions still open (platform submission, D101/D102 confirmation).
3. The extension zip built in CI from the tag matches a local clean build from the same commit (D100).
4. The frozen-input reproduction in the RC matches the asset SHA-256 of at least one package.
5. Assets: the extension zip, the Munich and Pittsburgh `.mbmap` from the CLI (and the Blender candidates), the
   renders, and the viewer capture.
6. **Floating collision (D126).** `tools/floating_audit.py` on every release package, CLI and Blender: 0 floating,
   0 `water_above_bank` and 0 `water_buried` regions above 0.2 m. The notes state the remaining `water_shore_step`
   count and maximum (≤ 1.5 m) and describe the new `bank:<id>` terrain objects.
7. **Typing (D128).** The VALIDATION row says mypy-clean with CI enforcement only after S4-MYPY has merged; before
   that, no mypy claim.
8. **Final RC (D130).** The RC is rebased on the final main after S4-MYPY; every package, render and checksum is
   rebuilt from it, and the RC's `design/` hunk is dropped (D125). Tagging and publishing stay a separate user
   decision.

## Conflict domain

Version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.5.0/`, `docs/releases/v0.5.0.md`,
`docs/DEMO.md`. Runs alone.
