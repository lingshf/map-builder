# S5-STYLE: stylized low-poly look for the GLB visuals (direction and tasks)

Owner: design (direction); dev (tasks below) · sprint S5, after v0.5.0 (D136) · decisions D136–D140 · user
decisions U1–U4 at the end

## User direction (verbatim)

> 你参考背景的地图风格，你的地图不用追求逼真，而是首先好看，不要求高硬件，然后才尽量还原真实地图。
>
> 高度和碰撞数据必须准确，因为飞行依赖这个

The reference is a stylized low-poly cartoon map. Only the background terrain art counts, not the UI overlay
(level nodes, labels, path lines). The image is not committed. Its palette is sampled below, and the full image
stays with the coordinator.

## Priorities (D137)

1. **Looks good.** The output matches the reference style: saturated, bright and readable from drone height.
2. **Low hardware cost.** It runs on low-end and mobile GPUs: few materials, opaque, no custom shaders.
3. **Real-map fidelity.** Every object stays where OSM and the DEM put it, and landcover keeps its real class. The
   style changes how things look, not where they are or whether they exist.

**Hard invariant (above all three).** Terrain height (`.mbhf`), `.mbcol` collision, passage probes and the
georeference are accurate and are **never altered for looks**. Every S5-STYLE task keeps
`collision/map.mbcol` and `collision/terrain.mbhf` byte-identical, and keeps the manifest georeference fields,
`report.json` probes, passages and the blocked list equal to the base. This holds for the sample, Munich and
Pittsburgh, through the CLI and Blender, with pinned settings (frozen caches, seed 1, DSM on, offline,
`created_utc = "2026-11-20T00:00:00Z"`). The only exceptions are listed per task (S5-STYLE-TREES; S5-STYLE-WATER
only under U3 option a), and each needs the replay proof stated in that task.

## Visual versus collision (D138)

Today the exporter refuses to publish unless each node's visual and collision triangles correspond one-to-one
(`docs/PACKAGE_FORMAT.md:187–193`; README: "GLB visuals, baked from the final evaluated triangles"). Trees are in
`.mbcol` as class 4 `vegetation`. This rule is revisited here, and **it stays**:

* **Anything a pilot can see as solid stays in collision with the same triangles.** That covers terrain, water,
  roads, buildings, bridges, tunnels, structures, trees and any rock or cliff mesh. A stylized tree is therefore a
  new tree mesh in **both** the visual and the collision.
* **The look comes from attributes that are not geometry:** vertex colours (`COLOR_0`), material base colours,
  flat versus smooth normals, and vertex layout (welding). None of these enter `.mbcol` or `.mbhf`. A task may
  unweld visual vertices for faceted colour only if the exporter correspondence check still passes and `.mbcol`
  stays byte-identical.
* **Visual-only decoration** (flowers, grass tufts, pebbles) is **not allowed** without user decision U2. If U2
  allows it, it must meet all of these:
  * ≤ 0.3 m tall, so it can never look like an obstacle;
  * marked as node `extras.mb_decor = true` (an extras field, no new package member, D110);
  * excluded from the correspondence check by that mark only;
  * counted in the budgets;
  * covered by a positive frozen-reader fixture (D101).
* **Nothing invented is taller than 0.3 m unless it is in collision.** Procedural scatter trees already follow
  this, because they are collision objects.

## Target look (palette sampled from the reference, sRGB)

The swatches include the reference's own lighting, so they are targets for the **rendered** result under the
acceptance lighting below, not raw vertex colours. The palette module (S5-STYLE-PALETTE) converts them and stores
linear values.

| Element | Target sRGB | Source in the reference |
|---|---|---|
| Grass, light / mid | `#b9d17a` / `#96b671` | open meadow, dominant cluster |
| Grass, shaded | `#7ea55b` | meadow near trees |
| Tree foliage, lit / mid / shadow side | `#6f934e` / `#39864c` / `#3d6e69` | faceted cones and blobs |
| Water, open | `#6dc0e7` | river and lake |
| Water, shallow shore band | `#ceeef6` | light band along every shore |
| Sand bank / footpath | `#f2dcae` / `#fdeaa2` | beaches, dirt path |
| Cliff, lit faces / shadowed faces | `#d4b590` / `#70828b` | river cliffs |
| Rock | `#88909c` | boulders |

Further rules:

