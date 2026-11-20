# S3-SKELETON: straight skeleton of a simple polygon

Owner: dev · sprint S3 · wave 1 · D55 · complex geometry (DoD 10)

## Goal

A pure-geometry module, `core/skeleton.py`, that computes the straight skeleton of a simple
polygon without holes. It returns one planar face per footprint edge, and each skeleton node
carries its offset distance (time). It must be deterministic, bounded and free of Blender and
OSM types. The roof tasks build on it; this task does not touch `roofs.py`.

## Scope

* Event-driven wavefront: edge events and split events (reflex vertices). Coincident events
  are merged within a documented tolerance. Use double precision with the same tolerance
  constants as `roofs.py`.
* API, for example: `straight_skeleton(ring) -> Skeleton(nodes=[(x, y, t)], faces=[[node ids]
  per input edge])`. Raise `SkeletonError` with a reason on unsupported input: self-touching
  ring, an edge shorter than the tolerance, or more than `MAX_SKELETON_VERTICES` (64, D55)
  vertices.
* Work bound: count events and raise `LimitError` past `MAX_SKELETON_EVENTS`
  (O(n²), documented). Never time-based.

## Acceptance criteria (tests written first, in `tests/test_skeleton.py`)

1. **Rectangle:** the skeleton equals the current analytic hipped result (ridge length L − W;
   4 faces).
2. **Square / regular n-gon:** a single apex at the centroid, with t = inradius.
3. **L, T, U and Z shapes and the reflex arrow:**
   * face count equals edge count;
   * each face is planar when lifted with z = t;
   * the faces tile the footprint, shown by the two **independent** checks of
     `tests/roof_checks.py` (S3-ROOF-CASES): no gap (footprint − union ≤ 1e-9 relative) and no
     overlap (sum of pairwise intersections ≤ 1e-9 relative). The checks run on the
     explicitly triangulated faces.

   If S3-ROOF-CASES is not merged yet, this PR carries a local copy of the two checks, and the
   PR that merges second switches it to the shared module. An area-sum check alone is not
   accepted.
4. **Reflex split events:** a concave "arrow" shape produces the expected split node,
   hand-computed in the test.
5. **Degenerate input:** collinear runs are merged first; a self-touching ring, a zero-length
   edge and > 64 vertices raise `SkeletonError` with a reason.
6. **Determinism:** the same ring, rotated in start index or in orientation, gives the same
   face set.
7. **Real excerpts:** every *eligible* case of S3-ROOF-CASES returns a skeleton whose lifted
   faces pass the S3-ROOF-CASES area and planarity checks. If S3-ROOF-CASES is not merged yet,
   add these cases in the PR that merges second.

## Performance considerations

For n ≤ 64, at most `MAX_SKELETON_EVENTS` events. Report the event count for the largest Munich
case in the PR. The whole test file runs in ≤ 5 s. No wall-clock assertions: work is bounded
by the event counter.

## Conflict domain

Hard: `core/skeleton.py` (new), `tests/test_skeleton.py` (new).
