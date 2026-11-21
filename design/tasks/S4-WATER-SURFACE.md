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

## Pinned inputs and baselines (D90, D103, D106)

* **Base commit** = the main commit this task branches from, expected to be the S4-COL-DEGEN merge. Record its
  SHA in the PR. Every A/B in this task is base → head on that commit. The release check against v0.4.0
  (18f0822) is a separate measurement, made in S4-REVIEW check 4 and not here.
* **Presets and settings**: Pittsburgh (40.437, −80.016, 1200 × 1000 m) and Munich Altstadt (the committed
  preset). Both use terrain spacing 10 m, DSM correction on, seed 1, textures on, and the CLI defaults otherwise.
  Munich has **no water area** in its frozen data (only one `waterway=ditch` line). It is the **no-water path**:
  every gate is measured on both presets.
* **Frozen inputs**: the RC #56 caches identified by acquisition SHA-256 (D103), served offline through
  `design/bench/offline_guard.py` with 0 network attempts. The Overpass query text is part of the cache key
  (`core/cache.py:71`), so this task **must not change `osm.FEATURE_SELECTORS`** (§1).

## AC0: measured baseline first (D90)

On the base commit, for each preset, record a table in the PR body with one row per water area (Munich: one
row "0 water bodies, N/A"):

1. **Bed spread.** min, p10, p50, p90, max and range of z for the terrain vertices inside the polygon. N/A if
   no vertex falls inside.
2. **Shoreline deviation (staircase).** Area of the symmetric difference between the painted water cells and the
   clipped OSM polygon, divided by the non-clipped perimeter, in metres. Use exact clipping, or a ≤ 2 m raster
   with a bbox prefilter. N/A if that perimeter is 0. A naive per-vertex `contains` over the river multipolygons
   is too slow; this was measured while writing this spec.
3. **Shore band.** The §2 samples: their count, and p5, p10, p20, p30 and p50, per body and per station.
4. **D106 performance baseline**: the base-commit runs of AC9, on the same host as the head runs.

Numeric targets that depend on these numbers become final only after AC0 (D90). Each is written as a floor
plus the measured value.

## Scope

### 1. Inputs: water polygons and centrelines (D113)

The inputs are narrowed to what the current selectors already fetch, so the frozen caches stay valid.

* **Surfaces.** The `area_class == "water"` polygons after the existing ring validation
  (`landcover_ring_problem`), clipped to the area extent. Holes such as islands are kept. Today these come from:
  * `natural=water` ways and relations (this includes `water=river` and the other `water=*` values on them);
  * `landuse=reservoir|basin` ways and relations;
  * any fetched way or relation carrying `water=*`.
  
  **One classification edit, in two places:** closed `waterway=riverbank` ways are already fetched by
  `("way", "waterway")`, but today `_is_area_tagged` (`core/osm.py:767`) rejects them. `classify` therefore
  never forms an area, and the way falls through to the "waterway lines are not generated" report. The edit:
  * `osm.area_class` (`core/osm.py:1656`) returns `water` for `waterway=riverbank`. `_area_family` follows,
    so a riverbank way that is also the outer of a water multipolygon is still de-duplicated.
  * The area test in `classify`'s way loop (`core/osm.py:1155`) becomes
    `closed and (_is_area_tagged(tags) or _is_riverbank(tags)) and tags.get("area") != "no"`, where
    `_is_riverbank` is `tags.get("waterway") == "riverbank"`.
  * `_is_area_tagged` itself is **not** changed. Its other caller is the margin-only DSM mask scan
    (`core/osm.py:957`), and widening it there would assemble riverbank rings and charge them to the shared mask
    work budget. The DSM correction inputs and budget therefore stay byte-identical.
  * Report delta: a closed riverbank way leaves the "waterway lines" unsupported list and becomes a water area.
    Open riverbank ways stay in that list. The frozen Pittsburgh and Munich data contain no riverbank way, so
    neither preset changes. A unit test covers both the closed and the open case.
