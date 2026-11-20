# S3-ROOF-HIPPED: hipped roofs on non-rectangular footprints

Owner: dev · sprint S3 · wave 2 · depends on S3-SKELETON, S3-ROOF-CASES · D55, D61, D64

## Roof pipeline order (must be kept)

The decision, the budget reservation and the emission are three separate steps in
`build_building`. The outcome is fixed **before** any mesh is allocated:

1. **Preflight.** `roofs.resolve_shape` (`generate.py:446`) is replaced by `roofs.plan_roof`. It
   returns a `RoofPlan`:
   * `shape_built`;
   * the lifted skeleton faces already **triangulated**;
   * the exact `(extra_vertices, extra_triangles)`;
   * the `roof_shape` provenance string.

   For `hipped` on an eligible non-rectangular footprint it runs `skeleton.straight_skeleton`
   **here**. A `SkeletonError` or `LimitError` is caught here and turned into the v0.3.0
   fallback (pyramidal if convex, else flat), with the skeleton reason appended to
   `prov["roof_shape"]`. Rectangles keep the analytic path; their plan has no skeleton.
2. **Reservation.** `roofs.roof_budget(plan, n_ring)` (`generate.py:533`) returns the plan's
   exact counts, so `reserve(...)` is called with what will actually be emitted. A new test
   asserts reserved == emitted vertices and triangles for every skeleton case.
3. **Emission.** `roofs.build_roof(mesh, plan, ...)` (`generate.py:574`) only emits the plan.
   It cannot change the shape. `prov["roof_shape_built"]` (`generate.py:580`) is set from
   `plan.shape_built`, so the recorded outcome is the actual one.

**Triangulation.** Skeleton faces can be concave, for example at a reflex corner, but
`MeshData` and the GLB writer fan every face from its vertex 0. Each lifted skeleton face is
therefore projected onto its own plane and triangulated with `core.triangulate.triangulate`, the
footprint triangulator. The face is emitted as explicit triangles; it is never passed to
`add_planar_face` as one polygon. Its triangles count against `MAX_ROOF_TRIANGLES` and the
plan's budget.

Lifting: z = eave + t · (roof_h / t_max), so the highest node is exactly at the expected top.

## Acceptance criteria

1. Every eligible **hipped** case in `tests/test_roofs_munich.py` is counted by
   `built_as_tagged` (geometry, on emitted triangles) and passes `tests/roof_checks.py`. The
   test's asserted count rises accordingly; report it before and after, out of 67.
2. Counterexamples keep a named fallback. The concave-face counterexample is built as hipped
   and passes the overlap and gap checks.
3. Reserved == emitted (step 2 test), and `roof_shape_built` == `plan.shape_built` for all 67.
4. Rectangle cases and the synthetic sample are **byte-identical** (`test_examples` sample
   check unchanged). The task does not edit `tests/fixtures/synthetic_area.osm` or
   `examples/synthetic_sample.mbmap` (D64).
5. Roof harness edits in `tests/blender/checks_roofs.py`:
   * add a scratch-OSM L-shaped hipped house, written like `UNSUPPORTED_OSM`, not in the shared
     fixture;
   * assert Blender equals Python, 1 mm on vertices;
   * add the hipped signature, closed manifold and outward winding checks;
   * update the module docstring.

   Then run `tests/blender/run_integration.py`: `OK: 0 failure(s)`.

## Performance considerations

* The roof stage is measured on the **frozen** snapshot `tests/fixtures/munich_roofs.osm`. Build
  it at tag `v0.3.0` (eb134a1) and at the PR head on the same machine and take the median of 3
  runs (D32). The budget is ≤ +20 % of the v0.3.0 stage plus the cost of the new legal
  geometry, listed separately (D35).
* The fixture build, with the sample unchanged, stays within ≤ +2 %.
* At most one skeleton per building, computed in the preflight only.

## Conflict domain

Hard: `core/roofs.py`, `core/generate.py` (building roof section only: lines ~446–580, the
`plan_roof` / `roof_budget` / `build_roof` call sites), `tests/test_roofs.py`,
`tests/test_roofs_munich.py`, `tests/blender/checks_roofs.py`. Soft: `docs/VALIDATION.md` (own
row). Serialised with S3-ROOF-GABLED. No other S3 task edits `generate.py` (D59).