* **Shading.** The look is faceted (flat-shaded) and soft. Materials are roughness ≈ 1, metallic 0 and opaque.
  There is no alpha blending, water included. A glTF primitive without `NORMAL` must be rendered with flat
  normals (glTF 2.0 specification, mesh attributes), so faceting may cost nothing. S5-STYLE-PALETTE measures this against the
  validator's orientation probes and picks between dropping normals and unwelding.
* **Terrain** is coloured per face by landcover class (real OSM), then by slope. Faces of ≥ 35° use the cliff
  colours, lit or shadowed by facing. Faces in a bank band (≤ 6 m from a built water body, or on a `bank:` ramp)
  use sand. Nothing is moved.
* **Water** is open cyan with a light shore band (see U3 for how the band is built).
* **Trees** are faceted low-poly conifers and broadleaf blobs, two to three variants. The variant comes
  deterministically from the OSM id or the scatter index, and tags (`leaf_type`) choose the type when present.
* **Buildings** use flat-shaded walls from a soft pastel palette, with roofs in a few saturated warm or cool
  colours. Tagged `building:colour` and `roof:colour` are kept as the **hue** but pulled into the palette
  (fidelity P3 under looks P1). There are no facade textures.
* **Roads** are light warm grey; footways, tracks and paths are sand-coloured. The ribbon geometry is unchanged.
* **No textures by default.** The stylized mode embeds no images, so texture memory is 0 and there are no
  `asset_notices`. The S3/S4 detail textures stay available only in the classic mode (U1).

## Low-end budgets (D139)

The first step of S5-STYLE-BASE measures every baseline on main after v0.5.0 (D90). The floors below are relative
to those numbers. Pittsburgh (1.2 × 1 km) is the sizing case.

| Item | Floor (must) | Aim |
|---|---|---|
| Materials (= draw-call groups after merge by material) | ≤ 8 per package | ≤ 6 |
| Shaders | standard glTF PBR metallic-roughness only, no required extension; works with glTFast default shaders on URP (incl. mobile) | — |
| Visual triangles | ≤ baseline + 25 % (trees may add triangles; terrain, roads and buildings add none) | ≤ baseline |
| Visual vertices | ≤ baseline × 2 (unwelding for facets) | ≤ baseline + 25 % |
| Nodes | ≤ baseline (trees stay shared-mesh instances) | — |
| Embedded texture bytes (stylized mode) | 0 | — |
| GLB size | ≤ baseline | ≤ baseline − 20 % |
| Whole Generate, CLI and Blender (D91, D106) | ≤ +5 % vs base | ≤ base |
| Collision size and triangles | unchanged (hard invariant), except S5-STYLE-TREES within its own limit | — |

## Blender and CLI parity, determinism

* One palette and style module in `core/` is used by both paths. The Blender path adds nothing of its own.
* For the same inputs and settings, the CLI and Blender packages have equal visual vertex colours and materials
  per node. This is checked in S5-STYLE-BASE's harness, while today's collision and probe parity continues.
* Two builds with the same inputs are byte-identical. No randomness except seeded by feature id or scatter index;
  no wall-clock or host data in the output.

## Consumer impact (drone-flight-simulator, read-only)

* **Flight is unaffected.** `.mbcol`, `.mbhf` and the probes are unchanged (hard invariant). S5-STYLE-TREES changes
  tree collision shapes within the limits below. The simulator's `GroundBelow` and capsule queries behave as before.
* **Visual import.** It is the same glTF feature set (`COLOR_0`, base colour, metallic-roughness, no extension),
  and glTFast imports it as today. With no textures, the visual is cheaper. A missing `NORMAL` (if chosen) is
  standard glTF; the C# reader and the glTF-Validator CI proxy (D66) confirm it.
* **Format.** Schema stays 2.1.0. If U2 allows decoration, `extras.mb_decor` is additive and needs the D101
  positive fixture. `package_id` changes for every package.
* The simulator owner's own visual check is a user or owner action, not claimed here.

## Visual acceptance method (D140, cheap)

1. **Fixed cameras:** the demokit presets plus three style cameras: a Pittsburgh river bend with banks, a Munich
   roofscape, and a forest edge on the sample. Cameras are stored in `tools/demo/presets/`.
2. **One fixed render setup:** Blender EEVEE, one sun and the world colour as soft ambient, 64 samples,
   1280 × 720. The target is ≤ 2 min for all cameras, CPU fallback allowed. A three.js viewer capture
   (`tools/demo/viewer/`, vendored) is the low-end proxy.
