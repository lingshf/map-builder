# S3-REVIEW: sprint 3 milestone review and test audit

Owner: design · sprint S3 · after all S3 dev tasks merge · D63

Runs on main **before** REL-v0.4.0, following the D48 pattern. Its findings become `S3-Fn`
tasks, which are tagged as v0.4.0 blockers or later.

## Checks

1. **Roofs.**
   * Munich count of tagged non-flat roofs built as tagged is ≥ 40/67, or the D61 re-baseline,
     per shape.
   * `roof_checks.py` passes on all built cases.
   * Every remaining fallback has a named reason.
   * Spot renders of 3 complex footprints.
2. **Textures.**
   * The Pittsburgh and Munich CLI and Blender packages are strictly VALID with textures.
   * The C# reader loads them.
   * The GLB opens in the three.js viewer with textures visible.
   * Size versus v0.3.0 is within the D60 budget.
   * The licence file is present in the zip.
3. **Consumer.**
   * A 2.0-only reader path behaves as documented on 2.1, ignoring the textures.
   * The `.mbcol` bytes for the same input are unchanged by textures (on/off).
4. **Test audit.**
   * List the slowest tests.
   * No new test > 5 s.
   * No wall-clock gates.
   * The fixture build is re-measured against v0.3.0 (G6 style).
5. **Design conformance.**
   * The skeleton is isolated from OSM and Blender.
   * UVs are post-hoc and `generate.py` is untouched by the texture track.
   * There is no over-engineering, for example no speculative material system.
6. **Retro notes.**

## Deliverable

`design/reviews/S3-REVIEW.md` in one PR through the gate.

## Conflict domain

`design/` only.
