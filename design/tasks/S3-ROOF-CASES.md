# S3-ROOF-CASES: Munich roof acceptance cases and geometry checker (write first)

Owner: dev · sprint S3 · wave 1 · DoD 10 (cases before implementation) · D55, D61

## Goal

Freeze the real-data acceptance set for non-rectangular roofs **before** any roof algorithm
lands, so that S3-ROOF-HIPPED and S3-ROOF-GABLED are measured against committed data, not
against their own output.

## Scope

1. Extract every Munich Altstadt building with a tagged `roof:shape` in `{gabled, hipped}`
   that v0.3.0 builds as a fallback. There are 46 per docs/demo/v0.3.0. Take them from the
   cached acquisition of the `munich-altstadt` preset. Reuse `tests/fixtures/munich_altstadt_excerpt.osm`
   (S2-F2) where it already holds them; otherwise add `tests/fixtures/munich_roofs.osm`. Keep the original OSM ids. Add the ODbL attribution in
   `tests/fixtures/README.md`.
2. Classify each case as *eligible*: a simple polygon, no inner ring, ≤ 64 vertices after
   simplification, valid `roof:height` or default. Otherwise mark it *excluded*, with a named
   reason. Record the table (id, shape, vertices, convex/concave, eligible, reason) in the PR.
3. Add **counterexamples**, synthetic and committed:
   * a self-touching ring;
   * a footprint with a 0.05 m sliver edge;
   * a near-collinear vertex run;
   * a footprint with a courtyard (must keep the existing fallback);
   * one with > 64 vertices (must fall back with a reason).
4. Add a reusable **geometry checker**, `tests/roof_checks.py`, used by both roof tasks and by
   S3-REVIEW. For one built building mesh it asserts:
   * the mesh (walls + roof) is closed: no boundary edges, every edge used exactly twice;
   * every roof face is planar (≤ `PLANAR_TOL_M`) and lies at or above the eave;
   * the projected roof area equals the footprint area within 0.1 %, with every projected roof
     face positively oriented. Together these mean no overlap and no gap;
   * the maximum roof z equals eave + roof height within 1 mm;
   * sloped faces have an upward normal (`n.z > 0`); gable ends are vertical (`|n.z| < 1e-6`)
     and use `MB Facade`.
5. Add `tests/test_roofs_munich.py`. On main today it proves the baseline: the excerpt builds,
   and the eligible cases fall back with the v0.3.0 reason. Each roof task flips its cases to
   "built as tagged" with the checker.

## Acceptance criteria

1. The excerpt and counterexamples are committed and load offline; the test runs in ≤ 5 s.
2. The eligible count *E* is recorded. **D61:** the sprint target is "≥ 40 of 67 Munich tagged
   non-flat roofs built as tagged". If *E* + 5 < 40, report it; the coordinator re-baselines the
   target before HIPPED starts.
3. The checker is proven to catch a broken mesh: a test feeds it a mesh with one removed face,
   one overlapping face and one face below the eave, and each fails.

## Performance considerations

No product code. The excerpt is ≤ 300 KB. The new tests run in ≤ 5 s together.

## Conflict domain

Hard: `tests/fixtures/munich_roofs.osm` (new, if needed), `tests/fixtures/README.md`, `tests/roof_checks.py` (new),
`tests/test_roofs_munich.py` (new). No product code.
