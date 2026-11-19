# S1-SEAMS: structure seams

Sprint S1 · depends on #11 merged · decision D18

## Goal

Prepare the code so bridges, tunnels and passages can be developed in parallel in their own
modules, **without changing any output**.

## Scope

1. **Routing in `core/osm.py`.** `classify` puts supported structure features in their own lists
   on `Classified` instead of only in `unsupported`:
   * `bridges`: highway ways with `bridge` ∉ {no} (PR #11 already keeps a `bridges` list for the
     DSM mask; reuse it, do not duplicate);
   * `tunnels`: highway ways with `tunnel` ∈ {yes, ...} except `building_passage` and `culvert`;
   * `passages`: highway ways with `tunnel=building_passage` or `covered=yes`.
   Until the feature task lands, each list is still reported in `unsupported_features` with the
   current wording (the stage stub does this), so the report is unchanged. Railway/waterway,
   `man_made=bridge|tunnel`, `building=bridge`, `layer<0` without tunnel, `location=underground`
   stay unsupported (D25).
2. **Stage hooks in `core/generate.py`.** `build_plan` calls, in this order, after roads and
   before trees: `bridges.build(plan, ctx)`, `tunnels.build(plan, ctx)`; and
   `passages.split(...)` inside the building loop before `build_one`. `ctx` is a small plain
   object (terrain grid, z_offset, budget, options, `add`, road segments for tree blocking).
   Stub modules `core/bridges.py`, `core/tunnels.py`, `core/passages.py` only report the
   features as unsupported (today's wording) and return.
   `ScenePlan` gets `passage_probes = []` (already read via `getattr` by pipeline/scene_build).
3. **Shared helper `core/structures.py`** (pure Python, no bpy):
   * `sweep(profile_2d, path_3d, closed_ends)` → mesh with consistent winding: closed ends =
     solid (CCW outward, positive volume), open ends = tube (inward, portal loops open). Mitred
     joints, collapse guard for sharp turns (> 60° → split into separate segments with a joint
     piece, or reject with `InvalidFeature`).
   * `polyline_z_profile(points_xy, z_func, ...)` arc-length helpers shared by bridges/tunnels.
   * `check_probes(plan, probes, max_work)` → (kept, blocked[{id, blocker mb_id}]) using
     `query.capsule_hits` on the plan meshes (world transforms applied); D21.
4. **Blender.** `scene_build` maps classes to collections `Bridges`, `Tunnels`, `Structures`;
   adds materials `MB Concrete` (deck sides, piers, headwalls) and `MB Tunnel` (tube walls).
   Bake/export already carry `mb_class`; confirm tube objects survive bake with mirrored
   transforms (tube winding flips with negative determinant like solids).
5. **Integration harness split.** `tests/blender/run_integration.py` `main()` is one long
   function; split into `tests/blender/checks_core.py` (today's checks, unchanged) and a tiny
   runner that imports optional `checks_*.py` modules, so each feature adds its own file.

## Acceptance criteria

* `examples/synthetic_sample.mbmap` is **byte-identical** before and after (test_examples
  passes without regeneration); `report.json` of the fixture unchanged.
* `sweep` unit tests: a box profile with closed ends passes the validator's solid rule; with
  open ends passes the tube rule (negative volume after capping, two portal loops); a 90° turn
  either produces a valid mesh or a clear `InvalidFeature`; mirrored copies keep their rule.
* `check_probes`: a probe through an open tube passes; the same probe with a blocking box is
  returned in `blocked` naming the box `mb_id`; budget exhaustion is reported, not silent.
* Headless Blender: the split harness still reports the same 74 checks, `OK: 0 failure(s)`.
* No new public behaviour in the UI or CLI.

## Performance considerations

* `sweep` is O(path points × profile points); no global work. `check_probes` prunes by object
  AABB before triangles and shares one work budget (default the validator's 2 M visits).
* Unit-test time added ≤ 5 s.

## Expected tests

`tests/test_structures.py` (sweep solid/tube, mirrored, sharp turn, probe pass/blocked/budget,
using `package` winding checks and `query.capsule_hits` as oracles); `tests/test_scene_generation.py`
routing assertions (lists populated, report unchanged); Blender harness re-run.

## Conflict domain

Hard: `core/osm.py` (`_unsupported_reason`, `Classified`, `classify` routing),
`core/generate.py` (`ScenePlan`, `build_plan` hook calls), new `core/structures.py`,
`core/bridges.py`, `core/tunnels.py`, `core/passages.py` (stubs), `blender/scene_build.py`,
`tests/blender/*`. Can run in parallel with S2-ROOF (different functions of `generate.py`).
