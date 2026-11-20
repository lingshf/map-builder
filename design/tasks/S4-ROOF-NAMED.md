# S4-ROOF-NAMED: every uncounted roof has a named reason; roof-checker robustness

Owner: dev · sprint S4 · lane A · D95, D103 · closes S3-F1, S3-F7, S3-F8, S3-F9

## Background

Baseline (f8bedf6): 29/67 counted, and 34 of the 38 uncounted roofs carry a named reason in
`provenance.roof_shape`. The 4 analytic near-rectangle gables fail the checker's `planar` test and say only
`measured:osm roof:shape` (S3-F1). Related follow-ups:

* S3-F7: planarity uses the largest triangle as its reference plane, which can warp the verdict.
* S3-F8: the way-9007 fixture is sensitive to near-axis rounding.
* S3-F9: the legacy reservation bounds are loose.

## Scope

1. Fix the reference-plane warp (S3-F7) in the **builder**: for example, build the analytic gable so that
   each slope is exactly planar. A roof that then passes the unchanged checker is counted.
2. Any analytic gable that still fails gets a named reason in provenance. The fallback is decided in the
   `plan_roof` preflight (D64), not after emission.
3. Make the 9007 fixture robust: tolerance-aware comparison, or a perturbation test on both sides of the axis.
4. Tighten the legacy reservation bounds to the emitted geometry, plus a documented margin. Budget accounting
   must not undercount.

## Acceptance criteria

1. **Must:** `tests.test_roofs_munich` asserts the **floor ≥ 29** counted and that **every** roof that is still
   uncounted has a non-empty named reason (baseline 34 of 38; the test iterates over the uncounted set, not a
   fixed 38). **Aim:** the 4 analytic gables become counted through the planar-exact build. The checker in `tests/roof_checks.py` is not loosened; any
   change to it is limited to the reference-plane choice, and is covered by a permutation and subdivision
   invariance test (D73, D80).
2. The frozen v0.3.0 replay does not inflate (it stays 1/67).
3. A unit test shows the old largest-triangle reference rejected a roof that a planar-exact build passes, or
   that the new builder output is planar to within `TOL`.
4. A 9007 perturbation test passes at ±1e-9 m around the axis.
5. **Pre-change measurement:** before editing, record on f8bedf6 the ratio reserved / emitted (triangles and
   vertices) for every Munich and sample roof, by kind (min, median, max) in the PR. The documented margin is
   then chosen from that table. A reservation-bounds test shows reserved ≥ emitted for every roof kind, and
   reserved ≤ emitted × (1 + margin). **Must:** no undercount. **Aim:** the max ratio falls below the
   pre-change max.
6. Real data: Munich and Pittsburgh CLI builds VALID; the counted number and the reason histogram are in the
   PR.
7. If the checker's reference plane changed, notify the lane-A dev so that the S4-ROOF-SPIKE final-checker
   replay runs (D95), and quote the replayed floor baseline (main before this PR, final checker) in the PR.

## Performance considerations

Roof stage on Munich ≤ +10 % against f8bedf6 (information, D91). Whole Generate is the gate.

## Expected tests

`tests/test_roofs.py`, `tests/test_roofs_munich.py`, `tests/roof_checks.py` (reference plane only). Each new
test ≤ 5 s. Headless Blender `checks_roofs.py` run recorded in VALIDATION.

## Conflict domain

Hard: `core/roofs.py`, `core/generate.py` (building roof section and reservation only), `tests/roof_checks.py`,
`tests/test_roofs.py`, `tests/test_roofs_munich.py`, `tests/fixtures/munich_roofs_expected.json`. Soft: sample
(only if the fixture roofs change, D103), VALIDATION row.
