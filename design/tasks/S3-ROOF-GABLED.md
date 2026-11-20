# S3-ROOF-GABLED: gabled roofs on non-rectangular footprints

Owner: dev · sprint S3 · wave 3 · depends on S3-ROOF-HIPPED · D55, D61, D64

## Scope

Gabled = the hipped skeleton with the hip faces of **gable-end edges** turned into vertical
gable walls. Everything happens inside `roofs.plan_roof`, the preflight defined in
S3-ROOF-HIPPED, so reservation and provenance stay exact.

* **Gable-end edges** are footprint edges whose skeleton face is a triangle at a ridge end.
  They are chosen by `roof:orientation` (along/across), then by `roof:direction` if tagged,
  otherwise by the existing rectangle rule generalised to the minimum-area bounding rectangle.
* **Conversion.** Move the ridge-end node vertically above the gable edge, onto the edge's
  vertical plane. Re-lift the adjacent sloped faces, which must stay planar and must not
  self-intersect. Emit the gable as explicit `MB Facade` triangles (vertical), and triangulate
  the sloped faces as in S3-ROOF-HIPPED.
* **Fallback.** If a gable end is not representable (for example at a reflex ridge end), the
  plan becomes the **hipped** skeleton roof, with
  `prov["roof_shape"] = "fallback:hipped (gable end not representable: …)"`. It is decided in
  the preflight, before reservation; `roof_shape_built = "hipped"`.
* **Unchanged.** Half-hipped, gambrel, mansard, round and saltbox stay rectangle-only (later).

## Acceptance criteria

1. Every eligible **gabled** case is counted by `built_as_tagged` (gabled signature on emitted
   triangles: at least 2 vertical gable ends whose base lies on footprint edges). If it is not
   counted, it is built hipped with the named fallback, and its geometry passes the hipped
   checks. Report both counts.
2. **Sprint roof target (D61).** The geometry-based count over **all 67** snapshot roofs is
   **≥ 40**, or the re-baselined target. It is enforced as a count in
   `tests/test_roofs_munich.py`. The live Munich preset count (CLI, current acquisition) is
   reported in the PR for information; it is not gated.
3. A `roof:direction` counterexample builds its ridge perpendicular to the tagged direction,
   checked on the emitted ridge edge.
4. Reserved == emitted, and `roof_shape_built` == `plan.shape_built`, for all 67 and for the
   counterexamples.
5. Rectangle cases and the synthetic sample are byte-identical (D64).
6. Roof harness edits in `tests/blender/checks_roofs.py`:
   * add a scratch-OSM L-shaped gabled house;
   * assert Blender equals Python;
   * check that the gable ends are vertical `MB Facade` and the mesh is closed.

   Then run `run_integration.py`: `OK: 0 failure(s)`.

## Performance considerations

As for S3-ROOF-HIPPED. Measure on the frozen snapshot at `v0.3.0` versus the head, median of 3
runs. The budget is roof stage ≤ +20 % plus the new legal geometry listed separately. Each
building runs at most one skeleton plus one gable conversion. New tests ≤ 5 s each.

## Conflict domain

Hard: `core/roofs.py`, `core/generate.py` (roof section only, if the call sites change),
`tests/test_roofs.py`, `tests/test_roofs_munich.py`, `tests/blender/checks_roofs.py`. Soft:
`docs/VALIDATION.md` (own row). After S3-ROOF-HIPPED.
