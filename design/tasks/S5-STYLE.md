# S5-STYLE: stylized low-poly look for the GLB visuals (direction and tasks)

Owner: design (direction); dev (tasks below) · sprint S5 · decisions D136–D145, D153, D156, D157

## User direction (verbatim)

> 你参考背景的地图风格，你的地图不用追求逼真，而是首先好看，不要求高硬件，然后才尽量还原真实地图。
>
> 高度和碰撞数据必须准确，因为飞行依赖这个

> 其他的你先尽量选择最优，推进项目，不要等我

The reference is a stylized low-poly cartoon map. Only its background terrain art counts, not the UI overlay. The
image is not committed. Its palette is sampled below, and the coordinator holds the full image.

## Priorities (D137)

1. **Looks good.** The output matches the reference style: saturated, bright and readable from drone height.
2. **Low hardware cost.** It is cheap to render on low-end and mobile GPUs. This is measured, not assumed; see
   the budgets.
3. **Real-map fidelity.** Every object stays where OSM and the DEM put it, and landcover keeps its real class.

## G0: the flight-data gate (every S5 task, no waivers)

Flight depends on height and collision, so G0 sits above all three priorities. It is one gate, run by
`tools/style_check.py` (S5-STYLE-BASE) on the task's base and head.

* **Packages:** the sample, Munich, Pittsburgh and Bellevue-Factoria (D157). Wherever this spec lists
  "the sample, Munich and Pittsburgh", Bellevue-Factoria is included from S5-STYLE-BASE onwards.
* **Paths:** the CLI and headless Blender.
* **Modes:** stylized and classic.
* **Pinned settings:** frozen caches, seed 1, DSM on, offline, `created_utc = "2026-11-20T00:00:00Z"`, and the
  same export options on both sides.

G0 requires:

1. `collision/map.mbcol` and `collision/terrain.mbhf` are **byte-identical**.
2. `manifest.georeference` (the whole object) and `manifest.passage_probes` are exactly equal (JSON equality, no
   tolerance).
3. `report.json` `passage_probes_blocked` and `passage_probes_dropped` are exactly equal.

`tools/style_check.py` must fail on each of these negative cases: one `.mbcol` byte flipped; one `.mbhf` byte
flipped; one probe moved by 1 mm; one georeference field changed; one probe status changed (passable → blocked,
and exported → dropped).

**No S5 task has a geometry exception.** Tree and water styling are appearance-only (D143, D145). A future change
to collision geometry is a separate task that needs explicit user approval. Its spec must then add:

* a per-object comparison proving every object outside the changed class is byte-identical in `.mbcol`;
* explicit geometric criteria (surface, holes and the class of every triangle);
* query-equivalence criteria (ground height and capsule clearance) for the changed objects.

## Classic mode stays exactly as it is today (D141)

Stylized is the default (U1, user). Classic stays available. In **classic** mode, every S5 task keeps the
**whole `.mbmap` archive** byte-identical to main before S5. This covers the sample, Munich and Pittsburgh, through
the CLI and Blender, with the G0 settings.

Between classic and stylized on the same head, only these may differ, so each change is attributable to the mode:

* `visual/map.glb`;
* the manifest `files[]` hashes and `package_id`;
* `asset_notices` and NOTICES (stylized embeds no textures);
* one `report.json` options entry, `style`.

The PR lists every changed member.

## Visual versus collision (D138)

The exporter refuses to publish unless each node's visual and collision triangles correspond one-to-one
(`docs/PACKAGE_FORMAT.md:187–193`). The validator also rejects a glTF node with triangles but no same-name
collision object ("visible but not collidable", `core/package.py:1747`), and so do the frozen readers. Trees are
class 4 `vegetation` in `.mbcol`. The rule **stays** for every S5 task except S5-DECOR:

* Anything that looks solid is in collision with the same triangles.
* The look comes only from attributes that are not geometry: vertex colours (`COLOR_0`), material parameters,
  normals, and the visual vertex layout (welding).
