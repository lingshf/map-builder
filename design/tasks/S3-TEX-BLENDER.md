# S3-TEX-BLENDER: textures in the Blender scene and Blender export

Owner: dev · sprint S3 · wave 3 · depends on S3-TEX-UV-CORE · D59, D60, D64

## Scope

* **Scene build** (`blender/scene_build.py`):
  * create a UV map from `MeshData.face_uvs`, which `core/uv.py` produces with the same rule as
    the CLI;
  * set the material nodes to Principled BSDF ← Mix(Multiply)(Image Texture, Vertex Colour);
  * pack the images (packed PNG from `core/textures`) into the .blend.
* **Export** (`blender/bake.py`):
  * export `TEXCOORD_0` from the UV map;
  * bind the texture by **material name**; the image comes from `core/textures`, not from the
    node trees;
  * the output must match the CLI writer's layout and bindings.
* **Notices (D65):** when textures are on, pass the same `asset_notices` entry from
  `core/textures.py` to the package writer, as the CLI does. `blender/sources.py` lists it in
  the panel's attribution text. `sources[]` and `core/package.py` are unchanged.
* **UI**: a "Textures" checkbox, default on (D60), in `props.py`, `ui.py` and `operators.py`.
* `blender/export.py`: drop the "textures are not exported" note.
* **Edited meshes.** User meshes without UVs get the world-XY rule (with the per-mesh offset) at
  bake time, plus one warning with the face count. Export is never failed because UVs are
  missing.

## Acceptance criteria

1. `tests/blender/checks_textures.py` (new), registered in `run_integration.py`, passes these
   checks on the synthetic scene:
   * every textured object has a UV map;
   * the images are packed;
   * the exported GLB passes the S3-TEX-UV-CORE corner, seam and binding assertions, reused
     from `tests/test_uv.py` helpers;
   * the exported GLB is strictly VALID;
   * per-material UVs equal the CLI's within 1e-5;
   * the "Textures" checkbox off reproduces the untextured layout.
2. Edit round trip: add a cube and export. It gets fallback UVs and exactly one warning, and the
   package is VALID.
3. The panel-registration assertion includes the new property (D27).
4. Real data: Pittsburgh built in headless Blender with textures is strictly VALID, and the C#
   reader loads it. Its `NOTICES.txt` has the CC0 Assets section, and the frozen v0.3.0 Python and
   C# readers accept it.
5. A demokit render (Cycles CPU) of the synthetic preset, textured vs untextured, is attached
   to the PR.

## Performance considerations

Blender scene build ≤ +20 % with textures on (headless, median of 3). PR CI is unchanged;
Blender checks stay in the local harness.

## Conflict domain

Hard: `blender/scene_build.py`, `blender/bake.py`, `blender/export.py`, `blender/sources.py`,
`blender/ui.py`, `blender/props.py`, `blender/operators.py`, `tests/blender/checks_textures.py`
(new). Soft: `tests/blender/run_integration.py` (one appended registration line). Does not touch
the sample (D64).