* **Centrelines.** `waterway=river|canal` ways are already fetched and today are only reported as unsupported
  (`core/osm.py:1187`). `osm.classify` additionally keeps their clipped polylines, with node order (the way
  direction is downstream), in a new `ClassifiedOSM.waterways` list. The unsupported report entry stays
  byte-identical, because the lines are still not generated as geometry. `stream`, `ditch` and `drain` are
  ignored.
* **Not covered (later; needs a selector change and new frozen caches, so not in v0.5.0):** a standalone
  `water=*` way or relation without `natural=water`, `waterway=riverbank` relations, and `natural=coastline`.
  Record this as an S4-Fn "later" item in S4-REVIEW.

### 2. Water level (D114)

All steps are deterministic. Ties and orderings use the OSM id, then the vertex index.

**Shore samples.** Walk the non-clipped shoreline edges, outer rings and holes alike, every s/2 = 5 m, starting at
each ring's first vertex. At each point, sample the **pre-carve corrected DEM** at outward offsets of 0.5, 1.0,
1.5 and 2.0 cells (the 0–2-cell band). For a hole, outward means into the hole. Discard samples that are outside
the terrain extent, inside a building, bridge or tunnel mask, or inside any water polygon. `N_min = 8`.

**Body kind.** The *centreline* of a body is the set of `waterways` parts that have ≥ 50 % of their length
inside the polygon.
* If there is no such part, the body is **flat**.
* Otherwise, chain the parts that share end nodes. The body is **flat** with the reported note
  `ambiguous centreline` when either of these holds:
  * more than one chain remains;
  * a part's direction contradicts its chain.
* With exactly one consistent chain, let ℓ be the chain length clipped to the polygon. The body is **flat** if
  ℓ < 300 m and **profiled** if ℓ ≥ 300 m.

**Flat level.** L = p20 of all the body's samples. If there are fewer than N_min samples, widen the band once to
4 cells. If there are still fewer than N_min, the outcome is `fallback(no shore samples)`.

**Profile.**
* Stations are 100 m along the chain, from the upstream end; a final remainder shorter than 50 m joins the
  previous station. Each sample goes to the station of its projection onto the chain; ties go upstream.
* A station with fewer than N_min samples merges with its downstream neighbour (upstream for the last station).
  Merging repeats until every station has at least N_min samples. If only one station remains, the body is
  flat, using the rule above.
* Each station's level is its p20. Pool-adjacent-violators makes the levels non-increasing downstream. Pooled
  blocks take the sample-count-weighted mean.
* **Slope cap.** The cap is checked locally, per adjacent station pair: |ΔL| / Δs must be ≤ 1 %. If any pair
  exceeds it, the whole body becomes flat, using the rule above, and is reported as `profile slope > 1 %`.
* The surface is linear in the chain parameter between station centres and constant before the first and after
  the last. The mesh is cut along the station lines, perpendicular to the chain.

**Sanity window (AC5).** For a flat body, L must lie within that body's sample [p5, p50]. For a profiled body,
each pooled block's level must lie within [min p5, max p50] over its stations. A miss is a reported warning, and
AC5 requires 0 misses on the presets.

**Why p20 of the shore band, not the cell heights inside the polygon.** Inside the polygon the DSM is exactly
the noisy signal that causes the ditch. Its minimum is the deepest radar artefact, and its median floats on the
noise. Banks are land: GLO-30 is reliable there, and the water line is the lowest stable part of the bank. p20 is
robust in both directions:
* embankments, walls and quays pull the median and maximum up;
* single low outliers pull the minimum and p5 down.

AC0.3 may move the percentile within p10–p30; record the choice in D114.

**Tolerance.** Emitted water vertex z equals the computed level or profile to within 1 mm. Flat bodies are flat
to 1 mm, and profiles are non-increasing to 1 mm.

**Outcome.** Every water area gets exactly one coverage outcome. Nothing is dropped silently.