* Unwelding visual vertices is allowed only if the exporter correspondence check still passes and G0 holds.
* The only planned exception is S5-DECOR, last in the sprint. It covers visual-only decoration ≤ 0.3 m (D142,
  user), and it is contingent on its own compatibility proof.

## Target look (palette sampled from the reference, sRGB)

The swatches include the reference's lighting, so they are targets for the **rendered** result under the
acceptance setup, not raw vertex colours. `core/style.py` stores linear values.

| Element | Target sRGB |
|---|---|
| Grass, light / mid / shaded | `#b9d17a` / `#96b671` / `#7ea55b` |
| Tree foliage, lit / mid / shadow side | `#6f934e` / `#39864c` / `#3d6e69` |
| Water, open / shallow shore band | `#6dc0e7` / `#ceeef6` |
| Sand bank / footpath | `#f2dcae` / `#fdeaa2` |
| Cliff, lit / shadowed faces | `#d4b590` / `#70828b` |
| Rock | `#88909c` |

How each element is styled:

* **Lighting.** Materials are lit (U4, D144): standard glTF metallic-roughness, roughness ≈ 1, metallic 0, opaque.
  There is no alpha blending and no extension. `KHR_materials_unlit` may be revisited after S5-STYLE-REVIEW.
* **Faceting.** A primitive without `NORMAL` must be rendered with flat normals (glTF 2.0 specification, mesh
  attributes). S5-STYLE-PALETTE measures dropping normals against unwelding, using the validator's orientation
  probes and the runtime proxy, and picks the one that passes and costs less.
* **Terrain** is coloured per face by OSM landcover, then by slope: faces of ≥ 35° use the cliff colours, lit or
  shadowed by facing. A bank band (≤ 6 m from a built water body, plus every `bank:` ramp face) uses sand.
* **Water and its shore** (U3, D143): **colour only** on the existing triangles. Water bodies get open cyan.
  The light shore band goes on the terrain-side faces next to water (and on the `bank:` ramps), using the
  shallow-band colour blending into sand. The water is not re-triangulated.
* **Trees** (D145): the current tree mesh is already a faceted bicone, and its triangles stay unchanged. Style
  comes from colours: per-face foliage shading (lit, mid or shadow by facing), a deterministic tint variant from
  the OSM id or scatter index, and the bark colour. A new tree **shape** changes `vegetation` collision, so it is
  deferred (S5-F1) and needs explicit user approval.
* **Buildings** use a soft pastel wall palette and a few saturated roof colours. Tagged `building:colour` and
  `roof:colour` keep their hue but are pulled into the palette. There are no facade textures.
* **Roads** are light warm grey; footways, tracks and paths are sand-coloured. Ribbon geometry is unchanged.
* **No textures** in stylized mode: 0 embedded image bytes and no `asset_notices`. Classic keeps today's textures.

## Low-end budgets (D139)

S5-STYLE-BASE records the **classic** baseline on main at the S5 start, for the sample, Munich, Pittsburgh and
Bellevue-Factoria (D90, D157). The stylized mode does not exist yet; S5-STYLE-PALETTE records the first **stylized**
baseline. Pittsburgh is the sizing case; Bellevue-Factoria is the main visual example.

**Per-PR rule (replaces the earlier cumulative rule).** Every S5 PR is judged against **its own merge-base**, same
mode. The first stylized PR (PALETTE) is judged against the classic merge-base. Absolute caps (materials ≤ 8,
0 texture bytes) stay absolute. Generation cost is gated by D153 against the merge-base (timing rule below).
**Cumulative S5 drift** against the BASE classic baseline is reported once, at S5-STYLE-REVIEW, as **information**,
not as a gate.

