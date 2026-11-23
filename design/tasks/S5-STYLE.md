# S5-STYLE: stylized low-poly look for the GLB visuals (direction and tasks)

Owner: design (direction); dev (tasks below) · sprint S5 · decisions D136–D145

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

* **Packages:** the sample, Munich and Pittsburgh.
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

S5-STYLE-BASE measures every baseline on main at the S5 start, both modes, for the sample, Munich and Pittsburgh
(D90). Pittsburgh is the sizing case.

**Cumulative rule.** Each implementation task reports every row twice:

* against the S5-BASE baseline: cumulative, and this must stay within the floor;
* against its own base: incremental, reported with D106 alternating rounds for timing.

| Item | How it is counted | Floor (must, cumulative) |
|---|---|---|
| Material definitions | glTF `materials[]` length | ≤ 8 |
| Draw submissions | Σ over rendered node instances of their primitives, counted statically from the GLB; trees count once per instance | ≤ baseline; S5-DECOR ≤ baseline + 2 % |
| Runtime frame time (proxy) | Labelled proxy, not a device: the vendored three.js viewer (`tools/demo/viewer/`) in headless Chromium with SwiftShader software rendering, 1280 × 720, fixed Pittsburgh overview camera; median frame time over 300 frames after 60 warm-up frames; same host, alternating base/head runs | ≤ baseline + 10 % |
| Render memory (proxy) | vertex-buffer bytes + index-buffer bytes + texture bytes in the GLB | ≤ baseline |
| Visual triangles | from the GLB | = baseline; S5-DECOR ≤ baseline + 10 % |
| Visual vertices | from the GLB | ≤ baseline × 2 (unwelding) |
| Embedded texture bytes (stylized) | images in the GLB | 0 |
| GLB size | bytes | ≤ baseline; S5-DECOR ≤ baseline + 10 % |
| Generate time (D91, D106) | **CLI whole Generate**, **Blender Generate** and **Blender Generate+Export**, each reported separately | each ≤ +5 % vs the task's base |

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
* **S5-DECOR:** decoration is visual-only. Consumers can identify it by its marking, it has no collision, and the
  simulator's `.mbcol` queries never see it.
* **Format:** schema stays 2.1.0 unless S5-DECOR's feasibility step fails (see that task). `package_id` changes
  for every stylized package.
* The simulator owner's visual check is a user or owner action and is not claimed here.

## Visual acceptance method (D140)

1. **Cameras:** the demokit presets plus three style cameras: a Pittsburgh river bend with banks, a Munich
   roofscape and a forest edge on the sample. Cameras are stored in `tools/demo/presets/`.
2. **Render:** Blender EEVEE, one sun and the world colour as soft ambient, 64 samples, 1280 × 720.
3. **Contact sheet:** for each camera, the reference crop (held by the coordinator), the base render and the head
   render side by side. It is attached to the PR, not committed (`docs/demo/` is for REL only).
4. **Palette report:** mean colour of fixed screen regions compared with the target table, as ΔE2000. This is
   information only; a value above 15 is flagged to the reviewer.
5. **Verdict:** the reviewer judges the sheet against the user's priority order. **S5-STYLE-REVIEW is an explicit
   GO/NO-GO** on the G0 evidence, classic identity, the cumulative budgets and the sheets.

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

Every implementation task meets **G0**, **classic identity**, the **cumulative budgets** and **D91 timing**
(three series), and attaches the contact sheet and the palette report. Test budget: D134 (≤ 5 s per test, no
wall-clock asserts, no duplicate cases; renders and real-data runs are PR evidence only).

Order: **BASE → PALETTE → WATER → REVIEW**, then **DECOR** last. Nothing waits on DECOR.

### S5-STYLE-BASE: baselines, metrics, G0 checker and acceptance harness

* **Change:**
  * `tools/style_check.py` (new): G0 and its negative cases; classic whole-archive identity; the member diff
    between classic and stylized; every budget row (materials, draw submissions, render memory, triangles,
    vertices, texture bytes, GLB size); per-node CLI-versus-Blender colour and material parity; and the palette
    regions for given renders;
  * the runtime frame-time proxy runner (headless Chromium, SwiftShader, the vendored viewer);
  * the three style cameras and the render and contact-sheet recipe in `tools/demo/`.
* **ACs:**
  1. The baseline table (every budget row, both modes, the sample, Munich and Pittsburgh, CLI and Blender, plus
     the three D91 series) is posted in the PR. Design records it in the roadmap.
  2. `tests/test_style_check.py` covers each G0 negative case and one classic-identity negative case (a single
     GLB byte change).
  3. The frame-time proxy repeats within ±5 % over three runs of the same package on the pinned host; otherwise
     the PR proposes a more stable proxy before PALETTE starts.
  4. The render recipe produces all cameras in ≤ 2 min.
  5. No generator output changes; the sample is byte-identical.
* **Conflict domain:** `tools/style_check.py`, `tests/test_style_check.py` (both new), `tools/demo/` (presets,
  recipe, proxy runner). No `core/` edits.
* **Dependencies:** #75 merged (D136).

### S5-STYLE-PALETTE: style option (default stylized), palette, faceting, terrain, buildings, roads and trees

* **Change:**
  * `core/style.py` (new): the palette; the slope, bank-band and road-class rules; the building and roof mapping;
    and tree tinting and facet shading;
  * a `style` option (`"stylized"` by default, or `"classic"`) in the CLI, Blender properties and
    `GenerateOptions`;
  * faceting by dropping `NORMAL` or by unwelding, whichever is measured best;
  * no textures in stylized mode.
