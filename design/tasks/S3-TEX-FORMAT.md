# S3-TEX-FORMAT: package format 2.1.0, UVs and embedded textures in GLB

Owner: dev · sprint S3 · wave 1 · D57, D58

## Goal

Let `visual/map.glb` carry glTF 2.0 core PBR textures, staying self-contained, and bump the
package schema **2.0.0 → 2.1.0** (minor, additive). `.mbcol` and the heightfield do not change.

## Scope

* `core/mesh.py`: optional per-face-corner UVs `MeshData.face_uvs` (`None` = no UVs). Existing
  callers are unaffected.
* `core/glb.py` `write_glb`:
  * Emit `TEXCOORD_0` (float32 VEC2) for primitives whose mesh has UVs.
  * Materials may name an image. Write `images` (bufferView + `image/png`, inside the single
    BIN buffer), `textures`, and one `sampler` (REPEAT/REPEAT, LINEAR_MIPMAP_LINEAR/LINEAR).
  * `pbrMetallicRoughness.baseColorTexture` with `texCoord: 0`. Keep `baseColorFactor` and
    COLOR_0. Each image is written once even when several materials share it.
  * Without UVs or images the output is byte-identical to v0.3.0 (except the version string).
* `core/glb.py` validator. Error conditions:
  * an image that is not embedded, or a URI of any kind;
  * a MIME type other than `image/png`;
  * a PNG signature or size that does not match its IHDR;
  * a side that is not a power of two, or larger than 1024;
  * total image bytes > `MAX_TEXTURE_BYTES` (4 MiB);
  * a texture or sampler index out of range;
  * `TEXCOORD_0` count ≠ POSITION count;
  * non-finite UVs;
  * any extension in `extensionsRequired`.
* `core/__init__.py`: `PACKAGE_SCHEMA_VERSION = "2.1.0"`. The D50 drift guard and the
  `GENERATOR_VERSION` bump belong to REL-v0.4.0.
* C# `examples/csharp/MbmapReader`: parity for the same checks. Accept 2.0 and 2.1, and reject
  an unknown major as today.
* `docs/PACKAGE_FORMAT.md`: 2.1.0 changelog. Textures are optional; consumers that ignore them
  still render factor plus vertex colour.

## Acceptance criteria

1. A unit test builds a 2-triangle mesh with UVs and a 4×4 PNG. The GLB round-trips: the
   validator accepts it, and the parsed JSON has the expected image, texture, sampler and
   `TEXCOORD_0`.
2. Each error condition above has one negative test that fails with a named error, in both
   Python and C# (shared fixture bytes).
3. Without textures, `examples/synthetic_sample.mbmap` differs from v0.3.0 only in the version
   fields. This is shown by a test diffing the parsed GLB JSON and BIN.
4. The C# reader loads the v0.3.0 Pittsburgh package (2.0.0) and a 2.1.0 textured test package.
   Real-data check: in the PR, run `MbmapReader` on the Pittsburgh package that S3 builds.
5. `PACKAGE_FORMAT.md` and `UNITY_CORE_HANDOFF.md` (materials checklist) are updated.

## Performance considerations

The writer cost is O(images + UV floats). The validator checks the PNG header only (no
decode). New tests run in ≤ 5 s.

## Conflict domain

Hard: `core/glb.py`, `core/mesh.py`, `core/__init__.py` (schema version only),
`examples/csharp/MbmapReader/**`, `docs/PACKAGE_FORMAT.md`, `tests/test_package.py`,
`tests/test_csharp_parity.py`. Soft:
`docs/UNITY_CORE_HANDOFF.md`.