| Item | How it is counted | Floor (must, vs the PR's merge-base) |
|---|---|---|
| Material definitions | glTF `materials[]` length | ≤ 8 |
| Draw submissions | Σ over rendered node instances of their primitives, counted statically from the GLB; trees count once per instance | ≤ baseline; S5-DECOR ≤ baseline + 2 % |
| Runtime frame time (proxy) | Labelled proxy, not a device: the vendored three.js viewer (`tools/demo/viewer/`) in headless Chromium with SwiftShader software rendering, 1280 × 720, fixed Pittsburgh overview camera; median frame time over 300 frames after 60 warm-up frames; same host, alternating base/head runs | ≤ baseline + 10 % |
| Render memory (proxy) | vertex-buffer bytes + index-buffer bytes + texture bytes in the GLB | ≤ baseline |
| Visual triangles | from the GLB | = baseline; S5-DECOR ≤ baseline + 10 % |
| Visual vertices | from the GLB | ≤ baseline × 2 (unwelding) |
| Embedded texture bytes (stylized) | images in the GLB | 0 |
| GLB size | bytes | ≤ baseline; S5-DECOR ≤ baseline + 10 % |
| Generation work (D153 gate) | D153 work vector for **CLI whole Generate**, **Blender Generate** and **Blender Generate+Export**, each separately, base = merge-base + counter commit C | F1–F3 pass; F4 and F6 answered |
| CPU sanity (D147, F5 only) | D147 CPU medians, 5 alternating rounds, the same three series | ≤ +5 % or explained under F5; not a gate |

Shaders: standard glTF PBR only, as imported by glTFast with its default URP shaders, mobile included. No custom
or required-extension shaders.

The contact-sheet render (D140) has its own time limit (≤ 2 min for all cameras). That limit is about producing
evidence quickly and is **not** a hardware budget.

## Blender and CLI parity, determinism

* One style module, `core/style.py`, is used by both paths.
* For the same inputs and settings, CLI and Blender packages have equal visual vertex colours and materials per
  node (`tools/style_check.py`), while today's collision and probe parity continues.
* Two builds are byte-identical. No randomness except seeded by feature id or scatter index, and no wall-clock
  or host data in the output.

## Consumer impact (drone-flight-simulator, read-only)

* **Flight is unaffected:** G0 keeps `.mbcol`, `.mbhf`, probes and georeference identical in every S5 task.
* **Visual import:** the same glTF feature set (`COLOR_0`, base colour, metallic-roughness, no extension), which
  glTFast imports as today. With no textures it is cheaper. If normals are dropped, that is standard glTF; the C#
  reader and the glTF-Validator proxy (D66) confirm it.
* **S5-DECOR:** decoration is visual-only. Consumers find it as a separate submesh with material `MB Decor` and can hide it (proven with glTFast in step 1b); it has no collision, and the
  simulator's `.mbcol` queries never see it.
* **Format:** schema stays 2.1.0 unless S5-DECOR's feasibility step fails (see that task). `package_id` changes
  for every stylized package.
* The simulator owner's visual check is a user or owner action and is not claimed here.

## Visual acceptance method (D140)

1. **Cameras:** the demokit presets plus five style cameras: a Pittsburgh river bend with banks, a Munich
   roofscape, a forest edge on the sample, and two Bellevue-Factoria views (D157). Cameras are stored in
   `tools/demo/presets/`. **Every** S5 task's before/after evidence includes the Factoria cameras.
2. **Render:** Blender EEVEE, one sun and the world colour as soft ambient, 64 samples, 1280 × 720.
3. **Contact sheet:** for each camera, the reference crop (held by the coordinator), the base render and the head
   render side by side. It is attached to the PR, not committed (`docs/demo/` is for REL only).
4. **Palette report:** mean colour of fixed screen regions compared with the target table, as ΔE2000. This is
   information only; a value above 15 is flagged to the reviewer.
5. **Verdict:** the reviewer judges the sheet against the user's priority order. **S5-STYLE-REVIEW is an explicit
   GO/NO-GO** on the G0 evidence, classic identity, the per-PR budgets and the sheets; cumulative drift is
   information only.

## Acceptance example: Bellevue-Factoria (D157, user request)

> 后期检验效果的时候，生成一张Bellevue， factoria，这一片的map，作为example

| Field | Value |
|---|---|
| Preset id | `bellevue-factoria` (`tools/demo/presets/bellevue-factoria.json`) |
| Centre | 47.5790 N, 122.1790 W |
| Extent | 1600 m (E–W) × 1400 m (N–S); bbox S 47.5727, N 47.5853, W −122.1897, E −122.1683 |
| Settings | as the other presets: seed 1, DSM correction on, terrain 10 m, heightfield 2 m, textured, `created_utc` pinned |

Why this area (checked against OSM on 2026-11-24):

* **I-90/I-405 interchange edge:** the motorway junctions on I-90 (exits 10, 10A, 10B, 11) lie at about
  47.579–47.583 N, 122.177–122.189 W, inside the box; the 405 ramps run along the west part.
* **Factoria commercial buildings:** Marketplace at Factoria (`shop=mall`, centre 47.5745 N, 122.1726 W) and the
  surrounding commercial blocks south of I-90.
* **Residential streets and trees** east and south-east of the mall.
* **Water:** the southern `natural=water` ponds of the Mercer Slough area (ways 1537086924, 1537086925,
  1537086926 and 1062196544, at 47.584–47.586 N) and Richards Creek (`waterway=stream`) near the east edge.
  Mercer Slough's main multipolygon (relation 2315576) lies further north and is mostly outside; streams and
  standalone water polygons outside D113's built set are reported, not built (S4-F3).

Size: 2.24 km², about 1.9× Pittsburgh's area, inside the D3 limits (50–2000 m sides). **Build time** (D102.9,
≤ 120 s per path) uses the D91 boundaries: CLI = acquisition from the frozen cache through package write and strict
validation; Blender = Generate+Export measured inside Blender. BASE reports the median of 3 D147 runs per path;
on this shared host the number is **information only**, not a gate.