3. **Contact sheet:** for each camera, a reference crop (kept with the coordinator, not committed), the base render
   and the head render side by side. The sheet is attached to the PR, not committed (`docs/demo/` stays REL-only).
4. **Palette check (automatic, information only):** the mean colour of fixed screen regions (grass, water,
   shore band, sand, tree crowns, a cliff where one exists) is compared with the target table. The PR reports
   ΔE2000. Over 15 is flagged for the reviewer, but it does not fail CI.
5. **Verdict:** the reviewer judges the sheet against the user's priority order. The user accepts the look on the
   S5-STYLE-REVIEW sheet before the stylized mode becomes the default (U1).

## Tasks

Each task also has a row in [README.md](README.md#sprint-5-style). Test budget for all of them: D134 (≤ 5 s per
test, no wall-clock asserts, no duplicate cases; renders and real-data runs are PR evidence only). Every task
meets the **hard invariant** AC and the **D91/D106** timing AC unless it lists an exception.

### S5-STYLE-BASE: baselines, metrics and the acceptance harness

* **Change:**
  * add `tools/style_check.py`, which reports materials, visual triangles, vertices, nodes, texture bytes and GLB
    size; checks the hard invariant (byte-compares the collision members, georeference, probes and passages
    between two packages); and computes the palette regions for given renders;
  * add the three style cameras;
  * add the render and contact-sheet recipe to `tools/demo/`.
* **ACs:**
  1. The baseline table (all budget rows) on main after v0.5.0, for the sample, Munich and Pittsburgh through the
     CLI and Blender, is posted in the PR and recorded by Design in the roadmap.
  2. The invariant check fails on a package with one `.mbcol` byte flipped, with one probe moved by 1 mm, and with
     one georeference field changed.
  3. The render recipe produces all cameras in ≤ 2 min on the pinned host.
  4. No generator output changes; the sample is byte-identical.
* **Conflict domain:** `tools/style_check.py`, `tests/test_style_check.py` (both new), `tools/demo/`
  (presets and recipe). No `core/` edits.
* **Dependencies:** REL-v0.5.0 merged (D136).

### S5-STYLE-PALETTE: style option, palette, faceted terrain, buildings and roads

* **Change:**
  * add a new `core/style.py`, which holds the palette, the slope, bank and road-class colour rules, and the
    building and roof palette mapping;
  * add a `style` option (`"stylized"` or `"classic"`) to the CLI, Blender properties and `GenerateOptions`;
  * add flat shading by dropping `NORMAL` or by unwelding, whichever passes the validator's orientation probes
    and costs less; the PR measures both;
  * in stylized mode, embed no textures.
* **ACs:**
  1. Hard invariant, both paths, all three packages.
  2. Classic mode is byte-identical to the base for every package and path.
  3. Budgets: materials, triangles, vertices, nodes, texture bytes and GLB size, with base versus head numbers in
     the PR.
  4. Contact sheet and palette report for every camera; there is no tree or water change yet.
  5. Parity: CLI versus Blender vertex colours and materials are equal per node on the sample, Munich and
     Pittsburgh.
  6. Determinism: two builds of each package are byte-identical.
  7. glTF-Validator (D66) and the C# reader pass on a stylized sample.
* **Tests:**
  * palette rule unit tests: slope threshold, bank band, the road-class mapping, and a tagged colour pulled into
    the palette;
  * one Blender check for the option;
  * classic byte identity on the sample.
* **Conflict domain:**
  * Hard: `core/style.py` (new), `core/generate.py` (the `LANDCOVER_COLORS`, `MATERIALS`, `FACADE_PALETTE` and
    `ROOF_PALETTE` constants and the colour choice in `build_terrain`, buildings and roads; no geometry code),
    `core/glb.py` (normals and welding), `core/uv.py` / `core/textures.py` (mode switch only), `tools/mbmap_cli.py`
    (flag), `blender/props.py`, `blender/ui.py`, `blender/scene_build.py` (option plumbing).
  * Soft: sample slot (D103) only if the default changes, which it does not before U1.
* **Dependencies:** S5-STYLE-BASE.

### S5-STYLE-TREES: faceted low-poly trees

* **Change:**
  * replace `tree_mesh()` with two or three faceted variants: a conifer and broadleaf blobs, ≤ 48 triangles each,
    shared meshes;
  * the variant comes from the id or index plus `leaf_type`;
  * the mesh is the same in the visual and in collision class 4.
