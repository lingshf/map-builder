# S4-PERF-PKG: single-pass deflate and faster strict validation (byte-identical)

Owner: dev · sprint S4 · lane B · D91, D96, D97 · replaces S3-F5

## Background (measured on f8bedf6, Pittsburgh frozen cache)

* Same-host v0.4.0 medians of 3 with the pinned setup (roadmap sprint-4 baselines, `design/bench/`): CLI
  Munich 4.16 s, Pittsburgh 20.43 s (package step 15.24 s); headless Blender Export (write + strict validate)
  Munich 5.51 s, Pittsburgh 30.18 s; Generate+Export Munich 9.77 s, Pittsburgh 43.35 s. **Strict validation alone is 9.45 s** (median
  of 3, `validate_package(strict=True)`). The top internal costs are `_correspondence`, `_dist`,
  `match_one_to_one`, `_centroid_cells`, `match_winding` and `find_secrets`.
* `_zinfo` (`core/package.py:1130`) deflates each member once to test `MAX_RATIO`, and then `zipfile` deflates
  it again. The 15 MB GLB is compressed twice.
* S3-F5 (ZIP_STORED for PNGs) does not apply as written, because the PNGs are inside `visual/map.glb` (D96).

## Scope

1. Deflate each member once: compute the raw stream once, then either write it as the deflated member or,
   when the ratio is exceeded, store the member. The archive bytes must be identical.
2. Speed up the GLB ↔ `.mbcol` correspondence and the secret scan. Keep the algorithm's results exactly; for
   example, precompute centroids, use squared distances or index cells once.

## Acceptance criteria

1. **Byte identity (D97):** the committed sample and frozen Munich and Pittsburgh builds give the same SHA-256
   before and after. A unit test pins the sample bytes, or `tests/test_examples.py` covers it.
2. **Verdict identity:** every positive and negative package fixture gives the same errors and warnings, in the
   same order (existing tests, plus one test that compares the message lists of all negative fixtures with a
   recorded list).
3. **Floor:** CLI whole Generate ≤ +5 % vs the same-host v0.4.0 median (Munich ≤ 4.37 s, Pittsburgh
   ≤ 21.45 s), and headless Blender Generate+Export ≤ +5 % (Munich ≤ 10.26 s, Pittsburgh ≤ 45.52 s).
   **Stretch:** Pittsburgh CLI ≤ 15.0 s with strict validation ≥ 2× faster, Pittsburgh Blender
   Generate+Export ≤ 35 s. Re-measure v0.4.0 and the PR head with `design/bench/` on one host, sequentially,
   and quote both in the PR (D91). Not asserted in any test.
4. A test asserts that each member is deflated once (for example, by counting `zlib.compressobj` calls).

## Performance considerations

This is a performance task. Peak memory must not grow more than one extra copy of the largest member. Report
headless Blender Generate and Generate+Export for both presets separately (Export calls the same writer and
validator).

## Expected tests

`tests/test_package.py` additions, ≤ 5 s each. No wall-clock assertion.

## Conflict domain

Hard: `core/package.py` (writer and validator internals; no format or message change). Soft: none. S4-FORMAT-
POLICY's optional `package.py` edit comes after this task.
