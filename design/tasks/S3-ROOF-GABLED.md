# S3-ROOF-GABLED: gabled roofs on non-rectangular footprints

Owner: dev · sprint S3 · wave 3 · depends on S3-ROOF-HIPPED · D55, D61

## Scope

Gabled = hipped skeleton with the hip faces of **gable-end edges** turned into vertical gable
walls.

* **Gable-end edges.** These are the footprint edges whose skeleton face is a triangle at the
  end of a ridge. Pick them by `roof:orientation` (along/across), then by
  `roof:direction`/`roof:ridge:direction` if tagged, otherwise by the existing rectangle rule
  generalised to the minimum-area bounding rectangle.
* **Turning a hip into a gable.** Move the ridge-end node vertically above the gable edge, by
  projection onto the edge's vertical plane. Then re-lift the adjacent sloped faces, which must
  stay planar, and emit the gable triangle as `MB Facade`, vertical.
* **When the gable cannot be made.** This happens if projecting would make a sloped face
  non-planar or self-intersecting, for example on a reflex ridge end. In that case the building
  falls back to the **hipped** skeleton roof, reporting
  `fallback:hipped (gable end not representable: …)`. It does not fall back to flat.
* **Shapes not covered.** Half-hipped, gambrel, mansard, round and saltbox stay rectangle-only
  (later).

## Acceptance criteria

1. Every eligible **gabled** case in `tests/test_roofs_munich.py` is either built as tagged
   (passes `roof_checks.py`, with vertical gable ends) or uses the named hipped fallback. Give
   both counts.
2. **Sprint roof target (D61):** on the Munich preset, the count of tagged non-flat roofs built
   as tagged is **≥ 40 of 67**, up from 5, or the re-baselined target from S3-ROOF-CASES.
   Measure it with the CLI on the cached acquisition, and report it per shape. The offline
   excerpt test enforces the same number of built-as-tagged cases as a count (not a time).
3. A `roof:direction` counterexample: one excerpt with a tagged direction builds its ridge
   perpendicular to that direction.
4. The synthetic fixture gains one L-shaped gabled building (append-only), and the headless
   Blender `checks_roofs` passes on it.
5. Rectangle cases are unchanged.

## Performance considerations

As for S3-ROOF-HIPPED: roof stage ≤ +20 % plus new geometry listed separately; at most one
extra skeleton per building. New tests ≤ 5 s each.

## Conflict domain

Hard: `core/roofs.py`, `tests/test_roofs.py`, `tests/test_roofs_munich.py`. Soft: fixture OSM,
sample, VALIDATION. After S3-ROOF-HIPPED.