* **Hard-invariant exception:** only `vegetation` triangles in `.mbcol` change. The ACs below must hold.
* **ACs:**
  1. Fixed-query replay (as D116), Python and C#: every changed hit is class `vegetation`. Terrain, road, water,
     building and bridge hits are unchanged.
  2. Every passage probe is still passable, and the blocked list is unchanged. The D21 rule still keeps trees out of
     probe clearances.
  3. No tree is taller than the old one by more than 10 %, and each tree's footprint stays within its old crown
     radius + 0.3 m, so tree density and obstacle placement read the same.
  4. Total visual triangles stay within the budget, and tree instances still share a mesh.
  5. Contact sheet (forest-edge camera) and palette check.
  6. Classic mode keeps today's tree byte-identical.
* **Conflict domain:** `core/generate.py` (`tree_mesh`, `TREE_UNIT_HEIGHT` and the tree loop's mesh choice only),
  `core/style.py` (tree colours), `tests/test_scene_generation.py` (tree cases) or a new `tests/test_trees.py`; soft: sample slot.
* **Dependencies:** S5-STYLE-PALETTE (shares `core/style.py` and `generate.py`).

### S5-STYLE-WATER: cyan water, shore band and sandy banks

* **Change:**
  * water and shore-band colours;
  * the terrain bank band and the `bank:` ramps in sand;
  * the light shore band on the water, built as U3 decides.
* **ACs:**
  1. Hard invariant. Under U3 option (a), the exception is the water triangles only, and needs:
     * the D98 hit-equivalence replay on a deterministic ray grid over every body, where hits match in class and
       in Z within 1e-6 m;
     * every probe unchanged;
     * the S4-COL-FLOAT-2 floating audit still at 0 `water_above_bank` and 0 `water_buried`.
  2. Budgets.
  3. Contact sheet with the river-bend and bridge-under cameras; the palette check includes the shore band.
  4. The water stays opaque, with no transparency or extra material beyond the budget.
* **Conflict domain:** `core/water.py`, `core/shore.py` (colour and band only), `core/style.py`, the water-stage
  colour code in `core/generate.py`; soft: sample slot.
* **Dependencies:** S5-STYLE-PALETTE; v0.5.0 released (`core/water.py` and `core/shore.py` free after #77).
  Serialised after S5-STYLE-TREES because both use `core/style.py` and `generate.py`.

### S5-STYLE-REVIEW: design milestone review and the user's look check

* **Scope:**
  * a contact sheet of every camera, before and after, with the reference;
  * the budget table, the invariant evidence and the test audit;
  * the GO/NO-GO verdict, which carries U1 to the user;
  * `design/` only.
* **Dependencies:** all S5-STYLE dev tasks. It then precedes the next REL task; the release itself is a user
  decision.

Order: **BASE → PALETTE → TREES → WATER → REVIEW**. These tasks are serial because PALETTE, TREES and WATER share
`core/style.py` and `core/generate.py`. BASE can start as soon as v0.5.0 has merged.

Deferred, not scheduled: rocks and boulders as `prop` collision objects from OSM `natural=stone` / `bare_rock`, which
needs data and a collision-class review; also visual-only decoration (U2). S4-F2 (water texture) and S4-F4/F6
(default tint, landcover staircase) are superseded in stylized mode and stay classic-only follow-ups.

## Decisions for the user

* **U1, default look.** Should stylized become the default after S5-STYLE-REVIEW, with classic kept as an option?
  The recommendation is yes, because classic stays byte-identical for anyone who needs it.
* **U2, visual-only decoration.** Should small decoration with no collision be allowed (flowers, tufts ≤ 0.3 m,
  marked `mb_decor`)? It would look closer to the reference, but it breaks "what you see is what you hit" for
  those items. The recommendation is not in S5.
* **U3, shore band on water.** One option is to re-triangulate the water sheet with a band ring (a). That
  changes the `.mbcol` water triangles while keeping the same flat surface, proven by the replay. The other is to
  approximate the band on the terrain side only (b), with no collision change but a weaker look. The
  recommendation is (a).
* **U4, unlit look.** Should the soft lighting be baked into vertex colours under a `KHR_materials_unlit`
  material? That is cheaper and closer to the reference, but it is an extension and needs a D101 fixture. The
  alternative is standard lit materials. The recommendation is lit first, revisiting after REVIEW.
