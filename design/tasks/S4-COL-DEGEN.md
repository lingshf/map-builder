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

## Scope (D98)

Drop zero-area triangles at collision bake in both paths, with the same predicate as the validator
(`is_degenerate`). The generator's export check asserts zero. The validator keeps the warning for third-party
packages.

## Acceptance criteria

1. The sample and the Munich and Pittsburgh packages, from both the CLI and headless Blender, validate with
   **0 degenerate triangles** and no warnings, or the PR lists any other warning that remains.
2. **Collision equivalence:** on Pittsburgh, every passage probe and an in-test grid of rays and capsules (for
   example 10 k rays over the sample) give identical hit results before and after, in Python and in the C#
   reader (D47). The probes are the same ids and all pass.
3. Tube, open-tube and surface-orientation rules still pass (existing `.mbcol` traversal tests).
4. If a whole object would be left with no triangles, it is dropped with a report entry, never written empty.
5. Sample regenerated (D103), with the byte change listed in the PR.

## Performance considerations

One extra cross product per triangle at bake, which is negligible. Report whole Generate (D91).

## Expected tests

`tests/test_collision*.py` (predicate parity with the validator, empty-object case), ray/capsule equivalence on
the sample (≤ 5 s), `tests/blender/checks_*` export assertion.

## Conflict domain

Hard: `core/collision.py`, `blender/bake.py`, `blender/export.py` (degenerate handling only), the collision
tests. Soft: sample (D103), VALIDATION rows. Serialised after S4-BLENDER-HYGIENE.