| Outcome | Meaning |
|---|---|
| `built(flat)` | flat water surface |
| `built(profile, n stations)` | profiled water surface |
| `fallback(no shore samples)` | painted cells as today |
| `fallback(budget)` | painted cells as today |
| `fallback(carve invariant)` | painted cells as today |
| `unsupported(...)` | from the existing ring validation |

Notes such as `ambiguous centreline` or `profile slope > 1 %` go alongside the outcome. A **fallback body keeps
today's behaviour exactly**: painted cells, no water mesh, and no carve.

### 3. Water mesh

* One object per built body, `mb_id = water:<osm-id>`, class `water`, material `MB Water` (the S4-TEX-WATER
  neutral texture and colour). UVs follow the S3-UV-CORE planar tile-offset rule.
* Triangulate the clipped polygon with holes using `core/triangulate.py`, split at the station lines for
  profiles. All normals are +Z.
* Reserve `water:<id>` in the triangle budget before emission, as for terrain and roofs. A refusal gives
  `fallback(budget)`.
* Terrain cells inside water keep the water vertex colour, so the bed reads as water from below.

### 4. Ground model, bed carve and bank blend (D115)

**Two grids.** The *pre-carve ground* is the corrected DEM grid after `dsm.apply_correction`. Everything except
the terrain mesh keeps using it, unchanged:
* roads (draped at `ROAD_LIFT_M`, `core/generate.py:1423`);
* building bases;
* bridges and tunnels;
* the clearance floors (§5).

Only the emitted `terrain:grid` mesh uses the *carved grid*. Topology and `grid_layout` are unchanged.
`z_offset` is still taken from the pre-carve grid, so local z may go below 0 by up to the carve depth. The
package format allows negative z. On a no-water preset (Munich) the package bytes are therefore unchanged (AC10).

**Carve (conservative).** A cell *overlaps* a body if the exact intersection of the cell's square with the
clipped polygon has positive area (bbox prefilter). For every grid vertex v whose four adjacent cells include a
cell that overlaps a built body:

`z_v := min(z_v, min over those cells c of Lmin(c) − D)`, with **D = 1.5 m**.

Lmin(c) is the minimum water level over c ∩ polygon: L for a flat body, or for a profile the minimum at the
vertices of that clipped region. Every terrain triangle that overlaps water lies in one overlapping cell, and all
three of its vertices are ≤ Lmin(c) − D. A planar triangle is therefore below the water everywhere over the
overlap, including where a station break crosses the cell.

**Inside the polygon the carve always wins.** It makes no exception for roads, buildings or abutments, so no
terrain can poke through.
* **At-grade roads over water** (not a bridge or tunnel): the road mesh is preserved. It stays draped on the
  pre-carve ground, independent of the bed. It is reported per body as `at-grade road over water: <road id>,
  length inside, length below L`, and it is not "fixed": this is an OSM data issue, for example a ford or an
  untagged causeway. Shoreline acceptance (AC4) is unaffected, because the water mesh is still the exact
  polygon.
* **Buildings whose footprint overlaps water** keep their pre-carve base. Their walls extend down to the carved
  bed, like piers, and they are counted in the report.

**Bank blend** over k = 1 cell (k = 2 if AC0.3 shows banks steeper than 1:1). This applies only to vertices
outside every polygon that were not already carved, and it only lowers terrain:

`z := min(z, L_near + (d/(k·s))·(z − L_near))`

Here d is the distance to the nearest non-clipped shoreline, and L_near is the level at that shoreline point.
Vertices under building footprints, bridge abutments or road ribbons are excluded from the blend, so roads and
foundations on the banks are not undercut.

**Invariant, enforced on the final emitted triangles (D39).** For every pair of a terrain triangle and a water
triangle whose xy projections overlap (bbox prefilter by cell), clip the two triangles against each other.
Because both triangles are planar, the maximum of z_terrain − z_water over the overlap is reached at a vertex of
the clipped polygon, so evaluating those vertices is exact. The maximum must be ≤ 0, and the per-body maximum is
reported.

**Bounded remedy:**
1. If the check fails, for example through float rounding, lower the three vertices of each offending terrain
   triangle by (violation + 0.01 m), then re-check. Do this at most 2 times.
