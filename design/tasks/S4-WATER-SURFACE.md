# S4-WATER-SURFACE: flat water surfaces on carved beds

Owner: dev · sprint S4 (v0.5.0, D112) · after S4-COL-DEGEN, before S4-REVIEW · D4, D21, D22, D39,
D90, D91, D98, D101, D103, D110 · D111, D112; proposed decisions D113–D117 (in [../roadmap.md](../roadmap.md))

User request (verbatim): "检查地图的河流，看起来像是一个沟，上面改垫了垫子，你看下，能改进么"
("The rivers on the map look like a ditch with a mat laid on top. Please look at them. Can this be improved?")

## Background (diagnosis)

Water has no geometry of its own. `build_terrain` (`core/generate.py:759`) builds the single `MB Terrain` grid
mesh. Each cell takes the colour of the highest-priority landcover area that contains the cell centre
(`LANDCOVER_PRIORITY`, water = 4). Water cells are painted `LANDCOVER_COLORS["water"]` and nothing else changes.
In the v0.4.0 demo (`docs/demo/v0.4.0/pittsburgh-bridge-under-v040.png`) this causes two problems:

* **Ditch.** The painted surface keeps the corrected GLO-30 heights. Over rivers the DSM sags and undulates
  (radar returns from water are noisy, and the DSM mask in `core/dsm.py` does not cover water). The "river" is
  therefore a blue trough that dips and rises, instead of a level surface.
* **Mat.** The blue/green boundary is a staircase of 10 m terrain cells, decided by cell centre. It is not the
  OSM shoreline, so the water reads as a blanket draped over the ground.

The collision format already has water: class 5 `water`, kind surface, normal Z > 0
(`core/collision.py:60,70`, `docs/PACKAGE_FORMAT.md:98,478`). No generator path emits it today.

## AC0: measured baseline first (D90)

Before any change, on the v0.4.0 / v0.5.0 main and with the frozen Pittsburgh and Munich caches (offline,
`design/bench/offline_guard.py`), record per water area in a table in the PR body:

1. **Bed spread.** For the terrain vertices inside the polygon: min, p10, p50, p90, max and range of z.
   This number is the "ditch".
2. **Shoreline deviation (staircase).** Area of the symmetric difference between the painted water cells and
   the OSM polygon, divided by the polygon perimeter. The result is a mean offset in metres, about s/4 for a
   10 m staircase. Use a point-in-polygon raster at ≤ 2 m with a bbox prefilter, or exact clipping. A naive
   per-vertex `contains` over the river multipolygons is too slow for the benchmark harness; this was measured
   while writing this spec.
3. **Shore band.** DEM samples in a band 0–2 cells outside the polygon: p10, p20 and p50. Use these to choose
   the level statistic (D114).
4. **D91 baseline.** Whole Generate on the same host (CLI and Blender). Reuse the v0.5.0 numbers if they were
   measured on the same commit and host.

All numeric targets below that refer to the baseline become final only after AC0 (D90). The targets are written
as a floor plus the measured value.

## Scope

### 1. Water bodies (D113)

A *water body* is an `area_class == "water"` polygon after the existing ring validation
(`landcover_ring_problem`): `natural=water`, `landuse=reservoir|basin`, any `water=*` (this includes
`water=river`, the modern riverbank tagging) and `waterway=riverbank`. Multipolygons keep their holes, for
example islands and piers. Linear `waterway=*` ways do **not** create a surface; they are used only as a
centreline hint for long rivers (§2). Polygons are clipped to the area extent first. Clipped edges are not
shoreline and are excluded from the shore statistics.

### 2. Water level (D114)

Each water body gets one level, or a level profile for rivers.

* **Lakes, reservoirs and basins, and any body whose extent along its main axis is < 300 m:**
  one flat level `L = p20` of the DEM shore-band samples (§AC0.3). Use the *corrected* DEM (after
  `dsm.apply_correction`) and drop samples that fall inside buildings, bridges or other water bodies.
* **Rivers** (`water=river`, `waterway=riverbank`, or a body intersected by a `waterway=river|canal` centreline)
  longer than 300 m in the area: project the shore samples onto the centreline, take p20 in 100 m stations,
  then apply isotonic regression (pool-adjacent-violators) so the level is **non-increasing downstream**.
  Downstream is the way direction of `waterway=*`. If no centreline exists or its direction is ambiguous, fall
  back to one flat level.
  The surface is a piecewise-planar mesh that follows the station levels. Its slope is capped at 1 % of length:
  real rivers in a ≤ 2 km tile drop well under 1 m. Above the cap the result is "flat level + reported warning".

**Why p20 of the shore band, not the cell heights inside the polygon.** Inside the polygon the DSM is exactly
the noisy signal that causes the ditch. Its minimum is the deepest radar artefact, and its median floats on the
noise. Banks are land: GLO-30 is reliable there, and the water line is the lowest stable part of the bank.
p20 is robust to embankments, walls and quays, which pull the median and maximum up. It is also robust to
single low outliers, which pull the minimum and p5 down. AC0.3 may move the percentile between p10 and p30 if
the Pittsburgh/Munich data argue for it. Record the choice in D114.