* **ACs:**
  1. G0, classic identity and the cumulative budgets on every package and path.
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
* **Dependencies:** S5-STYLE-BASE; #75 merged; S4-MYPY merged (it shares `generate.py` and `glb.py` typing).

### S5-STYLE-WATER: cyan water, terrain-side shore band, sandy banks (colour only)

* **Change:**
  * water body colour;
  * the shallow-band and sand colours on the terrain faces next to built water and on the `bank:` ramps, colour
    only (D143);
  * no new vertices, no re-triangulation, no transparency.
* **ACs:**
  1. G0, classic identity and the cumulative budgets. Visual triangles per water, terrain and `bank:` node are
     unchanged.
  2. The S4-COL-FLOAT-2 floating audit is unchanged from the base (0 `water_above_bank`, 0 `water_buried`).
  3. Contact sheets with the river-bend and bridge-under cameras; the palette report includes the shore band.
* **Conflict domain:** `core/style.py` (water and band colours), the water-stage and `bank:` colour code in
  `core/generate.py`, `core/water.py` and `core/shore.py` (colour only); soft: sample slot.
* **Dependencies:** S5-STYLE-PALETTE (it shares `core/style.py` and `generate.py`); U3 resolved as colour-only
  (D143); #75 merged, which means #77 has merged too.

### S5-STYLE-REVIEW: design milestone review (GO/NO-GO)

* **Scope:** `design/` only.
* **Evidence:** G0 and classic identity for every package, path and mode; cumulative budgets against the S5-BASE
  baseline; the contact sheets; and the test audit (D134).
* **Verdict:** explicit **GO or NO-GO**. A NO-GO names the failing evidence and the S5-Fn fix tasks.
* **Dependencies:** S5-STYLE-BASE, PALETTE and WATER. S5-DECOR is not a dependency.

### S5-DECOR: visual-only decoration ≤ 0.3 m (last; contingent)

The user allowed it (U2, D142). It runs last, and nothing else waits on it.

**Step 1, feasibility (no merge).** Today a triangle node without a same-name collision object is rejected by the
validator (`core/package.py:1747`) and by the frozen readers. A separate decoration node is therefore not possible
in 2.x, and D110 forbids new package members. The candidate within 2.1.0 is:

* decoration is an **additional primitive inside an existing terrain node's mesh**;
* the primitive uses material `MB Decor` and carries primitive `extras.mb_decor = true`;
* its triangles always lie inside the host node's collision AABB, within the existing tolerance.

The developer builds a **genuine exported package**: the real exporter path, not a hand-made GLB. The fixture must
show all of these:

* the current Python validator and C# reader report no new error or warning;
* the frozen v0.3.0 Python and C# readers accept it (the D101 positive fixture);
* the current exporter's 1:1 GLB-to-`.mbcol` name binding still holds;
* the orientation probes pass;
* glTF-Validator is clean.

If any check fails, stop. Design then writes the minimal minor-format change (for example 2.2.0, declaring decor
primitives) and flags it to the coordinator. BASE, PALETTE, WATER and REVIEW are not blocked.

**Step 2, implementation (only after step 1 passes):**

* Content: small grass tufts, flowers and pebbles, placed deterministically (seeded by area id) on grass and
  forest landcover only.
* Height: each instance ≤ 0.3 m above the terrain under it. A test enforces this on the emitted triangles.
* Exclusions, each enforced by a test: never on road ribbons, water bodies, `bank:` ramps, bridge decks or building
  footprints; never inside a passage-probe capsule's swept volume dilated by 1 m.
* The exporter exempts only primitives marked `mb_decor`, and only from the 1:1 triangle correspondence. The node
  name binding and every other check stay.
* Documented in `docs/PACKAGE_FORMAT.md` and `docs/UNITY_CORE_HANDOFF.md`: consumers may hide decoration by its
  marking, and it is never collidable.
* **ACs:**
  1. G0 holds: decoration never touches `.mbcol` or `.mbhf`.
  2. Classic identity: no decoration in classic mode.
  3. The DECOR budget rows.
  4. The step-1 fixture is persisted as a CI test.
  5. Contact sheet.
* **Conflict domain:** `core/decor.py` (new); `core/generate.py` (decor call only); `core/glb.py` (extra
  primitive); `core/package.py` (exporter exemption); `docs/PACKAGE_FORMAT.md`; `docs/UNITY_CORE_HANDOFF.md`;
  `tests/test_decor.py`; the format-policy fixture tests.
* **Dependencies:** S5-STYLE-REVIEW GO.

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
| D142 | U2: visual-only decoration ≤ 0.3 m is allowed, as the last task S5-DECOR, within D101/D110, contingent on the step-1 fixture; otherwise a minimal minor change is specified and flagged, without blocking other tasks. | U (overrides the Design recommendation) |
| D143 | U3: the shore band is colour only on existing triangles; no water re-triangulation; `.mbcol` and `.mbhf` byte-identical. | C (delegated by the user) |
| D144 | U4: lit materials first; `KHR_materials_unlit` may be revisited after S5-STYLE-REVIEW. | C |
| D145 | Trees are appearance-only in S5; no S5 task changes collision geometry. A tree shape change (S5-F1) or any other geometry change needs explicit user approval. | C (user delegated open points; user may change) |