2. If the check still fails, the body becomes `fallback(carve invariant)`, and it is removed from the active set.
3. **The carve is recomputed, not restored.** The carved grid is a pure function of the active body set:
   z_v = min(pre-carve z_v, carve_b(v), blend_b(v), remedy_b(v) over the active bodies b). Each body's carve,
   blend and remedy deltas are recorded per body, and a remedy lowering belongs to the body whose check
   triggered it. When a body falls back, every vertex in its footprint (carve, blend and remedy) is recomputed
   from the bodies that remain. A vertex shared with a neighbouring active body therefore keeps that body's carve.
   It is neither reset to the pre-carve height nor left at the dropped body's depth.
4. The invariant is then re-run for every active body that touches a recomputed vertex. A new failure goes
   through steps 1–3 again. Each round removes at least one body, so the loop ends after at most as many rounds
   as there are bodies. The final check runs on the final geometry, and the order is deterministic (ascending
   body id).

The same check runs on Blender's baked triangles (AC7).

### 5. Bridges, piers and probes (D116)

* **Pre-carve deck floor.** Today's deck rule uses `_ground_max` (`core/bridges.py:110`) on the **pre-carve
  ground**, so decks never drop. The new rule is

  `ground = max(_ground_max(pre-carve), Wmax(section)) + ROAD_LIFT_M`

  Wmax(section) is the **exact** maximum water level along the cross-section through (x, y): the maximum over the
  section's intersections with water-triangle edges and its endpoints that lie inside water. It is not sampled,
  so narrow water between `SEGMENT_SAMPLE_M` samples is not missed. D22 clearance is then measured over the
  highest surface a drone can hit.
* **Piers** take their top from the deck and their base from the carved bed: the lowest carved terrain under the
  footprint minus `PIER_SINK_M`. `PIER_MIN_CLEARANCE_M` uses the same `ground` as the deck.
* **Under-bridge probe.** Its height is the highest surface under the **whole capsule footprint** plus a margin.
  The footprint F is the xy projection of the swept capsule: the probe segment's projection dilated by the
  radius r = `PROBE_RADIUS_M` (1.0 m). It is represented conservatively by a polygon that contains it, with
  each round end replaced by a circumscribed 8-segment half-polygon. For a probe whose F intersects a built water
  body:

  `z = max(_ground_max(pre-carve, reach), Gmax(F), Wmax(F)) + UNDER_PROBE_HEIGHT_M`

  * Gmax(F) is the exact maximum of the **pre-carve** terrain triangles over F. It is evaluated at the vertices
    of each triangle ∩ F clip; this is exact because each triangle is planar.
  * Wmax(F) is the same exact maximum over the water triangles ∩ F.
  * The pre-carve ground is used because it is never lower than the carved terrain mesh, and it bounds the
    building and road bases, which stay on it.

  The capsule's lowest point is z − r. With `UNDER_PROBE_HEIGHT_M = 1.5 m` and r = 1.0 m, the capsule is
  therefore at least **0.5 m** above both water and ground **everywhere over F**, not only along the centre
  segment. A probe whose F touches no water keeps today's rule, `max(_ground_max(pre-carve, reach))` + 1.5 m,
  so no-water packages stay byte-identical (AC10). The 4 m
  `UNDER_PROBE_MIN_CLEARANCE_M` rule is evaluated against the same height. Blocked probes stay listed and are
  not emitted (D21).

### 6. Collision and query semantics (D117)

* Water surfaces are emitted to `.mbcol` as **class 5 `water` (kind surface, normal Z > 0)**. The class, kind,
  members and layout already exist, and the frozen v0.3.0 and current C# readers accept them. This is **no format
  change** under D101/D110: no new member, role or format number.
* Semantics (documentation only; the simulator repo is read-only):
  * Water is a surface, reported with its class, so the consumer can treat it as a crash, splash or float.
  * A downward query over a built body hits `water` at L first. The bed (`terrain`) lies at least D below it.
