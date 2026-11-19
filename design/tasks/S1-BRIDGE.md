# S1-BRIDGE: bridge decks

Sprint S1 · depends on S1-SEAMS · decisions D15, D21, D22, D25

## Goal

Highway ways tagged `bridge=*` (not `no`) become flyable-under deck solids (class `bridge`) with
passage probes over and under the deck.

## Approach

* **Input:** `Classified.bridges` (highway ways). Width from `road_width(tags)` + 0.5 m per side
  (provenance `inferred:road width + 2 x 0.5 m`; `width` tag measured when present).
* **End heights:** at an endpoint shared with an at-grade road, `z = road z there` (terrain +
  `ROAD_LIFT_M`), so the deck meets the road within 5 cm. At a free endpoint (no at-grade
  neighbour, or clipped at the area edge), `z = terrain + ROAD_LIFT_M`.
* **Profile (D22):** linear in arc length between the end heights; where the ground under the
  deck (DSM-corrected) plus `max(1, layer) × 5.0 m` clearance is higher than that line, raise
  the profile, with ramps ≤ 8 % grade back to the line. Sample at ≤ 10 m and at every OSM
  node. Provenance names the rule and whether it was raised.
* **Geometry:** `structures.sweep` of a rectangle (width × 1.0 m, top = profile) with closed
  ends → one closed solid per bridge way. Ends sink 0.5 m into the abutting ground/road so
  there is no visible gap. Top faces use `MB Road`, sides/underside `MB Concrete`.
* **Ground under the deck** is not modified (DSM correction already lowered it). At-grade roads,
  water and terrain beneath are generated normally; trees are blocked within the deck footprint.
* **Probes** (kind `bridge`, radius 1.0 m):
  * `deck`: along the centreline at deck top + 1.5 m, ≤ 64 points;
  * `under`: a straight segment across the span at the point of maximum clearance, from
    half-width + 3 m on one side to the other, at `ground max along the segment + 1.5 m`;
    emitted only if clearance under the deck ≥ 4 m.
  Checked with `structures.check_probes`; blocked probes go to `report.json`
  `passage_probes_blocked` (D21). Probe ids: `<mb_id>:deck`, `<mb_id>:under`.
* **Report:** bridges leave `unsupported_features`; new count `bridges`; a bridge that cannot be
  built (degenerate, too short < 2 m, sharp turn) goes to `invalid_features` with the reason.

## Acceptance criteria

1. On an in-code synthetic valley (two at-grade roads joined by a bridge way over a 15 m deep
   valley): one `bridge` object; deck ends within 5 cm of the adjoining road ribbons; package
   `VALID`; both probes present and PASS in the validator; a vertical ray from 2 m above the
   valley floor upwards hits the deck underside; heightfield unchanged under the deck.
2. On flat ground with `layer=1` over an at-grade road: deck clearance over the crossing road ≥
   5.0 m; ramps ≤ 8 %; the under probe along the crossing road PASSes.
3. The fixture footway bridge (`way/1069`) is generated; the regenerated sample is `VALID`; the
   C# reader CI step shows its probes PASS.
4. Blender: generate → export → validate round trip; moving the deck down onto the road makes
   the `under` probe a validator **warning** (not an error), naming the probe by index.
5. `man_made=bridge`, `building=bridge`, railway bridges stay in `unsupported_features` (D25).
6. Docs: PACKAGE_FORMAT (unsupported list, `passage_probes_blocked`), README Limits,
   UNITY_CORE_HANDOFF ("not generated yet" → generated), VALIDATION matrix row.

## Performance considerations

* Deck mesh O(samples); reserve in `SceneBudget` before allocation.
* Probe check cost ≈ (objects + nearby triangles) × segments; with AABB pruning a 1 km map with
  ≤ 50 bridges must stay < 1 s plan-time and inside the 2 M package budget. If over budget,
  keep probes of the longest bridges first and report the rest as unchecked.
* Fixture build time ≤ +20 %.

## Expected tests

`tests/test_bridges.py` (profile maths incl. ramp limit and layer clearance, end-height join,
sweep validity via the validator, probes pass/blocked, invalid cases, determinism);
an acceptance case in `tests/test_acceptance.py` (ray under deck, probe PASS);
`tests/blender/checks_bridges.py` (round trip + moved-deck warning). Plus sample regeneration.

## Conflict domain

Hard: `core/bridges.py`, `core/generate.py` (bridge hook call only), `tests/test_bridges.py`,
`tests/blender/checks_bridges.py`. Soft: sample, fixture, docs bullets. Parallel with
S1-TUNNEL and S2-ELEV.
