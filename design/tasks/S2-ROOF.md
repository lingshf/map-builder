# S2-ROOF: roof shapes

Sprint S2 (may start early as a parallel lane in S1; ships in v0.3.0) · depends on #11 merged (both touch `core/generate.py`)

## Goal

Model the common OSM `roof:shape` values that v1 flattens, on the footprints where they are
well defined, and move roof code out of `build_building`.

## Scope

* **Refactor first (no output change):** move the roof part of `build_building` (shape
  selection, fallbacks, roof faces) into `core/roofs.py` with one entry point
  `build_roof(mesh, ring, holes, eave_z, roof_h, shape, tags, prov)`. Commit separately so the
  review can see the move is behaviour-preserving (sample byte-identical after this commit).
* **New shapes:**
  * rectangles (`_rect_check`): `half-hipped`, `gambrel`, `mansard`, `round` (barrel, 8
    segments), `saltbox`; honour `roof:orientation=along|across` and `roof:direction` for
    gabled/skillion/saltbox;
  * convex footprints: `dome` and `onion` (6 rings, ≤ MAX_RING_VERTICES vertices);
  * anything else, or courtyard footprints: today's fallbacks with provenance
    `fallback:… not modelled`.
* Heights follow the existing OSM semantics (total vs eave height, roof:height/roof:levels,
  inferred 0.3 × short side).

## Acceptance criteria

1. After the refactor commit, `examples/synthetic_sample.mbmap` byte-identical.
2. Each new shape on a synthetic footprint: closed, outward, positive volume (validator),
   maximum z = total height within 1 mm, eave z within 1 mm, visual == collision binding.
3. `roof:orientation=across` swaps the ridge axis; `roof:direction` rotates the skillion slope
   (tested with ridge/low-edge coordinates).
4. Fixture `way/1043` (`roof:shape=dome`) is built as a dome; sample regenerated and `VALID`.
5. Unsupported shapes and courtyards keep a `fallback:` provenance and the report lists them.
6. VALIDATION matrix roof row updated.

## Performance considerations

Dome/onion triangles = rings × footprint vertices; cap rings so a 2000-vertex footprint stays
≤ 25 k roof triangles; budget reserved. Fixture build ≤ +20 %.

## Expected tests

`tests/test_roofs.py` (per shape: closure, heights, orientation/direction, fallbacks);
`tests/test_scene_generation.py` roof assertions updated; sample regeneration.

## Conflict domain

Hard: `core/generate.py` roof section of `build_building` (and its call sites inside that
function only), new `core/roofs.py`, `tests/test_roofs.py`, roof tests in
`tests/test_scene_generation.py`. Parallel with S1-SEAMS and S2-ELEV (neither edits
`build_building`).
