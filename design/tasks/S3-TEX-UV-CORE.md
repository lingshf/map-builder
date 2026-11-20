# S3-TEX-UV-CORE: UV assignment, textured CLI export, sample owner

Owner: dev · sprint S3 · wave 2 · depends on S3-TEX-FORMAT, S3-TEX-ASSETS · D57, D59, D60, D64

## Goal

CLI packages get world-scaled UVs and textured materials. UVs are assigned **after**
generation in a new module, `core/uv.py`, so `generate.py` and `roofs.py` are not edited.

This task is the **only S3 task that changes `examples/synthetic_sample.mbmap`** (D64):

* it flips `PACKAGE_SCHEMA_VERSION` to `"2.1.0"`;
* it regenerates the sample, textured;
* it updates the sample rows of `docs/VALIDATION.md` "Recorded results".

## UV rule

* **Units.** UV = metres / tile size. The tile sizes come from `core/textures.py`.
* **Tile offset, one per mesh.** Each mesh gets one offset `o = tile · floor(origin / tile)`,
  where `origin` is the mesh's world origin (its local frame centre). It is subtracted before
  scaling. Faces of the same mesh share the offset, so UVs are continuous across their shared
  edges. Values stay ≤ (mesh extent / tile) + 1, which is float32-safe for 2 km meshes. There
  are no per-face offsets.
* **Per material:**

  | Material | U | V |
  |---|---|---|
  | `MB Facade` (walls) | the cumulative perimeter distance along the footprint ring from ring vertex 0 | z − wall base z |
  | `MB Facade` (gable ends) | the same U as the wall below, so they continue the wall | z − wall base z |
  | `MB Roof` | per roof plane: distance along the plane's eave (horizontal) direction | up-slope distance |
  | `MB Terrain`, `MB Road` | world X | world Y (after the mesh offset) |
  | `MB Concrete`, `MB Tunnel` | box projection by the dominant normal axis | box projection by the dominant normal axis |
  | Others (`MB Probe`, `MB Foliage`, `MB Bark`, `MB Default`) | untextured, no `TEXCOORD_0` | untextured, no `TEXCOORD_0` |

  Facade walls have one seam per ring, at ring vertex 0, where U jumps by the perimeter. Roof
  planes meet at seams at hips and ridges. Box projection has seams where the dominant axis
  changes.
* **Shared corners.** UVs are per face corner, and the GLB writer emits per-triangle vertices.
  A corner shared by two faces of the same material and projection must get the same UV,
  except at the seams listed above.

## Scope

* `core/uv.py`: `assign_uvs(mesh, ...)` implements the rule above.
* `core/pipeline.py` (export path): call `assign_uvs` before `write_glb`. Textured materials get
  `baseColorTexture`, with the existing factor kept and COLOR_0 kept.
* **Notices (D65).** When textures are on, pass one `asset_notices` entry to the package writer
  (the API added by S3-TEX-FORMAT): name "map-builder procedural textures"; attribution
  "map-builder procedural textures (own work)"; licence `CC0-1.0` with name, URL and text; the
  SHA-256 of each embedded PNG. The entry comes from `core/textures.py`. `sources[]` is
  unchanged, and this task does not edit `core/package.py`.
* CLI: `--textures/--no-textures`, default **on** (D60). `--no-textures` gives a 2.1.0 package
  whose GLB equals today's untextured GLB, apart from the manifest version fields.

## Acceptance criteria

1. **Exact corners.** A fixed building (a 10 × 6 m L-footprint wall ring, a 6 m wall, a hipped
   plane), a 2 × 2 terrain cell and a road quad are built at a world origin of x = 2000 m. The
   test decodes the **exported GLB** and asserts the expected `TEXCOORD_0` of every corner,
   ±1e-6:
   * facade V spans 0 → 6 m / tile;
   * facade U is continuous across every wall corner except the ring-start seam;
   * roof U runs along the eave;
   * terrain and road UVs = (XY − mesh offset) / tile;
   * all |UV| ≤ extent / tile + 1.
2. **Seams.** For every shared edge between two faces of the same mesh and material, the UVs
   on both sides are equal, except the documented seams. The test counts the seams and
   asserts the expected number.
3. **Material bindings** in the exported GLB:
   * each textured material's `baseColorTexture` → the texture → the image whose bytes have
     the SHA-256 of `core/textures.py`'s PNG for that material;
   * every primitive with a textured material has `TEXCOORD_0`;
   * untextured primitives (Probe, Foliage, Bark, Default) have none.
4. **Sample.** The sample is regenerated with textures and is strictly VALID. `--no-textures` on
   the same input gives the pre-S3 GLB bytes. `NOTICES.txt` has the CC0 "Assets" section.
   The 2.1 validator rejects a copy whose `asset_notices` is removed (texture without provenance).
   The S3-TEX-FORMAT CI step, the frozen v0.3.0 Python and C# readers, accepts this regenerated
   committed sample with 0 warnings.
5. **Real data.** Pittsburgh, built with textures, is strictly VALID in Python and loaded by the
   C# reader. The frozen v0.3.0 Python validator and C# reader also accept this exact package
   (output in the PR). Record the GLB size before and after: the target is ≤ +35 % plus the fixed
   texture bytes (D60). `.mbcol` bytes are identical with textures on and off.

## Performance considerations

UV assignment is O(face corners) and is measured as its own stage. The budget is ≤ +20 % of the
fixture build (D35), taken as the median of 3 runs. Measure on the same input at `v0.3.0` and
at the head (the sample input is unchanged by roof tasks, D64). New tests ≤ 5 s each.

## Conflict domain

Hard:
* `core/uv.py` (new) and `tests/test_uv.py` (new);
* `core/pipeline.py` (export call site, `asset_notices` argument) and `tools/mbmap_cli.py`;
* `core/__init__.py` (schema version);
* `examples/synthetic_sample.mbmap` (sole S3 owner);
* the sample rows of `docs/VALIDATION.md`.

Soft: README CLI section.