**Preset roles.** Munich and Pittsburgh are the **gating** presets for S5-PERF-GATE and the D153 work-vector gate
(as that spec says). The sample and Bellevue-Factoria are **evidence-only**: they are in G0, classic identity, the
budgets table and the visual evidence, but not in the D153 gate.

**Cache custody.** The Factoria caches are acquired once and frozen **outside the repository**, with the same
location and custody as the existing frozen caches (`cache-munich`, `cache-pittsburgh`; roadmap "Measured
baselines", pinned setup): kept in the Team Leader Project's files (`frozen-caches/`, with `MANIFEST-sha256.txt`; D163) because the release manager is on demand, never committed, copied fresh
for every run, and identified only by their acquisition SHA-256 (per file and combined). The repository holds only
`tools/demo/presets/bellevue-factoria.json` and the recorded hashes (in the BASE PR and the D157 row). CI never needs
the caches. **Allowed adjustment:** if the first build shows the mall or the
pond group clipped, BASE may move the centre or change a side by at most 200 m; the PR records the final values
and Design updates this table and D157 before PALETTE starts. Multi-level interchanges beyond `layer` clearance
are a v2 non-goal: they appear in `unsupported_features` and do not fail the build.

## Scheduling and shared files (D136)

* **One start gate:** S5 implementation starts after the REL-v0.5.0 RC PR (#75) has **merged into main**.
  Tagging and publishing v0.5.0 are separate user decisions and are not S5 gates.
* **Shared files:** S5 overlaps v0.5.0 work. The rule is **no simultaneous edits**, not no overlap:

| S5 task | Shares with | Files |
|---|---|---|
| S5-STYLE-PALETTE | #77 (S4-COL-FLOAT-2) | `core/generate.py` |
| S5-STYLE-PALETTE | S4-MYPY, after its triage | the files with mypy errors (likely `core/generate.py`, `core/glb.py`) |
| S5-STYLE-PALETTE | #75 | the sample slot (D103), when the default changes to stylized |
| S5-STYLE-WATER | #77 | `core/water.py`, `core/shore.py`, `core/generate.py` (water stage) |
| S5-DECOR | #77 | `core/package.py` (validator), if the feasibility step needs a format change |

* **The design PR itself:** S5-STYLE only shares `design/tasks/README.md` with #75's hunk, which is scheduled for
  removal (D125, D133).

## Tasks

Every implementation task meets **G0**, **classic identity**, the **per-PR budgets** and the **timing rule**
(below), and attaches the contact sheet and the palette report. Test budget: D134 (≤ 5 s per test, no
wall-clock asserts, no duplicate cases; renders and real-data runs are PR evidence only).

**Timing rule (D153, D147).** The **gate** is the D153 deterministic work vector (F1–F3 must pass; F4 and F6 are
answered in review), measured with the checker and counter commit C pinned in D153 against base = merge-base + C.
**D147 CPU time** (5 alternating rounds, three series) is the **F5 sanity check only**: a series above +5 % must be
explained, but CPU time never passes or fails a task by itself. This replaces every earlier "D91/D106 timing,
≤ +5 % per series" rule in this spec. Before S5-PERF-GATE merges (S5-STYLE-BASE only), CPU timing is recorded for
information and nothing is gated on time.

**Pinned work-vector baseline.** S5-STYLE-PALETTE's first step records the S5 work-vector baseline (D153 checker
and C at their pinned commits, the merge-base SHA, the interpreter, and all four presets) as a roadmap row next to
D153. Every later S5 task compares its own base against that row as well as against its own merge-base.

Order (D156, D161): **BASE** (in parallel with S4-F8 and S5-F3 step 1) → S5-PERF-GATE → S5-F3 fix (if any) → **PALETTE** → **WATER** → S5-PERF-WATER → **REVIEW**, then **DECOR** last. Nothing waits on DECOR.

### S5-STYLE-BASE: baselines, metrics, G0 checker and acceptance harness

* **Change:**
  * `tools/style_check.py` (new): G0 and its negative cases; classic whole-archive identity; the member diff
    between classic and stylized; every budget row (materials, draw submissions, render memory, triangles,
    vertices, texture bytes, GLB size); per-node CLI-versus-Blender colour and material parity; and the palette
    regions for given renders;
  * the runtime frame-time proxy runner (headless Chromium, SwiftShader, the vendored viewer);
  * the three style cameras and the render and contact-sheet recipe in `tools/demo/`;
  * the **`bellevue-factoria` preset** (D157): `tools/demo/presets/bellevue-factoria.json` and two Factoria
    cameras (an interchange-and-mall overview, and a low street-level view with trees and water). The preset's
    caches are acquired **once** and then frozen and used offline, kept outside the repository under the custody
    rule above; the PR records the acquisition SHA-256 per cache file and the combined hash.
* **ACs:**
  1. The **classic** baseline table (every budget row, classic mode only, the sample, Munich, Pittsburgh and
     Bellevue-Factoria, CLI and Blender, plus D147 CPU time for the three series, information only) is posted in the PR. Design records it
     in the roadmap. **Conditional refresh:** if S4-F8 merges as case (B) and changes any package, AC1 is re-measured
     on the post-S4-F8 main before PALETTE starts; if S4-F8 is case (A), the AC1 table stands.
  1a. **Bellevue-Factoria builds VALID** on the CLI and Blender, classic mode, offline from its frozen caches. G0
     data (`.mbcol`, `.mbhf`, georeference, probes) is recorded as the classic baseline. Unsupported features (for
     example a multi-level interchange beyond `layer` clearance, a v2 non-goal) are listed in
     `report.json` `unsupported_features` and are not a failure; a failure to build or validate is. The
     floating audit result is posted, and any finding becomes an S5-Fn row. Build time per path (D91 boundaries,
     median of 3 D147 runs) is reported against the ≤ 120 s target (D102.9), information only.
  2. `tests/test_style_check.py` covers each G0 negative case and one classic-identity negative case (a single
     GLB byte change).
  3. The frame-time proxy repeats within ±5 % over three runs of the same package on the pinned host; otherwise
     the PR proposes a more stable proxy before PALETTE starts.
  4. The render recipe produces all cameras in ≤ 2 min.
  5. No generator output changes; the sample is byte-identical.
* **Conflict domain:** `tools/style_check.py`, `tests/test_style_check.py` (both new), `tools/demo/` (presets,
  including the new `bellevue-factoria.json`, recipe, proxy runner); soft: `tests/test_demo_bundle.py` preset rows
  if that test enumerates presets. No `core/` edits.
* **Dependencies:** #75 merged (D136; done at 6535f38). Runs in parallel with S4-F8 (D156): the domains are disjoint while S4-F8 stays case (A), which edits only `tools/floating_audit.py` and its tests. AC1's conditional refresh covers S4-F8 case (B). BASE changes no product code and runs before the counters exist, so its timing is D147 CPU time for information; the gated work-vector baseline is pinned by PALETTE's first step (timing rule above).

### S5-STYLE-PALETTE: style option (default stylized), palette, faceting, terrain, buildings, roads and trees

* **Change:**
  * `core/style.py` (new): the palette; the slope, bank-band and road-class rules; the building and roof mapping;
    and tree tinting and facet shading;
  * a `style` option (`"stylized"` by default, or `"classic"`) in the CLI, Blender properties and
    `GenerateOptions`;
  * faceting by dropping `NORMAL` or by unwelding, whichever is measured best;
  * no textures in stylized mode.
* **ACs:**
  1. G0, classic identity and the per-PR budgets on every package and path. First step: record the **stylized**
     baseline (every budget row, all four presets) beside the BASE classic table.
  2. Visual triangles equal to the baseline per node; only colours, materials, normals and welding change.
  3. Parity and determinism, as above.
  4. glTF-Validator (D66), the current Python validator and C# reader, and the frozen v0.3.0 readers accept a
     stylized sample. This is the same check as the existing CI step, run on the new sample.
  5. Contact sheets for every camera (water is still classic-coloured, which is expected).
  6. The default switch regenerates `examples/synthetic_sample.mbmap` only under the D103 slot. The PR lists the
     member changes.
* **Tests:** palette rules (slope threshold, bank band, road classes, a tagged colour pulled into the palette, a
  deterministic tree tint); classic byte identity on the sample; one Blender check that the option is present and
  defaults to stylized.
* **Conflict domain:**
  * Hard: `core/style.py` (new); `core/generate.py` (the `LANDCOVER_COLORS`, `MATERIALS`, `FACADE_PALETTE` and
    `ROOF_PALETTE` constants and the colour choice in `build_terrain`, buildings, roads and `tree_mesh` colours;
    **no geometry code**); `core/glb.py` (normals and welding); `core/uv.py` and `core/textures.py` (mode switch
    only); `tools/mbmap_cli.py` (flag); `blender/props.py`, `ui.py` and `scene_build.py` (option).
  * Soft: sample slot (D103).
* **Dependencies:** S5-STYLE-BASE, **S5-PERF-GATE** and the **verified closure of S5-F3** (D161: the measured `water_above_bank`/`water_buried` zero gate passed on main, plus the rebaseline if packages changed; an implementation merge only if one was needed) (D156; PALETTE shares `generate.py` and `blender/scene_build.py` with the counter commit). #75 and S4-MYPY are merged. First step: record the S5 work-vector baseline (D153 checker, merge-base + C) beside the BASE table.
* **Step 1 also (D163):** re-frame the Factoria ponds camera so it shows the southern Mercer Slough ponds (the
  #85 framing shows grey foreground only). Record the new camera in `tools/demo/presets/` before any stylized evidence.

### S5-STYLE-WATER: cyan water, terrain-side shore band, sandy banks (colour only)

* **Change:**
  * water body colour;
  * the shallow-band and sand colours on the terrain faces next to built water and on the `bank:` ramps, colour
    only (D143);
  * no new vertices, no re-triangulation, no transparency.
* **ACs:**
  1. G0, classic identity and the per-PR budgets. Visual triangles per water, terrain and `bank:` node are
     unchanged.
  2. The S4-COL-FLOAT-2 floating audit is unchanged from the base (0 `water_above_bank`, 0 `water_buried`).
  3. Contact sheets with the river-bend and bridge-under cameras; the palette report includes the shore band.
* **Conflict domain:** `core/style.py` (water and band colours), the water-stage and `bank:` colour code in
  `core/generate.py`, `core/water.py` and `core/shore.py` (colour only); soft: sample slot.
* **Dependencies:** S5-STYLE-PALETTE (it shares `core/style.py` and `generate.py`); U3 resolved as colour-only
  (D143); #75 merged, which means #77 has merged too.

### S5-STYLE-REVIEW: design milestone review (GO/NO-GO)

* **Scope:** `design/` only.
* **Evidence:** G0 and classic identity for every package, path and mode; each PR's per-PR budgets; the contact
  sheets; and the test audit (D134). **Cumulative S5 drift** against the BASE classic baseline (and PALETTE's
  stylized baseline) is reported as information only, not as a gate.
* **Main visual example (D157):** Bellevue-Factoria, classic vs stylized, from the two Factoria cameras, shown to the
  user next to the contact sheet against the reference. The GO/NO-GO states how Factoria reads against the user's
  priorities (looks good, low cost, fidelity).
* **Verdict:** explicit **GO or NO-GO**. A NO-GO names the failing evidence and the S5-Fn fix tasks.
* **Dependencies:** S5-STYLE-BASE, PALETTE and WATER, then S5-PERF-WATER (D156; byte-identical, so the review evidence is unchanged). S5-DECOR is not a dependency.

### S5-DECOR: visual-only decoration ≤ 0.3 m (last; contingent)

The user allowed it (U2, D142). It runs last and nothing else waits on it. If any step below fails, DECOR
**stops and escalates** to the coordinator, with Design proposing the minimal format change. BASE, PALETTE, WATER
and REVIEW are never blocked by it.

**Representation (the candidate within 2.1.0).** Decoration is one **additional primitive** in an existing
terrain node's mesh:

* its own material, `MB Decor`, used by nothing else;
* primitive `extras.mb_decor = true`;
* every triangle inside the host node's collision AABB, within the existing tolerance.

There are no new nodes or package members (D110), and the node name binding to `.mbcol` is unchanged.

**Marking that consumers can act on.** glTF importers, glTFast included, do not reliably expose `extras`, so the
**material name `MB Decor`** is the normative marker for consumers. `extras.mb_decor` serves readers that parse
the glTF JSON. Both are documented in `docs/PACKAGE_FORMAT.md` and `docs/UNITY_CORE_HANDOFF.md`.

**Step 1a, format compatibility (no merge).** The developer builds a **genuine exported package** with
decoration: the real exporter path, not a hand-made GLB. The fixture must show all of these:

* the current Python validator and C# reader report no new error or warning;
* the frozen v0.3.0 Python and C# readers accept it (the D101 positive fixture);
* the exporter's 1:1 GLB-to-`.mbcol` name binding still holds;
* the orientation probes pass;
* glTF-Validator is clean.

**Step 1b, the consumer can hide it (no merge).** This needs a minimal Unity project with **glTFast at the
simulator's pinned version** (URP). It lives outside the repository or under `tools/` as a script, never in the
simulator repo. The project imports the step-1a fixture, and its log, attached to the PR, shows:

* the terrain node imports as one mesh with a **separate submesh** whose material name is `MB Decor`;
* hiding that submesh alone leaves the terrain submesh and its triangle count unchanged. Hiding means removing
  the submesh or assigning a renderer material that draws nothing.

No Unity runs in CI (D66), so this is recorded PR evidence. If the pinned glTFast cannot be run, or does not
expose a separate submesh and material, DECOR stops and escalates.

**Flight corridors (designated, decoration-free).** The corridor set is the union of these XY regions, each
over the full height:

| Corridor | Region |
|---|---|
| Roads | every road ribbon's collision footprint, dilated 1.0 m |
| Water and banks | every built water body piece (outer minus holes) and every `bank:` ramp, dilated 1.0 m |
| Bridges and tunnels | the XY footprint of every `bridge`, `tunnel` and `structure` object (deck, piers, portals and approaches as emitted), dilated 2.0 m |
| Buildings | every building footprint, dilated 0.5 m |
| Passage probes | every passage-probe capsule (`manifest.passage_probes`): the swept segment dilated by capsule radius + 1.0 m clearance |

**Step 2, implementation (only after steps 1a and 1b pass).**

* Content: grass tufts, flowers and pebbles, placed deterministically (seeded by area id) on grass and forest
  landcover only.
* **Exclusion is tested on the emitted triangles,** using the exact area test in `core/overlap.py`: no
  decoration triangle overlaps or touches the corridor set. Boundary contact counts as overlap here, which is
  conservative.
* **Height cap, over the whole triangle:** for every decoration triangle, the maximum of (decoration Z − terrain
  surface Z directly below) over the **entire triangle area**, including its interior over terrain dips, is
  ≤ 0.30 m. Both surfaces are piecewise planar, so the check is exact when it evaluates the difference at every
  vertex of their XY overlay:
  * the decoration triangle's vertices;
  * the crossings of its edges with terrain triangle edges;
  * the terrain vertices that lie inside it.

  "Terrain" means the final emitted ground surface: the `terrain` class collision triangles, including the
  `bank:` ramps. There is no vertex-only or sampled shortcut.
* The exporter exempts only `MB Decor` primitives, and only from the 1:1 triangle correspondence; every other
  check stays.

**ACs:**

1. G0 holds: `.mbcol` and `.mbhf` are byte-identical with and without decoration.
2. Classic identity: no decoration in classic mode.
3. The DECOR budget rows (draw submissions ≤ baseline + 2 %, triangles and GLB ≤ baseline + 10 %).
4. The steps 1a and 1b fixture and its evidence: 1a persisted as a CI test, 1b attached to the PR.
5. On the sample, Munich and Pittsburgh: 0 decoration triangles in the corridor set, and the maximum
   whole-triangle height over terrain ≤ 0.30 m, both reported.
6. Contact sheet.

**Tests (≤ 5 s each), all on synthetic inputs:**

* a decoration triangle partly inside a dilated road, inside a probe capsule plus clearance, or on a bridge
  envelope is rejected;
* a 0.31 m decoration instance is rejected, and a 0.30 m one is accepted;
* **straddle over a dip:** a flat decoration triangle whose three vertices are each 0.20 m above the terrain, but
  which spans a terrain vertex lowered by 0.15 m inside it (0.35 m gap at that point), is rejected. The same
  triangle over flat terrain is accepted;
* the exporter exempts `MB Decor` primitives only; an unmarked extra primitive still fails the binding.

**Conflict domain:** `core/decor.py` (new); `core/generate.py` (decor call only); `core/glb.py` (extra
primitive); `core/package.py` (exporter exemption); `docs/PACKAGE_FORMAT.md`; `docs/UNITY_CORE_HANDOFF.md`;
`tests/test_decor.py`; the format-policy fixture tests.

**Dependencies:** S5-STYLE-REVIEW GO.

### Deferred (not scheduled)

* **S5-F1:** tree shape change, which changes `vegetation` collision. It needs explicit user approval and the
  geometry-exception criteria under G0.
* **S5-F2:** rocks and boulders as collision objects from OSM `natural=stone` / `bare_rock`. It needs data and a
  collision-class review.
* **Classic-only follow-ups:** S4-F2 (water texture) and S4-F4/F6 (default tint, landcover staircase) stay
  classic-only.

## Decision record for this spec

| # | Decision | Who |
|---|---|---|
| D141 | U1: stylized is the default; classic stays available and is whole-archive byte-identical to pre-S5 main. | U |
| D142 | U2: visual-only decoration ≤ 0.3 m is allowed, as the last task S5-DECOR, within D101/D110, contingent on the step-1a format fixture and the step-1b glTFast hide proof; it is kept out of the designated flight corridors (tested on its triangles). If any step fails, it stops and escalates, without blocking other tasks. | U (overrides the Design recommendation) |
| D143 | U3: the shore band is colour only on existing triangles; no water re-triangulation; `.mbcol` and `.mbhf` byte-identical. | C (delegated by the user) |
| D144 | U4: lit materials first; `KHR_materials_unlit` may be revisited after S5-STYLE-REVIEW. | C |
| D145 | Trees are appearance-only in S5; no S5 task changes collision geometry. A tree shape change (S5-F1) or any other geometry change needs explicit user approval. | C (user delegated open points; user may change) |
| D157 | Third real-data preset `bellevue-factoria` (user request) for S5 acceptance; see the roadmap. | U |
