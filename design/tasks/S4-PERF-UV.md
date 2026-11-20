# S4-PERF-UV: cheaper UV assignment (byte-identical)

Owner: dev · sprint S4 · lane C · after S4-TEX-WATER · D91, D97 · closes S3-F4

## Background

`assign_uvs` and `textured_copy` in `core/uv.py` are pure Python. In #53 the Pittsburgh `build_scene` stage
grew +62 % textured (1.17 → 1.89 s) and +75 % untextured (0.97 → 1.70 s) (D85, D87). Under cProfile on
f8bedf6 the two functions took 1.14 s and 1.41 s of a 53 s profiled build. Re-measure both stages unprofiled
on the S4-TEX-WATER head first and put that baseline in the PR (D90).

## Scope

Reduce per-face overhead: hoist per-material constants, avoid rebuilding per-vertex tuples, batch the tile
offset per mesh and skip untextured meshes early. The output must be exactly the same (D97). No new
dependency (no NumPy in core).

## Acceptance criteria

1. **Byte identity:** the sample and frozen Munich and Pittsburgh textured and untextured builds give the same
   SHA-256 before and after.
2. **Floor:** whole Pittsburgh CLI textured build no slower than the baseline in the PR. **Stretch:**
   `assign_uvs` + `textured_copy` ≥ 2× faster on Pittsburgh, reported as information (D91).
3. Existing `tests/test_uv.py` (corners, seams, tile-offset rule, material bindings) passes unchanged.

## Performance considerations

This is a performance task. No extra full copy of the mesh data.

## Expected tests

No new behaviour, so no new tests are needed beyond an optional equivalence test on a scratch mesh (≤ 5 s).

## Conflict domain

Hard: `core/uv.py`. Soft: none. Serialised after S4-TEX-WATER (the `TEXTURE_MEAN_ALBEDO` table).