* **`.mbhf` stays terrain-only.** It derives from the final terrain (`docs/PACKAGE_FORMAT.md:502`), so at
  covered grid points it reports the carved bed. `docs/PACKAGE_FORMAT.md` and `docs/UNITY_CORE_HANDOFF.md` must
  state that consumers need the `.mbcol` query, not the heightfield, for altitude above the surface over water.
* GLB: one mesh per built body with the existing `MB Water` material. No glTF extension is needed.

## Acceptance criteria

1. **AC0** baseline table (above), both presets.
2. **Renders.** Cycles CPU before/after renders with the demokit cameras `pittsburgh-bridge-under` and
   `pittsburgh-overview`, in the PR and later in `docs/demo/`. They must show:
   * a level water surface;
   * a shoreline that follows the OSM polygon;
   * no blue trough;
   * no terrain poking through.
3. **No terrain above water.** The §4 invariant passes on the final emitted triangles of both presets, the
   synthetic sample and the CLI and Blender outputs: 0 violations, with the per-body maximum reported. Every
   water area has exactly one outcome (§2), and every fallback has a named reason. The Pittsburgh river bodies
   (`water=river`) must be `built`; any other fallback is listed.
4. **Shoreline.** For each built body, the water mesh boundary equals the clipped polygon within 1 mm
   (Hausdorff distance, both directions). The AC0.2 metric, measured on the water mesh, is ≤ 0.5 m, against the
   staircase value AC0 measured.
5. **Level.** The §2 tolerance holds, and there are 0 sanity-window misses on the presets.
6. **Bridges, piers and probes.**
   * Every deck vertex is ≥ its base-commit height − 1 mm, so decks are never lowered. Raised decks are listed.
   * Piers reach the carved bed.
   * Every emitted under-probe whose footprint touches water clears the exact pre-carve ground and water
     maximum over its whole capsule footprint by ≥ 0.5 m (§5), checked on the emitted package.
   * Both replays (§7) pass.
7. **Both paths.** CLI and headless Blender builds of both presets are VALID (D53.1), and the C# reader reads
   them. Blender emits the water objects with class `water` and the same triangle counts as the CLI plan. The
   §4 invariant holds on Blender's baked triangles.
8. **Format.** No version bump. The frozen v0.3.0 C# reader loads the regenerated sample and the Pittsburgh
   package. NOTICES changes only as D86 already requires.
9. **Performance (D91, D106).** Measurements:
   * independent, same-host and offline;
   * alternating base/head runs, ≥ 3 per revision and preset;
   * medians compared, base commit → head, on both presets.

   | Measure | Tool | Gate |
   |---|---|---|
   | CLI whole Generate (acquire from the frozen cache + plan + package) | `design/bench/cli_time.py` | ≤ +5 % |
   | Headless Blender **Generate+Export** | `design/bench/bl_time.py` | ≤ +5 % |
   | Blender Generate | `design/bench/bl_time.py` | reported separately |
   | Stages | either harness | informational |
10. **No-water path.** The Munich CLI package is byte-identical to the base commit with fixed time, textured and
    untextured.
11. **Tests.** The new focused tests take ≤ 5 s in total. Report their timing in the PR (`unittest -v` durations);
    no test asserts on wall-clock time.

### 7. Probe and query replays (two separate checks)

**(a) Fixed-query replay.**
* Freeze the query coordinates on the base commit: the D98 probe set of S4-COL-DEGEN (passage probe paths as
  they are on base, the deterministic ray and capsule grid, and the centroid rays), plus one downward ray per
  built water body at its polygon's pole of inaccessibility.
* Run them against the base and head packages in Python and C#, and compare hit/miss, distance (1 mm) and class.
* Every difference must appear in a listed, classified change set:
  * new `water` hit;
  * bed moved (terrain hit lower);
  * deck raised;
  * pier extended;
  * building wall extended.

  An unlisted difference fails. Python and C# must agree on every query.

