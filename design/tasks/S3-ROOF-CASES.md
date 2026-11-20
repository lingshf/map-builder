# S3-ROOF-CASES: frozen Munich roof snapshot, counterexamples and geometry checker (write first)

Owner: dev · sprint S3 · wave 1 · DoD 10 (cases before implementation) · D55, D61, D64

## Goal

Freeze the real-data acceptance set for non-rectangular roofs **before** any roof algorithm
lands. S3-ROOF-HIPPED and S3-ROOF-GABLED are then measured against committed data and frozen
heights, not against their own output or a live acquisition.

## Scope

1. **Frozen snapshot of all 67.** Commit every Munich Altstadt building with a non-flat
   `roof:shape` tag (all 67 counted in docs/demo/v0.3.0, not only the 46 gabled/hipped
   fallbacks) as an offline snapshot, `tests/fixtures/munich_roofs.osm`. Take it from the
   `munich-altstadt` preset acquisition. Keep the OSM ids, the ways' nodes and their tags, and
   add the ODbL attribution to `tests/fixtures/README.md`.
   * Record the acquisition's SHA-256 in the fixture README.
   * The snapshot is built over a flat synthetic DEM, so terrain cannot change the result.
2. **Frozen heights.** Commit `tests/fixtures/munich_roofs_expected.json`. For each id it holds
   the tagged shape, the eave z and top z (eave + roof height) relative to the building base,
   and the v0.3.0 outcome (built shape and `roof_shape` provenance). It is produced **once, by
   v0.3.0** (tag `v0.3.0`, eb134a1) on the snapshot; the generator command goes in the README.
   The ridge and eave checks read heights from this file, never from the code under test. A
   change to the height rules must update the file in its own reviewed diff.
3. **Eligibility table.** Classify each of the 67 cases:
   * *eligible for the skeleton*: gabled or hipped, a simple polygon, no inner ring, ≤ 64
     vertices after collinear merge;
   * *already built* (the 5 v0.3.0 successes);
   * *out of S3 scope*: any other shape, a courtyard, or > 64 vertices. Each gets a named reason.

   Record the table in the JSON and in the PR.
4. **Counterexamples**, synthetic and committed in `tests/fixtures/roof_counterexamples.osm`:
   * a self-touching ring;
   * a 0.05 m sliver edge;
   * a near-collinear vertex run;
   * a courtyard (must keep the existing fallback);
   * > 64 vertices (must fall back with a reason);
   * a footprint whose skeleton has a **concave face**, such as a U or a deep L.
5. **Geometry checker, `tests/roof_checks.py`.** It is shared by both roof tasks and by
   S3-REVIEW. It works on the **emitted triangles**: the triangles written to `visual/map.glb`
   and `.mbcol`, decoded from the built package. It never uses `MeshData` faces, because the
   GLB fans faces from vertex 0 and a non-convex face would be mis-triangulated. For one
   building it asserts:
   * **Closed:** walls + roof together have no boundary edge and every edge is used exactly
     twice, after welding positions within 1e-6 m.
   * **Above the eave:** no roof triangle vertex is below the eave z of the expected file
     (−1 mm).
   * **Ridge:** the maximum roof z equals the expected top z ±1 mm. For gabled and hipped, at
     least one horizontal ridge edge, or the apex, lies at that z.
   * **Slopes and gable ends:** every `MB Roof` triangle has an upward normal
     (`n.z > 1e-6`). Every gable-end triangle (an `MB Facade` triangle with a vertex above the
     eave) is vertical, `|n.z| < 1e-6`, and its base edge lies on a footprint edge.
   * **No gap (checked independently):** the area of the footprint minus the union of the
     projected roof triangles is ≤ 1e-6 · footprint area. Compute it with exact convex
     clipping of the triangles against the footprint triangulation.
   * **No overlap (checked independently):** the sum of the pairwise intersection areas of the
     projected roof triangles is ≤ 1e-6 · footprint area. Use convex–convex clipping with a bbox
     prefilter, as in D39, under a pair cap that raises `LimitError` when exceeded. A balanced
     overlap plus gap therefore fails both checks; a positive area sum alone is not accepted.
   * **Inside:** every projected roof triangle lies inside the footprint (clipped area loss
     ≤ 1e-6 · footprint area).
6. **Geometry-based count, `built_as_tagged(building)`.** This is the D61 metric, over all 67.
   A building counts only if the checker passes **and** the emitted geometry has the tagged
   shape's signature:

   | Shape | Signature |
   |---|---|
   | hipped | no gable-end triangle; every footprint edge carries ≥ 1 sloped roof triangle |
   | gabled | ≥ 2 vertical gable-end triangles; every other footprint edge carries sloped triangles |
   | skillion, pyramidal and the rectangle-only shapes | the existing invariants of `tests/blender/checks_roofs.py`, ported |

   Provenance (`roof_shape_built`) must agree with the signature. A disagreement is a test
   failure, but the count itself comes from the geometry.
7. `tests/test_roofs_munich.py` builds the snapshot offline and asserts the **baseline** on
   main: exactly 5 of 67 counted, and every other case matching its frozen v0.3.0 outcome.
   Each roof task raises the asserted number.

## Acceptance criteria

1. The snapshot, expected file and counterexamples are committed and load offline. All new
   tests together run in ≤ 5 s; report the count for the largest.
2. The baseline count on main is 5/67, from the geometry.
3. The number of eligible cases *E* is recorded. If 5 + *E* < 40 (D61), report it, and the
   coordinator re-baselines the target before HIPPED starts.
4. The checker is proven to catch defects. Six crafted meshes each fail with a named check:
   * a missing triangle (closed);
   * an overlap balanced by a gap of equal area (both overlap and gap fail);
   * a vertex below the eave;
   * a ridge 2 mm low;
   * a tilted gable end;
   * a fan-triangulated concave face (overlap fails).

## Performance considerations

No product code. The fixtures are ≤ 300 KB together. The pairwise overlap check is O(t²) per
building for t ≤ a few hundred triangles, under a pair cap; it is counted, not timed.

## Conflict domain

Hard (all new): `tests/fixtures/munich_roofs.osm`, `tests/fixtures/munich_roofs_expected.json`,
`tests/fixtures/roof_counterexamples.osm`, `tests/roof_checks.py`, `tests/test_roofs_munich.py`.
Also `tests/fixtures/README.md`. Does **not** touch `tests/fixtures/synthetic_area.osm`, the
sample or `tests/blender/` (D64).
