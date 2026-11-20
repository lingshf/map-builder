# S3-TEX-BLENDER: textures in the Blender scene and Blender export

Owner: dev · sprint S3 · wave 3 · depends on S3-TEX-UV-CORE · D59, D60

## Scope

* `blender/scene_build.py`:
  * Create a UV map from `MeshData.face_uvs`.
  * Material nodes become Principled BSDF ← Mix(Multiply)(Image Texture (packed PNG from
    `core/textures`), Vertex Colour).
  * Images are packed into the .blend, so there are no external paths.
* `blender/bake.py`: export `TEXCOORD_0` from the UV map and the texture by **material name**
  (the image comes from `core/textures`, not by reading node trees). The output matches the
  CLI writer.
* Panel: a "Textures" checkbox, default on (D60), passed to generation.
* `blender/export.py`: remove the "textures are not exported" note.
* Edited user meshes that lose UVs: faces without UVs get the world-XY fallback at bake time.
  Never fail the export because of this; emit one warning with the count of affected faces.

## Acceptance criteria

1. `tests/blender/checks_textures.py`, run in the headless Blender harness:
   * the synthetic scene has a UV map on every textured object;
   * the images are packed;
   * the exported GLB has `TEXCOORD_0` and `images` and is strictly VALID;
   * toggling textures off reproduces the v0.3.0 material layout.
2. Edit round-trip: add a cube in Blender, export; the cube's faces get fallback UVs and the
   one warning; the package is VALID.
3. The panel-registration assertion includes the new property (D27).
4. Real data: Pittsburgh built in headless Blender with textures is strictly VALID, and the C#
   reader loads it.
5. A demokit render (Cycles CPU) of the synthetic preset, textured vs untextured, is attached
   to the PR.

## Performance considerations

Blender scene build: ≤ +20 % with textures on (median of 3 runs, headless). The PR CI suite is
unchanged: Blender checks run in the local harness or in the release flow, as today.

## Conflict domain

Hard: `blender/scene_build.py`, `blender/bake.py`, `blender/export.py`, `blender/ui.py`, `blender/props.py`,
`blender/operators.py`,
`tests/blender/checks_textures.py` (new). Soft: `tests/blender/run_integration.py` registration.
