# S1-TUNNEL: road tunnels

Sprint S1 · depends on S1-SEAMS (parallel with S1-BRIDGE; the shared sweep lands in S1-SEAMS) · decisions D21, D23, D25

## Goal

Highway ways tagged `tunnel=yes` (and other values except `building_passage`/`culvert`) become
flyable tubes (class `tunnel`) with open portals cut into the terrain.

## Approach

* **Input:** `Classified.tunnels`.
* **Profile:** road z at both portals (terrain + `ROAD_LIFT_M` at the endpoint, or the adjoining
  at-grade road z); linear in arc length between them. Sample ≤ 10 m and at every node.
* **Cross-section:** floor width = road width + 2 × 1.0 m; wall height 4.5 m; roof a 5-segment
  polygonal arch with 1.0 m rise (total clearance 5.5 m, `inferred`). `maxheight` tag, if present
  and 2.5–10 m, sets the clearance (`measured`).
* **Tube:** `structures.sweep` with open ends → inward tube, floor material `MB Road`, walls
  `MB Tunnel`. Clip at the area edge (open portal there).
* **Terrain cut (D23):** inside the tunnel stage, remove from the terrain object's mesh the
  triangles that intersect the tube's interior volume (cross-section grown by 0.1 m). No
  approach trench is dug; where terrain near a portal is lower than the roof, the tube simply
  runs in the open (a short gallery). Heightfield cells without terrain become NaN (format
  already allows it).
* **Headwalls:** at each portal, a `structure` solid: a slab 1.0 m thick at the point where the
  terrain first rises above the tube roof, spanning the cut width + 2 × terrain spacing, from
  1 m below the floor up to the highest cut terrain + 1 m, with a through-hole matching the
  tube profile (genus-1 closed solid). Between the portal and the headwall, side skirts (part
  of the same solid) close the cut edge down to the tube walls. The invariant is the leak test
  below; the exact pieces are the developer's choice.
* **Cover check:** where terrain above the roof is < 0.5 m for > 50 % of the length, still build
  it but add a `warnings` entry (likely cut-and-cover/underpass).
* **Buildings above:** a building solid intersecting the tube interior is kept (OSM is the
  truth) and blocks the probe → probe goes to `passage_probes_blocked` with that `mb_id`.
* **Probe** (kind `tunnel`): centreline from 3 m outside one portal to 3 m outside the other at
  floor + r + 0.5 m, `r = min(1.5, (clearance − 1.0) / 2)`; id `<mb_id>:bore`.
* **Report:** tunnels leave `unsupported_features`; count `tunnels`; `terrain_cut_cells`.

## Acceptance criteria

1. In-code synthetic hill (15 m high) with a road tunnel through it between two at-grade roads:
   one `tunnel` object passing the tube rule (two portal loops, negative capped volume); two
   `structure` headwalls passing the solid rule; package `VALID`; the bore probe PASSes.
2. **No leak:** for a grid of points around each portal (±10 m), a vertical ray from 50 m above
   downwards hits terrain, headwall, tube or road before reaching floor z − 2 m (i.e. no gap
   into the space below the terrain). A ray from inside the tube upwards hits the tube roof.
3. Cover: a vertical ray above the tunnel's midpoint hits terrain first, then the tube roof.
4. Heightfield is NaN exactly at cut cells and unchanged elsewhere (max |dz| 0 outside).
5. The fixture tunnel (`way/1072`, `layer=-1`) is generated; regenerated sample `VALID`; C#
   reader CI shows the probe PASS.
6. Blender round trip; a mirrored tunnel keeps the tube rule after bake.
7. `tunnel=culvert`, railway tunnels and `man_made=tunnel` stay unsupported (D25).
8. Docs updated as in the common definition of done (heightfield NaN note now real).

## Performance considerations

* Terrain cut: only cells in the tube's XY bounding corridor are tested (grid indexing), O(cells
  in corridor × profile segments); no full-terrain scan.
* Tube + headwalls ≤ (profile points × samples) + 200 triangles per tunnel; budget reserved.
* Probe as in S1-BRIDGE; fixture build ≤ +20 %.

## Expected tests

`tests/test_tunnels.py` (profile, cross-section from `maxheight`, tube rule, terrain cut set,
headwall genus/solid, leak ray grid, cover warning, building-blocked probe, edge clipping,
determinism); acceptance case; `tests/blender/checks_tunnels.py`; sample regeneration.

## Conflict domain

Hard: `core/tunnels.py`, `core/generate.py` (tunnel hook only; the cut edits the terrain
spec's mesh inside the stage), `tests/test_tunnels.py`, `tests/blender/checks_tunnels.py`. Soft: sample,
fixture, docs bullets. Parallel with S1-BRIDGE and S2-ELEV.
