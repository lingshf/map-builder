# M3-PIERS: bridge piers and parapets

Milestone M3 · depends on M3-BRIDGE

## Goal

Make long bridges look and collide like bridges: piers under long spans and low parapets on the
deck edges, without blocking the passages M3-BRIDGE guarantees.

## Approach

* **Piers:** for decks with clearance > 6 m, place piers at ≤ 40 m spacing, never within 3 m of
  the `under` probe segment, never on an at-grade road ribbon (shift along the deck ≤ 5 m, else
  skip). Cross-section 1.5 m × (deck width − 1 m), from 1 m below the ground to the deck
  underside, as extra closed shells of the same bridge object (one object per bridge keeps the
  `mb_id` binding simple). Over water, piers are allowed.
* **Parapets:** 1.0 m high, 0.3 m wide on both deck edges, part of the deck shell (union, not
  overlapping shells). Deck probe height unchanged (the probe runs between the parapets).
* Option `PlanOptions.bridge_piers` (default on) and CLI/Blender switch only if cheap; otherwise
  internal option for tests.

## Acceptance criteria

1. All M3-BRIDGE acceptance tests still pass; both probes still PASS on the synthetic valley.
2. Synthetic 120 m valley bridge: 2 piers, each a closed positive-volume shell, touching the deck
   underside within 1 cm; no pier intersects the `under` capsule or an at-grade road ribbon.
3. Bridge object stays a valid solid (validator), visual/collision binding exact.
4. Parapets: a ray along the deck edge at deck top + 0.5 m hits the parapet.

## Performance considerations

≤ 12 triangles per pier, ≤ 4 × samples per parapet; budget reserved. No change to probe cost
beyond the extra triangles.

## Expected tests

Extend `tests/test_bridges.py` (pier placement, avoidance of probe and roads, parapet ray);
sample regeneration if the fixture bridge gains parapets.

## Conflict domain

Hard: `core/bridges.py`, `tests/test_bridges.py`. Soft: sample. Parallel with anything not in
`core/bridges.py`.