**Tolerance.** The emitted level must equal the computed statistic to within 1 mm, and a flat body must be flat
to within 1 mm. For the chosen percentile, acceptance against data is: on each preset, the level lies between
the shore-band p5 and p50 (a sanity window, not an accuracy claim; GLO-30 vertical accuracy is a few metres).

### 3. Water mesh

* One object per body, `mb_id = water:<osm-id>`, class `water`, material `MB Water`. This is the existing
  S4-TEX-WATER neutral texture/colour. UVs follow the planar tile-offset rule from S3-UV-CORE.
* Triangulate the clipped polygon with holes using `core/triangulate.py`, plus the station cuts for river
  profiles. All normals are +Z. The mesh is reserved in the triangle budget before emission, like terrain and
  roofs (a `water:<id>` reservation). If the budget refuses it, the body falls back to today's painted cells,
  and the coverage report names the reason.
* Coverage: every water area is reported as `built` or `fallback(<reason>)`. The old "no cell centre ⇒
  unsupported" rule no longer applies to water.
* Terrain cells inside water keep the existing water vertex colour, so any gap reads as water. The bank cells
  use the bank colour/texture.

### 4. Bed carve and bank blend (D115)

After DSM correction and before bridges, roads and probes are built, the terrain heights are modified on the
grid only (topology unchanged, so `grid_layout` and the probes' cell lookup keep working):

* **Inside** (vertex inside the polygon, or any of its adjacent cells overlapping the polygon):
  `z := min(z, L(x,y) − D)`, with **D = 1.5 m** (bed depth below the surface).
* **Bank blend** over 1 cell (2 cells if AC0.3 shows banks steeper than 1:1): vertices within `k·s` outside the
  polygon are pulled down to `min(z, L + (d/(k·s))·(z_orig − L))`, where `d` is the distance to the shoreline.
  This only ever lowers terrain and never raises it, so it cannot lift a road or building base.
* Vertices under a building footprint or a bridge abutment are excluded from the blend. Their height already
  drives foundations and clearance (D22, D39).

**Invariant (checked exactly on the emitted triangles, D39):** no terrain triangle has any point above the local
water level `L(x,y)` within the water polygon. Because terrain triangles are planar over a 10 m grid, the check
also covers edges that cross the shoreline. Inside-or-adjacent cells are carved for exactly this reason.

### 5. Bridges, piers, roads and probes (D116)

* **Clearance is measured over the water surface.** In `core/bridges.py`, `_ground_max` uses a sampler
  `max(terrain_z, water_level)`, where water_level is −∞ outside water. D22 then still means "layer × 5 m above
  what a drone sees". Decks must not drop because the bed was carved. On the presets, bridge decks keep
  today's heights within 0.1 m (regression test), unless they now gain clearance.
* **Piers** sink `PIER_SINK_M` below the *carved bed*, so they reach the bed and never float above it.
  `PIER_MIN_CLEARANCE_M` is evaluated against the water surface.
* **Roads** that cross a water polygon outside a bridge stay where they are. A road at grade over water is an
  OSM data issue, so it is reported and not "fixed". The carve excludes road corridors that are not bridges
  (`ROAD_LIFT_M` sits on the original terrain).
* **Passage probes (D21, D98).** Under-bridge probes start at the water level plus the probe radius, not on the
  bed. Probes the generator knows to be blocked stay listed, not emitted (D21). All existing probes must stay
  passable (hit equivalence on the probe set, per the D98 method). New expected hits on water surfaces are
  listed in the PR.

### 6. Collision and query semantics (D117)

* Water surfaces are emitted to `.mbcol` as **class 5 `water` (kind surface, normal Z > 0)**. The class, kind,
  members and layout already exist, so this is **no format change**. It fits D101/D110: no new members, no
  version bump, and both the frozen v0.3.0 reader and the current C# reader already accept class 5.
* Semantics for the simulator (documentation only, no change to the simulator repo, which is read-only):
  water is a *surface* the drone can touch or "land" on, and it is reported with its class so the consumer can
  treat it as a crash, splash or float. Downward ray and capsule queries over a river now hit `water` at L
  before the bed. The bed (`terrain`) sits D below it.
* **`.mbhf` heightfield stays terrain-only** (`docs/PACKAGE_FORMAT.md:502`), so over water it now reports the
  bed. This is consistent with its definition. `docs/PACKAGE_FORMAT.md` and `docs/UNITY_CORE_HANDOFF.md` must
  state explicitly that consumers need the `.mbcol` query, not the heightfield, for an altitude-above-surface
  reading over water.
* GLB: one extra mesh per water body using the existing `MB Water` material. glTF needs no extension.

## Acceptance criteria

1. **AC0** baseline table in the PR body (above).
2. **Renders.** Before/after Cycles CPU renders of the Pittsburgh confluence using the demokit cameras
   (`pittsburgh-bridge-under`, `pittsburgh-overview`), stored in the PR and later in `docs/demo/`. Munich
   Altstadt (400 × 400 m) is only checked for regressions: if AC0 finds no water body there, its renders must
   be unchanged apart from the terrain texture. After: a level water surface, the shoreline follows the OSM polygon,
   no blue trough, and no terrain poking through.
3. **No terrain above water.** An exact check on emitted triangles (§4 invariant) for both presets and the
   synthetic sample: 0 violations.
4. **Shoreline deviation.** The water mesh boundary equals the clipped OSM polygon within 1 mm (Hausdorff
   distance, both directions). The visible-shore metric (§AC0.2 measured on the rendered water mesh against
   the polygon) must be ≤ 0.5 m, against the ~s/4 staircase measured in AC0.
5. **Level.** Flatness/profile monotonicity to within 1 mm. The level lies within the shore-band [p5, p50]
   (§2).
6. **Clearances.** Bridge deck heights are unchanged within 0.1 m or raised. Piers reach the bed. All existing
   passage probes stay passable (D98 method). The `.mbcol` traversal tests are green.
7. **Both paths.** CLI and headless Blender builds of both presets are VALID. The C# reader reads them
   (D53.1). Blender bake/export emit the water objects with class `water` and the same triangle counts as the
   CLI plan.
8. **Format.** No version bump. The frozen v0.3.0 C# reader loads the new Pittsburgh-style sample. NOTICES is
   unchanged except for the texture entry D86 already requires.
9. **Performance (D91).** Whole Generate on real data (Pittsburgh), offline, same host: ≤ +5 % on both the CLI
   and the Blender path. Stage timings are informational.
10. **Tests.** New tests ≤ 5 s in total, with no wall-clock gates.

## Performance considerations

* The level statistic is O(shore samples). The carve is O(grid vertices × bodies near them): use the bbox
  prefilter plus one point-in-polygon pass per vertex in the dilated bbox. The distance-to-shore for the blend
  is computed only for vertices within k·s of a bbox. Never run a per-vertex `contains` over the whole grid
  against every multipolygon. AC0 showed that this is the slow path.
* Water meshes add triangles roughly equal to the polygon vertices plus the station cuts (hundreds, not
  thousands). Pittsburgh's rivers are the largest case; the triangle budget numbers go in the PR.
* Blender: the water objects must go through the same batch path as other landcover objects. No per-object
  operator calls.

## Expected tests

* `tests/test_water.py` (new, synthetic, ≤ 2 s):
  * a lake and a sloping river with an island hole: level = p20 of the shore band; flat or monotone; boundary
    Hausdorff ≤ 1 mm;
  * the no-terrain-above-water invariant on emitted triangles;
  * blend only lowers terrain;
  * the clipped edge is excluded from the statistic;
  * a budget refusal produces a named fallback.
* Bridge test (extend `tests/test_bridges.py`, ≤ 1 s): a bridge over a synthetic river keeps its deck height,
  its piers reach the carved bed, and the under-bridge probe starts at L + r and stays passable.
* `.mbcol` traversal: a downward ray over water hits class 5 at L, and a second query below L hits the bed.
* Blender headless integration (existing harness, no new Blender run in PR CI beyond what exists): water
  objects present, class `water`, triangle counts equal to the CLI plan.
* Sample: regenerate `examples/synthetic_sample.mbmap` in the sample slot (D103). Add a water body to the
  synthetic fixture only if it has none.

## Conflict domain

Hard:
* `core/generate.py` (build_terrain, build_plan landcover/terrain section, coverage);
* `core/water.py` (new: level, mesh, carve);
* `core/bridges.py` (`_ground_max` sampler, piers);
* `core/passages.py` or the probe placement in bridges (probe start height);
* `blender/scene_build.py` / `blender/bake.py` / `blender/export.py` (water objects, class mapping);
* `tests/test_water.py` (new), `tests/test_bridges.py`;
* `docs/PACKAGE_FORMAT.md` (water semantics, `.mbhf` note), `docs/UNITY_CORE_HANDOFF.md`.

Soft: sample slot (D103), `docs/VALIDATION.md`, `docs/demo/`.

It overlaps S4-COL-DEGEN (`core/collision.py`, `blender/bake.py`, `blender/export.py`) and the roof lane in
`core/generate.py`. It must therefore start after S4-COL-DEGEN merges and must not run in parallel with any
task that holds `core/generate.py` or `core/bridges.py`.

## Sprint fit (D112, coordinator)

**Ships in v0.5.0 (sprint 4).** It runs right after S4-COL-DEGEN merges, and before S4-REVIEW. This is the
user's direct request, and the user prefers infrequent releases. S4-REVIEW audits this task (check 3), and
REL-v0.5.0 carries the river renders and notes. While the task is open it takes the exclusive sample slot
(D103) and is the only writer of `core/generate.py` (terrain section) and `core/bridges.py`.

Size: one dev PR (about 2–3 days), plus the sample slot and renders. Split it into **S4-WATER-A** (level, mesh,
collision class, docs) and **S4-WATER-B** (carve, blend, bridges/probes) only if review asks. A is not useful
on its own: a flat sheet over an un-carved, undulating bed lets terrain poke through.