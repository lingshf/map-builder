# M4-ELEV: elevated parts and building passages

Milestone M4 · depends on M2-SEAMS · decisions D20, D23

## Goal

Make the space beneath elevated building parts and through building passages a verified free
volume.

## Approach

1. **Elevated parts** (`min_height` / `building:min_level` > 0): geometry already starts at
   `min_h` (`build_building`). This task removes the "not supported" report entry, keeps the
   existing terrain-reaches-underside rejection, and adds a probe (kind `elevated`, id
   `<mb_id>:under`): a straight segment across the footprint's longest axis at
   `max ground under the footprint + r + 0.3 m`, `r = min(1.0, (clearance − 0.6) / 2)`; emitted
   only if clearance ≥ 2.6 m. If another solid (its own outline's other parts, a neighbour)
   blocks it, D20 applies.
2. **Building passages** (`Classified.passages`: highways with `tunnel=building_passage` or
   `covered=yes`) crossing a building footprint (D23). In `core/passages.py`, before the
   building is built:
   * corridor = passage way buffered by road width / 2 + 0.5 m, restricted to the footprint;
   * passage height = `maxheight` (2.5–10 m, measured) else min(4.5 m, building eave − 1 m)
     (inferred);
   * the building is replaced by: **lower parts** = footprint minus corridor (may be several
     polygons), flat-topped at passage height, ids `<id>#1..k`; **upper part** = full footprint
     from passage height to the original roof, built as an elevated volume, id `<id>#k+1`.
     Lower and upper must not share overlapping faces (lower top 0.01 m below, or the upper
     part starts exactly at the lower top with matching shells — the validator's solid rule is
     the oracle).
   * The passage road itself is generated at grade under the building (it is no longer
     unsupported), clipped to nothing else.
   * Probe kind `elevated`, id `<way mb_id>:passage`, along the passage way inside the
     footprint ± 3 m, at road z + r + 0.3 m.
   * Cases not handled (corridor does not cross the footprint, polygon difference fails the ring
     checks, courtyard building, building:part outlines): building unchanged, passage reported
     in `unsupported_features` with the reason.

## Acceptance criteria

1. Fixture `way/1048` (`min_height=6`) no longer listed as unsupported; its `under` probe PASSes
   in the validator.
2. Synthetic building 30 × 20 m crossed by a `tunnel=building_passage` service road: 2 lower
   parts + 1 upper part, all closed positive-volume solids, ids `#1..#3`, package `VALID`,
   passage probe PASS; a horizontal ray along the passage at 2 m hits nothing for the
   footprint length; a ray across the building at 2 m outside the corridor hits a lower part.
3. A passage that ends inside the footprint (dead end) is unsupported and the building unchanged.
4. Blender: duplicate/move of an upper part keeps ids distinct (`~` rule); a moved-down upper
   part turns the probe into a validator warning.
5. Docs: unsupported list, README Limits, provenance rules for passage height.

## Performance considerations

Polygon difference only for buildings that a passage crosses (bbox prefilter); reuse
`triangulate.validate_rings` and the existing triangulation work budget. Fixture build ≤ +20 %.

## Expected tests

`tests/test_passages.py` (split geometry, ids, heights from tags, failure fallbacks, probes);
acceptance case for the fixture elevated part; `tests/blender/checks_passages.py`; sample
regeneration.

## Conflict domain

Hard: `core/passages.py`, `core/generate.py` (building loop in `build_plan` and the elevated
report entry only — not `build_building`), `tests/test_passages.py`,
`tests/blender/checks_passages.py`. Parallel with M3-BRIDGE / M3-TUNNEL; with M4-ROOF only if
ROOF has merged or ROOF keeps out of the building loop (it should).
