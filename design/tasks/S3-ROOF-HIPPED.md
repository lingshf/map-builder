# S3-ROOF-HIPPED: hipped roofs on non-rectangular footprints

Owner: dev · sprint S3 · wave 2 · depends on S3-SKELETON, S3-ROOF-CASES · D55, D61

## Scope

In `core/roofs.py`, route `roof:shape=hipped` on an eligible non-rectangular footprint (no
holes, ≤ 64 vertices) through `skeleton.straight_skeleton`.

* Lift each skeleton node to z = eave + t · (roof_h / t_max), so the highest node is exactly at
  eave + roof height.
* Add one planar face per skeleton face with `MB Roof`.
* Rectangles keep the existing analytic path, so their output stays byte-identical.
* On `SkeletonError` or `LimitError`, keep the v0.3.0 fallback and add the skeleton reason to
  `provenance.roof_shape`.
* Built roofs report `measured:hipped (straight skeleton)` or `inferred:…` as today.
* Pyramidal-on-convex stays as is.

## Acceptance criteria

1. Every eligible **hipped** case in `tests/test_roofs_munich.py` is built as tagged and passes
   `tests/roof_checks.py`.
2. Counterexamples keep their fallback, each with a named reason.
3. Rectangle cases are unchanged: the existing `test_roofs` tests pass, and
   `examples/synthetic_sample.mbmap` is unchanged unless the fixture gains a case.
4. The synthetic fixture gains one L-shaped hipped building (append-only, D20), covered by the
   existing Blender `tests/blender/checks_roofs.py` closure check. Run the headless Blender harness
   (`tests/blender/run_integration.py`): `OK: 0 failure(s)`.
5. The PR reports the Munich preset count (CLI, cached acquisition): tagged non-flat roofs built
   as tagged, before and after.

## Performance considerations

* Roof stage on Munich: ≤ +20 % of v0.3.0's roof stage plus the cost of new legal geometry,
  listed separately (D35).
* Fixture build: ≤ +2 % if the fixture is unchanged.
* Roof triangles stay below `MAX_ROOF_TRIANGLES`.
* Build medians are taken over 3 runs (D32).

## Conflict domain

Hard: `core/roofs.py`, `tests/test_roofs.py`, `tests/test_roofs_munich.py` (flip hipped cases).
Soft: `tests/fixtures/synthetic_area.osm`, `examples/synthetic_sample.mbmap`, VALIDATION.
Serialised with S3-ROOF-GABLED, which shares `roofs.py`.
