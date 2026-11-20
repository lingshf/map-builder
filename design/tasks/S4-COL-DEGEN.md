# S4-COL-DEGEN: no degenerate collision triangles from either path

Owner: dev · sprint S4 · lane B · after S4-BLENDER-HYGIENE · D4, D98 · closes S3-F12

## Background (measured)

The validator warns "collision has N degenerate (zero-area) triangles":

| Package | CLI | Blender |
|---|---|---|
| synthetic sample | 2 | — |
| Munich | 59 | 58 |
| Pittsburgh | 76 | 78 |

`count_degenerate` exists in `core/collision.py`, and Blender already counts them per object
(`blender/bake.py:193`, `blender/export.py:489`).

**The validator's predicate is not a miss predicate.** `is_degenerate` uses an area epsilon. A 1 mm right
triangle is classified degenerate, yet the watertight ray through its interior hits it at t = 1.0 (review of
#59). Dropping every validator-degenerate triangle can therefore change query results, and "zero-area
triangles never hit" must not be claimed.

## Scope (D98)

1. **Measure first.** On f8bedf6, for every validator-degenerate triangle in the sample and both presets (both
   paths): its source (which builder and polygon), its exact area in float64, and whether a ray through its
   centroid hits it in the Python query and in the C# reader. Record the table (counts by source; hit-capable
   vs not) in the PR before any change.
2. **Remove at the source.** Drop collinear and duplicate ring vertices before triangulation and
   re-triangulate, so the covered surface is unchanged and no sliver is emitted. Do not filter triangles after
   the fact with the validator epsilon.
3. A triangle that cannot be removed without changing a hit on the probe set (below) stays, and is listed by
   object and reason in the build report. Dropping it anyway is a disclosed query change that needs the
   coordinator's explicit acceptance.
4. The validator keeps the warning for third-party packages, with no predicate change.

## Acceptance criteria

1. **Near-degenerate counterexample test:** the 1 mm right triangle (validator-degenerate, hit at t = 1.0)
   is pinned as a unit test, so a later change to either predicate is caught.
2. **Measured hit equivalence (D98)** on a fixed probe set, before and after, in Python and in the C# reader
   (D47): (a) every passage probe (same ids, all pass); (b) a deterministic ray and capsule grid (seeded, for
   example 10 k rays over the sample and a fixed subset over each preset); (c) one ray through the centroid of
   every triangle that was validator-degenerate before. Hit/miss identical, hit distance within 1e-6 m, class
   identical. The probe set and both result tables are in the PR. Any difference blocks the PR unless the
   coordinator explicitly accepts it as a disclosed change.
3. **Counts (must):** fewer validator-degenerate triangles than the baseline (sample 2; Munich 59 CLI / 58
   Blender; Pittsburgh 76 / 78) in every package and path, with each remaining one listed. **Aim:** 0.
4. Tube, open-tube and surface-orientation rules still pass (existing `.mbcol` traversal tests).
5. If a whole object would be left with no triangles, it is dropped with a report entry, never written empty.
6. Sample regenerated in the exclusive merge-time sample slot (D103), with the byte change listed in the PR.
7. Consumer: the simulator repo is read-only. The PR reports the in-repo C# replay; it does not claim a
   simulator import or visual check (a separate user/simulator-owner action).

## Performance considerations

One extra cross product per triangle at bake, which is negligible. Report whole Generate (D91).

## Expected tests

`tests/test_collision*.py` (predicate parity with the validator, empty-object case), ray/capsule equivalence on
the sample (≤ 5 s), `tests/blender/checks_*` export assertion.

## Conflict domain

Hard: `core/collision.py`, `blender/bake.py`, `blender/export.py` (degenerate handling only), the collision
tests. Soft: sample (D103), VALIDATION rows. Serialised after S4-BLENDER-HYGIENE.
