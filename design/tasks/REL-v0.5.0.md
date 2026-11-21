# REL-v0.5.0: release candidate for sprint 4

Owner: release manager · sprint S4 · after S4-REVIEW and its blocker S4-Fn tasks · D28, D32, D50, D53, D104

## Scope

Same shape as REL-v0.4.0:

* version 0.5.0 through the D50 drift guard;
* CHANGELOG, user docs and flows;
* `docs/demo/v0.5.0/`, with before/after renders against v0.4.0 for roofs, the river (colour and the S4-WATER-SURFACE flat surface, Pittsburgh demokit cameras) and one collision probe;
* `docs/releases/v0.5.0.md`.

## Acceptance criteria

1. Real-data builds of Munich and Pittsburgh through the CLI **and** headless Blender, VALID (D53.1). The only
   allowed warnings are degenerate-triangle warnings for triangles kept under D98, each listed in the
   S4-COL-DEGEN report and disclosed in the release notes; counts are below the v0.4.0 baseline and the D98
   probe set is unchanged apart from the water-surface hits that S4-WATER-SURFACE lists (D116). Any other warning, or an unlisted degenerate, blocks the RC. The C# reader passes the same probes. Build time is the median of 3 (D32).
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

## Conflict domain

Version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.5.0/`, `docs/releases/v0.5.0.md`,
`docs/DEMO.md`. Runs alone.