**(b) Regenerated-passage replay.**
* **Same-id rule:** every passage id present on base exists on head, **unless** it is in the listed drop set
  with its D21 reason. A missing id that is not listed fails, and so does a listed drop that is actually present.
* Every surviving id is validated passable on its **regenerated** path (its new height), in Python and C#.
* New and newly blocked ids are listed with their D21 reason too. An unlisted new or blocked id fails.

The S4-COL-DEGEN hit-equivalence result (D98, D111) is a separate check. It is judged on that PR's own base →
head comparison and is not re-judged against this task's intentional changes.

## Performance considerations

* The shore samples are O(perimeter / 5 m × 4). The carve visits only vertices of the cells that overlap a
  body's dilated bbox, with exact cell∩polygon clipping. The blend computes distances only within k·s of a bbox.
  The invariant check pairs triangles by cell. A per-vertex `contains` over the whole grid against every
  multipolygon is forbidden: it is the slow path seen while writing this spec.
* Water meshes add about the polygon's vertex count plus the station cuts in triangles (hundreds). The PR
  reports the triangle-budget numbers.
* Blender: the water objects use the same batch path as other landcover objects, with no per-object operator
  calls.

## Expected tests

All focused tests are synthetic and their timings are reported (AC11).
* `tests/test_water.py` (new, ≤ 3 s):
  * a lake, and a ≥ 300 m sloping river with an island hole: level = p20, flat or monotone, boundary Hausdorff
    ≤ 1 mm;
  * the 300 m boundary (299 m flat, 300 m profiled);
  * fewer than N_min samples, the widened band, then `fallback(no shore samples)`;
  * an empty station merged downstream;
  * two competing chains, and one reversed part (`ambiguous centreline`, flat);
  * the local slope cap, giving a body-wide flat level;
  * a clipped edge excluded from the samples;
  * a budget refusal, giving `fallback(budget)` with today's painted cells;
  * a **station break crossing a grid cell**: the exact invariant on the emitted triangles;
  * a **protected at-grade road across a flat lake**: the road unchanged on the pre-carve ground, terrain
    carved, the invariant passes, and the road is reported;
  * the blend only lowers terrain and skips road, building and abutment vertices;
  * a forced invariant failure, giving the bounded remedy and then `fallback(carve invariant)`;
  * **two adjacent bodies sharing grid vertices**, one forced to fall back: the shared vertices keep the
    remaining body's carve, its invariant still passes, and vertices touched only by the dropped body return to
    the pre-carve height;
  * `osm.classify` on a closed riverbank way (a water area, not in the unsupported list) and an open one
    (unchanged unsupported entry), with the DSM mask candidate list unchanged.
* `tests/test_bridges.py` (≤ 1 s):
  * a bridge over a synthetic river: the deck is not lowered and the piers reach the carved bed;
  * a **mixed bank/water span** where water lies between `_ground_max` samples, and a bank peak lies under
    the capsule's edge but off the centre segment: the height is max(Gmax(F), Wmax(F)) + 1.5 m, with Gmax
    and Wmax exact over the footprint, and the capsule clears both by ≥ 0.5 m everywhere over F;
  * a probe that touches no water keeps today's height bit for bit.
* `.mbcol` traversal (≤ 1 s): a downward ray over water hits class 5 at L, and a ray started below L hits the
  bed; Python and C# agree.
* Blender headless integration (existing harness): water objects present, class `water`, triangle counts equal
  to the CLI plan, and the invariant on the baked triangles.
* Sample: regenerate `examples/synthetic_sample.mbmap` in the sample slot (D103). Add a water body to the
  synthetic fixture if it has none.

## Conflict domain

Hard:
* `core/generate.py` (build_terrain, build_plan landcover/terrain section, coverage);
* `core/water.py` (new: samples, level, mesh, carve, invariant);
* `core/osm.py` (`area_class` riverbank rule; `classify` area test and `waterways`; `_is_area_tagged` and selectors unchanged);
* `core/bridges.py` (deck ground rule with exact Wmax, piers, `_under_probe` height);
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